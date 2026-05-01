"""
SQ1C label review — researcher confirmation of AI pre-labels.

Walks each row of sq1c_<aoi>_relabel.csv, opens the per-scene thumbnail in
the macOS default viewer, prompts for confirm-or-override, and autosaves
back to the same CSV row-by-row.

Two protocols:

  STANDARD — AI pre-label is shown; pressing Enter confirms it. The common
  case for the 37 rows that were not bias-exposed during AI pre-labeling.

  COLD — AI pre-label is HIDDEN. The 6 rows flagged
  bias_exposed_during_ai_labeling=True must be cold-labeled blind to break
  the contamination chain. No default; must type a choice explicitly.

UVAI value is NEVER printed at labeling time, regardless of protocol. UVAI
is selector and post-hoc audit, never input. (Locked 2026-04-30 after the
6-row contamination incident; same rule applied to the researcher.)

Usage:
    python sq1c_label_review.py --aoi qiddiya
    python sq1c_label_review.py --aoi ksp
    python sq1c_label_review.py --aoi diriyah
    python sq1c_label_review.py --aoi qiddiya --no-resume   # re-prompt all rows

Autosaves every row immediately, so a Ctrl+C / quit mid-pass loses nothing.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/dust-honesty/data"

AOI_ALIASES = {
    "ksp": "king_salman_park",
    "king_salman_park": "king_salman_park",
    "qiddiya": "qiddiya_core",
    "qiddiya_core": "qiddiya_core",
    "diriyah": "diriyah_gate",
    "diriyah_gate": "diriyah_gate",
}

LABEL_KEYS = {
    "c": "clean",
    "l": "light_haze",
    "h": "heavy_dust",
    "m": "mixed",
    "cl": "cloud",
}

VALID_LABELS = set(LABEL_KEYS.values())


def relabel_path(aoi: str) -> Path:
    return DATA / f"sq1c_{aoi}_relabel.csv"


def thumb_dir(aoi: str) -> Path:
    return DATA / f"sq1c_{aoi}_test_thumbnails"


def thumb_path(aoi: str, date: str) -> Path:
    return thumb_dir(aoi) / f"{date}.png"


def load_rows(path: Path):
    with open(path) as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    return fieldnames, rows


def save_rows(path: Path, fieldnames, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def open_thumbnail(path: Path):
    if not path.exists():
        print(f"  [WARN] thumbnail not found: {path}")
        return False
    # -g keeps focus in terminal so the keypress flow doesn't break.
    subprocess.run(["open", "-g", str(path)], check=True)
    time.sleep(0.3)
    return True


def is_bias_exposed(row) -> bool:
    v = row.get("bias_exposed_during_ai_labeling", "False")
    return str(v).strip().lower() == "true"


def is_already_confirmed(row) -> bool:
    return bool(str(row.get("confirmed_label", "")).strip())


def remaining_counts(rows):
    """Return (total, confirmed, std_remaining, cold_remaining)."""
    total = len(rows)
    confirmed = sum(1 for r in rows if is_already_confirmed(r))
    std_remaining = sum(
        1 for r in rows
        if not is_already_confirmed(r) and not is_bias_exposed(r)
    )
    cold_remaining = sum(
        1 for r in rows
        if not is_already_confirmed(r) and is_bias_exposed(r)
    )
    return total, confirmed, std_remaining, cold_remaining


def prompt_label(protocol: str, ai_prelabel: str) -> str | None:
    """
    Returns:
      - one of VALID_LABELS on confirmed/override choice
      - "__skip__"  when user types 's' (leave blank, revisit later)
      - "__quit__"  when user types 'q' (save and exit)
    """
    options = "[c]lean / [l]ight_haze / [h]eavy_dust / [m]ixed / [cl]oud / [s]kip / [q]uit"
    if protocol == "standard":
        prompt = f"label> (Enter = confirm AI '{ai_prelabel}')   {options}\n> "
    else:
        prompt = f"label> (no default — type a choice)   {options}\n> "
    while True:
        try:
            raw = input(prompt).strip().lower()
        except EOFError:
            return "__quit__"
        if raw == "":
            if protocol == "standard":
                if ai_prelabel in VALID_LABELS:
                    return ai_prelabel
                print(f"  AI prelabel '{ai_prelabel}' not in valid labels; type a choice.")
                continue
            print("  Cold protocol: no default. Type a single-letter choice.")
            continue
        if raw == "q":
            return "__quit__"
        if raw == "s":
            return "__skip__"
        if raw in LABEL_KEYS:
            return LABEL_KEYS[raw]
        print(f"  Unrecognized: '{raw}'. Choices: c / l / h / m / cl / s / q.")


def prompt_notes() -> str:
    try:
        raw = input("notes> (Enter to skip)\n> ").strip()
    except EOFError:
        return ""
    return raw


def review_aoi(aoi_canonical: str, resume: bool):
    csv_path = relabel_path(aoi_canonical)
    if not csv_path.exists():
        print(f"ERROR: relabel CSV not found: {csv_path}", file=sys.stderr)
        return 1
    fieldnames, rows = load_rows(csv_path)

    required_cols = {
        "confirmed_label", "reviewer_notes", "confirmed_at", "review_protocol",
    }
    missing = required_cols - set(fieldnames)
    if missing:
        print(f"ERROR: relabel CSV missing columns: {sorted(missing)}", file=sys.stderr)
        print("Run the schema-add step first (Unit 1 of session 2026-05-01).", file=sys.stderr)
        return 1

    total, confirmed_at_start, std_rem, cold_rem = remaining_counts(rows)
    print(f"AOI: {aoi_canonical} | total rows: {total} | "
          f"already confirmed: {confirmed_at_start} | "
          f"remaining: {std_rem} standard / {cold_rem} cold")
    print(f"Source CSV: {csv_path}")
    print(f"Thumbnail dir: {thumb_dir(aoi_canonical)}")
    print()

    quit_requested = False
    for idx, row in enumerate(rows):
        if quit_requested:
            break
        if resume and is_already_confirmed(row):
            continue

        bias = is_bias_exposed(row)
        protocol = "cold" if bias else "standard"
        date = row.get("date", "")
        s2 = row.get("s2_system_index", "")
        cloud = row.get("s2_cloud_pct", "")
        ai_prelabel = row.get("ai_prelabel", "").strip()

        # Header per row.
        print("=" * 72)
        print(f"Row {idx + 1}/{total}  |  AOI: {aoi_canonical}  |  Date: {date}")
        print(f"Scene: {s2}")
        if cloud:
            print(f"S2 cloud%: {cloud}")
        if protocol == "standard":
            print(f"AI pre-label: {ai_prelabel}  (researcher: confirm or override)")
            print("Reviewer protocol: STANDARD")
        else:
            print("Reviewer protocol: COLD (no AI label visible — label this row blind)")
            print("[AI label HIDDEN. UVAI HIDDEN. This row was bias-exposed during AI")
            print(" pre-labeling; cold-labeling now to break contamination chain.]")
        print()

        thumb = thumb_path(aoi_canonical, date)
        opened = open_thumbnail(thumb)
        if not opened:
            print("  Skipping thumbnail open; you can still type a label from memory.")

        choice = prompt_label(protocol, ai_prelabel if protocol == "standard" else "")
        if choice == "__quit__":
            print("  Quit requested. Saving progress.")
            quit_requested = True
            break
        if choice == "__skip__":
            print("  Skipped (will revisit on next run).")
            print()
            continue

        notes = prompt_notes()
        now_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row["confirmed_label"] = choice
        row["reviewer_notes"] = notes
        row["confirmed_at"] = now_iso
        row["review_protocol"] = protocol

        save_rows(csv_path, fieldnames, rows)

        # Running counter.
        _, confirmed_now, std_left, cold_left = remaining_counts(rows)
        print(f"  Saved. [{confirmed_now}/{total} confirmed | "
              f"{std_left} standard / {cold_left} cold remaining for this AOI]")
        print()

    # Summary.
    total, confirmed_end, std_rem_end, cold_rem_end = remaining_counts(rows)
    print("=" * 72)
    print(f"End-of-AOI summary: {aoi_canonical}")
    print(f"  Total rows         : {total}")
    print(f"  Confirmed          : {confirmed_end} (was {confirmed_at_start})")
    print(f"  Still unlabeled    : {std_rem_end + cold_rem_end} "
          f"({std_rem_end} standard, {cold_rem_end} cold)")

    agree = 0
    override = 0
    overrides_by_dir = {}
    for r in rows:
        cl = r.get("confirmed_label", "").strip()
        ai = r.get("ai_prelabel", "").strip()
        if not cl:
            continue
        if cl == ai:
            agree += 1
        else:
            override += 1
            key = f"{ai} -> {cl}"
            overrides_by_dir[key] = overrides_by_dir.get(key, 0) + 1
    print(f"  AI agreement       : {agree}")
    print(f"  Overrides          : {override}")
    if overrides_by_dir:
        print("    direction:")
        for k, v in sorted(overrides_by_dir.items(), key=lambda kv: -kv[1]):
            print(f"      {k}: {v}")
    print()
    print("UVAI cross-check happens AFTER confirmation (sq1c_label_comparison.py).")
    return 0


def main():
    p = argparse.ArgumentParser(
        description="SQ1C researcher confirmation pass — walks one AOI at a time, "
                    "autosaves per row. Cold protocol for the 6 bias_exposed rows; "
                    "UVAI is never shown at labeling time.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--aoi", required=True, choices=sorted(AOI_ALIASES.keys()),
        help="Which AOI's relabel CSV to walk. Aliases: ksp, qiddiya, diriyah.",
    )
    p.add_argument(
        "--resume", dest="resume", action="store_true", default=True,
        help="Skip rows that already have confirmed_label (default).",
    )
    p.add_argument(
        "--no-resume", dest="resume", action="store_false",
        help="Re-prompt every row, including ones already confirmed.",
    )
    args = p.parse_args()
    aoi_canonical = AOI_ALIASES[args.aoi]
    return review_aoi(aoi_canonical, args.resume)


if __name__ == "__main__":
    sys.exit(main())
