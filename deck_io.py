#==================================================
# Convert .txt or .csv of cards into a usable list.
#==================================================

# Modules
import requests
import pandas as pd
import time
from collections import defaultdict

#Dictionary
THEME_KEYWORDS = {
    "tokens": [
        # Core token language
        "create a token",
        "create one or more tokens",
        "create a 1/1",
        "create a 2/2",
        "create a 3/3",
        "creature token",
        "artifact token",
        "enchantment token",
        "token that's a copy",
        "token that’s a copy",
        "tokens you control",
        # Specific token types (overlaps with artifacts / lands)
        "treasure token",
        "clue token",
        "food token",
        "blood token",
        "incubator token",
        "map token",
        "servo token",
        "thopter token",
        "germ token",
        # Mechanics that produce tokens / token-like bodies
        "populate",
        "myriad",
        "afterlife",
        "encore",
        "training",
        "rally",
        "alliance",
        "amass",
        "investigate",
        "incubate",
        "embalm",
        "eternalize",
        "disturb",     # often spirit tokens
    ],

    "sacrifice": [
        # Explicit sac costs
        "sacrifice a creature",
        "sacrifice another creature",
        "sacrifice a permanent",
        "sacrifice an artifact",
        "sacrifice an enchantment",
        "sacrifice a land",
        "sacrifice this creature",
        "sacrifice it",
        # Death triggers / “aristocrats” language
        "whenever a creature dies",
        "whenever another creature dies",
        "when a creature you control dies",
        "whenever a nontoken creature you control dies",
        "whenever a creature you control dies",
        "dies, each opponent",
        # Death / sac leaning mechanics
        "exploit",
        "morbid",
    ],

    "spellslinger": [
        # Classic spellslinger text
        "instant or sorcery spell",
        "noncreature spell",
        "whenever you cast an instant",
        "whenever you cast a sorcery",
        "whenever you cast a noncreature spell",
        "whenever you cast a spell,",
        "copy that spell",
        "copy target instant or sorcery",
        "storm",
        "prowess",
        "magecraft",
        # Spell-recursion / cast-from-yard mechanics
        "flashback",
        "jump-start",
        "rebound",
        "delve",
        "buyback",
        "cascade",
        "you may cast target instant",
        "you may cast target sorcery",
        "cast target instant or sorcery card from your graveyard",
        "cast spells from your graveyard",
    ],

    "counters": [
        # +1/+1 counters
        "+1/+1 counter",
        "put a +1/+1 counter",
        "additional +1/+1 counters",
        "distribute +1/+1 counters",
        "number of +1/+1 counters",
        # Generic counters
        "counter on target permanent",
        "counters on target permanent",
        "counters on it",
        "remove a counter from",
        "double the number of counters",
        "for each counter on",
        # Counter-related mechanics
        "proliferate",
        "energy counter",
        "experience counter",
        "shield counter",
        "oil counter",
        "loyalty counter",
        # Ability words / systems driven by counters
        "adapt",
        "bolster",
        "support",
        "outlast",
        "mentor",
        "explore",
        "level up",
        "saga",      # chapter counters
        "evolve",
        "graft",
        "modular",
    ],

    "artifacts": [
        # General artifact references
        "artifact you control",
        "artifacts you control",
        "artifact spell",
        "artifact creature",
        "noncreature artifact",
        "equipment",
        "equipment you control",
        "equipped creature",
        "vehicles you control",
        "vehicle",
        # Artifact token types (intentionally overlapping with tokens)
        "treasure token",
        "clue token",
        "food token",
        "blood token",
        "servo token",
        "thopter token",
        "germ token",
        # Artifact-centric mechanics
        "affinity for artifacts",
        "metalcraft",
        "improvise",
        "fabricate",
        "living weapon",
        "modular",
        # Equipment-specific
        "equip {",
        "reconfigure",
    ],

    "lifegain": [
        # Direct lifegain
        "you gain life",
        "you gain x life",
        "gain life equal to",
        "gains life equal to",
        "gains that much life",
        "life for each",
        # Lifegain payoff
        "whenever you gain life",
        "for each 1 life you gained",
        "for each life you gained",
        # Keywords / mechanics tied to lifegain
        "lifelink",
        "extort",
        # common “soul sisters” will be caught by lifegain text anyway,
        # but you can add names if you want more direct hits:
        "soul warden",
        "soul's attendant",
    ],

    "lands": [
        # Landfall and variants
        "landfall",
        "whenever a land enters the battlefield",
        "whenever a land enters the battlefield under your control",
        "whenever one or more lands enter the battlefield under your control",
        # Extra land plays
        "play an additional land",
        "you may play an additional land",
        "you may play an extra land",
        # Land search / ramp text
        "search your library for a land card",
        "search your library for a basic land card",
        "search your library for a forest card",
        "put a land card from your hand onto the battlefield",
        "put a land card from your graveyard onto the battlefield",
        "onto the battlefield tapped, then shuffle",
        # Domain / land-based scaling
        "domain",
        "landcycling",
        "basic landcycling",
        "awaken",
        "for each land you control",
        "equal to the number of lands you control",
        # Lands in graveyard / recursion
        "return target land card from your graveyard",
        "lands in your graveyard",
        "for each land card in your graveyard",
        # Land tokens
        "create a tapped land token",
        "create a colorless land token",
    ],

    "graveyard": [
        # Explicit graveyard references
        "from your graveyard",
        "from their graveyard",
        "from each graveyard",
        "from all graveyards",
        "cards in your graveyard",
        "creature cards in your graveyard",
        "return target creature card from your graveyard",
        "return target card from your graveyard",
        "return any number of target creature cards",
        "exile target card from a graveyard",
        "exile all cards from target player's graveyard",
        # Self-mill / mill
        "mill a card",
        "mill two cards",
        "mill three cards",
        "mill four cards",
        "mills a card",
        "put the top card of your library into your graveyard",
        "put the top two cards of your library into your graveyard",
        "put the top three cards of your library into your graveyard",
        "put the top four cards of your library into your graveyard",
        # Yard mechanics
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
        "encore",
        # Reanimation / casting from yard
        "return target creature card from a graveyard to the battlefield",
        "return target creature card from your graveyard to the battlefield",
        "you may cast creature spells from your graveyard",
        "cast target creature card from your graveyard",
    ],

    "control": [
        # Hard permission / counterspells
        "counter target spell",
        "counter target noncreature spell",
        "counter target creature spell",
        # Board control / mass removal (control-style)
        "destroy all creatures",
        "exile all creatures",
        "destroy all nonland permanents",
        "exile all nonland permanents",
        "each creature gets -",
        "all creatures get -",
        # Lock / tax effects
        "players can't cast more than one spell each turn",
        "players can’t cast more than one spell each turn",
        "players can't draw more than one card each turn",
        "players can’t draw more than one card each turn",
        "spells your opponents cast cost",
        "spells your opponent casts cost",
        "spells your opponents cast cost {1} more",
        "creatures your opponents control get",
        "creatures your opponents control enter the battlefield tapped",
        # Tap / stun / freeze and untap denial
        "tapped creatures don't untap",
        "tapped creatures don’t untap",
        "skip your untap step",
        "doesn't untap during its controller's untap step",
        "doesn’t untap during its controller’s untap step",
        "can't attack or block",
        "can't attack you or a planeswalker you control",
        "can't attack you or planeswalkers you control",
        # Repeatable upkeep / attrition triggers
        "at the beginning of each opponent's upkeep",
        "at the beginning of each opponent’s upkeep",
        "at the beginning of each player’s upkeep",
    ],

    "voltron": [
        # Equipment / Auras that focus on a single creature
        "equipped creature gets",
        "equipped creature has",
        "equipped creature has hexproof",
        "equipped creature has indestructible",
        "equipped creature gets +",
        "equipped creature can't be blocked",
        # Generic equipment text
        "equip {",
        "reconfigure",
        # Aura-based tall strategies
        "enchant creature you control",
        "enchant creature you own",
        "enchant legendary creature",
        "enchant commander",
        # Pump + evasion / protection on one target
        "target creature gets +",
        "target creature gets +x/+x",
        "target creature you control gets +",
        "target creature you control gains hexproof",
        "target creature you control gains indestructible",
        "target creature you control gains double strike",
        "target creature you control can't be blocked",
        # Commander damage / combat emphasis
        "whenever enchanted creature deals combat damage",
        "whenever equipped creature deals combat damage",
        "deals combat damage to a player, do",
    ],
}

