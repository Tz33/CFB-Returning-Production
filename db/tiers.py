"""Conference tier classification for transfer-translation modeling.

Tiers always come from per-season team_seasons rows, never teams.conference
(which holds only the latest affiliation).
"""

# Power conferences. The Pac-12 counts as P only through 2023 — the 2024+
# two-team rump is competitively a G conference. FBS Independents are G
# except Notre Dame.
_POWER = {"SEC", "Big Ten", "Big 12", "ACC"}
_PAC12_NAMES = {"Pac-12", "Pac-10"}
_POWER_INDEPENDENTS = {"Notre Dame"}


def conference_tier(conference: str | None, season: int, school: str | None = None) -> str:
    """'P' (power) or 'G' (group-of-5/other FBS)."""
    if school in _POWER_INDEPENDENTS:
        return "P"
    if conference in _POWER:
        return "P"
    if conference in _PAC12_NAMES and season <= 2023:
        return "P"
    return "G"
