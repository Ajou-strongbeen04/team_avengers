# -*- coding: utf-8 -*-
"""EX3 오차예산 — stageB DO 솔버 래퍼 (native 108x48x48, ILU 재사용)"""
import sys, os, json, time
sys.path.insert(0,"/sessions/youthful-eager-volta/mnt/Claude/03_논문/Experiment/EX3/dataset/stageB_DO")
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla
import solve_do as sd
RES="/sessions/youthful-eager-volta/mnt/Claude/03_논문/Experiment/EX3/dataset/result"
N,NX,NY,NZ,VC=sd.N,sd.NX,sd.NY,sd.NZ,sd.VC
CFG=dict(sd.CONFIG); CFG['plant_mode']='off'
_g={}
def geom():
    if 'o' in _g: return _g
    d=np.load('/tmp/mesh_conn.npz'); o=d['o']; nb=d['nb']; nIF=len(nb); o=o[:nIF]
    cen=sd.cell_centers(); sp_=np.abs(cen[nb]-cen[o]).max(axis=1)
    _g.update(o=o,nb=nb,spacing=sp_,area=VC/sp_,cen=cen,
              ptop=(np.arange(N)//(NX*NY))==(NZ-1))
    return _g
def build(case, phi=None, nut=None):
    g=geom(); cfg=CFG
    U=sd.read_field(f"{case}/200/UMean.gz")
    if nut is None: nut=sd.read_field(f"{case}/200/nutMean.gz")
    if phi is None: phi=sd.read_field(f"{case}/200/phiMean.gz")[:len(g['nb'])]
    Cstar=sd.do_saturation(cfg['T']); kL=cfg['kL20']*cfg['theta_a']**(cfg['T']-20.0)
    a=6*cfg['alpha_g']/cfg['d_b']; kLba=cfg['kLb']*a; R=cfg['R']
    Deff=cfg['D_mol']+nut/cfg['Sc_t']
    o,nb=g['o'],g['nb']
    Df=0.5*(Deff[o]+Deff[nb])*g['area']/g['spacing']
    aPo=Df+np.maximum(phi,0); aPn=Df+np.maximum(-phi,0)
    diag=np.bincount(o,aPo,minlength=N)+np.bincount(nb,aPn,minlength=N)
    rows=np.concatenate([o,nb]); cols=np.concatenate([nb,o]); vals=np.concatenate([-aPn,-aPo])
    b=np.full(N,-R*VC); Atop=sd.DX*sd.DY
    diag[g['ptop']]+=kL*Atop; b[g['ptop']]+=kL*Atop*Cstar
    plume=sd.read_plume_cells(case); diag[plume]+=kLba*VC; b[plume]+=kLba*VC*Cstar
    A=(sp.coo_matrix((vals,(rows,cols)),shape=(N,N))+sp.diags(diag)).tocsr()
    return A,b,U,Cstar,dict(kL=kL,kLba=kLba,R=R,plume=plume,Atop=Atop)
def zonemap(F, nyc=4, nxc=9, weight=None):
    """doc09 규약: (NY,NX) 4x9 구역, z(높이) 전체 평균."""
    V=F.reshape(NZ,NY,NX); by,bx=NY//nyc,NX//nxc
    out=np.zeros((nyc,nxc))
    for a in range(nyc):
        for b in range(nxc):
            out[a,b]=V[:,a*by:(a+1)*by,b*bx:(b+1)*bx].mean()
    return out
def metrics(C,U,Cstar,aux):
    mag=np.linalg.norm(U,axis=1); mc=int(np.argmin(C)); dc=int(np.argmin(mag))
    cen=geom()['cen']
    zm=zonemap(C); flat=np.sort(zm.ravel())
    zmU=zonemap(mag)
    supply=(aux['kL']*aux['Atop']*np.sum(Cstar-C[geom()['ptop']])
            +aux['kLba']*VC*np.sum(Cstar-C[aux['plume']]))
    return dict(C_min=float(C.min()),C_mean=float(C.mean()),C_max=float(C.max()),
        C_p05=float(np.percentile(C,5)),
        min_cell=mc, min_xyz_mm=[float(v*1e3) for v in cen[mc]],
        dead_xyz_mm=[float(v*1e3) for v in cen[dc]],
        min_dead_mm=float(np.linalg.norm(cen[mc]-cen[dc])*1e3),
        zoneDO_min=float(zm.min()), zone_top1=int(zm.argmin()),
        zone_gap12=float(flat[1]-flat[0]), zone_gap13=float(flat[2]-flat[0]),
        zone_span=float(flat[-1]-flat[0]),
        zoneU_top1=int(zmU.argmin()),
        zoneDO=[float(v) for v in zm.ravel()],
        massbal_rel=float((supply-aux['R']*VC*N)/(aux['R']*VC*N)),
        bounded=bool(C.min()>=0 and C.max()<=Cstar+1e-9))
def solve(A,b,Mop,x0=None,tol=1e-9):
    C,info=spla.bicgstab(A,b,rtol=tol,maxiter=2000,M=Mop,x0=x0)
    if info!=0: C,info=spla.lgmres(A,b,rtol=tol,maxiter=2000,M=Mop,x0=x0)
    return C,info
def run(cases, ilu_from=None, out='/tmp/do_out.jsonl', budget=38.0):
    t0=time.time(); g=geom()
    A0,b0,_,_,_=build(f"{RES}/{ilu_from or cases[0]}")
    M=spla.spilu(A0.tocsc(),drop_tol=1e-3,fill_factor=3)
    Mop=spla.LinearOperator((N,N),M.solve); tilu=time.time()-t0
    done=set()
    if os.path.exists(out):
        done={json.loads(l)['case'] for l in open(out)}
    for c in cases:
        if c in done: continue
        if time.time()-t0>budget: print("BUDGET STOP at",c,flush=True); break
        t=time.time(); A,b,U,Cs,aux=build(f"{RES}/{c}")
        C,info=solve(A,b,Mop)
        m=metrics(C,U,Cs,aux); m.update(case=c,info=int(info),t_s=round(time.time()-t,1),tilu=round(tilu,1))
        np.save(f"/tmp/Cf/{c}.npy",C.astype(np.float32))
        with open(out,'a') as f: f.write(json.dumps(m,ensure_ascii=False)+"\n")
        print(c,"Cmin",round(m['C_min'],5),"gap12",round(m['zone_gap12'],5),m['t_s'],"s",flush=True)
if __name__=='__main__':
    run(sys.argv[1:])
