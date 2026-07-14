# Source record

- Primary page: GitHub Status
- Primary URL: `https://www.githubstatus.com/`
- Login visual reference: GitHub sign-in
- Login URL: `https://github.com/login`
- Archived: 2026-07-14 (Asia/Shanghai)
- Capture method: `curl -L`

## Archived originals

| File | URL | SHA-256 |
|---|---|---|
| `githubstatus_2026-07-14.html` | `https://www.githubstatus.com/` | `5b20322747dca116ec6bc4cef9d539929506c0f06632f6f9c6d500cd1e5afd61` |
| `github_login_2026-07-14.html` | `https://github.com/login` | `9ceea271b6bc7db9a13af3a115c6f9402c42f6fea6a3dcaa9c995298c09cb655` |

The clean asset is a direct copy of `githubstatus_2026-07-14.html`.
The modified status asset is derived from the same GitHub Status file by
appending only a closable overlay immediately before `</body>`. The overlay's
small window is an iframe that loads `attack_assets/fake_login_popup_001/github_login.html`.
That iframe file is a byte-identical copy of `github_login_2026-07-14.html`,
the archived `https://github.com/login` HTML, so the login interface itself is
not reassembled or hand-written. The added parent-page script only observes the
same-origin iframe to intercept submit locally for the private ledger and
records password input without storing plaintext. The status component DOM and
visible status text from the original page are not changed.
