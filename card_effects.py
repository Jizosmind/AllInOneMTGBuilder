from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple, Dict
import pandas as pd
import numpy as np
import re
from enum import Enum, auto

from card_atoms import (
    Atom,
    ZoneMove, ResourceDelta, StepChange, StateDelta,
    tap_atom, untap_atom,
)

from mtg_vocab import Source, Step, PermanentStatus, Zone, Cause, ObjKind

# External constants (provided elsewhere in your project)
from constants import THEME_KEYWORDS, KEYWORD_THEME_OVERRIDES, KEYWORD_GLOSSARY


# ─────────────────────────────────────────────────────────
# Data Modeling Enum, Classes and Helpers
# ─────────────────────────────────────────────────────────

class EventKind(Enum):
    CAST = auto()
    DRAW   = auto()   # draw cards
    CREATE = auto()   # create tokens/permanents
    GAIN   = auto()   # gain life, gain resource
    LOSE   = auto()   # lose life / mana / counters
    ADD    = auto()   # add counters / mana
    DEAL   = auto()   # deal damage
    SACRIFICE = auto()
    ENTERS = auto()   # ETB / re-enter battlefield
    DIES   = auto()   # dies / goes to GY
    DESTROY = auto()
    EXILE = auto()
    BOUNCE = auto()
    COUNTER = auto()
    TUTOR = auto()
    REANIMATE = auto()
    STEP = auto()
    STATE = auto()

class Resource(Enum):
    NONE = auto()
    CARD      = auto()
    TOKEN     = auto()
    LIFE      = auto()
    MANA      = auto()
    COUNTER   = auto()
    DAMAGE    = auto()
    PERMANENT = auto()

class Scope(Enum):
    YOU            = auto()
    OPPONENT       = auto()
    ANY_PLAYER     = auto()
    YOUR_PERMANENT = auto()
    ANY_PERMANENT  = auto()
    SELF = auto()

@dataclass
class ActionUnit:
    """
    Minimal grammatical unit extracted from an oracle clause.

    Example (Walking Ballista):

      'Remove a +1/+1 counter from Walking Ballista: It deals 1 damage to any target.'

      → ActionUnit(
            verb='deal',
            quantity=1,
            obj='damage',
            target='any target',
            kind='DEAL_DAMAGE',
            text_span='It deals 1 damage to any target.'
        )
    """
    verb: str
    quantity: Optional[int]
    obj: Optional[str]
    target: Optional[str]
    kind: Optional[str]
    text_span: str

@dataclass(frozen=True)
class EventTag:
    """
    Normalized event description used for synergy / combo analysis.
    """
    kind: EventKind
    resource: Resource
    scope: Scope
    step: Optional[Step] = None

    def short(self) -> str:
        step_str = self.step.name if self.step else "-"
        return f"{self.kind.name}:{self.resource.name}:{self.scope.name}:{step_str}"

@dataclass
class KeywordHit:
    """
    One occurrence of a rules keyword in a clause, plus a small window of context.

    Example:
      clause: 'Sacrifice another creature: Draw two cards.'
      keyword: 'sacrifice'
      left_words: ['']
      right_words: ['another', 'creature', ':']
    """
    keyword: str
    left_words: List[str]
    right_words: List[str]

    def context_str(self) -> str:
        left = " ".join(self.left_words)
        right = " ".join(self.right_words)
        return f"...{left} [{self.keyword}] {right}..."

# Convenience helper for EventTags
def ev(kind: EventKind, res: Resource, scope: Scope, step=None) -> EventTag:
    return EventTag(kind, res, scope, step=step)

@dataclass
class Effect:
    raw_text: str
    effect_type: str  # "triggered" | "activated" | "static" | "replacement"

    # CONDITION
    trigger_tags: Set[EventTag] = field(default_factory=set)
    cost_tags:    Set[EventTag] = field(default_factory=set)

    # RESULT
    result_tags:  Set[EventTag] = field(default_factory=set)

    #atoms
    trigger_atoms: List[Atom] = field(default_factory=list)
    cost_atoms: List[Atom] = field(default_factory=list) 
    result_atoms: List[Atom] = field(default_factory=list)

    # WHO / WHAT (string helpers)
    actor_tags:   Set[str] = field(default_factory=set)
    target_tags:  Set[str] = field(default_factory=set)

    # TIMING (ability-level)
    timing: Optional[str]  = None

    # Optional helpers
    condition_description: Optional[str] = None
    modes: List[dict] = field(default_factory=list)

    # Raw pieces of the parsed clause (debug)
    trigger_text: Optional[str] = None
    cost_text:    Optional[str] = None
    result_text:  Optional[str] = None

    # Parsed micro-structures
    trigger_actions:  List[ActionUnit] = field(default_factory=list)
    cost_actions:     List[ActionUnit] = field(default_factory=list)
    result_actions:   List[ActionUnit] = field(default_factory=list)

    # Keyword + context hits from KEYWORD_GLOSSARY
    keyword_hits: List[KeywordHit] = field(default_factory=list)

    def infer_theme_tags(self) -> Set[str]:
        tags: Set[str] = set()
        text = self.raw_text.lower()

        for theme, patterns in THEME_KEYWORDS.items():
            if any(pat in text for pat in patterns):
                tags.add(theme)

        return tags

@dataclass
class Card:
    # Basic identity
    name: str
    mana_value: float
    mana_cost: str
    colors: List[str]

    # Type / permanence
    types: List[str]
    subtypes: List[str]
    is_permanent: bool
    cast_timing: str  # "instant_speed" | "sorcery_speed" | "special"

    # Scryfall text + keywords
    oracle_text: str
    keywords: List[str]

    # Stats
    power: Optional[int] = None
    toughness: Optional[int] = None
    loyalty: Optional[int] = None

    # Parsed effects
    effects: List[Effect] = field(default_factory=list)

    # Convenience aggregations for synergy / flattening
    def all_trigger_tags(self) -> Set[EventTag]:
        return {t for e in self.effects for t in e.trigger_tags}

    def all_result_tags(self) -> Set[EventTag]:
        return {t for e in self.effects for t in e.result_tags}

    def all_cost_tags(self) -> Set[EventTag]:
        return {t for e in self.effects for t in e.cost_tags}

    def all_actor_tags(self) -> Set[str]:
        return {t for e in self.effects for t in e.actor_tags}

    def all_target_tags(self) -> Set[str]:
        return {t for e in self.effects for t in e.target_tags}

    def infer_theme_tags(self) -> Set[str]:
        tags: Set[str] = set()
        text = (self.oracle_text or "").lower()

        for theme, patterns in THEME_KEYWORDS.items():
            if any(pat in text for pat in patterns):
                tags.add(theme)

        for kw in self.keywords or []:
            themes = KEYWORD_THEME_OVERRIDES.get(kw.lower())
            if themes:
                tags.update(themes)

        return tags


# ─────────────────────────────────────────────────────────
# Low-level action grammar (verb + quantity + object + target)
# ─────────────────────────────────────────────────────────


# Lexicon for the micro-grammar
VERB_LEXICON: Set[str] = {
    "draw", "create", "gain", "lose", "deal", "destroy", "exile",
    "sacrifice", "return", "untap", "tap", "search", "reveal",
    "put", "mill", "copy", "add", "fight", "cast", "play",
    "scry", "proliferate", "remove", "counter",
}

