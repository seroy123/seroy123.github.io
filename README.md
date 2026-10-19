# Roy Segal — personal AI site

Personal AI blog: https://seroy123.github.io/

RealPDE article: https://seroy123.github.io/work/realpde/

## Structure

- `dist/index.html`: home, My Work, Writing and About.
- `dist/work/realpde/index.html`: problem statement and four synchronized forecast examples, with expandable methodology links.
- Typography: 20px article text, minimum 16px labels, and shared desktop forecast headings.
- Six collapsed chapters on the same page (under the plain “How we built it” heading; deep links open and scroll to them): representation, augmentation, architecture, T2 history, postprocessing and efficiency.
- `content/realpde/`: editable HTML fragments; each chapter leads with a visual takeaway and keeps evidence collapsed.
- Old chapter URLs redirect into the corresponding expandable section.
- Scalar field plots are individual responsive panels; time-series charts have dedicated mobile layouts.
- `dist/assets/realpde/`: derived figures, forecast sprites and public evidence JSON.
- `dist/assets/article.js`: forecast playback, aligned crop explorer, vector-mixup slider, and 10 FPS mixup/reflection playback.
- `.github/workflows/pages.yml`: deploys only `dist/` to GitHub Pages on pushes to `main`.

## Preview

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory dist
```

Open http://127.0.0.1:8765 . No account credentials, external fonts, external scripts or build dependencies
are required to view the site.

## Edit and rebuild

Edit the fragments in `content/realpde/`, then run:

```sh
python3 tools/build_article.py
```

Scientific figures are already included. To regenerate them with the original
local evidence and the RealPDE Python environment:

```sh
python tools/build_forecast_gallery.py --project /path/to/RealPDE_challenge --archive /path/to/t2_energy_epoch400_v10_pp_bf16_fast.zip
python tools/build_explainers.py --project /path/to/RealPDE_challenge
python tools/build_augmentation_animation.py --project /path/to/RealPDE_challenge
python3 tools/build_article.py
```

The gallery builder verifies the exact submission archive hash, ranks the saved
validation-recording scores, then runs every chronological window in the chosen
recordings. It selects each recording's median-MAE representative window. It
requires a CUDA GPU and the original local archive/data. The explainer builder
requires the recovered crop histories/configs/splits in `.research/drive/`.
These private inputs and the extracted model remain under ignored `.research/`;
they are not part of the website or the Pages upload.

## Evidence and review

Forecasts use original Track 2 submission 944222, including its postprocessing.
They are actual model outputs, not illustrations synthesized by an image model.
Whole-recording ranks come from the saved A100 evaluation; image inference ran
locally on the RTX 5070 Ti. Re/AoA values come from HDF5 metadata.

The crop chart compares three completed runs with matching splits, base recipes,
runtime settings and seed. Crop area and resampling vary together. The article
also distinguishes whole-configuration T1/T2 comparisons from isolated ablations.
Public evidence JSON accompanies the figures; private source references are in
`.research/source-index.json`.

Review changes to the narrative, attribution and competition details before pushing to `main`.
Desktop/mobile browser verification is recorded in `.preview/verification.json`.

## GitHub repository

Public repository: https://github.com/seroy123/seroy123.github.io

GitHub Pages uses the Actions workflow to publish `dist/`. A push to `main`
updates the website; the source and generated site are both public.

The competition repository, Docker images, submission ZIPs and credentials are
not part of this site. Only the reviewed site source and derived figures belong
in its repository.
