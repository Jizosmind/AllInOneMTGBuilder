# card_features.py
from __future__ import annotations
import pandas as pd

from constants import MASS_LAND_DENIAL_NAMES

def is_land(row: pd.Series) -> bool:
    return "Land" in str(row.get("type_line", ""))

def is_ramp(row: pd.Series) -> bool:
    text = str(row.get("oracle_text", "")).lower()
    type_line = str(row.get("type_line", "")).lower()
    cmc = row.get("cmc", 0)

    # Mana rocks / dorks / treasures / land tutors
    ramp_keywords = [
        "add {",                      # mana abilities
        "search your library for a land card",
        "search your library for up to one basic land",
        "treasure token",
        "create a treasure token",
        "create a treasure artifact token",
        "gain control of target land until end of turn and untap it",
    ]

    if "creature" in type_line and "mana" in text:
        return True

    if cmc <= 4:
        for kw in ramp_keywords:
            if kw in text:
                return True

    return False

def is_card_draw(row: pd.Series) -> bool:
    text = str(row.get("oracle_text", "")).lower()
    # crude but effective: anything that literally says "draw a card"
    return "draw a card" in text or "draw two cards" in text or "draw three cards" in text

def is_board_wipe(row: pd.Series) -> bool:
    text = str(row.get("oracle_text", "")).lower()
    # look for "destroy all" / "each creature" style phrases
    wipe_phrases = [
        "destroy all creatures",
        "destroy all nonland permanents",
        "each creature gets",
        "all creatures get",
        "each creature loses",
        "exile all creatures",
        "exile all nonland permanents",
    ]
    for kw in wipe_phrases:
        if kw in text:
            return True
    return False

def is_removal(row: pd.Series) -> bool:
    # single-target removal or counterspells
    text = str(row.get("oracle_text", "")).lower()
    type_line = str(row.get("type_line", "")).lower()

    # board wipes are handled separately
    if is_board_wipe(row):
        return False

    removal_keywords = [
        "destroy target",
        "exile target",
        "counter target",
        "fight target",
        "deals damage to target creature",
        "deals damage to any target",
    ]
    for kw in removal_keywords:
        if kw in text:
            return True

    # enchantment-based removal like "enchant creature" that stops it
    if "aura" in type_line and "enchant creature" in text and (
        "can't attack" in text or "can't block" in text or "loses all abilities" in text
    ):
        return True

    return False

def is_game_changer(row: pd.Series) -> bool:
    """
    Use Scryfall's built-in game_changer flag instead of a manual name list.
    """
    val = row.get("game_changer", False)
    # Sometimes this might be bool, sometimes 0/1, sometimes None
    return bool(val)

def is_mass_land_denial(row: pd.Series) -> bool:
    if row.get("name") in MASS_LAND_DENIAL_NAMES:
        return True
    text = str(row.get("oracle_text", "")).lower()
    # very crude pattern-based backup
    if "destroy all lands" in text:
        return True
    if "each land" in text and ("doesn't untap" in text or "becomes" in text):
        return True
    return False

def is_extra_turn(row: pd.Series) -> bool:
    text = str(row.get("oracle_text", "")).lower()
    return "take an extra turn" in text or "extra turn after this one" in text

def is_nonland_tutor(row: pd.Series) -> bool:
    text = str(row.get("oracle_text", "")).lower()
    if "search your library" not in text:
        return False
    # Ignore pure land tutors (Rampant Growth, Cultivate, etc.)
    if "for a land card" in text or "for a basic land" in text:
        return False
    return True

def is_permanent_card(row: pd.Series) -> bool:
    type_line = str(row.get("type_line", "")).lower()
    return any(t in type_line for t in ("creature", "artifact", "enchantment", "planeswalker"))

def has_persistent_output(row: pd.Series) -> bool:
    text = str(row.get("oracle_text", "")).lower()
    # Crude example rules, tune later:
    if "create" in text and "token" in text:
        return True
    if "emblem" in text:
        return True
    # “Until end of turn” usually means non-persistent
    if "until end of turn" in text:
        return False
    # Any static anthem/effect text
    if "creatures you control" in text or "you control get" in text:
        return True
    return False

def persistence_score(row: pd.Series) -> float:
    """
    0 = totally ephemeral (one-shot spell)
    1 = somewhat persistent (makes tokens / has residual impact)
    2 = permanent engine (stays and does stuff)
    """
    score = 0.0
    if is_permanent_card(row):
        score += 1.0
    if has_persistent_output(row):
        score += 1.0
    return score