KEYWORD_THEME_OVERRIDES: dict[str, set[str]] = {
    # Evergreen combat & protection
    "deathtouch": {"control", "voltron"},
    "defender": {"control"},
    "double strike": {"voltron"},
    "enchant": {"voltron", "control"},
    "equip": {"artifacts", "voltron"},
    "first strike": {"voltron"},
    "flash": {"control", "spellslinger"},
    "flying": {"voltron", "control"},
    "haste": {"voltron"},
    "hexproof": {"voltron", "control"},
    "indestructible": {"voltron", "control"},
    "intimidate": {"voltron"},
    "landwalk": {"lands", "voltron"},
    "lifelink": {"lifegain", "voltron"},
    "protection": {"voltron", "control"},
    "reach": {"control"},
    "shroud": {"voltron", "control"},
    "trample": {"voltron", "counters"},
    "vigilance": {"voltron", "control"},
    "ward": {"voltron", "control"},

    # Old/weird combat stuff
    "banding": {"voltron"},
    "rampage": {"voltron"},
    "cumulative upkeep": {"control"},
    "flanking": {"voltron"},
    "phasing": {"control"},

    # Spell recursion / cost tweaks / spellstorm
    "buyback": {"spellslinger", "control"},
    "cycling": {"spellslinger", "graveyard"},
    "echo": {"control"},
    "kicker": {"spellslinger"},
    "flashback": {"spellslinger", "graveyard"},
    "madness": {"spellslinger", "graveyard"},
    "storm": {"spellslinger", "control"},
    "entwine": {"spellslinger"},
    "splice": {"spellslinger"},
    "replicate": {"spellslinger"},
    "forecast": {"control", "spellslinger"},
    "ripple": {"spellslinger"},
    "split second": {"control"},
    "suspend": {"spellslinger", "control"},
    "vanishing": {"control"},
    "delve": {"spellslinger", "graveyard"},
    "conspire": {"spellslinger"},
    "retrace": {"spellslinger", "graveyard"},
    "cascade": {"spellslinger"},
    "rebound": {"spellslinger"},
    "miracle": {"spellslinger"},
    "overload": {"spellslinger", "control"},
    "fuse": {"spellslinger"},
    "unddaunted": {"spellslinger"} if False else set(),  # typo guard; real one below
    "undaunted": {"spellslinger"},
    "assist": {"spellslinger"},
    "jump-start": {"spellslinger", "graveyard"},
    "surge": {"spellslinger"},
    "escalate": {"spellslinger"},
    "foretell": {"spellslinger", "control"},
    "demonstrate": {"spellslinger"},
    "plot": {"spellslinger"},
    "spree": {"spellslinger"},
    "freerunning": {"spellslinger", "voltron"},

    # Artifacts / vehicles / equipment
    "affinity": {"artifacts"},
    "modular": {"artifacts", "counters"},
    "sunburst": {"artifacts", "counters", "lands"},
    "fortify": {"artifacts", "lands"},
    "living weapon": {"artifacts", "tokens", "voltron"},
    "improvise": {"artifacts", "spellslinger"},
    "crew": {"artifacts", "voltron"},
    "fabricate": {"artifacts", "tokens"},
    "reconfigure": {"artifacts", "voltron"},
    "prototype": {"artifacts"},
    "living metal": {"artifacts", "voltron"},
    "more than meets the eye": {"artifacts", "voltron", "spellslinger"},
    "for mirrodin!": {"artifacts", "tokens", "voltron"},
    "craft": {"artifacts", "graveyard"},

    # Counters-focused mechanics
    "amplify": {"counters"},
    "graft": {"counters"},
    "sunburst": {"counters", "artifacts", "lands"},
    "level up": {"counters"},
    "evolve": {"counters"},
    "outlast": {"counters"},
    "mentor": {"counters", "voltron"},
    "riot": {"counters", "voltron"},
    "training": {"counters", "voltron"},
    "compleated": {"counters"},
    "backup": {"counters", "voltron"},
    "ravenous": {"counters"},
    "offspring": {"counters", "tokens"},

    # Lifegain / drain
    "lifelink": {"lifegain", "voltron"},
    "absorb": {"lifegain", "control"},
    "extort": {"lifegain", "control"},

    # Lands / land-based
    "landwalk": {"lands", "voltron"},
    "sunburst": {"lands", "artifacts", "counters"},
    "awaken": {"lands", "counters"},
    # (Landcycling is detected via text already in THEME_KEYWORDS)

    # Graveyard mechanics
    "dredge": {"graveyard"},
    "recover": {"graveyard"},
    "soulshift": {"graveyard"},
    "unearthed": set(),  # guard; real key is "unearth"
    "unearth": {"graveyard"},
    "persist": {"graveyard", "sacrifice", "counters"},
    "wither": {"control", "voltron"},
    "devour": {"sacrifice", "counters", "tokens"},
    "undying": {"graveyard", "counters"},
    "scavenge": {"graveyard", "counters"},
    "soulshift": {"graveyard"},
    "escape": {"graveyard", "spellslinger"},
    "embalm": {"graveyard", "tokens"},
    "eternalize": {"graveyard", "tokens"},
    "disturb": {"graveyard", "tokens"},
    "aftermath": {"graveyard", "spellslinger"},
    "escape": {"graveyard", "spellslinger"},
    "exploit": {"sacrifice", "graveyard"},
    "casualty": {"sacrifice", "spellslinger"},
    "bargain": {"sacrifice", "spellslinger"},
    "craft": {"graveyard", "artifacts"},
    "impending": {"control", "spellslinger"},

    # Sacrifice / aristocrats-adjacent
    "exploit": {"sacrifice", "graveyard"},
    "devour": {"sacrifice", "tokens", "counters"},
    "champion": {"sacrifice", "graveyard"},
    "aftermath": {"graveyard", "spellslinger"},
    "casualty": {"sacrifice", "spellslinger"},
    "bargain": {"sacrifice", "spellslinger"},
    "offering": {"sacrifice", "spellslinger"},
    "afterlife": {"tokens", "graveyard", "sacrifice"},

    # Tokens / go-wide / bodies
    "myriad": {"tokens"},
    "fabricate": {"tokens", "artifacts"},
    "devour": {"tokens", "sacrifice", "counters"},
    "battle cry": {"tokens", "voltron"},
    "living weapon": {"tokens", "artifacts", "voltron"},
    "embalm": {"tokens", "graveyard"},
    "eternalize": {"tokens", "graveyard"},
    "encore": {"tokens", "graveyard"},
    "afterlife": {"tokens", "graveyard", "sacrifice"},
    "squad": {"tokens"},
    "saddle": {"tokens", "voltron"},
    "gift": {"tokens", "lifegain"},  # set-specific, but fits “gifts with bodies”
    "offspring": {"tokens", "counters"},

    # Voltron / tall strategy
    "double strike": {"voltron"},
    "first strike": {"voltron"},
    "haste": {"voltron"},
    "flying": {"voltron", "control"},
    "trample": {"voltron", "counters"},
    "vigilance": {"voltron", "control"},
    "intimidate": {"voltron"},
    "bushido": {"voltron"},
    "bloodthirst": {"counters", "voltron"},
    "exalted": {"voltron"},
    "annihilator": {"voltron", "control"},
    "umbra armor": {"voltron"},
    "infect": {"voltron", "counters"},
    "battle cry": {"voltron", "tokens"},
    "soulbond": {"voltron"},
    "bestow": {"voltron"},
    "tribute": {"voltron", "counters"},
    "dethrone": {"voltron"},
    "prowess": {"spellslinger"},  # spellslinger wincon, but often on creatures
    "dash": {"voltron"},
    "menace": {"voltron"},
    "renown": {"voltron"},
    "melee": {"voltron"},
    "crew": {"voltron", "artifacts"},
    "partner": {"voltron", "control"},
    "mentor": {"voltron", "counters"},
    "riot": {"voltron", "counters"},
    "boast": {"voltron"},
    "daybound": {"control"},
    "nightbound": {"control"},
    "training": {"voltron", "counters"},
    "reconfigure": {"voltron", "artifacts"},
    "blitz": {"voltron", "graveyard"},
    "enlist": {"voltron"},
    "living metal": {"voltron", "artifacts"},
    "more than meets the eye": {"voltron", "artifacts", "spellslinger"},
    "for mirrodin!": {"voltron", "artifacts", "tokens"},
    "toxic": {"voltron", "control"},
    "backup": {"voltron", "counters"},
    "disguise": {"voltron", "control"},

    # Control / prison / disruption
    "deathtouch": {"control", "voltron"},
    "defender": {"control"},
    "flash": {"control", "spellslinger"},
    "flying": {"control", "voltron"},
    "hexproof": {"control", "voltron"},
    "indestructible": {"control", "voltron"},
    "ward": {"control", "voltron"},
    "cumulative upkeep": {"control"},
    "phasing": {"control"},
    "storm": {"control", "spellslinger"},
    "split second": {"control"},
    "suspend": {"control", "spellslinger"},
    "vanishing": {"control"},
    "echo": {"control"},
    "ninjutsu": {"control", "voltron"},
    "epic": {"control", "spellslinger"},
    "haunt": {"control", "graveyard"},
    "shadow": {"voltron"},
    "ascend": {"control"},
    "companion": {"control"},
    "afflict": {"control"},
    "hidden agenda": {"control"},
    "daybound": {"control"},
    "nightbound": {"control"},
    "space sculptor": {"control"},
    "visit": {"control"},
    "solved": {"control", "spellslinger"},
    "impending": {"control", "spellslinger"},

    # Misc / oddballs that still get *some* theme
    "horsemanship": {"voltron"},
    "fading": {"control"},
    "fear": {"voltron"},
    "morph": {"control"},
    "provoke": {"voltron"},
    "sunburst": {"counters", "artifacts", "lands"},
    "bushido": {"voltron"},
    "soulshift": {"graveyard"},
    "offering": {"sacrifice", "spellslinger"},
    "ninjutsu": {"voltron", "control"},
    "epic": {"spellslinger", "control"},
    "bloodthirst": {"counters", "voltron"},
    "haunt": {"graveyard", "control"},
    "transmute": {"spellslinger", "control"},
    "absorb": {"lifegain", "control"},
    "poisonous": {"voltron", "control"},
    "transfigure": {"spellslinger", "graveyard"},
    "changeling": {"control"},  # really tribal glue; treat as generic
    "evoke": {"graveyard", "spellslinger"},
    "hideaway": {"control"},
    "prowl": {"voltron"},
    "reinforce": {"counters"},
    "devour": {"sacrifice", "tokens", "counters"},
    "exalted": {"voltron"},
    "annihilator": {"voltron", "control"},
    "soulbond": {"voltron"},
    "mutate": {"counters", "graveyard"},
    "encore": {"tokens", "graveyard"},
    "skulk": {"voltron"},
    "emerge": {"graveyard", "artifacts"},
    "partner": {"voltron", "control"},
    "ascend": {"control"},
    "escape": {"graveyard", "spellslinger"},
    "companion": {"control"},
    "mutate": {"counters", "graveyard"},
    "boast": {"voltron"},
    "decayed": {"tokens", "graveyard"},
    "cleave": {"spellslinger"},
    "read ahead": {"control"},
    "squad": {"tokens"},
    "space sculptor": {"control"},
    "visit": {"control"},
    "saddle": {"tokens", "voltron"},
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

def get_commander_themes(commander_row: pd.Series) -> set[str]:
    return detect_card_themes(commander_row)

def card_matches_themes(card_row: pd.Series, themes: set[str]) -> bool:
    if not themes:
        return False
    card_theme_set = detect_card_themes(card_row)
    return bool(card_theme_set & themes)

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
    profile = build_commander_profile(commander_row)
    themes = commander_row.get("themes", set()) or set()

    # 1) Get legal pool for this commander
    pool = get_legal_pool(df, commander_row)
        # Ensure roles are present (in case you didn't precompute globally)
    if "roles" not in pool.columns:
        pool = pool.copy()
        pool["roles"] = pool.apply(get_card_roles, axis=1)

    # 2) Split lands / nonlands
    lands = pool[pool.apply(is_land, axis=1)].copy()
    nonlands = pool[~pool.apply(is_land, axis=1)].copy()

    # 3) Compute commander-specific synergy scores for nonlands
    nonlands = nonlands.copy()
    nonlands["synergy_score"] = nonlands.apply(
        lambda r: commander_synergy_score(profile, r),
        axis=1
    )

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
                lambda r: commander_synergy_score(profile, r),
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
    
    profile = build_commander_profile(commander_row)
    profile["curve_pref"] = deck_speed

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

def get_card_roles(row: pd.Series) -> set[str]:
    """
    Assign behavioral roles to a card based on its oracle_text and type_line.
    A card can have many roles. These roles are used later for synergy
    scoring (commander-specific) and for deck construction.
    """
    raw_text      = row.get("oracle_text", "")
    raw_type_line = row.get("type_line", "")
    raw_name      = row.get("name", "")
    raw_mana_cost = row.get("mana_cost", "")
    raw_colors    = row.get("color_identity", [])
    raw_cmc       = row.get("cmc", 0)

    text      = str(raw_text or "").lower()
    type_line = str(raw_type_line or "").lower()
    name      = str(raw_name or "").lower()
    mana_cost = str(raw_mana_cost or "").lower()

    # color_identity is usually a list like ["U","R"]; make sure it is
    if isinstance(raw_colors, list):
        colors = raw_colors
    elif pd.isna(raw_colors):
        colors = []
    else:
        # fallback if something weird comes through
        try:
            colors = list(raw_colors)
        except TypeError:
            colors = []

    # cmc as a number
    try:
        cmc = float(raw_cmc) if not pd.isna(raw_cmc) else 0.0
    except (TypeError, ValueError):
        cmc = 0.0

    roles: set[str] = set()

    # --- Basic type roles (lightweight, mostly for convenience) ---
    if "creature" in type_line:
        roles.add("creature")
    if "artifact" in type_line:
        roles.add("artifact")
    if "enchantment" in type_line:
        roles.add("enchantment")
    if "planeswalker" in type_line:
        roles.add("planeswalker")
    if "instant" in type_line:
        roles.add("instant")
    if "sorcery" in type_line:
        roles.add("sorcery")
    if "land" in type_line:
        roles.add("land")
    if "legendary" in type_line:
        roles.add("legendary")

    # --- Spells & cheap spells ---
    if "instant" in type_line or "sorcery" in type_line:
        roles.add("spell")
        if cmc <= 2:
            roles.add("cheap_spell")

    # --- Mana roles ---
    # Mana dork: creature with a mana ability
    if "creature" in type_line and "add {" in text:
        roles.add("mana_dork")

    # Mana rock: artifact with a mana ability
    if "artifact" in type_line and "add {" in text:
        roles.add("mana_rock")

    # Land ramp: search for lands / put lands onto battlefield
    if (
        "search your library for a land card" in text
        or "search your library for a basic land card" in text
        or "search your library for up to one basic land" in text
        or "put a land card from your hand onto the battlefield" in text
        or "put a land card from your graveyard onto the battlefield" in text
    ):
        roles.add("land_ramp")

    # Ritual / mana burst: spell that adds mana right now
    if ("instant" in type_line or "sorcery" in type_line) and "add {" in text:
        # exclude obvious "tap: add" style text that got copied into spells
        if "until end of turn" in text or "this mana" in text or "only to cast" in text:
            roles.add("ritual")
            roles.add("mana_burst")

    # Treasure engines / bursts
    if "treasure token" in text:
        if "whenever" in text or "at the beginning" in text or "{t}:" in text:
            roles.add("treasure_engine")
        else:
            roles.add("treasure_burst")

    # --- Token & aristocrats roles ---
    creates_token = ("create " in text and " token" in text)

    if creates_token:
        if "whenever" in text or "at the beginning" in text or "{t}:" in text or ":" in text and "create" in text.split(":", 1)[1]:
            roles.add("token_engine")
        else:
            roles.add("token_maker_once")

    # Token payoff: cares about tokens or creatures entering
    if (
        "whenever a token" in text
        or "whenever one or more tokens" in text
        or "for each token you control" in text
        or "for each creature token" in text
    ):
        roles.add("token_payoff")

    # Dies triggers / death payoff
    if (
        "whenever a creature dies" in text
        or "whenever another creature dies" in text
        or "whenever a creature you control dies" in text
        or "whenever another creature you control dies" in text
    ):
        roles.add("dies_trigger")
        roles.add("death_payoff")

    # Sac outlets – look for "Sacrifice X:" style costs or repeated sac usage
    if "sacrifice a creature" in text or "sacrifice another creature" in text:
        if ":" in text.split("sacrifice a creature", 1)[-1][:40] or ":" in text.split("sacrifice another creature", 1)[-1][:40]:
            roles.add("sac_outlet_creature")
        else:
            # still a sac outlet, but often sorcery-speed or one-shot
            roles.add("sac_outlet_creature")

    if "sacrifice a permanent" in text or "sacrifice an artifact" in text or "sacrifice an enchantment" in text or "sacrifice a land" in text:
        roles.add("sac_outlet_permanent")

    # Death/life drain e.g. Blood Artist
    if (
        ("whenever a creature dies" in text or "whenever another creature dies" in text)
        and ("each opponent loses" in text or "each opponent loses 1 life" in text)
    ):
        roles.add("death_payoff")

    # --- Card draw & velocity roles ---
    if "draw a card" in text or "draw two cards" in text or "draw three cards" in text:
        # Cheap cantrips
        if cmc <= 2 and ("instant" in type_line or "sorcery" in type_line):
            roles.add("cantrip")

        # Repeatable draw engine: uses "whenever" or "at the beginning"
        if ("whenever" in text or "at the beginning of" in text) and "draw" in text:
            roles.add("card_draw_engine")
        else:
            roles.add("card_draw_burst")

    # Looting / rummaging
    if "draw a card, then discard" in text or "draw two cards, then discard" in text:
        roles.add("loot")
    if "discard a card, then draw" in text or "discard two cards, then draw" in text:
        roles.add("rummage")

    # Draw on token / creature events (feeding token/aristocrats plans)
    if "whenever a token" in text and "draw" in text:
        roles.add("card_draw_engine")
        roles.add("token_payoff")
    if "whenever a creature you control dies" in text and "draw" in text:
        roles.add("card_draw_engine")
        roles.add("death_payoff")

    # --- Removal & control roles ---
    # Board wipes – creatures
    if (
        "destroy all creatures" in text
        or "exile all creatures" in text
        or ("each creature gets" in text and "until end of turn" in text)
        or "each creature gets -"
    ):
        roles.add("board_wipe_creatures")

    # Board wipes – noncreatures / mixed
    if (
        "destroy all artifacts" in text
        or "destroy all enchantments" in text
        or "destroy all artifacts and enchantments" in text
        or "exile all nonland permanents" in text
        or "destroy all nonland permanents" in text
    ):
        roles.add("board_wipe_noncreature")

    # Spot removal
    if "destroy target" in text or "exile target" in text:
        if "destroy target creature" in text or "exile target creature" in text:
            roles.add("spot_removal_creature")
        elif "destroy target planeswalker" in text or "exile target planeswalker" in text:
            roles.add("spot_removal_noncreature")
        elif "destroy target artifact" in text or "destroy target enchantment" in text or "destroy target artifact or enchantment" in text:
            roles.add("spot_removal_noncreature")
        elif "destroy target permanent" in text or "exile target permanent" in text:
            roles.add("spot_removal_any")

    # Counterspells
    if "counter target spell" in text or "counter target noncreature spell" in text or "counter target creature spell" in text:
        roles.add("counterspell")

    # Edicts
    if "each opponent sacrifices a creature" in text or "target opponent sacrifices a creature" in text:
        roles.add("edict")

    # Tax / stax
    if (
        "spells your opponents cast cost" in text
        or "spells your opponent casts cost" in text
        or "players can't cast more than one spell each turn" in text
        or "players can’t cast more than one spell each turn" in text
        or "players can't draw more than one card each turn" in text
        or "players can’t draw more than one card each turn" in text
    ):
        roles.add("tax_piece")

    if (
        "doesn't untap during its controller's untap step" in text
        or "doesn’t untap during its controller’s untap step" in text
        or "tapped creatures don't untap" in text
        or "tapped creatures don’t untap" in text
    ):
        roles.add("tap_freeze")

    # --- Graveyard & recursion roles ---
    if "mill a card" in text or "mills a card" in text or "put the top " in text and "of your library into your graveyard" in text:
        roles.add("self_mill")

    if "return target creature card from your graveyard to the battlefield" in text:
        roles.add("yard_recur_creature")
    if "return target creature card from your graveyard to your hand" in text:
        roles.add("yard_recur_creature")
    if "return target card from your graveyard to your hand" in text or "return target permanent card from your graveyard to your hand" in text:
        roles.add("yard_recur_any")
    if "return target permanent card from your graveyard to the battlefield" in text:
        roles.add("yard_recur_any")

    if "exile target card from a graveyard" in text or "exile all cards from target player's graveyard" in text or "exile all cards from target players' graveyards" in text:
        roles.add("yard_hate")

    # Escape / flashback / unearth support pieces
    if "escape" in text:
        roles.add("escape_piece")
    if "flashback" in text:
        roles.add("flashback_piece")
    if "unearth" in text:
        roles.add("unearth_piece")

    # --- Spellslinger / value-engine roles ---
    if "copy target instant or sorcery" in text or "copy that spell" in text:
        roles.add("spell_copy")

    if "instants and sorceries you cast cost" in text or "spells you cast cost" in text:
        roles.add("spell_discount")

    if (
        "whenever you cast an instant or sorcery" in text
        or "whenever you cast a noncreature spell" in text
        or "whenever you cast an instant" in text
        or "whenever you cast a sorcery" in text
    ):
        roles.add("spell_payoff")

    if "{x}" in mana_cost or "{x}" in text:
        roles.add("x_spell")

    if "storm" in text:
        roles.add("storm_piece")

    # --- Protection & combat roles ---
    if (
        "creatures you control have hexproof" in text
        or "creatures you control have indestructible" in text
        or "creatures you control gain hexproof" in text
        or "creatures you control gain indestructible" in text
    ):
        roles.add("protects_creatures")

    if (
        "commander you control" in text
        or "legendary creature you control gains hexproof" in text
        or "legendary creature you control gains indestructible" in text
    ):
        roles.add("protects_commander")

    if (
        "creatures you control get +" in text
        and "until end of turn" in text
    ):
        roles.add("combat_pump")

    if "there is an additional combat phase" in text or "after this phase, there is an additional combat phase" in text:
        roles.add("extra_combat")

    # Evasion granter
    if (
        "creatures you control have flying" in text
        or "creatures you control gain flying" in text
        or "target creature can't be blocked" in text
        or "target creature can’t be blocked" in text
    ):
        roles.add("evasion_granter")

    # --- Tutors & selection ---
    if "search your library" in text and "for a land card" not in text and "for a basic land" not in text:
        roles.add("tutor_any")
        if "for a creature card" in text:
            roles.add("tutor_creature")
        if "for an artifact card" in text:
            roles.add("tutor_artifact")
        if "for an enchantment card" in text:
            roles.add("tutor_enchantment")
        if "for a planeswalker card" in text:
            roles.add("tutor_planeswalker")

    return roles

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
