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
  (`scripts/fetch_resale.py`, `clean_resale.py`, `geocode_blocks.py`, `build_places.py`, `build_bto.py`, `build_bto_history.py`).
- **Safety settings:** read-only file system, no new privileges, non-root user, a health check on `/health`, rate limit and daily token cap
  (`API_RATE_PER_MINUTE`, `API_DAILY_TOKEN_CAP`). Nothing about visitors is stored.
- **Behind a proxy:** run `ask-hdb serve --forwarded-allow-ips <proxy ip>` (or set `FORWARDED_ALLOW_IPS`) so each visitor gets their own rate limit.
- **Tracing:** the image does not include the optional Langfuse package, so tracing stays off in Docker; add `--extra tracing` to the `uv sync` lines to use it.
- **Rate limit:** behind Docker Desktop port publishing every visitor can look like the same address, so all share one bucket.
- **Worktrees:** if `data` is a symlink (git worktrees) `COPY data/clean` fails; copy the real folder into the build context.
- **Checked 2026-10-23:** image builds (888 MB), starts healthy, serves the page, map data, cards and metrics, and answers a real question through
  the local model with the read-only settings on.
