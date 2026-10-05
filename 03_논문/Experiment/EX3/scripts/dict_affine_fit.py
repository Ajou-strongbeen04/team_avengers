# 아핀 제약(sum w = 1) 판: 평균장/기저유동을 보존하도록 강제
import sys, json, csv, os
import numpy as np, pandas as pd
pd.read_parquet = lambda p,**k: pd.read_csv(p)
sys.path.insert(0,'scripts'); import rom_pod as R
R.set_pool(2)
rows={r['case_id']:r for r in csv.DictReader(open('CFD/cases.csv'))}
ids=sorted(d for d in os.listdir('dataset/result') if d.startswith('case') and not d.endswith('.tgz'))
U,occ=R.load_fields('/tmp/fields/fields',ids); lab=pd.read_csv('/tmp/fields/labels.csv')
N=len(ids); mean_all=U.mean(0)
obs={c:json.loads(rows[c]['obstacles_json']) for c in ids}
def kindof(c):
    o=obs[c]; return 'none' if not o else ('rock' if all(x['kind']=='rock' for x in o) else ('plant' if all(x['kind']=='plant' for x in o) else '혼합'))
G=R.geom_features(occ,lab,ids); G=(G-G.mean(0))/(G.std(0)+1e-9)
Dg=((G[:,None,:]-G[None,:,:])**2).sum(-1); np.fill_diagonal(Dg,np.inf)
Occ=occ.reshape(N,-1).astype(np.float64)
def solve_aff(B,q,lam):
    K=len(B); A=B@B.T; sc=max(1e-12,np.trace(A)/K)
    M=np.zeros((K+1,K+1)); M[:K,:K]=A+lam*sc*np.eye(K); M[:K,K]=1; M[K,:K]=1
    r=np.zeros(K+1); r[:K]=B@q; r[K]=1
    return np.linalg.solve(M,r)[:K]
print(f"{'방법 (아핀제약 sum w=1)':<38}{'K':>4}{'anomL2':>9}{'IoU med':>9}{'IoU p10':>9}{'cdist':>8}")
store={}
for K in [8,16,32,64]:
    for lam in [1e-2,1e-1,1.0]:
        E=[]
        for i in range(N):
            c=np.argsort(Dg[i])[:K]
            w=solve_aff(Occ[c],Occ[i],lam)
            E.append(R.eval_case(U[i], w@U[c], occ[i,0], mean_all))
        E=np.array(E); store[(K,lam)]=E
        print(f"{'occ-fit lam=%.0e'%lam:<38}{K:>4}{np.nanmedian(E[:,1]):>9.3f}{np.median(E[:,2]):>9.3f}{np.percentile(E[:,2],10):>9.3f}{np.median(E[:,3]):>8.1f}")
E=store[(32,1e-1)]
print("\n종류별 (occ-fit K=32 lam=1e-1):")
for g in ['plant','rock','혼합']:
    s=[i for i,c in enumerate(ids) if kindof(c)==g]
    print(f"  {g:<6} n={len(s):>3}  anomL2={np.nanmedian(E[s,1]):.3f}  IoU={np.median(E[s,2]):.3f}  cdist={np.median(E[s,3]):.1f}mm")
