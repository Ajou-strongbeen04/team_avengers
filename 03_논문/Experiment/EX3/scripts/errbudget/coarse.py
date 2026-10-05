# -*- coding: utf-8 -*-
"""EX3 오차예산 — stageB DO 를 보존적 조대격자(2x pooling, 54x24x24)에서 푼다.
면플럭스는 fine 면 합(=정확 보존), Deff 는 체적평균. 108x48x48 native 와 교차검증."""
import sys, os, json, time
sys.path.insert(0,"/sessions/youthful-eager-volta/mnt/Claude/03_논문/Experiment/EX3/dataset/stageB_DO")
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla
import solve_do as sd
RES="/sessions/youthful-eager-volta/mnt/Claude/03_논문/Experiment/EX3/dataset/result"
NX,NY,NZ=sd.NX,sd.NY,sd.NZ; N=sd.N
P=2
NXc,NYc,NZc=NX//P,NY//P,NZ//P; Nc=NXc*NYc*NZc
DXc,DYc,DZc=sd.DX*P,sd.DY*P,sd.DZ*P; VCc=DXc*DYc*DZc
CFG=dict(sd.CONFIG)
_m={}
def facemaps():
    if 'ax' in _m: return _m
    d=np.load('/tmp/mesh_conn.npz'); o=d['o']; nb=d['nb']; nIF=len(nb); o=o[:nIF]
    i=o%NX; j=(o//NX)%NY; k=o//(NX*NY)
    inb=nb%NX; jnb=(nb//NX)%NY; knb=nb//(NX*NY)
    ax=np.where(inb!=i,0,np.where(jnb!=j,1,2))
    _m.update(o=o,nb=nb,i=i,j=j,k=k,ax=ax)
    return _m
def fine_flux_arrays(phi):
    m=facemaps(); i,j,k,ax=m['i'],m['j'],m['k'],m['ax']
    Fx=np.zeros((NX-1,NY,NZ)); Fy=np.zeros((NX,NY-1,NZ)); Fz=np.zeros((NX,NY,NZ-1))
    s=ax==0; Fx[i[s],j[s],k[s]]=phi[s]
    s=ax==1; Fy[i[s],j[s],k[s]]=phi[s]
    s=ax==2; Fz[i[s],j[s],k[s]]=phi[s]
    return Fx,Fy,Fz
def coarsen(case, phi=None, nut=None, occ_shift=None):
    if nut is None: nut=sd.read_field(f"{case}/200/nutMean.gz")
    if phi is None: phi=sd.read_field(f"{case}/200/phiMean.gz")[:len(facemaps()['nb'])]
    Fx,Fy,Fz=fine_flux_arrays(phi)
    # 조대 면플럭스 = fine 면 2x2 합 (경계면 i=2I+1)
    FXc=Fx[1::P,:,:].reshape(NXc-1,NYc,P,NZc,P).sum(axis=(2,4))
    FYc=Fy[:,1::P,:].reshape(NXc,P,NYc-1,NZc,P).sum(axis=(1,4))
    FZc=Fz[:,:,1::P].reshape(NXc,P,NYc,P,NZc-1).sum(axis=(1,3))
    nut3=nut.reshape(NZ,NY,NX).transpose(2,1,0)
    nutc=nut3.reshape(NXc,P,NYc,P,NZc,P).mean(axis=(1,3,5))
    return FXc,FYc,FZc,nutc
def build_coarse(case,**kw):
    FXc,FYc,FZc,nutc=coarsen(case,**kw)
    cfg=CFG; Cstar=sd.do_saturation(cfg['T']); kL=cfg['kL20']*cfg['theta_a']**(cfg['T']-20.0)
    a=6*cfg['alpha_g']/cfg['d_b']; kLba=cfg['kLb']*a; R=cfg['R']
    Deff=cfg['D_mol']+nutc/cfg['Sc_t']            # (NXc,NYc,NZc)
    idx=np.arange(Nc).reshape(NXc,NYc,NZc)        # p = I + NXc*(J + NYc*K) 를 쓰려면 재정렬 필요
    idx=(np.arange(NXc)[:,None,None]+NXc*(np.arange(NYc)[None,:,None]+NYc*np.arange(NZc)[None,None,:]))
    rows=[];cols=[];vals=[];diag=np.zeros(Nc)
    for axis,F,area,spacing in ((0,FXc,DYc*DZc,DXc),(1,FYc,DXc*DZc,DYc),(2,FZc,DXc*DYc,DZc)):
        if axis==0: o=idx[:-1,:,:]; nb=idx[1:,:,:]; Do=Deff[:-1,:,:]; Dn=Deff[1:,:,:]
        elif axis==1: o=idx[:,:-1,:]; nb=idx[:,1:,:]; Do=Deff[:,:-1,:]; Dn=Deff[:,1:,:]
        else: o=idx[:,:,:-1]; nb=idx[:,:,1:]; Do=Deff[:,:,:-1]; Dn=Deff[:,:,1:]
        o=o.ravel(); nb=nb.ravel(); Df=(0.5*(Do+Dn)*area/spacing).ravel(); f=F.ravel()
        aPo=Df+np.maximum(f,0); aPn=Df+np.maximum(-f,0)
        diag+=np.bincount(o,aPo,minlength=Nc)+np.bincount(nb,aPn,minlength=Nc)
        rows.append(o);cols.append(nb);vals.append(-aPn)
        rows.append(nb);cols.append(o);vals.append(-aPo)
    b=np.full(Nc,-R*VCc); Atop=DXc*DYc
    ptop=idx[:,:,NZc-1].ravel()
    diag[ptop]+=kL*Atop; b[ptop]+=kL*Atop*Cstar
    # 플룸: fine plume 셀 수 → 조대셀 체적분율
    pf=sd.read_plume_cells(case)
    pi=pf%NX; pj=(pf//NX)%NY; pk=pf//(NX*NY)
    cnt=np.zeros((NXc,NYc,NZc)); np.add.at(cnt,(pi//P,pj//P,pk//P),1.0)
    frac=(cnt/P**3).ravel()
    diag+=kLba*VCc*frac; b+=kLba*VCc*frac*Cstar
    A=(sp.coo_matrix((np.concatenate(vals),(np.concatenate(rows),np.concatenate(cols))),shape=(Nc,Nc))+sp.diags(diag)).tocsr()
    return A,b,Cstar,dict(kL=kL,kLba=kLba,R=R,Atop=Atop,ptop=ptop,frac=frac)
def solve_coarse(A,b):
    M=spla.spilu(A.tocsc(),drop_tol=1e-4,fill_factor=10)
    Mop=spla.LinearOperator((Nc,Nc),M.solve)
    C,info=spla.bicgstab(A,b,rtol=1e-11,maxiter=3000,M=Mop)
    if info!=0: C,info=spla.lgmres(A,b,rtol=1e-11,maxiter=3000,M=Mop)
    return C,info
def zonemap_c(C,nyc=4,nxc=9):
    V=C.reshape(NXc,NYc,NZc)              # (I,J,K)
    by,bx=NYc//nyc,NXc//nxc
    out=np.zeros((nyc,nxc))
    for a in range(nyc):
        for bq in range(nxc):
            out[a,bq]=V[bq*bx:(bq+1)*bx,a*by:(a+1)*by,:].mean()
    return out
def bottom_zonemap_c(C,nyc=4,nxc=9,ztop=None):
    """저층(하부 1/3) 만 평균 — 최소DO 가 저층에 있음(summary.csv 10/10)"""
    V=C.reshape(NXc,NYc,NZc); kz=NZc//3 if ztop is None else ztop
    by,bx=NYc//nyc,NXc//nxc; out=np.zeros((nyc,nxc))
    for a in range(nyc):
        for bq in range(nxc):
            out[a,bq]=V[bq*bx:(bq+1)*bx,a*by:(a+1)*by,:kz].mean()
    return out
def metrics_c(C,Cstar,aux,extra=None):
    V=C.reshape(NXc,NYc,NZc); mc=np.unravel_index(int(np.argmin(C)),(NXc,NYc,NZc))
    zm=zonemap_c(C); zb=bottom_zonemap_c(C)
    f=np.sort(zm.ravel()); fb=np.sort(zb.ravel())
    supply=aux['kL']*aux['Atop']*np.sum(Cstar-C[aux['ptop']])+aux['kLba']*VCc*np.sum(aux['frac']*(Cstar-C))
    d=dict(C_min=float(C.min()),C_mean=float(C.mean()),C_max=float(C.max()),
      C_p05=float(np.percentile(C,5)),
      min_ijk=[int(v) for v in mc],
      min_xyz_mm=[float((mc[0]+0.5)*DXc*1e3),float((mc[1]+0.5)*DYc*1e3),float((mc[2]+0.5)*DZc*1e3)],
      zoneDO_min=float(zm.min()),zone_top1=int(zm.argmin()),zone_gap12=float(f[1]-f[0]),
      zone_gap13=float(f[2]-f[0]),zone_span=float(f[-1]-f[0]),
      bzoneDO_min=float(zb.min()),bzone_top1=int(zb.argmin()),bzone_gap12=float(fb[1]-fb[0]),
      bzone_gap13=float(fb[2]-fb[0]),bzone_span=float(fb[-1]-fb[0]),
      zoneDO=[float(v) for v in zm.ravel()],bzoneDO=[float(v) for v in zb.ravel()],
      massbal_rel=float((supply-aux['R']*VCc*Nc)/(aux['R']*VCc*Nc)),
      bounded=bool(C.min()>=0 and C.max()<=Cstar+1e-9))
    if extra: d.update(extra)
    return d
def run(cases,out='/tmp/coarse_out.jsonl',budget=38.0,save=True):
    t0=time.time(); done=set()
    if os.path.exists(out): done={json.loads(l)['case'] for l in open(out)}
    for c in cases:
        if c in done: continue
        if time.time()-t0>budget: print("BUDGET STOP at",c,flush=True); break
        t=time.time(); A,b,Cs,aux=build_coarse(f"{RES}/{c}")
        C,info=solve_coarse(A,b)
        m=metrics_c(C,Cs,aux,dict(case=c,info=int(info),t_s=round(time.time()-t,2)))
        if save: np.save(f"/tmp/Cf/{c}_coarse.npy",C.astype(np.float32))
        open(out,'a').write(json.dumps(m,ensure_ascii=False)+"\n")
        print(c,"Cmin",round(m['C_min'],6),"zgap12",f"{m['zone_gap12']:.2e}","bgap12",f"{m['bzone_gap12']:.2e}",
              "mb",f"{m['massbal_rel']:.1e}",m['t_s'],"s",flush=True)
if __name__=='__main__': run(sys.argv[1:])
