# ② 중첩법 — 5-fold CV (전 253, 라이브러리는 각 fold의 train에서만 구성)
import sys, json, csv, numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0,'scripts'); import rom_pod as R
R.set_pool(2); NZ,NY,NX = R.NZ,R.NY,R.NX
LX,LY = 0.47,0.21; dx,dy = LX/NX, LY/NY
split = json.load(open('dataset/training_dataset/test_split.json'))
allids = split['train_val'] + split['test']
rows = {r['case_id']: r for r in csv.DictReader(open('CFD/cases.csv'))}
U, occ = R.load_fields('/tmp/fields/fields', allids); N=len(allids)
i0 = allids.index('case0000'); base = U[i0].reshape(3,NZ,NY,NX)
def shift2d(d,di,dj):
    if di==0 and dj==0: return d
    o=np.zeros_like(d)
    o[:,:,slice(max(0,dj),NY-max(0,-dj)),slice(max(0,di),NX-max(0,-di))] = \
      d[:,:,slice(max(0,-dj),NY-max(0,dj)),slice(max(0,-di),NX-max(0,di))]
    return o
rng=np.random.RandomState(0); order=rng.permutation(N)
res={'sup':[], 'mean':[]}
for f in range(5):
    te=order[f::5]; tr=np.setdiff1d(order,te)
    lib={}
    for i in tr:
        c=allids[i]
        if rows[c]['tier']!='1': continue
        o=json.loads(rows[c]['obstacles_json'])[0]
        lib.setdefault((o['kind'],o['size']),[]).append((o['x'],o['y'],U[i].reshape(3,NZ,NY,NX)-base))
    mean=U[tr].mean(0)
    for i in te:
        c=allids[i]; pred=base.copy()
        for o in json.loads(rows[c]['obstacles_json']):
            cand=lib.get((o['kind'],o['size']))
            if not cand: continue
            ds=sorted(((o['x']-x)**2*LX**2+(o['y']-y)**2*LY**2,x,y,d) for x,y,d in cand)[:3]
            w=np.array([1.0/(np.sqrt(t[0])+5e-3) for t in ds]); w/=w.sum()
            for wi,(dist,x,y,d) in zip(w,ds):
                pred += wi*shift2d(d,int(round((o['x']-x)*LX/dx)),int(round((o['y']-y)*LY/dy)))
        res['sup'].append(R.eval_case(U[i],pred.reshape(-1),occ[i,0],mean))
        res['mean'].append(R.eval_case(U[i],mean,occ[i,0],mean))
print(f"{'method':<24}{'anomL2 med':>11}{'IoU med':>9}{'IoU min':>9}{'IoU p10':>9}{'cdist_mm':>10}   (5-fold CV, n=253)")
for k in ['mean','sup']:
    e=np.array(res[k]); nm={'mean':'baseline_meanfield','sup':'superpose_shift(k=3)'}[k]
    print(f"{nm:<24}{np.nanmedian(e[:,1]):>11.3f}{np.median(e[:,2]):>9.3f}{e[:,2].min():>9.3f}"
          f"{np.percentile(e[:,2],10):>9.3f}{np.median(e[:,3]):>10.1f}")
# 구조물 종류별
e=np.array(res['sup']); ids=[allids[i] for f in range(5) for i in order[f::5]]
import collections
grp=collections.defaultdict(list)
for c,row in zip(ids,e):
    obs=json.loads(rows[c]['obstacles_json'])
    g='none' if not obs else ('rock만' if all(o['kind']=='rock' for o in obs) else
       ('plant만' if all(o['kind']=='plant' for o in obs) else '혼합'))
    grp[g].append(row)
print("\n구성별 (중첩법):")
for g,v in sorted(grp.items()):
    v=np.array(v); print(f"  {g:<8} n={len(v):>3}  IoU_med={np.median(v[:,2]):.3f}  anomL2={np.nanmedian(v[:,1]):.3f}  cdist={np.median(v[:,3]):.1f}mm")
