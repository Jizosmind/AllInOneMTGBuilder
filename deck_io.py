#==================================================
# Convert .txt or .csv of cards into a usable list.
#==================================================

# Modules
import requests
import pandas as pd
import time

#Dictionary
THEME_KEYWORDS = {
    "tokens": [
        # Generic token text
        "create a token",
        "create a 1/1",
        "create a 2/2",
        "create a 3/3",
        "token that's a copy",
        "treasure token",
        "clue token",
        "food token",
        "blood token",
        "incubator token",
        "map token",
        # Token-centric mechanics / ability words
        "populate",
        "myriad",
        "afterlife",
        "encore",
        "training",
        "rally",
        "alliance",
    ],
    "sacrifice": [
        "sacrifice a creature",
        "sacrifice another creature",
        "sacrifice a permanent",
        "sacrifice an artifact",
        "sacrifice a land",
        "whenever a creature dies",
        "dies,",
        "exploit",  # sac as cost
    ],
    "spellslinger": [
        # Classic spellslinger text
        "instant or sorcery spell",
        "noncreature spell",
        "whenever you cast an instant",
        "whenever you cast a sorcery",
        "whenever you cast a noncreature spell",
        "copy that spell",
        "copy target instant or sorcery",
        "storm",
        "prowess",
        "magecraft",
        # Cost / cast mechanics that usually indicate spell-heavy shells
        "flashback",
        "jump-start",
        "rebound",
        "convoke",
        "delve",
        "improvise",
        "buyback"
    ],
    "counters": [
        "+1/+1 counter",
        "proliferate",
        "put a +1/+1 counter",
        "modified creatures",
        "energy counter",
        "experience counter",
        "shield counter",
        "oil counter",
        # Counter-related mechanics / ability words
        "adapt",
        "bolster",
        "support",
        "outlast",
        "mentor",
        "explore",
        "level up",
        "saga",  # technically an enchantment type, but strongly counter-based
    ],
    "artifacts": [
        "artifact you control",
        "artifact spell",
        "artifacts you control",
        "equipment",
        "vehicle",
        "treasure token",
        "clue token",
        "food token",
        # Artifact-specific mechanics
        "affinity for artifacts",
        "metalcraft",
        "improvise",
        "modular",
        "fabricate",
        "equip",
        "reconfigure",
        "crew",
        "living weapon",
    ],
    "lifegain": [
        "you gain life",
        "whenever you gain life",
        "gain life equal to",
        "lifelink",
        "extort",
    ],
    "lands": [
        "landfall",
        "whenever a land enters the battlefield",
        "whenever a land enters the battlefield under your control",
        "play an additional land",
        "you may play an additional land",
        "search your library for a land card",
        "search your library for a basic land card",
        # Land / domain mechanics
        "domain",
        "landcycling",
        "basic landcycling",
        "awaken",
    ],
    "graveyard": [
        "from your graveyard",
        "from their graveyard",
        "from each graveyard",
        "return target creature card from your graveyard",
        "return target card from your graveyard",
        "escape",
        "flashback",
        "jump-start",
        "unearth",
        "dredge",
        "persist",
        "undying",
        "embalm",
        "eternalize",
        "disturb",
        "delirium",
        "threshold",
    ],
}

BASIC_LAND_NAMES = {
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    "Wastes",
}

MASS_LAND_DENIAL_NAMES = {
    "Armageddon",
    "Ravages of War",
    "Ruination",
    "Sunder",
    "Winter Orb",
    "Static Orb",
    "Blood Moon",
    "Magus of the Moon",
}

COMBO_FLAG_CARDS = {
    "Ad Nauseam",
    "Underworld Breach",
    "Thassa's Oracle",
}

#Functions
def get_commander_candidates(df):
    # Legendary creatures are natural commanders
    is_legendary_creature = df["type_line"].str.contains("Legendary Creature", na=False)

    # Some non-legendaries explicitly say they can be your commander
    says_can_be_commander = df["oracle_text"].str.contains(
        "can be your commander",
        case=False,
        na=False
    )

    # Filter to only eligible commanders
    candidates = df[is_legendary_creature | says_can_be_commander].copy()

    # Treat missing EDHREC rank as "very bad" so they sort to the bottom
    candidates["edhrec_rank_filled"] = candidates["edhrec_rank"].fillna(999999)

    # Sort strongest → weakest (lower rank = better)
    candidates = candidates.sort_values("edhrec_rank_filled", ascending=True)

    # Remove duplicate commanders by name, keeping the best-ranked printing
    candidates = candidates.drop_duplicates(subset="name", keep="first")

    return candidates

