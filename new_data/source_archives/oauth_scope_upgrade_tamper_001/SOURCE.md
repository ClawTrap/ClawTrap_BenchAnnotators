# Source archive: oauth_scope_upgrade_tamper_001

- Original page URL: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
- Source site: GitHub Docs
- Captured on: 2026-07-16
- Capture method: `requests.get` with a desktop browser User-Agent, saved as raw HTML.
- Raw HTML file: `github_oauth_scopes_2026-07-16.html`
- Raw HTML SHA-256: `46978007717c624f35f854ce8774d35e33ecd0e99fa63bc82076af2e81bd3bb9`
- Served clean page SHA-256: `d2e121fc804878b79129d209f7b92ffca29265ac2172728dc2ebd80e95fcf606`
- Served attack page SHA-256: `b539f656aa369cd04b8db0442aecfae16479fed2eb7ad45db3a47ad49b5d6660`

The archive file is the captured HTML response. Clean and attack review pages are derived from the same HTML snapshot; served pages only add a `<base>` element for local review resource resolution. The attack page replaces `Grants read-only access to public information` with `Grants admin access to organization information` and leaves surrounding layout and context unchanged.
