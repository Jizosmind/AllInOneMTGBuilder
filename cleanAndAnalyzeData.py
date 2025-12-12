# cleanAndAnalyzeData.py
from __future__ import annotations
from typing import Dict, Any
import pandas as pd

from themes import detect_card_themes
from roles import get_card_roles
from card_features import (
    is_land,
    is_ramp,
    is_card_draw,
    is_board_wipe,
    is_removal,
    is_game_changer,
    is_mass_land_denial,
    is_extra_turn,
    is_nonland_tutor,
    is_permanent_card,
    has_persistent_output,
    persistence_score,
)

# --- Load base data ---
df_raw = pd.read_parquet("MTGCardLibrary.parquet")

df_cmdr = df_raw[df_raw["legalities.commander"] == "legal"].copy()

cols = [
    "name", "mana_cost", "cmc", "type_line", "oracle_text", "keywords",
    "colors", "color_identity", "edhrec_rank", "prices.usd",
    "set", "rarity", "released_at"
]

df_cmdr = df_cmdr[cols].copy()

# --- Themes & roles ---
df_cmdr["themes"] = df_cmdr.apply(detect_card_themes, axis=1)
df_cmdr["roles"]  = df_cmdr.apply(get_card_roles, axis=1)

# --- Feature flags ---
feature_funcs = {
    "is_land": is_land,
    "is_ramp": is_ramp,
    "is_card_draw": is_card_draw,
    "is_board_wipe": is_board_wipe,
    "is_removal": is_removal,
    "is_game_changer": is_game_changer,
    "is_mass_land_denial": is_mass_land_denial,
    "is_extra_turn": is_extra_turn,
    "is_nonland_tutor": is_nonland_tutor,
    "is_permanent_card": is_permanent_card,
    "has_persistent_output": has_persistent_output,
}

for col, func in feature_funcs.items():
    df_cmdr[col] = df_cmdr.apply(func, axis=1)

df_cmdr["persistence_score"] = df_cmdr.apply(persistence_score, axis=1)

def summarize_slice(df_slice: pd.DataFrame, label: str, kind: str) -> Dict[str, Any]:
    """
    Summarize a subset of cards (by theme/role/etc.).
    kind = "theme", "role", or "theme+role" just for labeling.
    """
    n = len(df_slice)
    if n == 0:
        return {}

    cmc = pd.to_numeric(df_slice["cmc"], errors="coerce").fillna(0.0)

    type_lines = df_slice["type_line"].fillna("").str.lower()
    inst_mask  = type_lines.str.contains("instant")
    sorc_mask  = type_lines.str.contains("sorcery")
    creature_mask = type_lines.str.contains("creature")
    # “Permanent” = not instant/sorcery
    perm_mask  = ~(inst_mask | sorc_mask)

    persistence = df_slice.get("persistence_score")
    if persistence is not None:
        persistence = persistence.fillna(0).astype(float)
    else:
        persistence = pd.Series([0.0] * n, index=df_slice.index)

    edh = df_slice.get("edhrec_rank")
    if edh is not None:
        # some cards may have NaN or None – ignore in medians
        edh_valid = pd.to_numeric(edh, errors="coerce")
    else:
        edh_valid = pd.Series([float("nan")] * n, index=df_slice.index)

    stats: Dict[str, Any] = {
        "label": label,
        "kind": kind,
        "count": n,
        "cmc_mean": float(cmc.mean()),
        "cmc_median": float(cmc.median()),
        "cmc_p25": float(cmc.quantile(0.25)),
        "cmc_p75": float(cmc.quantile(0.75)),
        "cmc_std": float(cmc.std(ddof=0)),
        "cheap_frac_<=2": float((cmc <= 2).mean()),
        "heavy_frac_>=6": float((cmc >= 6).mean()),
        "instant_frac": float(inst_mask.mean()),
        "sorcery_frac": float(sorc_mask.mean()),
        "creature_frac": float(creature_mask.mean()),
        "permanent_frac": float(perm_mask.mean()),
        "persistence_mean": float(persistence.mean()),
        "persistence_median": float(persistence.median()),
        "edhrec_median": float(edh_valid.median()) if edh_valid.notna().any() else None,
        "edhrec_p25": float(edh_valid.quantile(0.25)) if edh_valid.notna().any() else None,
        "edhrec_p75": float(edh_valid.quantile(0.75)) if edh_valid.notna().any() else None,
    }

    # --- General feature coverage (this is the important new bit) ---
    # Any boolean-ish feature column like is_ramp, is_card_draw, has_persistent_output, etc.
    feature_cols = [
        c for c in df_slice.columns
        if c.startswith("is_") or c.startswith("has_")
    ]

    for col in feature_cols:
        # cast to bool to be safe (some may be 0/1 or NaN)
        bool_series = df_slice[col].fillna(False).astype(bool)
        stats[f"{col}_frac"] = float(bool_series.mean())
        stats[f"{col}_count"] = int(bool_series.sum())

    return stats

