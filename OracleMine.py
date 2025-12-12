# mine_ability_patterns.py

import re
import pandas as pd

PARQUET_PATH = "MTGCardLibrary.parquet"
OUTPUT_PATH  = "ability_patterns_all_tiers.csv"


def split_clauses(text: str) -> list[str]:
    if not text:
        return []
    # crude sentence/line splitter
    return [c.strip() for c in re.split(r"[.\n;]+", text) if c.strip()]


def normalize_clause(c: str) -> str:
    """
    Normalize to group similar patterns:
    - lowercase
    - normalize mana symbols
    - normalize numbers
    - compress whitespace
    """
    c = c.lower()

    # replace mana symbols {1}{w}{u/b} -> {COST}
    c = re.sub(r"\{[0-9wubrgc/]+\}", "{COST}", c)

    # replace tap symbol specifically
    c = c.replace("{t}", "{TAP}")

    # replace plain integers with {N}
    c = re.sub(r"\d+", "{N}", c)

    # normalize spacing
    c = re.sub(r"\s+", " ", c).strip()

    return c


# ────────────────────────
# Tier heuristics
# ────────────────────────

def is_replacement_like(cl: str) -> bool:
    cl = cl.lower()
    has_instead_or_prevent = (" instead" in cl) or ("prevent " in cl)
    has_if_when_would_as = (
        " if " in cl
        or cl.startswith("if ")
        or " whenever " in cl
        or cl.startswith("whenever ")
        or " when " in cl
        or cl.startswith("when ")
        or " would " in cl
        or cl.startswith("as ")
    )
    return has_instead_or_prevent and has_if_when_would_as


def is_triggered_like(cl: str) -> bool:
    cl = cl.lower()
    return (
        cl.startswith("whenever ")
        or cl.startswith("when ")
        or cl.startswith("at the beginning")
        or " whenever " in cl
        or " at the beginning of " in cl
        or "at end of combat" in cl
        or "at the end of combat" in cl
    )


def is_activated_like(clause: str) -> bool:
    """
    Look for "COST: effect" style.
    Very rough but good enough for mining.
    """
    if ":" not in clause:
        return False

    cost_part, _ = clause.split(":", 1)
    cl_cost = cost_part.lower()

    if "{" in cost_part:
        return True  # mana symbols

    # common non-mana costs
    cost_markers = [
        "tap ", "untap ", "discard a card", "discard a creature card",
        "sacrifice a", "sacrifice another", "pay {n} life", "pay {cost}",
        "exile a", "exile this", "return", "remove a +1/+1 counter",
    ]
    return any(m in cl_cost for m in cost_markers)


def classify_tier(clause: str) -> str:
    """
    Order matters: replacement > triggered > activated > static/other
    """
    cl = clause.strip()
    if not cl:
        return "none"

    if is_replacement_like(cl):
        return "replacement"
    if is_triggered_like(cl):
        return "triggered"
    if is_activated_like(cl):
        return "activated"
    return "static_or_other"


# ────────────────────────
# Main mining pass
# ────────────────────────

def mine_all_tiers(parquet_path: str, out_csv: str) -> None:
    df = pd.read_parquet(parquet_path)

    rows = []

    for _, row in df.iterrows():
        oracle_text = row.get("oracle_text")
        if not isinstance(oracle_text, str) or not oracle_text.strip():
            continue

        for clause in split_clauses(oracle_text):
            if not clause:
                continue

            tier = classify_tier(clause)
            if tier == "none":
                continue

            norm = normalize_clause(clause)

            rows.append(
                {
                    "name": row.get("name", ""),
                    "oracle_id": row.get("oracle_id", ""),
                    "type_line": row.get("type_line", ""),
                    "tier": tier,                   # triggered / activated / replacement / static_or_other
                    "clause": clause,
                    "normalized_clause": norm,
                }
            )

    if not rows:
        print("No clauses found.")
        return

    cand_df = pd.DataFrame(rows)

    # one row per (tier, normalized_clause) pattern
    dedup_df = cand_df.drop_duplicates(
        subset=["tier", "normalized_clause"]
    ).sort_values(
        by=["tier", "normalized_clause", "name"]
    )

    dedup_df.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"Found {len(dedup_df)} unique (tier, pattern) combos.")
    print(f"Wrote patterns to: {out_csv}")


if __name__ == "__main__":
    mine_all_tiers(PARQUET_PATH, OUTPUT_PATH)



patterns_path = "ability_patterns_all_tiers.csv"

df = pd.read_csv(patterns_path)

# Collapse to unique patterns with counts
agg = (
    df.groupby(["tier", "normalized_clause"])
      .size()
      .reset_index(name="count")
      .sort_values(["tier", "count"], ascending=[True, False])
)

agg.to_csv("ability_pattern_library.csv", index=False)
print("Wrote ability_pattern_library.csv with", len(agg), "unique patterns.")

