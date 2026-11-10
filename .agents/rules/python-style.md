# Python style

Applies to `src/wickworks/` and `tests/`.

- Target Python 3.12 (`requires-python >=3.12`, the images run 3.12). Start new modules with `from __future__ import annotations`. `mypy src` runs with `ignore_missing_imports = true`.
- `make lint` runs `flake8 --extend-ignore=E203,E501 src tests` and `mypy src` inside the dev image. `make format` runs isort (profile `black`) and black at line length 100.
- Module-level constants for limits and windows carry a leading underscore (`_SR_EVIDENCE_BARS`, `_OB_TOUCH_SETTLE_BARS`, `_SLOPE_LOOKBACK`).
- Loggers are named `logging.getLogger("wickworks...")`. Unexpected failures are logged with `log.exception`, then re-raised or mapped to the HTTP or MCP error.
- Domain failures raise the classes in `errors.py`, which subclass both `WickworksError` and `ValueError`. Error messages name the output key and the offending parameter, as `validation._invalid` does.
- Configuration comes only from `config.py`. Read new settings there with a default, and document them on the configuration docs page.
- Keep the comments that record a library quirk or a past bug (the CCI in-house implementation, the crypto precision notes, the MCP trailing-slash middleware).
