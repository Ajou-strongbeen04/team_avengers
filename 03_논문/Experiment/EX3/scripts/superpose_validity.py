# 중첩 타당성 정량 평가 — 이론항 + 실측 분해
# 실행: EX3 폴더에서  python3 superpose_validity.py
import sys, json, csv, itertools, collections
import numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0, 'scripts'); import rom_pod as R
R.set_pool(2)
NZ, NY, NX = R.NZ, R.NY, R.NX
LX, LY, LZ = 0.47, 0.21, 0.21
dx, dy, dz = LX/NX, LY/NY, LZ/NZ
FIELDS = '/tmp/fields/fields'

rows = {r['case_id']: r for r in csv.DictReader(open('CFD/cases.csv'))}
import os
ids = sorted(d for d in os.listdir('dataset/result') if d.startswith('case') and not d.endswith('.tgz'))
U, occ = R.load_fields(FIELDS, ids)
idx = {c: i for i, c in enumerate(ids)}
base = U[idx['case0000']].reshape(3, NZ, NY, NX)
obs = {c: json.loads(rows[c]['obstacles_json']) for c in ids}
tier = {c: rows[c]['tier'] for c in ids}
blk = {c: float(rows[c]['blockage_frac']) for c in ids}
T1 = [c for c in ids if tier[c] == '1']
T2 = [c for c in ids if tier[c] == '2']
print(f"cases={len(ids)}  T1={len(T1)}  T2={len(T2)}  grid={NZ}x{NY}x{NX}")

def fld(c): return U[idx[c]].reshape(3, NZ, NY, NX)
def pert(c): return fld(c) - base
def L2(a): return float(np.linalg.norm(a))

# ---------------------------------------------------------------
# T7. 이론: 중첩이 버리는 비선형 교차항 / 유지하는 선형항  (Tier1 쌍)
# ---------------------------------------------------------------
def adv(a, b):   # (a·∇)b
    gx = np.gradient(b, dx, axis=3); gy = np.gradient(b, dy, axis=2); gz = np.gradient(b, dz, axis=1)
    return a[0]*gx + a[1]*gy + a[2]*gz

print("\n" + "="*78)
print("T7. 비선형 교차항 비율  rho = ||u_j·∇u_k + u_k·∇u_j|| / ||U0·∇u + u·∇U0||")
print("="*78)
P = {c: pert(c) for c in T1}
recs = []
for a, b in itertools.combinations(T1, 2):
    oa, ob = obs[a][0], obs[b][0]
    d = np.hypot((oa['x']-ob['x'])*LX, (oa['y']-ob['y'])*LY)
    ua, ub = P[a], P[b]
    cross = adv(ua, ub) + adv(ub, ua)
    lin = adv(base, ua) + adv(ua, base) + adv(base, ub) + adv(ub, base)
    recs.append((d, L2(cross)/(L2(lin)+1e-30), oa['kind'], ob['kind'], oa['size'], ob['size']))
df7 = pd.DataFrame(recs, columns=['d', 'rho', 'ka', 'kb', 'sa', 'sb'])
df7['pair'] = df7.apply(lambda r: 'rock-rock' if r.ka == r.kb == 'rock' else
                        ('plant-plant' if r.ka == r.kb == 'plant' else '혼합'), axis=1)
print(f"\n{'조합':<12}{'n':>5}{'rho 중앙':>10}{'rho p90':>9}")
for g, v in df7.groupby('pair'):
    print(f"{g:<12}{len(v):>5}{v.rho.median():>10.3f}{v.rho.quantile(.9):>9.3f}")
print(f"\n간격 의존 (rho 중앙값):")
bins = [0, .05, .10, .15, .20, .30, 1]
df7['db'] = pd.cut(df7.d, bins)
piv = df7.pivot_table(index='db', columns='pair', values='rho', aggfunc='median', observed=True)
print(piv.round(3).to_string())

# ---------------------------------------------------------------
# T3. 선형응답 검사 (같은 위치, 크기 S/M/L) — 이동오차 0인 순수 비선형 검사
# ---------------------------------------------------------------
print("\n" + "="*78)
print("T3. 크기 스윕 선형응답:  u_L 이 u_S 의 상수배인가 (모양 상관 cos, 진폭비 vs 차단비)")
print("="*78)
pos = collections.defaultdict(dict)
for c in T1:
    o = obs[c][0]; pos[(o['kind'], round(o['x'], 3), round(o['y'], 3))][o['size']] = c
