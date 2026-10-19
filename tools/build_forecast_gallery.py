"""Run the exact submitted T2 archive and export a reproducible four-case gallery."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import torch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    site = Path(__file__).resolve().parents[1]
    private = site / ".research/gallery"
    assets = site / "dist/assets/realpde"
    private.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    expected = "1d43a4d5242ed6aa57b3fb896beced0c246d1737015bf0484e13ab94973e4c54"
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != expected:
        raise ValueError("Archive does not match the confirmed Codabench submission")
    if not torch.cuda.is_available():
        raise RuntimeError("This export requires the submitted CUDA/BF16 inference path")
    rows = list(csv.DictReader((args.project / "replication/track2/evidence/completed_docker_run/per_file.csv").open()))
    ranked = sorted((r for r in rows if r["partition"] == "validation"),
                    key=lambda r: -float(r["submitted_quality_without_time"]))
    if len(ranked) != 16:
        raise ValueError("Expected the complete 16-recording validation ranking")
    split = json.loads((args.project / "replication/track2/source/split.json").read_text())
    if {tuple(map(int, r["trajectory"].split(":")[1].split("_"))) for r in ranked} != {tuple(k) for k in split["validation_real_keys"]}:
        raise ValueError("Ranking does not match the validation split")
    directory = private / "submitted"
    directory.mkdir(exist_ok=True)
    with zipfile.ZipFile(args.archive) as archive:
        if any(Path(n).name != n for n in archive.namelist()):
            raise ValueError("Unexpected nested archive entry")
        archive.extractall(directory)
    sys.path.insert(0, str(args.project / "replication/track2"))
    from optimized_predictor import load_ttt_model
    engine = load_ttt_model(directory, "cuda", verify_artifacts=False)
    print(json.dumps({"stage": "loaded", "gpu": torch.cuda.get_device_name(0)}), flush=True)
    cases = []
    chosen = [(1, ranked[0]), (2, ranked[1]), (15, ranked[-2]), (16, ranked[-1])]
    for rank, row in chosen:
        name = row["trajectory"].split(":")[1]
        with h5py.File(args.project / "data/train_real-003/train_real" / (name + ".h5")) as handle:
            fields = np.stack([np.asarray(handle[k][:, ::2, ::2], dtype=np.float32) for k in ("u", "v")], axis=-1)
            # fields: (T,32,64,2), physical u/v on the canonical validation grid.
            reynolds, aoa = int(handle["re"][()]), int(handle["aoa"][()])
        if fields.shape[1:] != (32, 64, 2) or not np.isfinite(fields).all():
            raise ValueError("Unexpected recording fields")
        starts = list(range(0, len(fields) - 39, 20))
        if len(starts) != int(row["submitted_windows"]):
            raise ValueError("Chronological window count differs from saved validation")
        engine.reset_ttt_state()
        predictions, errors, lowers, uppers = [], [], [], []
        with torch.inference_mode():
            for start in starts:
                raw = torch.zeros((1, 20, 32, 64, 3), device="cuda", dtype=torch.float32)
                raw[..., :2] = torch.as_tensor(fields[start:start + 20], device="cuda")
                # normalized / output / bounds: (1,20,32,64,3), official normalized units.
                normalized = (raw - engine.mean_input) / engine.std_input
                output, info = engine.ttt_step(normalized, prev_target_norm=None)
                physical = [((x * engine.std_target + engine.mean_target)[0, ..., :2]
                             .float().cpu().numpy().copy()) for x in (output, info["lower"], info["upper"])]
                prediction, lower, upper = physical  # Each: (20,32,64,2), physical u/v.
                target = fields[start + 20:start + 40]
                if any(a.shape != target.shape or not np.isfinite(a).all() for a in physical):
                    raise ValueError("Invalid forecast output")
                if np.any(lower > upper):
                    raise ValueError("Reversed uncertainty bounds")
                mask = target != 0
                errors.append(float(np.abs(prediction.astype(np.float64) - target)[mask].mean()))
                predictions.append(prediction)
                lowers.append(lower)
                uppers.append(upper)
        index = int(np.argmin(np.abs(np.asarray(errors) - np.median(errors))))
        start = starts[index]
        target = fields[start + 20:start + 40]  # (20,32,64,2), ground truth.
        prediction = predictions[index]
        np.savez_compressed(private / (name + ".npz"), observed=fields[start:start + 20],
                            target=target, prediction=prediction, lower=lowers[index], upper=uppers[index])
        case = {"id": name, "rank": rank, "re": reynolds, "aoa": aoa,
                "recording_quality": float(row["submitted_quality_without_time"]),
                "recording_masked_mae": float(row["submitted_masked_point_mae_to_gt"]),
                "start_frame": start, "prior_frames": start, "windows": len(starts),
                "selected_window_masked_mae": errors[index], "window_maes": errors,
                "window_normalized_rmse": float(np.linalg.norm((prediction - target)[target != 0]) / np.linalg.norm(target[target != 0]))}
        cases.append(case)
        print(json.dumps({k:v for k,v in case.items() if k != "window_maes"}), flush=True)
    # Use one absolute vector-error scale across every selected case and horizon.
    max_error = max(float(np.linalg.norm(np.load(private / (c["id"] + ".npz"))["prediction"] -
                                        np.load(private / (c["id"] + ".npz"))["target"], axis=-1).max()) for c in cases)
    for case in cases:
        arrays = np.load(private / (case["id"] + ".npz"))
        target_speed = np.linalg.norm(arrays["target"], axis=-1)  # (20,32,64).
        prediction_speed = np.linalg.norm(arrays["prediction"], axis=-1)
        vector_error = np.linalg.norm(arrays["prediction"] - arrays["target"], axis=-1)
        speed_max = float(max(target_speed.max(), prediction_speed.max()))
        case.update(speed_max=speed_max, error_max=max_error)
        for label, field, cmap, maximum in [("truth", target_speed, "viridis", speed_max),
                                             ("prediction", prediction_speed, "viridis", speed_max),
                                             ("error", vector_error, "magma", max_error)]:
            colors = np.uint8(plt.get_cmap(cmap)(field / maximum) * 255)  # (20,32,64,4), RGBA.
            strip = np.concatenate(list(colors), axis=1)  # (32,20*64,4), horizontal atlas.
            Image.fromarray(strip).save(assets / f'{case["id"]}-{label}.png')
        observed = np.linalg.norm(arrays["observed"][-1], axis=-1)  # (32,64).
        plt.imsave(assets / f'{case["id"]}-observed.png', observed, cmap="viridis", vmin=0, vmax=speed_max, origin="upper")
    ranking = [{"id": r["trajectory"].split(":")[1], "rank": i + 1,
                "quality": float(r["submitted_quality_without_time"]),
                "masked_mae": float(r["submitted_masked_point_mae_to_gt"])} for i,r in enumerate(ranked)]
    report = {"archive_sha256": expected, "submission_id": 944222, "track": 2,
              "inference_gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
              "selection": "Two highest and two lowest complete validation-recording quality scores from the saved A100 evaluation; median-MAE chronological window within each selected recording",
              "protocol": "Reset per recording; every 20-frame input processed in order, no target feedback; no history truncation",
              "rendering": "Velocity magnitude; one common truth/prediction scale within each case; one absolute vector-error scale shared across all four; row zero at top",
              "ranking": ranking, "cases": cases}
    (assets / "gallery.json").write_text(json.dumps(report, indent=2) + "\n")
    (private / "verification.json").write_text(json.dumps({"passed": True, "selected_recordings": 4,
        "windows_processed": sum(c["windows"] for c in cases), "inference_only": True}, indent=2) + "\n")
    print("Gallery exported", flush=True)


if __name__ == "__main__":
    main()
