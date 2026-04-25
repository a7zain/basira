"""
Phase 1 — RGB Timelapse Generator
==================================
Reads monthly 6-band GeoTIFFs from data/phase1/<aoi>/, stacks B04/B03/B02
as RGB, and writes an animated timelapse (GIF and/or MP4) with a date
label and optional polygon outline overlay.

Usage:
    python src/phase1_timelapse.py --aoi <name> [--format gif|mp4|both]
                                   [--fps 4] [--contrast stretch|percentile]
                                   [--no-outline]
"""

import argparse
import glob
import os
import re
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from phase1_aois import get_aoi, list_primary_aois, list_subregions, AOIS

DATA_ROOT = "data/phase1"
OUT_DIR = "outputs/phase1"
TARGET_CRS = "EPSG:32638"
MIN_LONG_EDGE = 800  # px


def list_monthly_tifs(aoi_key):
    pattern = os.path.join(DATA_ROOT, aoi_key, "*.tif")
    files = sorted(glob.glob(pattern))
    out = []
    for f in files:
        m = re.search(r"(\d{4})-(\d{2})\.tif$", f)
        if m:
            out.append((int(m.group(1)), int(m.group(2)), f))
    return out


def load_rgb_array(path):
    """Return (rgb float32 array HxWx3, bounds) with bands in R,G,B order (B04,B03,B02)."""
    with rasterio.open(path) as src:
        red = src.read(3).astype(np.float32)
        green = src.read(2).astype(np.float32)
        blue = src.read(1).astype(np.float32)
        bounds = src.bounds
    rgb = np.stack([red, green, blue], axis=-1)
    return rgb, bounds


def compute_fixed_stretch(paths, sample_n=12):
    """Compute a single (lo, hi) joint across RGB across up to sample_n evenly spaced scenes."""
    if len(paths) > sample_n:
        idx = np.linspace(0, len(paths) - 1, sample_n).astype(int)
        sample_paths = [paths[i] for i in idx]
    else:
        sample_paths = paths

    stacks = [[], [], []]
    for p in sample_paths:
        try:
            rgb, _ = load_rgb_array(p)
        except Exception as e:
            print(f"    warn: {p} — {e}", file=sys.stderr)
            continue
        for b in range(3):
            band = rgb[:, :, b]
            valid = band[band > 0]
            if valid.size:
                # Sub-sample to keep memory bounded
                if valid.size > 200_000:
                    valid = np.random.default_rng(0).choice(valid, 200_000, replace=False)
                stacks[b].append(valid)

    # Joint stretch across all three bands — preserves color balance.
    parts = [a for s in stacks for a in s]
    if not parts:
        return (0.0, 1.0)
    arr = np.concatenate(parts)
    return (float(np.percentile(arr, 1)), float(np.percentile(arr, 99)))


def stretch_rgb(rgb, mode, fixed_lo_hi=None):
    """Return uint8 HxWx3 image. Joint linear stretch + mild gamma."""
    GAMMA = 1.4
    out = np.zeros_like(rgb)
    for b in range(3):
        band = rgb[:, :, b]
        if mode == "stretch" and fixed_lo_hi is not None:
            lo, hi = fixed_lo_hi
        else:
            valid = band[band > 0]
            if valid.size == 0:
                out[:, :, b] = 0
                continue
            lo, hi = np.percentile(valid, 1), np.percentile(valid, 99)
        if hi > lo:
            out[:, :, b] = np.clip((band - lo) / (hi - lo), 0, 1)
        else:
            out[:, :, b] = 0
    out = out ** (1.0 / GAMMA)
    return (out * 255).astype(np.uint8)


def upscale_nn(img_uint8, min_long_edge=MIN_LONG_EDGE):
    """Nearest-neighbor upscale so the long edge is at least min_long_edge."""
    h, w = img_uint8.shape[:2]
    long_edge = max(h, w)
    if long_edge >= min_long_edge:
        return img_uint8, 1
    scale = int(np.ceil(min_long_edge / long_edge))
    # Integer replication (preserves pixel identity)
    up = np.repeat(np.repeat(img_uint8, scale, axis=0), scale, axis=1)
    return up, scale


def polygon_pixel_coords(polygon_lonlat, bounds, img_w, img_h, scale):
    """Transform WGS84 polygon → pixel coords of the upscaled image."""
    t = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    west, south, east, north = bounds.left, bounds.bottom, bounds.right, bounds.top
    orig_w = img_w // scale
    orig_h = img_h // scale
    pts = []
    for lon, lat in polygon_lonlat:
        x, y = t.transform(lon, lat)
        px = (x - west) / (east - west) * orig_w * scale
        py = (north - y) / (north - south) * orig_h * scale
        pts.append((px, py))
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _load_font(size):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def annotate_frame(img_uint8, date_label):
    """Return annotated PIL Image (RGB) with date label only."""
    pil = Image.fromarray(img_uint8, mode="RGB")
    draw = ImageDraw.Draw(pil, "RGBA")

    font_size = max(18, pil.width // 40)
    font = _load_font(font_size)

    x, y = 12, 10
    # Thin black outline: draw text in 8 offset positions
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), date_label, font=font, fill=(0, 0, 0, 255))
    draw.text((x, y), date_label, font=font, fill=(255, 255, 255, 255))

    return pil


