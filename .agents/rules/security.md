# Security

- Wickworks has no authentication and disables the MCP SDK's DNS-rebinding Host check (`TransportSecuritySettings(enable_dns_rebinding_protection=False)`), so it works behind any hostname. Docs and examples bind the port to loopback (`127.0.0.1:8000:8000`) and send off-host access through a reverse proxy that enforces auth. Keep that advice in the docs and the skill whenever either changes.
- The service makes no outbound network calls, writes no files and keeps nothing between requests. Do not add a feature that breaks any of the three without documenting it on the security docs page.
- Bound every input: `MAX_BARS` (413), `symbol` 128 and `timeframe` 32 characters, Pydantic bar checks, and parameter validation in `validation.py`. A new input field gets a limit.
- The 500 response body is the fixed string `indicator computation failed`; details go to the log only. Do not put exception text or request data in a 500 body.
- Never read, print or commit `.env` or `.env.*` files. `.gitleaks.toml` extends the default ruleset with a fake canary; keep test data free of real keys and tokens.
- The runtime image runs as the non-root user `wickworks`. Keep it that way.
