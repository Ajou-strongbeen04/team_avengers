# -*- coding: utf-8 -*-
import json,csv,itertools,numpy as np
D={}
for l in open('/tmp/coarse_out.jsonl'):
    d=json.loads(l); D[d['case']]=d
meta={}
for r in csv.DictReader(open("/sessions/youthful-eager-volta/mnt/Claude/03_논문/Experiment/EX3/CFD/cases.csv")):
    if not r['case_id'].startswith('case'): continue
    ob=json.loads(r['obstacles_json'])
    meta[r['case_id']]=dict(tier=r['tier'],n=len(ob),ob=ob,blk=float(r['blockage_frac']))
LX,LY=470.0,210.0
t1=[c for c in D if meta[c]['tier']=='1']
print("=== 1. 판정 여유폭 (ε_DO 후보) — 61케이스 ===")
for k,lab in [('zone_gap12','z평균 4x9 1위-2위'),('bzone_gap12','저층(하1/3) 4x9 1위-2위'),
              ('zone_gap13','z평균 1위-3위'),('bzone_gap13','저층 1위-3위'),
              ('zone_span','z평균 최대-최소'),('bzone_span','저층 최대-최소')]:
    v=np.array([D[c][k] for c in D])
    print(f"  {lab:<22} 중앙 {np.median(v):.3e}  p10 {np.percentile(v,10):.3e}  최소 {v.min():.3e}  최대 {v.max():.3e} mg/L")
v=np.array([8.263456697819732-D[c]['C_min'] for c in D])
print(f"  결핍 진폭 C*-Cmin        중앙 {np.median(v):.4f} mg/L (R=3e-4)")
print()
print("=== 2. 위치 민감도 — 동일 종류·크기, 앵커쌍 유한차분 ===")
rows=[]
for a,b in itertools.combinations(t1,2):
    oa=meta[a]['ob'][0]; ob=meta[b]['ob'][0]
    if (oa['kind'],oa['size'])!=(ob['kind'],ob['size']): continue
    dx=(oa['x']-ob['x'])*LX; dy=(oa['y']-ob['y'])*LY; d=np.hypot(dx,dy)
    za=np.array(D[a]['zoneDO']); zb=np.array(D[b]['zoneDO'])
    ba=np.array(D[a]['bzoneDO']); bb=np.array(D[b]['bzoneDO'])
    rows.append(dict(a=a,b=b,kind=oa['kind'],size=oa['size'],d=d,dx=abs(dx),dy=abs(dy),
        dzone_max=float(np.abs(za-zb).max()), dzone_rms=float(np.sqrt(((za-zb)**2).mean())),
        dbzone_max=float(np.abs(ba-bb).max()), dbzone_rms=float(np.sqrt(((ba-bb)**2).mean())),
        dCmin=abs(D[a]['C_min']-D[b]['C_min']),
        flip=int(D[a]['zone_top1']!=D[b]['zone_top1']), bflip=int(D[a]['bzone_top1']!=D[b]['bzone_top1'])))
R=rows
print(f"  쌍 수 {len(R)}")
for lo,hi in [(0,60),(60,100),(100,150),(150,400)]:
    s=[r for r in R if lo<=r['d']<hi]
    if not s: continue
    dz=np.array([r['dzone_max'] for r in s]); db=np.array([r['dbzone_max'] for r in s])
    dd=np.array([r['d'] for r in s])
    print(f"  이격 {lo}~{hi}mm (n={len(s)}, 평균 {dd.mean():.0f}mm): "
          f"Δzone_max 중앙 {np.median(dz):.3e} → {np.median(dz/dd):.3e} mg/L/mm | "
          f"저층 {np.median(db):.3e} → {np.median(db/dd):.3e} | "
          f"top1 flip {np.mean([r['flip'] for r in s]):.2f} / 저층 {np.mean([r['bflip'] for r in s]):.2f}")
