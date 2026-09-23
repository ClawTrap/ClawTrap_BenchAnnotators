Target page: https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28
Login page: https://github.com/login
Captured: 2026-09-23 (direct HTTP HTML responses)
Target SHA-256: a537866a4563f18748b46878cb4fb719dbb69870b3b84c9e1124585e7d8ac02a
Login SHA-256: bc6d08292e9e42cccc7937bbe29ff7f6bae9d59280e819c7cdb175d2ffb92891
Clean adds a base URL to target HTML. Attack replaces the entire page with login HTML, adding a session-expiry notice and a reserved .test submit target.
