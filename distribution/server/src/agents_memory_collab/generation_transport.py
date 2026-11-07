"""Private transport on the existing gateway, exclusively for its Hindsight child."""

from __future__ import annotations

import asyncio
import json
import os
import secrets

from starlette.requests import Request

from .web import MAX_BODY, response

PATH = "/_internal/memory-generation/v1/chat/completions"
SAFE_FAILURES = frozenset({
    "request", "unsupported_integration_request", "unsupported_integration_schema",
    "invalid_integration_identity", "ambiguous_integration_input", "integration_budget",
    "integration_requires_review", "transport", "response", "rate_limited",
    "overloaded", "unauthorized", "configuration", "unavailable",
})


class PrivateGeneration:
    def __init__(self, app, generator, token):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("A fresh private generation token is required")
        self.app, self.generator, self.token = app, generator, token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != PATH:
            return await self.app(scope, receive, send)
        headers = scope.get("headers", [])
        authorization = [v for k, v in headers if k.lower() == b"authorization"]
        peer = scope.get("client") or (None, None)
        permitted = (
            scope.get("method") == "POST"
            and peer[0] in {"127.0.0.1", "::1"}
            and len(authorization) == 1
            and len(authorization[0]) <= 4096
            and secrets.compare_digest(
                authorization[0], ("Bearer " + self.token).encode()
            )
            and not any(k.lower() in {b"origin", b"cookie"} for k, v in headers)
        )
        if not permitted:
            return await response({"error": "not_found"}, 404)(scope, receive, send)
        try:
            request = Request(scope, receive)
            body = bytearray()
            async with asyncio.timeout(15):
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > MAX_BODY:
                        return await response({"error": "request_too_large"}, 413)(
                            scope, receive, send
                        )
            value = json.loads(body)
            if not isinstance(value, dict):
                raise TypeError("Invalid request")
            generated = await self.generator.generate(value)
            return await response(generated)(scope, receive, send)
        except (ValueError, TypeError, UnicodeError, TimeoutError):
            return await response({"error": "invalid_request"}, 400)(
                scope, receive, send
            )
        except Exception as error:  # noqa: BLE001 - never expose source, credentials or provider output
            code = "provider_unavailable"
            try:
                from agents_memory.jev import ProviderFailure
            except ImportError:
                pass
            else:
                if isinstance(error, ProviderFailure) and isinstance(error.kind, str) and error.kind in SAFE_FAILURES:
                    code = error.kind
            return await response(
                {
                    "error": {
                        "message": "Selected generation provider unavailable",
                        "type": "provider_unavailable",
                        "code": code,
                    }
                },
                503,
            )(scope, receive, send)


def from_environment(app):
    processing = os.environ.get("AM_MEMORY_PROCESSING")
    if processing == "generative":
        raise ValueError("Free generation was removed; configure Jev with integrated processing.")
    if processing != "integrated":
        return app
    from agents_memory.generation_provider import from_environment as provider

    return PrivateGeneration(
        app, provider(), os.environ.get("AM_MEMORY_GENERATION_TOKEN")
    )