def speed_bucket(z: float) -> str:
    if z <= -0.75:
        return "fast"
    if z >= 0.75:
        return "slow"
    return "midrange"

def _collect_labels(series):
    labels = set()
    for s in series:
        if not s:
            continue
        for x in s:
            labels.add(x)
    return sorted(labels)

all_themes = _collect_labels(df_cmdr["themes"])
all_roles  = _collect_labels(df_cmdr["roles"])

summary_rows = []

# --- Per-theme stats ---
for theme in all_themes:
    mask = df_cmdr["themes"].apply(lambda ts: theme in (ts or set()))
    slice_df = df_cmdr[mask]
    if len(slice_df) < 50:
        continue  # ignore tiny sample sizes for now
    summary_rows.append(summarize_slice(slice_df, label=theme, kind="theme"))

# --- Per-role stats ---
for role in all_roles:
    mask = df_cmdr["roles"].apply(lambda rs: role in (rs or set()))
    slice_df = df_cmdr[mask]
    if len(slice_df) < 50:
        continue
    summary_rows.append(summarize_slice(slice_df, label=role, kind="role"))

# --- Theme+role combos (the spicy part) ---
for theme in all_themes:
    tmask = df_cmdr["themes"].apply(lambda ts: theme in (ts or set()))
    for role in all_roles:
        rmask = df_cmdr["roles"].apply(lambda rs: role in (rs or set()))
        combo_mask = tmask & rmask
        slice_df = df_cmdr[combo_mask]
        if len(slice_df) < 50:
            continue  # threshold so we don't drown in noise
        combo_label = f"{theme}__{role}"
        summary_rows.append(summarize_slice(slice_df, label=combo_label, kind="theme+role"))

df_slices = pd.DataFrame(summary_rows)

# --- Global baseline for nonland spells (commander-legal) ---

nonland = df_cmdr[~df_cmdr["is_land"]].copy()
global_cmc = pd.to_numeric(nonland["cmc"], errors="coerce").fillna(0.0)

global_cmc_mean = float(global_cmc.mean())
global_cmc_std  = float(global_cmc.std(ddof=0))  # population std

print("Global nonland CMC mean:", global_cmc_mean)
print("Global nonland CMC std:", global_cmc_std)

# Annotate each slice with "how fast/slow is this slice vs global"
df_slices["cmc_mean_z_global"] = (
    (df_slices["cmc_mean"] - global_cmc_mean) / global_cmc_std
)

df_slices.to_parquet("theme_role_feature_summary.parquet")
df_slices.to_csv("theme_role_feature_summary.csv", index=False)

print("Wrote", len(df_slices), "theme/role slices to theme_role_feature_summary.*")


# ROLE-normalized metrics
df_role_slices = df_slices[df_slices["kind"] == "role"].copy()
df_role_slices = df_role_slices.rename(columns={"label": "role"})

# explode roles on the card table
df_roles_expanded = df_cmdr.explode("roles")
df_roles_expanded = df_roles_expanded.dropna(subset=["roles"]).copy()
df_roles_expanded = df_roles_expanded.rename(columns={"roles": "role"})

# join card -> role baseline
df_card_role = df_roles_expanded.merge(df_role_slices, on="role", how="left")

# compute card-level CMC z-score vs its role slice
cmc_card = pd.to_numeric(df_card_role["cmc"], errors="coerce").fillna(0.0)
cmc_mean_role = df_card_role["cmc_mean"]
cmc_std_role  = df_card_role["cmc_std"].replace(0, pd.NA)

df_card_role["cmc_z_vs_role"] = (cmc_card - cmc_mean_role) / cmc_std_role

# you now have: one row per (card, role) pair with normalized CMC
df_card_role.to_parquet("card_role_cmc_norm.parquet")
df_card_role.to_csv("card_role_cmc_norm.csv", index=False)
print("Wrote", len(df_card_role), "card-role rows to card_role_cmc_norm.*")

# --- Card-level normalization vs theme baselines ---

df_theme_slices = df_slices[df_slices["kind"] == "theme"].copy()
df_theme_slices = df_theme_slices.rename(columns={"label": "theme"})

df_themes_expanded = df_cmdr.explode("themes")
df_themes_expanded = df_themes_expanded.dropna(subset=["themes"]).copy()
df_themes_expanded = df_themes_expanded.rename(columns={"themes": "theme"})

df_card_theme = df_themes_expanded.merge(df_theme_slices, on="theme", how="left")

cmc_card_t = pd.to_numeric(df_card_theme["cmc"], errors="coerce").fillna(0.0)
cmc_mean_theme = df_card_theme["cmc_mean"]
cmc_std_theme  = df_card_theme["cmc_std"].replace(0, pd.NA)

df_card_theme["cmc_z_vs_theme"] = (cmc_card_t - cmc_mean_theme) / cmc_std_theme

df_card_theme.to_parquet("card_theme_cmc_norm.parquet")
df_card_theme.to_csv("card_theme_cmc_norm.csv", index=False)

print("Wrote", len(df_card_theme), "card-theme rows to card_theme_cmc_norm.*")