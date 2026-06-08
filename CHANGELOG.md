# Changelog

All notable changes per release. Versions follow [semver](https://semver.org)
pre-1.0 conventions: minor bumps may include breaking REST changes (called
out explicitly), patch bumps are docs / build / fixes only.

## v0.5.1 — 2026-06-08

Per-OB `touch_count` + raw `touch_events` for trader-eye freshness.

- Adds `touch_events: list[int]` per OB: the 1-based bar offsets from
  the OB candle where a contiguous run of later-bar [low..high]
  intersected the OB's [bottom..top] BEGAN. Each in-and-out of the
  zone = one entry. Raw list lets the chart frontend apply a user-
  tunable settle window without having to recompute server-side.
- Adds `touch_count: int` per OB: the same data, with the default
  settle window applied (`_OB_TOUCH_SETTLE_BARS = 5` — touches at
  offset 1..5 are dropped as OB-own-impulse continuation). Consumers
  that can't see the FE cog (quanthex scoring) read this directly.
- Captures the trader's "price already tested this zone N times"
  intuition. Neither lib mitigation flag does — the lib only fires
  on invalidating breaks (price PAST the zone in the wrong direction),
  not on entries/exits.
- Cost: one numpy slice + diff per OB to detect rising edges. Sub-ms.
- Additive — existing flags + cap unchanged.

## v0.5.0 — 2026-06-07

Surface both mitigation criteria for SMC order blocks.

- Order block extraction no longer drops mitigated OBs at the source.
  Every OB the smc lib detects now ships through, each tagged with two
  flags so the consumer can pick its own freshness criterion:
  - `mitigatedWick` — a later bar's wick fully traversed the zone
    (the loose, lib-default criterion that was the previous filter)
  - `mitigatedClose` — a later bar's close crossed into/through the
    zone (the stricter criterion most SMC traders read by eye)
- Runs `smc.ob` twice internally (one pass per `close_mitigation` value)
  to derive both flags; OB type/top/bottom/origin bar stay identical
  between the passes.
- `_order_blocks` cap raised 20 → 40 since we no longer pre-filter — a
  tighter cap would silently drop signals consumers might still want.
- **Breaking for FE renderers that assumed all OBs were live.** Filter
  on `mitigatedClose === false` for the strict-fresh view, or on
  `mitigatedWick === false` for the legacy behavior.
- Quanthex scoring continues to gate on `mitigated_wick` (unchanged
  semantics); the new flag is purely additive for chart overlays.

## v0.4.0 — 2026-05-30

Human-readable metadata catalog + GET /metadata endpoint.

- Adds `GET /metadata` returning a static catalog of every indicator,
  signal, and level the compute endpoint emits, with human labels,
  descriptions, interpretation hints, units, and categories. Consumers
  fetch once on startup; cache invalidates on version bump.
- Includes `lookup(path)` helper with three-tier fallback
  (exact → strip array indices → bare leaf) so dynamic dot-paths like
  `retracements[42].Direction` or `prevTimeframe.rsi` still resolve.
- Covers all ~70 top-level registry indicators plus nested object
  fields for SMC events, retracements, sessions, and divergences.
- 321 unit tests passing (11 new metadata tests).
- Backwards compatible — no schema changes to the compute response.

## v0.3.3 — 2026-05-22

Single source of truth for version.

- Drops the hardcoded `__version__` literal in
  `src/wickworks/__init__.py` in favour of
  `importlib.metadata.version("wickworks")`. `pyproject.toml` is now the
  only place a release number lives, so the `/health` endpoint can't
  drift from the tag again the way it did between v0.3.1 and v0.3.2.
- No runtime behavior change.

## v0.3.2 — 2026-05-20

Filter ±Inf/NaN from JSON output; preserve crypto micro-cap precision.

- Hardens the JSON output path: indicator series and SMC events route
  through `safe_float` so ±Inf / NaN never reach FastAPI (previously
  crashed the response with HTTPException 500 on symbols whose
  internals divided by zero, e.g. neousd, flwusd). `analyze()` bails
  early on a degenerate last-bar close to avoid the downstream
  divide-by-price storm.
- `safe_float` gets a `decimals=None` opt-out so crypto prices below
  `1e-6` (SHIB / PEPE / micro-caps down to ~1e-15) are no longer
  silently floored to zero by the default 6-decimal round, which
  previously caused the `price > 0` guard to bail on perfectly valid
  symbols.
- Bug-fix only — no API shape change. 310 unit tests pass.

## v0.3.1 — 2026-05-15

Tighten Bar volume validation; drop alias doc surface.

- Stricter input validation on the `Bar` schema: `volume` must be
  a finite, non-negative number; rejects NaN, ±Inf, negative values
  with a clear 400 instead of silently propagating into indicator
  internals.
- Drops the secondary alias docs from the README — the canonical
  field names are the documented surface.

## v0.3.0 — 2026-05-10

Primitives-only purification.

- Removed every legacy "computed signal" the early prototype shipped
  with — scores, weighted composites, derived buckets. Wickworks is
  now strictly bars-in → indicators + SMC objects out. Downstream
  consumers (quanthex) own all scoring logic.
- **Breaking.** Response no longer includes the score/composite top-
  level keys that v0.2 shipped; callers must compute their own.
- 287 unit tests passing.

## v0.2.0 — 2026-04-28

Initial public-ish release with full SMC coverage.

- Adds order blocks, FVGs, swing H/L, BOS/CHoCH, liquidity pools,
  previous H/L, sessions, retracements.
- FastAPI server + `/compute` POST endpoint.

## v0.1.0 — 2026-04-15

Initial scaffold.

- Bar schema, basic indicator surface (RSI, MACD, MA family).
- FastAPI server skeleton.
