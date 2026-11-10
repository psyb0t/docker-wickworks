---
title: "MCP server"
description: "The wickworks Model Context Protocol server: stateless streamable HTTP at /mcp with health, list_indicators, metadata and compute tools, plus client setup."
nav_order: 7
---

# MCP server

wickworks serves a [Model Context Protocol](https://modelcontextprotocol.io) server in the same process as the REST API, at `/mcp` on the same port. An agent can compute indicators over JSON-RPC without a REST client. There is nothing to enable; the endpoint is always there.

The server uses the streamable HTTP transport in stateless mode with JSON responses. Every call stands alone: no `initialize` handshake is required, no session is kept, and responses are plain JSON instead of an SSE stream. Both `/mcp` and `/mcp/` work.

## Tools

| Tool | Arguments | Returns |
| --- | --- | --- |
| `health` | none | `{ ok, version }`, the same as [`GET /health`](api.md#get-health) |
| `list_indicators` | none | `{ indicators: [...] }`, every type `compute` accepts, sorted |
| `metadata` | none | The output catalog, the same as [`GET /metadata`](api.md#get-metadata) |
| `compute` | `bars`, `indicators`, `timeframe` (optional), `symbol` (optional) | The same envelope as [`POST /`](api.md#post-) |

`compute` validates its arguments with the same model as the REST endpoint, so the [request rules](api.md#request-fields) and the [indicator specs](api.md#the-indicators-object) are identical. The result is the same camelCase JSON the REST API returns for the same input.

## Connect a client

Clients that support remote streamable-HTTP servers connect straight to the endpoint. Claude Code:

```bash
claude mcp add --transport http wickworks http://localhost:8000/mcp
```

For a client that only starts local stdio servers, the [`@psyb0t/wickworks`](agent-integrations.md#openclaw-and-other-stdio-clients) plugin bridges stdio to `/mcp/`.

## Raw JSON-RPC

Because the server is stateless, you can call a tool with a single POST:

```bash
curl -s http://localhost:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "health",
      "arguments": {}
    }
  }'
```

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"ok\": true,\n  \"version\": \"0.7.1\"\n}"
      }
    ],
    "structuredContent": {
      "ok": true,
      "version": "0.7.1"
    },
    "isError": false
  }
}
```

The `Accept` header above is what the streamable HTTP specification asks clients to send. The server answers with JSON either way. A `compute` call carries the bars and indicators in `arguments`:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "compute",
    "arguments": {
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
        "rsi": true
      }
    }
  }
}
```

## Errors

Tool failures do not use HTTP status codes. The JSON-RPC call succeeds and the result has `isError: true` with the message as text:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error executing tool compute: insufficient_bars: insufficient bars: have 1, but: rsi (type=rsi) needs 15 (available=1, deficits=[{'outputKey': 'rsi', 'type': 'rsi', 'required': 15, 'available': 1}])"
      }
    ],
    "isError": true
  }
}
```

The messages match the REST errors: empty bars or indicators, too many bars (`too many bars: N > MAX_BARS=5000`), `invalid request: ...` with the validation details where REST would answer 422, unknown indicator types and parameters, and insufficient bars. The [troubleshooting page](troubleshooting.md) lists them.

## Access control

The MCP endpoint has no authentication, like the rest of wickworks. The MCP SDK's DNS-rebinding protection, which only accepts an allowlist of `Host` headers, is turned off so the endpoint works behind any hostname or reverse proxy. Put access control in the proxy; see [Security](security.md).
