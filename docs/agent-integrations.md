---
title: "Agent integrations"
description: "Install the wickworks agent skill and plugins in Claude Code, Codex and OpenClaw, and bridge stdio-only MCP clients to a running wickworks server."
nav_order: 8
---

# Agent integrations

The repository ships an agent skill and an MCP bridge plugin so coding agents can call a wickworks server you run. Neither contains the analysis engine. Start the server first ([Install and run](deployment.md)), then point the agent at its URL.

| Piece | Where | What it does |
| --- | --- | --- |
| Skill | [`.agents/skills/wickworks/`](https://github.com/psyb0t/docker-wickworks/tree/main/.agents/skills/wickworks) | Teaches an agent the REST and MCP API, the indicator names and the errors |
| OpenClaw plugin `@psyb0t/wickworks` | [`.agents/plugins/wickworks/`](https://github.com/psyb0t/docker-wickworks/tree/main/.agents/plugins/wickworks) | A stdio-to-HTTP MCP bridge for clients that only run local stdio servers (MIT licensed) |
| Claude Code and Codex manifests | [`.agents/.claude-plugin/`](https://github.com/psyb0t/docker-wickworks/tree/main/.agents/.claude-plugin), [`.agents/.codex-plugin/`](https://github.com/psyb0t/docker-wickworks/tree/main/.agents/.codex-plugin) | Package the skill as a plugin for those clients |

The skill works in any agent that reads `.agents/skills/`, such as [peen](https://github.com/psyb0t/peen).

## Claude Code

```bash
claude plugin marketplace add psyb0t/agents
claude plugin install wickworks@psyb0t
```

Claude Code asks for the wickworks URL and, if a reverse proxy in front of wickworks requires one, a bearer token. It stores the token in your OS keychain.

Claude Code also speaks remote MCP, so you can connect the tools without the plugin:

```bash
claude mcp add --transport http wickworks http://localhost:8000/mcp
```

## Codex

```bash
codex plugin marketplace add psyb0t/agents
codex plugin add wickworks@psyb0t
```

Installed through the marketplace, the skill is invoked as `$wickworks:wickworks`. Codex also picks the skill up without any install in a repository that contains `.agents/skills/`; there it is invoked as `$wickworks`.

## OpenClaw and other stdio clients

The skill is published to ClawHub with every release:

```bash
openclaw skills install @psyb0t/wickworks
```

The plugin bridges a stdio MCP client to the server's `/mcp/` endpoint through [`mcp-remote`](https://www.npmjs.com/package/mcp-remote):

```bash
openclaw plugins install clawhub:@psyb0t/wickworks
```

Then set these in the plugin's environment:

| Variable | Required | Description |
| --- | --- | --- |
| `WICKWORKS_URL` | yes | Base URL of your server, such as `http://localhost:8000`. The bridge appends `/mcp/` |
| `WICKWORKS_TOKEN` | no | Sent as `Authorization: Bearer <token>`. Only needed when a reverse proxy in front of wickworks checks it; wickworks itself has no auth |

The bridge exits with an error message on stderr when `WICKWORKS_URL` is unset. It writes nothing else of its own, because stdout carries the MCP protocol, and it never logs the token.

The bridge runs on Node.js 18 or newer. Any MCP client that starts stdio servers can run its `wickworks-mcp` command the same way.

## Tools the agent gets

Through MCP, by plugin or directly: `health`, `list_indicators`, `metadata` and `compute`. See [MCP server](mcp.md) for arguments and results. Through the skill alone, the agent calls the [REST API](api.md) with `curl`; the skill lists `docker` (to run the server) and `curl` as the programs it needs.
