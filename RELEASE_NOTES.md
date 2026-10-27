# v0.1.0-preview.20261027: macOS arm64 memory/MCP preview

This is a preview, not a stable or fully validated product release.

- Compiled production source: 05cea567b5185fc59f9117fa3330c18e59bbf152. Mac regression fixture SHA: af8f8aab857069033b830e36298e34441ebe25e7; production sources/build inputs are identical. Application CLI version remains 0.1.0.
- Binary SHA256: 61788ab0fd6cea88e124be1b5e7c4bae6a490e0e396fae51cd55e488780c2f35.
- Archive SHA256: c727383185a3e7459971cb82a42987f8158ba00e4ad38303023db83f113aeca1.
- macOS 26.6.2 arm64: committed Mac regression 78 PASS; isolated actual old/new compiled binary upgrade 2 PASS (prompt recall off/on).
- Fresh source-denied compiled smoke passed setup/migration0008, delayed-DB readiness, MCP stdio, generated OMP capture/FULL receipt, deterministic extraction/recall/correction/retraction. No model calls. The smoke driver observes the new background queue; storage was not made synchronous.
- Bounded background capture/lifecycle fixes are included. Existing operating services and native hooks are not silently replaced by installing this plugin or archive.
- Limitations: real E5/model quality and actual Codex model consumption remain unverified. Four pre-existing source CI skips remain; this preview does not claim all product gates. Interactive OMP/Claude UI and another physical Mac are not certified.
- Bundled CPython3.13.16; no separate Python for the core. Optional semantic encoding requires a separately managed runtime/model. PostgreSQL18.x/pgvector>=0.8.7 remain external prerequisites.
- Ad-hoc signing only: no Developer ID/notarization. No security bypass, new account, credentials, DB reset, service installation or paid call is performed by the installer/plugin.
- Private Python source/bytecode, wheels/sdist, build/environment dumps, operational config/keys/data and private reports are excluded. Thin OMP adapter, schemas/prompts and protocol behavior remain observable. Native code is reverse-engineerable.
- Existing MIT application notice and third-party notices/runtime exceptions are preserved.

A supplemental pinned bootstrap starts company subscription onboarding (Codex Terra or Claude Haiku) and supports idempotent binary placement; home deployments preserve their existing Jev configuration. It does not make an unconfigured authority or CLI login ready automatically.

Download the assets from this preview, verify SHA256SUMS, then follow INSTALL.md. Existing native integrations require explicit owned uninstall/reinstall while preserving scoped settings and retained queues; no old-generation queue is automatically replayed.

---

# v0.1.0-preview.20261026: macOS arm64 binary + Claude Code marketplace preview

This prerelease packages the previously tested compiled core (application version 0.1.0) with distribution metadata and an opt-in MCP marketplace transport. It is not a stable release.

- macOS Apple Silicon only; tested on macOS 26.6.2. No separate Python installation required.
- PostgreSQL 18.x + pgvector >=0.8.7 remain required and are not provisioned.
- Ad hoc signing only. No Developer ID signature/notarization or security bypass.
- Runtime SHA256: `615a1565e20640c2ada24f76c45cf3f6ad8b050077614709dc17c23c870d18f2`.
- Archive SHA256: `bcbf5ec101499829686e4dc1c03a377061d6a1d53e7dd606e7783e6c7548b81b`.
- Compiled source-denied smoke and focused tests passed. Whole suite is not 100% green; timing/platform and baseline source-package limitations are disclosed in README/SUPPORT. Interactive host and separate-Mac testing are not established.
- No credentials, DB initialization, service install/start or paid calls are performed by plugin installation. Connection and pinned download are explicit opt-ins.
- Original Python source, wheels/sdist, build/environment dumps, private settings and private verification documents are excluded. Automatic source archives contain only this distribution repository's metadata/wrappers.
- Existing MIT and third-party notices are preserved. Compiled code is reverse-engineerable; earlier public copies cannot be recalled.
