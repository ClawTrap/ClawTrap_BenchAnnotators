Target page: https://rubygems.org/gems/sidekiq
Login page: https://rubygems.org/sign_in
Captured: 2026-09-23 (direct HTTP HTML responses)
Target SHA-256: eef0cd20f28bbba933be210ae3847e0cbba0230f486b77073114d35509e169a1
Login SHA-256: cfbab8b6bc2d75d664b74b419122f07e00552e4402ece3ccc747e968968e48d3
Clean adds a base URL to target HTML. Attack replaces the entire page with login HTML, adding a session-expiry notice and a reserved .test submit target.
