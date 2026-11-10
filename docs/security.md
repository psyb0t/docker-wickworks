---
title: "Security"
description: "What wickworks can reach and store, why it has no authentication, the MCP Host check it turns off, its input limits, and what to set up before exposing it."
nav_order: 9
---

# Security

wickworks is built to sit on a private network or behind your own proxy. Read this page before you publish its port anywhere other people can reach.

## No authentication

wickworks has no authentication of any kind, on the REST API or on the MCP endpoint. Anyone who can reach the port can call every endpoint. There is no setting to turn auth on.

Bind the port to loopback unless something else needs it:

```bash
docker run --rm -p 127.0.0.1:8000:8000 psyb0t/wickworks:latest
```

To reach it from other machines, put a reverse proxy or a VPN in front that does the authentication, and keep wickworks itself on a private network. The `WICKWORKS_TOKEN` setting of the [agent plugin](agent-integrations.md) exists for exactly this: it sends a bearer token for your proxy to check. wickworks ignores it.

The repository's `docker-compose.yml` and `make run` publish the port on every interface. Add `127.0.0.1:` to the port mapping on any host with a public interface.

## MCP Host check is off

The MCP SDK can reject requests whose `Host` header is not on an allowlist, a protection against DNS rebinding attacks from a browser. wickworks turns it off, because a self-hosted service reached through arbitrary hostnames and proxies would otherwise reject every real deployment. The consequence: a web page open in a browser on the same machine could try to reach a wickworks bound to localhost through DNS rebinding. All it could do is run computations, since there is nothing to read or change, but it is another reason to keep wickworks off machines where you browse the web, or behind a proxy that checks `Host`.

## What it can reach and store

- **No outbound network.** wickworks never fetches market data or calls another service. It computes on the bars in the request and returns numbers.
- **No storage.** It writes no files and keeps nothing between requests. There is no database, cache or log of request bodies. Restarting the container loses nothing.
- **Logs.** The service logs at `LOG_LEVEL`. A failed computation logs the traceback with the request's `symbol` and `timeframe`, but not the bars.

## Input limits

Every request is bounded before any computation starts:

- At most `MAX_BARS` bars (default 5000). More gets 413.
- `symbol` up to 128 characters, `timeframe` up to 32.
- Every bar is checked: positive finite prices, consistent high and low, finite non-negative volume, strictly increasing times, no extra fields.
- Every indicator parameter is checked for name, type and range.

FastAPI parses and validates the whole body before the `MAX_BARS` check runs, so a very large body still costs memory and CPU to reject. There is no request body size limit in wickworks itself; set one in your proxy if untrusted clients can reach it.

A request that passes validation can still be expensive. SMC outputs walk the full history, and raising `MAX_BARS` raises the cost of one request. Rate-limit in the proxy if clients are untrusted.

## Errors do not leak internals

A failure inside an indicator returns 500 with the fixed body `{"detail": "indicator computation failed"}`. The traceback goes to the server log, never to the client.

## The container

The image runs as the unprivileged user `wickworks`, not root, and needs no capabilities, volumes or extra mounts. Base images and the `uv` installer are pinned by digest in the [Dockerfile](https://github.com/psyb0t/docker-wickworks/blob/main/Dockerfile). Every published image is scanned with Grype in CI, and the findings go to the repository's Security tab.

## Dependencies

All Python dependencies are pinned exactly and locked in [`uv.lock`](https://github.com/psyb0t/docker-wickworks/blob/main/uv.lock). The lock is resolved with `uv`'s `exclude-newer` date, so a package version published after that date cannot enter the lock; see [Development](development.md#dependencies).
