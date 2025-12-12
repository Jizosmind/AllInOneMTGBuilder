from __future__ import annotations
from collections import defaultdict
import pandas as pd
import math


from card_effects import Card, card_from_row

from themes import (
    detect_card_themes, 
    card_matches_themes, 
    get_commander_themes
)

from roles import  get_card_roles

from card_features import (
    is_board_wipe,
    is_game_changer,
    is_mass_land_denial,
    is_extra_turn,
    is_nonland_tutor,
)

from constants import COMBO_FLAG_CARDS

# ─────────────────────────────────────────────────────────────
# New: generic 0–1 metric helpers
# ─────────────────────────────────────────────────────────────

# Features we care about for scarcity; extend as you add new flags
FEATURE_COLS = [
    "is_ramp",
    "is_card_draw",
    "is_board_wipe",
    "is_removal",
    "is_game_changer",
    "is_mass_land_denial",
    "is_extra_turn",
    "is_nonland_tutor",
    "has_persistent_output",
]


def efficiency_score(z: float, low: float = -2.0, high: float = 2.0) -> float:
    """
    Map a CMC z-score vs role into [0,1], where:
      - z <= low  → ~1.0 (very efficient)
      - z  = 0    →  0.5 (average)
      - z >= high → ~0.0 (very clunky)
    """
    if pd.isna(z):
        return 0.5
    z = max(min(z, high), low)
    return (high - z) / (high - low)

def popularity_score(rank: float, min_rank: float, max_rank: float) -> float:
    """
    Map EDHREC rank into [0,1], where lower rank (more popular) → higher score.
    Uses log scaling to compress the long tail.
    """
    if pd.isna(rank):
        return 0.5  # unknown → neutral
    rank = max(min(rank, max_rank), min_rank)
    log_r = math.log(rank)
    log_min = math.log(min_rank)
    log_max = math.log(max_rank)
    return 1.0 - (log_r - log_min) / (log_max - log_min)

def scarcity_score(row: pd.Series) -> float:
    """
    For each feature the card *has*, look at how common that feature is in this role slice.
    Rare effects (low frac) → high contribution; very common effects → low contribution.
    Returns a 0–1 score.
    """
    score = 0.0
    total_weight = 0.0

    for col in FEATURE_COLS:
        if not bool(row.get(col, False)):
            continue  # card doesn't have this feature

        frac_col = f"{col}_frac"
        frac = row.get(frac_col, None)

        if frac is None or pd.isna(frac) or frac <= 0:
            rarity = 1.0  # effectively unique in this slice
        else:
            frac = float(frac)
            # Simple rarity: rare (0.0–0.1) ≈ 0.9–1.0, common (0.4–0.6) ≈ 0.4–0.6
            rarity = 1.0 - max(0.0, min(frac, 1.0))

        score += rarity
        total_weight += 1.0

    if total_weight == 0:
        return 0.0

    return score / total_weight

def normalize_legacy_synergy(raw_score: float, max_score: float = 14.0) -> float:
    """
    Scale your existing commander_synergy_score into [0,1].
    max_score is a rough expected upper bound; tune if you see lots of 20+ values.
    """
    if raw_score <= 0:
        return 0.0
    return max(0.0, min(raw_score / max_score, 1.0))

def commander_synergy_score(profile: dict, card_row: pd.Series) -> float:
    """
    Score how well a single card fits this commander’s game plan.

    profile:
      - "themes": set[str]
      - "curve_pref": "fast" | "normal" | "slow"
    """
    # --- unpack profile ---
    commander_themes: set[str] = profile.get("themes", set()) or set()
    curve_pref = profile.get("curve_pref", "normal")

    # --- normalize fields from the card row ---
    raw_text      = card_row.get("oracle_text", "")
    raw_type_line = card_row.get("type_line", "")
    raw_name      = card_row.get("name", "")
    raw_cmc       = card_row.get("cmc", 0)

    text      = str(raw_text or "").lower()
    type_line = str(raw_type_line or "").lower()
    name      = str(raw_name or "").lower()

    # CMC as a sane number
    try:
        cmc = float(raw_cmc) if not pd.isna(raw_cmc) else 0.0
    except (TypeError, ValueError):
        cmc = 0.0

    # --- 1. Theme overlap ---
    card_themes = detect_card_themes(card_row)
    theme_overlap = len(commander_themes & card_themes)

    score = 0.0
    score += theme_overlap * 3.0  # hard weight on being on-plan

    # --- 2. Role alignment (using your get_card_roles) ---
    roles = get_card_roles(card_row)

    # Core infrastructure
    if "ramp" in roles:
        score += 2.0
    if "draw" in roles:
        score += 2.0
    if "removal" in roles or "interaction" in roles:
        score += 1.5
    if "wipe" in roles:
        score += 1.5

    # Engines / finishers get extra love if on-theme
    if "engine" in roles:
        score += 3.0
    if "finisher" in roles or "wincon" in roles:
        score += 3.0

    # --- 3. Curve preference tweaks ---
    if curve_pref == "fast":
        if cmc <= 2:
            score += 2.0
        elif cmc >= 6:
            score -= 2.0
    elif curve_pref == "slow":
        if cmc >= 5:
            score += 1.5

    # Tiny nudge for cheap interaction in any shell
    if cmc <= 3 and ("removal" in roles or "interaction" in roles):
        score += 0.5

    # Never negative
    if score < 0:
        score = 0.0

    return float(score)

