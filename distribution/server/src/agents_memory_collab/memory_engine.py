"""Common Hindsight adapter. Deployment location never selects a memory algorithm."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import urllib.error
import urllib.request
from urllib.parse import quote, urlsplit

from .models import Failure

CONTRACT = "agents-memory-grounded-v1"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Failure(503, "memory_backend_redirect_refused")


class HindsightEngine:
    contract = CONTRACT

    def __init__(self, url, processor, *, generative=False, source_preserving=False):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError(
                "Hindsight must be an internal loopback endpoint; expose only the authenticated gateway"
            )
        if getattr(processor, "contract", None) != CONTRACT:
            raise ValueError("A matching memory processor is required")
        self.url, self.processor = url.rstrip("/"), processor
        self.generative = generative
        self.source_preserving = source_preserving
        self.free_generation = generative and not source_preserving
        # Local internal calls must not send source data through the HTTP proxy.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def _request(self, path, value=None, method=None):
        payload = (
            None if value is None else json.dumps(value, ensure_ascii=False).encode()
        )
        request = urllib.request.Request(
            self.url + path,
            data=payload,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with self.opener.open(request, timeout=120) as response:
                raw = response.read(2_097_153)
                if len(raw) > 2_097_152:
                    raise Failure(503, "memory_backend_response_too_large")
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise Failure(503, "memory_backend_unavailable") from None
        except (OSError, ValueError):
            raise Failure(503, "memory_backend_unavailable") from None

    async def request(self, *args, **kwargs):
        return await asyncio.to_thread(self._request, *args, **kwargs)

    @staticmethod
    def bank(user, project):
        return "am-" + hashlib.sha256((str(user) + "\0" + project).encode()).hexdigest()

    @staticmethod
    def document(op):
        return "am-" + str(op.memory_id) + "-" + str(op.op_id)

    async def health(self):
        result = await self.request("/health/ready")
        if (
            not isinstance(result, dict)
            or result.get("status") != "healthy"
            or result.get("database") != "connected"
        ):
            raise Failure(503, "memory_backend_unavailable")
        return {
            "contract": CONTRACT,
            "engine": "hindsight",
            "extraction": "source_passages",
            "consolidation": (
                "source_preserving_observations"
                if self.source_preserving
                else "generated_observations"
            )
            if self.generative
            else "not_required_no_generated_observations",
            "integration_enabled": self.generative,
            "generation_enabled": self.free_generation,
        }

    async def prepare(self, source):
        try:
            value = await self.processor.process(source)
        except Exception as error:  # noqa: BLE001 - never expose provider payloads or credentials
            terminal = {
                "review_required": "memory_requires_review",
                "candidate_budget": "memory_candidate_budget_exceeded",
                "request": "memory_input_invalid",
                "secret_source": "memory_source_contains_credentials",
            }
            if getattr(error, "kind", None) in terminal:
                raise Failure(422, terminal[error.kind]) from None
            raise Failure(503, "memory_provider_retryable") from None
        if (
            not isinstance(value, dict)
            or value.get("contract") != CONTRACT
            or value.get("decision") not in {"keep", "discard"}
            or value.get("extraction") != "source_passages"
            or value.get("consolidation") != "not_required_no_generated_observations"
        ):
            raise Failure(503, "invalid_memory_processing_result")
        passages = value.get("passages")
        if not isinstance(passages, list) or len(passages) > 16:
            raise Failure(503, "invalid_memory_processing_result")
        last = 0
        for item in passages:
            if (
                not isinstance(item, dict)
                or set(item) != {"start", "end", "text"}
                or type(item["start"]) is not int
                or type(item["end"]) is not int
                or not last <= item["start"] < item["end"] <= len(source)
                or item["text"] != source[item["start"] : item["end"]]
                or not item["text"].strip()
            ):
                raise Failure(503, "ungrounded_memory_processing_result")
            last = item["end"]
        if bool(passages) != (value["decision"] == "keep"):
            raise Failure(503, "invalid_memory_processing_result")
        return value

    async def index(self, bank, document, prepared):
        text = "\n".join(item["text"] for item in prepared["passages"])
        await self.request("/v1/default/banks/" + bank, {}, "PUT")
        path = "/v1/default/banks/" + bank
        settings = await self.request(path + "/config")
        resolved = settings.get("config", {}) if isinstance(settings, dict) else {}
        if (
            resolved.get("retain_extraction_mode")
            != ("concise" if self.free_generation else "chunks")
            or resolved.get("enable_observations") is not self.generative
            or resolved.get("enable_auto_consolidation") is not False
        ):
            raise Failure(503, "memory_backend_contract_mismatch")
        # Existing deterministic document content is the retry witness after a lost ACK.
        prior = await self.document_record(bank, document)
        if prior is None:
            result = await self.request(
                path + "/memories",
                {
                    "async": False,
                    "items": [
                        {
                            "content": text,
                            "document_id": document,
                            "metadata": prepared.get("metadata", {}),
                        }
                    ],
                },
            )
            if not isinstance(result, dict) or result.get("async") is not False:
                raise Failure(503, "memory_index_not_confirmed")
        elif prior.get("original_text") != text or (
            prior.get("document_metadata") or {}
        ) != prepared.get("metadata", {}):
            raise Failure(409, "memory_document_identity_reused")
        confirmed = await self.document_record(bank, document)
        if (
            confirmed is None
            or confirmed.get("original_text") != text
            or (confirmed.get("document_metadata") or {})
            != prepared.get("metadata", {})
        ):
            raise Failure(503, "memory_index_not_confirmed")
        if self.generative:
            if not confirmed.get("memory_unit_count"):
                raise Failure(503, "memory_generation_empty")
            await self.integrate(bank)
        return text

    async def integrate(self, bank):
        path = "/v1/default/banks/" + bank
        operation = await self.request(path + "/consolidate", {})
        if not isinstance(operation, dict) or not isinstance(
            operation.get("operation_id"), str
        ):
            raise Failure(503, "memory_integration_not_confirmed")
        deadline = asyncio.get_running_loop().time() + 180
        while asyncio.get_running_loop().time() < deadline:
            status = await self.request(
                path + "/operations/" + quote(operation["operation_id"], safe="")
            )
            state = status.get("status") if isinstance(status, dict) else None
            if state == "completed":
                return
            if state in {"failed", "cancelled"}:
                raise Failure(503, "memory_integration_failed")
            await asyncio.sleep(0.2)
        raise Failure(503, "memory_integration_pending")

    async def read(self, bank, document):
        value = await self.document_record(bank, document)
        return None if value is None else value.get("original_text")

    async def document_record(self, bank, document):
        return await self.request(
            "/v1/default/banks/" + bank + "/documents/" + quote(document, safe="")
        )

    async def delete(self, bank, document):
        await self.request(
            "/v1/default/banks/" + bank + "/documents/" + quote(document, safe=""),
            method="DELETE",
        )
        if await self.read(bank, document) is not None:
            raise Failure(503, "memory_delete_not_confirmed")

    async def recall(self, bank, query):
        options = {"query": query, "budget": "high", "max_tokens": 8192}
        if self.generative:
            options.update(
                types=["observation", "world", "experience"],
                include={"source_facts": {"max_tokens": 12000}, "entities": None},
            )
        value = await self.request(
            "/v1/default/banks/" + bank + "/memories/recall", options
        )
        if value is None:
            return []
        results = value.get("results")
        if not isinstance(results, list):
            raise Failure(503, "invalid_memory_recall")
        if not self.generative:
            return results
        sources = value.get("source_facts") or {}
        nominated = []
        for hit in results:
            if not isinstance(hit, dict) or not isinstance(hit.get("text"), str):
                continue
            if hit.get("type") == "observation":
                ids = hit.get("source_fact_ids")
                if (
                    not isinstance(ids, list)
                    or not ids
                    or any(
                        not isinstance(i, str)
                        or i not in sources
                        or not isinstance(sources[i], dict)
                        or not isinstance(sources[i].get("document_id"), str)
                        for i in ids
                    )
                ):
                    continue  # Incomplete provenance never authorizes generated text.
                documents = sorted({sources[i]["document_id"] for i in ids})
            elif isinstance(hit.get("document_id"), str):
                documents = [hit["document_id"]]
            else:
                continue
            nominated.append({**hit, "source_documents": documents})
        return nominated


def from_environment():
    url = os.environ.get("AM_MEMORY_HINDSIGHT_URL")
    if not url:
        return None
    try:
        from agents_memory.memory_processor import from_environment as processor

        processing = os.environ.get("AM_MEMORY_PROCESSING")
        return HindsightEngine(
            url,
            processor(),
            generative=processing in {"generative", "integrated"},
            source_preserving=processing == "integrated",
        )
    except Exception:  # noqa: BLE001 - private configuration error boundary
        raise Failure(503, "memory_processor_configuration_invalid") from None
