from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple, Dict
from enum import Enum, auto
from typing import Union

#==========
# Classes 
#==========

class Zone(Enum):
    HAND = auto()
    STACK = auto()
    BATTLEFIELD = auto()
    GRAVEYARD = auto()
    EXILE = auto()
    LIBRARY = auto()
    COMMAND = auto()

class Cause(Enum):
    SACRIFICE = auto()
    DESTROY = auto()
    DAMAGE = auto()
    COST = auto()
    RULES = auto()
    SBA = auto()
    CAST = auto()
    ACTIVATION = auto()
    TRIGGER = auto()
    OTHER = auto()

class Source(Enum):
    ANY = auto()
    CARD = auto()
    RULES = auto()

class ObjKind(Enum):
    CARD = auto()
    TOKEN = auto()
    PERMANENT = auto()
    CREATURE = auto()
    ARTIFACT = auto()
    ENCHANTMENT = auto()
    LAND = auto()
    PLANESWALKER = auto()
    SPELL = auto()
    ABILITY = auto()

# =====================
# Pattern Atoms (wildcards allowed)
# =====================

@dataclass(frozen=True)
class ZoneMovePattern:
    from_zone: Optional[Zone] = None
    to_zone: Optional[Zone] = None
    obj: Optional[ObjKind] = None
    controller: Optional[str] = None
    cause: Optional[Cause] = None
    source: Optional[Source] = None

@dataclass(frozen=True)
class ResourceDeltaPattern:
    resource: Optional[str] = None
    delta: Optional[int] = None
    target: Optional[str] = None
    subtype: Optional[str] = None
    cause: Optional[Cause] = None
    source: Optional[Source] = None

@dataclass(frozen=True)
class StepChangePattern:
    step: Optional[str] = None
    source: Optional[Source] = None


@dataclass
class stateChange:
    target: Optional[str]
    


#============
#Event Atoms
#============

@dataclass(frozen=True)
class ZoneMove:
    from_zone: Zone
    to_zone: Zone
    obj: ObjKind
    controller: Optional[str] = None      # "YOU" / "OPPONENT" / etc
    cause: Cause = Cause.OTHER
    source: Source = Source.ANY           # did it come from a card or rules?

@dataclass(frozen=True)
class ResourceDelta:
    resource: str                         # "life", "mana", "counter", "card"
    delta: int                            # +1 / -1 / etc
    target: Optional[str] = None          # "YOU" / "OPPONENT" / "ANY_PLAYER"
    subtype: Optional[str] = None         # "W" mana, "+1/+1", "loyalty", etc
    cause: Cause = Cause.OTHER
    source: Source = Source.ANY

@dataclass(frozen=True)
class StepChange:
    step: str                             # keep it string for now, enum later
    source: Source = Source.RULES         # IMPORTANT: not RULES, but Source.RULES

#=================
#Helper Functions
#=================
def is_creature_dies(move: ZoneMove) -> bool:
    return (
        move.from_zone == Zone.BATTLEFIELD
        and move.to_zone == Zone.GRAVEYARD
        and move.obj == ObjKind.CREATURE
    )


Atom = Union[ZoneMove, ResourceDelta, StepChange]
AtomPattern = Union[ZoneMovePattern, ResourceDeltaPattern, StepChangePattern]

def atom_matches(pattern: AtomPattern, atom: Atom) -> bool:
    # must be same “shape”
    if type(pattern) is ZoneMovePattern and type(atom) is ZoneMove:
        return (
            (pattern.from_zone is None or pattern.from_zone == atom.from_zone) and
            (pattern.to_zone   is None or pattern.to_zone   == atom.to_zone) and
            (pattern.obj       is None or pattern.obj       == atom.obj) and
            (pattern.controller is None or pattern.controller == atom.controller) and
            (pattern.cause     is None or pattern.cause     == atom.cause) and
            (pattern.source    is None or pattern.source    == atom.source)
        )

    if type(pattern) is ResourceDeltaPattern and type(atom) is ResourceDelta:
        return (
            (pattern.resource is None or pattern.resource == atom.resource) and
            (pattern.delta    is None or pattern.delta    == atom.delta) and
            (pattern.target   is None or pattern.target   == atom.target) and
            (pattern.subtype  is None or pattern.subtype  == atom.subtype) and
            (pattern.cause    is None or pattern.cause    == atom.cause) and
            (pattern.source   is None or pattern.source   == atom.source)
        )

    if type(pattern) is StepChangePattern and type(atom) is StepChange:
        return (
            (pattern.step   is None or pattern.step   == atom.step) and
            (pattern.source is None or pattern.source == atom.source)
        )

    return False