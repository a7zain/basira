import numpy as np
import rasterio
import matplotlib.pyplot as plt
import xml.etree.ElementTree as ET

RAW = "data/raw"
IMG_2022 = f"{RAW}/S1A_IW_GRDH_1SDV_20220125T145758_20220125T145823_041619_04F365_5BEC_COG.SAFE/measurement/s1a-iw-grd-vv-20220125t145758-20220125t145823-041619-04f365-001-cog.tiff"
XML_2022 = f"{RAW}/S1A_IW_GRDH_1SDV_20220125T145758_20220125T145823_041619_04F365_5BEC_COG.SAFE/annotation/s1a-iw-grd-vv-20220125t145758-20220125t145823-041619-04f365-001-cog.xml"
IMG_2024 = f"{RAW}/S1A_IW_GRDH_1SDV_20240220T145743_20240220T145808_052644_065E6B_9C85_COG.SAFE/measurement/s1a-iw-grd-vv-20240220t145743-20240220t145808-052644-065e6b-001-cog.tiff"
XML_2024 = f"{RAW}/S1A_IW_GRDH_1SDV_20240220T145743_20240220T145808_052644_065E6B_9C85_COG.SAFE/annotation/s1a-iw-grd-vv-20240220t145743-20240220t145808-052644-065e6b-001-cog.xml"

# Riyadh city center bounding box
RIYADH_LAT_MIN, RIYADH_LAT_MAX = 24.55, 24.85
RIYADH_LON_MIN, RIYADH_LON_MAX = 46.55, 46.95

def get_crop_pixels(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    gcps = root.findall('.//geolocationGridPoint')
    lines, pixels, lats, lons = [], [], [], []
    for g in gcps:
        lines.append(int(g.find('line').text))
        pixels.append(int(g.find('pixel').text))
        lats.append(float(g.find('latitude').text))
        lons.append(float(g.find('longitude').text))
    lines = np.array(lines)
    pixels = np.array(pixels)
    lats = np.array(lats)
    lons = np.array(lons)

    mask = ((lats >= RIYADH_LAT_MIN) & (lats <= RIYADH_LAT_MAX) &
            (lons >= RIYADH_LON_MIN) & (lons <= RIYADH_LON_MAX))

    if mask.sum() == 0:
        print("  No GCPs in bbox — using fallback")
        return 4000, 9000, 9000, 16000

    r0 = max(0, lines[mask].min() - 300)
    r1 = lines[mask].max() + 300
    c0 = max(0, pixels[mask].min() - 300)
    c1 = pixels[mask].max() + 300
    print(f"  Crop: rows {r0}-{r1}, cols {c0}-{c1}")
    return int(r0), int(r1), int(c0), int(c1)

def load_crop(img_path, xml_path):
    r0, r1, c0, c1 = get_crop_pixels(xml_path)
    with rasterio.open(img_path) as src:
        w = rasterio.windows.Window(c0, r0, c1-c0, r1-r0)
        arr = src.read(1, window=w).astype(np.float32)
    print(f"  Shape: {arr.shape}")
    return arr

def to_db(arr):
    return 10 * np.log10(np.where(arr > 0, arr, 1e-10))

def match_size(a, b):
    """Crop both arrays to the same size."""
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    return a[:h, :w], b[:h, :w]

if __name__ == "__main__":
    print("Loading 2022...")
    arr_2022 = load_crop(IMG_2022, XML_2022)
    print("Loading 2024...")
    arr_2024 = load_crop(IMG_2024, XML_2024)

    db_2022 = to_db(arr_2022)
    db_2024 = to_db(arr_2024)
    db_2022, db_2024 = match_size(db_2022, db_2024)
    print(f"\nMatched shape: {db_2022.shape}")

    # Save for next step
    np.save('data/processed/db_2022.npy', db_2022)
    np.save('data/processed/db_2024.npy', db_2024)

    # Visualize
    vmin = np.percentile(db_2022[db_2022 > -30], 2)
    vmax = np.percentile(db_2022[db_2022 > -30], 98)

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    axes[0].imshow(db_2022, cmap='gray', vmin=vmin, vmax=vmax)
    axes[0].set_title('Riyadh — Jan 2022 (SAR VV)', fontsize=14)
    axes[0].axis('off')
    axes[1].imshow(db_2024, cmap='gray', vmin=vmin, vmax=vmax)
    axes[1].set_title('Riyadh — Feb 2024 (SAR VV)', fontsize=14)
    axes[1].axis('off')

    plt.tight_layout()
    plt.savefig('outputs/02_riyadh_matched.png', dpi=150, bbox_inches='tight')
    print("Saved: outputs/02_riyadh_matched.png")
    plt.show()