out = []
for key, sz in pos.items():
    for s1, s2 in [('S', 'M'), ('S', 'L'), ('M', 'L')]:
        if s1 in sz and s2 in sz:
            u1, u2 = P[sz[s1]], P[sz[s2]]
            cos = float((u1*u2).sum()/(L2(u1)*L2(u2)+1e-30))
            out.append((key[0], f"{s1}->{s2}", cos, L2(u2)/(L2(u1)+1e-30),
                        blk[sz[s2]]/(blk[sz[s1]]+1e-12)))
df3 = pd.DataFrame(out, columns=['kind', 'pair', 'cos', 'amp_ratio', 'blk_ratio'])
print(f"\n{'kind':<7}{'pair':<8}{'n':>4}{'cos 중앙':>10}{'진폭비':>9}{'차단비':>9}{'진폭/차단':>10}")
for (k, p), v in df3.groupby(['kind', 'pair']):
    print(f"{k:<7}{p:<8}{len(v):>4}{v.cos.median():>10.3f}{v.amp_ratio.median():>9.2f}"
          f"{v.blk_ratio.median():>9.2f}{(v.amp_ratio/v.blk_ratio).median():>10.2f}")

# ---------------------------------------------------------------
# 라이브러리 + 이동 예측기 (기존 09 방식과 동일)
# ---------------------------------------------------------------
def shift2d(d, di, dj):
    if di == 0 and dj == 0: return d
    o = np.zeros_like(d)
    o[:, :, slice(max(0, dj), NY-max(0, -dj)), slice(max(0, di), NX-max(0, -di))] = \
        d[:, :, slice(max(0, -dj), NY-max(0, dj)), slice(max(0, -di), NX-max(0, di))]
    return o

def predict(case, lib, k=3):
    p = base.copy()
    for o in obs[case]:
        cand = lib.get((o['kind'], o['size']))
        if not cand: continue
        ds = sorted(((o['x']-x)**2*LX**2 + (o['y']-y)**2*LY**2, x, y, d) for x, y, d in cand)[:k]
        w = np.array([1.0/(np.sqrt(t[0])+5e-3) for t in ds]); w /= w.sum()
        for wi, (dist, x, y, d) in zip(w, ds):
            p += wi*shift2d(d, int(round((o['x']-x)*LX/dx)), int(round((o['y']-y)*LY/dy)))
    return p

def build_lib(cases):
    lib = collections.defaultdict(list)
    for c in cases:
        o = obs[c][0]; lib[(o['kind'], o['size'])].append((o['x'], o['y'], P[c]))
    return lib

mean_all = U.mean(0)

# ---------------------------------------------------------------
# T1. 이동오차 격리 — Tier1 LOO (구조물 1개 → 가법성 오차 0)
# T2. 총오차 — Tier2 (이동 + 가법성)
# ---------------------------------------------------------------
print("\n" + "="*78)
print("T1/T2. 오차원인 분해:  n=1 LOO(이동오차만)  vs  n=2(이동+가법성)")
print("="*78)
e1 = []
for c in T1:
    lib = build_lib([x for x in T1 if x != c])
    e1.append(R.eval_case(U[idx[c]], predict(c, lib).reshape(-1), occ[idx[c], 0], mean_all))
e1 = np.array(e1)

lib_all = build_lib(T1)
e2 = np.array([R.eval_case(U[idx[c]], predict(c, lib_all).reshape(-1), occ[idx[c], 0], mean_all)
               for c in T2])
em1 = np.array([R.eval_case(U[idx[c]], mean_all, occ[idx[c], 0], mean_all) for c in T1])
em2 = np.array([R.eval_case(U[idx[c]], mean_all, occ[idx[c], 0], mean_all) for c in T2])
print(f"\n{'set':<26}{'n':>5}{'anomL2':>9}{'IoU med':>9}{'cdist mm':>10}")
for nm, e in [('평균장 baseline (n=1)', em1), ('중첩 LOO  n=1 (이동만)', e1),
              ('평균장 baseline (n=2)', em2), ('중첩      n=2 (이동+가법)', e2)]:
    print(f"{nm:<26}{len(e):>5}{np.nanmedian(e[:, 1]):>9.3f}{np.median(e[:, 2]):>9.3f}{np.median(e[:, 3]):>10.1f}")

# 종류별
print(f"\n종류별 anomL2 중앙값:")
def kindof(c):
    o = obs[c]
    return 'rock' if all(x['kind'] == 'rock' for x in o) else ('plant' if all(x['kind'] == 'plant' for x in o) else '혼합')
