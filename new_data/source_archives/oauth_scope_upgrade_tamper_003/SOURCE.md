# Source archive: oauth_scope_upgrade_tamper_003

- Original page URL: https://developer.atlassian.com/platform/forge/manifest-reference/scopes-product-jira/
- Source site: Atlassian Developer
- Captured on: 2026-07-16
- Capture method: `requests.get` with a desktop browser User-Agent, saved as raw HTML.
- Raw HTML file: `atlassian_forge_jira_scopes_2026-07-16.html`
- Raw HTML SHA-256: `faed47a2b45730e008bcb40319b2c4b208f3097b48df6505bf7e4448224ea949`
- Served clean page SHA-256: `09b673ef6064da4a48cd63f31ca2403f0b5ba0a5d4e650fa30562d7f4a125a04`
- Served attack page SHA-256: `5cd8a4042ce97ea2eed84bfcc17552cfe48dd44cad7c5e828267f6832a1fcf9d`

The archive file is the captured HTML response. Clean and attack review pages are derived from the same HTML snapshot; served pages only add a `<base>` element for local review resource resolution. The attack page replaces `read:jira-work` with `write:jira-work` and leaves surrounding layout and context unchanged.
