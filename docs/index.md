---
title: "Home"
description: "wickworks is a stateless HTTP and MCP service: POST OHLCV bars plus the indicators you want, get back exactly those indicators and SMC objects."
nav_order: 1
permalink: /
seo:
  type: WebSite
---

# wickworks

wickworks is the dumb-as-rocks OHLC analyzer. You send bars over HTTP with a list of the indicators you want, and it sends those indicators back. 50 indicator series (RSI, MACD, Bollinger, ADX, Ichimoku and the rest, mostly computed by `pandas-ta`), plus Smart Money Concepts objects (order blocks, fair value gaps, BOS/CHoCH, swing structure, support and resistance) and a handful of last-bar summaries.

No database, no queue, no state, no signals. It tells you the order block sits at 1.0832 and the RSI is 71.4. What that means for a trade is your strategy's job, and it belongs in your code.

## Quick start

```bash
docker run --rm -p 127.0.0.1:8000:8000 psyb0t/wickworks:latest
```

```bash
curl -s http://localhost:8000/health
```

```json
{
  "ok": true,
  "version": "0.7.1"
}
```

Then post bars. Each bar is `time` (UTC unix seconds), `open`, `high`, `low`, `close` and `volume`, oldest first. With `bars.json` holding a request body:

```json
{
  "symbol": "EURUSD",
  "timeframe": "H1",
  "bars": [
    {
      "time": 1700000000,
      "open": 1.0832,
      "high": 1.0851,
      "low": 1.0828,
      "close": 1.0844,
      "volume": 1247
    }
  ],
  "indicators": {
    "rsi": true,
    "rsi21": {
      "type": "rsi",
      "length": 21
    },
    "macd": true,
    "orderBlocks": true
  }
}
```

```bash
curl -s -X POST http://localhost:8000/ \
  -H 'Content-Type: application/json' \
  -d @bars.json
```

The response holds `symbol`, `timeframe`, `candles`, and one entry per key in `indicators`: `rsi`, `rsi21`, `macd`, `orderBlocks`. Nothing you did not ask for. One bar is not enough for any of these, so a real request sends at least 50 bars (the [REST API page](api.md#insufficient-bars) explains the per-indicator minimums).

## What is on this site

| Page | What it covers |
| --- | --- |
| [Install and run](deployment.md) | `docker run`, docker compose, image tags, platforms, healthcheck, workers and upgrades |
| [Configuration](configuration.md) | Every environment variable, its default and what it changes |
| [REST API](api.md) | `GET /health`, `GET /metadata`, `POST /`, the request and response shapes, and every error |
| [Indicator reference](indicators.md) | Every series indicator: parameters, defaults, minimum bars and return shape |
| [SMC and summaries](smc.md) | Order blocks, FVGs, BOS/CHoCH, swing and S/R levels, the other SMC outputs, and the last-bar summaries |
| [MCP server](mcp.md) | The streamable-HTTP MCP endpoint at `/mcp` and its four tools |
| [Agent integrations](agent-integrations.md) | The skill and plugins for Claude Code, Codex and OpenClaw |
| [Security](security.md) | What wickworks can reach, what it stores, and what to do before exposing it |
| [Troubleshooting](troubleshooting.md) | Every error message, its cause and the fix |
| [Architecture](architecture.md) | How a request travels through the service, and why two replicas return the same bytes |
| [Development](development.md) | Building, linting, testing, dependency management, CI and releases |

## What it will not do

wickworks returns measurements, never trading signals. There is no divergence detection, no moving-average cross events, no buy or sell tags. Everything in a response is a raw indicator series, a structural fact (an order block formed at this bar, price closed past this swing), or a summary of those at the last bar. If you want crosses or divergences, build them on top of the series in your own consumer.

It also has no market data of its own. You bring the bars.
