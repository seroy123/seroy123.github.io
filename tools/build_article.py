"""Build the overview and linked RealPDE explainers from reviewable HTML fragments."""
from html import escape
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ('index', 'Our RealPDE solution', 'A compact overview, real forecasts, and the experiments behind each improvement.'),
    ('representation', 'Input features and residual prediction', 'Last-frame conditioning, residual targets, and local flow statistics.'),
    ('augmentation', 'View augmentations', 'Why a small native crop helped, how we mixed windows, and what the ablations showed.'),
    ('architecture', 'Model architecture and training losses', 'The SimVPv2 backbone, metric-aware objectives, and a dedicated uncertainty path.'),
    ('history', 'T2 history features', 'How Track 2 adds causal context to the strongest Track 1 architecture.'),
    ('postprocessing', 'Prediction postprocessing', 'Reflected views, fluctuation-energy corrections, and learned interval widths.'),
    ('efficiency', 'Inference optimization and reproducibility', 'Fast inference, training from scratch, and evidence that the package reproduces the result.'),
]


def gallery_markup(data):
    cases = data['cases']
    if len(cases) != 4 or len({case['error_max'] for case in cases}) != 1:
        raise ValueError('Expected four cases with one shared error scale')
    labels = [('truth', 'Measured future'), ('prediction', 'T2 forecast'), ('error', 'Error')]
    cards = []
    scale_rows = []
    for case in cases:
        group = 'Best' if case['rank'] <= 2 else 'Worst'
        panels = []
        for key, label in labels:
            # Sprite shape: 32 rows × (20 frames × 64 columns).
            panels.append(f'''<div class="forecast-panel">
                <span class="mobile-panel-label">{label}</span>
                <div class="atlas"><img class="forecast-strip"
                    src="../../assets/realpde/{case['id']}-{key}.png" width="1280" height="32"
                    alt="{label} for Re {case['re']}, AoA {case['aoa']} degrees; 20 synchronized frames."></div>
            </div>''')
        cards.append(f'''<section class="forecast-case" aria-label="{group} case: Re {case['re']}, AoA {case['aoa']} degrees">
            <div class="case-heading"><h3>Re {case['re']:,} <span>·</span> AoA {case['aoa']}°</h3>
                <span class="case-rank">{group} · {case['rank']}/16</span></div>
            <div class="forecast-panels">{''.join(panels)}</div>
        </section>''')
        scale_rows.append(f"<tr><td>Re {case['re']:,} · AoA {case['aoa']}°</td><td>0–{case['speed_max']:.3f}</td></tr>")
    headings = ''.join(f'<span>{label}</span>' for _, label in labels)
    return f'''<div id="forecast-gallery">
        <div class="gallery-controls"><button id="forecast-play" type="button" aria-pressed="false">Play forecast</button>
            <label for="forecast-horizon">Frame <output id="forecast-time">+1</output> / 20</label>
            <input id="forecast-horizon" type="range" min="1" max="20" value="1" aria-label="Forecast frame, synchronized across all four examples"></div>
        <div class="gallery-column-labels" aria-hidden="true">{headings}</div>
        {''.join(cards)}
        <details class="read-more gallery-notes"><summary>Reading the plots &amp; selection details</summary>
            <p>Measured future and forecast show speed on the same color scale within each condition. Error is the magnitude of the velocity-vector difference, with one scale across all four conditions. The three panels show the same spatial region.</p>
            <div class="plot-legend"><span><i class="color-ramp speed"></i> Speed: low → high</span>
                <span><i class="color-ramp error"></i> Error: 0 → {cases[0]['error_max']:.3f}</span></div>
            <div class="table-wrap"><table><thead><tr><th>Condition</th><th>Speed range</th></tr></thead><tbody>{''.join(scale_rows)}</tbody></table></div>
            <p>We rank the 16 complete validation recordings by local quality without runtime, then show a median-error window from each selected recording. Re is Reynolds number; AoA is angle of attack. Both come from the recording metadata.</p>
            <p>Forecasts use the exact submitted T2 weights. <a href="../../assets/realpde/gallery.json">Selection and inference record</a>.</p>
        </details>
    </div>'''


def render_fragment(slug, replacements):
    fragment = (ROOT / 'content/realpde' / f'{slug}.html').read_text()
    for key, value in replacements.items():
        fragment = fragment.replace(key, value)
    if '{{' in fragment:
        raise ValueError(f'Unresolved template field: {slug}')
    return fragment


