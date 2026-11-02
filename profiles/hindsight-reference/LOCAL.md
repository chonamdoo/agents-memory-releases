# Local Hindsight reference launcher

This small stdlib helper requires **Python 3.11+** (`hashlib.file_digest`) and checks or
executes the **official preinstalled** `hindsight-api`.
The profile is NoneLLM / 3000-character chunks / observations off / E5 ONNX / RRF.
It does not install packages, download models, create a database, change host configuration,
or start a separate model server. RRF remains the working profile. CE is not adopted because a quality gain is unproven;
RAM savings are not the decision criterion. The separate CE quality-priority trial did not
produce CE QA answers, so it establishes neither a CE gain nor CE inferiority.

This standalone opt-in component does not migrate Native/Jev/subscription-CLI data or
connect their existing routes. Existing authority and source-review requirements remain in
force. No new paid API key, GGUF server, provider bridge or Native mirror is required.
Local E5 embeddings still require the official compatible runtime.

Prerequisites: an already provisioned **new isolated** PostgreSQL database with the extensions
required by official Hindsight (including pgvector), the official API environment with its ONNX
runtime/tokenizer dependencies, and private pre-cached model assets. Use a trusted installation
matching upstream source `14e7306e27cdbd03ad5f17cf46f22a5f6d6ec5a2`; the package version string
`1.1.0` alone does not verify that source pin. The helper checks executable availability, not
installed source provenance, dependency imports, database extensions or database freshness.

The five files in `e5-assets.sha256.json` are the existing multilingual-E5-small assets from
upstream model revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`. `model.onnx` is that
revision's `onnx/model_qint8_avx512_vnni.onnx`, renamed locally. Metadata files are from the
model root; `tokenizer.json` is from `onnx/tokenizer.json`. Checksums are fixed from the
existing download receipts. Put the five files directly inside your private asset directory.
Alongside Linux x86_64 testing, these pinned assets passed the
[Apple Silicon CPU smoke in CI](https://github.com/chonamdoo/agents-memory/actions/runs/41382015740/job/125074666538)
at source head `5c135c93812cff2864622defe46bacce99861996`. The job requires Darwin/arm64,
uses Python 3.12 and ONNX Runtime's CPUExecutionProvider, and exercises Korean/English mixed
inputs, special tokens/padding, 512-token truncation, and finite 384-dimensional vectors
with attention-masked mean pooling and L2 normalization. This verifies the pinned E5 assets
on a GitHub Apple Silicon runner. Full Hindsight/PostgreSQL operation and the user's MacBook
Jev/subscription-CLI installation, hooks, injection and durability remain unverified there.
This smoke supplies no Mac full-stack latency, RAM or retrieval-quality evidence. Other CPU
instruction sets remain unverified; checksums alone do not establish compatibility or sufficient RAM.

Supply `DATABASE_URL` through your process-local secret manager, never as a CLI argument.
It must select the already provisioned isolated database on a loopback PostgreSQL host
(no URI query parameters). The decoded database name must be a simple identifier of at most
63 characters; administration databases, placeholders and malformed paths are rejected.
The profile fixes `HINDSIGHT_API_DATABASE_SCHEMA=hindsight_reference`, including the
migration version table namespace, to avoid collision with Native's `public.alembic_version`.
This is collision defense, not authorization or shared-database safety: a **new isolated
database remains required**. Never point this profile at an existing Native deployment.
Do not reuse a bank containing vectors from another embedding
configuration. Choose two new unused ports and a new bank name:

```bash
python3 local.py --check \
  --asset-dir '/your/private/e5-small' \
  --hindsight-api '/your/hindsight-env/bin/hindsight-api' \
  --api-port 18240 --worker-port 18241 --bank new-project-reference
