"""
SA5 — V4 ∩ bare_epoch_flag anchor probe (pre-registered halt mechanism, §SA5).

Pure date math over piece B's V4 fire table and SA1's S30 BSI table. No EE,
no Sentinel Hub. Sub-minute runtime. This is the SA5 halt-floor probe per
pre-reg, not a separate sub-question — runs without sa5_implementation.md
because the halt mechanism itself is fully specified at pre-reg level
(post Amendment 01 redirect).

Anchor definition (post Amendment 01)
-------------------------------------
Pre-reg §SA5 reference labels: "scenes flagged V4-fire (piece B SQ2 output)
AND high-BSI (Q4 from SA2)". Amendment 01 (locked d1eba5a) substitutes
"bare_epoch_flag from SA1" for "Q4 from SA2" — content-identical because
SA1's bare_epoch_flag is the per-AOI 75th-percentile BSI cut, which is
the same threshold SA2's Q4 would have produced.

Anchor = scene where (V4 fired in piece B SQ2) AND (bare_epoch_flag == True
in SA1 S30 baseline). Date-join on scene_date.

In-scope AOIs
-------------
Pre-reg §SA5 specifies the anchor density floor at Qiddiya only ("Build two
change maps over the 76-month window at Qiddiya. ... V4-anchor cell count
< 15 at Qiddiya"). KSP and Diriyah are out-of-scope per pre-reg for the
SA5 false-positive design. They are included in the summary CSV as
diagnostic rows (no halt_status) for sa5_implementation.md drafting if
Qiddiya clears, but receive NO halt receipts.

Cloud / filtering parity
------------------------
V4 table is already the post-filter input (piece B SQ2 encoded its cloud
handling there). bare_epoch_flag in SA1 already implies cf<0.10. No
additional filtering applied here.

AOI naming map
--------------
piece B operational table       <-> piece A SA1 CSVs
qiddiya_core                    <-> qiddiya
king_salman_park                <-> ksp
diriyah_gate                    <-> diriyah

Outputs
-------
  data/sa5_anchor_probe/anchor_summary.csv
    aoi, in_scope, v4_fired_n, bare_epoch_flag_true_n, anchors_n,
    anchor_floor, halt_status
  data/halts/sa5_anchors/qiddiya.md
    Qiddiya-only halt receipt (CLEAR or HALT framing).
"""

from __future__ import annotations

import csv
import datetime as dt
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SA1_DIR = REPO_ROOT / "research/construction-substrate-by-site/data/sa1_bsi_baseline"
V4_TABLE = REPO_ROOT / "research/dust-honesty/data/operational/dbb_operational_sq2.csv"
OUT_DATA_DIR = REPO_ROOT / "research/construction-substrate-by-site/data/sa5_anchor_probe"
OUT_HALT_DIR = REPO_ROOT / "research/construction-substrate-by-site/data/halts/sa5_anchors"

ANCHOR_FLOOR = 15

AOIS = [
    # (slug, label, piece_b_aoi_name, in_scope)
    ("qiddiya", "Qiddiya", "qiddiya_core", True),
    ("ksp", "King Salman Park", "king_salman_park", False),
    ("diriyah", "Diriyah Gate", "diriyah_gate", False),
]


