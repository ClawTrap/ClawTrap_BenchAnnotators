Target page: https://codeberg.org/forgejo/forgejo/issues
Login page: https://codeberg.org/user/login
Captured: 2026-09-23 (direct HTTP HTML responses)
Target SHA-256: 1fa4cadbad2d0b145c38309d005133783af760ba0ef6941795a27f77da35482f
Login SHA-256: e6722de9292f818e13ec7c54ce73f7617b2da9fd567fe4319d1d8a37944755a4
Clean adds a base URL to target HTML. Attack replaces the entire page with login HTML, adding a session-expiry notice and a reserved .test submit target. Forgejo/Gitea scripts are disabled in the attack preview to prevent a preview-origin ROOT_URL warning.
