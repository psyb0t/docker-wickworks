---
title: "Configuration"
description: "Every wickworks environment variable: LOG_LEVEL, MAX_BARS, MIN_BARS, WORKERS and DISABLE_SMC_FAST, with defaults and what each one changes."
nav_order: 3
---

# Configuration

wickworks reads its settings from environment variables when the process starts. The defaults work for a first run; there is nothing you have to set. A change takes effect on the next container start.

| Variable | Default | What it does |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Python logging level for the service (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Case does not matter. An unknown name falls back to `INFO`. |
| `MAX_BARS` | `5000` | The most bars one request may carry. A larger request gets HTTP 413 (over MCP, an error result). |
| `MIN_BARS` | `50` | The minimum bars for every SMC output and every summary, and for any indicator type without its own requirement. Series indicators compute their own minimum from their parameters. See [minimum bars](api.md#insufficient-bars). |
| `WORKERS` | `2` | Number of uvicorn worker processes in the container. |
| `DISABLE_SMC_FAST` | unset | Any non-empty value turns off the numba-accelerated SMC functions and runs the upstream `smartmoneyconcepts` code instead. The output is the same; it exists for debugging. |

`MAX_BARS`, `MIN_BARS` and `WORKERS` must be integers. A value that is not an integer is ignored and the default applies, without a warning.

`WORKERS` is read by the image's start command, not by the service code, so it applies to the Docker image only. `make run` starts a single uvicorn process.

## Examples

```bash
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  -e LOG_LEVEL=WARNING \
  -e MAX_BARS=20000 \
  -e WORKERS=4 \
  psyb0t/wickworks:latest
```

Raising `MAX_BARS` raises the memory and CPU one request can use. The analysis behind the SMC outputs walks the whole history, so a request for `orderBlocks` on 20000 bars takes noticeably longer than one on 500.

Lowering `MIN_BARS` lets the SMC outputs run on shorter histories. Swing, order block and S/R detection need history to find anything, so a very low value mostly returns empty arrays. [`srLevels`](smc.md#srlevels) returns nothing below 50 bars regardless of this setting.

## What is not configurable

- There is no authentication setting. Put access control in a reverse proxy; see [Security](security.md).
- The listening port inside the container is always 8000. Map a different host port instead.
- The timezone is UTC. Bars are UTC unix seconds and every UTC-based bucket (VWAP anchors, previous-period high and low, sessions) uses UTC.
