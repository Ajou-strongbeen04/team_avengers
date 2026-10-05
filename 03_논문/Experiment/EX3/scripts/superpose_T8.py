# T8. 직접 가법성 검사 — 두 번째 교란을 더하는 것이 실제로 이득인가
# span{u_A}, span{u_A,u_B} 최적계수 적합 = "가법성 상한(ceiling)"
import sys, json, csv, collections, os
import numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0, 'scripts'); import rom_pod as R
R.set_pool(2); NZ, NY, NX = R.NZ, R.NY, R.NX
LX, LY = 0.47, 0.21; dx, dy = LX/NX, LY/NY
rows = {r['case_id']: r for r in csv.DictReader(open('CFD/cases.csv'))}
ids = sorted(d for d in os.listdir('dataset/result') if d.startswith('case') and not d.endswith('.tgz'))
U, occ = R.load_fields('/tmp/fields/fields', ids); idx = {c: i for i, c in enumerate(ids)}
base = U[idx['case0000']].reshape(3, NZ, NY, NX)
obs = {c: json.loads(rows[c]['obstacles_json']) for c in ids}
blk = {c: float(rows[c]['blockage_frac']) for c in ids}
T1 = [c for c in ids if rows[c]['tier'] == '1']; T2 = [c for c in ids if rows[c]['tier'] == '2']
P = {c: U[idx[c]].reshape(3, NZ, NY, NX) - base for c in T1}
mean_all = U.mean(0)

def shift2d(d, di, dj):
    if di == 0 and dj == 0: return d
    o = np.zeros_like(d)
    o[:, :, slice(max(0, dj), NY-max(0, -dj)), slice(max(0, di), NX-max(0, -di))] = \
        d[:, :, slice(max(0, -dj), NY-max(0, dj)), slice(max(0, -di), NX-max(0, di))]
    return o

lib = collections.defaultdict(list)
for c in T1:
    o = obs[c][0]; lib[(o['kind'], o['size'])].append((o['x'], o['y'], P[c]))

def atom(o, k=3):
    """구조물 o 하나에 대한 라이브러리 교란 원자 (이동+IDW)."""
    cand = lib.get((o['kind'], o['size']))
    if not cand: return None, np.nan
    ds = sorted(((o['x']-x)**2*LX**2 + (o['y']-y)**2*LY**2, x, y, d) for x, y, d in cand)[:k]
    w = np.array([1.0/(np.sqrt(t[0])+5e-3) for t in ds]); w /= w.sum()
    a = np.zeros_like(base)
    for wi, (dist, x, y, d) in zip(w, ds):
        a += wi*shift2d(d, int(round((o['x']-x)*LX/dx)), int(round((o['y']-y)*LY/dy)))
    return a, np.sqrt(ds[0][0])

def kindof(c):
    o = obs[c]
    return 'rock' if all(x['kind'] == 'rock' for x in o) else ('plant' if all(x['kind'] == 'plant' for x in o) else '혼합')

rec = []
for c in T2:
    if len(obs[c]) != 2: continue
    aA, dA = atom(obs[c][0]); aB, dB = atom(obs[c][1])
    if aA is None or aB is None: continue
    t = (U[idx[c]].reshape(3, NZ, NY, NX) - base).ravel()
    A = np.stack([aA.ravel(), aB.ravel()], 1)
    nt = np.linalg.norm(t) + 1e-30
    # 1항만 / 2항 합(계수1) / 2항 최적계수
    r1 = min(np.linalg.norm(t - A[:, j])/nt for j in (0, 1))
    r2 = np.linalg.norm(t - A.sum(1))/nt
    cA, *_ = np.linalg.lstsq(A[:, :1], t, rcond=None); rc1 = np.linalg.norm(t - A[:, :1]@cA)/nt
    cAB, *_ = np.linalg.lstsq(A, t, rcond=None);      rc2 = np.linalg.norm(t - A@cAB)/nt
    cos = float(A.sum(1) @ t/(np.linalg.norm(A.sum(1))*nt))
    rec.append((c, kindof(c), blk[c], max(dA, dB), r1, r2, rc1, rc2, cos, cAB[0], cAB[1]))

df = pd.DataFrame(rec, columns=['case', 'kind', 'blk', 'libdist', 'r_1atom', 'r_sum',
                                'ceil_1atom', 'ceil_2atom', 'cos', 'cA', 'cB'])
print("="*82)
print("T8. 가법성 직접검사 (n=2, 192케이스) — 잔차/||참교란|| (1.0 = 교란 전혀 못맞춤)")
print("="*82)
print(f"\n{'구성':<8}{'n':>5}{'1원자':>9}{'합(c=1)':>10}{'상한1원자':>10}{'상한2원자':>10}{'cos':>8}{'c_A':>7}{'c_B':>7}")
for g, v in list(df.groupby('kind')) + [('전체', df)]:
    print(f"{g:<8}{len(v):>5}{v.r_1atom.median():>9.3f}{v.r_sum.median():>10.3f}"
          f"{v.ceil_1atom.median():>10.3f}{v.ceil_2atom.median():>10.3f}{v.cos.median():>8.3f}"
          f"{v.cA.median():>7.2f}{v.cB.median():>7.2f}")
print("\n→ '상한2원자' < '상한1원자' 이면 두 번째 교란이 실제 정보를 준다(=가법성 이득).")
print("→ 최적계수 c 가 1 에서 멀수록 진폭 비선형.")

print("\n라이브러리 최근접거리별 (상한2원자 = 이동오차 제거 후 남는 가법성 한계):")
df['dbin'] = pd.cut(df.libdist, [0, .02, .035, .05, .08, 1])
print(df.pivot_table(index='dbin', values=['r_sum', 'ceil_2atom'], aggfunc='median', observed=True)
      .join(df.groupby('dbin', observed=True).size().rename('n')).round(3).to_string())
print("\n종류별 상한2원자 vs 실제합:")
print(df.pivot_table(index='kind', values=['r_sum', 'ceil_2atom', 'ceil_1atom'], aggfunc='median').round(3).to_string())
df.to_csv('/tmp/superpose_T8.csv', index=False)