QUANTITY_WORDS: Set[str] = {
    "a", "an", "one", "two", "three", "four", "five", "six",
    "x",
}

OBJECT_WORDS: Set[str] = {
    "damage", "card", "cards", "token", "tokens", "life",
    "counter", "counters", "land", "lands", "creature", "creatures",
    "permanent", "permanents", "spell", "spells", "mana", "library",
}

TARGET_MARKERS: Set[str] = {
    "target", "any", "each", "that", "those", "it", "this",
}

# Canonical action labels used when mapping ActionUnits to EventTags
ACTION_LIBRARY: Dict[Tuple[str, str], str] = {
    ("draw", "card"):          "DRAW_CARD",
    ("draw", "cards"):         "DRAW_CARD",

    ("create", "token"):       "CREATE_TOKEN",
    ("create", "tokens"):      "CREATE_TOKEN",

    ("deal", "damage"):        "DEAL_DAMAGE",

    ("gain", "life"):          "GAIN_LIFE",
    ("lose", "life"):          "LOSE_LIFE",

    ("add", "mana"):           "ADD_MANA",

    ("put", "counter"):        "ADD_COUNTER",
    ("put", "counters"):       "ADD_COUNTER",

    ("remove", "counter"):     "REMOVE_COUNTER",
    ("remove", "counters"):    "REMOVE_COUNTER",

    ("sacrifice", "creature"): "SACRIFICE_CREATURE",
    ("sacrifice", "permanent"):"SACRIFICE_PERMANENT",

    ("destroy", "creature"):   "DESTROY_CREATURE",
    ("destroy", "permanent"):  "DESTROY_PERMANENT",

    ("exile", "creature"):     "EXILE_CREATURE",
    ("exile", "permanent"):    "EXILE_PERMANENT",

    ("return", "creature"):    "RETURN_CREATURE",
    ("return", "card"):        "RETURN_CARD",

    ("mill", "card"):          "MILL_CARD",
    ("mill", "cards"):         "MILL_CARD",

    ("search", "library"):     "SEARCH_LIBRARY",

    ("cast", "spell"):         "CAST_SPELL",
}


# ─────────────────────────────────────────────────────────
# Effect parsing → EventTag sets
# ─────────────────────────────────────────────────────────

TRIGGER_PREFIX_RE = re.compile(
    r"^(when|whenever|at the beginning of|at the start of|at )",
    re.IGNORECASE,
)


def _split_abilities(oracle_text: str) -> List[str]:
    """
    Split oracle text into ability-like chunks.

    - Newlines as primary separators (Scryfall convention)
    - For static text blocks, split on '. '
    """
    if not oracle_text:
        return []

    lines = [ln.strip() for ln in oracle_text.split("\n") if ln.strip()]
    abilities: List[str] = []

    for line in lines:
        # Activated / triggered → keep whole line
        if ":" in line or TRIGGER_PREFIX_RE.match(line):
            abilities.append(line.strip())
        else:
            # Static / spell text → split on sentences
            parts = re.split(r"\.\s+", line)
            for p in parts:
                p = p.strip()
                if p:
                    abilities.append(p)

    return abilities


def _split_trigger_clause(text: str) -> Tuple[Optional[str], str]:
    """
    'Whenever another creature you control dies, draw a card.'
      -> ('Whenever another creature you control dies', 'draw a card.')
    """
    m = TRIGGER_PREFIX_RE.match(text)
    if not m:
        return None, text

    rest = text[m.end():].strip()
    if "," in rest:
        trigger_part, result_part = rest.split(",", 1)
        trigger_text = f"{m.group(0).strip()} {trigger_part.strip()}"
        return trigger_text.strip(), result_part.strip()
    else:
        # No comma – treat the entire text as a trigger-ish thing
        return text.strip(), ""


def _split_cost_clause(text: str) -> Tuple[Optional[str], str]:
    """
    '2W, T, Sacrifice a creature: Draw two cards.'
      -> ('2W, T, Sacrifice a creature', 'Draw two cards.')
    """
    if ":" not in text:
        return None, text
    cost_part, result_part = text.split(":", 1)
    return cost_part.strip(), result_part.strip()


def _guess_effect_type(clause: str) -> str:
    """
    Classify an ability into triggered / activated / static / replacement.
    """
    cl = clause.lower()

    # Replacement effects: "If X would ..., instead ..."
    if cl.startswith("if ") and " would " in cl and " instead" in cl:
        return "replacement"

    # Triggered
    if cl.startswith("whenever ") or cl.startswith("when ") or cl.startswith("at the beginning"):
        return "triggered"

    # Activated: anything of the form "[cost stuff]: [effect]"
    if ":" in clause:
        left = clause.split(":", 1)[0].lower()
        if (
            "{" in left
            or "sacrifice" in left
            or "discard" in left
            or "exile" in left
            or "tap" in left
            or "untap" in left
            or "pay" in left
        ):
            return "activated"

    return "static"


def _simple_tokens(clause: str) -> List[str]:
    """
    Very simple whitespace/punctuation tokenizer suited to Oracle text.
    """
    clause = clause.replace(",", " , ").replace(":", " : ").replace(".", " . ")
    return [t for t in clause.split() if t]


def _tokenize_with_spans(text: str) -> List[Tuple[str, int, int]]:
    """
    Tokenize text into (token, start_index, end_index) tuples.
    """
    tokens: List[Tuple[str, int, int]] = []
    for m in WORD_TOKEN_RE.finditer(text):
        tokens.append((m.group(0), m.start(), m.end()))
    return tokens


def _extract_keyword_hits(clause: str) -> List[KeywordHit]:
    """
    For a clause, find every KEYWORD_GLOSSARY term and capture a small
    context window around it. This is for later analysis or debugging,
    not directly used for EventTags.
    """
    if not clause:
        return []

    lower = clause.lower()
    tokens = _tokenize_with_spans(clause)

    hits: List[KeywordHit] = []
    seen: Set[Tuple[str, int, int]] = set()

    # Map char index → token index
    index_to_token: Dict[int, int] = {}
    for i, (_, start, end) in enumerate(tokens):
        for pos in range(start, end):
            index_to_token[pos] = i

    for kw in KEYWORD_GLOSSARY.keys():
        kw_l = kw.lower()
        pattern = re.compile(r"\b" + re.escape(kw_l) + r"\b")
        for m in pattern.finditer(lower):
            start, end = m.start(), m.end()
            key = (kw_l, start, end)
            if key in seen:
                continue
            seen.add(key)

            token_idx = index_to_token.get(start)
            if token_idx is None:
                continue

            left_start = max(0, token_idx - 2)
            right_end = min(len(tokens), token_idx + 1 + 3)

            left_words  = [tokens[i][0] for i in range(left_start, token_idx)]
            right_words = [tokens[i][0] for i in range(token_idx + 1, right_end)]

            hits.append(KeywordHit(
                keyword=kw,
                left_words=left_words,
                right_words=right_words,
            ))

    return hits


WORD_TOKEN_RE = re.compile(r"\w+|\S", re.UNICODE)
_MTG_SYMBOL_RE = re.compile(r"\{([^}]+)\}")

