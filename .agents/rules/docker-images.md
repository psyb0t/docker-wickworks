# Docker images

- `Dockerfile` builds the published image `psyb0t/wickworks` for `linux/amd64` and `linux/arm64`: a builder stage that runs `uv sync --frozen --no-dev` into `/opt/venv` (with an unfrozen `uv sync` as fallback), then a slim runtime that runs as the non-root user `wickworks`, exposes 8000, and has a `HEALTHCHECK` on `/health`.
- `Dockerfile.dev` is the image every Make target runs in. It bakes the `dev` group into `/opt/venv`, skips installing the project (`--no-install-project`), and imports the source from the bind mount through `PYTHONPATH=/work/src`. It carries the Docker CLI for the `docker` tests.
- Both Dockerfiles install `pandas-ta==0.4.71b0` and `smartmoneyconcepts==0.0.26` with `--no-deps`. Change those pins in both files together, and never add them to `[project.dependencies]`.
- Base images and the `uv` image are pinned by tag and digest. Bump the tag and the digest together, in both Dockerfiles.
- Keep `LABEL io.modelcontextprotocol.server.name="io.github.psyb0t/wickworks"` in `Dockerfile`; the MCP Registry checks it against `server.json`'s `name`.
- The runtime defaults (`LOG_LEVEL`, `MAX_BARS`, `MIN_BARS`, `WORKERS`, `TZ=UTC`) are set in `Dockerfile` `ENV` and mirrored in `docker-compose.yml`. Keep them equal to the defaults in `config.py`.
- `.dockerignore` keeps `docs/`, `tests/`, `.testing/`, caches, Git metadata and Markdown other than `README.md` out of the build context. The Dockerfile copies `pyproject.toml`, `uv.lock`, `README.md` and `src/`; anything else it needs must be added to the Dockerfile and kept out of `.dockerignore`.
