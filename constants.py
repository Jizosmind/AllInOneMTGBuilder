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
        "players can’t gain life",
        "your opponents can't gain life",
        "your opponents can’t gain life",
        "players can't search libraries",
        "players can’t search libraries",
        "your opponents can't search libraries",
        "your opponents can’t search libraries",
        "each opponent sacrifices a creature",
        "each opponent sacrifices a permanent",
        "each player sacrifices a creature",
        "each player sacrifices a permanent",
        "skip your draw step",
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
    "awaken": {"lands", "counters"},
    "landcycling": {"lands", "graveyard"},
    "basic landcycling": {"lands", "graveyard"},
    "domain": {"lands", "control"},
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
    "surveil": {"graveyard", "control"},
    "connive": {"graveyard", "counters"},  
    "descend": {"graveyard"},              
    "craft": {"graveyard", "artifacts"}, 

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
    "convoke": {"tokens", "spellslinger"},
    "battalion": {"tokens", "voltron"},
    "pack tactics": {"tokens", "voltron"},
    "celebrate": {"tokens"},

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

KEYWORD_GLOSSARY: dict[str, dict[str, str]] = {
    # Symbols / costs
    "tap": {
        "kind": "symbol",          # the {T} symbol
    },
    "x": {
        "kind": "variable_cost",   # X in mana/activation costs
    },

    # Cost / cast structure
    "additional cost": {
        "kind": "rules_term",
    },
    "cost": {
        "kind": "rules_term",
    },
    "mana": {
        "kind": "rules_term",
    },
    "mana ability": {
        "kind": "rules_term",
    },
    "mana value": {
        "kind": "rules_term",
    },
    "mulligan": {
        "kind": "rules_term",
    },

    # Card / object identity
    "aura": {
        "kind": "subtype",
    },
    "equipment": {
        "kind": "subtype",
    },
    "planeswalker": {
        "kind": "card_type",
    },
    "legendary": {
        "kind": "supertype",
    },
    "basic land": {
        "kind": "supertype_type",
    },
    "permanent": {
        "kind": "rules_term",
    },
    "token": {
        "kind": "rules_term",
    },
    "spell": {
        "kind": "rules_term",
    },
    "source": {
        "kind": "rules_term",
    },

    # Color / colorless
    "color": {
        "kind": "rules_term",
    },
    "colorless": {
        "kind": "rules_term",
    },

    # Zones & movement
    "enters the battlefield": {
        "kind": "rules_term",
    },
    "leaves the battlefield": {
        "kind": "rules_term",
    },
    "put onto the battlefield": {
        "kind": "rules_term",
    },
    "exile": {
        "kind": "zone_action",
    },
    "shuffle": {
        "kind": "keyword_action",
    },
    "scry": {
        "kind": "keyword_action",
    },
    "sacrifice": {
        "kind": "keyword_action",
    },
    "discard": {
        "kind": "keyword_action",
    },
    "counter a spell or ability": {
        "kind": "rules_term",
    },
    "counter on a permanent": {
        "kind": "rules_term",
    },
    "destroy": {
        "kind": "zone_action",
    },

    # Damage / combat / life
    "damage": {
        "kind": "rules_term",
    },
    "combat damage": {
        "kind": "rules_term",
    },
    "deathtouch": {
        "kind": "keyword_ability",
    },
    "double strike": {
        "kind": "keyword_ability",
    },
    "first strike": {
        "kind": "keyword_ability",
    },
    "trample": {
        "kind": "keyword_ability",
    },
    "flying": {
        "kind": "keyword_ability",
    },
    "reach": {
        "kind": "keyword_ability",
    },
    "menace": {
        "kind": "keyword_ability",
    },
    "vigilance": {
        "kind": "keyword_ability",
    },
    "lifelink": {
        "kind": "keyword_ability",
    },
    "haste": {
        "kind": "keyword_ability",
    },
    "goad": {
        "kind": "keyword_action",
    },

    # Protection / blocking / attacking constraints
    "defender": {
        "kind": "keyword_ability",
    },
    "hexproof": {
        "kind": "keyword_ability",
    },
    "indestructible": {
        "kind": "keyword_ability",
    },

    # Timing & recursion
    "flash": {
        "kind": "keyword_ability",
    },
    "flashback": {
        "kind": "keyword_ability",
    },

    # Control & ownership & players
    "control": {
        "kind": "rules_term",
    },
    "controller": {
        "kind": "rules_term",
    },
    "owner": {
        "kind": "rules_term",
    },
    "player": {
        "kind": "rules_term",
    },
    "opponent": {
        "kind": "rules_term",
    },
    "you": {
        "kind": "rules_term",
    },
}