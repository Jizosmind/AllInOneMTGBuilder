# mtg_analyzer/roles.py
from __future__ import annotations
from constants import MASS_LAND_DENIAL_NAMES
import pandas as pd


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
    raw_colors = row.get("color_identity", [])

    # Right now we don't actually use `colors` anywhere in this function.
    # Just normalize lists and ignore everything else to avoid pandas/NumPy weirdness.
    if isinstance(raw_colors, list):
        colors = raw_colors
    else:
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
    # Board wipes – creatures (stricter)
    if (
        "destroy all creatures" in text
        or "exile all creatures" in text
        or "destroy each creature" in text
        or "exile each creature" in text
        # global shrink that is very likely to kill a ton of stuff
        or ("each creature gets -" in text and "until end of turn" in text)
        or ("all creatures get -" in text and "until end of turn" in text)
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