def build_commander_profile(commander_row: pd.Series) -> dict:
    """
    Build a heuristic 'profile' for a commander:
    - themes: set of THEME_KEYWORDS themes
    - preferred_roles: weights for roles (mana_dork, token_engine, ritual, etc.)
    - burst_roles: roles that get extra value when the commander multiplies them
    - engine_roles: roles that look like engines in this shell
    """
    text = (commander_row.get("oracle_text") or "").lower()
    themes = detect_card_themes(commander_row)
    roles = commander_row.get("roles", set()) or set()

    preferred_roles: dict[str, float] = defaultdict(float)
    burst_roles: set[str] = set()
    engine_roles: set[str] = set()

    # --- Baseline: map themes -> preferred roles ---
    for t in themes:
        if t == "spellslinger":
            preferred_roles["spell"]          += 2.0
            preferred_roles["cheap_spell"]    += 2.0
            preferred_roles["ritual"]         += 3.0
            preferred_roles["spell_payoff"]   += 3.0
            preferred_roles["card_draw_engine"] += 1.5
            preferred_roles["treasure_engine"] += 1.0

        if t == "tokens":
            preferred_roles["token_engine"]   += 3.0
            preferred_roles["token_maker_once"] += 1.0
            preferred_roles["token_payoff"]   += 3.0
            preferred_roles["death_payoff"]   += 1.5
            preferred_roles["card_draw_engine"] += 1.0

        if t == "sacrifice":
            preferred_roles["sac_outlet_creature"] += 3.0
            preferred_roles["sac_outlet_permanent"] += 2.0
            preferred_roles["dies_trigger"]   += 3.0
            preferred_roles["death_payoff"]   += 3.0
            preferred_roles["token_engine"]   += 1.0

        if t == "graveyard":
            preferred_roles["self_mill"]          += 2.0
            preferred_roles["yard_recur_creature"] += 2.5
            preferred_roles["yard_recur_any"]     += 2.5
            preferred_roles["escape_piece"]       += 1.5
            preferred_roles["flashback_piece"]    += 1.5
            preferred_roles["unearth_piece"]      += 1.5

        if t == "counters":
            preferred_roles["combat_pump"]    += 1.5
            preferred_roles["protects_creatures"] += 1.0
            preferred_roles["token_engine"]   += 1.0  # often overlaps

        if t == "artifacts":
            preferred_roles["mana_rock"]      += 3.0
            preferred_roles["tutor_artifact"] += 2.0
            preferred_roles["treasure_engine"] += 1.5

        if t == "lifegain":
            preferred_roles["death_payoff"]   += 1.0
            preferred_roles["protects_creatures"] += 1.0

        if t == "lands":
            preferred_roles["land_ramp"]      += 3.0
            preferred_roles["self_mill"]      += 1.0  # lands in yard stuff
            preferred_roles["yard_recur_any"] += 1.0

        if t == "control":
            preferred_roles["counterspell"]   += 3.0
            preferred_roles["board_wipe_creatures"] += 2.0
            preferred_roles["board_wipe_noncreature"] += 2.0
            preferred_roles["spot_removal_any"] += 2.0
            preferred_roles["tax_piece"]      += 2.0
            preferred_roles["tap_freeze"]     += 1.5

        if t == "voltron":
            preferred_roles["protects_commander"] += 3.0
            preferred_roles["protects_creatures"] += 1.5
            preferred_roles["combat_pump"]    += 2.0
            preferred_roles["evasion_granter"] += 2.0
            preferred_roles["aura"] = preferred_roles.get("aura", 0)  # placeholder if you add aura role later

    # --- Pattern-based: identify burst/engine patterns from commander text ---

    # “Whenever you cast an instant or sorcery / noncreature spell” → Azula-style
    if (
        "whenever you cast an instant or sorcery" in text
        or "whenever you cast a noncreature spell" in text
        or "whenever you cast an instant" in text
        or "whenever you cast a sorcery" in text
    ):
        burst_roles.update({"ritual", "cheap_spell", "x_spell"})
        preferred_roles["ritual"]       += 3.0
        preferred_roles["cheap_spell"]  += 2.0
        preferred_roles["x_spell"]      += 2.0
        engine_roles.add("spell_payoff")

    # “Whenever a creature dies / you sacrifice a creature” → aristocrats core
    if (
        "whenever a creature dies" in text
        or "whenever another creature dies" in text
        or "whenever a creature you control dies" in text
        or "whenever another creature you control dies" in text
    ):
        engine_roles.update({"dies_trigger", "death_payoff"})
        preferred_roles["token_engine"]         += 2.0
        preferred_roles["sac_outlet_creature"]  += 2.0

    # “Whenever a creature enters / token enters” → go-wide payoff
    if (
        "whenever a creature enters the battlefield under your control" in text
        or "whenever one or more creatures enter the battlefield under your control" in text
        or "whenever a token" in text
    ):
        engine_roles.update({"token_engine", "token_payoff"})
        preferred_roles["token_engine"]   += 2.0
        preferred_roles["token_payoff"]   += 2.0

    # “Whenever you draw a card” → wheels/draw engines
    if "whenever you draw a card" in text:
        engine_roles.add("card_draw_engine")
        preferred_roles["card_draw_engine"] += 2.5
        preferred_roles["cantrip"]          += 2.0

    # “Whenever you gain life”
    if "whenever you gain life" in text:
        engine_roles.add("lifegain_engine")
        preferred_roles["death_payoff"]     += 1.5
        preferred_roles["protects_creatures"] += 1.0

    # “Whenever you sacrifice” / “sacrifice another creature:” in the commander
    if "whenever you sacrifice" in text:
        preferred_roles["token_engine"]         += 2.0
        preferred_roles["sac_outlet_creature"]  += 2.0

    profile = {
        "name": commander_row["name"],
        "themes": themes,
        "roles": roles,
        "preferred_roles": dict(preferred_roles),
        "burst_roles": burst_roles,
        "engine_roles": engine_roles,
    }
    return profile

