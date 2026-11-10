# Python style

Applies to `src/wickworks/` and `tests/`.

- Target Python 3.12 (`requires-python >=3.12`, the images run 3.12). Start new modules with `from __future__ import annotations` and type every function signature. `mypy src` must pass with `ignore_missing_imports = true` and no new `# type: ignore` without a reason.
- `make lint` runs `flake8 --extend-ignore=E203,E501 src tests` and `mypy src` inside the dev image. Both must report nothing. `make format` runs isort (profile `black`) and black at line length 100; run it before handing off.
- Module-level constants with a leading underscore for limits and windows (`_SR_EVIDENCE_BARS`, `_OB_TOUCH_SETTLE_BARS`, `_SLOPE_LOOKBACK`). Name the number instead of repeating it.
- Log through `logging.getLogger("wickworks...")` with `%s` arguments, never f-strings in log calls. `log.exception` on unexpected failures, then re-raise or map to the HTTP or MCP error.
- Domain failures raise the classes in `errors.py`, which subclass both `WickworksError` and `ValueError`. Error messages name the output key and the offending parameter, as `validation._invalid` does.
- Configuration comes only from `config.py`. Read new settings there with a default, and document them on the configuration docs page.
- `__version__` comes from package metadata in `__init__.py`. Never hardcode a version in Python.
- Comments say why. Keep the ones that record a library quirk or a past bug (the CCI in-house implementation, the crypto precision notes, the MCP trailing-slash middleware).
