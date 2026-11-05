# Unified memory contract — written before implementation (2026-11-05)

Scope: the existing local, personal-server, team-server and company-server
deployment locations. Location is configuration, never a different memory algorithm.
No new hosted service, model weights, billing or production migration is authorized.

## Required observable states

1. `received`: the candidate and original operation fingerprint are durable. This
   is not a searchable memory and does not acknowledge completed processing.
2. `judged`: the selected provider has returned a validated keep/discard result.
   Provider failure or ambiguity remains retryable; no provider fallback.
3. `extracted`: only source-grounded, self-contained selected passages remain.
   This initial contract uses extractive selection, not invented paraphrases.
   Jev's existing typed judgment API does not supply arbitrary generated prose.
   Selection receives the complete bounded source as context. Offsets identify
   exact source substrings. No output may invent or change a fact.
4. `indexed`: Hindsight synchronously retained the selected passages under a
   deterministic document ID. Neither an HTTP acceptance nor an empty response
   proves indexing. Read the document back and verify its content.
5. `ready`: the current revision and Hindsight document are published together
   in the application projection; another device can apply the change. Retrieval
   must use Hindsight and recheck current revision/authorization before returning.

`discarded` is a terminal, durable receipt, not a searchable empty memory. A
discarded proposed edit preserves the previous accepted revision. `deleted`
publishes a tombstone and excludes every old document from subsequent application
queries. `legacy_pending` preserves pre-upgrade rows without presenting them as
processed memories. The retained input, selected passages, project, kind,
session_id, source_id, account and operation identity remain linked server-side.

Extraction is source-grounded passage selection. Automatic cross-document
observations / generative consolidation are **not implemented or claimed** by
this contract. No operation requiring them may report them as completed. Explicit
revision replacement is supported; implicit semantic conflict resolution is not.
Provider quality, sentence segmentation quality and full benchmark retrieval
quality require separate evidence and are not implied by contract tests.

## Invariants

- Location never changes selection, admission, source grounding or search rules.
- Same operation ID + same original bytes returns the same durable outcome;
  different bytes are rejected. Retries may repeat transport, not publish duplicates.
- The original fingerprint and the processed output digest are distinct.
- Rejected input never becomes a searchable memory or a team brief. Receiving it
  in a private inbox is distinct from accepting it as memory.
- Edits use compare-and-set revision checks. A failed edit must not hide the last
  accepted revision. Other memory operations must continue past a conflict.
- Derived Hindsight IDs are nominations. Current account/project membership,
  sharing, current revision and deletion status determine publication authority.
- New requests after revocation completion are denied. Previously delivered
  copies and in-flight requests cannot be recalled; no remote-wipe claim.
- Raw prompts remain explicit opt-in and never enter automatic/team context.
- Keys, endpoints, user data and existing SQL history are preserved. No destructive
  migration or automatic reclassification of existing user data in this task.
- Historical SQL change logs and backups may contain previous text. Search
  exclusion, physical document cleanup and irreversible backup erasure are three
  different guarantees. Backup retention/erasure policy remains undecided.
- Sync convergence assumes writes stop, connectivity returns, retries run and
  provider configuration is usable. Unresolved conflicts remain visible.

## Providers and automation

The existing private typed clients support Jev and locally authenticated Claude /
Codex subscription CLI. Jev receives the submitted candidate at its configured
HTTPS endpoint; CLI executes on the machine hosting the processor and may send
the candidate to its subscription service. No OAuth credential is copied between
machines. A real local model adapter is not inferred from the term local-llm.
Unsupported providers fail closed. Team/company describe placement and ACL,
not ownership of a particular LLM subscription.

MCP startup context, question-triggered recall, prompt capture and background
draining are separate paths. A tool permission is not an event subscription.
Only an actually exercised host event path may be described as automatic.
Native Mac/Windows host behavior not executed here remains unverified.

## Capture origin and per-operation results

Only the local host hook (Claude Code / Codex `UserPromptSubmit`, omp
`before_agent_start`) attests `origin: "user_prompt"`: the whole source is the
user's own typed prompt. The judge then may treat a direct request in the user's
own words as durable, never for credentials, secrets, other people's personal
data, or requests that appear only inside quoted/pasted text. MCP tools (local and
remote `sync_retain`) cannot attest origin; a tool argument carrying `origin` is
rejected with `origin_not_accepted_from_tools`. A missing origin is omitted from
the operation body and digest, so pre-origin fingerprints are unchanged. Clients
send origin only to servers whose health reports `origin_aware`.

For a multi-passage user-prompt origin, admission v5 also judges whether each
passage is only a bare retention request. Such a passage can be omitted from an
otherwise admitted operation only when another passage already meets the keep
threshold, its request-only probability is at least 0.8, and its injection score
is below 0.5. Other uncertain content and suspected injection still block the
whole operation. `audit.items[].request_only` records this signal (null when not
asked). Origin-less and single-passage requests keep their existing judgment path.

`setup_status.state` / `ready` describe the queue and engine, not whether a given
memory was stored. Per-operation results are separate: `sync_now` returns
`outcomes`, `setup_status` returns `recent`, each with `applied`, `discarded`,
`processing`, `needs_review` or `unknown` and a machine reason
(`judge_not_durable`, `memory_requires_review`, `reason_not_recorded` for
pre-upgrade discards, `reason_not_reported_by_server` for older servers). An empty
recall carries `empty_result_scope`: it is not proof that nothing was captured.

Codex reads a project `.codex/hooks.json` only when that project is trusted;
otherwise no capture or recall runs and nothing reports it. Claude Code's own
auto-memory may separately save content this contract did not store; that copy is
local to Claude Code and is not shared with Codex or omp.

## Release gates

Required before deployment: real Hindsight + PostgreSQL/pgvector tests with two
replicas, failure/retry/restart/edit/delete/revocation tests, inspector mutation
controls, explicit legacy migration plan, selected real-provider smoke, and
actual supported host automation tests. Missing gates block a full-support claim.
This task creates no release and changes no user installation.
