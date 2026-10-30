# Deploy

The app is **deployment-ready, not deployed**. The intended host is `credit.zarreh.ai` behind the shared Caddy proxy.

## Topology

`compose.prod.yaml` runs `credit-api` and `credit-web` on the external `edge` network and **publishes no host ports**. The reverse proxy is the only way in.

```caddyfile
credit.zarreh.ai {
    basicauth {
        demo <bcrypt-hash from `caddy hash-password`>
    }
    handle_path /api/* {
        reverse_proxy credit-api:8000 {
            # Overwrite, never append: the API trusts this header for rate limiting.
            header_up X-Forwarded-For {remote_host}
        }
    }
    reverse_proxy credit-web:3000
}
```

**Auth.** Basic auth at the proxy covers both the site and the browser's direct API calls. There are no user accounts, and no API key is ever placed in browser code. The reviewer name stored with decisions is a demo label, not an identity.

## Environment

Set in `.env` on the server (never committed):

| Variable | Purpose |
|---|---|
| `CREDIT_ENVIRONMENT` | `production` (JSON logs, explicit CORS only) |
| `CREDIT_FRONTEND_ORIGINS` | JSON list, e.g. `["https://credit.zarreh.ai"]` |
| `CREDIT_OPENAI_API_KEY` | Enables the analyst; leave empty to run without AI |
| `CREDIT_ANALYST_MODEL` | Default `gpt-4o-mini` |
| `CREDIT_LANGSMITH_API_KEY` | Optional tracing |
| `WEB_PUBLIC_API_URL` | Build arg, e.g. `https://credit.zarreh.ai/api` (inlined at build time) |
| `WEB_PUBLIC_DOCS_URL` | Build arg for the docs links |

## Data and state

- The image contains the serving model, `evidence.json`, `verifier_report.json` and `data/queue.json`.
- `./data` is mounted as a volume for `credit.db` (queue, events, report drafts) and `analyst.db` (chat threads).
- The analyst's aggregate tool downloads the UCI file into `data/raw/` on first use and verifies its checksum; pre-seed it with `make data` if the server has no outbound access.
- **Reset** is explicit and destructive: `docker compose -f compose.prod.yaml exec credit-api python -m credit.cli`. It rebuilds the queue in one transaction and clears analyst threads. Nothing resets at startup.
- SQLite is single-instance. Running more than one API replica needs a shared database first.

## Containers

Both images run as non-root users with health checks. `.dockerignore` excludes secrets, caches, tests and local databases. PR CI builds the images but never pushes or deploys.