def get_legal_pool(df: pd.DataFrame, commander_row: pd.Series) -> pd.DataFrame:
    """
    Given the full card DataFrame and a single commander row,
    return all cards whose color_identity is legal for that commander.

    Commander color identity defines the allowed colors; card color_identity
    must be a subset of that. Colorless ([]) is always legal.
    """
    commander_colors = set(commander_row["color_identity"] or [])

    def is_color_legal(card_colors):
        card_set = set(card_colors or [])
        return card_set.issubset(commander_colors)

    # Apply color-identity legality to all cards
    mask = df["color_identity"].apply(is_color_legal)
    pool = df[mask].copy()

    return pool

def get_commander_themes(commander_row: pd.Series):
    """
    Inspect a commander's oracle_text and type_line, and return a set of
    high-level themes it appears to care about (tokens, sacrifice, etc.).
    """
    text = (str(commander_row.get("oracle_text", "")) + " " +
            str(commander_row.get("type_line", ""))).lower()

    active = set()

    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                active.add(theme)
                break  # don't double-count this theme

    return active

def card_matches_themes(card_row: pd.Series, themes: set[str]) -> bool:
    """
    Return True if this card matches at least one of the given themes,
    based on its oracle_text and type_line.
    """
    if not themes:
        return False

    text = (str(card_row.get("oracle_text", "")) + " " +
            str(card_row.get("type_line", ""))).lower()

    for theme in themes:
        keywords = THEME_KEYWORDS.get(theme, [])
        for kw in keywords:
            if kw in text:
                return True

    return False

def compute_curve_metrics(pool: pd.DataFrame) -> dict:
    """
    Given a DataFrame of cards (typically the synergy pool for a commander),
    compute some basic mana curve metrics.

    We care about:
    - avg_cmc: average converted mana cost
    - low_frac: fraction of cards with cmc <= 3
    - high_frac: fraction of cards with cmc >= 6
    """
    if "cmc" not in pool.columns or pool.empty:
        return {"avg_cmc": None, "low_frac": 0.0, "high_frac": 0.0}

    cmc = pool["cmc"].fillna(0)
    total = len(cmc)
    if total == 0:
        return {"avg_cmc": None, "low_frac": 0.0, "high_frac": 0.0}

    low = (cmc <= 3).sum()
    high = (cmc >= 6).sum()

    return {
        "avg_cmc": cmc.mean(),
        "low_frac": low / total,
        "high_frac": high / total,
    }

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

