"""Player-name normalization for cross-source joins (NCAA stats <-> CFBD).

NCAA rosters and CFBD rosters share no player ids, so participation data is
joined on normalized names within a team-season. Normalization strips
diacritics, punctuation, spacing, and generational suffixes so that
"Frank Sutton, Jr." == "frank sutton" and "José Ramírez" == "Jose Ramirez".
"""
import re
import unicodedata

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_player_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    tokens = re.sub(r"[^a-z]+", " ", ascii_name.lower()).split()
    tokens = [t for t in tokens if t not in _SUFFIXES]
    return "".join(tokens)
