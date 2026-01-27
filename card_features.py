"""
card_features.py

Lightweight, text-driven feature detectors for Commander deck analysis.

Design goals:
- Never crash on missing columns / NaNs.
- Prefer "good enough" heuristics over overfitting.
- Keep everything DATAFRAME-FRIENDLY (row-in, bool/float out).

If you later migrate to full CardObjects/EventAtoms, these functions should remain
valid as a fast first-pass layer.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


# -------------------------
# Small helpers
# -------------------------

def _s(v: Any) -> str:
    """Safe lowercased string."""
    if v is None:
        return ""
    return str(v).lower()

def _type(row) -> str:
    return _s(row.get("type_line", ""))

def _text(row) -> str:
    return _s(row.get("oracle_text", ""))

def _name(row) -> str:
    return str(row.get("name", "") or "")

def _cmc(row) -> float:
    try:
        return float(row.get("cmc", 0) or 0)
    except Exception:
        return 0.0


# -------------------------
# Core card type checks
# -------------------------

def is_land(row) -> bool:
    tl = _type(row)
    # Includes Artifact Land, Basic Land, etc.
    return "land" in tl

def is_creature(row) -> bool:
    return "creature" in _type(row)

def is_artifact(row) -> bool:
    return "artifact" in _type(row)

def is_enchantment(row) -> bool:
    return "enchantment" in _type(row)

def is_instant_or_sorcery(row) -> bool:
    tl = _type(row)
    return ("instant" in tl) or ("sorcery" in tl)


# -------------------------
# Ramp / Draw / Removal / Wipes
# -------------------------

_RAMP_PATTERNS = [
    r"\badd\s*\{",                         # "Add {G}"
    r"\badd\s+\w+\s+mana\b",               # "add one mana"
    r"\badd\s+\w+\s+mana\s+of\s+any\s+color\b",
    r"\bsearch your library for (a|two|up to two) land",  # land ramp
    r"\bput (a|two|up to two) land card[s]? from your (hand|graveyard|library) onto the battlefield\b",
    r"\btreasure token\b",
    r"\bcreate (a|two|three|x) treasure\b",
    r"\buntap (up to )?\w+ lands?\b",
    r"\breveal.*land card.*put.*onto the battlefield\b",
]

def is_ramp(row) -> bool:
    if is_land(row):
        return False
    t = _text(row)
    # avoid false positives like "add a counter" etc.
    if "add a +1/+1 counter" in t or "add a counter" in t:
        # still might be mana in text, but this kills the worst FP.
        pass
    return any(re.search(p, t) for p in _RAMP_PATTERNS)

_DRAW_PATTERNS = [
    r"\bdraw (a|two|three|four|x) card",
    r"\bdraw cards\b",
    r"\blook at the top \d+ cards? of your library\b",
    r"\breveal the top \d+ cards? of your library\b",
    r"\bimpulse draw\b",                   # slang sometimes appears in notes; harmless
    r"\bexile the top \d+ cards? of your library\b.*\byou may play\b",  # impulse
    r"\bwhenever you draw\b",              # engines
    r"\bat the beginning of your upkeep\b.*\bdraw\b",
    r"\bwhenever .* attacks?\b.*\bdraw\b",
]

def is_card_draw(row) -> bool:
    if is_land(row):
        return False
    t = _text(row)
    # Don't count "each opponent draws" as your draw; but if it says "each player draws", it can still be CA parity.
    # We'll be permissive for now; refine later if needed.
    return any(re.search(p, t) for p in _DRAW_PATTERNS)

_REMOVAL_PATTERNS = [
    r"\bdestroy target\b",
    r"\bexile target\b",
    r"\breturn target\b.*\bto its owner's hand\b",
    r"\b(counter|counter target)\b",
    r"\bfight target\b",
    r"\bdeals? \d+ damage to target\b",
    r"\btarget creature gets -\d+/-\d+\b",
    r"\bsacrifice\b.*\btarget\b",  # edicts
]

def is_removal(row) -> bool:
    if is_land(row):
        return False
    t = _text(row)
    # If it's clearly a wipe, don't double-count as single-target removal.
    if is_board_wipe(row):
        return False
    return any(re.search(p, t) for p in _REMOVAL_PATTERNS)

_WIPE_PATTERNS = [
    r"\bdestroy all\b",
    r"\bexile all\b",
    r"\breturn all\b.*\bto their owners' hands\b",
    r"\beach creature\b.*\bdestroy\b",
    r"\beach nonland permanent\b",
    r"\ball creatures get -\d+/-\d+\b",
]

def is_board_wipe(row) -> bool:
    if is_land(row):
        return False
    t = _text(row)
    return any(re.search(p, t) for p in _WIPE_PATTERNS)


# -------------------------
# High-impact / "game changer" heuristics
# -------------------------

def is_extra_turn(row) -> bool:
    t = _text(row)
    return bool(re.search(r"\btake an extra turn\b", t))

def is_mass_land_denial(row) -> bool:
    t = _text(row)
    # Armageddon-style, or heavy stax on lands
    if re.search(r"\bdestroy all lands\b", t):
        return True
    if re.search(r"\beach player sacrifices (all|a) lands?\b", t):
        return True
    # Winter Orb / Stasis-like effects
    if re.search(r"\b(lands?|permanents?) don't untap\b", t) and ("each" in t or "players" in t):
        return True
    return False

def is_nonland_tutor(row) -> bool:
    t = _text(row)
    # Land tutors are usually ramp; we want "find any card / nonland card"
    if "search your library" not in t:
        return False
    if re.search(r"\bsearch your library for (a|an) land\b", t):
        return False
    # Common nonland tutor phrasings
    return bool(
        re.search(r"\bsearch your library for (a|an) (card|creature|artifact|enchantment|instant|sorcery|planeswalker)\b", t)
        or re.search(r"\bsearch your library for a nonland card\b", t)
    )

def is_game_changer(row) -> bool:
    """
    Very coarse 'this spikes the power level' detector.
    This should be conservative; false positives are annoying.
    """
    t = _text(row)
    # Auto-wins / alt-wins
    if re.search(r"\byou win the game\b", t) or re.search(r"\bwin the game\b", t):
        return True
    # Extra turns
    if is_extra_turn(row):
        return True
    # Mass land denial
    if is_mass_land_denial(row):
        return True
    # Strong tutors (nonland)
    if is_nonland_tutor(row) and _cmc(row) <= 3.0:
        return True
    # "Infinite mana" is not usually spelled out, but "any number" + untap can be a hint. Keep it mild.
    if "infinite" in t:
        return True
    return False


# -------------------------
# Persistent output / engines
# -------------------------

def has_persistent_output(row) -> bool:
    """
    Detect *repeatable* advantage sources:
    - triggered or activated abilities on permanents that repeatedly make mana/cards/tokens
    - "at the beginning of", "whenever", "each" patterns
    """
    if is_land(row):
        # Lands can be engines (Cabal Coffers), but treat them separately via persistence_score
        pass

    tl = _type(row)
    t = _text(row)

    # Instants/sorceries are not persistent engines by themselves
    if "instant" in tl or "sorcery" in tl:
        return False

    # Trigger-based repetition
    if re.search(r"\bwhenever\b", t) or re.search(r"\bat the beginning of\b", t):
        if any(x in t for x in ["draw", "create", "add {", "treasure", "token", "return", "exile the top"]):
            return True

    # Activated abilities with a repeatable output
    # e.g., "{T}: Add {G}", "{2}, {T}: Draw a card"
    if re.search(r"\{t\}:\s*add\s*\{", t):
        return True
    if re.search(r"\{t\}:\s*draw\b", t):
        return True
    if re.search(r":\s*create\b.*token", t):
        return True

    # Continuous / replacement engines (Rhystic Study style)
    if "whenever an opponent" in t and "draw" in t:
        return True

    return False

def persistence_score(row) -> float:
    """
    Score how 'engine-y' the card is. Used for sorting/reporting.
    0 = not an engine by our heuristics.
    """
    t = _text(row)
    tl = _type(row)

    if not has_persistent_output(row):
        return 0.0

    score = 1.0

    # Bigger if it's hard to remove (enchantment/land)
    if "enchantment" in tl:
        score += 0.75
    if "land" in tl:
        score += 0.75
    if "artifact" in tl:
        score += 0.25

    # Draw engines > token engines > mana engines (roughly)
    if "draw" in t:
        score += 1.25
    if "create" in t and "token" in t:
        score += 0.75
    if "add {" in t or "treasure" in t:
        score += 0.5

    # Trigger quality
    if "whenever" in t:
        score += 0.5
    if "at the beginning of" in t:
        score += 0.25

    # Soft cap so sorting doesn't go nuts
    return float(min(score, 5.0))