def load_v4_dates(piece_b_aoi: str) -> set[dt.date]:
    fired: set[dt.date] = set()
    with open(V4_TABLE, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("aoi") != piece_b_aoi:
                continue
            if row.get("flag_v4") != "True":
                continue
            try:
                fired.add(dt.date.fromisoformat(row["scene_date"]))
            except (KeyError, ValueError):
                continue
    return fired


def load_bare_epoch_dates(slug: str) -> set[dt.date]:
    bare: set[dt.date] = set()
    csv_path = SA1_DIR / f"{slug}_s30_bsi_per_scene.csv"
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("bare_epoch_flag") != "True":
                continue
            try:
                bare.add(dt.date.fromisoformat(row["scene_date"]))
            except (KeyError, ValueError):
                continue
    return bare


def write_qiddiya_receipt(out_path: Path, v4_n: int, bare_n: int, anchors_n: int) -> None:
    halted = anchors_n < ANCHOR_FLOOR
    decision = "HALT" if halted else "CLEAR"
    relation = "<" if halted else ">="
    if halted:
        downstream = (
            "SA5 false-positive comparison (Pipeline A vs Pipeline B at Qiddiya) "
            "cannot proceed with the pre-registered anchor density. SA5B "
            "(expanded-window framing) is pre-scoped per pre-reg §SA5 but does "
            "NOT auto-invoke; it requires its own pre-registration before "
            "execution per locked decisions in CLAUDE.md. The alternate "
            "framing — drop the false-positive design entirely and report "
            "only SA3+SA4 mechanism findings — is also explicitly named in "
            "the pre-reg as a valid path forward."
        )
    else:
        downstream = (
            "Qiddiya cleared the V4 ∩ bare_epoch_flag anchor density floor. "
            "SA5 false-positive comparison can proceed once "
            "sa5_implementation.md locks the under-specified items "
            "(Δ(NDVI) construction at non-fired scenes, Pipeline A/B exact "
            "operationalization beyond the 0.05 threshold, false-positive "
            "denominator definition, bootstrap or per-anchor reporting "
            "convention)."
        )
    body = f"""# SA5 anchor probe -- Qiddiya ({decision})

**Pre-registered halt rule (piece A §SA5):** V4-anchor cell count < 15 at Qiddiya implies insufficient anchor density for the false-positive comparison. Defer to SA5B (expanded window) or drop the false-positive design entirely and report only SA3+SA4 mechanism findings. SA5B requires its own pre-registration before execution.

**Anchor definition (post Amendment 01, locked d1eba5a):** scene where piece B SQ2 V4-fire AND SA1 bare_epoch_flag == True (the per-AOI 75th-percentile BSI cut, content-identical to SA2 Q4).

## Numbers

- AOI: Qiddiya
- V4-fired scenes (piece B SQ2, aoi=qiddiya_core, flag_v4=True): {v4_n}
- Bare-epoch scenes (SA1 S30, bare_epoch_flag=True): {bare_n}
- Anchors (intersection on scene_date): {anchors_n}
- Anchor floor: {ANCHOR_FLOOR}
- Decision: {decision} (anchors {relation} threshold)

## Effect on outputs

{downstream}

## Why this halt threshold and not a workaround

Per piece B stop-rule philosophy carried into piece A: when a halt fires, the cheapest possible scope review is the one happening mid-run. Lowering the anchor floor post-hoc to admit the result, or substituting a different anchor definition that produces more anchors, would conflate "this AOI doesn't have enough V4 ∩ bare_epoch overlap" with "we should answer a different question." The halt is the finding. The V4 ∩ bare_epoch_flag count at Qiddiya is itself diagnostic information about the joint distribution of vegetation-flush events and substrate-dominated scenes at this site under piece B's V4 ramp test and SA1's 75th-percentile BSI cut.
"""
    out_path.write_text(body)


def main() -> None:
    OUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HALT_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    qiddiya_anchor_count = None
    qiddiya_v4 = None
    qiddiya_bare = None

    for slug, label, piece_b_name, in_scope in AOIS:
        v4_dates = load_v4_dates(piece_b_name)
        bare_dates = load_bare_epoch_dates(slug)
        anchors = v4_dates & bare_dates
        anchors_n = len(anchors)

        if in_scope:
            halted = anchors_n < ANCHOR_FLOOR
            halt_status = "HALT" if halted else "CLEAR"
        else:
            halt_status = "out_of_scope"

        summary_rows.append({
            "aoi": slug,
            "in_scope": str(in_scope),
            "v4_fired_n": len(v4_dates),
            "bare_epoch_flag_true_n": len(bare_dates),
            "anchors_n": anchors_n,
            "anchor_floor": ANCHOR_FLOOR,
            "halt_status": halt_status,
        })

        print(
            f"{label:20s}  in_scope={str(in_scope):5s}  "
            f"V4={len(v4_dates):4d}  bare={len(bare_dates):4d}  "
            f"anchors={anchors_n:4d}  -> {halt_status}"
        )

        if slug == "qiddiya":
            qiddiya_anchor_count = anchors_n
            qiddiya_v4 = len(v4_dates)
            qiddiya_bare = len(bare_dates)

    summary_path = OUT_DATA_DIR / "anchor_summary.csv"
    tmp_path = summary_path.with_suffix(".csv.tmp")
    with open(tmp_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    os.replace(tmp_path, summary_path)
    print(f"\nWrote {summary_path}")

    write_qiddiya_receipt(
        OUT_HALT_DIR / "qiddiya.md",
        v4_n=qiddiya_v4,
        bare_n=qiddiya_bare,
        anchors_n=qiddiya_anchor_count,
    )
    print(f"Wrote Qiddiya receipt under {OUT_HALT_DIR}")


if __name__ == "__main__":
    main()
