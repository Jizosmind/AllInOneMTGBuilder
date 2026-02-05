from pathlib import Path
import re
import json
from collections import Counter

FILE_PATH = Path("MagicCompRules 20260116.txt")
OUT_PY = Path("mtg_keywords.py")
OUT_JSON = Path("mtg_keywords.json")

def normalize_label(label: str) -> str:
    # Strip parenthetical trailing notes if present
    label = re.sub(r"\s*\(.*?\)\s*$", "", label).strip()
    # normalize apostrophes/hyphens/spaces for enum member names
    return label

def to_enum_member(label: str) -> str:
    s = label.lower()
    s = s.replace("’", "'")
    s = s.replace("'", "")
    s = s.replace("-", "_")
    s = s.replace("/", "_")
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "unknown"
    if s[0].isdigit():
        s = f"k_{s}"
    return s.upper()

def extract_rule_headings(text: str, section: int, skip_nums: set[int] | None = None):
    """
    Extract headings like:
      702.2. Deathtouch
      701.4. Attach
    """
    if skip_nums is None:
        skip_nums = set()

    pat = re.compile(rf"^{section}\.(\d+)\.\s+([^\n]+?)\s*$", re.MULTILINE)
    out = []
    for m in pat.finditer(text):
        idx = int(m.group(1))
        if idx in skip_nums:
            continue

        raw = normalize_label(m.group(2))
        if raw:
            out.append((idx, raw))

    # de-dupe by label while preserving order
    seen = set()
    deduped = []
    for idx, raw in sorted(out, key=lambda x: x[0]):
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((idx, raw))
    return deduped


def unique_members(labels):
    """
    Ensure enum member names are unique even if normalization collides.
    """
    base = [to_enum_member(x) for x in labels]
    counts = Counter(base)
    used = Counter()
    result = []
    for name in base:
        if counts[name] == 1:
            result.append(name)
        else:
            used[name] += 1
            result.append(f"{name}_{used[name]}")
    return result

def render_enum(enum_name: str, labels):
    members = unique_members(labels)
    lines = [f"class {enum_name}(str, Enum):"]
    if not labels:
        lines.append("    pass")
        return "\n".join(lines)

    for mem, val in zip(members, labels):
        lines.append(f'    {mem} = "{val.lower()}"')
    return "\n".join(lines)

def main():
    text = FILE_PATH.read_text(encoding="utf-8")

    # 702 = keyword abilities, 701 = keyword actions
    keyword_abilities = extract_rule_headings(text, 702, skip_nums={1})
    keyword_actions   = extract_rule_headings(text, 701, skip_nums={1})

    ability_labels = [name for _, name in keyword_abilities]
    action_labels = [name for _, name in keyword_actions]

    py_parts = [
        "from enum import Enum",
        "",
        "# Auto-generated from Comprehensive Rules text",
        "",
        render_enum("KeywordAbility", ability_labels),
        "",
        render_enum("KeywordAction", action_labels),
        "",
    ]
    OUT_PY.write_text("\n".join(py_parts), encoding="utf-8")

    OUT_JSON.write_text(
        json.dumps(
            {
                "keyword_abilities": ability_labels,
                "keyword_actions": action_labels,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Done.")
    print(f"- abilities: {len(ability_labels)}")
    print(f"- actions:   {len(action_labels)}")
    print(f"Wrote {OUT_PY} and {OUT_JSON}")

if __name__ == "__main__":
    main()
