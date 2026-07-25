# @psyb0t/wickworks

An OpenClaw/MCP plugin that connects your agent to a self-hosted
[wickworks](https://github.com/psyb0t/docker-wickworks) technical-analysis
service over the [Model Context Protocol](https://modelcontextprotocol.io).

wickworks already serves a Streamable-HTTP MCP endpoint at `/mcp/`. This
package is a thin stdio↔HTTP bridge (via
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote)) for MCP clients that
speak local stdio servers — it forwards everything to your running wickworks
instance and adds a bearer token when your endpoint requires one.

> wickworks is **self-hosted** and **stateless**. This plugin does not ship the
> analysis engine — it connects to a wickworks server that **you** run. See the
> [wickworks repo](https://github.com/psyb0t/docker-wickworks) to stand one up.

## Tools

The wickworks MCP tools become available to your agent:

- **`compute`** — feed OHLC bars + an indicator/SMC selection, get the computed
  primitives back (the same envelope as the REST `POST /`). No scoring, no
  opinions, no state.
- **`list_indicators`** — the registered indicator types you can request.
- **`metadata`** — the human-readable catalog of every output path `compute`
  can produce (cache it; it's static per wickworks version).
- **`health`** — liveness + the running wickworks version.

## Configuration

| Env var | Required | Description |
|---|---|---|
| `WICKWORKS_URL` | yes | Base URL of your running wickworks server, e.g. `http://localhost:8000`. The bridge appends `/mcp/`. |
| `WICKWORKS_TOKEN` | no | Bearer token — only if you front wickworks with a reverse proxy that requires connection-level auth (wickworks itself ships auth-less). |

## Install

Install it into your OpenClaw agent from ClawHub:

```bash
openclaw plugins install clawhub:@psyb0t/wickworks
```

Then set `WICKWORKS_URL` (and `WICKWORKS_TOKEN` if your endpoint uses auth) in
the plugin's environment.

## Native remote MCP (no install)

If your MCP client already supports **remote** Streamable-HTTP servers, you
don't need this bridge — point the client straight at `$WICKWORKS_URL/mcp/`
(with an `Authorization: Bearer <token>` header if your proxy requires one).

## License

MIT. See [LICENSE](LICENSE).
