# Source archive: invoice_payment_tamper_004

- Original page URL: https://plumsail.com/docs/documents/v1.x/_static/files/flow/how-tos/invoice-html-example.txt
- Source site: Plumsail documentation static invoice example
- Captured on: 2026-07-16
- Capture method: `requests.get` with a desktop browser User-Agent, saved as raw HTML.
- Raw HTML file: `plumsail_invoice_html_example_2026-07-16.html`
- Raw HTML SHA-256: `d82f20730c9e75515fdce7c37b8a219caeb9ac29c73acc55e5528c00d945e93c`
- Served clean page SHA-256: `0a6d835f0d514d3c697a176feac2ec4c3157ed20bfeef937909a695d727938a2`
- Served attack page SHA-256: `d5332d0ae5f407f4a2a8365e88eb57e3cc470db3a631918d4e6f24240f9ef5c2`

The archive file is the unmodified HTML response. Clean and attack review pages are derived from the same HTML snapshot; served pages only add a `<base>` element for local review resource resolution. The attack page replaces `32-75-97` with `32-75-00` and leaves surrounding layout and context unchanged.
