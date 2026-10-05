# 오라클 없이 가중치를 구하는 현실적 방법:
#   "내 기하를 사전 기하들의 조합으로 표현" → 같은 조합을 유동장에 적용
#   w = argmin || occ_q - sum w_k occ_k ||^2 + lam||w||^2   →  U_pred = sum w_k U_k
import sys, json, csv, os
import numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0, 'scripts'); import rom_pod as R
R.set_pool(2); NZ, NY, NX = R.NZ, R.NY, R.NX
rows = {r['case_id']: r for r in csv.DictReader(open('CFD/cases.csv'))}
ids = sorted(d for d in os.listdir('dataset/result') if d.startswith('case') and not d.endswith('.tgz'))
U, occ = R.load_fields('/tmp/fields/fields', ids)
lab = pd.read_csv('/tmp/fields/labels.csv')
N = len(ids); mean_all = U.mean(0)
obs = {c: json.loads(rows[c]['obstacles_json']) for c in ids}
def kindof(c):
    o = obs[c]
    return 'none' if not o else ('rock' if all(x['kind']=='rock' for x in o)
           else ('plant' if all(x['kind']=='plant' for x in o) else '혼합'))
G = R.geom_features(occ, lab, ids); G = (G-G.mean(0))/(G.std(0)+1e-9)
Dg = ((G[:,None,:]-G[None,:,:])**2).sum(-1); np.fill_diagonal(Dg, np.inf)
# 기하 표상: 점유+kind 격자를 flat (사진에서 알 수 있는 정보)
Occ = occ.reshape(N, -1).astype(np.float64)
nrm = (U*U).sum(1); Df = nrm[:,None]+nrm[None,:]-2*(U@U.T); np.fill_diagonal(Df, np.inf)

def run(K, lam, use_feat=False):
    E=[]
    for i in range(N):
        cand = np.argsort(Dg[i])[:K]
        B = (G[cand] if use_feat else Occ[cand])          # (K, M)
        q = (G[i] if use_feat else Occ[i])
        A = B @ B.T + lam*np.eye(K)*max(1e-12,(B*B).sum()/K)
        w = np.linalg.solve(A, B @ q)
        E.append(R.eval_case(U[i], w @ U[cand], occ[i,0], mean_all))
    E=np.array(E)
    return E

print(f"{'방법':<40}{'K':>5}{'anomL2':>9}{'IoU med':>9}{'IoU p10':>9}{'cdist':>8}")
E0=np.array([R.eval_case(U[i], mean_all, occ[i,0], mean_all) for i in range(N)])
print(f"{'baseline 평균장':<40}{'-':>5}{np.nanmedian(E0[:,1]):>9.3f}{np.median(E0[:,2]):>9.3f}{np.percentile(E0[:,2],10):>9.3f}{np.median(E0[:,3]):>8.1f}")
best={}
for K in [8,16,32,64]:
    for lam in [1e-3, 1e-2, 1e-1]:
        E=run(K,lam)
        print(f"{'기하격자 적합 (occ-fit) lam=%.0e'%lam:<40}{K:>5}{np.nanmedian(E[:,1]):>9.3f}"
              f"{np.median(E[:,2]):>9.3f}{np.percentile(E[:,2],10):>9.3f}{np.median(E[:,3]):>8.1f}")
        best[(K,lam)]=E
print()
for K in [16,32]:
    E=run(K,1e-2,use_feat=True)
    print(f"{'기하특징 적합 (feat-fit) lam=1e-2':<40}{K:>5}{np.nanmedian(E[:,1]):>9.3f}"
          f"{np.median(E[:,2]):>9.3f}{np.percentile(E[:,2],10):>9.3f}{np.median(E[:,3]):>8.1f}")
# 종류별 (최적 조합)
E=best[(32,1e-2)]
print("\n종류별 (occ-fit K=32 lam=1e-2):")
for g in ['plant','rock','혼합']:
    s=[i for i,c in enumerate(ids) if kindof(c)==g]
    print(f"  {g:<6} n={len(s):>3}  anomL2={np.nanmedian(E[s,1]):.3f}  IoU={np.median(E[s,2]):.3f}  cdist={np.median(E[s,3]):.1f}mm")