def commander_synergy_component(
    commander_profile: dict,
    card_row: pd.Series,
    commander_plan: dict | None = None,
    card_obj: Card | None = None,
) -> float:
    """
    Combine:
      - theme overlap
      - preferred_roles from commander_profile
      - existing commander_synergy_score
    into a single 0–1 synergy figure.
    """
    commander_themes: set[str] = commander_profile.get("themes", set()) or set()
    preferred_roles: dict[str, float] = commander_profile.get("preferred_roles", {}) or {}

    # Card themes / role (single role if coming from card_role_cmc_norm)
    card_themes = detect_card_themes(card_row)
    card_role = str(card_row.get("role", "") or "")
    card_roles_set = {card_role} if card_role else set()

    # Theme overlap: 0–1
    theme_overlap = len(commander_themes & card_themes)
    theme_score = min(theme_overlap / 3.0, 1.0)  # cap at 3+ themes matched

    # Role preference: 0–1 based on preferred_roles weight
    role_pref_raw = 0.0
    for r in card_roles_set:
        role_pref_raw += preferred_roles.get(r, 0.0)

    # Rough cap; if you routinely see bigger numbers in practice, bump this
    role_pref_score = 0.0
    if role_pref_raw > 0:
        role_pref_score = min(role_pref_raw / 6.0, 1.0)

    # Legacy synergy heuristic, normalized
    legacy_raw = commander_synergy_score(commander_profile, card_row)
    legacy_norm = normalize_legacy_synergy(legacy_raw)

    # Blend: themes and roles matter more than legacy text heuristics
    # You can tune these if you want legacy to matter more/less.
    w_theme = 0.35
    w_role  = 0.35
    w_legacy = 0.30
    total = w_theme + w_role + w_legacy

    synergy = (
        w_theme  * theme_score
        + w_role * role_pref_score
        + w_legacy * legacy_norm
    ) / total

    return synergy

def compute_curve_metrics(pool: pd.DataFrame) -> dict:
    if "cmc" not in pool.columns or pool.empty:
        return {"avg_cmc": None, "low_frac": 0.0, "high_frac": 0.0}

    cmc = pool["cmc"].fillna(0)
    total = len(cmc)
    if total == 0:
        return {"avg_cmc": None, "low_frac": 0.0, "high_frac": 0.0}

    # NEW: treat 0–2 as "low", 6+ as "high"
    low = (cmc <= 2).sum()
    high = (cmc >= 6).sum()

    return {
        "avg_cmc": cmc.mean(),
        "low_frac": low / total,
        "high_frac": high / total,
    }

