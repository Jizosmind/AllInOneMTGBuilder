import pandas as pd


df_raw = pd.read_parquet("MTGCardLibrary.parquet")

df_cmdr = df_raw[df_raw["legalities.commander"] == "legal"].copy()

cols = [
    "name", "mana_cost", "cmc", "type_line", "oracle_text", "keywords",
    "colors", "color_identity", "edhrec_rank", "prices.usd",
    "set", "rarity", "released_at"
]

df_cmdr = df_cmdr[cols].copy()

print(df_cmdr["keywords"])