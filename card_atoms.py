from dataclasses import dataclass
from typing import Optional, Union, FrozenSet
from mtg_vocab import Source, Step, PermanentStatus, Zone, Cause, ObjKind

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
    require_type: Optional[str] = None   # e.g. "Creature"
    forbid_type: Optional[str] = None    # e.g. "Token" if you ever model it as a type

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
    step: Optional[Step] = None
    source: Optional[Source] = None

@dataclass(frozen=True)
class StateDeltaPattern:
    target: Optional[str] = None
    set_mask: Optional[PermanentStatus] = None
    clear_mask: Optional[PermanentStatus] = None
    cause: Optional[Cause] = None
    source: Optional[Source] = None


#============
# Event Atoms
#============

@dataclass(frozen=True)
class ZoneMove:
    from_zone: Zone
    to_zone: Zone
    obj: ObjKind
    obj_types: FrozenSet[str] = frozenset()
    controller: Optional[str] = None
    cause: Cause = Cause.OTHER
    source: Source = Source.ANY

@dataclass(frozen=True)
class ResourceDelta:
    resource: str
    delta: int
    target: Optional[str] = None
    subtype: Optional[str] = None
    cause: Cause = Cause.OTHER
    source: Source = Source.ANY

@dataclass(frozen=True)
class StepChange:
    step: Step
    source: Source = Source.RULES

@dataclass(frozen=True)
class StateDelta:
    target: Optional[str] = None
    set_mask: PermanentStatus = PermanentStatus(0)
    clear_mask: PermanentStatus = PermanentStatus(0)
    cause: Cause = Cause.OTHER
    source: Source = Source.ANY


#=================
# Helper Functions
#=================

def has_type(move: ZoneMove, type_name: str) -> bool:
    return type_name in move.obj_types

def is_permanent_dies(move: ZoneMove) -> bool:
    return (
        move.from_zone == Zone.BATTLEFIELD
        and move.to_zone == Zone.GRAVEYARD
        and move.obj == ObjKind.PERMANENT
    )

def is_dies(move: ZoneMove, require_type: str | None = None) -> bool:
    if move.from_zone != Zone.BATTLEFIELD or move.to_zone != Zone.GRAVEYARD:
        return False
    if move.obj not in (ObjKind.PERMANENT, ObjKind.TOKEN):
        return False
    if require_type is None:
        return True
    return require_type in (move.obj_types or ())

def tap_atom(target="SELF", cause=Cause.COST, source=Source.CARD) -> StateDelta:
    return StateDelta(target=target, set_mask=PermanentStatus.TAPPED, cause=cause, source=source)

def untap_atom(target="SELF", cause=Cause.EFFECT, source=Source.CARD) -> StateDelta:
    return StateDelta(target=target, clear_mask=PermanentStatus.TAPPED, cause=cause, source=source)


Atom = Union[ZoneMove, ResourceDelta, StepChange, StateDelta]
AtomPattern = Union[ZoneMovePattern, ResourceDeltaPattern, StepChangePattern, StateDeltaPattern]

def atom_matches(pattern: AtomPattern, atom: Atom) -> bool:
    if isinstance(pattern, ZoneMovePattern) and isinstance(atom, ZoneMove):
        if pattern.require_type is not None and pattern.require_type not in atom.obj_types:
            return False
        if pattern.forbid_type is not None and pattern.forbid_type in atom.obj_types:
            return False

        return (
            (pattern.from_zone is None or pattern.from_zone == atom.from_zone) and
            (pattern.to_zone   is None or pattern.to_zone   == atom.to_zone) and
            (pattern.obj       is None or pattern.obj       == atom.obj) and
            (pattern.controller is None or pattern.controller == atom.controller) and
            (pattern.cause     is None or pattern.cause     == atom.cause) and
            (pattern.source    is None or pattern.source    == atom.source)
        )

    if isinstance(pattern, ResourceDeltaPattern) and isinstance(atom, ResourceDelta):
        return (
            (pattern.resource is None or pattern.resource == atom.resource) and
            (pattern.delta    is None or pattern.delta    == atom.delta) and
            (pattern.target   is None or pattern.target   == atom.target) and
            (pattern.subtype  is None or pattern.subtype  == atom.subtype) and
            (pattern.cause    is None or pattern.cause    == atom.cause) and
            (pattern.source   is None or pattern.source   == atom.source)
        )

    if isinstance(pattern, StepChangePattern) and isinstance(atom, StepChange):
        return (
            (pattern.step   is None or pattern.step   == atom.step) and
            (pattern.source is None or pattern.source == atom.source)
        )

    if isinstance(pattern, StateDeltaPattern) and isinstance(atom, StateDelta):
        return (
            (pattern.target     is None or pattern.target     == atom.target) and
            (pattern.set_mask   is None or (atom.set_mask & pattern.set_mask) == pattern.set_mask) and
            (pattern.clear_mask is None or (atom.clear_mask & pattern.clear_mask) == pattern.clear_mask) and
            (pattern.cause      is None or pattern.cause      == atom.cause) and
            (pattern.source     is None or pattern.source     == atom.source)
        )

    return False
