"""§4.6 레짐 지도 — 측정된 칸 하나와 예상되는 칸들.
   측정: 03_논문 §3.10 표 3-11 (off/night/day).  나머지는 소스 배치로부터의 구조적 예상(미검증)."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams.update({"font.family":"Noto Sans CJK JP","axes.unicode_minus":False,
                     "font.size":10.5})
FG="#222222"
fig,ax=plt.subplots(figsize=(10.2,4.6))
ax.set_xlim(-1.05,1.05); ax.set_ylim(-0.6,3.2); ax.axis("off")

# 축
ax.annotate("", xy=(1.02,0), xytext=(-1.02,0),
            arrowprops=dict(arrowstyle="<|-|>", lw=1.2, color=FG))
for v,l in [(-1,"−1.0"),(-0.5,"−0.5"),(0,"0"),(0.5,"+0.5"),(1,"+1.0")]:
    ax.plot([v,v],[-0.06,0.06],color=FG,lw=1)
    ax.text(v,-0.20,l,ha="center",fontsize=9.5,color=FG)
ax.text(0,-0.46,r"$\rho_{UC}=\mathrm{corr}(|\mathbf{U}|,\,C_i)$",
        ha="center",fontsize=11.5,color=FG)

# 레짐 밴드
ax.add_patch(FancyBboxPatch((0.60,0.12),0.42,0.30,boxstyle="round,pad=0.02",
                            fc="#dbe7f3",ec="none"))
ax.text(0.81,0.27,"유동지배",ha="center",va="center",fontsize=10,fontweight="bold")
ax.add_patch(FancyBboxPatch((-1.02,0.12),1.22,0.30,boxstyle="round,pad=0.02",
                            fc="#f2ded9",ec="none"))
ax.text(-0.41,0.27,"소스지배",ha="center",va="center",fontsize=10,fontweight="bold")
ax.text(0.40,0.27,"전이대",ha="center",va="center",fontsize=9.5,color="#666666")

# 측정된 점 (같은 항목 DO, 소스 배치만 변경)
meas=[(0.71,"균일 소비\n$A$ = 1.5 %"),(0.48,"국소 싱크\n$A\\approx3$ %"),
      (-0.11,"국소 소스\n$A\\approx6$ %")]
for x,lab in meas:
    ax.plot(x,1.15,"o",ms=11,color="#1f4e79",mec="black",mew=.7,zorder=3)
    ax.plot([x,x],[0.45,1.05],color="#1f4e79",lw=1,ls=":")
    ax.text(x,1.34,lab,ha="center",va="bottom",fontsize=9.2,linespacing=1.5)
ax.text(-1.0,1.15,"측정\n(DO, 소스 배치만 변경)",ha="left",va="center",
        fontsize=9.4,fontweight="bold",color="#1f4e79",linespacing=1.5)
ax.annotate("",xy=(-0.02,1.15),xytext=(0.66,1.15),
            arrowprops=dict(arrowstyle="-|>",lw=1.4,color="#1f4e79"))
ax.text(0.32,1.03,"소스가 국소화될수록",ha="center",fontsize=8.8,
        color="#1f4e79",style="italic")

# 예상 (항목 축)
pred=[(0.71,"DO"),(0.15,"$\\mathrm{CO_2}$"),(-0.30,"pH"),
      (-0.55,"TAN · $\\mathrm{NO_2^-}$"),(-0.80,"입자 · 약품")]
for x,lab in pred:
    mk = "o" if lab=="DO" else "^"
    col = "#1f4e79" if lab=="DO" else "#999999"
    ax.plot(x,2.35,mk,ms=10,color=col,mec="black",mew=.6,
            mfc=col if lab=="DO" else "white",zorder=3)
    ax.text(x,2.54,lab,ha="center",va="bottom",fontsize=9.4)
ax.text(-1.0,2.35,"항목 축\n(예상 · 미검증)",ha="left",va="center",
        fontsize=9.4,fontweight="bold",color="#666666",linespacing=1.5)
ax.text(0.71,2.14,"측정된 유일한 칸",ha="center",fontsize=8.6,
        color="#1f4e79",style="italic")

ax.plot([-1.02,1.02],[1.85,1.85],color="#cccccc",lw=.9,ls="--")
fig.tight_layout(pad=0.4)
fig.savefig("fig17_regime_map.png",dpi=320,bbox_inches="tight",facecolor="white")
print("ok")