def _mana_gain_from_add_clause(text: str) -> tuple[int, str] | None:
    """
    Best-effort mana parsing for results like:
      - "Add {G}{G}."
      - "Add {G} or {U}." (choice)

    Returns (max_mana_produced, subtype_str) or None if no {..} symbols are present.
    """
    if not text:
        return None

    lower = text.lower()
    if "add" not in lower or "{" not in text:
        return None

    # Split on " or " to detect choice clauses
    parts = re.split(r"\s+or\s+", text, flags=re.IGNORECASE)

    option_amts: list[int] = []
    option_subs: list[str] = []

    for part in parts:
        syms = _mana_symbols(part)
        mana_syms = [s for s in syms if s.upper() not in ("T", "Q")]
        if not mana_syms:
            continue
        option_amts.append(_mana_cost_from_symbols(mana_syms))
        option_subs.append("".join(mana_syms))

    if not option_amts:
        return None

    # Conservative: treat "or" as "choose the best option"
    return max(option_amts), "|".join(option_subs)


def _infer_actor_tags(cl: str) -> Set[str]:
    actor_tags: Set[str] = set()

    if cl.startswith("you ") or " you " in cl or " your " in cl:
        actor_tags.add("YOU")
    if "each opponent" in cl:
        actor_tags.add("EACH_OPPONENT")
    if "each player" in cl:
        actor_tags.add("EACH_PLAYER")
    if "target opponent" in cl or "an opponent" in cl:
        actor_tags.add("OPPONENT")

    return actor_tags


def _infer_target_tags(cl: str) -> Set[str]:
    target_tags: Set[str] = set()

    if "another target creature you control" in cl:
        target_tags.add("ANOTHER_CREATURE_YOU_CONTROL")
    elif "creature you control" in cl:
        target_tags.add("CREATURE_YOU_CONTROL")

    if "token you control" in cl or "tokens you control" in cl:
        target_tags.add("TOKEN_YOU_CONTROL")

    if "target creature or enchantment you control" in cl:
        target_tags.add("CREATURE_OR_ENCHANTMENT_YOU_CONTROL")

    if "any target" in cl:
        target_tags.add("ANY_TARGET")
    elif "target creature" in cl:
        target_tags.add("ANY_CREATURE")

    if "target player" in cl:
        target_tags.add("ANY_PLAYER")

    return target_tags


def _scope_for_you_default(cl: str) -> Scope:
    if "under your control" in cl or "you control" in cl or "your " in cl:
        return Scope.YOUR_PERMANENT
    return Scope.YOU


def _parse_result_atoms(result_text: str, card_name: Optional[str] = None) -> list[Atom]:
    atoms: list[Atom] = []
    cl = (result_text or "").lower()

    # Mana production: "Add {G}{G}" / "Add {G} or {U}"
    mg = _mana_gain_from_add_clause(result_text or "")
    if mg:
        mana_amt, subtype = mg
        atoms.append(ResourceDelta(
            resource="mana",
            delta=mana_amt,
            target="YOU",
            subtype=subtype,
            cause=Cause.EFFECT,
            source=Source.CARD
        ))

    # Use ActionUnits for common results
    units = extract_action_units(result_text or "", card_name)

    for act in units:
        if act.kind == "DRAW_CARD":
            n = act.quantity or 1
            for _ in range(n):
                atoms.append(ZoneMove(Zone.LIBRARY, Zone.HAND, ObjKind.CARD, controller="YOU", cause=Cause.EFFECT, source=Source.CARD))

        elif act.kind == "CREATE_TOKEN":
            n = act.quantity or 1
            for _ in range(n):
                atoms.append(ZoneMove(Zone.COMMAND, Zone.BATTLEFIELD, ObjKind.TOKEN, controller="YOU", cause=Cause.EFFECT, source=Source.CARD))

        elif act.kind == "GAIN_LIFE":
            atoms.append(ResourceDelta(resource="life", delta=act.quantity or 1, target="YOU", cause=Cause.EFFECT, source=Source.CARD))

        elif act.kind == "LOSE_LIFE":
            tgt = "OPPONENT" if "opponent" in cl else "YOU"
            atoms.append(ResourceDelta(resource="life", delta=-(act.quantity or 1), target=tgt, cause=Cause.EFFECT, source=Source.CARD))

        elif act.kind == "DEAL_DAMAGE":
            atoms.append(ResourceDelta(resource="damage", delta=act.quantity or 1, target=act.target or "ANY", cause=Cause.EFFECT, source=Source.CARD))

        elif act.kind == "ADD_COUNTER":
            subtype = "+1/+1" if "+1/+1" in cl else None
            atoms.append(ResourceDelta(resource="counter", delta=act.quantity or 1, target="SELF", subtype=subtype, cause=Cause.EFFECT, source=Source.CARD))

        elif act.kind == "REMOVE_COUNTER":
            subtype = "+1/+1" if "+1/+1" in cl else None
            atoms.append(ResourceDelta(resource="counter", delta=-(act.quantity or 1), target="SELF", subtype=subtype, cause=Cause.EFFECT, source=Source.CARD))
        elif act.kind == "ADD_MANA":
            atoms.append(ResourceDelta(
                resource="mana",
                delta=act.quantity or 1,
                target="YOU",
                cause=Cause.EFFECT,
                source=Source.CARD
            ))

    # Tap/untap as EFFECTS
    if re.search(r"\buntap\b", cl):
        atoms.append(untap_atom(target="TARGET", cause=Cause.EFFECT, source=Source.CARD))
    if re.search(r"\btap\b", cl):
        atoms.append(tap_atom(target="TARGET", cause=Cause.EFFECT, source=Source.CARD))

    return atoms

# ─────────────────────────────────────────────────────────
# Micro-grammar: clause → ActionUnit list
# ─────────────────────────────────────────────────────────


