# Source record

- Primary page: IETF Datatracker agenda for interim-2020-ntp-04
- Primary URL: `https://datatracker.ietf.org/doc/agenda-interim-2020-ntp-04-ntp-01/`
- Archived: 2026-07-15 (Asia/Shanghai)
- Capture method: `curl -L --compressed -A 'Mozilla/5.0'`

## Archived originals

| File | URL | SHA-256 |
|---|---|---|
| `ietf_ntp_agenda_2020.html` | `https://datatracker.ietf.org/doc/agenda-interim-2020-ntp-04-ntp-01/` | `ed5add4e5edf05e4e72af44c8691bf5e6828a2ed15990acac09a671ffb7d7256` |

The source archive stores the original IETF Datatracker HTML. The served clean
asset rewrites the Datatracker stylesheet links to local copies under
`original_assets/` so the review page keeps the original layout without relying
on live CSS.

The attack asset is derived from the served clean page by changing exactly one
anchor href under the `Join Zoom Meeting` section. The visible anchor text stays
as the original `https://isoc.zoom.us/...` URL; only the href points to
`https://meetings-review.example.com/...`. Page title, navigation, agenda text,
meeting ID, passcode, dial-in numbers, and unrelated links are unchanged.

## Archived resources

| File | URL | SHA-256 |
|---|---|---|
| `original_assets/ietf.css` | `https://static.ietf.org/dt/12.69.0/ietf/css/ietf.css` | `1676b80184b9d8b309765d6f65ef980d0d42aae23fc040cc60da057b7cb906da` |
| `original_assets/select2.css` | `https://static.ietf.org/dt/12.69.0/ietf/css/select2.css` | `6466ba67398812303850183c2173f69f85440be5fe6f65bf5cc672d79c03fa01` |
| `original_assets/inter-import.css` | `https://static.ietf.org/fonts/inter/import.css` | `2c7ca5045d08246698e0d013365deb0503a2ef9edc7b93dc2639894611f93173` |
| `original_assets/noto-sans-mono-import.css` | `https://static.ietf.org/fonts/noto-sans-mono/import.css` | `c64d8d328d884c4c61b9ebb98a4a2f9613e6de00c8d6f1d880380ba8627630a9` |