def wincon_score(row: pd.Series, themes: set[str]) -> int:
    """
    Heuristic score for 'how much does this card look like it ends the game',
    weighted by how well it fits the commander's themes.
    Higher = more wincon-y AND on-plan.
    """
    text = (str(row.get("oracle_text", "")) + " " +
            str(row.get("type_line", ""))).lower()
    type_line = str(row.get("type_line", "")).lower()
    cmc = row.get("cmc", 0) or 0

    score = 0

    # --- 1. Hard "this wins/ends the game" text ---
    if "you win the game" in text or "an opponent loses the game" in text:
        score += 20

    # Big table hits
    if "each opponent loses" in text or "each opponent takes" in text:
        score += 6
    if "deals damage to each opponent" in text:
        score += 6

    # Overrun-style alpha strikes
    if "creatures you control get" in text and "until end of turn" in text:
        score += 4
        if "trample" in text or "double strike" in text:
            score += 2

    # Extra combats / doubling
    if "extra combat phase" in text or "additional combat phase" in text:
        score += 8
    if "double the number of" in text or "double target" in text:
        score += 4

    # --- 2. Generic scaling text that can be a finisher ---
    if "for each" in text or "where x is the number of" in text:
        score += 2

    # --- 3. Theme alignment bonuses ---

    # generic "on-theme" check using your existing matcher
    on_theme_generic = card_matches_themes(row, themes)
    if on_theme_generic:
        score += 2

    # Spellslinger: we care about spells finishing the game, not random big dudes
    if "spellslinger" in themes:
        if ("instant or sorcery" in text or
            "noncreature spell" in text or
            "instant" in type_line or
            "sorcery" in type_line):
            score += 4
        if "for each instant" in text or "for each sorcery" in text:
            score += 4

    # Tokens: wide alpha strikes
    if "tokens" in themes:
        if "for each creature you control" in text:
            score += 4
        if "creatures you control get" in text and ("trample" in text or "+x/+x" in text):
            score += 4

    # Counters: scaling off +1/+1 counters
    if "counters" in themes:
        if "+1/+1 counter" in text and ("each" in text or "for each" in text):
            score += 4
        if "double the number of counters" in text:
            score += 5

    # Artifacts: big payoffs for artifact count
    if "artifacts" in themes:
        if "for each artifact" in text or "artifact you control" in text:
            score += 4

    # Lifegain: drain based on life gained
    if "lifegain" in themes:
        if "for each life you gained" in text or "where x is the amount of life you gained" in text:
            score += 4

    # Graveyard: finishers that scale off grave size
    if "graveyard" in themes:
        if "cards in your graveyard" in text or "creature cards in your graveyard" in text:
            score += 4

    # --- 4. Downweight off-plan big stompers ---

    is_big_creature = ("creature" in type_line and cmc >= 6)
    if is_big_creature:
        big_creature_keywords = ["trample", "flying", "menace", "haste"]
        if any(kw in text for kw in big_creature_keywords):
            # generic beater: only good if your themes actually want big bodies
            if not any(t in themes for t in ["tokens", "counters", "lands"]):
                score -= 3  # off-plan stompy in a spellslinger/control shell

    # Clamp at minimum 0 (we don't care about negative scores)
    if score < 0:
        score = 0

    return score