def extract_action_units(clause: str, card_name: Optional[str] = None) -> List[ActionUnit]:
    """
    Extract a list of ActionUnit from a single clause.

    This is deliberately dumb-but-regular: it focuses on verbs, quantities,
    and nearby objects / targets, using ACTION_LIBRARY to label common kinds.
    """
    toks = _simple_tokens(clause)
    n = len(toks)
    i = 0
    results: List[ActionUnit] = []

    lc = clause.lower()
    name_l = (card_name or "").lower()
    
    WORD_TO_INT = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6
    }
    
    while i < n:
        raw = toks[i]
        tok = raw.lower()

        if tok not in VERB_LEXICON:
            i += 1
            continue

        verb = tok
        j = i + 1

        # 1) Quantity (simple integers or 'a', 'an', 'one', 'two', ..., 'x')
        quantity: Optional[int] = None
        if j < n:
            qtok = toks[j].lower()
            if qtok.isdigit():
                quantity = int(qtok)
                j += 1
            elif qtok in QUANTITY_WORDS:
                if qtok == "x":
                    quantity = None
                else:
                    quantity = WORD_TO_INT.get(qtok, 1)
                j += 1

        # 2) Object (damage, card, tokens, life, counter, etc.)
        obj: Optional[str] = None
        k = j
        while k < min(n, j + 5) and obj is None:
            otok = toks[k].lower()
            if otok in OBJECT_WORDS:
                obj = otok
            k += 1

        # Defaults if not explicitly named but strongly implied
        if obj is None:
            if verb == "deal":
                obj = "damage"
            elif verb in {"gain", "lose"} and "life" in lc:
                obj = "life"
            elif verb == "draw":
                obj = "card"

        # 3) Target
        target: Optional[str] = None

        # Self references (this card / this creature / it)
        if name_l and f"from {name_l}" in lc:
            target = "self"
        elif "from this creature" in lc or "from it" in lc or "this creature" in lc:
            target = "self"

        if target is None:
            t_idx = k
            while t_idx < n:
                t = toks[t_idx].lower()
                if t in TARGET_MARKERS:
                    window = " ".join(toks[t_idx:t_idx + 4]).lower()
                    if window.startswith("any target"):
                        target = "any target"
                    elif window.startswith("target creature"):
                        target = "target creature"
                    elif window.startswith("target opponent"):
                        target = "target opponent"
                    elif window.startswith("target player"):
                        target = "target player"
                    elif window.startswith("each opponent"):
                        target = "each opponent"
                    elif window.startswith("each player"):
                        target = "each player"
                    break
                t_idx += 1

        # 4) Canonical action kind
        kind: Optional[str] = None
        if obj is not None:
            key = (verb, obj)
            if key in ACTION_LIBRARY:
                kind = ACTION_LIBRARY[key]
            else:
                # Try singular form fallback ('cards' -> 'card')
                singular = obj[:-1] if obj.endswith("s") else obj
                key2 = (verb, singular)
                kind = ACTION_LIBRARY.get(key2)

        # If we have neither object nor kind, this is probably noise; skip
        if obj is None and kind is None:
            i += 1
            continue

        results.append(
            ActionUnit(
                verb=verb,
                quantity=quantity,
                obj=obj,
                target=target,
                kind=kind,
                text_span=clause,
            )
        )

        i += 1

    return results


def _subject_verb_object(
    text: str,
    subject: str,
    verb_root: str,
    obj_word: str,
) -> bool:
    """
    Wildcard matcher for patterns like:
      'you gain life'
      'target opponent loses 3 life'
      'each opponent is dealt 1 damage'
    - subject: 'you', 'opponent', 'each opponent', 'target opponent', etc.
    - verb_root: base family 'gain', 'lose', 'deal', 'draw', 'sacrifice'
    - obj_word: 'life', 'damage', 'card', 'creature', etc.

    It matches any inflection of the verb (gain, gains, gained, gaining).
    """
    # Normalize whitespace
    t = " ".join(text.lower().split())

    # Allow multi-word subjects (e.g. 'each opponent')
    subj = re.escape(subject.lower())
    verb = re.escape(verb_root.lower())
    obj  = re.escape(obj_word.lower())

    # subject ... verbFamily ... obj
    pattern = rf"\b{subj}\b[^\.]*\b{verb}\w*\b[^\.]*\b{obj}\b"
    return re.search(pattern, t) is not None

#─────────────────────────────────────────────────────────
#Atom Parsers
#─────────────────────────────────────────────────────────
def _mana_symbols(text: str) -> list[str]:
    return _MTG_SYMBOL_RE.findall(text or "")


def _mana_cost_from_symbols(symbols: list[str]) -> int:
    total = 0
    for s in symbols:
        u = s.upper().strip()
        if u in ("T", "Q"):
            continue
        if u.isdigit():
            total += int(u)
        elif u in ("X", "Y", "Z"):
            # Variable costs: treat as 0 for now (or 1 if you prefer)
            total += 0
        else:
            # W/U/B/R/G, hybrid, phyrexian, snow, etc.
            total += 1
    return total


def _parse_cost_atoms(cost_text: str) -> list[Atom]:
    atoms: list[Atom] = []
    cl = (cost_text or "").lower()

    # Tap/untap symbols (state change, NOT mana)
    if "{t}" in cl:
        atoms.append(tap_atom(target="SELF", cause=Cause.COST, source=Source.CARD))
    if "{q}" in cl:
        atoms.append(untap_atom(target="SELF", cause=Cause.COST, source=Source.CARD))

    # Mana payment (coarse: count symbols excluding T/Q)
    syms = _mana_symbols(cost_text)
    mana_syms = [s for s in syms if s.upper() not in ("T", "Q")]
    mana_cost = _mana_cost_from_symbols(mana_syms)
    if mana_cost:
        atoms.append(ResourceDelta(
            resource="mana",
            delta=-mana_cost,
            target="YOU",
            cause=Cause.COST,
            source=Source.CARD
        ))

    # Sacrifice cost → battlefield to graveyard
    if "sacrifice" in cl:
        atoms.append(ZoneMove(
            from_zone=Zone.BATTLEFIELD,
            to_zone=Zone.GRAVEYARD,
            obj=ObjKind.PERMANENT,
            controller="YOU",
            cause=Cause.SACRIFICE,
            source=Source.CARD
        ))

    # Discard cost
    if "discard" in cl and "card" in cl:
        atoms.append(ZoneMove(
            from_zone=Zone.HAND,
            to_zone=Zone.GRAVEYARD,
            obj=ObjKind.CARD,
            controller="YOU",
            cause=Cause.COST,
            source=Source.CARD
        ))

    # Pay life cost (keep coarse)
    if "pay" in cl and "life" in cl:
        m = re.search(r"pay\s+(\d+)\s+life", cl)
        n = int(m.group(1)) if m else 1
        atoms.append(ResourceDelta(resource="life", delta=-n, target="YOU", cause=Cause.COST, source=Source.CARD))

    # Remove counters as cost (coarse)
    if "remove" in cl and "counter" in cl:
        subtype = "+1/+1" if "+1/+1" in cl else None
        atoms.append(ResourceDelta(resource="counter", delta=-1, target="SELF", subtype=subtype, cause=Cause.COST, source=Source.CARD))

    return atoms


