Target page: https://codeberg.org/forgejo/forgejo/releases
Login page: https://codeberg.org/user/login
Captured: 2026-09-23 (direct HTTP HTML responses)
Target SHA-256: 1088313fdb3c7dbc25ee61f8b2cb148afb013e01322c5eb6f2f3055840cd51c5
Login SHA-256: e6722de9292f818e13ec7c54ce73f7617b2da9fd567fe4319d1d8a37944755a4
Clean adds a base URL to target HTML. Attack replaces the entire page with login HTML, adding a session-expiry notice and a reserved .test submit target. Forgejo/Gitea scripts are disabled in the attack preview to prevent a preview-origin ROOT_URL warning.