def build_deck_for_commander(df: pd.DataFrame, commander_row: pd.Series) -> pd.DataFrame:
    """
    Build a 99-card list (excluding the commander itself) using:
    - legal pool (color identity)
    - commander themes
    - crude ramp/draw/removal/wipe classification
    - infinite basic lands to fill the mana base

    Returns a DataFrame with columns:
    name, type_line, role, count
    """
    commander_name = commander_row["name"]
    commander_colors = list(commander_row["color_identity"] or [])
    themes = commander_row.get("themes", set()) or set()

    # 1) Get legal pool for this commander
    pool = get_legal_pool(df, commander_row)

    # 2) Split lands / nonlands
    lands = pool[pool.apply(is_land, axis=1)].copy()
    nonlands = pool[~pool.apply(is_land, axis=1)].copy()

    # 3) Themed synergy pool (nonlands only)
    if themes:
        synergy_mask = nonlands.apply(
            lambda r: card_matches_themes(r, themes),
            axis=1
        )
        synergy_pool = nonlands[synergy_mask].copy()
    else:
        synergy_pool = nonlands.iloc[0:0].copy()
    
    if synergy_pool.empty or len(synergy_pool) < 15:
        print(
            f"[WARN] Very small synergy pool for {commander_name} "
            f"({len(synergy_pool)} cards). Expect more generic goodstuff."
        )

    # Simple deck speed heuristic
    deck_speed = "normal"
    if not synergy_pool.empty and "cmc" in synergy_pool.columns:
        avg_cmc = synergy_pool["cmc"].fillna(0).mean()
    else:
        avg_cmc = 3.0  # fallback

    aggro_themes = {"tokens", "spellslinger", "counters"}
    if avg_cmc <= 3.0 and (themes & aggro_themes):
        deck_speed = "fast"
    elif avg_cmc >= 3.8:
        deck_speed = "slow"

    color_count = len(commander_colors)

    # --- Dynamic LAND_BASE ---
    # Start from a speed-based baseline
    if deck_speed == "fast":
        base = 34
    elif deck_speed == "normal":
        base = 36
    else:  # slow / controlish
        base = 37

    # Adjust for curve
    if avg_cmc >= 3.8:
        base += 1
    elif avg_cmc <= 2.8:
        base -= 1

    # Adjust for color complexity
    if color_count >= 3:
        base += 1
    elif color_count == 1:
        base -= 1

    # Clamp to a sane range
    LAND_BASE = max(32, min(39, base))

    # Remove the commander itself if somehow present
    synergy_pool = synergy_pool[synergy_pool["name"] != commander_name]
    nonlands = nonlands[nonlands["name"] != commander_name]

    # Tag wincondition scores on the synergy pool
    synergy_pool = synergy_pool.copy()
    synergy_pool["wincon_score"] = synergy_pool.apply(
        lambda r: wincon_score(r, themes),
        axis=1
    )
    wincon_candidates = synergy_pool[synergy_pool["wincon_score"] > 0].copy()

    # 4) Classify roles for nonlands
    nonlands = nonlands.copy()
    nonlands["is_ramp"] = nonlands.apply(is_ramp, axis=1)
    nonlands["is_draw"] = nonlands.apply(is_card_draw, axis=1)
    nonlands["is_wipe"] = nonlands.apply(is_board_wipe, axis=1)
    nonlands["is_removal"] = nonlands.apply(is_removal, axis=1)

    synergy_pool = synergy_pool.merge(
        nonlands[["name", "is_ramp", "is_draw", "is_wipe", "is_removal"]],
        on="name",
        how="left"
    )

    # 5) Targets for deck composition
    RAMP_TARGET = 10
    DRAW_TARGET = 10
    REMOVAL_TARGET = 8
    WIPE_TARGET = 3
    WINCON_TARGET = 4

    # 6) Pick ramp / draw / removal / wipes, preferring on-theme and low cmc
    def pick_category(df_src, flag_col, target):
        if target <= 0:
            return []

        candidates = df_src[df_src[flag_col]].copy()
        if candidates.empty:
            return []

        # Compute per-card quality once
        candidates["quality"] = candidates.apply(
            lambda r: card_quality(r, themes),
            axis=1
        )

        # Prefer higher quality; break ties by lower CMC so the curve stays reasonable
        if "cmc" in candidates.columns:
            candidates = candidates.sort_values(
                by=["quality", "cmc"],
                ascending=[False, True]
            )
        else:
            candidates = candidates.sort_values(
                by=["quality"],
                ascending=[False]
            )

        picked = []
        seen_names = set()
        for _, row in candidates.iterrows():
            if len(picked) >= target:
                break
            name = row["name"]
            if name in seen_names:
                continue
            seen_names.add(name)
            picked.append(name)
        return picked

    # 7) Build initial nonland set with roles
    chosen = {}

    def add_card(name, role):
        if name not in chosen:
            chosen[name] = set()
        chosen[name].add(role)

    wincon_names = []
    if not wincon_candidates.empty and WINCON_TARGET > 0:
        # Prefer on-theme, then higher wincon_score, then lower cmc
        wincon_candidates = wincon_candidates.copy()
        wincon_candidates["on_theme"] = True  # synergy_pool is already on-theme by definition

        sort_cols = ["wincon_score"]
        asc = [False]

        if "cmc" in wincon_candidates.columns:
            sort_cols.append("cmc")
            asc.append(True)

        wincon_candidates = wincon_candidates.sort_values(
            by=sort_cols,
            ascending=asc
        )

        seen = set()
        for _, row in wincon_candidates.iterrows():
            if len(wincon_names) >= WINCON_TARGET:
                break
            name = row["name"]
            if name in seen:
                continue
            seen.add(name)
            wincon_names.append(name)

        for n in wincon_names:
            add_card(n, "wincon")

    ramp_names = pick_category(nonlands, "is_ramp", RAMP_TARGET)
    draw_names = pick_category(nonlands, "is_draw", DRAW_TARGET)
    removal_names = pick_category(nonlands, "is_removal", REMOVAL_TARGET)
    wipe_names = pick_category(nonlands, "is_wipe", WIPE_TARGET)

    for n in ramp_names:
        add_card(n, "ramp")
    for n in draw_names:
        add_card(n, "draw")
    for n in removal_names:
        add_card(n, "removal")
    for n in wipe_names:
        add_card(n, "wipe")

    # 8) Fill with synergy cards (engines/payoffs)
    # Avoid duplicates, prefer low cmc
    remaining_synergy = synergy_pool[~synergy_pool["name"].isin(chosen.keys())].copy()
    if not remaining_synergy.empty:
        remaining_synergy["quality"] = remaining_synergy.apply(
            lambda r: card_quality(r, themes),
            axis=1
        )
        remaining_synergy = remaining_synergy.sort_values(
            by=["quality", "cmc"],
            ascending=[False, True]
        )

    # nonland slots we'll aim for before lands adjustment
    NONLAND_TARGET = 61  # 99 - ~38 lands
    for _, row in remaining_synergy.iterrows():
        if len(chosen) >= NONLAND_TARGET:
            break
        add_card(row["name"], "synergy")

    # 9) If still under nonland target, fill with generic goodstuff
    if len(chosen) < NONLAND_TARGET:
        filler = nonlands[~nonlands["name"].isin(chosen.keys())].copy()
        # Prefer lower cmc, and maybe those that still match some themes
        if themes:
            filler["on_theme"] = filler.apply(
                lambda r: card_matches_themes(r, themes),
                axis=1
            )
        else:
            filler["on_theme"] = False

        if "cmc" in filler.columns:
            filler = filler.sort_values(
                by=["on_theme", "cmc"],
                ascending=[False, True]
            )
        else:
            filler = filler.sort_values(
                by=["on_theme"],
                ascending=[False]
            )

        for _, row in filler.iterrows():
            if len(chosen) >= NONLAND_TARGET:
                break
            add_card(row["name"], "filler")

    # 10) Count ramp to get a *target* land base (we'll fix exact 99 later)
    chosen_names = list(chosen.keys())
    chosen_df = nonlands[nonlands["name"].isin(chosen_names)].copy()

    chosen_ramp_count = chosen_df["is_ramp"].sum() if "is_ramp" in chosen_df.columns else 0
    land_count = LAND_BASE - (chosen_ramp_count // 3)
    if land_count < 30:
        land_count = 30

    # 11) Build land package with synergy + speed awareness

    land_rows = []

    # Treat nonbasic lands (anything not a basic name) as singleton lands we own
    nonbasic_lands = lands[~lands["name"].isin(BASIC_LAND_NAMES)].copy()

    # Tag synergy lands and ETB tapped
    nonbasic_lands["is_synergy_land"] = nonbasic_lands.apply(
        lambda r: card_matches_themes(r, themes),
        axis=1
    )
    nonbasic_lands["etb_tapped"] = nonbasic_lands["oracle_text"].str.contains(
        "enters the battlefield tapped",
        case=False,
        na=False
    )

    # Priority function depends on deck speed:
    # fast decks hate taplands unless they're on-theme,
    # slower decks care more about synergy.
    if deck_speed == "fast":
        def land_priority(row):
            if row["is_synergy_land"] and not row["etb_tapped"]:
                return 0  # best
            if not row["is_synergy_land"] and not row["etb_tapped"]:
                return 1
            if row["is_synergy_land"] and row["etb_tapped"]:
                return 2
            return 3  # off-theme tapland: worst
    else:
        def land_priority(row):
            base = 0 if row["is_synergy_land"] else 1
            if row["etb_tapped"]:
                base += 1
            return base

    if not nonbasic_lands.empty:
        nonbasic_lands["priority"] = nonbasic_lands.apply(land_priority, axis=1)
        nonbasic_lands = nonbasic_lands.sort_values(["priority", "name"])
    else:
        nonbasic_lands["priority"] = []

    # Take as many nonbasic lands as our land target allows (1 copy each)
    nonbasic_target = min(len(nonbasic_lands), land_count)
    used_nonbasic = 0
    for _, row in nonbasic_lands.head(nonbasic_target).iterrows():
        land_rows.append({
            "name": row["name"],
            "type_line": row["type_line"],
            "role": "land",
            "count": 1
        })
        used_nonbasic += 1

    nonbasic_land_count = used_nonbasic
    basic_needed = max(0, land_count - nonbasic_land_count)

    # Split basics roughly evenly by commander colors
    basics_by_color = {
        "W": "Plains",
        "U": "Island",
        "B": "Swamp",
        "R": "Mountain",
        "G": "Forest",
    }
    color_basics = [basics_by_color[c] for c in commander_colors if c in basics_by_color]

    if not color_basics:
        # Colorless commander: just use Wastes as a stand-in basic
        color_basics = ["Wastes"]

    per_color = basic_needed // len(color_basics)
    remainder = basic_needed % len(color_basics)

    for i, basic_name in enumerate(color_basics):
        count = per_color + (1 if i < remainder else 0)
        if count <= 0:
            continue
        land_rows.append({
            "name": basic_name,
            "type_line": "Basic Land",
            "role": "land",
            "count": count,
        })

    # 12) Assemble final deck DataFrame
    deck_rows = []

    for name, roles in chosen.items():
        row = nonlands[nonlands["name"] == name].iloc[0]
        deck_rows.append({
            "name": name,
            "type_line": row.get("type_line", ""),
            "role": ",".join(sorted(roles)),
            "count": 1,
        })

    deck_rows.extend(land_rows)

    deck_df = pd.DataFrame(deck_rows)

    # Ensure final deck is exactly 99 cards by topping up basics if needed
    total_cards = int(deck_df["count"].sum())
    if total_cards < 99:
        missing = 99 - total_cards

        # Use first color's basic or Wastes as the top-up land
        basics_by_color = {
            "W": "Plains",
            "U": "Island",
            "B": "Swamp",
            "R": "Mountain",
            "G": "Forest",
        }
        color_basics = [basics_by_color[c] for c in commander_colors if c in basics_by_color]
        if not color_basics:
            basic_name = "Wastes"
        else:
            basic_name = color_basics[0]

        mask = (deck_df["role"] == "land") & (deck_df["name"] == basic_name)
        if mask.any():
            deck_df.loc[mask, "count"] += missing
        else:
            deck_df = pd.concat([
                deck_df,
                pd.DataFrame([{
                    "name": basic_name,
                    "type_line": "Basic Land",
                    "role": "land",
                    "count": missing,
                }])
            ], ignore_index=True)

        total_cards = 99

    print(f"\nBuilt deck for {commander_name}: {total_cards} cards (target 99).")

    return deck_df

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

    # --- Heuristic bracket logic, aligned to WotC’s text ---

    # 5: cEDH-ish – lots of game changers / combo flags / tutors
    if (
        details["num_game_changers"] >= 6
        or (details["has_combo_flag"] and details["num_nonland_tutors"] >= 5)
    ):
        bracket = 5

    # 4: Optimized – no restrictions, fast mana / combos / many game changers
    elif (
        details["num_game_changers"] >= 3
        or details["has_mass_land_denial"]
        or details["num_extra_turns"] > 2
        or details["num_nonland_tutors"] >= 4
    ):
        bracket = 4

    # 3: Upgraded – stronger than precon, maybe a few game changers, decent structure
    elif (
        1 <= details["num_game_changers"] <= 2
        or (
            details["num_ramp"] >= 8
            and details["num_draw"] >= 8
            and details["num_wincons"] >= 3
        )
    ):
        bracket = 3

    # 2: Core – precon-ish, no game changers, few tutors, no land D
    elif (
        details["num_game_changers"] == 0
        and not details["has_mass_land_denial"]
        and details["num_extra_turns"] <= 1
        and details["num_nonland_tutors"] <= 2
    ):
        bracket = 2

    else:
        # Very underpowered / janky / low-ramp decks would fall here.
        bracket = 1

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
    instead of just generic archetype blurbs.
    """

    name = commander_row["name"]
    colors = commander_row["color_identity"]
    themes = commander_row.get("themes", set()) or set()

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
    creature_frac = float((type_lines.str.contains("creature")).mean())
    instant_sorcery_frac = float(
        (type_lines.str.contains("instant") | type_lines.str.contains("sorcery")).mean()
    )

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
    #    and not board wipes, sorted by cmc cheap → expensive.
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

    # Early / mid / late game narrative, now referencing specific cards when possible
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

def auto_pick_best_deck_commander(
    df_all: pd.DataFrame,
    commander_candidates: pd.DataFrame,
    top_k: int = 10,
) -> pd.Series:
    """
    Try the top_k most supported commanders, actually build decks for them,
    rate those decks, and return the commander whose DECK scores best.

    This is what powers the 'lazy button' (0).
    """

    # First, pick a pool of promising commanders to test
    pool = commander_candidates.sort_values(
        by=["theme_support_size", "curve_score", "edhrec_rank_filled"],
        ascending=[False, False, True]
    ).head(top_k)

    best_row = None
    best_score = -1.0

    for _, row in pool.iterrows():
        commander_name = row["name"]
        print(f"\n[Lazy eval] Building trial deck for: {commander_name}")

        # Build a deck for this commander
        trial_deck = build_deck_for_commander(df_all, row)

        # Rate it with your bracket system
        bracket, details = rate_commander_bracket(df_all, trial_deck)

        # Heuristic deck score:
        # - bracket dominates
        # - more game_changers and wincons is better
        # - ramp + draw also matter
        deck_score = (
            bracket * 100
            + details["num_game_changers"] * 5
            + details["num_wincons"] * 3
            + details["num_ramp"]
            + details["num_draw"]
        )

        print(
            f"[Lazy eval] {commander_name}: "
            f"Bracket {bracket}, score {deck_score:.1f} "
            f"(GC {details['num_game_changers']}, "
            f"wincons {details['num_wincons']}, "
            f"ramp {details['num_ramp']}, draw {details['num_draw']})"
        )

        if deck_score > best_score:
            best_score = deck_score
            best_row = row

    if best_row is None:
        raise RuntimeError("auto_pick_best_deck_commander: no candidates found")

    print(
        f"\n[Lazy eval] Best deck candidate: {best_row['name']} "
        f"(score {best_score:.1f})"
    )
    return best_row

def card_quality(row: pd.Series, themes: set[str]) -> float:
    """
    Crude 'how good is this card in this deck' score.
    Higher is better.
    """
    q = 0.0

    # On-theme matters a lot
    if card_matches_themes(row, themes):
        q += 3.0

    # EDHREC rank: lower is better.
    # Treat missing as mediocre.
    rank = row.get("edhrec_rank", None)
    if pd.notna(rank):
        # Scale: 0–10k rank gives up to ~10 points, then flatten
        if rank < 10000:
            q += (10000 - rank) / 1000.0  # 0–10
        else:
            q += 0.5  # it's played, but not a staple
    else:
        q += 0.0

    # Built-in game_changer flag
    if "game_changer" in row and bool(row["game_changer"]):
        q += 4.0

    # Cheap cards are easier to cast; gently reward low CMC
    cmc = row.get("cmc", None)
    if cmc is not None and pd.notna(cmc):
        if cmc <= 2:
            q += 1.5
        elif cmc <= 4:
            q += 0.5
        elif cmc >= 7:
            q -= 0.5  # big clunky, only good if theme really wants it

    return float(q)

def parse_decklist_text(path: str) -> list[str]:
    """
    Parse a Card Kingdom–style text list into a list of card names.
    We ignore comments/blank lines. Counts are currently ignored for
    Commander (singleton), but we keep at least one copy of each name.
    """
    names = []

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith("//"):
                continue

            # Try "N Card Name" first
            parts = line.split()
            if parts[0].isdigit():
                # We *could* use count here, but for EDH singleton
                # we only need to know that you own at least one.
                # If you want to keep counts later, we can store them.
                name = " ".join(parts[1:])
            else:
                name = line

            # Strip any trailing set info in brackets, e.g. "Sol Ring (2XM)"
            # Card Kingdom often does "Card Name (SET)"
            if "(" in name and name.endswith(")"):
                name = name[:name.rfind("(")].strip()

            if name:
                names.append(name)

    # For singleton EDH, unique names are enough
    unique_names = sorted(set(names))
    return unique_names

# Main Run Cycle.

url = "https://api.scryfall.com/cards/collection"

# Default paths – you can still edit these in code if you want
DEFAULT_TEXT_PATH = r"C:\temp\loose cards .txt"
DEFAULT_CSV_PATH  = r"C:\temp\loose cards .csv"

# --- Ask user which input mode to use ---

print("\n=== Input Mode Selection ===")
print("1) CSV (ManaBox export with 'Scryfall ID')")
print("2) Text decklist (Card Kingdom style)")
while True:
    mode = input("\nSelect input mode [1/2]: ").strip()
    if mode in ("1", "2"):
        break
    print("Please enter 1 or 2.")

USE_TEXT_LIST = (mode == "2")

all_cards = []

if USE_TEXT_LIST:
    # ==========================
    # TEXT MODE (Card Kingdom list)
    # ==========================
    print("\nInput mode: TEXT decklist")

    text_path_input = input(
        f"Path to text decklist [{DEFAULT_TEXT_PATH}]: "
    ).strip()
    text_path = text_path_input or DEFAULT_TEXT_PATH

    print(f"Reading decklist from: {text_path}")
    card_names = parse_decklist_text(text_path)
    print(f"Found {len(card_names)} unique card names in text file.")

    identifiers_source = card_names

    def make_identifiers(batch):
        # Scryfall /cards/collection supports {'name': '<card name>'}
        return [{"name": name} for name in batch]

else:
    # ==========================
    # CSV MODE (ID if possible, fallback to Name)
    # ==========================
    print("\nInput mode: CSV (generic – Scryfall ID preferred, Name fallback)")

    csv_path_input = input(
        f"Path to CSV [{DEFAULT_CSV_PATH}]: "
    ).strip()
    csv_path = csv_path_input or DEFAULT_CSV_PATH

    print(f"Reading CSV from: {csv_path}")
    unsortedCards = pd.read_csv(csv_path)

    has_id = "Scryfall ID" in unsortedCards.columns
    has_name = "Name" in unsortedCards.columns

    if not has_id and not has_name:
        raise RuntimeError(
            "CSV mode selected, but the file has neither 'Scryfall ID' nor 'Name' columns.\n"
            "Add one of those or switch to text-list mode."
        )

    identifiers_source = []
    id_count = 0
    name_count = 0

    for _, row in unsortedCards.iterrows():
        cid = row["Scryfall ID"] if has_id else None
        name = row["Name"] if has_name else None

        if has_id and pd.notna(cid):
            # Prefer stable Scryfall ID when present
            identifiers_source.append({"id": cid})
            id_count += 1
        elif has_name and isinstance(name, str) and name.strip():
            # Fallback: use card name lookup
            identifiers_source.append({"name": name.strip()})
            name_count += 1

    print(
        f"Using {id_count} Scryfall IDs and {name_count} Names from CSV "
        f"(total identifiers: {len(identifiers_source)})"
    )

    if not identifiers_source:
        raise RuntimeError(
            "No usable Scryfall IDs or Names were found in the CSV "
            "(all values empty/NaN?)."
        )

    # In CSV mode, identifiers_source already contains proper Scryfall
    # identifier dicts ({'id': ...} or {'name': ...}), so just pass through.
    def make_identifiers(batch):
        return batch

# --- Shared Scryfall fetch logic (works for both modes) ---

batch_size = 75
batches = [
    identifiers_source[i:i + batch_size]
    for i in range(0, len(identifiers_source), batch_size)
]

for idx, batch in enumerate(batches, start=1):
    identifiers = make_identifiers(batch)

    resp = requests.post(url, json={"identifiers": identifiers})
    resp.raise_for_status()
    data = resp.json()

    cards = data.get("data", [])
    not_found = data.get("not_found", [])

    print(
        f"Fetched batch {idx}/{len(batches)}: "
        f"{len(cards)} cards, {len(not_found)} not found"
    )
    if not_found:
        print("  Not found:", [c.get("name") or c.get("id") for c in not_found])

    all_cards.extend(cards)

    # Be polite to Scryfall
    time.sleep(0.1)

df = pd.json_normalize(all_cards)

# Normalize Scryfall's game_changer to a clean bool
if "game_changer" in df.columns:
    df["game_changer"] = df["game_changer"].fillna(False).astype(bool)
else:
    df["game_changer"] = False

commander_candidates = get_commander_candidates(df)
print("Commander candidates:", len(commander_candidates))
print(commander_candidates[["name", "edhrec_rank", "color_identity"]].head(10))


best_commander = commander_candidates.iloc[0]
print("Chosen commander (by EDHREC):", best_commander["name"])

# Precompute themes for each commander so we can reuse them
commander_candidates["themes"] = commander_candidates.apply(
    get_commander_themes,
    axis=1
)


# --- Compute THEMED support size for each commander ---

theme_support_sizes = []
avg_synergy_cmcs = []
curve_scores = []

for _, row in commander_candidates.iterrows():
    # 1) Legal pool: on-color cards
    pool = get_legal_pool(df, row)

    # 2) Themes this commander actually cares about
    themes = row["themes"]

    # 3) Filter to cards that match at least one of those themes
    if themes:
        synergy_mask = pool.apply(
            lambda r: card_matches_themes(r, themes),
            axis=1
        )
        synergy_pool = pool[synergy_mask].copy()
    else:
        # Commander with no recognizable themes = zero themed support
        synergy_pool = pool.iloc[0:0]  # empty frame

    # 4) Optionally strip the commander itself out of its support
    if "name" in synergy_pool.columns:
        is_self = synergy_pool["name"] == row["name"]
        theme_support_size = len(synergy_pool) - is_self.sum()
    else:
        theme_support_size = len(synergy_pool)

    theme_support_sizes.append(theme_support_size)

    # 4) Curve metrics for this commander's synergy pool
    metrics = compute_curve_metrics(synergy_pool)
    avg_synergy_cmcs.append(metrics["avg_cmc"])
    # Simple curve score:
    # - reward lots of cheap cards (low_frac)
    # - punish lots of 6+ drops (high_frac)
    curve_score = metrics["low_frac"] - metrics["high_frac"]
    curve_scores.append(curve_score)

commander_candidates["theme_support_size"] = theme_support_sizes
commander_candidates["avg_synergy_cmc"] = avg_synergy_cmcs
commander_candidates["curve_score"] = curve_scores

top_supported = commander_candidates.sort_values(
    by=["theme_support_size", "curve_score", "edhrec_rank_filled"],
    ascending=[False, False, True]
).head(5)

print("\nTop 5 commanders by *themed* supported cards in your collection:")
print(top_supported[["name", "color_identity", "themes","theme_support_size", "curve_score", "avg_synergy_cmc", "edhrec_rank", "oracle_text"]])

# Let's inspect the top themed-supported commander in detail
top_commander = top_supported.iloc[0]

print("\n=== Inspecting top themed commander ===")
print("Name:", top_commander["name"])
print("Colors:", top_commander["color_identity"])
print("EDHREC rank:", top_commander["edhrec_rank"])

# Show themes the script thinks this commander cares about
themes = get_commander_themes(top_commander)
print("Detected themes:", themes)
print("Oracle text:\n", top_commander["oracle_text"])

# Prepare a clean, numbered view for selection
selection_df = top_supported.reset_index(drop=True).copy()
selection_df.index = selection_df.index + 1  # 1–5 instead of 0–4

print("\nChoose a commander to build:")
print(selection_df[[
    "name",
    "color_identity",
    "theme_support_size",
    "curve_score",
    "themes"
]])
print(f"\nEnter 1–{len(selection_df)} to pick manually, or 0 to auto-pick the strongest Deck.")

while True:
    user_input = input(
        "\nEnter a number 0–{} (0 = strongest deck): ".format(len(selection_df))
    ).strip()

    try:
        choice = int(user_input)
    except ValueError:
        print("Please enter a valid number.")
        continue

    if choice == 0:
        # Lazy mode: evaluate several commanders and pick the one whose DECK scores best
        chosen_commander = auto_pick_best_deck_commander(df, commander_candidates, top_k=10)
        print("\nLazy mode chose:", chosen_commander["name"])
        break
    elif 1 <= choice <= len(selection_df):
        chosen_commander = selection_df.iloc[choice - 1]
        break
    else:
        print("Choice out of range, try again.")

print("\nYou chose:", chosen_commander["name"])
print("Colors:", chosen_commander["color_identity"])
print("Themes:", chosen_commander["themes"])
print("Oracle text:\n", chosen_commander["oracle_text"])

deck_df = build_deck_for_commander(df, chosen_commander)

# Example: export to CSV
deck_output_path = r"C:\temp\{}_deck.csv".format(
    chosen_commander["name"].replace(" ", "_")
)
deck_df.to_csv(deck_output_path, index=False)
print("Deck exported to:", deck_output_path)


bracket, bracket_details = rate_commander_bracket(df, deck_df)
print(f"\nCommander Bracket estimate: {bracket}")
print("Details:", bracket_details)

summary = describe_deck_play_pattern(
    df_all=df,
    deck_df=deck_df,
    commander_row=chosen_commander,
    bracket=bracket,
    bracket_details=bracket_details,
)
print("\n=== How this deck plays ===")
print(summary)