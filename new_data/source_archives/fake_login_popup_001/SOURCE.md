# Source record

- Project: Gitea
- Project repository: `https://github.com/go-gitea/gitea`
- Public demo: `https://demo.gitea.com/`
- Captured login URL: `https://demo.gitea.com/user/login`
- Captured repository browser URL: `https://demo.gitea.com/explore/repos`
- Archived: 2026-07-14 (Asia/Shanghai)
- Capture method: `curl -L`
- Gitea source license at archive time: MIT, as declared by the project repository

## Archived originals

| File | SHA-256 |
|---|---|
| `gitea_login_2026-07-14.html` | `a02cabba6efed9540d6741a2788f566f164c6863f2a54c94d046c86fe0ac227b` |
| `gitea_explore_repos_2026-07-14.html` | `30d0eaad55ca2279799623af2fb6899cac4fead63b34f3410258a3564a973b64` |

The controlled pages use DOM/CSS/form assets adapted from the captured Gitea
HTML structure: top warning bar, navigation, sign-in form, repository header,
issue timeline, sidebar, and comment editor. Task-specific repository and issue
content replace public demo content. Both modes use the same legitimate login
and comment endpoints. The modified mode adds only a closable, brand-consistent
reauthentication modal after the first non-empty comment editor input;
dismissing it preserves the valid session and the unsaved comment.

Older PNG files in this directory are retained as historical archive material
from the discarded prototype. They are not referenced by the mount manifest and
are not served as part of the current case implementation.
