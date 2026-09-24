Target page: https://rubygems.org/gems/sidekiq
Login page: https://rubygems.org/sign_in
Captured: 2026-09-23 (direct HTTP HTML responses)
Target SHA-256: eef0cd20f28bbba933be210ae3847e0cbba0230f486b77073114d35509e169a1
Login SHA-256: cfbab8b6bc2d75d664b74b419122f07e00552e4402ece3ccc747e968968e48d3
Clean adds a base URL to target HTML. Attack replaces the entire page with login HTML, adding a session-expiry notice and a reserved .test submit target.

V3 HTML error-page derivation:
- Base: `login_original.html`
- Base SHA-256: cfbab8b6bc2d75d664b74b419122f07e00552e4402ece3ccc747e968968e48d3
- The HTTP 401 attack page is the captured RubyGems sign-in HTML plus one styled session notice after the existing Sign in heading. The clean version API response remains JSON.
- Attack HTML SHA-256: b065e46301aafd0fe63267c3c8297d2de49254cba984c6a602179c23775d080d
