"""Transfer production translation coefficients across conference tiers.

Aggregate ratios sum(dest production)/sum(origin production) for players with
meaningful origin-season production who appear on a different FBS team's
roster the next season (zero-production destinations included — no
survivorship bias).
"""

# provenance: analysis/estimate_transfer_translation.py, dest seasons
# 2021-2025 (portal era), offense = total_yards >= 100 (n=1,255),
# defense = tackles >= 10 (n=1,573)
TRANSLATION: dict[str, dict[tuple[str, str], float]] = {
    "offense": {("G", "G"): 0.944, ("G", "P"): 0.583, ("P", "G"): 1.48, ("P", "P"): 1.056},
    "defense": {("G", "G"): 0.957, ("G", "P"): 0.642, ("P", "G"): 1.534, ("P", "P"): 0.969},
}


def translate(production: float, origin_tier: str, dest_tier: str, side: str) -> float:
    """Expected destination-context production for a transfer."""
    return production * TRANSLATION[side][(origin_tier, dest_tier)]
