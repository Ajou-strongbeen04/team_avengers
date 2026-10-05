# ② 후류 라이브러리 + 국소중첩 검증
import sys, json, csv, numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0, 'scripts')
import rom_pod as R
R.set_pool(2)
NZ, NY, NX = R.NZ, R.NY, R.NX
LX, LY = 0.47, 0.21
dx, dy = LX/NX, LY/NY

split = json.load(open('dataset/training_dataset/test_split.json'))
tr, te = split['train_val'], split['test']
rows = {r['case_id']: r for r in csv.DictReader(open('CFD/cases.csv'))}
allids = tr + te
U, occ = R.load_fields('/tmp/fields/fields', allids)
idx = {c: i for i, c in enumerate(allids)}
mean = U[:len(tr)].mean(0)
base = U[idx['case0000']].reshape(3, NZ, NY, NX)

lib = {}
for c in tr:
    r = rows[c]
    if r['tier'] != '1': continue
    o = json.loads(r['obstacles_json'])[0]
    lib.setdefault((o['kind'], o['size']), []).append(
        (o['x'], o['y'], U[idx[c]].reshape(3, NZ, NY, NX) - base))
print("라이브러리:", {k: len(v) for k, v in sorted(lib.items())}, "총", sum(len(v) for v in lib.values()))

def shift2d(d, di, dj):
    """x축(axis3) di셀, y축(axis2) dj셀 평행이동. 밖은 0."""
    if di == 0 and dj == 0: return d
    out = np.zeros_like(d)
    xs_src = slice(max(0, -di), NX - max(0, di)); xs_dst = slice(max(0, di), NX - max(0, -di))
    ys_src = slice(max(0, -dj), NY - max(0, dj)); ys_dst = slice(max(0, dj), NY - max(0, -dj))
    out[:, :, ys_dst, xs_dst] = d[:, :, ys_src, xs_src]
    return out

def predict(cid, mode, k):
    obs = json.loads(rows[cid]['obstacles_json'])
    pred = base.copy()
    for o in obs:
        cand = lib.get((o['kind'], o['size']))
        if not cand: continue
        ds = sorted(((o['x']-x)**2*LX**2 + (o['y']-y)**2*LY**2, x, y, d) for x, y, d in cand)[:k]
        w = np.array([1.0/(np.sqrt(t[0]) + 5e-3) for t in ds]); w /= w.sum()
        for wi, (dist, x, y, d) in zip(w, ds):
            if mode == 'shift':
                d = shift2d(d, int(round((o['x']-x)*LX/dx)), int(round((o['y']-y)*LY/dy)))
            pred += wi * d
    return pred.reshape(-1)

def report(name, fn):
    ev = np.array([R.eval_case(U[idx[c]], fn(c), occ[idx[c], 0], mean) for c in te])
    print(f"{name:<28}{np.nanmedian(ev[:,0]):>8.3f}{np.nanmedian(ev[:,1]):>11.3f}"
          f"{np.median(ev[:,2]):>9.3f}{ev[:,2].min():>9.3f}{np.median(ev[:,3]):>10.1f}")
    return ev

print(f"\n{'method':<28}{'relL2':>8}{'anomL2 med':>11}{'IoU med':>9}{'IoU min':>9}{'cdist_mm':>10}")
print("-"*75)
report("baseline_meanfield", lambda c: mean)
ev = {}
ev['sup_nearest_k1']   = report("superpose_nearest(k=1)",  lambda c: predict(c, 'none', 1))
ev['sup_shift_k1']     = report("superpose_shift(k=1)",    lambda c: predict(c, 'shift', 1))
ev['sup_shift_k3']     = report("superpose_shift(k=3, IDW)", lambda c: predict(c, 'shift', 3))
ev['sup_shift_k4']     = report("superpose_shift(k=4, IDW)", lambda c: predict(c, 'shift', 4))

print("\n--- per-case (superpose_shift k=3) ---")
e = ev['sup_shift_k3']
for c, row in zip(te, e):
    o = json.loads(rows[c]['obstacles_json'])
    desc = "+".join(f"{x['kind'][:4]}{x['size']}" for x in o) or "none"
    print(f"  {c} {desc:<22} anomL2={row[1]:.3f} IoU={row[2]:.3f} cdist={row[3]:.1f}mm")
