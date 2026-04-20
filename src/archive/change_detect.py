import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Load preprocessed arrays
db_2022 = np.load('data/processed/db_2022.npy')
db_2024 = np.load('data/processed/db_2024.npy')

print(f"2022 shape: {db_2022.shape}")
print(f"2024 shape: {db_2024.shape}")

def log_ratio_change(img1, img2):
    """
    Log-ratio change detection — the standard SAR method.
    Subtracting in dB space = dividing in linear space.
    Large positive values = got brighter (new construction).
    Large negative values = got darker (demolition/clearing).
    """
    return img2 - img1

def threshold_change(change_map, threshold=3.0):
    """
    Classify change into 3 categories:
    +1 = significant increase (new construction)
    -1 = significant decrease (demolition/clearing)
     0 = no change
    """
    result = np.zeros_like(change_map)
    result[change_map > threshold]  = 1   # increased backscatter
    result[change_map < -threshold] = -1  # decreased backscatter
    return result

if __name__ == "__main__":
    # Step 1 — compute change map
    change = log_ratio_change(db_2022, db_2024)
    classified = threshold_change(change, threshold=3.0)

    # Stats
    total = classified.size
    increased = (classified == 1).sum()
    decreased = (classified == -1).sum()
    unchanged = (classified == 0).sum()

    print(f"\nChange Detection Results:")
    print(f"  Increased (new construction): {increased:,} pixels ({100*increased/total:.1f}%)")
    print(f"  Decreased (clearing/change):  {decreased:,} pixels ({100*decreased/total:.1f}%)")
    print(f"  No change:                    {unchanged:,} pixels ({100*unchanged/total:.1f}%)")

    # Step 2 — visualize
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))

    vmin = np.percentile(db_2022[db_2022 > -30], 2)
    vmax = np.percentile(db_2022[db_2022 > -30], 98)

    axes[0].imshow(db_2022, cmap='gray', vmin=vmin, vmax=vmax)
    axes[0].set_title('Riyadh — Jan 2022', fontsize=13)
    axes[0].axis('off')

    axes[1].imshow(db_2024, cmap='gray', vmin=vmin, vmax=vmax)
    axes[1].set_title('Riyadh — Feb 2024', fontsize=13)
    axes[1].axis('off')

    # Change map: red = increase, blue = decrease, white = no change
    cmap = mcolors.ListedColormap(['#2166ac', '#f7f7f7', '#d6604d'])
    norm = mcolors.BoundaryNorm([-1.5, -0.5, 0.5, 1.5], cmap.N)
    im = axes[2].imshow(classified, cmap=cmap, norm=norm)
    axes[2].set_title('Change Detection\n🔴 Increased  ⬜ No change  🔵 Decreased', fontsize=13)
    axes[2].axis('off')

    cbar = plt.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04)
    cbar.set_ticks([-1, 0, 1])
    cbar.set_ticklabels(['Decreased', 'No Change', 'Increased'])

    plt.suptitle('SAR Amplitude Change Detection — Riyadh 2022 vs 2024', fontsize=15, y=1.02)
    plt.tight_layout()
    plt.savefig('outputs/03_change_detection.png', dpi=150, bbox_inches='tight')
    print("\nSaved: outputs/03_change_detection.png")
    plt.show()