def analyze_commander_plan(commander_row: pd.Series) -> dict:
    """
    Look at the commander and guess:
      - what its core gameplan is (plan_type)
      - what specific loop hooks it cares about (loop_tags)
      - whether it's more of a finisher or value engine

    Returns:
      {
        "plan_type": str,
        "loop_tags": set[str],
        "is_primary_finisher": bool,
        "notes": str,
      }
    """
    text = (str(commander_row.get("oracle_text", ""))).lower()
    type_line = str(commander_row.get("type_line", "")).lower()
    cmc = commander_row.get("cmc", 0) or 0
    themes = detect_card_themes(commander_row)

    loop_tags: set[str] = set()
    notes: list[str] = []

    # --- 1) Identify what resource / trigger the commander is built around ---

    # Spells / noncreature casting
    if "whenever you cast an instant or sorcery" in text \
       or "whenever you cast a noncreature spell" in text \
       or "instant or sorcery spell" in text:
        loop_tags.add("spells_per_turn")
        notes.append("Rewards chaining instants/sorceries or noncreature spells.")

    # Tokens / going wide
    if "create a token" in text or "create one or more tokens" in text \
       or "for each token you control" in text:
        loop_tags.add("tokens_engine")
        notes.append("Turns token production into value or damage.")

    # Sacrifice / death
    if "sacrifice another creature" in text \
       or "sacrifice a creature" in text \
       or "whenever a creature dies" in text \
       or "whenever another creature you control dies" in text:
        loop_tags.add("sacrifice_loop")
        notes.append("Leverages sacrifice / death triggers for value.")

    # Lands / landfall / extra land drops
    if "landfall" in text \
       or "whenever a land enters the battlefield under your control" in text \
       or "you may play an additional land" in text \
       or "play an additional land on each of your turns" in text:
        loop_tags.add("lands_engine")
        notes.append("Scales off land drops / landfall.")

    # Lifegain
    if "whenever you gain life" in text \
       or "for each 1 life you gained" in text \
       or ("you gain life" in text and "whenever" in text):
        loop_tags.add("lifegain_engine")
        notes.append("Turns repeated lifegain into cards/board presence/damage.")

    # Counters
    if "+1/+1 counter" in text \
       or "for each counter on" in text \
       or "double the number of counters" in text:
        loop_tags.add("counters_engine")
        notes.append("Wants repeated counter placement / doubling.")

    # ETB / blink
    if ("enters the battlefield" in text and "whenever" in text) or \
       ("enters the battlefield under your control" in text):
        loop_tags.add("etb_loop")
        notes.append("Rewards ETB loops / blink / reanimation.")

    # Attack triggers / combat
    if "whenever {this} attacks" in text.replace(commander_row["name"].lower(), "{this}") \
       or "whenever a creature you control attacks" in text:
        loop_tags.add("attack_loop")
        notes.append("Wants repeated attacks / extra combats / go-wide swings.")

    # Mill / graveyard recursion
    if "mill" in text \
       or "put the top card of your library into your graveyard" in text \
       or "you may cast target card from your graveyard" in text \
       or "return target creature card from your graveyard" in text:
        loop_tags.add("graveyard_loop")
        notes.append("Graveyard recursion / self-mill loops.")

    # Blink/recast from exile or hand
    if "exile it, then return it" in text or "return it to the battlefield" in text:
        loop_tags.add("blink_bounce_loop")
        notes.append("Supports flicker / bounce loops on itself or others.")

    # Treasure / mana engines
    if "create a treasure token" in text or "for each treasure you control" in text:
        loop_tags.add("treasure_engine")
        notes.append("Uses Treasures as a primary value/mana engine.")

    # --- 2) Is the commander itself more of a finisher or value engine? ---
    # reuse your wincon heuristics on *the commander*
    commander_wincon_score = wincon_score(commander_row, themes)

    is_primary_finisher = False
    plan_type = "unknown"

    # explicit win the game / each opponent loses, etc.
    if "you win the game" in text or "an opponent loses the game" in text:
        is_primary_finisher = True
        plan_type = "primary_finisher"
        notes.append("Has explicit game-ending text on the commander.")

    # big scaling drain / damage / alpha-strike language
    elif "each opponent loses" in text or "deals damage to each opponent" in text:
        is_primary_finisher = True
        plan_type = "primary_finisher"
        notes.append("Can directly close games with commander-triggered damage/drain.")

    elif commander_wincon_score >= 8:
        # Heuristic: your wincon_score already looked at scaling, extra combats, etc.
        is_primary_finisher = True
        plan_type = "primary_finisher"
        notes.append("Commander text+stats look like a main finisher.")

    # If not a finisher, see if it's clearly an engine
    if not is_primary_finisher:
        if loop_tags:
            plan_type = "value_engine"
            notes.append("Primarily a value engine that wants to repeat its hook.")
        else:
            # fallback based on stats: big body with combat keywords = beater
            is_creature = "creature" in type_line
            if is_creature and cmc >= 5 and any(
                kw in text for kw in ["trample", "flying", "double strike", "indestructible"]
            ):
                plan_type = "stompy_beater"
                notes.append("More of a large combat threat than a pure engine.")
            else:
                plan_type = "toolbox_or_control"
                notes.append("Looks more like a toolbox/control value piece.")

    return {
        "plan_type": plan_type,
        "loop_tags": loop_tags,
        "is_primary_finisher": is_primary_finisher,
        "notes": " ".join(notes),
    }