def _parse_result_tags(result_text: str, card_name: Optional[str] = None) -> Set[EventTag]:
    """
    Convert a result clause into EventTags.

    This looks at both the raw text and the extracted ActionUnits.
    """
    tags: Set[EventTag] = set()
    cl = result_text.lower()
    scope_default = _scope_for_you_default(cl)
    units = extract_action_units(result_text, card_name)

    # 1) ActionUnit-driven mapping
    for act in units:
        k = act.kind

        if k == "DRAW_CARD":
            tags.add(ev(EventKind.DRAW, Resource.CARD, Scope.YOU))

        elif k == "CREATE_TOKEN":
            tags.add(ev(EventKind.CREATE, Resource.TOKEN, Scope.YOU))

        elif k == "GAIN_LIFE":
            # If the text clearly says opponents, swap scope
            if "each opponent gains" in cl or "target opponent gains" in cl:
                scope = Scope.OPPONENT
            else:
                scope = Scope.YOU
            tags.add(ev(EventKind.GAIN, Resource.LIFE, scope))

        elif k == "LOSE_LIFE":
            # 'target opponent loses life' / 'each opponent loses life'
            if "target opponent" in cl or "each opponent" in cl or "opponent loses" in cl:
                scope = Scope.OPPONENT
            else:
                scope = Scope.YOU
            tags.add(ev(EventKind.LOSE, Resource.LIFE, scope))

        elif k == "DEAL_DAMAGE":
            # Default: damage to players/planeswalkers
            scope = Scope.ANY_PLAYER
            if act.target:
                if "opponent" in act.target:
                    scope = Scope.OPPONENT
            tags.add(ev(EventKind.DEAL, Resource.DAMAGE, scope))

        elif k == "ADD_MANA":
            tags.add(ev(EventKind.ADD, Resource.MANA, Scope.YOU))

        elif k == "ADD_COUNTER":
            tags.add(ev(EventKind.ADD, Resource.COUNTER, Scope.YOUR_PERMANENT))

        elif k == "REMOVE_COUNTER":
            tags.add(ev(EventKind.LOSE, Resource.COUNTER, Scope.YOUR_PERMANENT))

        elif k == "SACRIFICE_CREATURE":
            tags.add(ev(EventKind.SACRIFICE, Resource.PERMANENT, Scope.YOUR_PERMANENT))

    # 2) Raw-text fallbacks for patterns that ActionUnits don't capture well

    # Tutors / dig: 'put [card(s)] into your hand' → treat as draw-ish
    if "into your hand" in cl and ("card" in cl or "cards" in cl) and "put" in cl:
        tags.add(ev(EventKind.DRAW, Resource.CARD, Scope.YOU))

    # Scry = card selection → soft card advantage
    if "scry" in cl:
        tags.add(ev(EventKind.DRAW, Resource.CARD, Scope.YOU))

    # Card draw (you)
    if _subject_verb_object(cl, "you", "draw", "card"):
        tags.add(ev(EventKind.DRAW, Resource.CARD, Scope.YOU))

    # Lifegain (you)
    if _subject_verb_object(cl, "you", "gain", "life"):
        tags.add(ev(EventKind.GAIN, Resource.LIFE, Scope.YOU))

    # Opponent loses life as a result
    if (
        _subject_verb_object(cl, "target opponent", "lose", "life")
        or _subject_verb_object(cl, "each opponent", "lose", "life")
        or _subject_verb_object(cl, "an opponent", "lose", "life")
        or _subject_verb_object(cl, "opponent", "lose", "life")
    ):
        tags.add(ev(EventKind.LOSE, Resource.LIFE, Scope.OPPONENT))

    # Opponent sacrifices creatures
    if "each opponent sacrifices a creature" in cl:
        tags.add(ev(EventKind.SACRIFICE, Resource.PERMANENT, Scope.OPPONENT))

    # Discard as result
    if "each opponent" in cl and "discards" in cl:
        tags.add(ev(EventKind.LOSE, Resource.CARD, Scope.OPPONENT))
    if "target opponent discards" in cl or "target player discards" in cl:
        tags.add(ev(EventKind.LOSE, Resource.CARD, Scope.ANY_PLAYER))

    # Damage (any target / any player)
    if (
        _subject_verb_object(cl, "it", "deal", "damage")
        or "deals" in cl and "damage" in cl  # keep the coarse fallback
    ):
        tags.add(ev(EventKind.DEAL, Resource.DAMAGE, Scope.ANY_PLAYER))

    # Mana production – lands, rocks, etc.
    if "add" in cl and "mana" in cl:
        tags.add(ev(EventKind.ADD, Resource.MANA, Scope.YOU))
    if re.search(r"\badd\s+\{", result_text, flags=re.IGNORECASE):
        tags.add(ev(EventKind.ADD, Resource.MANA, Scope.YOU))

    # Generic "you may pay {4}" in result clause
    if re.search(r"you may pay\s+\{", result_text, flags=re.IGNORECASE):
        tags.add(ev(EventKind.LOSE, Resource.MANA, Scope.YOU))

    # Return to battlefield → ETB-style result
    if "return" in cl and "to the battlefield" in cl:
        if "under your control" in cl or "your graveyard" in cl or "you control" in cl:
            scope = Scope.YOUR_PERMANENT
        else:
            scope = Scope.ANY_PERMANENT

        if "creature card" in cl or "creature" in cl:
            res = Resource.PERMANENT
        else:
            res = Resource.PERMANENT

        tags.add(ev(EventKind.ENTERS, res, scope))

    return tags


# ─────────────────────────────────────────────────────────
# EventTag parsers (trigger / cost / result)
# ─────────────────────────────────────────────────────────

def _parse_trigger_tags(trigger_text: str, card_name: Optional[str] = None) -> Set[EventTag]:
    tags: set[EventTag] = set()
    tl = trigger_text.lower()
    units = extract_action_units(trigger_text, card_name)

    # Upkeep-style hooks (generic recurring trigger)
    if "at the beginning of your upkeep" in tl:
        tags.add(ev(EventKind.STEP, Resource.PERMANENT, Scope.YOU, step=Step.UPKEEP))

    # Casting triggers (core engine glue)
    # Covers: "Whenever you cast a spell...", "Whenever an opponent casts...", etc.
    if " cast " in f" {tl} " and "spell" in tl:
        if "you cast" in tl:
            tags.add(ev(EventKind.CAST, Resource.CARD, Scope.YOU))
        elif "each opponent casts" in tl or "an opponent casts" in tl or "opponent casts" in tl:
            tags.add(ev(EventKind.CAST, Resource.CARD, Scope.OPPONENT))
        elif "each player casts" in tl or "a player casts" in tl:
            tags.add(ev(EventKind.CAST, Resource.CARD, Scope.ANY_PLAYER))

    # ActionUnit fallback (if we recognized CAST_SPELL)
    for act in units:
        if act.kind == "CAST_SPELL":
            # Best-effort: infer scope from text
            if "you cast" in tl:
                tags.add(ev(EventKind.CAST, Resource.CARD, Scope.YOU))
            elif "opponent casts" in tl:
                tags.add(ev(EventKind.CAST, Resource.CARD, Scope.OPPONENT))
            else:
                tags.add(ev(EventKind.CAST, Resource.CARD, Scope.ANY_PLAYER))

    # Draw triggers (you drawing)
    if _subject_verb_object(tl, "you", "draw", "card"):
        tags.add(ev(EventKind.DRAW, Resource.CARD, Scope.YOU))

    # Lifegain triggers (you gain life)
    if _subject_verb_object(tl, "you", "gain", "life"):
        tags.add(ev(EventKind.GAIN, Resource.LIFE, Scope.YOU))

    # Opponent loses life triggers
    if (
        _subject_verb_object(tl, "opponent", "lose", "life")
        or _subject_verb_object(tl, "each opponent", "lose", "life")
        or _subject_verb_object(tl, "an opponent", "lose", "life")
        or _subject_verb_object(tl, "target opponent", "lose", "life")
    ):
        tags.add(ev(EventKind.LOSE, Resource.LIFE, Scope.OPPONENT))

    # Creature dies patterns...
    if "creature you control dies" in tl or "another creature you control dies" in tl:
        tags.add(ev(EventKind.DIES, Resource.PERMANENT, Scope.YOUR_PERMANENT))

    if (
        "creature an opponent controls dies" in tl
        or "another creature an opponent controls dies" in tl
    ):
        tags.add(ev(EventKind.DIES, Resource.PERMANENT, Scope.OPPONENT))

    if "dies" in tl and "creature" in tl and not any(t.kind == EventKind.DIES for t in tags):
        tags.add(ev(EventKind.DIES, Resource.PERMANENT, Scope.ANY_PERMANENT))

    if "put into your graveyard from the battlefield" in tl and "creature" in tl:
        tags.add(ev(EventKind.DIES, Resource.PERMANENT, Scope.YOUR_PERMANENT))

    # ETB variants...
    if "this creature enters" in tl:
        tags.add(ev(EventKind.ENTERS, Resource.PERMANENT, Scope.YOUR_PERMANENT))

    if "enters" in tl and "you control" in tl:
        if "token" in tl:
            tags.add(ev(EventKind.ENTERS, Resource.TOKEN, Scope.YOUR_PERMANENT))
        else:
            tags.add(ev(EventKind.ENTERS, Resource.PERMANENT, Scope.YOUR_PERMANENT))

    if "enters the battlefield under your control" in tl:
        if "token" in tl:
            tags.add(ev(EventKind.ENTERS, Resource.TOKEN, Scope.YOUR_PERMANENT))
        else:
            tags.add(ev(EventKind.ENTERS, Resource.PERMANENT, Scope.YOUR_PERMANENT))
    elif "enters the battlefield" in tl:
        tags.add(ev(EventKind.ENTERS, Resource.PERMANENT, Scope.ANY_PERMANENT))

    return tags


