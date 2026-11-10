# Agent surface

Applies to `.agents/skills/`, `.agents/plugins/`, `.agents/.claude-plugin/`, `.agents/.codex-plugin/` and `server.json`.

- The indicator list in `.agents/skills/wickworks/SKILL.md` must equal `sorted(registry.INDICATORS)`.
- The OpenClaw plugin (`.agents/plugins/wickworks/`) is MIT, unlike the WTFPL repository. `bin/cli.js` only proxies stdio through `mcp-remote` to `$WICKWORKS_URL/mcp/` and adds `Authorization: Bearer $WICKWORKS_TOKEN` when that is set. Stdout is the MCP channel, so diagnostics go to stderr.
- `package.json` and `openclaw.plugin.json` keep version `0.0.0`; the ClawHub publish workflow sets the real version. `.agents/.codex-plugin/plugin.json` carries the release version.
- `pipeline.yml` publishes exactly the directories listed in `skill_names` and `plugin_names` of the `publish-to-clawhub` job. Add a new skill or plugin directory to those arrays.
- `server.json` `name` and the Dockerfile `LABEL` are both `io.github.psyb0t/wickworks`. Keep them equal.
- Examples use placeholders such as `SYMBOL_X`.