def build_frames(aoi_key, contrast_mode):
    scenes = list_monthly_tifs(aoi_key)
    if not scenes:
        print(f"ERROR: no .tif under {DATA_ROOT}/{aoi_key}/", file=sys.stderr)
        return []

    print(f"  Found {len(scenes)} monthly scenes")

    fixed_lo_hi = None
    if contrast_mode == "stretch":
        print("  Computing fixed stretch across stack...")
        fixed_lo_hi = compute_fixed_stretch([p for _, _, p in scenes])
        lo, hi = fixed_lo_hi
        print(f"    joint RGB: {lo:.4f} → {hi:.4f}")

    frames = []
    for y, m, path in scenes:
        label = f"{y}-{m:02d}"
        try:
            rgb, _bounds = load_rgb_array(path)
        except Exception as e:
            print(f"  WARN [{label}] skipping — {e}", file=sys.stderr)
            continue

        if not np.any(rgb):
            print(f"  WARN [{label}] empty raster — skipping")
            continue

        img8 = stretch_rgb(rgb, contrast_mode, fixed_lo_hi)
        img8, _scale = upscale_nn(img8)
        h, w = img8.shape[:2]

        pil = annotate_frame(img8, label)
        frames.append(np.array(pil))
        print(f"  frame [{label}] {w}x{h}")

    return frames


def write_gif(frames, out_path, fps):
    import imageio.v2 as imageio
    duration = 1.0 / fps
    imageio.mimsave(out_path, frames, duration=duration, loop=0)
    return os.path.getsize(out_path)


_MP4_PARAMS = dict(
    codec="libx264",
    pixelformat="yuv420p",
    output_params=["-crf", "18", "-preset", "slow",
                   "-movflags", "+faststart", "-an"],
    macro_block_size=1,
)


def write_mp4_native(frames, out_path, fps):
    """Encode frames at their native dimensions (crop 1px if odd, no padding)."""
    import imageio.v2 as imageio

    h, w = frames[0].shape[:2]
    new_w, new_h = w - (w % 2), h - (h % 2)
    if (new_w, new_h) != (w, h):
        frames = [f[:new_h, :new_w] for f in frames]

    imageio.mimsave(out_path, frames, fps=fps, **_MP4_PARAMS)
    return os.path.getsize(out_path)


def write_mp4_blurred(frames, out_path, fps,
                      target_w=1920, target_h=1080,
                      blur_radius=30, bg_brightness=0.85, fg_margin=0.05):
    """Per-frame composite: blurred cover-fill background + sharp fit-with-margin
    foreground from the SAME frame. Background changes with the foreground."""
    import imageio.v2 as imageio

    h, w = frames[0].shape[:2]
    bg_scale = max(target_w / w, target_h / h)
    bg_w = int(np.ceil(w * bg_scale))
    bg_h = int(np.ceil(h * bg_scale))
    bg_left = (bg_w - target_w) // 2
    bg_top = (bg_h - target_h) // 2

    fg_scale = min(target_w * (1 - 2 * fg_margin) / w,
                   target_h * (1 - 2 * fg_margin) / h)
    fg_w = int(round(w * fg_scale))
    fg_h = int(round(h * fg_scale))
    fg_w -= fg_w % 2
    fg_h -= fg_h % 2
    fg_off_x = (target_w - fg_w) // 2
    fg_off_y = (target_h - fg_h) // 2

    out_frames = []
    for f in frames:
        src = Image.fromarray(f, mode="RGB")
        bg = src.resize((bg_w, bg_h), Image.LANCZOS)
        bg = bg.crop((bg_left, bg_top, bg_left + target_w, bg_top + target_h))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        bg = ImageEnhance.Brightness(bg).enhance(bg_brightness)
        fg = src.resize((fg_w, fg_h), Image.LANCZOS)
        bg.paste(fg, (fg_off_x, fg_off_y))
        out_frames.append(np.array(bg))

    imageio.mimsave(out_path, out_frames, fps=fps, **_MP4_PARAMS)
    return os.path.getsize(out_path)


def parse_args():
    p = argparse.ArgumentParser(description="Phase 1 RGB timelapse")
    p.add_argument("--aoi", required=True, choices=list_primary_aois())
    p.add_argument("--format", choices=["gif", "mp4", "both"], default="gif")
    p.add_argument("--fps", type=int, default=6)
    p.add_argument("--contrast", choices=["stretch", "percentile"],
                   default="percentile",
                   help="'stretch' = fixed across stack; 'percentile' = per-frame")
    p.add_argument("--variant", choices=["native", "blurred"], default="native",
                   help="MP4 variant: native dims, or 1920x1080 blurred-context composite")
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    frames = build_frames(args.aoi, args.contrast)
    if not frames:
        print("No frames produced; aborting.")
        sys.exit(1)

    print(f"  Writing {len(frames)} frames at {args.fps} fps")
    base = os.path.join(OUT_DIR, f"{args.aoi}_timelapse")

    if args.format in ("gif", "both"):
        size = write_gif(frames, base + ".gif", args.fps)
        print(f"  Saved: {base}.gif ({size/1e6:.1f} MB)")
    if args.format in ("mp4", "both"):
        out = f"{base}_{args.variant}.mp4"
        if args.variant == "native":
            size = write_mp4_native(frames, out, args.fps)
        else:
            size = write_mp4_blurred(frames, out, args.fps)
        print(f"  Saved: {out} ({size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
