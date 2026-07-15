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
| `original_assets/img/landing-downloads.0f509c33f57f.png` | `https://www.python.org/static/img/landing-downloads.0f509c33f57f.png?1694722768` | `a55b59389454350bf81acf2a6bd4c7fd24e14e169c67222518194f6ae28b6871` |
| `original_assets/fonts/SourceSansPro-Regular-webfont.fd0d51605201.woff` | `https://www.python.org/static/fonts/SourceSansPro-Regular-webfont.fd0d51605201.woff` | `2ef432d9dfd7a11432b7fc6fcb2c1424fb2e1788138da4c39e603f0867c284cd` |
| `original_assets/fonts/SourceSansPro-Bold-webfont.be855452e565.woff` | `https://www.python.org/static/fonts/SourceSansPro-Bold-webfont.be855452e565.woff` | `7d454011abbb34fbf71a34b604f7d7790ba47609785c71be77a84158e7452ae2` |
| `original_assets/fonts/FluxRegular.f5549a4fe75f.woff` | `https://www.python.org/static/fonts/FluxRegular.f5549a4fe75f.woff` | `f24e445ee46da838c24ed1f62c1f16fb19881796f32615750a87e084e3927190` |
| `original_assets/fonts/FluxBold.3fd71a747d5c.woff` | `https://www.python.org/static/fonts/FluxBold.3fd71a747d5c.woff` | `60b40b66be6fc9a6d52600b5b6349855f29b758274be150b061bf5ef60530a7a` |
