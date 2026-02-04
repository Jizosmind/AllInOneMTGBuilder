from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


def is_stale(path: Path, max_age_days: int) -> bool:
    """Return True if path is missing or older than max_age_days."""
    if not path.exists():
        return True
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds > (max_age_days * 24 * 60 * 60)


def run_script(script: Path, cwd: Path) -> None:
    """Run a python script in a given working directory."""
    if not script.exists():
        raise FileNotFoundError(f"Script not found: {script}")

    print(f"\n=== Running: {script.name} (cwd={cwd}) ===")
    subprocess.check_call([sys.executable, str(script)], cwd=str(cwd))


def ensure_library(root: Path, max_age_days: int, force: bool) -> Path:
    """Ensure MTGCardLibrary.parquet exists and is fresh; download if not."""
    parquet = root / "MTGCardLibrary.parquet"
    if force or is_stale(parquet, max_age_days):
        if parquet.exists():
            print(f"\nLibrary parquet is stale: {parquet}")
        else:
            print(f"\nLibrary parquet missing: {parquet}")
        run_script(root / "downloadLibrary.py", cwd=root)

    if not parquet.exists():
        raise FileNotFoundError(
            f"Expected {parquet} to exist after download step, but it does not."
        )
    return parquet


def ensure_filtered(root: Path, raw_path: Path, force: bool) -> Path:
    """Ensure MTGCardLibrary_filtered.parquet exists and is >= raw mtime; clean if not."""
    filtered = root / "MTGCardLibrary_filtered.parquet"

    needs = force or (not filtered.exists()) or (filtered.stat().st_mtime < raw_path.stat().st_mtime)
    if needs:
        if filtered.exists():
            print(f"\nFiltered parquet older than raw (or --force-clean): {filtered}")
        else:
            print(f"\nFiltered parquet missing: {filtered}")
        run_script(root / "cleanAndAnalyzeData.py", cwd=root)

    if not filtered.exists():
        raise FileNotFoundError(
            f"Expected {filtered} to exist after cleaning step, but it does not."
        )
    return filtered


def run_atom_smoketest(root: Path, sample: int, seed: int) -> None:
    """Run the existing card_effects random atom test."""
    if sample <= 0:
        return

    # Make sure imports resolve relative to the project folder.
    sys.path.insert(0, str(root))

    import importlib

    card_effects = importlib.import_module("card_effects")
    if not hasattr(card_effects, "test_random_cards_atoms"):
        raise AttributeError("card_effects.test_random_cards_atoms not found.")

    print(f"\n=== Atom smoketest: {sample} random cards (seed={seed}) ===")
    card_effects.test_random_cards_atoms(num_samples=sample, seed=seed)


def build_engine_table(root: Path, data_path: Path, out_path: Path) -> None:
    """Build engine table from card_effects and write it."""
    sys.path.insert(0, str(root))
    import importlib

    card_effects = importlib.import_module("card_effects")
    if not hasattr(card_effects, "build_engine_table"):
        raise AttributeError("card_effects.build_engine_table not found.")

    print(f"\n=== Building engine table from: {data_path.name} ===")
    df = pd.read_parquet(data_path)

    # build_engine_table expects a DataFrame of cards.
    out_df = card_effects.build_engine_table(df)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)
    print(f"Wrote: {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AllInOneMTGBuilder pipeline orchestrator")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project directory containing downloadLibrary.py, cleanAndAnalyzeData.py, card_effects.py",
    )
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--use-filtered", action="store_true")
    parser.add_argument("--force-clean", action="store_true")
    parser.add_argument("--sample", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--build-engine", action="store_true")
    parser.add_argument("--engine-out", type=Path, default=Path("outputs/engine_table.parquet"))

    args = parser.parse_args()

    root = args.root or Path(__file__).resolve().parent

    # IMPORTANT: match your existing scripts which read/write relative paths.
    os.chdir(root)

    print(f"Project root: {root}")

    raw_path = ensure_library(root, max_age_days=args.max_age_days, force=args.force_download)

    data_path = raw_path
    if args.use_filtered:
        data_path = ensure_filtered(root, raw_path=raw_path, force=args.force_clean)

    run_atom_smoketest(root, sample=args.sample, seed=args.seed)

    if args.build_engine:
        build_engine_table(root, data_path=data_path, out_path=root / args.engine_out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
