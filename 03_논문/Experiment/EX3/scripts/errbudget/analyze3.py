# -*- coding: utf-8 -*-
"""Tier2 근접쌍(25~40mm) — 52.5mm 미만 변위구간 flip 확률 (실제 CFD 쌍)"""
import json,numpy as np,sys
sys.path.insert(0,'/tmp'); import coarse as co
NXc,NYc,NZc=co.NXc,co.NYc,co.NZc
D={json.loads(l)['case']:json.loads(l) for l in open('/tmp/coarse_out.jsonl')}
pr=json.load(open('/tmp/t2pairs.json'))
def zmap(V,nyc,nxc,bottom=False):
    kz=NZc//3 if bottom else NZc; by,bx=NYc//nyc,NXc//nxc; out=np.zeros((nyc,nxc))
    for a in range(nyc):
        for b in range(nxc): out[a,b]=V[b*bx:(b+1)*bx,a*by:(a+1)*by,:kz].mean()
    return out.ravel()
F={}
ok=[(d,a,b) for d,a,b in pr if a in D and b in D]
print(f"Tier2 근접쌍 {len(ok)}개 (변위 {min(o[0] for o in ok)}~{max(o[0] for o in ok)}mm)")
for d,a,b in ok:
    for c in (a,b):
        if c not in F: F[c]=np.load(f'/tmp/Cf/{c}_coarse.npy').astype(np.float64).reshape(NXc,NYc,NZc)
for bottom in [False,True]:
    print(f"\n{'저층' if bottom else 'z평균'}: 격자별 flip / topQ위반 / Δzone_max / S_diff")
    for nyc,nxc in [(3,6),(4,9),(6,18),(8,27)]:
        fl=[];vq=[];dz=[];sd=[]
        for d,a,b in ok:
            za=zmap(F[a],nyc,nxc,bottom); zb=zmap(F[b],nyc,nxc,bottom)
            fl.append(int(za.argmin())!=int(zb.argmin()))
            q=max(1,len(za)//4); rank=np.argsort(np.argsort(za)); vq.append(rank[int(zb.argmin())]>=q)
            dz.append(np.abs(za-zb).max())
            i1,i2=np.argsort(za)[:2]; sd.append(abs((zb[i2]-zb[i1])-(za[i2]-za[i1]))/d)
        gaps=[]
        for c in F:
            v=np.sort(zmap(F[c],nyc,nxc,bottom)); gaps.append(v[1]-v[0])
        eps=np.median(gaps)
        print(f"  {nyc}x{nxc:<6} flip {np.mean(fl):.2f}  topQ위반 {np.mean(vq):.2f}  Δzone_max중앙 {np.median(dz):.2e}"
              f"  S_diff중앙 {np.median(sd):.2e} p90 {np.percentile(sd,90):.2e} mg/L/mm"
              f"  → δ_allow {eps/np.median(sd):.0f} / p90 {eps/np.percentile(sd,90):.0f} mm")