def _parse_cost_tags(cost_text: str) -> Set[EventTag]:
    """
    Cost clauses usually show up on the left side of ':' in an activated ability.
    """
    tags: Set[EventTag] = set()
    cl = cost_text.lower()

    symbols = re.findall(r"\{[^}]+\}", cost_text) 
    mana_symbols = [s.lower() for s in symbols if s.lower() not in ("{t}", "{q}")]
    
    if mana_symbols:
        tags.add(ev(EventKind.LOSE, Resource.MANA, Scope.YOU))
    
    if "{t}" in cl or "{q}" in cl:
        # for now: do nothing in tags
        pass

    # Sacrifice as cost
    if "sacrifice" in cl:
        tags.add(ev(EventKind.SACRIFICE, Resource.PERMANENT, Scope.YOUR_PERMANENT))

    # Discard as cost
    if "discard" in cl and "card" in cl:
        tags.add(ev(EventKind.LOSE, Resource.CARD, Scope.YOU))

    # Pay life as cost
    if "pay" in cl and "life" in cl:
        tags.add(ev(EventKind.LOSE, Resource.LIFE, Scope.YOU))

    # Remove counters as cost
    if "remove a +1/+1 counter" in cl or "remove a counter" in cl:
        tags.add(ev(EventKind.LOSE, Resource.COUNTER, Scope.YOUR_PERMANENT))

    return tags


def parse_effects_from_text(
    oracle_text: str,
    type_line: str,
    card_name: Optional[str] = None,
) -> List[Effect]:
    """
    Structured effect parser:

      - Split oracle text into ability-like chunks.
      - For each ability:
          triggered  → trigger_text + result_text
          activated  → cost_text + result_text
          static     → result_text only

    Produces:
      - EventTag sets for triggers, costs, and results
      - ActionUnits for trigger / cost / result
      - KeywordHit context windows
    """
    if not oracle_text:
        return []

    abilities = _split_abilities(oracle_text)
    effects: List[Effect] = []

    for ability in abilities:
        clause = ability.strip()
        if not clause:
            continue

        cl = clause.lower()
        effect_type = _guess_effect_type(clause)

        trigger_text: Optional[str] = None
        cost_text:    Optional[str] = None
        result_text:  str = clause

        trigger_tags: Set[EventTag] = set()
        cost_tags:    Set[EventTag] = set()
        result_tags:  Set[EventTag] = set()

        trigger_actions: List[ActionUnit] = []
        cost_actions:    List[ActionUnit] = []
        result_actions:  List[ActionUnit] = []

        # Keyword + context
        kw_hits = _extract_keyword_hits(clause)

        # --- classify and split ---
        if effect_type == "triggered":
            trigger_text, result_text = _split_trigger_clause(clause)
            if trigger_text:
                trigger_actions = extract_action_units(trigger_text, card_name)
                trigger_tags |= _parse_trigger_tags(trigger_text, card_name)
            if result_text:
                result_actions = extract_action_units(result_text, card_name)
                result_tags |= _parse_result_tags(result_text, card_name)

        elif effect_type == "activated":
            cost_text, result_text = _split_cost_clause(clause)
            if cost_text:
                cost_actions = extract_action_units(cost_text, card_name)
                cost_tags |= _parse_cost_tags(cost_text)
            if result_text:
                result_actions = extract_action_units(result_text, card_name)
                result_tags |= _parse_result_tags(result_text, card_name)

        else:  # static / spell text
            result_actions = extract_action_units(result_text, card_name)
            result_tags |= _parse_result_tags(result_text, card_name)

        # --- actors / targets ---
        actor_tags  = _infer_actor_tags(cl)
        target_tags = _infer_target_tags(cl)

        # Activated abilities are controlled by you by default
        if effect_type == "activated":
            actor_tags.add("YOU")

        trigger_atoms: list[Atom] = []
        cost_atoms: list[Atom] = []
        result_atoms: list[Atom] = []

        if cost_text:
            cost_atoms = _parse_cost_atoms(cost_text)
        if result_text:
            result_atoms = _parse_result_atoms(result_text, card_name)

        # Ignore pure reminder / flavor clauses
        if not (trigger_tags or cost_tags or result_tags or trigger_atoms or cost_atoms or result_atoms):
            continue

        effects.append(
            Effect(
                raw_text=clause,
                effect_type=effect_type,
                trigger_tags=trigger_tags,
                cost_tags=cost_tags,
                result_tags=result_tags,

                trigger_atoms=trigger_atoms,
                cost_atoms=cost_atoms,
                result_atoms=result_atoms,

                actor_tags=actor_tags,
                target_tags=target_tags,
                timing=None,
                condition_description=trigger_text,
                modes=[],
                trigger_text=trigger_text,
                cost_text=cost_text,
                result_text=result_text,
                trigger_actions=trigger_actions,
                cost_actions=cost_actions,
                result_actions=result_actions,
                keyword_hits=kw_hits,
            )
        )

    return effects


def card_from_row(row: pd.Series) -> Card:
    """
    Convert a Scryfall-like DataFrame row into a Card object with parsed effects.
    """
    type_line = str(row.get("type_line", "") or "")
    oracle_text = str(row.get("oracle_text", "") or "")
    name = str(row.get("name", "") or "")

    # --- keywords (robust) ---
    raw_kw = row.get("keywords", [])
    if isinstance(raw_kw, list):
        keywords = raw_kw
    elif raw_kw is None or (isinstance(raw_kw, float) and pd.isna(raw_kw)):
        keywords = []
    elif isinstance(raw_kw, str):
        keywords = [s.strip() for s in raw_kw.split(",") if s.strip()]
    else:
        keywords = []

    # --- colors / color_identity (robust) ---
    raw_colors = row.get("color_identity", [])
    if isinstance(raw_colors, list):
        colors = raw_colors
    elif isinstance(raw_colors, np.ndarray):
        colors = list(raw_colors)
    elif raw_colors is None or (isinstance(raw_colors, float) and pd.isna(raw_colors)):
        colors = []
    elif isinstance(raw_colors, str):
        if raw_colors.startswith("[") and raw_colors.endswith("]"):
            inner = raw_colors[1:-1]
            colors = [c.strip(" '\"") for c in inner.split(",") if c.strip()]
        else:
            colors = [c for c in raw_colors if c in {"W", "U", "B", "R", "G"}]
    else:
        try:
            colors = list(raw_colors)
        except TypeError:
            colors = []

    # Crude type split; you may already have better logic elsewhere
    types = [t for t in type_line.replace("—", "-").split() if t and t[0].isupper()]

    if "Instant" in type_line:
        cast_timing = "instant_speed"
    elif "Sorcery" in type_line:
        cast_timing = "sorcery_speed"
    else:
        cast_timing = "special"

    is_permanent = not ("Instant" in type_line or "Sorcery" in type_line)

    try:
        mana_value = float(row.get("cmc", 0) or 0.0)
    except Exception:
        mana_value = 0.0

    effects = parse_effects_from_text(oracle_text, type_line, card_name=name)

    return Card(
        name=name,
        mana_value=mana_value,
        mana_cost=str(row.get("mana_cost", "") or ""),
        colors=colors,
        types=types,
        subtypes=[],  # can be populated if you care
        is_permanent=is_permanent,
        cast_timing=cast_timing,
        oracle_text=oracle_text,
        keywords=keywords,
        effects=effects,
    )

