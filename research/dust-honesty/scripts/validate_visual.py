"""
Visual validation helpers for SQ1.

This script does two things:

1. `sample_scenes` — random stratified sample of 30 scenes from the
   Phase 1 corpus (76 months × 3 AOIs), with required quotas in the
   peak dust season (Mar–May) and the low dust season (Dec–Feb).

2. `make_thumbnail_grid` — 6×5 grid of RGB thumbnails of the sampled
   scenes, each labeled with date and AOI. Ahmed opens the resulting
   PNG and fills in `sq1_manual_labels.csv` row by row.

Run as a script to produce all SQ1 artifacts at once:

    python validate_visual.py
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio

from dbb_index import dbb_scene_mean

REPO = Path(__file__).resolve().parents[3]
PHASE1 = REPO / "data" / "phase1"
RESEARCH = REPO / "research" / "dust-honesty"
DATA = RESEARCH / "data"
FIGS = RESEARCH / "figures"
AOIS = ["qiddiya_core", "king_salman_park", "diriyah_gate"]

PEAK_DUST_MONTHS = {"03", "04", "05"}
LOW_DUST_MONTHS = {"12", "01", "02"}

N_TOTAL = 30
N_PEAK_MIN = 5
N_LOW_MIN = 5
SEED = 20260427


def all_scenes():
    scenes = []
    for aoi in AOIS:
        for tif in sorted((PHASE1 / aoi).glob("*.tif")):
            date = tif.stem  # YYYY-MM
            scenes.append({"date": date, "AOI": aoi, "scene_id": f"{aoi}/{date}", "path": tif})
    return scenes


def sample_scenes(scenes, n_total=N_TOTAL, n_peak_min=N_PEAK_MIN, n_low_min=N_LOW_MIN, seed=SEED):
    rng = random.Random(seed)

    peak = [s for s in scenes if s["date"][5:7] in PEAK_DUST_MONTHS]
    low = [s for s in scenes if s["date"][5:7] in LOW_DUST_MONTHS]
    other = [s for s in scenes if s["date"][5:7] not in (PEAK_DUST_MONTHS | LOW_DUST_MONTHS)]

    picked_peak = rng.sample(peak, n_peak_min)
    picked_low = rng.sample(low, n_low_min)

    chosen_ids = {s["scene_id"] for s in picked_peak + picked_low}
    remaining = [s for s in scenes if s["scene_id"] not in chosen_ids]
    n_remaining = n_total - n_peak_min - n_low_min
    picked_rest = rng.sample(remaining, n_remaining)

    sample = picked_peak + picked_low + picked_rest
    sample.sort(key=lambda s: (s["date"], s["AOI"]))
    return sample


def read_rgb(path, gamma=1.0, stretch=(2, 98)):
    """Read RGB from Phase 1 tif (B04/B03/B02 = bands 3/2/1) with percentile stretch."""
    with rasterio.open(path) as src:
        r = src.read(3).astype(np.float32)
        g = src.read(2).astype(np.float32)
        b = src.read(1).astype(np.float32)
    rgb = np.stack([r, g, b], axis=-1)
    finite = np.isfinite(rgb) & (rgb >= 0)
    if not finite.all():
        rgb = np.where(finite, rgb, 0)
    lo, hi = np.percentile(rgb[rgb > 0], stretch) if (rgb > 0).any() else (0.0, 1.0)
    rgb = np.clip((rgb - lo) / (hi - lo + 1e-6), 0, 1) ** (1.0 / gamma)
    return rgb


def make_thumbnail_grid(sample, out_path, cols=5, rows=6):
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3))
    for ax, scene in zip(axes.flat, sample):
        rgb = read_rgb(scene["path"])
        ax.imshow(rgb)
        ax.set_title(f"{scene['date']}  {scene['AOI']}", fontsize=9)
        ax.axis("off")
    for ax in axes.flat[len(sample):]:
        ax.axis("off")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def write_sample_csv(sample, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "AOI", "scene_id"])
        for s in sample:
            w.writerow([s["date"], s["AOI"], s["scene_id"]])


def write_labels_template(sample, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "AOI", "scene_id", "label", "notes"])
        for s in sample:
            # label values: clean | light_haze | heavy_dust | cloud | mixed
            w.writerow([s["date"], s["AOI"], s["scene_id"], "", ""])


def write_dbb_values(sample, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in sample:
        dbb = dbb_scene_mean(s["path"])
        rows.append({"date": s["date"], "AOI": s["AOI"], "scene_id": s["scene_id"], "dbb_mean": dbb})
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "AOI", "scene_id", "dbb_mean"])
        w.writeheader()
        w.writerows(rows)
    return rows


def histogram(rows, out_path):
    vals = [r["dbb_mean"] for r in rows if np.isfinite(r["dbb_mean"])]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(vals, bins=15, color="#b4793b", edgecolor="black")
    ax.set_xlabel("DBB index (scene mean)")
    ax.set_ylabel("count")
    ax.set_title(f"DBB distribution across n={len(vals)} sampled scenes")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return vals


def main():
    scenes = all_scenes()
    print(f"Corpus: {len(scenes)} scenes ({len(AOIS)} AOIs × ~{len(scenes)//len(AOIS)} months)")

    sample = sample_scenes(scenes)
    print(f"Sampled: {len(sample)} scenes (seed={SEED})")

    write_sample_csv(sample, DATA / "sq1_sample.csv")
    write_labels_template(sample, DATA / "sq1_manual_labels.csv")
    make_thumbnail_grid(sample, FIGS / "sq1_thumbnails.png")

    rows = write_dbb_values(sample, DATA / "sq1_dbb_values.csv")
    vals = histogram(rows, FIGS / "sq1_dbb_histogram.png")
    arr = np.array(vals)
    print(f"DBB mean across sample: {arr.mean():+.4f}  std: {arr.std():.4f}  range: {arr.min():+.4f}..{arr.max():+.4f}")

    print("\nWrote:")
    print(f"  {DATA / 'sq1_sample.csv'}")
    print(f"  {DATA / 'sq1_manual_labels.csv'}  (template, label column blank)")
    print(f"  {DATA / 'sq1_dbb_values.csv'}")
    print(f"  {FIGS / 'sq1_thumbnails.png'}")
    print(f"  {FIGS / 'sq1_dbb_histogram.png'}")


if __name__ == "__main__":
    main()
