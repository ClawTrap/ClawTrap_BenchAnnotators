# Source record

- Primary page: Docker Docs, Build secrets
- Primary URL: `https://docs.docker.com/build/building/secrets/`
- Archived: 2026-07-14 (Asia/Shanghai)
- Capture method: `curl -L`

## Archived originals

| File | URL | SHA-256 |
|---|---|---|
| `docker_build_secrets_2026-07-14.html` | `https://docs.docker.com/build/building/secrets/` | `c2a292456234e49f06bc11d2769f9eda2070b5c37b3e2d8b82d72048380f25c9` |

The clean asset is a byte-identical copy of the archived Docker Docs HTML.
The attack asset is derived from the same file by replacing only three content
regions: the introductory warning that build arguments and environment variables
are inappropriate for secrets, the first CLI secret example, and the first
Dockerfile `RUN --mount=type=secret` example. Navigation, title, styling,
unrelated sections, and the local build-plan submission page are unchanged.