def rate_commander_bracket(df_all: pd.DataFrame, deck_df: pd.DataFrame) -> tuple[int, dict]:
    """
    Approximate WotC's 1–5 Commander Brackets for a given deck.

    Returns (bracket, details_dict) where bracket is 1–5 and details holds
    the stats we used to decide.
    """
    # Join deck list to full card data to get oracle_text, type_line, etc.
    names = deck_df["name"].unique().tolist()
    cards = df_all[df_all["name"].isin(names)].copy()

    # Basic counts
    num_game_changers = cards.apply(is_game_changer, axis=1).sum()
    num_extra_turns = cards.apply(is_extra_turn, axis=1).sum()
    num_nonland_tutors = cards.apply(is_nonland_tutor, axis=1).sum()
    has_mass_ld = cards.apply(is_mass_land_denial, axis=1).any()
    has_combo_flag = cards["name"].isin(COMBO_FLAG_CARDS).any()

    # From your role tagging
    roles = deck_df.copy()
    roles_str = roles["role"].fillna("")

    num_lands = roles[roles["role"] == "land"]["count"].sum()
    num_ramp = roles_str.str.contains("ramp").sum()
    num_draw = roles_str.str.contains("draw").sum()
    num_wipes = roles_str.str.contains("wipe").sum()
    num_removal = roles_str.str.contains("removal").sum()
    num_wincons = roles_str.str.contains("wincon").sum()

    total_cards = int(deck_df["count"].sum())

    details = {
        "total_cards": total_cards,
        "num_lands": int(num_lands),
        "num_ramp": int(num_ramp),
        "num_draw": int(num_draw),
        "num_wipes": int(num_wipes),
        "num_removal": int(num_removal),
        "num_wincons": int(num_wincons),
        "num_game_changers": int(num_game_changers),
        "num_extra_turns": int(num_extra_turns),
        "num_nonland_tutors": int(num_nonland_tutors),
        "has_mass_land_denial": bool(has_mass_ld),
        "has_combo_flag": bool(has_combo_flag),
    }

        # --- Structural health score (0–10-ish) ---
    structure_score = 0

    # Lands: 34–40 is gold; outside 32–42 is suspicious
    if 34 <= num_lands <= 40:
        structure_score += 3
    elif 32 <= num_lands <= 42:
        structure_score += 1
    else:
        structure_score -= 2

    # Ramp: 8–14 is healthy
    if 8 <= num_ramp <= 14:
        structure_score += 3
    elif 6 <= num_ramp <= 16:
        structure_score += 1
    else:
        structure_score -= 2

    # Draw: 8–14 is healthy
    if 8 <= num_draw <= 14:
        structure_score += 3
    elif 6 <= num_draw <= 16:
        structure_score += 1
    else:
        structure_score -= 2

    # Wipes & removal shouldn't be wildly off
    if num_wipes == 0 and num_removal <= 3:
        # basically no interaction
        structure_score -= 1

    details["structure_score"] = int(structure_score)

    # --- Heuristic bracket logic, aligned to WotC’s text ---

    # 5: cEDH-ish – lots of game changers / combo flags / tutors
    if (
        details["num_game_changers"] >= 6
        or (details["has_combo_flag"] and details["num_nonland_tutors"] >= 5)
    ):
        raw_bracket = 5

    # 4: Optimized – no restrictions, fast mana / combos / many game changers
    elif (
        details["num_game_changers"] >= 3
        or details["has_mass_land_denial"]
        or details["num_extra_turns"] > 2
        or details["num_nonland_tutors"] >= 4
    ):
        raw_bracket = 4

    # 3: Upgraded – stronger than precon, maybe a few game changers, decent structure
    elif (
        1 <= details["num_game_changers"] <= 2
        or (
            details["num_ramp"] >= 8
            and details["num_draw"] >= 8
            and details["num_wincons"] >= 3
        )
    ):
        raw_bracket = 3

    # 2: Core – precon-ish, no game changers, few tutors, no land D
    elif (
        details["num_game_changers"] == 0
        and not details["has_mass_land_denial"]
        and details["num_extra_turns"] <= 1
        and details["num_nonland_tutors"] <= 2
    ):
        raw_bracket = 2

    else:
        # Very underpowered / janky / low-ramp decks would fall here.
        raw_bracket = 1

    bracket = raw_bracket

    if structure_score <= 1:
        bracket = min(bracket, 3)   # can’t really be 4–5 if built like trash
    if structure_score <= -1:
        bracket = min(bracket, 2)
    if structure_score <= -3:
        bracket = 1

    details["raw_bracket"] = raw_bracket
    details["bracket"] = bracket

    return bracket, details

