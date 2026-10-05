"""그림 4 — 실측 앵커. 실험 폭기축 (0.035, 0.195) · medium 108x48x48 단일격자.
   출처: 03_논문/Experiment/EX2/CFD/kla_cfd.csv (2026-08-03)"""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family":"Noto Sans CJK JP","axes.unicode_minus":False,
                     "font.size":10.5,"axes.grid":True,"grid.alpha":.3})
TH=1.024
runs=[("S1",0.020,24.19,2.4540,2.4743,"train"),
      ("S2",0.020,23.87,2.3730,2.4710,"position"),
      ("S3",0.020,23.89,2.4320,2.4712,"position"),
      ("S4",0.080,23.84,2.0230,1.9615,"train"),
      ("S5",0.170,23.95,1.0440,1.0138,"holdout")]
c20=lambda v,T: v*TH**(20.0-T)
STY={"train":("o","#1f4e79","train"),"position":("s","#2e7d32","프로브 위치 반복"),
     "holdout":("D","#b03a2e","hold-out")}
fig,ax=plt.subplots(1,2,figsize=(11.0,4.3))

zs=sorted({r[1] for r in runs})
cfd=[c20([r for r in runs if r[1]==z][0][4],[r for r in runs if r[1]==z][0][2]) for z in zs]
ax[0].plot(zs,cfd,"^-",color="#888888",lw=1.6,ms=7,mfc="white",
           label="CFD ($\\alpha_g$ 자기일관, 20 °C 환산)")
seen=set()
for n,z,T,m,c,k in runs:
    mk,col,lab=STY[k]
    ax[0].plot(z,c20(m,T),mk,color=col,ms=8,mec="black",mew=.6,
               label=lab if k not in seen else None); seen.add(k)
    ax[0].annotate(n,(z,c20(m,T)),textcoords="offset points",xytext=(7,5),fontsize=9)
ax[0].set_xlabel("에어스톤 침지 높이 $z_\\mathrm{start}$ [m]")
ax[0].set_ylabel("$K_La^{20}$ [1/h]")
ax[0].set_title("(a) 침지 높이 레버 — 실측 vs CFD",fontsize=10.5,pad=7)
ax[0].legend(fontsize=8.6,loc="upper right")

seen=set()
for n,z,T,m,c,k in runs:
    mk,col,lab=STY[k]
    ax[1].plot(z,m/c,mk,color=col,ms=8,mec="black",mew=.6,
               label=lab if k not in seen else None); seen.add(k)
    ax[1].annotate(n,(z,m/c),textcoords="offset points",xytext=(7,5),fontsize=9)
ax[1].axhline(1.0,color="black",ls="--",lw=1.1)
ax[1].axhspan(0.95,1.05,color="#2e7d32",alpha=.08)
ax[1].set_ylim(0.90,1.10)
ax[1].set_xlabel("$z_\\mathrm{start}$ [m]")
ax[1].set_ylabel("$\\kappa = K_La^\\mathrm{meas}/K_La^\\mathrm{CFD}$")
ax[1].set_title("(b) 물리 엔진과 현실의 이격",fontsize=10.5,pad=7)
ax[1].text(0.085,1.075,"$z_\\mathrm{start}$=0.02 : $\\kappa$ = 0.978 ± 0.016 ($n$=3)",
           fontsize=9.4,ha="center")
ax[1].text(0.16,0.925,"±5 % 밴드",fontsize=9,color="#2e7d32",ha="right")
for a in ax:
    for s in ("top","right"): a.spines[s].set_visible(False)
fig.tight_layout(pad=0.7)
fig.savefig("fig05_EX2_KLa_vs_zstart.png",dpi=320,bbox_inches="tight",facecolor="white")
print("ok  kappa:", [round(m/c,4) for _,_,_,m,c,_ in runs])
