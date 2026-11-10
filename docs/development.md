---
title: "Development"
description: "Work on wickworks: the Docker-only dev container, Make targets, lint, unit and Docker tests, dependency updates with exclude-newer, CI pipeline and releases."
nav_order: 12
---

# Development

You need Docker and Make. Every target runs inside a development image built from [`Dockerfile.dev`](https://github.com/psyb0t/docker-wickworks/blob/main/Dockerfile.dev), so the host never needs Python, `uv` or any project tool, and no `.venv` directory appears in the checkout. The image bakes the dependencies into `/opt/venv` and imports the source from your checkout through `PYTHONPATH`. Docker's layer cache makes the rebuild that every target starts with nearly free until `pyproject.toml` or `uv.lock` changes.

Instructions for coding agents, the code layout and the repository rules are in [`AGENTS.md`](https://github.com/psyb0t/docker-wickworks/blob/main/AGENTS.md) and [`.agents/rules/`](https://github.com/psyb0t/docker-wickworks/tree/main/.agents/rules).

## Make targets

```bash
make help          # list every target
make run           # uvicorn on :8000 in the dev container
make shell         # a shell inside the dev container
make lint          # flake8 + mypy
make format        # isort + black
make test-unit     # in-process tests only
make test          # unit + Docker integration tests
make test-docker   # Docker integration tests only
make check         # lint + test
make docs          # build this documentation site into .testing/docs-site
make clean         # remove build and cache files
```

`make run` takes `PORT=9000` to change the host port. The dev container runs as your user, so files it writes stay yours.

## Lint

`make lint` runs `flake8 --extend-ignore=E203,E501 src tests` and `mypy src`. `make format` runs isort with the black profile and black at line length 100. Both linters must report nothing; CI fails otherwise.

## Testing

`make test-unit` runs about 370 tests in process through FastAPI's test client. `make test` builds the production image as `psyb0t/wickworks:test` and adds seven integration tests (marker `docker`) that start that image through testcontainers and call it over HTTP. They need the host Docker socket, which the target mounts into the dev container.

The tests fall into three groups:

1. **Closed-form references.** For the standard indicators (RSI, MACD, ATR, Bollinger, Stochastic, Aroon, CCI, Williams %R, ROC, MOM, OBV, Donchian, VWMA, EMA, SMA and more), [`tests/_helpers.py`](https://github.com/psyb0t/docker-wickworks/blob/main/tests/_helpers.py) implements the formula in plain numpy and pandas, without `pandas-ta`, and the tests compare the last bar with wickworks' output on 500 real EURUSD H1 bars ([`tests/fixtures/eurusd_h1.json`](https://github.com/psyb0t/docker-wickworks/blob/main/tests/fixtures/eurusd_h1.json)). If `pandas-ta` or the wiring drifts, these fail.
2. **smc_fast parity.** [`tests/test_smc_fast_parity.py`](https://github.com/psyb0t/docker-wickworks/blob/main/tests/test_smc_fast_parity.py) proves the numba port returns the same values as upstream `smartmoneyconcepts` on the same input.
3. **Contract tests.** Determinism (same bars, same bytes), append stability (new bars do not change past values of causal indicators), warmup `null` counts, isolation (two outputs requested together equal each requested alone), error paths, the `volume` field, the response envelope, checks of parts of [`schema.json`](https://github.com/psyb0t/docker-wickworks/blob/main/schema.json) against the code, and metadata coverage of every indicator.

## Dependencies

Python dependencies are pinned exactly in [`pyproject.toml`](https://github.com/psyb0t/docker-wickworks/blob/main/pyproject.toml) and locked in `uv.lock`. `[tool.uv] exclude-newer` holds a date, and `uv` refuses any package version published after it. A version fresh enough to be a hijacked release still in its detection window cannot get in by accident.

Change dependencies only through these targets. Each one except `pkg-lock` first moves `exclude-newer` to today's UTC midnight with [`scripts/bump_exclude_newer.sh`](https://github.com/psyb0t/docker-wickworks/blob/main/scripts/bump_exclude_newer.sh), then edits the lock inside the dev image:

```bash
make pkg-add PKG=foo==1.2.3   # add a package
make pkg-remove PKG=foo       # remove a package
make pkg-update PKG=foo       # upgrade one package
make pkg-upgrade              # upgrade everything
make pkg-lock                 # refresh the lock with the current date
```

Do not hand-edit `exclude-newer`.

`pandas-ta` (0.4.71b0) and `smartmoneyconcepts` (0.0.26) pin conflicting versions of their own dependencies. Both Dockerfiles install them with `uv pip install --no-deps`, and they are deliberately left out of `[project.dependencies]`. Change their versions in both Dockerfiles together.

## Adding an indicator

One change touches all of these. `tests/test_metadata.py` fails when an indicator has no catalog entry, but nothing checks that `schema.json` or the docs list a new indicator, so review those by hand.

- the function in `INDICATORS` in [`registry.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/registry.py);
- its parameters in [`validation.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/validation.py);
- its minimum bars in [`requirements.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/requirements.py) (without one, it silently needs `MIN_BARS`);
- catalog entries in [`metadata.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/metadata.py);
- its request and output definitions in `schema.json`;
- tests, including a closed-form reference for a standard indicator;
- the [indicator reference](indicators.md) or [SMC page](smc.md), and the agent skill's indicator list.

## Documentation

This site is `docs/`, built by GitHub Pages with Jekyll and the Just the Docs theme. `make docs` builds it with the same image GitHub uses into `.testing/docs-site`. Links between pages use relative `.md` paths; links to files outside `docs/` use full GitHub URLs.

## CI

[`.github/workflows/pipeline.yml`](https://github.com/psyb0t/docker-wickworks/blob/main/.github/workflows/pipeline.yml) runs on every push, using the shared workflows from [psyb0t/reusable-github-workflows](https://github.com/psyb0t/reusable-github-workflows):

- **Every branch push:** `make lint` and `make test`, the full suite including the Docker integration tests. Both run their tools in containers, so the runner needs only Docker and Make, and neither needs credentials.
- **Push to `main`, after the checks pass:** builds the image for `linux/amd64` and `linux/arm64`, pushes `psyb0t/wickworks:latest` and `psyb0t/wickworks:sha-<commit>` to Docker Hub, scans it with Grype (findings go to the Security tab without failing the run), and updates the version and license badges.
- **A `v*` tag:** waits for the `main` run of the same commit to succeed, points the release tag at that run's `sha-<commit>` image without rebuilding, cuts the GitHub release, publishes the skill and the OpenClaw plugin to ClawHub, and publishes `server.json` to the MCP Registry.

Other workflows mirror the repository and manage issues; they do not build anything.

## Releases

1. Update the version in `pyproject.toml`, `uv.lock` (the `wickworks` entry) and [`.agents/.codex-plugin/plugin.json`](https://github.com/psyb0t/docker-wickworks/blob/main/.agents/.codex-plugin/plugin.json).
2. Add a `## vX.Y.Z (YYYY-MM-DD)` entry to the [CHANGELOG](https://github.com/psyb0t/docker-wickworks/blob/main/CHANGELOG.md). Before 1.0, call out any breaking request or response change.
3. Push to `main` and let the pipeline pass.
4. Push an annotated `vX.Y.Z` tag on that commit.

The tag pipeline fails if the `main` run for the tagged commit failed or never ran, so tag only commits that are already on `main`.