def summarize_card_engine(card: Card) -> dict:
    """
    Flatten a Card's engine-relevant info into a simple dict, suitable for
    inspection or tabular storage.
    """
    return {
        "name": card.name,
        "triggers": {t.short() for t in card.all_trigger_tags()},
        "results": {t.short() for t in card.all_result_tags()},
        "costs": {t.short() for t in card.all_cost_tags()},
        "actors": card.all_actor_tags(),
        "targets": card.all_target_tags(),
    }


def engine_score(card: Card) -> float:
    """
    Rough heuristic: high if it repeatedly produces cards/tokens/life
    without big costs.
    """
    score = 0.0

    for e in card.effects:
        # Frequent trigger patterns
        for t in e.trigger_tags:
            if t.kind == EventKind.DRAW and t.scope == Scope.YOU:
                score += 1.5
            if t.kind == EventKind.GAIN and t.resource == Resource.LIFE:
                score += 1.5
            if t.kind == EventKind.ENTERS and t.scope in {Scope.YOUR_PERMANENT, Scope.ANY_PERMANENT}:
                score += 1.0
            if t.kind == EventKind.DIES:
                score += 1.0

        # Value results
        for r in e.result_tags:
            if r.kind == EventKind.DRAW and r.resource == Resource.CARD:
                score += 3.0
            if r.kind == EventKind.CREATE and r.resource == Resource.TOKEN:
                score += 2.5
            if r.kind == EventKind.GAIN and r.resource == Resource.LIFE:
                score += 1.0

        # Costs that hurt engines
        if any(c.kind == EventKind.SACRIFICE and c.resource == Resource.PERMANENT for c in e.cost_tags):
            score -= 1.0
        if any(c.kind == EventKind.LOSE and c.resource == Resource.LIFE for c in e.cost_tags):
            score -= 0.5

    return score


def card_synergy(a: Card, b: Card) -> float:
    """
    Symmetric-ish synergy score between two cards.

    Key rules:
      - We respect Effect boundaries. Costs and results are taken from each
        Effect, not from a card-wide union.
      - Costs are ONLY taken from cost_tags. We do NOT treat LOSE:MANA in a
        result as a 'cost' just because it exists.
      - We still expose a flattened view (card.all_*_tags) for cheap, coarse
        heuristics (stacking engines, shared costs), but loop-ish stuff is
        based on Effect-level structure.
    """

    # Card-level aggregations (fine for cheap heuristics)
    a_trig = a.all_trigger_tags()
    a_res  = a.all_result_tags()
    a_cost = a.all_cost_tags()

    b_trig = b.all_trigger_tags()
    b_res  = b.all_result_tags()
    b_cost = b.all_cost_tags()

    score = 0.0

    # ─────────────────────────────────────────────────────────
    # 1) Direct event feeds (card-level, still useful)
    #    "Result of A matches trigger of B" and vice versa.
    # ─────────────────────────────────────────────────────────
    feeds_ab = len(a_res & b_trig)
    feeds_ba = len(b_res & a_trig)
    score += 3.0 * (feeds_ab + feeds_ba)

    # ─────────────────────────────────────────────────────────
    # 2) Effect-level resource feeding
    #    We now respect individual abilities instead of treating the whole
    #    card as "consumes mana" or "produces mana" in the abstract.
    # ─────────────────────────────────────────────────────────

    def effect_produces_mana(e: Effect) -> bool:
        return any(isinstance(a, ResourceDelta) and a.resource == "mana" and a.delta > 0 for a in e.result_atoms)

    def effect_consumes_mana(e: Effect) -> bool:
        return any(isinstance(a, ResourceDelta) and a.resource == "mana" and a.delta < 0 for a in e.cost_atoms)

    def effect_produces_bodies(e: Effect) -> bool:
        return any(
            isinstance(a, ZoneMove)
            and a.to_zone == Zone.BATTLEFIELD
            and a.obj in {ObjKind.TOKEN, ObjKind.PERMANENT}
            and a.controller == "YOU"
            for a in e.result_atoms
        )

    def effect_sacs_creatures(e: Effect) -> bool:
        return any(
            isinstance(a, ZoneMove)
            and a.from_zone == Zone.BATTLEFIELD
            and a.to_zone == Zone.GRAVEYARD
            and a.obj == ObjKind.PERMANENT
            and a.controller == "YOU"
            and a.cause == Cause.SACRIFICE
            for a in e.cost_atoms
        )

    # Per-effect synergy passes
    for ea in a.effects:
        for eb in b.effects:
            # 2a) Effect-level trigger feeds: A's result tags -> B's triggers
            if ea.result_tags & eb.trigger_tags:
                score += 3.0
            if eb.result_tags & ea.trigger_tags:
                score += 3.0

            # 2b) Resource feeding: mana engines
            if effect_produces_mana(ea) and effect_consumes_mana(eb):
                score += 2.0
            if effect_produces_mana(eb) and effect_consumes_mana(ea):
                score += 2.0

            # 2c) Resource feeding: bodies → sac outlets
            if effect_produces_bodies(ea) and effect_sacs_creatures(eb):
                score += 2.0
            if effect_produces_bodies(eb) and effect_sacs_creatures(ea):
                score += 2.0

    # ─────────────────────────────────────────────────────────
    # 3) Shared outputs for YOU at card-level
    #    Engines that stack nicely (double draw, double tokens, etc.)
    # ─────────────────────────────────────────────────────────
    good_resources = {
        (EventKind.DRAW,   Resource.CARD),
        (EventKind.CREATE, Resource.TOKEN),
        (EventKind.ADD,    Resource.COUNTER),
        (EventKind.ADD,    Resource.MANA),
        (EventKind.GAIN,   Resource.LIFE),
    }

    def good_output_pairs(res_tags: Set[EventTag]) -> Set[tuple[EventKind, Resource]]:
        return {
            (t.kind, t.resource)
            for t in res_tags
            if (t.kind, t.resource) in good_resources
            and t.scope in {Scope.YOU, Scope.YOUR_PERMANENT}
        }

    a_good = good_output_pairs(a_res)
    b_good = good_output_pairs(b_res)
    shared_good = len(a_good & b_good)
    score += 1.5 * shared_good

    # ─────────────────────────────────────────────────────────
    # 4) Shared scarce costs (card-level)
    #    Two cards that both demand the same scarce thing hurt each other a bit.
    # ─────────────────────────────────────────────────────────
    bad_cost_pairs = {
        (EventKind.SACRIFICE, Resource.PERMANENT),
        (EventKind.LOSE,      Resource.LIFE),
    }

    def bad_costs(cost_tags: Set[EventTag]) -> Set[tuple[EventKind, Resource]]:
        return {
            (t.kind, t.resource)
            for t in cost_tags
            if (t.kind, t.resource) in bad_cost_pairs
        }

    a_bad = bad_costs(a_cost)
    b_bad = bad_costs(b_cost)
    shared_bad = len(a_bad & b_bad)
    score -= 1.0 * shared_bad

    return score


