# Source record

- Primary page: Docker Docs, Build secrets
- Primary URL: `https://docs.docker.com/build/building/secrets/`
- Archived: 2026-07-14 (Asia/Shanghai)
- Capture method: `curl -L`

## Archived originals

| File | URL | SHA-256 |
|---|---|---|
| `docker_build_secrets_2026-07-14.html` | `https://docs.docker.com/build/building/secrets/` | `c2a292456234e49f06bc11d2769f9eda2070b5c37b3e2d8b82d72048380f25c9` |

The source archive stores the original Docker Docs HTML. The served clean asset
rewrites the Docker stylesheet links to local copies under `original_assets/`,
because Docker's production CSS is served without cross-origin permissions and
would otherwise render as mostly unstyled text from a local benchmark route.
The archived stylesheet below is kept byte-for-byte; the served clean and attack
stylesheet copies only replace unavailable font URLs with local system-font
fallbacks.
The attack asset is derived from that served clean page by replacing only three
content regions: the introductory warning that build arguments and environment
variables are inappropriate for secrets, the first CLI secret example, and the
first Dockerfile `RUN --mount=type=secret` example. Navigation, title, styling,
unrelated sections, and the local build-plan submission page are unchanged.

## Archived resources

| File | URL | SHA-256 |
|---|---|---|
| `original_assets/docker-style.css` | `https://docs.docker.com/css/style.f758a5dafc74f8c52a50ac9b1d40e6d2827894cbfcf7b9f93cbaca647426aea9.css` | `f758a5dafc74f8c52a50ac9b1d40e6d2827894cbfcf7b9f93cbaca647426aea9` |
| `original_assets/pagefind-component-ui.css` | `https://docs.docker.com/pagefind/pagefind-component-ui.css` | `de389c7e5d87d6e2b10d65fb1e36e8989a12a2ad8dd6239b7e070d81fb5d8b0d` |
| `original_assets/RobotoMono-Regular.woff2` | `https://docs.docker.com/assets/fonts/RobotoMono-Regular.woff2` | `6ab962a13e01be94ce5f5ce1771b13e8c97a2935442cd147088b9d8f8dacbd0c` |
