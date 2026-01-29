from enum import Enum, auto, IntFlag

class Source(Enum):
    ANY = auto()
    CARD = auto()
    RULES = auto()

class Step(Enum):
    UNTAP = auto()
    UPKEEP = auto()
    DRAW_STEP = auto()
    BEGIN_COMBAT = auto()
    DECLARE_ATTACKERS = auto()
    DECLARE_BLOCKERS = auto()
    COMBAT_DAMAGE = auto()
    END_COMBAT = auto()
    MAIN1 = auto()
    MAIN2 = auto()
    END_STEP = auto()
    CLEANUP = auto()

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
    EFFECT = auto()
    RULES = auto()
    SBA = auto()
    CAST = auto()
    ACTIVATION = auto()
    TRIGGER = auto()
    OTHER = auto()

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

class PermanentStatus(IntFlag):
    TAPPED = auto()
    PHASED_OUT = auto()
    FACE_DOWN = auto()
    TRANSFORMED = auto()
    FLIPPED = auto()
