# Dependencies

- Change dependencies only through the Make targets: `make pkg-add PKG=name==x.y.z`, `make pkg-remove PKG=name`, `make pkg-update PKG=name`, `make pkg-upgrade`. Each one runs `scripts/bump_exclude_newer.sh` first, which moves `[tool.uv] exclude-newer` in `pyproject.toml` to today's UTC midnight, then edits `uv.lock` inside the dev image. `make pkg-lock` refreshes the lock without moving the date.
- Do not hand-edit `exclude-newer`. It is the supply-chain age gate: `uv` refuses package versions published after it.
- Pin every runtime and dev dependency exactly (`==`) in `pyproject.toml`. Commit `pyproject.toml` and `uv.lock` together.
- The production image runs `uv sync --frozen` and, if that fails, falls back to an unfrozen `uv sync` that resolves again. A stale lock does not fail the build; the image then resolves inside the build instead of using the lock. Run `make pkg-lock` after any manual change to `pyproject.toml`.
- The OpenClaw plugin pins `mcp-remote` exactly in `.agents/plugins/wickworks/package.json`.
