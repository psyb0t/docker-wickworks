"""Divergence trend detection.

A divergence trend is when 2+ different indicators show divergences of the
same type where consecutive divergence endpoints (idx2) are each within
`window` bars of the next (default 10) — forming a sequential chain.

Indicators must fire at distinct bars (simultaneous hits on the same pivot
are divergence confluence, not a trend).

The highlighted span runs from the earliest idx1 in the chain to the latest
idx2.
"""

import pandas as pd


def detect_div_trends(
    df: pd.DataFrame,
    window: int = 10,
    min_count: int = 2,
    divergences: list[dict] | None = None,
) -> list[dict]:
    """Return divergence trend events across all tracked indicators.

    Each dict:
        type        – "bearish" or "bullish"
        bar_start   – earliest idx1 in the chain (start of first divergence)
        bar_end     – latest idx2 in the chain (end of last divergence)
        indicators  – indicator labels in chronological fire order
        count       – number of distinct indicators
    """
    if divergences is None:
        from . import detect_all_divergences

        divergences = detect_all_divergences(df)

    divs = divergences
    results: list[dict] = []

    for div_type in ("bearish", "bullish"):
        # (idx2, idx1, label) sorted by idx2 ascending
        events = sorted(
            [(d["idx2"], d["idx1"], d["label"]) for d in divs if d["type"] == div_type],
            key=lambda x: x[0],
        )

        if len(events) < min_count:
            continue

        # Build chains: extend while consecutive idx2 gap <= window
        current: list[tuple[int, int, str]] = []
        chains: list[list[tuple[int, int, str]]] = []

        for idx2, idx1, label in events:
            # Chain if new div STARTS within window bars of previous div ENDING
            if not current or idx1 - current[-1][0] <= window:
                current.append((idx2, idx1, label))
                continue
            if len({lbl for _, _, lbl in current}) >= min_count:
                chains.append(list(current))
            current = [(idx2, idx1, label)]

        if len({lbl for _, _, lbl in current}) >= min_count:
            chains.append(current)

        for chain in chains:
            # Simultaneous hits on the same pivot = confluence, not a trend
            if len({idx2 for idx2, _, _ in chain}) < 2:
                continue

            seen: set[str] = set()
            ordered_labels: list[str] = []
            for _, _, lbl in chain:
                if lbl not in seen:
                    seen.add(lbl)
                    ordered_labels.append(lbl)

            results.append(
                {
                    "type": div_type,
                    "bar_start": min(idx1 for _, idx1, _ in chain),
                    "bar_end": max(idx2 for idx2, _, _ in chain),
                    "indicators": ordered_labels,
                    "count": len(seen),
                }
            )

    return results
