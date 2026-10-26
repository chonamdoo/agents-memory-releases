---
name: setup
description: Explain safe, explicit onboarding for the agents-memory binary MCP transport before enabling its connection.
disable-model-invocation: true
---
Explain this plugin's onboarding in the user's language. Do not execute DB initialization, credential issuance, service installation/start, account login, model verification or paid calls merely because this skill was invoked.

1. Explain that this macOS arm64 preview connects on demand to an independently prepared authority and supplies no automatic capture/recall guarantee.
2. Ask separately where the authority process runs, where PostgreSQL data lives, and whether judgment uses Jev, an existing official subscription CLI, or the coding agent. This preview initializes local loopback/Unix PostgreSQL only. Cloud process/cloud DB initialization is unsupported and must not silently fall back.
3. Explain PostgreSQL18.x + pgvector>=0.8.7, private runtime/migrator files, and explicit `agents-memory setup --plan-only` before any authorized effects. Existing state must not be overwritten. Jev and subscription egress require independent consent; subscription verification may consume quota. Do not request keys or tokens in chat.
4. After the user separately authorizes and completes core setup, have them choose the existing private config and scoped agent token file in `/plugin configure agents-memory@agents-memory`. Keep these outside plugin/cache directories. They can choose a verified installed runtime or explicitly permit the version/SHA-pinned download. Connection remains disabled until enabled and managed-service recovery is acknowledged. The core can resume only an already-enabled owned service and honors a manual stopped latch.
5. This is an MCP-tools integration. Native capture hooks are separate opt-in work. Avoid duplicate direct/plugin MCP registrations. Show how to check `/mcp` after connection and distinguish disconnected service, missing configuration, checksum failure and unsupported platform. Never manufacture a successful connection.

This skill is guidance, not authorization to mutate the user's authority or files. The current session's explicit user permissions govern any later actions.
