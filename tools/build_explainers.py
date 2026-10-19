"""Render data-grounded augmentation, representation, history and interval figures."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import torch

PAPER = "#f8f6ef"
plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})


def save(fig, root, name):
    fig.savefig(root / (name + ".png"), dpi=160, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)


def field_panel(root, name, field, cmap, minimum=None, maximum=None):
    """Export one 2-D field with an uncluttered horizontal scale; HTML owns its title."""
    from matplotlib.ticker import MaxNLocator, FormatStrFormatter
    field = np.asarray(field)  # Shape: (H, W), one scalar spatial field.
    if field.ndim != 2 or not np.isfinite(field).all():
        raise ValueError(f'Invalid figure field: {name}')
    fig, ax = plt.subplots(figsize=(4.2, 2.9), layout='constrained')
    plotted = ax.imshow(field, cmap=cmap, vmin=minimum, vmax=maximum, interpolation='nearest')
    ax.set_xticks([])
    ax.set_yticks([])
    bar = fig.colorbar(plotted, ax=ax, orientation='horizontal', shrink=.9, pad=.08, aspect=30)
    bar.locator = MaxNLocator(nbins=3)
    bar.formatter = FormatStrFormatter('%.3g')
    bar.update_ticks()
    bar.ax.tick_params(labelsize=14)
    save(fig, root, name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    site = Path(__file__).resolve().parents[1]
    out = site / "dist/assets/realpde"
    out.mkdir(parents=True, exist_ok=True)
    research = site / ".research"
    baseline = research / 'drive/retained_history.json'
    studies = []
    raw_histories = []
    configs = []
    for key, label, history_path, config_path in [
        ("mild", "80–100% area + resize", research / 'drive/mild_history.json', research / 'drive/mild_config.json'),
        ("medium", "40–70% area + resize", research / 'drive/medium_history.json', research / 'drive/medium_config.json'),
        ("retained", "25% area · native crop", baseline, research / 'drive/retained_config.json'),
    ]:
        history = json.loads(history_path.read_text())
        config = json.loads(config_path.read_text())
        configs.append(config)
        valid = [r for r in history if r.get('validation')]
        best = max(valid, key=lambda r: r['validation']['quality_without_time'])
        if len(history) != 400 or config['runtime']['steps_per_epoch'] != 800:
            raise ValueError("Expected completed 400 × 800 crop studies")
        studies.append({"key": key, "label": label, "best_epoch": best['epoch'],
                        "quality": best['validation']['quality_without_time'],
                        "tke": best['validation']['tke'], "rel_l2": best['validation']['rel_l2'],
                        "mvpe": best['validation']['mvpe'], "sps": best['validation']['sps'],
                        "final_epoch_quality": valid[-1]['validation']['quality_without_time'],
                        "history_sha256": hashlib.sha256(history_path.read_bytes()).hexdigest(),
                        "curve": [{"epoch": r['epoch'], "quality": r['validation']['quality_without_time']} for r in valid]})
        raw_histories.append(valid)
    for config in configs[1:]:
        if config['recipe'] != configs[0]['recipe']:
            raise ValueError("Crop study base recipes differ")
        a, b = ({k:v for k,v in c['runtime'].items() if k != 'output_dir'} for c in (configs[0], config))
        if a != b:
            raise ValueError("Crop study runtime settings differ")
    splits = [json.loads((research / f'drive/{k}_split.json').read_text()) for k in ('mild','medium','retained')]
    if not splits[0] == splits[1] == splits[2]:
        raise ValueError("Crop study splits differ")
    crop_report = {"scope": "Three completed single-seed T1 recipe comparisons, shared split and recorded base/runtime settings",
                   "epochs": 400, "steps_per_epoch": 800, "seed": 42, "crop_probability": 0.5,
                   "selection": "Best scheduled validation checkpoint, no TTA/learned PP in these logged scores",
                   "interpretation": "Both resized alternatives underperformed the native 25%-area crop; crop area and resampling change together",
                   "config_note": "recipe.steps_per_epoch is a stale default of 400; runtime.steps_per_epoch and 12,800 samples per epoch confirm 800 updates at batch 16",
                   "studies": studies}
    (out / 'crop-evidence.json').write_text(json.dumps(crop_report, indent=2) + '\n')
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = ['#a56d49', '#778696', '#256548']
    for study,color in zip(studies, colors):
        curve = [r for r in study['curve'] if r['epoch'] >= 100]
        ax.plot([r['epoch'] for r in curve], [r['quality'] for r in curve], label=study['label'], color=color)
    ax.set(xlabel='Epoch', ylabel='Local validation quality · runtime excluded', title='The crop recipe mattered, not just adding a crop transform')
    ax.legend(loc='lower right', frameon=False)
    ax.grid(axis='y',alpha=.15)
    save(fig, out, 'crop-curves')
    with plt.rc_context({'font.size': 14}):
        fig, ax = plt.subplots(figsize=(4.2, 4.6), layout='constrained')
        for study, color, label in zip(studies, colors, ['80–100% resized', '40–70% resized', '25% native']):
            curve = [row for row in study['curve'] if row['epoch'] >= 100]
            ax.plot([row['epoch'] for row in curve], [row['quality'] for row in curve], color=color, label=label)
        ax.set(xlabel='Epoch', ylabel='Local quality')
        ax.legend(loc='lower right', frameon=False, fontsize=13)
        ax.grid(axis='y', alpha=.15)
        save(fig, out, 'crop-curves-mobile')
    with h5py.File(args.project / 'data/train_real-003/train_real/10125_0.h5') as handle:
        raw = np.stack([np.asarray(handle[k][:120], dtype=np.float32) for k in ('u','v')], axis=-1)
        # raw: (120,64,128,2), two disjoint 40-frame training windows plus their gap.
        metadata = {"recording": '10125_0.h5', "re": int(handle['re'][()]), "aoa": int(handle['aoa'][()])}
    if raw.shape != (120,64,128,2) or not np.isfinite(raw).all():
        raise ValueError('Unexpected augmentation source')
    speed = np.linalg.norm(raw,axis=-1)  # (120,64,128).
    limit = float(speed.max())
    for idx, name in [(19,'crop-input'),(39,'crop-target')]:
        plt.imsave(out / (name+'.png'), speed[idx], cmap='viridis',vmin=0,vmax=limit,origin='upper')
    fig, axes = plt.subplots(1,3,figsize=(11,3.4))
    top,left = 16,32
    for ax, array, title in zip(axes, [speed[19],speed[19,::2,::2],speed[19,top:top+32,left:left+64]],
                                ['Raw field · 64 × 128','Full-field stride 2 · 32 × 64','Native crop · 32 × 64']):
        ax.imshow(array,cmap='viridis',vmin=0,vmax=limit,origin='upper',interpolation='nearest')
        ax.set_title(title);ax.set_xticks([]);ax.set_yticks([])
    axes[0].add_patch(Rectangle((left-.5,top-.5),64,32,fill=False,edgecolor='white',linewidth=2))
    fig.text(.5,.06,'Same tensor shape. Different field of view and spatial detail. The native crop retains 25% of the raw area.',ha='center',fontsize=10)
    save(fig,out,'crop-comparison')
    # Apply mixup to u/v first; plotting speed only happens after the vector mixture.
    for percent in range(50,101,5):
        weight = percent / 100
        for a,b,label in [(19,99,'input'),(39,119,'target')]:
            mixed = weight * raw[a,::2,::2] + (1-weight) * raw[b,::2,::2]  # (32,64,2).
            plt.imsave(out / f'mixup-{label}-{percent}.png',np.linalg.norm(mixed,axis=-1),cmap='viridis',vmin=0,vmax=limit)
        for idx,label in [(19,'a-input'),(39,'a-target'),(99,'b-input'),(119,'b-target')]:
            if percent==50: plt.imsave(out / f'mixup-{label}.png',speed[idx,::2,::2],cmap='viridis',vmin=0,vmax=limit)
    fields = raw[19,::2,::2]  # (32,64,2), one canonical observed frame.
    reflected = fields[::-1].copy();reflected[...,1] *= -1
    bound = float(np.abs(fields[...,1]).max())
    fig,axes=plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
    for ax,value,title in zip(axes,[fields[...,1],fields[::-1,:,1],reflected[...,1]],['Original v','Image flip only','Flip + negate v']):
        image=ax.imshow(value,cmap='RdBu_r',vmin=-bound,vmax=bound,interpolation='nearest');ax.set_title(title,fontsize=10);ax.set_xticks([]);ax.set_yticks([])
    fig.colorbar(image,ax=axes,shrink=.65,label='Signed vertical velocity')
    save(fig,out,'vector-reflection')
    for name, value in [('original', fields[...,1]), ('wrong', fields[::-1,:,1]), ('correct', reflected[...,1])]:
        field_panel(out, f'reflection-{name}', value, 'RdBu_r', -bound, bound)
    last=raw[19,::2,::2,0];future=raw[39,::2,::2,0];delta=future-last  # Each (32,64), horizontal velocity.
    fig,axes=plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
    for ax,arr,title,cmap,vmin,vmax in [(axes[0],last,'Last observed u','viridis',0,float(max(last.max(),future.max()))),
                                        (axes[1],future,'Measured future u','viridis',0,float(max(last.max(),future.max()))),
                                        (axes[2],delta,'Future − last observed','RdBu_r',-float(abs(delta).max()),float(abs(delta).max()))]:
        im=ax.imshow(arr,cmap=cmap,vmin=vmin,vmax=vmax,interpolation='nearest');ax.set_title(title);ax.set_xticks([]);ax.set_yticks([]);fig.colorbar(im,ax=ax,shrink=.7)
    save(fig,out,'residual-target')
    shared_max = float(max(last.max(), future.max()))
    field_panel(out, 'residual-last', last, 'viridis', 0, shared_max)
    field_panel(out, 'residual-future', future, 'viridis', 0, shared_max)
    field_panel(out, 'residual-delta', delta, 'RdBu_r', -float(abs(delta).max()), float(abs(delta).max()))
    observed=torch.from_numpy(raw[:20,::2,::2])[None]  # (1,20,32,64,2), physical input.
    mean=observed.mean(1);variance=observed.var(1,unbiased=False)  # (1,32,64,2).
    smooth=torch.nn.functional.avg_pool2d(torch.nn.functional.pad(variance.permute(0,3,1,2),(2,2,2,2),mode='replicate'),5,1)
    scale=smooth.clamp_min(1e-12).sqrt().permute(0,2,3,1)  # (1,32,64,2), positive local RMS.
    z=(observed-mean[:,None])/scale[:,None]
    fig,axes=plt.subplots(1,3,figsize=(12,3.8),layout='constrained')
    for ax,arr,title,cmap in [(axes[0],mean[0,...,0],'Local mean u','viridis'),(axes[1],scale[0,...,0],'Local scale u','magma'),(axes[2],z[0,-1,...,0],'Normalized last u','RdBu_r')]:
        im=ax.imshow(arr,cmap=cmap,interpolation='nearest');ax.set_title(title);ax.set_xticks([]);ax.set_yticks([]);fig.colorbar(im,ax=ax,shrink=.7)
    save(fig,out,'local-normalization')
    field_panel(out, 'normalization-mean', mean[0,...,0], 'viridis')
    field_panel(out, 'normalization-scale', scale[0,...,0], 'magma')
    field_panel(out, 'normalization-z', z[0,-1,...,0], 'RdBu_r', -float(z[0,-1,...,0].abs().max()), float(z[0,-1,...,0].abs().max()))
    # Evaluate actual saved history feature code with the original trained confidence.
    sys.path.insert(0,str(research/'gallery/submitted'))
    from history_model import load_history
    from history_stats import CausalHistoryState
    model,_,_=load_history(research/'gallery/submitted/model.ckpt',torch.device('cpu'))
    gallery=json.loads((out/'gallery.json').read_text())
    example=gallery['cases'][2]
    with h5py.File(args.project/'data/train_real-003/train_real'/(example['id']+'.h5')) as h:
        uv=np.stack([np.asarray(h[k][:example['start_frame']+20,::2,::2],dtype=np.float32) for k in ('u','v')],axis=-1)
    state=CausalHistoryState(torch.device('cpu'),history_mode='window_energy')
    with torch.inference_mode():
        for start in range(0,example['start_frame'],20): state.update(torch.from_numpy(uv[start:start+20])[None])
        _,means,logs,_=model.base._network_components(torch.from_numpy(uv[-20:])[None])
        features=model.history_features(means,logs,state.get())[0].numpy()  # (7,32,64), actual feature maps.
    if features.shape!=(7,32,64) or not np.isfinite(features).all(): raise ValueError('Invalid history feature maps')
    fig,axes=plt.subplots(2,4,figsize=(12,4.8))
    names=['Historical mean Δu','Historical mean Δv','Historical log-scale Δu','Historical log-scale Δv','History confidence','Within-window energy Δu','Within-window energy Δv']
    for i,ax in enumerate(axes.flat):
        if i==7: ax.axis('off');continue
        limits={'vmin':0,'vmax':1} if i==4 else {'vmin':-max(float(abs(features[i]).max()),1e-5),'vmax':max(float(abs(features[i]).max()),1e-5)}
        im=ax.imshow(features[i],cmap='viridis' if i==4 else 'RdBu_r',**limits,interpolation='nearest');ax.set_title(names[i],fontsize=9);ax.set_xticks([]);ax.set_yticks([]);fig.colorbar(im,ax=ax,shrink=.7)
    fig.tight_layout();save(fig,out,'history-features')
    for index, field in enumerate(features):
        bound = max(float(abs(field).max()), 1e-5)
        field_panel(out, f'history-{index+1}', field, 'viridis' if index == 4 else 'RdBu_r',
                    0 if index == 4 else -bound, 1 if index == 4 else bound)
    arrays=np.load(research/'gallery'/(example['id']+'.npz'))
    variability=arrays['observed'][...,1].std(axis=0)  # (32,64), observed v variability.
    y,x=np.unravel_index(np.argmax(variability),variability.shape)
    fig,ax=plt.subplots(figsize=(9,4.5),layout='constrained');times=np.arange(1,21)
    ax.fill_between(times,arrays['lower'][:,y,x,1],arrays['upper'][:,y,x,1],color='#b4cdb3',alpha=.8,label='Final predicted interval')
    ax.plot(times,arrays['target'][:,y,x,1],color='#202b25',label='Measured future v')
    ax.plot(times,arrays['prediction'][:,y,x,1],color='#256548',label='Point forecast')
    ax.set(xlabel='Forecast frame',ylabel='Vertical velocity',title=f'Re {example["re"]:,} · AoA {example["aoa"]}° · pixel ({y}, {x})')
    ax.legend(frameon=False,fontsize=12,loc='upper center',bbox_to_anchor=(.5,1.26),ncol=2);save(fig,out,'uncertainty-example')
    with plt.rc_context({'font.size': 14}):
        fig, ax = plt.subplots(figsize=(4.2, 4.9), layout='constrained')
        ax.fill_between(times, arrays['lower'][:,y,x,1], arrays['upper'][:,y,x,1], color='#b4cdb3', alpha=.8, label='Predicted interval')
        ax.plot(times, arrays['target'][:,y,x,1], color='#202b25', label='Measured v')
        ax.plot(times, arrays['prediction'][:,y,x,1], color='#256548', label='Forecast')
        ax.set(xlabel='Forecast frame', ylabel='Vertical velocity', xticks=[1,5,10,15,20])
        ax.legend(loc='lower center', bbox_to_anchor=(.5,1.01), frameon=False, fontsize=14)
        save(fig, out, 'uncertainty-example-mobile')
    # Report actual measured Re values rather than nominal filename labels.
    for row in gallery['ranking']:
        with h5py.File(args.project/'data/train_real-003/train_real'/(row['id']+'.h5')) as h:
            row.update(re=int(h['re'][()]),aoa=int(h['aoa'][()]))
    (out/'gallery.json').write_text(json.dumps(gallery,indent=2)+'\n')
    fig,ax=plt.subplots(figsize=(9,4))
    pts=ax.scatter([r['re'] for r in gallery['ranking']],[r['aoa'] for r in gallery['ranking']],c=[r['quality'] for r in gallery['ranking']],cmap='viridis',s=120,edgecolors=PAPER)
    for r in gallery['ranking']:
        if r['rank'] in (1,2,15,16): ax.annotate(f'#{r["rank"]}',(r['re'],r['aoa']),xytext=(8,7),textcoords='offset points',fontsize=10)
    ax.set(xlabel='Reynolds number · recording metadata',ylabel='Angle of attack (degrees)',title='All 16 validation conditions · original T2 quality ranking')
    fig.colorbar(pts,ax=ax,label='Local quality · runtime excluded');ax.grid(alpha=.12);save(fig,out,'condition-map')
    notes={"augmentation_source":metadata,"illustration_windows":[[0,39],[80,119]],"illustration_lambda_range":[.5,1],
           "crop_area_fraction":.25,"crop_application_probability":.5,"crop_interpolation":"none",
           "reflection":"Reverse row order and negate vertical velocity for both input and target",
           "mixup":"Linear mixture of vectors before computing displayed speed; same coefficient for input and target",
           "history_example":{k:example[k] for k in ('id','re','aoa','start_frame')},
           "uncertainty_pixel":{"row":int(y),"column":int(x),"selection":"Maximum observed v standard deviation; selected without future targets"}}
    (out/'explainer-provenance.json').write_text(json.dumps(notes,indent=2)+'\n')
    print(json.dumps({"crop_scores":[r['quality'] for r in studies],"shared_split":True,"figures":"complete"}),flush=True)


if __name__ == '__main__': main()
