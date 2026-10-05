# -*- coding: utf-8 -*-
"""해상도별 판정 flip 확률 vs 기하 변위 — VLM 허용오차 도출"""
import json,csv,itertools,numpy as np, sys
sys.path.insert(0,'/tmp'); import coarse as co
NXc,NYc,NZc=co.NXc,co.NYc,co.NZc
D={}
for l in open('/tmp/coarse_out.jsonl'):
    d=json.loads(l); D[d['case']]=d
meta={}
for r in csv.DictReader(open("/sessions/youthful-eager-volta/mnt/Claude/03_논문/Experiment/EX3/CFD/cases.csv")):
    if r['case_id'].startswith('case'):
        meta[r['case_id']]=dict(tier=r['tier'],ob=json.loads(r['obstacles_json']),blk=float(r['blockage_frac']))
LX,LY=470.0,210.0
cases=sorted(D)
F={c:np.load(f'/tmp/Cf/{c}_coarse.npy').astype(np.float64).reshape(NXc,NYc,NZc) for c in cases}
def zmap(V,nyc,nxc,bottom=False):
    kz=NZc//3 if bottom else NZc
    by,bx=NYc//nyc,NXc//nxc; out=np.zeros((nyc,nxc))
    for a in range(nyc):
        for b in range(nxc):
            out[a,b]=V[b*bx:(b+1)*bx,a*by:(a+1)*by,:kz].mean()
    return out.ravel()
ZONINGS=[(2,3),(3,6),(4,9),(6,18),(8,27)]
t1=[c for c in cases if meta[c]['tier']=='1']
pairs=[]
for a,b in itertools.combinations(t1,2):
    oa,ob=meta[a]['ob'][0],meta[b]['ob'][0]
    if (oa['kind'],oa['size'])!=(ob['kind'],ob['size']): continue
    d=np.hypot((oa['x']-ob['x'])*LX,(oa['y']-ob['y'])*LY)
    pairs.append((a,b,d,oa['kind'],oa['size']))
print(f"동일 종류·크기 앵커쌍 {len(pairs)}개 (이격 {min(p[2] for p in pairs):.1f}~{max(p[2] for p in pairs):.1f}mm)")
BINS=[(50,60),(90,100),(100,130),(130,200),(200,400)]
for bottom in [False,True]:
    print(f"\n=== {'저층(하1/3)' if bottom else 'z평균'} 위험맵 — 변위구간별 top1 flip 확률 / topQ 위반율 ===")
    Z={}
    for nyc,nxc in ZONINGS:
        Z[(nyc,nxc)]={c:zmap(F[c],nyc,nxc,bottom) for c in cases}
    hdr="  격자      블록cm     "+ "".join(f"{lo}~{hi}mm".rjust(13) for lo,hi in BINS)
    print(hdr)
    for nyc,nxc in ZONINGS:
        z=Z[(nyc,nxc)]; row=f"  {nyc}x{nxc:<7}{LY/nyc:.1f}x{LX/nxc:.1f}  "
        for lo,hi in BINS:
            s=[p for p in pairs if lo<=p[2]<hi]
            if not s: row+=f"{'-':>13}"; continue
            fl=[]; vq=[]
            for a,b,d,k,sz in s:
                za,zb=z[a],z[b]
                t1a,t1b=int(za.argmin()),int(zb.argmin())
                fl.append(t1a!=t1b)
                q=max(1,len(za)//4); rank=np.argsort(np.argsort(za))
                vq.append(rank[t1b]>=q)     # 예측(b)의 1위가 실제(a) 하위25% 밖 = 위반
            row+=f"{np.mean(fl):.2f}/{np.mean(vq):.2f}".rjust(13)
        print(row)
    # 판정 여유폭·차분민감도 (4x9 기준 + 각 해상도)
    print(f"  --- ε_DO(1위-2위 격차, 중앙) 및 차분민감도 S_diff=|Δ(gap)|/d (52.5mm쌍) ---")
    for nyc,nxc in ZONINGS:
        z=Z[(nyc,nxc)]
        gaps=[]
        for c in cases:
            v=np.sort(z[c]); gaps.append(v[1]-v[0])
        s=[p for p in pairs if abs(p[2]-52.5)<1]
        sd=[]
        for a,b,d,k,sz in s:
            za,zb=z[a],z[b]; i1,i2=np.argsort(za)[:2]
            sd.append(abs((zb[i2]-zb[i1])-(za[i2]-za[i1]))/d)
        eps=np.median(gaps); S=np.median(sd)
        print(f"    {nyc}x{nxc:<6} ε_DO {eps:.3e} mg/L | S_diff {S:.3e} mg/L/mm | δ_allow = ε/S = {eps/S:6.1f} mm"
              f" | p90 S {np.percentile(sd,90):.3e} → {eps/np.percentile(sd,90):5.1f} mm")
# 크기 채널 (4x9, 저층)
print("\n=== 크기 등급 오판 — flip 확률 (4x9) ===")
dimL={'rock':{'S':40,'M':70,'L':110},'plant':{'S':40,'M':70,'L':110}}
for bottom in [False,True]:
    for kind in ['rock','plant']:
        for s1,s2 in [('S','M'),('M','L'),('S','L')]:
            fl=[];vq=[]
            for a in t1:
                oa=meta[a]['ob'][0]
                if oa['kind']!=kind or oa['size']!=s1: continue
                for b in t1:
                    ob=meta[b]['ob'][0]
                    if ob['kind']!=kind or ob['size']!=s2 or (oa['x'],oa['y'])!=(ob['x'],ob['y']): continue
                    za=zmap(F[a],4,9,bottom); zb=zmap(F[b],4,9,bottom)
                    t1a,t1b=int(za.argmin()),int(zb.argmin()); fl.append(t1a!=t1b)
                    q=max(1,len(za)//4); rank=np.argsort(np.argsort(za)); vq.append(rank[t1b]>=q)
            if fl: print(f"  {'저층' if bottom else 'z평균'} {kind} {s1}→{s2} (등가 {dimL[kind][s1]}→{dimL[kind][s2]}mm, n={len(fl)}): flip {np.mean(fl):.2f} topQ위반 {np.mean(vq):.2f}")
