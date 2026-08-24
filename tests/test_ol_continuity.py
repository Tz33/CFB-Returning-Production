"""Tests for OL continuity: name normalization and starts-share math."""
from db.names import normalize_player_name
from etl.compute_ol_continuity import ol_starts_share


def test_normalize_strips_suffixes_and_punctuation():
    assert normalize_player_name("Frank Sutton, Jr.") == "franksutton"
    assert normalize_player_name("Lester Cotton Sr.") == "lestercotton"
    assert normalize_player_name("O.J. Howard") == "ojhoward"
    assert normalize_player_name("Da'Shawn Hand") == "dashawnhand"


def test_normalize_strips_diacritics():
    assert normalize_player_name("José Ramírez") == "joseramirez"


def test_normalize_matches_across_sources():
    # NCAA lists the suffix, CFBD doesn't
    assert normalize_player_name("Tim Keenan III") == normalize_player_name("Tim Keenan")


def test_suffix_only_stripped_as_token():
    # "sr"/"jr" inside a name must survive; only standalone suffix tokens drop
    assert normalize_player_name("Srinivas Junior") == "srinivasjunior"


def test_share_full_return():
    rows = [("A Lineman", 13), ("B Lineman", 13)]
    share, returning, total = ol_starts_share(rows, {"alineman", "blineman"})
    assert share == 1.0
    assert (returning, total) == (26, 26)


def test_share_partial_return():
    rows = [("A Lineman", 12), ("B Lineman", 4), ("C Backup", 0)]
    share, returning, total = ol_starts_share(rows, {"alineman", "cbackup"})
    assert share == 12 / 16
    assert (returning, total) == (12, 16)


def test_share_none_when_no_starts_recorded():
    rows = [("A Lineman", 0), ("B Lineman", 0)]
    share, _, total = ol_starts_share(rows, {"alineman"})
    assert share is None
    assert total == 0


def test_share_name_match_uses_normalization():
    rows = [("Frank Sutton, Jr.", 13)]
    share, _, _ = ol_starts_share(rows, {normalize_player_name("Frank Sutton")})
    assert share == 1.0
