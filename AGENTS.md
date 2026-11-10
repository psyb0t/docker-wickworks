# wickworks

Instructions for coding agents (Codex, Claude Code and others) and for people changing this repository. Users of the image want the documentation site, https://psyb0t.github.io/docker-wickworks/, not this file.

## Agent setup

`CLAUDE.md` is a committed symlink to `AGENTS.md`, and `.claude` is a committed symlink to `.agents`, so Claude Code reads the same instructions, rules and skills as Codex. Claude's Edit and Write tools refuse to write through a symlink, so edit `AGENTS.md` and `.agents/rules/*.md` directly.

## What it is

A stateless HTTP service, published as the Docker image `psyb0t/wickworks`, that takes OHLCV bars plus a map of requested indicators and returns only those outputs: technical indicator series from `pandas-ta`, Smart Money Concepts objects from `smartmoneyconcepts` (with a numba port of its hot loops), in-house support and resistance levels, and last-bar summaries. The same compute path is exposed over REST (`POST /`) and over a stateless streamable-HTTP MCP server mounted at `/mcp`. There is no database, no auth, no outbound network call and no state between requests. The repository also ships an agent skill, an OpenClaw stdio-to-HTTP MCP bridge plugin, and Claude Code and Codex plugin manifests.

## Architecture

- `src/wickworks/server.py`: the FastAPI app. `GET /health`, `GET /metadata`, `POST /`. `POST /` checks `MAX_BARS` (413), empty `bars` and `indicators` (400), builds a DataFrame, calls `compute_dataframe`, maps `InvalidIndicatorSpecError`/`UnknownIndicatorError` to 400, `InsufficientBarsError` to a structured 400 (`detail.error = "insufficient_bars"`), anything else to 500, then serializes with `NumpyEncoder` and rewrites every key to camelCase. It mounts the MCP app at `/mcp` and rewrites a bare `/mcp` to `/mcp/` in `_McpTrailingSlashMiddleware`.
- `src/wickworks/mcp_server.py`: `build_mcp_server()` returns a `FastMCP` with `stateless_http=True`, `json_response=True`, DNS-rebinding protection off and `streamable_http_path="/"`. Tools: `health`, `list_indicators`, `metadata`, `compute`. `compute` validates through the same `ComputeRequest` model, runs `compute_dataframe` in a thread and returns the REST envelope; failures raise `ValueError`, which reaches the client as an `isError` tool result.
- `src/wickworks/schemas.py`: Pydantic models. `Bar` forbids extra fields, requires positive finite OHLC, finite non-negative `volume`, and `low <= open, close <= high`. `ComputeRequest` caps `symbol` at 128 and `timeframe` at 32 characters, requires strictly increasing bar times, and accepts each indicator spec as `true` or an object. Schema failures are FastAPI 422s.
- `src/wickworks/compute.py`: `compute_dataframe` resolves each `(outputKey, spec)` to `(type, params)`, rejects unknown types, validates params, collects every bar deficit before raising, then runs each registry function against one shared `Context`.
- `src/wickworks/validation.py`: per-type allowed parameter sets (camelCase plus snake_case aliases), type checks, and cross-parameter rules (`fast < slow`, `tenkan < kijun < senkou`, psar step not above max, `rangePercent <= 1`, the `previousHighLow` bucket list, the `sessions` names and Custom window rules).
- `src/wickworks/requirements.py`: minimum bars per indicator type, derived from params. SMC outputs and summaries need `MIN_BARS`; unknown types fall back to `MIN_BARS`.
- `src/wickworks/registry.py`: `INDICATORS`, the name to function map (67 entries), and `Context`, which runs the full analysis (`indicators.add_all` then `smc.analyze`) lazily and at most once per request. Series go through `safe_float(decimals=None)` so NaN and infinity become `null`.
- `src/wickworks/indicators/`: column builders used by the analysis pass. Importing the package calls `smc_fast.patch()` unless `DISABLE_SMC_FAST` is set.
- `src/wickworks/smc.py`: `analyze()` builds order blocks (max 40), FVGs (max 15, unmitigated only), BOS/CHoCH and swing levels (max 10 each, trailing 50 bars), S/R levels, recent range, levels, momentum, volume, position and slope.
- `src/wickworks/smc_fast.py`: numba replacements for `smartmoneyconcepts` `ob`, `fvg`, `bos_choch` and `swing_highs_lows`, ported from the MIT upstream (see `THIRD_PARTY.md`).
- `src/wickworks/metadata.py`: the static `GET /metadata` catalog (`version`, `count`, `entries`), keyed by dot paths into the response.
- `src/wickworks/config.py`: `LOG_LEVEL`, `MAX_BARS`, `MIN_BARS`, `WORKERS` from the environment. A non-integer value falls back to the default.

Request path: client -> `POST /` or MCP `compute` -> `ComputeRequest` validation -> `compute_dataframe` pre-flight (type, params, bar requirements) -> registry functions (`pandas-ta` directly, or the cached analysis pass for SMC and summaries) -> `NumpyEncoder` -> camelCase keys -> response.

