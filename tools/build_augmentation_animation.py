"""Export real 20-frame augmentation sequences for the interactive article."""
import argparse
import json
from pathlib import Path

import h5py
import matplotlib
import numpy as np
from PIL import Image


def save_strip(path, fields, cmap, minimum, maximum):
    # fields: (20, 32, 64), one scalar value at each pixel and time step.
    if fields.shape != (20, 32, 64) or not np.isfinite(fields).all() or maximum <= minimum:
        raise ValueError(f'Invalid animation field: {path.name}')
    normalized = np.clip((fields - minimum) / (maximum - minimum), 0, 1)
    rgba = np.uint8(matplotlib.colormaps[cmap](normalized) * 255)  # (20, 32, 64, 4).
    strip = np.concatenate(list(rgba), axis=1)  # (32, 1280, 4): 20 frames across.
    Image.fromarray(strip).save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / 'dist/assets/realpde'
    output.mkdir(parents=True, exist_ok=True)
    with h5py.File(args.project / 'data/train_real-003/train_real/10125_0.h5') as handle:
        raw = np.stack([np.asarray(handle[key][:120], dtype=np.float32) for key in ('u', 'v')], axis=-1)
    # raw: (120, 64, 128, 2), physical u/v with disjoint windows at offsets 0 and 80.
    if raw.shape != (120, 64, 128, 2) or not np.isfinite(raw).all():
        raise ValueError('Unexpected augmentation source')
    speed_max = float(np.linalg.norm(raw, axis=-1).max())
    sampled = raw[:, ::2, ::2]  # (120, 32, 64, 2), canonical full-field sampling.
    windows = {'a-input': sampled[:20], 'a-target': sampled[20:40],
               'b-input': sampled[80:100], 'b-target': sampled[100:120]}
    for name, field in windows.items():
        save_strip(output / f'mixup-{name}-sequence.png', np.linalg.norm(field, axis=-1), 'viridis', 0, speed_max)
    for percent in range(50, 101, 5):
        weight = percent / 100
        for part in ('input', 'target'):
            mixed = weight * windows[f'a-{part}'] + (1 - weight) * windows[f'b-{part}']
            # Mix physical vectors before computing the displayed speed magnitude.
            save_strip(output / f'mixup-{part}-{percent}-sequence.png', np.linalg.norm(mixed, axis=-1), 'viridis', 0, speed_max)
    vertical = sampled[:20, ..., 1]  # (20, 32, 64), observed vertical velocity.
    bound = float(np.abs(vertical).max())
    for name, field in [('original', vertical), ('wrong', vertical[:, ::-1]), ('correct', -vertical[:, ::-1])]:
        save_strip(output / f'reflection-{name}-sequence.png', field, 'RdBu_r', -bound, bound)
    report = {'recording': '10125_0.h5', 'frames': 20, 'mixup_windows': [[0, 39], [80, 119]],
              'mixup_speed_range': [0, speed_max], 'reflection_v_range': [-bound, bound],
              'reflection_frames': [0, 19], 'fps': 10, 'vector_mixing_before_speed': True}
    (output / 'augmentation-animation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Exported 29 real-data animation strips.')


if __name__ == '__main__':
    main()