for nm, cs, e in [('n=1 LOO', T1, e1), ('n=2', T2, e2)]:
    g = collections.defaultdict(list)
    for c, r in zip(cs, e): g[kindof(c)].append(r)
    s = "  ".join(f"{k}={np.nanmedian(np.array(v)[:, 1]):.3f}(n={len(v)})" for k, v in sorted(g.items()))
    print(f"  {nm:<9} {s}")

# ---------------------------------------------------------------
# T5. 전역 스케일 편향 alpha — 중첩이 교란을 과대계상하는가
# ---------------------------------------------------------------
print("\n" + "="*78)
print("T5. 최적 스케일  U ~ U0 + alpha*Σu   (alpha<1 이면 중첩이 교란 과대계상)")
print("="*78)
def alpha_of(cases, e_lib):
    num = den = 0.0; per = []
    for c in cases:
        du_t = (fld(c) - base).ravel()
        du_p = (predict(c, e_lib) - base).ravel()
        num += float(du_p @ du_t); den += float(du_p @ du_p)
        per.append(float(du_p @ du_t)/(float(du_p @ du_p)+1e-30))
    return num/den, np.array(per)
a2, per2 = alpha_of(T2, lib_all)
print(f"\n전체 n=2 최적 alpha = {a2:.3f}")
for k in ['rock', 'plant', '혼합']:
    sel = [i for i, c in enumerate(T2) if kindof(c) == k]
    if sel: print(f"  {k:<6} alpha 중앙={np.median(per2[sel]):.3f}  (n={len(sel)})")
# alpha 보정 후 재평가
e2a = np.array([R.eval_case(U[idx[c]], (base + a2*(predict(c, lib_all)-base)).reshape(-1),
                            occ[idx[c], 0], mean_all) for c in T2])
print(f"\nalpha 보정 후 n=2 : anomL2={np.nanmedian(e2a[:,1]):.3f}  IoU={np.median(e2a[:,2]):.3f}  cdist={np.median(e2a[:,3]):.1f}mm")

# ---------------------------------------------------------------
# T4. no-slip 위배 — 예측장이 고체 안에서 흐르는가
# ---------------------------------------------------------------
print("\n" + "="*78)
print("T4. 고체 셀 내부 잔류유속 (occ>0.5) — 참값 vs 중첩예측")
print("="*78)
vt, vp = [], []
for c in T2:
    m = occ[idx[c], 0] > 0.5
    if m.sum() == 0: continue
    ut = fld(c); up = predict(c, lib_all)
    U0m = np.abs(base).mean()
    vt.append(np.linalg.norm(ut[:, m], axis=0).mean()/U0m)
    vp.append(np.linalg.norm(up[:, m], axis=0).mean()/U0m)
print(f"\n고체내 |U| / |U0|평균 :  참값 {np.median(vt):.3f}   중첩예측 {np.median(vp):.3f}"
      f"   (배율 {np.median(vp)/np.median(vt):.1f}x, n={len(vt)})")

# ---------------------------------------------------------------
# T6. 오차 vs 간격 / 차단율
# ---------------------------------------------------------------
print("\n" + "="*78)
print("T6. n=2 중첩오차의 간격·차단율 의존")
print("="*78)
rec = []
for c, e in zip(T2, e2):
    o = obs[c]
    d = np.hypot((o[0]['x']-o[1]['x'])*LX, (o[0]['y']-o[1]['y'])*LY) if len(o) == 2 else np.nan
    rec.append((c, kindof(c), d, blk[c], e[1], e[2], e[3]))
df6 = pd.DataFrame(rec, columns=['case', 'kind', 'd', 'blk', 'anomL2', 'IoU', 'cdist'])
df6['dbin'] = pd.cut(df6.d, [0, .08, .14, .20, .28, 1])
print("\n간격별:")
print(df6.pivot_table(index='dbin', values=['anomL2', 'IoU'], aggfunc='median', observed=True)
      .join(df6.groupby('dbin', observed=True).size().rename('n')).round(3).to_string())
df6['bbin'] = pd.qcut(df6.blk, 4)
print("\n차단율별:")
print(df6.pivot_table(index='bbin', values=['anomL2', 'IoU'], aggfunc='median', observed=True)
      .join(df6.groupby('bbin', observed=True).size().rename('n')).round(3).to_string())
print("\n종류×차단율 (anomL2 중앙):")
print(df6.pivot_table(index='bbin', columns='kind', values='anomL2', aggfunc='median', observed=True).round(3).to_string())
df6.to_csv('/tmp/superpose_T6.csv', index=False)
print("\n[saved] /tmp/superpose_T6.csv")