## Stack

- Python `>=3.12`; the images run `python:3.12-slim-bookworm`, pinned by digest in `Dockerfile` and `Dockerfile.dev`.
- FastAPI, uvicorn, Pydantic 2, pandas, numpy, scipy, numba, `mcp`, all exact-pinned in `pyproject.toml` and locked in `uv.lock`.
- `pandas-ta==0.4.71b0` and `smartmoneyconcepts==0.0.26` are installed with `uv pip install --no-deps` in both Dockerfiles because their transitive pins conflict. They are deliberately absent from `[project.dependencies]`.
- `uv` 0.5.11 (copied from its pinned image), with `[tool.uv] exclude-newer` as a supply-chain age gate.
- Dev tools in the `dev` dependency group: pytest, pytest-cov, httpx, black, isort, flake8, mypy, testcontainers, requests.
- OpenClaw plugin: Node.js `>=18`, one dependency, `mcp-remote` (exact pin).
- CI: `.github/workflows/pipeline.yml` calling `psyb0t/reusable-github-workflows`.

## Layout

| Path | What it holds |
| --- | --- |
| `src/wickworks/` | The service package (see Architecture) |
| `src/wickworks/indicators/` | DataFrame column builders for the analysis pass |
| `tests/` | pytest suite; `tests/fixtures/eurusd_h1.json` holds 500 real EURUSD H1 bars |
| `tests/test_docker.py` | Integration tests against the built image, marker `docker`, opt-in |
| `schema.json` | JSON Schema (Draft 2020-12) for the request and response, checked by `tests/test_schema_contract.py` |
| `Dockerfile` | Production image: builder stage with `uv`, slim runtime as user `wickworks`, healthcheck, MCP Registry `LABEL` |
| `Dockerfile.dev` | Dev image every Make target runs in: dev deps in `/opt/venv`, Docker CLI, source on a bind mount via `PYTHONPATH=/work/src` |
| `docker-compose.yml` | Example deployment of `psyb0t/wickworks:latest` |
| `Makefile` | Every dev command; run `make help` |
| `scripts/bump_exclude_newer.sh` | Moves `exclude-newer` to today, called by the `pkg-*` targets |
| `docs/` | The documentation site (GitHub Pages, Jekyll, Just the Docs) |
| `.agents/skills/wickworks/` | The agent skill and its `references/setup.md` |
| `.agents/plugins/wickworks/` | The OpenClaw stdio-to-HTTP MCP bridge plugin (MIT) |
| `.agents/.claude-plugin/`, `.agents/.codex-plugin/` | Claude Code and Codex plugin manifests |
| `.agents/rules/` | Rules for changing this repository |
| `server.json`, `glama.json` | MCP Registry and Glama metadata |
| `THIRD_PARTY.md`, `LICENSES/` | Notice for the MIT code ported into `smc_fast.py` |
| `.github/workflows/` | `pipeline.yml` plus repository housekeeping workflows |

## Commands

Docker and Make are enough. Every target runs inside the dev image, which it builds first.

```bash
make help                     # every target
make run                      # uvicorn on :8000 in the dev container (PORT=... to change)
make lint                     # flake8 + mypy
make format                   # isort + black
make test-unit                # in-process tests, no Docker socket needed
make test                     # unit + docker integration tests (builds psyb0t/wickworks:test)
make test-docker              # docker integration tests only
make check                    # lint + test
make pkg-add PKG=name==1.2.3  # bump exclude-newer, then uv add
make pkg-lock                 # refresh uv.lock with the current exclude-newer
make docs                     # build the documentation site into .testing/docs-site
```

## Project-specific landmines

- The version lives in `pyproject.toml`, the `wickworks` entry of `uv.lock` and `.agents/.codex-plugin/plugin.json`; keep all three equal. `__version__` comes from package metadata, so `/health` reports `0.0.0+unknown` when the package is not installed (as in the dev image, which runs from `PYTHONPATH`). `server.json` keeps `0.0.0`; the MCP Registry publish workflow stamps it from the tag.
- A new indicator needs entries in `registry.INDICATORS`, `validation._PARAMS_BY_INDICATOR`, `requirements.REQUIREMENTS`, `metadata.py`, `schema.json`, the docs pages and the skill's indicator list. A missing `requirements` entry silently falls back to `MIN_BARS`.
- Response keys are camelized recursively after serialization. A snake_case key in an analysis dict reaches clients as camelCase; `smartmoneyconcepts` event columns such as `CurrentRetracement%` pass through as-is.
- `config.py` reads the environment once at import, and `requirements.py` copies `MIN_BARS` at import. A changed value needs a process restart, and a test that patches it must patch the module attribute it reads.
- The `docker` tests need the image `psyb0t/wickworks:test`, which `make test` and `make test-docker` build first, and the host Docker socket.

## Rules

Rules for every change live in `.agents/rules/`, one file per topic. Read the ones that match what you are touching before editing.