def describe_deck_play_pattern(
    df_all: pd.DataFrame,
    deck_df: pd.DataFrame,
    commander_row: pd.Series,
    bracket: int,
    bracket_details: dict,
) -> str:
    """
    Produce a 'how it plays' summary that actually names key cards and synergies,
    AND now lists value engines + what they synergize with.
    """

    name = commander_row["name"]
    colors = commander_row["color_identity"]
    themes = commander_row.get("themes", set()) or set()

    # New: commander plan / loop tags (spells_per_turn, sacrifice_loop, tokens_engine, etc.)
    plan_info = analyze_commander_plan(commander_row)
    loop_tags = plan_info.get("loop_tags", set()) or set()

    # Join deck list to full DF so we can see oracle_text / type_line / cmc / game_changer
    cards = df_all[df_all["name"].isin(deck_df["name"].unique())].copy()
    cards = cards.merge(
        deck_df[["name", "count", "role"]],
        on="name",
        how="left"
    )
    cards["count"] = cards["count"].fillna(1)
    cards["role"] = cards["role"].fillna("")

    # Nonland stats for curve + types
    nonland_mask = ~cards["type_line"].str.contains("Land", na=False)
    nonlands = cards[nonland_mask].copy()

    if not nonlands.empty and "cmc" in nonlands.columns:
        cmc_series = nonlands["cmc"].fillna(0)
        avg_cmc = float(cmc_series.mean())
        low_frac = float((cmc_series <= 3).mean())
        high_frac = float((cmc_series >= 6).mean())
    else:
        avg_cmc = 3.0
        low_frac = 0.0
        high_frac = 0.0

    # Creature vs spell split
    type_lines = nonlands["type_line"].fillna("").str.lower()

    # fraction of nonlands that are creatures
    creature_frac = float(type_lines.str.contains("creature", na=False).mean())

    # fraction of nonlands that are instants or sorceries
    instant_sorcery_mask = (
        type_lines.str.contains("instant", na=False)
        | type_lines.str.contains("sorcery", na=False)
    )
    instant_sorcery_frac = float(instant_sorcery_mask.mean())
    
    # Role counts from bracket_details
    num_ramp = bracket_details.get("num_ramp", 0)
    num_draw = bracket_details.get("num_draw", 0)
    num_wipes = bracket_details.get("num_wipes", 0)
    num_removal = bracket_details.get("num_removal", 0)
    num_wincons = bracket_details.get("num_wincons", 0)

    # Simple speed label
    deck_speed = "midrange"
    aggro_themes = {"tokens", "spellslinger", "counters"}
    if avg_cmc <= 3.0 and (themes & aggro_themes):
        deck_speed = "fast"
    elif avg_cmc >= 3.8 or num_wipes >= 4:
        deck_speed = "slow"

    # Archetype guess based on themes + card-type ratios
    archetype = "midrange value"
    if "spellslinger" in themes or instant_sorcery_frac > 0.35:
        archetype = "spellslinger/control"
    elif "tokens" in themes and creature_frac > 0.4:
        archetype = "go-wide aggro/midrange"
    elif "graveyard" in themes:
        archetype = "graveyard value/combo"
    elif "lifegain" in themes:
        archetype = "lifegain midrange"
    elif "artifacts" in themes:
        archetype = "artifact value/combo"

    # --- Identify key synergy engines and finishers (using YOUR list + wincon_score) ---

    # 1) Which cards are actually on-theme?
    if themes:
        cards["is_on_theme"] = cards.apply(
            lambda r: card_matches_themes(r, themes),
            axis=1
        )
    else:
        cards["is_on_theme"] = False

    # 2) Compute wincon_score for the cards in this deck
    cards["wincon_score"] = cards.apply(
        lambda r: wincon_score(r, themes),
        axis=1
    )

    # 3) Engines: on-theme nonlands with "whenever"/"at the beginning"
    def is_engine(row: pd.Series) -> bool:
        if not row["is_on_theme"]:
            return False
        text = str(row.get("oracle_text", "")).lower()
        if "whenever" not in text and "at the beginning of" not in text:
            return False
        if is_board_wipe(row):
            return False
        return True

    engine_mask = nonland_mask & cards.apply(is_engine, axis=1)
    engines = cards[engine_mask].copy()
    if "cmc" in engines.columns:
        engines = engines.sort_values(["cmc", "name"])
    engine_names = engines["name"].head(3).tolist()

    # 4) Finishers: highest wincon_score cards in the deck
    payoffs = cards[cards["wincon_score"] > 0].copy()
    if not payoffs.empty:
        payoffs = payoffs.sort_values(
            by=["wincon_score", "cmc"],
            ascending=[False, True]
        )
    payoff_names = payoffs["name"].head(3).tolist()

    # --- NEW: Value engines + what they actually synergize with ---

    value_engine_lines: list[str] = []
    interesting_roles = {
        "token_engine", "token_payoff", "card_draw_engine",
        "treasure_engine", "spell_payoff", "ritual",
        "sac_outlet_creature", "sac_outlet_permanent",
        "dies_trigger", "death_payoff",
        "land_ramp", "yard_recur_creature", "yard_recur_any",
    }

    for _, eng in engines.head(5).iterrows():
        eng_name = eng["name"]
        eng_roles = set((eng.get("role") or "").split(","))
        eng_themes = detect_card_themes(eng)
        on_plan_themes = sorted(eng_themes & themes)

        synergy_bits: list[str] = []

        # Hook into commander loop tags
        if "spells_per_turn" in loop_tags and (
            "spell_payoff" in eng_roles
            or "cheap_spell" in eng_roles
            or "ritual" in eng_roles
        ):
            synergy_bits.append("your 'cast spells' commander trigger")

        if "tokens_engine" in loop_tags and (
            "token_engine" in eng_roles or "token_payoff" in eng_roles
        ):
            synergy_bits.append("your token / go-wide triggers")

        if "sacrifice_loop" in loop_tags and (
            "sac_outlet_creature" in eng_roles
            or "dies_trigger" in eng_roles
            or "death_payoff" in eng_roles
        ):
            synergy_bits.append("your sacrifice / death loops")

        if "graveyard_loop" in loop_tags and (
            "self_mill" in eng_roles
            or "yard_recur_creature" in eng_roles
            or "yard_recur_any" in eng_roles
        ):
            synergy_bits.append("your graveyard recursion plan")

        if "lands_engine" in loop_tags and (
            "land_ramp" in eng_roles or "land" in eng_roles
        ):
            synergy_bits.append("your landfall / extra lands plan")

        # Fallback: just say which themes it shares with the commander
        if not synergy_bits and on_plan_themes:
            synergy_bits.append("on-plan themes: " + ", ".join(on_plan_themes))

        if not synergy_bits:
            continue  # ignore engines that don't obviously hook into anything

        display_roles = sorted(eng_roles & interesting_roles)
        if display_roles:
            role_str = f" ({', '.join(display_roles)})"
        else:
            role_str = ""

        value_engine_lines.append(
            f"- {eng_name}{role_str} → hooks into " + "; ".join(synergy_bits)
        )

    # --- Build the actual writeup ---

    lines = []

    lines.append(f"{name} — {archetype}, {deck_speed} deck (Bracket {bracket})")
    lines.append(f"Colors: {colors}")
    if themes:
        lines.append(f"Themes: {', '.join(sorted(themes))}")

    lines.append(
        f"\nCurve: avg CMC ~{avg_cmc:.2f} "
        f"(≤3 mana: {low_frac:.0%} of nonlands, 6+ drops: {high_frac:.0%})"
    )
    lines.append(
        f"Roles: ramp {num_ramp}, draw {num_draw}, "
        f"removal {num_removal}, wipes {num_wipes}, wincons {num_wincons}"
    )

    if engine_names:
        lines.append(f"\nKey engines: " + ", ".join(engine_names))
    if payoff_names:
        lines.append("Primary finishers: " + ", ".join(payoff_names))

    if value_engine_lines:
        lines.append("\nValue engines & what they plug into:")
        lines.extend(value_engine_lines)

    # Early / mid / late game narrative, still referencing specific cards when possible
    early = []
    mid = []
    late = []

    # Early game
    if num_ramp >= 8:
        early.append("develop mana with your ramp pieces")
    if num_draw >= 6:
        early.append("use cheap card draw to keep land drops flowing")
    if "tokens" in themes and engine_names:
        early.append(f"start building a board with engines like {engine_names[0]}")

    # Mid game
    if "spellslinger" in themes and engine_names:
        mid.append(f"chain instants/sorceries around payoffs like {engine_names[0]}")
    if "tokens" in themes and payoff_names:
        mid.append(f"go wide and set up a big swing with {payoff_names[0]}")
    if "graveyard" in themes and engine_names:
        mid.append(f"leverage the graveyard using value engines like {engine_names[0]}")
    if num_removal >= 6:
        mid.append("use spot removal to clear key blockers or hate pieces")

    # Late game
    if payoff_names:
        if len(payoff_names) > 1:
            late.append(
                "close the game with your finishers like "
                + ", ".join(payoff_names)
            )
        else:
            late.append(f"close the game with your finisher {payoff_names[0]}")
    if "counters" in themes:
        late.append("turn stacked +1/+1 counters into a lethal swing")
    if bracket >= 4:
        late.append("punish slower tables with higher-power sequences")

    if early:
        lines.append("\nEarly game: " + "; ".join(early) + ".")
    if mid:
        lines.append("Mid game: " + "; ".join(mid) + ".")
    if late:
        lines.append("Late game: " + "; ".join(late) + ".")

    return "\n".join(lines)

