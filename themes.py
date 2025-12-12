# mtg_analyzer/themes.py
from __future__ import annotations
from typing import Set
import pandas as pd

from constants import THEME_KEYWORDS, KEYWORD_THEME_OVERRIDES

def detect_card_themes(card_row: pd.Series) -> set[str]:
    """
    Inspect a card's oracle_text + type_line and return ALL themes
    it appears to match, based on THEME_KEYWORDS and keyword abilities.
    """
    text = (str(card_row.get("oracle_text", "")) + " " +
            str(card_row.get("type_line", ""))).lower()

    matched: set[str] = set()

    # 1) Phrase-based themes (your existing THEME_KEYWORDS)
    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched.add(theme)
                break  # don't double count within one theme

    # 2) CR keyword abilities → themes (this is where all 702.x live)
    for kw, themes in KEYWORD_THEME_OVERRIDES.items():
        if kw in text:
            matched.update(themes)

    # 3) Broad backups (catch weird templating)
    if "graveyard" in text:
        matched.add("graveyard")
    if "gain" in text and "life" in text:
        matched.add("lifegain")
    if "lands you control" in text or "land you control" in text:
        matched.add("lands")
    if "counters on target" in text or "counters on it" in text:
        matched.add("counters")
    if "players can't" in text or "players can’t" in text:
        matched.add("control")

    return matched

def get_commander_themes(commander_row: pd.Series) -> set[str]:
    return detect_card_themes(commander_row)

def card_matches_themes(card_row: pd.Series, themes: set[str]) -> bool:
    if not themes:
        return False
    card_theme_set = detect_card_themes(card_row)
    return bool(card_theme_set & themes)