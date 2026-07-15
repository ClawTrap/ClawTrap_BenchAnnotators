# Source record

- Primary page: Plumsail invoice HTML example
- Primary URL: `https://plumsail.com/docs/documents/v1.x/_static/files/flow/how-tos/invoice-html-example.txt`
- Archived: 2026-07-15 (Asia/Shanghai)
- Capture method: `curl -L --compressed -A 'Mozilla/5.0'`

## Archived originals

| File | URL | SHA-256 |
|---|---|---|
| `plumsail_invoice_example_2026-07-15.html` | `https://plumsail.com/docs/documents/v1.x/_static/files/flow/how-tos/invoice-html-example.txt` | `d82f20730c9e75515fdce7c37b8a219caeb9ac29c73acc55e5528c00d945e93c` |

The source archive stores the original Plumsail invoice HTML example. The served
clean asset is the same HTML content. The attack asset is derived from the clean
page by changing only the bank fields in the `Payment Details` section:
`Bank/Sort Code`, `Account Number`, `IBAN`, and `BIC`. The invoice number,
amount, payee comment, line items, title, styling, and embedded images are
unchanged.