def main():
    gallery = json.loads((ROOT / 'dist/assets/realpde/gallery.json').read_text())
    animation = json.loads((ROOT / 'dist/assets/realpde/augmentation-animation.json').read_text())
    crop = json.loads((ROOT / 'dist/assets/realpde/crop-evidence.json').read_text())
    asset = '../../assets/realpde/'
    feature_names = ['Mean shift · u', 'Mean shift · v', 'Log-scale shift · u',
                     'Log-scale shift · v', 'History confidence', 'Window energy · u', 'Window energy · v']
    features = ''.join(f'<figure><h4>{name}</h4><img loading="lazy" src="{asset}history-{index+1}.png" alt="{escape(name)} history feature map with its own color scale"></figure>' for index, name in enumerate(feature_names))
    replacements = {
        '{{asset}}': asset,
        '{{reflection_limit}}': f"{animation['reflection_v_range'][1]:.3f}",
        '{{mixup_limit}}': f"{animation['mixup_speed_range'][1]:.3f}",
        '{{base}}': '../../',
        '{{article}}': './',
        '{{crop_rows}}': ''.join(f'<tr><td>{escape(study["label"])}</td><td>{study["quality"]:.4f}</td><td>{study["best_epoch"]}</td><td>{study["tke"]:.4f}</td></tr>' for study in crop['studies']),
        '{{history_panels}}': f'<div class="field-grid history-fields">{features}</div>',
    }
    chapters = []
    for number, (slug, title, subtitle) in enumerate(PAGES[1:], 1):
        body = render_fragment(slug, replacements)
        chapters.append(f'''<details class="solution-chapter" id="{slug}">
            <summary><span class="chapter-number">0{number}</span><span>{escape(title)}</span><span class="chapter-toggle" aria-hidden="true">+</span></summary>
            <div class="chapter-content">{body}<a class="chapter-back" href="#improvements">↑ Back to the process</a></div>
        </details>''')
    replacements.update({'{{gallery}}': gallery_markup(gallery), '{{chapters}}': ''.join(chapters)})
    fragment = render_fragment('index', replacements)
    # Reserve each PNG's intrinsic aspect ratio before collapsed sections open.
    def image_dimensions(match):
        tag = match.group(0)
        source = re.search(r'src="([^"]+)"', tag)
        if source is None or not source[1].startswith(asset) or not source[1].endswith('.png'):
            return tag
        path = ROOT / 'dist/assets/realpde' / source[1].removeprefix(asset)
        header = path.read_bytes()[:24]
        if header[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError(f'Invalid PNG: {path}')
        width, height = struct.unpack('>II', header[16:24])
        if 'width=' not in tag:
            tag = tag[:-1] + f' width="{width}" height="{height}">'
        return tag
    fragment = re.sub(r'<img\b[^>]*>', image_dimensions, fragment)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Our RealPDE solution: real forecasts and visual explanations of the biggest improvements.">
<title>Our RealPDE solution — Roy Segal</title><link rel="stylesheet" href="../../assets/site.css"><link rel="icon" href="../../assets/favicon.svg" type="image/svg+xml"><script src="../../assets/article.js" defer></script></head>
<body><a class="skip" href="#article">Skip to article</a><div class="shell">
<header class="nav"><a class="brand" href="../../">Roy Segal<span>.</span></a><nav class="nav-links" aria-label="Main navigation"><a href="../../#about">About me</a><a href="../../#work">My works</a><a class="external" href="https://github.com/seroy123">GitHub ↗</a></nav></header>
<main><div class="article-heading"><a class="back" href="../../#work">← My works</a><p class="eyebrow" style="margin-top:32px">Team Pistachio · RealPDE</p><h1>Our RealPDE solution</h1><p class="lede">Validation forecasts and solution details.</p><p class="byline">Roy Segal · Work with Amit Aharoni · October 2026</p></div>
<article class="article-body overview" id="article">{fragment}</article></main>
<footer class="footer"><a href="#problem">↑ Back to the problem</a><span>© 2026 Roy Segal</span></footer></div></body></html>
'''
    root = ROOT / 'dist/work/realpde'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'index.html').write_text(html)
    # Preserve old chapter URLs as redirects into the same-page expandable sections.
    for slug, title, _ in PAGES[1:]:
        fragment_ids = re.findall(r'id="([^"]+)"', (ROOT / 'content/realpde' / f'{slug}.html').read_text())
        folder = root / slug
        folder.mkdir(exist_ok=True)
        redirect = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><link rel="canonical" href="../#{slug}"><script>
const known = {json.dumps(fragment_ids)};
const requested = location.hash.slice(1);
location.replace('../' + (known.includes(requested) ? '#' + requested : '#{slug}'));
</script></head><body><p><a href="../#{slug}">Read {escape(title)} in the RealPDE article</a>.</p></body></html>'''
        (folder / 'index.html').write_text(redirect)
    print('Built one article with six expandable chapters and six legacy redirects.')


if __name__ == '__main__':
    main()
