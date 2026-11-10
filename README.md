# wickworks

[![CI](https://github.com/psyb0t/docker-wickworks/actions/workflows/pipeline.yml/badge.svg?branch=main)](https://github.com/psyb0t/docker-wickworks/actions/workflows/pipeline.yml)
[![version](https://raw.githubusercontent.com/psyb0t/docker-wickworks/badges/version.svg)](https://github.com/psyb0t/docker-wickworks/releases)
[![license](https://raw.githubusercontent.com/psyb0t/docker-wickworks/badges/license.svg)](https://github.com/psyb0t/docker-wickworks/blob/main/LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/psyb0t/wickworks?style=flat-square)](https://hub.docker.com/r/psyb0t/wickworks)

The dumb-as-rocks OHLC analyzer. You throw bars at it over HTTP, it throws indicators and SMC objects back. That's the whole product. No database, no queue, no state, no opinions, no "AI-powered signals," no upsell to a $97/mo Discord. Just the numbers.

Every snake-oil-flavored TA SaaS out there wants to tell you when to buy. Wickworks tells you the order block is at 1.0832 and the RSI is 71.4. The "what does that mean?" part is where your strategy lives, and it should live in your code, not behind someone else's paywall.

Built on `pandas-ta` and `smartmoneyconcepts`, wrapped in a FastAPI server with an MCP endpoint, locked behind 377 tests, including formulas written from scratch and diffed against the output on real EURUSD bars. If a math bug slips in, the test suite screams before the image ships.

## Table of Contents

- [What's inside](#whats-inside)
- [Quick start](#quick-start)
- [MCP and agents](#mcp-and-agents)
- [Documentation](#documentation)
- [Development](#development)
- [Sponsor](#sponsor)
- [License](#license)

## What's inside

| Category | What you can ask for |
| --- | --- |
| **Trend** | SMA/EMA + 15 other moving averages, Donchian channels, Ichimoku, Aroon, Vortex, supertrend, PSAR, chandelier exit |
| **Momentum** | RSI, MACD, Stochastic, StochRSI, ADX, MFI, CCI, Williams %R, ROC, MOM, TSI, TRIX, UO, Fisher |
| **Volatility** | ATR, NATR, Bollinger Bands, Keltner Channels, TTM Squeeze |
| **Volume** | VWAP (anchored), VWMA, OBV, AD, ADOSC, CMF, KVO |
| **SMC** | Order blocks, fair value gaps, BOS/CHoCH, swing levels, S/R levels, liquidity, retracements, sessions, previous-period high/low |
| **Summaries** | Price, levels, momentum, volume, position, slope: last-bar snapshots in one call |

All JSON field names are camelCase. `NaN` becomes `null`, never a literal `NaN` token that blows up downstream parsers. Bars in UTC, math in UTC, container runs `TZ=UTC`. Timezone bullshit is your problem, not mine.

## Quick start

```bash
docker run --rm -p 127.0.0.1:8000:8000 psyb0t/wickworks:latest
```

Send bars plus the indicators you want. You get back only what you asked for, under the names you picked:

```bash
curl -s -X POST http://localhost:8000/ \
  -H 'Content-Type: application/json' \
  -d @request.json
```

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
    "stochFast": {
      "type": "stoch",
      "k": 5,
      "d": 3
    },
    "macd": true,
    "orderBlocks": true
  }
}
```

The response holds `symbol`, `timeframe`, `candles`, `rsi`, `rsi21`, `stochFast`, `macd` and `orderBlocks`. Nothing else. Send enough bars for what you ask (at least 50 for the SMC outputs); if you don't, the 400 lists every under-fed indicator at once. wickworks has no auth, so keep the port on loopback or behind a proxy that does auth.

The [REST API page](https://psyb0t.github.io/docker-wickworks/api/) has the full request rules, response shapes and errors.

## MCP and agents

The same compute runs over a stateless streamable-HTTP [MCP](https://modelcontextprotocol.io) server at `/mcp` on the same port, with the tools `health`, `list_indicators`, `metadata` and `compute`:

```bash
claude mcp add --transport http wickworks http://localhost:8000/mcp
```

The [skill](https://github.com/psyb0t/docker-wickworks/tree/main/.agents/skills/wickworks) works in any agent that reads `.agents/skills/` (such as [peen](https://github.com/psyb0t/peen)), and installs natively in Claude Code, Codex and OpenClaw:

```bash
claude plugin marketplace add psyb0t/agents
claude plugin install wickworks@psyb0t

codex plugin marketplace add psyb0t/agents
codex plugin add wickworks@psyb0t

openclaw skills install @psyb0t/wickworks
```

The [agent integrations page](https://psyb0t.github.io/docker-wickworks/agent-integrations/) covers the stdio bridge plugin and tokens.

## Documentation

The full documentation lives at **[psyb0t.github.io/docker-wickworks](https://psyb0t.github.io/docker-wickworks/)**.

| Section | What it covers |
| --- | --- |
| [Install and run](https://psyb0t.github.io/docker-wickworks/deployment/) | `docker run`, compose, tags, platforms, scaling, upgrades |
| [Configuration](https://psyb0t.github.io/docker-wickworks/configuration/) | Every environment variable and its default |
| [REST API](https://psyb0t.github.io/docker-wickworks/api/) | Endpoints, request and response shapes, errors |
| [Indicator reference](https://psyb0t.github.io/docker-wickworks/indicators/) | Every series indicator with parameters and outputs |
| [SMC and summaries](https://psyb0t.github.io/docker-wickworks/smc/) | Order blocks, FVGs, structure, S/R, sessions and the summaries |
| [MCP server](https://psyb0t.github.io/docker-wickworks/mcp/) | The `/mcp` endpoint and its tools |
| [Agent integrations](https://psyb0t.github.io/docker-wickworks/agent-integrations/) | Claude Code, Codex and OpenClaw |
| [Security](https://psyb0t.github.io/docker-wickworks/security/) | No auth, exposure, input limits |
| [Troubleshooting](https://psyb0t.github.io/docker-wickworks/troubleshooting/) | Every error message and its fix |
| [Architecture](https://psyb0t.github.io/docker-wickworks/architecture/) | How a request flows, determinism |
| [Development](https://psyb0t.github.io/docker-wickworks/development/) | Tests, dependencies, CI and releases |

The machine-readable contract is [`schema.json`](https://github.com/psyb0t/docker-wickworks/blob/main/schema.json) (JSON Schema Draft 2020-12).

## Development

Docker and Make are all you need. Every target runs in a dev container.

```bash
make help        # list targets
make run         # uvicorn on :8000 in the dev container
make lint        # flake8 + mypy
make test-unit   # in-process tests, the fast loop
make test        # unit + docker integration tests, what CI runs
make docs        # build the documentation site
```

Dependencies only change through the `make pkg-*` targets, which move `uv`'s `exclude-newer` cutoff to today first. The [development page](https://psyb0t.github.io/docker-wickworks/development/) explains why, plus the test suite, CI and releases.

## Sponsor

<a href="https://www.buymeacoffee.com/psyb0t"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me a Coffee" height="60" width="217"></a>

## License

WTFPL, see [LICENSE](https://github.com/psyb0t/docker-wickworks/blob/main/LICENSE). Do what the fuck you want. The numba port in `smc_fast.py` keeps its upstream MIT license, see [THIRD_PARTY.md](https://github.com/psyb0t/docker-wickworks/blob/main/THIRD_PARTY.md).