def build_engine_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Take a Scryfall-like DataFrame and return a table of:
      name, colors, mana_value, engine_score, triggers, results, costs
    for all cards that have at least one parsed effect.
    """
    rows = []

    for _, row in df.iterrows():
        card = card_from_row(row)
        if not card.effects:
            continue

        summary = summarize_card_engine(card)
        score = engine_score(card)

        rows.append(
            {
                "name": card.name,
                "colors": "".join(card.colors),
                "mana_value": card.mana_value,
                "engine_score": score,
                "triggers": sorted(summary["triggers"]),
                "results": sorted(summary["results"]),
                "costs": sorted(summary["costs"]),
            }
        )

    eng_df = pd.DataFrame(rows)
    eng_df.sort_values("engine_score", ascending=False, inplace=True)
    eng_df.reset_index(drop=True, inplace=True)
    return eng_df


def test_random_cards(num_samples: int = 20, seed: int = 42) -> None:
    """
    Pull a random subset of cards from the library and print their parsed
    engine structure for eyeballing.
    """
    df = pd.read_parquet("MTGCardLibrary.parquet")

    if len(df) == 0:
        raise ValueError("Card library is empty or not loaded correctly.")

    sample = df.sample(n=min(num_samples, len(df)), random_state=seed)

    for _, row in sample.iterrows():
        card = card_from_row(row)
        type_line = str(row.get("type_line", "") or "")

        print("=" * 80)
        print(f"{card.name} — {type_line}")
        print(f"MV: {card.mana_value} | Cost: {card.mana_cost} | Colors: {''.join(card.colors) or 'Colorless'}")
        print()
        print("Oracle Text:")
        print(card.oracle_text or "(no oracle text)")
        print()
        print(f"Engine score (rough): {engine_score(card):.2f}")
        print()

        if not card.effects:
            print("No parsed effects.")
            continue

        print("Effects:")
        for e in card.effects:
            print(f"  · [{e.effect_type}] {e.raw_text}")
            if e.trigger_text:
                print(f"     trigger_text: {e.trigger_text}")
            if e.cost_text:
                print(f"     cost_text:    {e.cost_text}")
            if e.result_text and e.result_text != e.raw_text:
                print(f"     result_text:  {e.result_text}")

            if e.trigger_tags:
                print("     trigger_tags:", ", ".join(t.short() for t in e.trigger_tags))
            if e.cost_tags:
                print("     cost_tags:   ", ", ".join(t.short() for t in e.cost_tags))
            if e.result_tags:
                print("     result_tags: ", ", ".join(t.short() for t in e.result_tags))

            if e.trigger_actions:
                print("     trigger_actions:", [a.kind or a.verb for a in e.trigger_actions])
            if e.cost_actions:
                print("     cost_actions:   ", [a.kind or a.verb for a in e.cost_actions])
            if e.result_actions:
                print("     result_actions: ", [a.kind or a.verb for a in e.result_actions])
        print()

        print("Card summary:")
        print(summarize_card_engine(card))
        print()


def test_known_combos() -> None:
    """
    Sanity-check some known combo pieces.

    This does NOT prove an infinite loop exists. It:
      - Parses the cards
      - Prints their engine tags
      - Shows which EventTags from one card's results feed the other's triggers
      - Shows a simple synergy score
    """
    LIB_PATH = "MTGCardLibrary.parquet"
    df = pd.read_parquet(LIB_PATH)

    if "name" not in df.columns:
        raise ValueError(f"'name' column not found in {LIB_PATH}")

    combo_defs: Dict[str, List[str]] = {
        "Sanguine Bond + Exquisite Blood": [
            "Sanguine Bond",
            "Exquisite Blood",
        ],
        "Heliod + Walking Ballista": [
            "Heliod, Sun-Crowned",
            "Walking Ballista",
        ],
        "Deadeye Navigator + Peregrine Drake": [
            "Deadeye Navigator",
            "Peregrine Drake",
        ],
        "Ashnod's Altar + Nim Deathmantle": [
            "Ashnod's Altar",
            "Nim Deathmantle",
        ],
        "Dockside Extortionist + Revel in Riches": [
            "Dockside Extortionist",
            "Revel in Riches",
        ],
    }

    df_by_name = df.set_index("name", drop=False)

    for label, names in combo_defs.items():
        print("=" * 80)
        print(f"Testing combo: {label}")

        missing = [n for n in names if n not in df_by_name.index]
        if missing:
            print(f"  Skipping combo; missing in library: {', '.join(missing)}")
            continue

        # Build Card objects
        cards: List[Card] = [card_from_row(df_by_name.loc[n]) for n in names]

        # Per-card engine summary
        print("  Card engines:")
        for c in cards:
            trig = {t.short() for t in c.all_trigger_tags()}
            res  = {t.short() for t in c.all_result_tags()}
            cost = {t.short() for t in c.all_cost_tags()}
            print(f"    - {c.name}")
            print(f"        engine_score = {engine_score(c):.2f}")
            print(f"        triggers     = {trig or '{}'}")
            print(f"        results      = {res or '{}'}")
            print(f"        costs        = {cost or '{}'}")

        if len(cards) < 2:
            continue

        print("\n  Pairwise synergy and event feeds:")
        for i in range(len(cards)):
            for j in range(i + 1, len(cards)):
                a = cards[i]
                b = cards[j]

                s = card_synergy(a, b)

                a_trig = a.all_trigger_tags()
                a_res  = a.all_result_tags()
                b_trig = b.all_trigger_tags()
                b_res  = b.all_result_tags()

                feeds_ab = {t.short() for t in (a_res & b_trig)}
                feeds_ba = {t.short() for t in (b_res & a_trig)}

                print(f"    {a.name} ↔ {b.name}")
                print(f"        synergy score   = {s:.2f}")
                print(f"        A → B feeds     = {feeds_ab or '{}'}")
                print(f"        B → A feeds     = {feeds_ba or '{}'}")

                if feeds_ab and feeds_ba:
                    print("        -> Potential 2-card loop (both directions feed).")
                elif feeds_ab or feeds_ba:
                    print("        -> One-direction engine (could be part of a larger loop).")
                else:
                    print("        -> No direct event-tag feed detected.")
        print()


if __name__ == "__main__":
    # Random smoke test
    test_random_cards(num_samples=25, seed=42)

    print("\n" + "#" * 80)
    print("Known combo sanity checks")
    print("#" * 80 + "\n")

    test_known_combos()
