"""Create review figures from the real recording and documented paired scores."""
from pathlib import Path
import argparse
import json

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    source = args.project / "data/train_real-003/train_real/10125_0.h5"
    method = args.project / "replication/track2/METHOD.md"
    if not source.is_file() or not method.is_file():
        raise FileNotFoundError("Expected recording and Track 2 method evidence")
    out = Path(__file__).resolve().parents[1] / "dist/assets"
    out.mkdir(parents=True, exist_ok=True)
    with h5py.File(source) as recording:
        u = np.asarray(recording["u"][:40, ::2, ::2])  # (40, 32, 64), measured horizontal velocity.
        v = np.asarray(recording["v"][:40, ::2, ::2])  # (40, 32, 64), measured vertical velocity.
    if u.shape != (40, 32, 64) or v.shape != u.shape:
        raise ValueError("Recording does not match the expected temporal/spatial sample")
    speed = np.hypot(u, v)  # (40, 32, 64), measured speed magnitude.
    if not np.isfinite(speed).all():
        raise ValueError("Nonfinite recording values")
    vmax = float(speed.max())
    frames = [(19, "observed"), (20, "future-1"), (29, "future-10"), (39, "future-20")]
    for index, name in frames:
        plt.imsave(out / f"flow-{name}.png", speed[index], cmap="viridis", vmin=0, vmax=vmax, origin="lower")
    fig, ax = plt.subplots(figsize=(8, 2.8), facecolor="#f8f6ef")
    ax.set_facecolor("#f8f6ef")
    ax.hlines(0, 82.509437, 82.713986, color="#708c70", linewidth=5, zorder=1)
    ax.scatter([82.509437, 82.713986], [0, 0], s=145, color=["#646b65", "#256548"], zorder=2)
    for value, label in [(82.509437, "T1 · 82.509437"), (82.713986, "T2 · 82.713986")]:
        ax.annotate(label, (value, 0), xytext=(0, 22), textcoords="offset points", ha="center", fontsize=12)
    ax.text((82.509437 + 82.713986) / 2, -0.24, "+0.204549 quality points", ha="center", color="#256548", fontsize=12)
    ax.set_xlim(82.35, 82.87)
    ax.set_ylim(-0.55, 0.55)
    ax.set_yticks([])
    ax.set_xlabel("Local validation quality · runtime excluded", labelpad=12)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c8cdc4")
    fig.tight_layout()
    fig.savefig(out / "paired-quality.svg", facecolor=fig.get_facecolor())
    fig.savefig(out / "paired-quality.png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    provenance = {
        "recording": "10125_0.h5",
        "sampling": "40 initial frames, spatial stride 2, phase (0,0)",
        "quantity": "sqrt(u*u + v*v)",
        "shared_color_range": [0, vmax],
        "frames": dict(frames),
        "images_are": "Measured recording frames, not model predictions",
        "comparison_source": "Track 2 METHOD.md section 8, original submitted archives",
        "t1_quality": 82.509437,
        "t2_quality": 82.713986,
        "comparison_scope": "Same 16 validation recordings and 653 windows; whole configurations, runtime excluded",
    }
    (out / "figure-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print("Created four measured-flow frames, a paired-score figure, and provenance.")


if __name__ == "__main__":
    main()
