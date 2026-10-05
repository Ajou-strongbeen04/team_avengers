# ②-b 물리 prior(중첩) + 잔차 ROM 하이브리드
import sys, json, csv, numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0, 'scripts')
import rom_pod as R
R.set_pool(2)
NZ, NY, NX = R.NZ, R.NY, R.NX
LX, LY = 0.47, 0.21; dx, dy = LX/NX, LY/NY

split = json.load(open('dataset/training_dataset/test_split.json'))
tr, te = split['train_val'], split['test']
rows = {r['case_id']: r for r in csv.DictReader(open('CFD/cases.csv'))}
allids = tr + te
U, occ = R.load_fields('/tmp/fields/fields', allids)
idx = {c: i for i, c in enumerate(allids)}
labels = pd.read_csv('/tmp/fields/labels.csv')
mean = U[:len(tr)].mean(0)
base = U[idx['case0000']].reshape(3, NZ, NY, NX)

lib = {}
for c in tr:
    if rows[c]['tier'] != '1': continue
    o = json.loads(rows[c]['obstacles_json'])[0]
    lib.setdefault((o['kind'], o['size']), []).append(
        (o['x'], o['y'], U[idx[c]].reshape(3, NZ, NY, NX) - base))

def shift2d(d, di, dj):
    if di == 0 and dj == 0: return d
    out = np.zeros_like(d)
    out[:, :, slice(max(0,dj), NY-max(0,-dj)), slice(max(0,di), NX-max(0,-di))] = \
        d[:, :, slice(max(0,-dj), NY-max(0,dj)), slice(max(0,-di), NX-max(0,di))]
    return out

def superpose(cid, k=3):
    pred = base.copy()
    for o in json.loads(rows[cid]['obstacles_json']):
        cand = lib.get((o['kind'], o['size']))
        if not cand: continue
        ds = sorted(((o['x']-x)**2*LX**2 + (o['y']-y)**2*LY**2, x, y, d) for x, y, d in cand)[:k]
        w = np.array([1.0/(np.sqrt(t[0])+5e-3) for t in ds]); w /= w.sum()
        for wi, (dist, x, y, d) in zip(w, ds):
            pred += wi * shift2d(d, int(round((o['x']-x)*LX/dx)), int(round((o['y']-y)*LY/dy)))
    return pred.reshape(-1)

S = np.stack([superpose(c) for c in allids])          # 물리 prior
Res = U - S                                            # 잔차
ntr = len(tr)
Xtr = R.geom_features(occ[:ntr], labels, tr); Xte = R.geom_features(occ[ntr:], labels, te)

def ev(name, pred_te):
    e = np.array([R.eval_case(U[ntr+i], pred_te[i], occ[ntr+i, 0], mean) for i in range(len(te))])
    print(f"{name:<30}{np.nanmedian(e[:,0]):>8.3f}{np.nanmedian(e[:,1]):>11.3f}"
          f"{np.median(e[:,2]):>9.3f}{e[:,2].min():>9.3f}{np.median(e[:,3]):>10.1f}")
    return e

print(f"\n{'method':<30}{'relL2':>8}{'anomL2 med':>11}{'IoU med':>9}{'IoU min':>9}{'cdist_mm':>10}")
print("-"*77)
# 기준: 순수 POD+RF
Phi, Atr, w, r = R.pod_basis(U[:ntr] - mean, 0.99)
reg = R.fit_regressors(Xtr, Atr, 'rf')
ev(f"pod_rf (r={r})", mean + reg.predict(Xte) @ Phi.T)
# 물리 prior 단독
ev("superpose only", S[ntr:])
# 하이브리드: 잔차 POD+RF
mres = Res[:ntr].mean(0)
Phi2, A2, w2, r2 = R.pod_basis(Res[:ntr] - mres, 0.99)
reg2 = R.fit_regressors(Xtr, A2, 'rf')
ev(f"superpose + 잔차 POD+RF (r={r2})", S[ntr:] + mres + reg2.predict(Xte) @ Phi2.T)
# 하이브리드 상한(잔차 참계수 투영)
ceil2 = S[ntr:] + mres + ((Res[ntr:] - mres) @ Phi2) @ Phi2.T
ev("  └ 하이브리드 ceiling", ceil2)
# 참고: 순수 POD ceiling
ev("pod ceiling(참고)", mean + ((U[ntr:] - mean) @ Phi) @ Phi.T)