```

Replace `--check` with `--start` to execute the official API in the foreground. **Explicit
start allows the official API to initialize/migrate the supplied database.** The helper does
not bootstrap or create it. Use normal Ctrl-C/service supervision for the foreground process.
Neither mode prints the database URL. Upstream runtime output after exec belongs to the
official CLI; keep its logs private. There is no startup health/readiness claim from preflight.

`--check` reads/hashes assets, validates local settings and binds/closes both loopback ports;
it makes no network connections, database calls, subprocesses, installs or downloads. Ports
can be taken after this snapshot. The API binds `127.0.0.1`. The enabled internal worker runs
inside the API; the worker-port setting is checked and passed to the official configuration,
but does not create a separate worker HTTP listener. No standalone worker is launched.
All inherited `HINDSIGHT_API_*` overrides are removed before applying this reviewed profile.
Model offline flags and dotenv disabling are enforced. Other environment variables, including
proxy, CA, platform authentication and guard variables, are preserved. This is a profile
launcher, not an OS network sandbox; use the trusted official installation and private DB.

## Project MCP connection

After an explicit start, manually merge the following into the host's **project** configuration,
substituting your new port and bank. The launcher never writes these files. A bank URL routes
one trusted user's project; it is not a multiuser ACL boundary.
Copyable snippets are `claude.mcp.example.json` and `codex.mcp.example.toml` in this directory.
**Direct official bank MCP is the default for current policy QA requiring verified citations.**

Claude project `.mcp.json`:

```json
{"mcpServers":{"hindsight-reference":{"type":"http","url":"http://127.0.0.1:18240/mcp/new-project-reference/"}}}
```

Codex project configuration (manual merge into the appropriate project configuration supported
by your installed host; do not overwrite global configuration):

```toml
[mcp_servers.hindsight_reference]
url = "http://127.0.0.1:18240/mcp/new-project-reference/"
```

Verify the official bank-scoped tool list is exactly `retain`, `sync_retain`, `recall`,
`get_document`, `delete_document`, `get_memory`, `list_memories`, `list_documents`,
`get_operation`, `list_operations`. These tools need no `bank_id` argument; `reflect` is
excluded. `accepted` is not completion: poll `get_operation` until terminal `completed`,
check exact original text with `get_document`, recall with source chunks, reconnect and
read again. Check replacement/deletion again after worker quiescence. API/config checks
alone do not establish successful Codex/Claude installation, automatic hooks or agent use.

## EXPERIMENTAL Korean policy/document bank preset

`policy-ko-bank.json` is **EXPERIMENTAL**, an **optional bank override**, not a launcher/global default.
Keep the general working-memory bank at 3000 characters: an earlier English 1000-character
trial regressed. For a **fresh, separate policy/document bank** only, explicitly apply this
body through the authorized official admin REST
`PATCH /v1/default/banks/<new-policy-bank>/config`, then use the matching `GET` endpoint to
check the resolved configuration and bank overrides before ingestion. The preset sets
`retain_chunk_size: 800` and `retain_structured_chunk_size: null`; leave the reviewed
None/chunks/E5/RRF profile otherwise unchanged. The bank-config write API must be enabled
and the target new bank explicitly checked. This file performs no request automatically.

Changing bank configuration **does not reindex existing memories**. Reingest the original
documents into the fresh bank, wait for terminal retain completion, and verify exact original
bytes with `get_document`. No Native/Jev/subscription-CLI corpus migration or route wiring
is automatic; existing authority and source-review requirements still apply.

In the known Linux 14-question development trial over 87 Korean documents, 207 of the baseline
237 chunks exceeded E5's 512-token limit. With the same questions and recall budgets, the
separate 800-character bank had 890 chunks: expected-source coverage rose from 4/14 to
14/14 and exact recalled anchors from 9/24 to 22/24, with no previously found source case
lost. Candidate recall p95 over those 14 queries was 0.05712 seconds. These are retrieval-development
observations, **not correct-answer scores**; citation availability does not establish answer
correctness. Database size including the same guards rose from 21,976,767 to 35,903,167 bytes;
API peak RSS rose from 1.045 to 1.449 GiB. Candidate ingestion took 55.29 seconds; baseline
ingestion time was not separately measured, so no ingestion-speed comparison is established.
Six matched guards and multi-chunk replacement/deletion passed; the lost-ACK guard remains
blocked for this profile. The separately frozen 32-query confirmation on the same known
corpus improved ranked expected-source coverage from 6/24 to 22/24. Candidate-only first-attempt
QA scored **24/32 and failed** the frozen 28/32 minimum, despite 8/8 correct unanswerable
abstentions, 66/66 exact supported citations and zero unsupported policy assertions.
Five answerable abstentions lacked required delivered evidence; three further answers omitted
rubric-required details beyond the explicit question wording. The frozen gate is unchanged.
See the [aggregate report](POLICY-EXPERIMENT.ko.md)
for evidence stages, QA limitations and resource measurements. There is no baseline QA delta.
The Mac CI asset smoke above does not evaluate this bank candidate. This candidate remains
unpromoted and supplies no production approval or SOTA evidence.

## Completed consumer-fidelity trial: separate 16-case evidence

A fresh RRF trial on the EXPERIMENTAL 800-character policy bank, over six documents in
the same known 87-document corpus, received an
independent Astra strict grade of **16/16**: 12 answerable cases and four correctly declined
cases whose requested information was absent, 28/28 exact supported citations, and zero
unsupported policy assertions. Four of the answerable questions literally asked about dated synchronization
or graph status; the four absent-information cases were separate. The final independent grade records 768 supporting checks passed; aggregate results and
logical artifact digests are frozen in [VALIDATION.json](VALIDATION.json). Hashes do not
establish public reproducibility, and the raw cases and policy content are excluded.
This is neither a fresh-corpus holdout nor evidence of general SOTA quality
or the full Mac product. The earlier 32-case strict result remains **24/32, FAIL** against
28/32. The questions and consumer differ; no 75%-to-100% improvement is claimed.

The evaluated consumer allowed **48 KiB** (32 KiB primary plus 16 KiB supplemental) and
used all complete, previously unused chunks already returned by the official MCP response.
This checks evaluation-consumer fidelity, not backend retrieval: the official MCP already
returns those chunks. The 16/16 result is a QA consistency observation, not evidence that
the supplemental 16 KiB caused a QA improvement. A caller should consider the complete official returned-chunk payload
before dropping evidence; allowing this 48 KiB budget is a documented evaluation procedure,
not a newly installed wrapper, host hook or change to the official server. The snippets and
helper do not install a renderer or enlarge an agent's context automatically.

On these 16 cases, Linux RRF recall median was 0.04546 seconds and maximum 0.10697 seconds.
The 8.001-second run phase includes startup and queries, not QA. RRF peak RSS was 814,952,448
bytes. The operationally valid official CE paired capture had median recall 14.0711 seconds,
maximum 16.9033 seconds and peak RSS 1,712,435,200 bytes. These are observations, not a reason
to prefer capacity over answer quality. The preregistered positive CE criterion required at
least RRF+2 strict cases; after RRF reached 16/16 that criterion was impossible in this sample.
No CE QA answers were produced. CE quality gain remains **UNPROVEN**, CE is **not adopted**,
and no CE files or settings are included. This trial cannot compare CE answer quality.

## Optional official coding-agents configuration

Direct bank MCP is the smaller previously verified interface. For a separately tested official
coding-agents plugin trial, copy `coding-agents.recall.example.json` into private storage,
replace the API URL/project path/bank, and point the plugin process's `HINDSIGHT_CONFIG` at
that copy. Follow upstream host-specific installation instructions; this helper does not
install hooks. Options match pinned `hindsight-integrations/coding-agents/src/core/config.ts`.

`autoInject: "recall"` avoids the plugin's automatic reflect default; recall types
`world`/`experience` match this chunks profile instead of observation-only recall. Use an
already configured chunks bank with observations/auto-consolidation disabled.
`manageBankConfig: false` preserves it, and `defaultBankConfig` is ignored in that mode.
`retainExtractionMode` does not reconfigure that bank in this mode. The disabled retention,
ingestion, survey and five page options avoid automatic transcript/survey/page generation
in this initial explicit-memory trial. Plugin tools may still offer explicit reflect; this
example does not prove all generative endpoints are disabled. Automatic host injection
and durability remain unverified.

The pinned plugin's successful automatic recall injection runs **once per session**, not on
every prompt. Its recall path returns text only, discards source/document/chunk identifiers,
and collapses whitespace in fallback formatting. A memory-attribution heading is not a
verified source citation. Treat optional hook text as a nonauthoritative hint. On a later
topic or after an update in the same session, explicitly call fresh bank MCP `recall` and
`get_document`; check the exact current document/source version before citing policy.

For a separately authorized fresh plugin-managed bank only, official options are
`manageBankConfig: true`, `retainExtractionMode: "chunks"`, and
`defaultBankConfig: {"enable_observations": false, "enable_auto_consolidation": false}`.
Verify the resolved bank configuration: additive defaults cannot override existing values.
Never put `retain_extraction_mode` inside `defaultBankConfig`; upstream rejects that field.

## Source and review status

The helper and examples come from [source PR 51](https://github.com/chonamdoo/agents-memory/pull/51),
merged as `48793d2331a501efa51b07fcbb8ceaa0799b35a1`. Its final exact-head
[CI run 41385568603](https://github.com/chonamdoo/agents-memory/actions/runs/41385568603)
passed all eight checks. This is separate from the earlier Apple Silicon asset smoke.
The source merge at `48793d2331a501efa51b07fcbb8ceaa0799b35a1` also passed all eight
checks in [main CI run 41386502280](https://github.com/chonamdoo/agents-memory/actions/runs/41386502280).
The new 16-case independent result and its consumer limits are described above; public profile
review is separate. CE quality gain is unproven and CE is not adopted.
See [installation](INSTALL.md), [validation scope](VALIDATION.json) and
[model provenance](UPSTREAM.json). This working-tree update does not change the immutable
`v0.1.0-hindsight-reference-preview.20261101` release or its assets.
