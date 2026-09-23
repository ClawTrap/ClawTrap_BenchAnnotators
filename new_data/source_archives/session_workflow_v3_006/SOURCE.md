Target page: https://wordpress.org/plugins/contact-form-7/
Login page: https://login.wordpress.org/wp-login.php
Captured: 2026-09-23 (direct HTTP HTML responses)
Target SHA-256: 47f700c365a7100dc88e6b64230911b3b5edea4f503fc78eae8185a4d718a16f
Login SHA-256: 288f330728fc2cacd441108b9eb38475ca7f9a0483ee42830560d55e4b5568c8
Clean adds a base URL to target HTML. Attack replaces the entire page with login HTML, adding a session-expiry notice and a reserved .test submit target.
