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
