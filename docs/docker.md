# Running in Docker (simulated hosting)

The image is the same one you would deploy; locally it stands in for the host.

```bash
docker compose up --build        # http://localhost:8000 (this machine only)
# To share on your home network only, put BIND_ADDR=<this machine's LAN address> in .env.
# The app has no login: anyone on that network can use it (and spend its model quota).
```

- **Model:** reached over the network, never inside the container. By default the Ollama on your machine
  (`LOCAL_LLM_URL=http://host.docker.internal:11434/v1`, used only for the local provider). For a hosted model put `LLM_PROVIDER`, `LLM_MODEL` and `LLM_API_KEY` in `.env`
  (git-ignored; never in the compose file). The default model timeout is 420 s because a cold or loaded local model can take minutes.
- **Data:** `data/clean` is git-ignored, so the build copies it from your checkout. A fresh clone must build it first with the scripts
  (`scripts/fetch_resale.py`, `clean_resale.py`, `geocode_blocks.py`, `build_places.py`, `build_buildings.py`, `build_amenities.py`, `build_bto.py`, `build_bto_history.py`).
  The build fails if `buildings.geojson` or `amenities.parquet` is missing.
- **Safety settings:** read-only file system, no new privileges, non-root user, a health check on `/health`, rate limit and daily token cap
  (`API_RATE_PER_MINUTE`, `API_DAILY_TOKEN_CAP`). One model call runs at a time; a second visitor waits up to `API_QUEUE_WAIT` seconds (30) behind at most three others, then sees "busy". Nothing about visitors is stored.
- **Behind a proxy:** run `ask-hdb serve --forwarded-allow-ips <proxy ip>` (or set `FORWARDED_ALLOW_IPS`) so each visitor gets their own rate limit.
- **Tracing:** off by default; the image does not include the optional Langfuse package. To use it, build with `TRACING=1 docker compose up --build`
  (or `docker build --build-arg TRACING=1 .`), which installs the `tracing` extra, and put `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env`.
  Also set `LANGFUSE_BASE_URL` (`LANGFUSE_HOST` is the older name) for a non-default or self-hosted region, and `LANGFUSE_TRACING_ENVIRONMENT`
  (for example `production` or `development`) so test traces stay apart. Visitor text stays `[redacted]` unless `TRACE_TEXT=1`.
  Traces carry no user or session id, because the app deliberately stores nothing that links one question to another.
- **Rate limit:** behind Docker Desktop port publishing every visitor can look like the same address, so all share one bucket.
- **Worktrees:** if `data` is a symlink (git worktrees) `COPY data/clean` fails; copy the real folder into the build context.
- **Checked 2026-10-23:** image builds (888 MB), starts healthy, serves the page, map data, cards and metrics, and answers a real question through
  the local model with the read-only settings on.

## Public test through a Cloudflare quick tunnel

`docker-compose.tunnel.yml` adds a `cloudflared` container that publishes the app on a random `trycloudflare.com` address (no account).
It also sets `FORWARDED_ALLOW_IPS` so each visitor gets their own rate limit, and drops extra rights from both containers. Start it with the three
`-f` files named in the header of that file. Your computer must stay on, and a local model answers slowly. Treat it as a short test, not hosting.
