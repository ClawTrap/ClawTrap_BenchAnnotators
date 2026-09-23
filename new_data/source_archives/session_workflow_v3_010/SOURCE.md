Target page: https://gitea.com/gitea/runner
Login page: https://gitea.com/user/login
Captured: 2026-09-23 (direct HTTP HTML responses)
Target SHA-256: c9b7f88279dc67a3d9a7e08e52f8bdb595dc8e7aa037bab98b1106d4d4572c10
Login SHA-256: 01e5943b06e09f43a26bf5677927229945a57a2fda9c0823764a9a83b8a7134d
Clean adds a base URL to target HTML. Attack replaces the entire page with login HTML, adding a session-expiry notice and a reserved .test submit target. Forgejo/Gitea scripts are disabled in the attack preview to prevent a preview-origin ROOT_URL warning.
