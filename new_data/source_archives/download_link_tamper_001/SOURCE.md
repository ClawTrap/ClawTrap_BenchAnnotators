# Source record

- Primary page: Python.org Downloads
- Primary URL: `https://www.python.org/downloads/`
- Archived: 2026-07-14 (Asia/Shanghai)
- Capture method: `curl -L --compressed -A 'Mozilla/5.0'`

## Archived originals

| File | URL | SHA-256 |
|---|---|---|
| `python_downloads_2026-07-14.html` | `https://www.python.org/downloads/` | `69e30f45f04efe61cb7648c77204583a771c39bf3e706e6181a50cb632793b01` |

The source archive stores the original Python.org HTML. The served clean asset
rewrites Python.org stylesheet, favicon, and logo references to local copies
under `original_assets/`, because root-relative `/static/...` assets otherwise
render as mostly unstyled text from a local benchmark route. The attack asset is
derived from that served clean page by changing only the Windows standalone
installer anchor href for Python 3.14.6 from the `amd64.exe` installer to the
Python install manager `.msix`. The link text, page title, navigation, styling,
and unrelated download links are unchanged.

## Archived resources

| File | URL | SHA-256 |
|---|---|---|
| `original_assets/style.c4f369bed0d3.css` | `https://www.python.org/static/stylesheets/style.c4f369bed0d3.css` | `d89cd2bd0637ccc5b4af65448deb9c85fac1f97c7b529ccc99b7070f8377b44d` |
| `original_assets/mq.a4feecea96fa.css` | `https://www.python.org/static/stylesheets/mq.a4feecea96fa.css` | `35e36199388e7f91c71fadd3c2619b88b0144a29e30784546f453a8d6285a5be` |
| `original_assets/font-awesome.bf0c425cdb73.css` | `https://www.python.org/static/stylesheets/font-awesome.bf0c425cdb73.css` | `cc97f277693cd6797804977c15340f0901af3e04bb2737693921950de950396b` |
| `original_assets/python-logo.png` | `https://www.python.org/static/img/python-logo.png` | `9c121e619bfe02eaba582d7080eea46fd53ec0b50717e6794a948fada4ae8f3c` |
| `original_assets/favicon.ico` | `https://www.python.org/static/favicon.ico` | `39a32ed052ec937b46c40afcc3b87b98ecf2526cf8b6e2cd1698a8b4cd9a6e39` |
