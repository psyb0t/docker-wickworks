# Testing

- `make test-unit` runs every test not marked `docker`, in process through `fastapi.testclient.TestClient` (`tests/_helpers.py`). It needs no network and no Docker socket.
- `make test` runs the unit tests plus the `docker` tests, which start `psyb0t/wickworks:test` through testcontainers and reach it on the container IP. `make test` and `make test-docker` build that image first. CI runs `make test`.
- Standard indicators get a closed-form reference in `tests/_helpers.py` written in plain numpy/pandas (no `pandas_ta`) and a last-bar comparison on the real fixture `tests/fixtures/eurusd_h1.json` with `assert_last_bar_matches`. A new indicator gets the same.
- `tests/test_smc_fast_parity.py` proves `smc_fast` matches upstream `smartmoneyconcepts`. Any change to `smc_fast.py` must keep it green.
- Contract tests cover determinism, append stability, warmup nulls, isolation between outputs, error paths, the volume field, the response envelope, `schema.json` parity and metadata coverage. Extend the matching file instead of starting a new one.
- Synthetic bars come from the generators in `tests/conftest.py` and `tests/_helpers.py`.
