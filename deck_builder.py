#==================================================
# Convert .txt or .csv of cards into a usable list.
#==================================================

# Modules
import requests
import pandas as pd
import time
from collections import defaultdict

# From other functions
from themes import (
    get_commander_themes,
    card_matches_themes,
)

from roles import get_card_roles

from card_features import (
    is_land,
    is_ramp,
    is_card_draw,
    is_board_wipe,
    is_removal,
    has_persistent_output,
    persistence_score,
    is_game_changer
)

from scoring import (
    commander_synergy_score,
    build_commander_profile,
    compute_curve_metrics,
    wincon_score,
    analyze_commander_plan,
    rate_commander_bracket,
    describe_deck_play_pattern,
    advanced_card_score_for_commander,   # ← NEW
)

from constants import BASIC_LAND_NAMES

#Functions

def get_commander_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pick Commander-eligible cards and sort them so 'better-supported' options float up.

    - Legendary Creatures
    - Cards that say 'can be your commander'
    - Sort by EDHREC rank if present, otherwise fall back to name.
    """
    # Legendary creatures are natural commanders
    is_legendary_creature = df["type_line"].str.contains("Legendary Creature", na=False)

    # Some non-legendaries explicitly say they can be your commander
    says_can_be_commander = df["oracle_text"].str.contains(
        "can be your commander",
        case=False,
        na=False
    )

    candidates = df[is_legendary_creature | says_can_be_commander].copy()

    # Robust EDHREC handling
    if "edhrec_rank" in candidates.columns:
        candidates["edhrec_rank_filled"] = candidates["edhrec_rank"].fillna(999_999)
        candidates = candidates.sort_values(
            ["edhrec_rank_filled", "name"],
            ascending=[True, True],
        )
    else:
        # No EDHREC at all – just sort by name to keep it deterministic
        candidates["edhrec_rank_filled"] = 999_999
        candidates = candidates.sort_values("name", ascending=True)

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

def get_edh_rank_bounds(df: pd.DataFrame) -> tuple[int, int]:
    """
    Robust min/max EDHREC rank for popularity_score.

    - If the column is missing or empty → fall back to [1, 300000].
    - If all ranks are the same → widen the window by 1 to avoid log div-by-zero.
    """
    if "edhrec_rank" not in df.columns:
        return 1, 300_000

    series = df["edhrec_rank"].dropna()
    if series.empty:
        return 1, 300_000

    min_rank = int(series.min())
    max_rank = int(series.max())

    # Clamp to sane values
    if min_rank < 1:
        min_rank = 1
    if max_rank < min_rank:
        max_rank = min_rank + 1
    if max_rank == min_rank:
        max_rank = min_rank + 1

    return min_rank, max_rank

def classify_engine_tags(row: pd.Series) -> str:
    """
    Roughly classify what kind of value engine a card is, based on:
    - persistent output
    - its role string
    - oracle text keywords

    This is *descriptive*, not used for scoring.
    """
    if not bool(row.get("has_persistent_output", False)):
        return ""

    text = str(row.get("oracle_text", "")).lower()
    role_str = str(row.get("role", "")).lower()

    tags = []

    # Ramp-y engines
    if "ramp" in role_str or "add {" in text or "add one mana" in text:
        tags.append("ramp_engine")

    # Card advantage engines
    if "draw" in role_str or "draw a card" in text or "card advantage" in text:
        tags.append("card_advantage_engine")

    # Token factories / board presence
    if "create" in text and "token" in text:
        tags.append("token_engine")

    # Death / aristocrats engines
    if "whenever" in text and "dies" in text:
        tags.append("death_trigger_engine")

    # Spellslinger / cast triggers
    if "whenever you cast" in text or "whenever you cast a spell" in text:
        tags.append("spellslinger_engine")

    # If we saw nothing specific but it *is* persistent, call it a generic engine
    if not tags:
        tags.append("generic_engine")

    return ",".join(tags)

def build_deck_for_commander(df: pd.DataFrame, commander_row: pd.Series) -> pd.DataFrame:
    """
    Build a 99-card list (excluding the commander itself) using:
    - legal pool (color identity)
    - commander themes / plan profile
    - synergy scoring (advanced_card_score_for_commander with safe fallbacks)
    - ramp/draw/removal/wipe classification
    - infinite basic lands to fill the mana base
    """
    commander_name = commander_row["name"]
    commander_colors = list(commander_row.get("color_identity") or [])

    # Build reusable commander profile + plan once
    commander_profile = build_commander_profile(commander_row)
    commander_plan = analyze_commander_plan(commander_row)

    # We'll set curve_pref later once we've seen the actual chosen nonlands
    commander_profile["curve_pref"] = "normal"

    # 1) Get legal pool for this commander
    pool = get_legal_pool(df, commander_row)

    # Ensure roles are present (in case you didn't precompute globally)
    if "roles" not in pool.columns:
        pool = pool.copy()
        pool["roles"] = pool.apply(get_card_roles, axis=1)

    # 2) Split lands / nonlands
    lands = pool[pool.apply(is_land, axis=1)].copy()
    nonlands = pool[~pool.apply(is_land, axis=1)].copy()

    # Robust EDH bounds for popularity component
    edh_min_rank, edh_max_rank = get_edh_rank_bounds(df)

    # 3) Compute commander-specific scores for nonlands
    def compute_synergy(r: pd.Series) -> float:
        """
        Prefer the advanced scorer, but never crash:
        fall back to old commander_synergy_score on error.
        """
        try:
            return advanced_card_score_for_commander(
                card_role_row=r,
                commander_profile=commander_profile,
                commander_plan=commander_plan,
                edh_min_rank=edh_min_rank,
                edh_max_rank=edh_max_rank,
            )
        except Exception:
            return commander_synergy_score(commander_profile, r)

    nonlands = nonlands.copy()
    nonlands["synergy_score"] = nonlands.apply(compute_synergy, axis=1)

    themes = commander_row.get("themes", set()) or set()

    # Themed synergy pool: cards that either match themes OR have positive synergy_score
    if themes:
        synergy_mask = nonlands.apply(
            lambda r: card_matches_themes(r, themes),
            axis=1
        )
    else:
        synergy_mask = nonlands["synergy_score"] > 0

    synergy_pool = nonlands[synergy_mask | (nonlands["synergy_score"] > 0)].copy()

    # Prefer higher synergy_score, then lower cmc
    if "cmc" in synergy_pool.columns:
        synergy_pool = synergy_pool.sort_values(
            by=["synergy_score", "cmc"],
            ascending=[False, True]
        )
    else:
        synergy_pool = synergy_pool.sort_values(
            by=["synergy_score"],
            ascending=False
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

        # Prefer on-theme, then by cmc ascending
        if "name" in synergy_pool.columns:
            candidates["on_theme"] = candidates["name"].isin(synergy_pool["name"])
        else:
            candidates["on_theme"] = False

        if "cmc" in candidates.columns:
            candidates = candidates.sort_values(
                by=["on_theme", "cmc"],
                ascending=[False, True]
            )
        else:
            candidates = candidates.sort_values(
                by=["on_theme"],
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
    if "cmc" in remaining_synergy.columns:
        remaining_synergy = remaining_synergy.sort_values("cmc", ascending=True)

    NONLAND_TARGET = 57  # 99 - ~42 lands

    for _, row in remaining_synergy.iterrows():
        if len(chosen) >= NONLAND_TARGET:
            break
        add_card(row["name"], "synergy")

    # 9) If still under nonland target, fill with generic goodstuff
    if len(chosen) < NONLAND_TARGET:
        filler = nonlands[~nonlands["name"].isin(chosen.keys())].copy()

        if themes:
            filler["on_theme"] = filler.apply(
                lambda r: card_matches_themes(r, themes),
                axis=1
            )
        else:
            filler["on_theme"] = False

        if "synergy_score" not in filler.columns:
            filler["synergy_score"] = filler.apply(
                lambda r: commander_synergy_score(commander_profile, r),
                axis=1
            )

        if "cmc" in filler.columns:
            filler = filler.sort_values(
                by=["on_theme", "synergy_score", "cmc"],
                ascending=[False, False, True]
            )
        else:
            filler = filler.sort_values(
                by=["on_theme", "synergy_score"],
                ascending=[False, False]
            )

        for _, row in filler.iterrows():
            if len(chosen) >= NONLAND_TARGET:
                break
            add_card(row["name"], "filler")

    # 10) Land count — Commander-optimized, based on 42 → 37 heuristic
    chosen_names = list(chosen.keys())
    chosen_df = nonlands[nonlands["name"].isin(chosen_names)].copy()

    deck_speed = "midrange"

    if not chosen_df.empty and "cmc" in chosen_df.columns:
        cmc_series = chosen_df["cmc"].fillna(0)
        avg_cmc = float(cmc_series.mean())
        low_frac = float((cmc_series <= 2).mean())   # really cheap stuff
        high_frac = float((cmc_series >= 6).mean())  # true top-end

        if avg_cmc <= 2.7 and low_frac >= 0.60:
            deck_speed = "fast"
        elif avg_cmc >= 3.8 or high_frac >= 0.25:
            deck_speed = "slow"
    else:
        avg_cmc = 3.0  # fallback
        low_frac = 0.0
        high_frac = 0.0
    
    commander_profile["curve_pref"] = deck_speed

    # Ramp package we actually play
    ramp_df = chosen_df[chosen_df.get("is_ramp", False) == True].copy()
    ramp_count = len(ramp_df)

    # Mana dorks: creatures that tap for mana
    def is_mana_dork(r: pd.Series) -> bool:
        tl = str(r.get("type_line", "")).lower()
        txt = str(r.get("oracle_text", "")).lower()
        return ("creature" in tl) and ("add {" in txt)

    # Mana rocks: artifacts that tap for mana
    def is_mana_rock(r: pd.Series) -> bool:
        tl = str(r.get("type_line", "")).lower()
        txt = str(r.get("oracle_text", "")).lower()
        return ("artifact" in tl) and ("add {" in txt)

    dork_count = int(ramp_df.apply(is_mana_dork, axis=1).sum())
    rock_count = int(ramp_df.apply(is_mana_rock, axis=1).sum())

    # Cheap cantrips: "draw a card" style effects at CMC ≤ 2
    if "cmc" in chosen_df.columns:
        cantrip_df = chosen_df[
            (chosen_df.get("is_draw", False) == True)
            & (chosen_df["cmc"].fillna(99) <= 2)
        ].copy()
    else:
        cantrip_df = chosen_df.iloc[0:0].copy()
    cantrip_count = len(cantrip_df)

    # Start from 42 lands (article baseline assumes Sol Ring is present)
    land_count = 42

    # Cut 1 land per ~2–3 mana rocks
    land_count -= rock_count // 3

    # Cut 1 land per ~3–4 mana dorks
    land_count -= dork_count // 4

    # Cut 1 land per ~3–4 cheap cantrips
    land_count -= cantrip_count // 4

    # Don't go below 37 for normal midrange Commander
    if land_count < 35:
        land_count = 35

    # Also cap at the starting 42, just so we don't drift upwards
    if land_count > 42:
        land_count = 42

        # 11) Build land package with synergy + speed awareness

    land_rows = []

    nonbasic_lands = lands[~lands["name"].isin(BASIC_LAND_NAMES)].copy()

    nonbasic_lands["is_synergy_land"] = nonbasic_lands.apply(
        lambda r: card_matches_themes(r, themes),
        axis=1
    )
    nonbasic_lands["etb_tapped"] = nonbasic_lands["oracle_text"].str.contains(
        "enters the battlefield tapped",
        case=False,
        na=False
    )

    # --- NEW: tapland caps per deck speed ---
    if deck_speed == "fast":
        tap_cap = 6       # aim for ~0–6 taplands total
    elif deck_speed == "slow":
        tap_cap = 12      # control can afford more
    else:  # midrange / unknown
        tap_cap = 9

    # Prioritize:
    #  0: untapped + on-theme
    #  1: untapped + off-theme
    #  2: tapped + on-theme
    #  3: tapped + off-theme
    def land_priority(row):
        if not row["etb_tapped"] and row["is_synergy_land"]:
            return 0
        if not row["etb_tapped"] and not row["is_synergy_land"]:
            return 1
        if row["etb_tapped"] and row["is_synergy_land"]:
            return 2
        return 3

    if not nonbasic_lands.empty:
        nonbasic_lands["priority"] = nonbasic_lands.apply(land_priority, axis=1)
        nonbasic_lands = nonbasic_lands.sort_values(["priority", "name"])
    else:
        nonbasic_lands["priority"] = []

    # Take as many nonbasic lands as our land target allows,
    # but respect the tapland cap.
    nonbasic_target = land_count
    used_nonbasic = 0
    used_taplands = 0

    for _, row in nonbasic_lands.iterrows():
        if used_nonbasic >= nonbasic_target:
            break

        if row["etb_tapped"]:
            if used_taplands >= tap_cap:
                # skip extra taplands
                continue
            used_taplands += 1

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

def filter_commander_legal(df: pd.DataFrame, allow_banned: bool = False) -> pd.DataFrame:
    """
    Strip out tokens, planes, dungeons, attractions, etc. and anything that
    isn't Commander-legal in paper.

    - Keeps only cards that can actually appear in a Commander deck.
    - Excludes token/emblem/plane/phenomenon/vanguard/scheme/sticker/etc.
    """

    df = df.copy()

    # 1) Only cards that exist in paper
    if "games" in df.columns:
        df = df[df["games"].apply(lambda g: isinstance(g, list) and "paper" in g)]

    # 2) Commander legality from Scryfall
    # json_normalize creates a 'legalities.commander' column
    if "legalities.commander" in df.columns:
        if allow_banned:
            df = df[df["legalities.commander"].isin(["legal", "banned"])]
        else:
            df = df[df["legalities.commander"] == "legal"]

    # 3) Filter out objects that are structurally not deck cards

    # Layout-based cut (tokens, emblems, planes, etc.)
    bad_layouts = {
        "token",
        "double_faced_token",
        "emblem",
        "art_series",
        "planar",
        "scheme",
        "vanguard",
        "reversible_card",
    }
    if "layout" in df.columns:
        df = df[~df["layout"].isin(bad_layouts)]

    # Type line backup (in case some weird layout slips through)
    if "type_line" in df.columns:
        bad_type_words = [
            "Token",
            "Plane",
            "Phenomenon",
            "Scheme",
            "Vanguard",
            "Dungeon",
            "Attraction",
            "Sticker",
        ]
        bad_pattern = "|".join(bad_type_words)
        mask_bad = df["type_line"].fillna("").str.contains(bad_pattern, na=False)
        df = df[~mask_bad]

    return df

def summarize_engines_and_loops(
    df_all: pd.DataFrame,
    deck_df: pd.DataFrame,
    commander_name: str,
) -> None:
    """
    Print and export a report of:
    - persistent value engines in the final 99
    - big swing / potential loop-pivot cards

    Does NOT affect deckbuilding; purely analysis.
    """
    # Columns we care about from the global card pool
    base_cols = ["name", "oracle_text"]
    engine_cols = [
        c for c in [
            "has_persistent_output",
            "persistence_score",
            "game_changer",
            "game_changer_flag",
        ]
        if c in df_all.columns
    ]
    cols = list(dict.fromkeys(base_cols + engine_cols))  # dedupe, preserve order

    merged = deck_df.merge(
        df_all[cols],
        on="name",
        how="left",
        suffixes=("", "_card"),
    )

    # --- Value engines: persistent sources of advantage ---
    if "has_persistent_output" not in merged.columns:
        print("\n[Engine report] No has_persistent_output column found; "
              "did you forget to compute engine features on df?")
        return

    engines = merged[merged["has_persistent_output"] == True].copy()

    if engines.empty:
        print("\n=== Engine Report ===")
        print("No obvious persistent value engines detected in this deck.")
    else:
        # Attach readable tags
        engines["engine_tags"] = engines.apply(classify_engine_tags, axis=1)

        if "persistence_score" in engines.columns:
            engines = engines.sort_values("persistence_score", ascending=False)

        print("\n=== Value engines in this deck (persistent sources of advantage) ===")
        print(
            engines[
                [c for c in ["name", "role", "engine_tags", "persistence_score"]
                 if c in engines.columns]
            ].head(30)
        )

        # Export a CSV for offline inspection
        engine_export_cols = [
            "name",
            "role",
            "engine_tags",
            "persistence_score",
            "oracle_text",
        ]
        existing = [c for c in engine_export_cols if c in engines.columns]
        engine_export = engines[existing].copy()

        engine_export_path = rf"C:\temp\{commander_name.replace(' ', '_')}_engines.csv"
        engine_export.to_csv(engine_export_path, index=False)
        print(f"\n[Engine report] Exported engine details to: {engine_export_path}")

    # --- Big swing / potential loop pivots (very coarse) ---
    if "game_changer_flag" in merged.columns:
        pivots = merged[merged["game_changer_flag"] == True].copy()
    elif "game_changer" in merged.columns:
        pivots = merged[merged["game_changer"] == True].copy()
    else:
        pivots = merged.iloc[0:0].copy()

    if not pivots.empty:
        print("\n=== Big swing / potential loop-pivot cards ===")
        print(pivots[["name", "role"]].head(30))

# Main Run Cycle.

url = "https://api.scryfall.com/cards/collection"
path = r"C:/temp/loose cards .csv"
output_path = r"C:\temp\loose_cards_enriched.csv"

unsortedCards = pd.read_csv(path)
scryfall_ids = unsortedCards["Scryfall ID"].dropna().tolist()

batch_size = 75
batches = [
    scryfall_ids[i:i + batch_size]
    for i in range(0, len(scryfall_ids), batch_size)
]

all_cards = []

for idx, batch in enumerate(batches, start=1):
    identifiers = [{"id": cid} for cid in batch]

    resp = requests.post(url, json={"identifiers": identifiers})
    resp.raise_for_status()
    data = resp.json()

    print(f"Fetched batch {idx}: {len(data['data'])} cards")
    all_cards.extend(data["data"])
    
    time.sleep(0.1)

df = pd.json_normalize(all_cards)

# Normalize Scryfall's game_changer to a clean bool
if "game_changer" in df.columns:
    df["game_changer"] = df["game_changer"].fillna(False).astype(bool)
else:
    df["game_changer"] = False

# --- Engine features: persistent value + game-changers ---

# Persistent value engines (your own heuristic in card_features)
df["has_persistent_output"] = df.apply(has_persistent_output, axis=1)
df["persistence_score"] = df.apply(persistence_score, axis=1)

# Optional: combine Scryfall's tag with your own heuristic
try:
    local_gc = df.apply(is_game_changer, axis=1)
    df["game_changer_flag"] = df["game_changer"] | local_gc
except Exception:
    # If is_game_changer isn't available or blows up, just reuse Scryfall field
    df["game_changer_flag"] = df["game_changer"]

df = filter_commander_legal(df)

df["roles"] = df.apply(get_card_roles, axis=1)

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

plan_info_series = commander_candidates.apply(analyze_commander_plan, axis=1)

commander_candidates["plan_type"] = plan_info_series.apply(
    lambda d: d["plan_type"]
)
commander_candidates["plan_tags"] = plan_info_series.apply(
    lambda d: d["loop_tags"]
)
commander_candidates["plan_notes"] = plan_info_series.apply(
    lambda d: d["notes"]
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

# --- NEW: Engine / loop report for the final 99 ---
summarize_engines_and_loops(
    df_all=df,
    deck_df=deck_df,
    commander_name=chosen_commander["name"],
)

# --- Build export-friendly CSV with "count name" + commander on top ---

# First, prepend the commander as a row
commander_name = chosen_commander["name"]
commander_type_line = chosen_commander.get("type_line", "")

commander_row = {
    "name": commander_name,
    "type_line": commander_type_line,
    "role": "commander",
    "count": 1,
}

# Make sure deck_df has the expected columns
# (name, type_line, role, count)
deck_with_commander = pd.concat(
    [pd.DataFrame([commander_row]), deck_df],
    ignore_index=True
)

# Combine count + name into a single string column, e.g. "1 Sol Ring"
deck_with_commander["card"] = (
    deck_with_commander["count"].astype(int).astype(str)
    + " "
    + deck_with_commander["name"]
)

# Choose what you actually want in the CSV.
# First column is the import-friendly "card" string;
# keep role and type_line for your own analysis if you want.
export_df = deck_with_commander[["card", "role", "type_line"]]

deck_output_path = r"C:\temp\{}_deck.csv".format(
    commander_name.replace(" ", "_")
)

export_df.to_csv(deck_output_path, index=False)
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