# 최소 이격(52.5mm, y 인접) 만
s=[r for r in R if abs(r['d']-52.5)<1]
dz=np.array([r['dzone_max'] for r in s]); db=np.array([r['dbzone_max'] for r in s])
print(f"\n  [최소이격 52.5mm y인접, n={len(s)}]  Δzone_max 중앙 {np.median(dz):.3e}  p90 {np.percentile(dz,90):.3e} mg/L")
print(f"     → 단위변위 민감도 S_zone 중앙 {np.median(dz)/52.5:.3e}  p90 {np.percentile(dz,90)/52.5:.3e} mg/L/mm")
print(f"     저층 S 중앙 {np.median(db)/52.5:.3e}  p90 {np.percentile(db,90)/52.5:.3e} mg/L/mm")
print(f"     top1 flip {np.mean([r['flip'] for r in s]):.2f}  저층 flip {np.mean([r['bflip'] for r in s]):.2f}")
print(f"     ΔCmin 중앙 {np.median([r['dCmin'] for r in s]):.3e} → {np.median([r['dCmin'] for r in s])/52.5:.3e} mg/L/mm")
print()
print("=== 3. 크기 민감도 — 동일 앵커, 크기등급 변경 ===")
# 등가 대표치수: rock S 4x4x4, M 7x6x7, L 11x8x10 cm (sweep_design §8)
dim={'rock':{'S':(40,40,40),'M':(70,60,70),'L':(110,80,100)},
     'plant':{'S':None,'M':None,'L':None}}
for kind in ['rock','plant']:
    for (s1,s2) in [('S','M'),('M','L')]:
        pairs=[]
        for a in t1:
            oa=meta[a]['ob'][0]
            if oa['kind']!=kind or oa['size']!=s1: continue
            for b in t1:
                ob=meta[b]['ob'][0]
                if ob['kind']!=kind or ob['size']!=s2: continue
                if (oa['x'],oa['y'])!=(ob['x'],ob['y']): continue
                za=np.array(D[a]['zoneDO']); zb=np.array(D[b]['zoneDO'])
                ba=np.array(D[a]['bzoneDO']); bb=np.array(D[b]['bzoneDO'])
                pairs.append((a,b,float(np.abs(za-zb).max()),float(np.abs(ba-bb).max()),
                              abs(D[a]['C_min']-D[b]['C_min']),
                              int(D[a]['zone_top1']!=D[b]['zone_top1']),int(D[a]['bzone_top1']!=D[b]['bzone_top1']),
                              meta[b]['blk']-meta[a]['blk']))
        if not pairs: continue
        dz=np.median([p[2] for p in pairs]); db=np.median([p[3] for p in pairs])
        print(f"  {kind} {s1}→{s2} (n={len(pairs)}, Δblockage {pairs[0][7]:+.4f}): "
              f"Δzone_max {dz:.3e} | 저층 {db:.3e} | ΔCmin {np.median([p[4] for p in pairs]):.3e} | "
              f"flip {np.mean([p[5] for p in pairs]):.2f}/저층 {np.mean([p[6] for p in pairs]):.2f}")
print()
print("=== 4. 구조물 유무(n=0 대비) — 절대 기준 ===")
z0=np.array(D['case0000']['zoneDO']); b0=np.array(D['case0000']['bzoneDO'])
dz=[float(np.abs(np.array(D[c]['zoneDO'])-z0).max()) for c in t1]
db=[float(np.abs(np.array(D[c]['bzoneDO'])-b0).max()) for c in t1]
print(f"  Δzone_max vs case0000: 중앙 {np.median(dz):.3e} 최대 {max(dz):.3e} mg/L")
print(f"  저층: 중앙 {np.median(db):.3e} 최대 {max(db):.3e} mg/L")
print(f"  top1 구역 분포(z평균): {sorted(set(D[c]['zone_top1'] for c in D))}")
print(f"  top1 구역 분포(저층):  {sorted(set(D[c]['bzone_top1'] for c in D))}")
from collections import Counter
print("  z평균 top1 빈도:",Counter(D[c]['zone_top1'] for c in D).most_common())
print("  저층 top1 빈도:",Counter(D[c]['bzone_top1'] for c in D).most_common())
