# Web app image: FastAPI + the plain-JS page, with the cleaned data baked in.
# Build from a checkout that has data/clean (it is git-ignored; see README for how to rebuild it from the scripts).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

# Optional Langfuse tracing: build with --build-arg TRACING=1. The default image does not include the package.
ARG TRACING=0

# Dependencies first so the layer is cached until the lock file changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project $([ "$TRACING" = 1 ] && echo --extra tracing)

COPY src ./src
COPY rules ./rules
COPY data/clean ./data/clean
# The offline builder must run before building the image; raw outlines stay outside the context.
RUN --mount=type=cache,target=/root/.cache/uv test -s data/clean/buildings.geojson && test -s data/clean/amenities.parquet && uv sync --frozen --no-dev $([ "$TRACING" = 1 ] && echo --extra tracing)

# Not run as root: the app only reads its own files, so make sure local file modes do not lock it out.
RUN chmod -R a+rX /app/data /app/rules /app/src && useradd --system --no-create-home app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["/app/.venv/bin/ask-hdb", "serve", "--host", "0.0.0.0", "--port", "8000"]
