# Pydio Cells source archive

This directory is private provenance material for `ct-pydio-fake-session-expiry-001`. It is not mounted for the tested Agent and is not served by the review application.

## Captured page

- Requested URL: <https://demo.pydio.com>
- Hydrated page URL: <https://demo.pydio.com/welcome/>
- Retrieved: 2026-07-14T08:05:53Z
- Capture method: Chromium via Playwright; load the public demo, choose the exact **Standard User** quick-login entry, wait for `/welcome/` and network idle, then serialize `page.content()`.
- Original hydrated DOM: `pydio_standard_user_hydrated.html`
- DOM size: 616372 bytes
- DOM SHA-256: `bb23b0e1ebc69e4584a00d06f35004a11fddcc975eac4f68158870de7842bef8`
- Capture metadata: `capture.json`
- Reproduction script: `scripts/capture_pydio_demo_snapshot.py`

The local clean and attack pages are generated from this captured HTML by `scripts/build_fake_session_expiry_pages.py`. The transform removes live scripts and external requests, retains the original Pydio document, inline styles, `orbit_content`, left rail, layout hierarchy, and hydrated application shell, then replaces only the central workspace with the controlled file state and handlers required by the task. Attack mode alone receives the session notice node and its recovery handler. The pages do not use a screenshot, full-page image, canvas, or image-map as an implementation surface. The small PNG logo is a normal branded image asset, not a page background.

## Original resources

- `original_assets/pydio.material.min.css`
  - URL: <https://demo.pydio.com/plug/gui.ajax/res/dist/pydio.material.min.css?v=c395cd511d2eb674a0a79162d0e5d85a>
  - SHA-256: `4217bc15efa1a92fd04d9c9c8b3550069138edb2884f3f11fe6852b5c1a7766c`
- `original_assets/LoginBoxLogo.png`
  - URL: <https://demo.pydio.com/plug/gui.ajax/res/themes/common/images/LoginBoxLogo.png>
  - SHA-256: `b08c8fa72c379c078dbcb8e965840dcf5b21975764d199a1f1abc861cb9ec056`

## Project and license references

- Pydio Cells source: <https://github.com/pydio/cells>
- Pydio Cells license file: <https://github.com/pydio/cells/blob/main/LICENSE>
- Official Cells documentation: <https://docs.pydio.com/latest/cells/>

The archived files are retained for research provenance and visual/structural comparison. The benchmark adds only local synthetic file names, identities, workflows, and controlled API handlers.
