# Private data stays on your computer

Public Jinx source and releases must contain no API keys, passwords, browser sessions, account configurations, personal memory databases or chat history. Each person connects their own accounts after installation.

Private NAS transfers may contain explicitly selected avatar and voice assets. They must not contain credentials or browser profiles. Never upload a personal backup as a public release asset.

Before publishing, run `python scripts/check-release.py --history --local-secrets` on the maintainer's computer. This checks source/history against local credential values without logging the values. Enable the local pre-push guard with `git config core.hooksPath .githooks`.

GitHub secret scanning and push protection provide additional checks for supported secret types. CI scans complete Git history with Gitleaks. Detection is a safeguard, not a guarantee that arbitrary passwords will be recognised.

If a credential is ever exposed, revoke or rotate it at its provider promptly. Removing a file from the latest commit does not remove copies from history or downloads. Report security issues privately; never paste a real credential into a public issue or build log.
