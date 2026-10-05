# chi(DO 결핍 응답장) 의 차원성 vs U 의 차원성 — 같은 11케이스
import sys,os,re,gzip,numpy as np
sys.path.insert(0,'scripts'); import rom_pod as R
R.set_pool(2); NZ,NY,NX=R.NZ,R.NY,R.NX
NX0,NY0,NZ0=108,48,48
def read_field(path):
    return np.loadtxt(path)
D='dataset/stageB_DO/fields'
ids=sorted(f[:8] for f in os.listdir(D) if f.endswith('_C.gz'))
Cs=CST=8.263456697819732; Rr=3.0e-4
X=[]
for c in ids:
    C=read_field(f'{D}/{c}_C.gz')
    X.append(((CST-C)/Rr).astype(np.float64))
X=np.array(X); print('chi cases',X.shape, 'chi mean',X.mean().round(1),'range',X.min().round(1),X.max().round(1))
U,occ=R.load_fields('/tmp/fields/fields',ids)
def spectrum(M,name):
    m=M.mean(0); A=M-m
    s=np.linalg.svd(A,compute_uv=False); e=s**2/ (s**2).sum()
    cum=np.cumsum(e)
    nrm=np.linalg.norm(A,axis=1)/ (np.linalg.norm(M,axis=1)+1e-30)
    print(f"\n{name}: 평균장 대비 케이스 변동(상대) 중앙={np.median(nrm):.4f}")
    print("  모드별 에너지비:", " ".join(f"{x:.3f}" for x in e[:6]))
    print("  누적:          ", " ".join(f"{x:.3f}" for x in cum[:6]))
    return e
spectrum(X,'chi (DO 결핍 응답장)')
spectrum(U.astype(np.float64),'U (유동장)')
# 공간구조 지표: chi 저DO 하위10% 영역이 케이스마다 얼마나 다른가
def mask10(v, occ0=None):
    t=np.percentile(v,90); return v>=t     # chi 클수록 저DO
M=[mask10(x) for x in X]
iou=[]
for i in range(len(ids)):
    for j in range(i+1,len(ids)):
        iou.append((M[i]&M[j]).sum()/(M[i]|M[j]).sum())
print(f"\n케이스쌍 저DO영역 IoU: 중앙={np.median(iou):.3f} 최소={min(iou):.3f}  (1.0=기하 무관)")
mm=mask10(X.mean(0))
print(f"평균 chi 로 예측한 저DO영역 IoU: 중앙={np.median([ (mm&m).sum()/(mm|m).sum() for m in M]):.3f}")
# 대응: U 저유속 영역 IoU (같은 케이스)
Um=[R.lowvel_mask(U[i],occ[i,0]) for i in range(len(ids))]
iu=[]
for i in range(len(ids)):
    for j in range(i+1,len(ids)): iu.append((Um[i]&Um[j]).sum()/(Um[i]|Um[j]).sum())
print(f"케이스쌍 저유속영역 IoU: 중앙={np.median(iu):.3f} 최소={min(iu):.3f}")
