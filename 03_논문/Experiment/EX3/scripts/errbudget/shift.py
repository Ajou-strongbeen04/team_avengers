# -*- coding: utf-8 -*-
"""국소(mm급) 민감도 — 단일구조물 유동 이상장을 정수셀 평행이동 → 조대 DO 재해석.
검증: y+12셀(=52.5mm) 이동 결과 vs 실제 CFD 인접앵커 케이스(예 case0001→case0002)."""
import sys,os,json,time
sys.path.insert(0,'/tmp'); sys.path.insert(0,"/sessions/youthful-eager-volta/mnt/Claude/03_논문/Experiment/EX3/dataset/stageB_DO")
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla
import solve_do as sd, coarse as co
NX,NY,NZ,P=co.NX,co.NY,co.NZ,co.P
def fine(case):
    nb=co.facemaps()['nb']
    phi=sd.read_field(f"{co.RES}/{case}/200/phiMean.gz")[:len(nb)]
    nut=sd.read_field(f"{co.RES}/{case}/200/nutMean.gz")
    Fx,Fy,Fz=co.fine_flux_arrays(phi)
    return Fx,Fy,Fz,nut.reshape(NZ,NY,NX).transpose(2,1,0)
def shift_arr(A,s,axis):
    out=np.zeros_like(A)
    if s==0: return A.copy()
    sl_dst=[slice(None)]*3; sl_src=[slice(None)]*3
    sl_dst[axis]=slice(s,None); sl_src[axis]=slice(0,A.shape[axis]-s)
    out[tuple(sl_dst)]=A[tuple(sl_src)]
    return out
def coarsen_from(Fx,Fy,Fz,nut3):
    NXc,NYc,NZc=co.NXc,co.NYc,co.NZc
    FXc=Fx[1::P,:,:].reshape(NXc-1,NYc,P,NZc,P).sum(axis=(2,4))
    FYc=Fy[:,1::P,:].reshape(NXc,P,NYc-1,NZc,P).sum(axis=(1,4))
    FZc=Fz[:,:,1::P].reshape(NXc,P,NYc,P,NZc-1).sum(axis=(1,3))
    nutc=nut3.reshape(NXc,P,NYc,P,NZc,P).mean(axis=(1,3,5))
    return FXc,FYc,FZc,nutc
def build_from(FXc,FYc,FZc,nutc,case_for_plume):
    # coarse.build_coarse 의 후반부와 동일 (조립부 복제 최소화 위해 monkey-patch)
    orig=co.coarsen
    co.coarsen=lambda case,**kw:(FXc,FYc,FZc,nutc)
    try: A,b,Cs,aux=co.build_coarse(f"{co.RES}/{case_for_plume}")
    finally: co.coarsen=orig
    return A,b,Cs,aux
def run(src,base,shifts,axis=1,out='/tmp/shift_out.jsonl',budget=36.0):
    t0=time.time()
    done=set()
    if os.path.exists(out): done={json.loads(l)['case'] for l in open(out)}
    Fxb,Fyb,Fzb,nb3=fine(base); Fxs,Fys,Fzs,ns3=fine(src)
    dFx,dFy,dFz,dn=Fxs-Fxb,Fys-Fyb,Fzs-Fzb,ns3-nb3
    for s in shifts:
        tag=f"{src}_sh{axis}{s:+d}"
        if tag in done: continue
        if time.time()-t0>budget: print("BUDGET STOP",tag,flush=True); break
        t=time.time()
        Fx=Fxb+shift_arr(dFx,s,axis); Fy=Fyb+shift_arr(dFy,s,axis)
        Fz=Fzb+shift_arr(dFz,s,axis); nut3=nb3+shift_arr(dn,s,axis)
        A,b,Cs,aux=build_from(*coarsen_from(Fx,Fy,Fz,nut3),base)
        C,info=co.solve_coarse(A,b)
        disp=s*(co.DYc/P if axis==1 else co.DXc/P)*1e3
        m=co.metrics_c(C,Cs,aux,dict(case=tag,src=src,axis=axis,shift=s,disp_mm=round(disp,3),
                                     info=int(info),t_s=round(time.time()-t,2)))
        np.save(f"/tmp/Cf/{tag}.npy",C.astype(np.float32))
        open(out,'a').write(json.dumps(m,ensure_ascii=False)+"\n")
        print(tag,"disp",round(disp,2),"mm Cmin",round(m['C_min'],6),"mb",f"{m['massbal_rel']:.1e}",
              "bt1",m['bzone_top1'],m['t_s'],"s",flush=True)
if __name__=='__main__':
    run('case0001','case0000',[0,1,2,3,4,6,8,12],axis=1)
