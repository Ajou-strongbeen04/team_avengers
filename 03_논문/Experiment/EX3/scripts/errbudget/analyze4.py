# -*- coding: utf-8 -*-
"""깊이축 통합 판정(1xN)의 방향별 민감도 — VLM 깊이 미관측 대응 검토"""
import json,csv,itertools,numpy as np,sys
sys.path.insert(0,'/tmp'); import coarse as co
NXc,NYc,NZc=co.NXc,co.NYc,co.NZc
D={json.loads(l)['case']:json.loads(l) for l in open('/tmp/coarse_out.jsonl')}
meta={r['case_id']:r for r in csv.DictReader(open("/sessions/youthful-eager-volta/mnt/Claude/03_논문/Experiment/EX3/CFD/cases.csv"))}
F={c:np.load(f'/tmp/Cf/{c}_coarse.npy').astype(np.float64).reshape(NXc,NYc,NZc) for c in D}
def zmap(V,nyc,nxc):
    by,bx=NYc//nyc,NXc//nxc; out=np.zeros((nyc,nxc))
    for a in range(nyc):
        for b in range(nxc): out[a,b]=V[b*bx:(b+1)*bx,a*by:(a+1)*by,:].mean()
    return out.ravel()
t1=[c for c in D if meta[c]['tier']=='1']
pairs=[]
for a,b in itertools.combinations(t1,2):
    oa=json.loads(meta[a]['obstacles_json'])[0]; ob=json.loads(meta[b]['obstacles_json'])[0]
    if (oa['kind'],oa['size'])!=(ob['kind'],ob['size']): continue
    dx=abs(oa['x']-ob['x'])*470; dy=abs(oa['y']-ob['y'])*210   # dy = 깊이(폭)방향
    pairs.append((a,b,dx,dy))
def stat(sel,nyc,nxc):
    fl=[];vq=[];sd=[]
    for a,b,dx,dy in sel:
        za,zb=zmap(F[a],nyc,nxc),zmap(F[b],nyc,nxc)
        fl.append(int(za.argmin())!=int(zb.argmin()))
        q=max(1,len(za)//4); rank=np.argsort(np.argsort(za)); vq.append(rank[int(zb.argmin())]>=q)
        d=np.hypot(dx,dy); i1,i2=np.argsort(za)[:2]
        sd.append(abs((zb[i2]-zb[i1])-(za[i2]-za[i1]))/d)
    gaps=[np.sort(zmap(F[c],nyc,nxc))[1]-np.sort(zmap(F[c],nyc,nxc))[0] for c in D]
    return np.mean(fl),np.mean(vq),np.median(gaps),np.median(sd),np.percentile(sd,90),len(sel)
pure_d=[p for p in pairs if p[2]==0 and abs(p[3]-52.5)<1]      # 깊이만 52.5mm
pure_x=[p for p in pairs if p[3]==0 and abs(p[2]-94)<1]        # x만 94mm
print("동일 종류·크기 쌍:", f"깊이만 52.5mm n={len(pure_d)} · x만 94mm n={len(pure_x)}")
for nyc,nxc in [(4,9),(1,9),(1,6),(1,18)]:
    lab=f"{nyc}x{nxc}"
    a=stat(pure_d,nyc,nxc); b=stat(pure_x,nyc,nxc)
    print(f"\n[{lab}] 구역 {nyc*nxc}개 · 블록 {210/nyc:.0f}(깊이)x{470/nxc:.0f}(좌우) mm")
    print(f"   깊이 변위 52.5mm: flip {a[0]:.2f} topQ위반 {a[1]:.2f} | eps {a[2]:.2e} S {a[3]:.2e} → δ_allow {a[2]/a[3]:.0f}mm (p90 {a[2]/a[4]:.0f}mm)")
    print(f"   x    변위 94.0mm: flip {b[0]:.2f} topQ위반 {b[1]:.2f} | S {b[3]:.2e} → δ_allow {b[2]/b[3]:.0f}mm (p90 {b[2]/b[4]:.0f}mm)")
