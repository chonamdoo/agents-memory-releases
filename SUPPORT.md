# Support and boundaries

- Platform: macOS arm64; tested macOS 26.6.2. Mach-O minimum 11.0 is a technical header, not a tested compatibility promise. No Intel/Windows/Linux/cloud artifact.
- Signing: ad hoc only; no Developer ID/notarization. Security settings are never bypassed.
- Runtime: bundled CPython 3.13.16 and native dependencies; no separate Python needed. PostgreSQL 18.x and pgvector >=0.8.7 remain independent requirements. Existing official CLIs are needed only for the chosen subscription route; OMP is needed for its optional adapter.
- Privacy: no private runtime config, tokens, keys, environment dump or developer home path is intentionally packaged. Upstream native wheels retain generic CI build-path strings and public attribution/contact notices. Application code and protocol strings can be reverse engineered.
- Verification: scoped compiled smoke and focused tests passed; whole-suite success, separate-Mac compatibility and interactive host acceptance are not established. Public checksums provide integrity, not a notarized publisher identity.
- Requests: use issues in this distribution repository. Never paste keys, private configs, memory contents or environment dumps. This is a community distribution, not an Anthropic-endorsed directory listing or registry submission.
