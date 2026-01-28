from card_atoms import Zone, Cause, Source, ObjKind, ZoneMove

m = ZoneMove(
    from_zone=Zone.BATTLEFIELD,
    to_zone=Zone.GRAVEYARD,
    obj=ObjKind.CREATURE,
    cause=Cause.SACRIFICE,
    source=Source.CARD,
)
print(m)