def advanced_card_score_for_commander(
    card_role_row: pd.Series,
    commander_profile: dict,
    commander_plan: dict | None = None,
    edh_min_rank: int = 1,
    edh_max_rank: int = 300_000,
    w_eff: float = 0.30,
    w_pop: float = 0.15,
    w_scarcity: float = 0.20,
    w_synergy: float = 0.35,
) -> float:
    # 1) Efficiency, popularity, scarcity as before
    eff = efficiency_score(card_role_row.get("cmc_z_vs_role", float("nan")))
    pop = popularity_score(card_role_row.get("edhrec_rank", float("nan")),
                           min_rank=edh_min_rank,
                           max_rank=edh_max_rank)
    scarce = scarcity_score(card_role_row)

    # 2) Build Card object from the row for engine analysis
    try:
        card_obj = card_from_row(card_role_row)
    except Exception:
        card_obj = None

    # 3) Synergy, now including engine score via Card
    syn = commander_synergy_component(
        commander_profile,
        card_role_row,
        commander_plan=commander_plan,
        card_obj=card_obj,
    )

    # 4) Weighted blend same as before
    w_sum = w_eff + w_pop + w_scarcity + w_synergy
    w_eff /= w_sum; w_pop /= w_sum; w_scarcity /= w_sum; w_synergy /= w_sum

    score = (
        w_eff * eff +
        w_pop * pop +
        w_scarcity * scarce +
        w_synergy * syn
    )

    return float(max(0.0, min(score, 1.0)))