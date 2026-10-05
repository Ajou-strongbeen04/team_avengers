"""§3.9 전달 총량의 로버스트성 — 수위 · 폭기 침지 · Sc_t 밴드
   출처: 03_논문/Experiment/야간작업_20260805/night_결과.md (2026-08-07)"""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": "Noto Sans CJK JP", "axes.unicode_minus": False,
                     "font.size": 10.5, "axes.grid": True, "grid.alpha": .3})
FG = "#222222"
fig, ax = plt.subplots(1, 3, figsize=(11.4, 3.5))

# (a) 수위
d   = [0.21, 0.18, 0.15, 0.12, 0.09]
kla = [2.4712, 2.6139, 2.7633, 3.0234, 3.3776]
est = [2.4712*x for x in (1.00, 0.84, 0.70, 0.59, 0.53)]
ax[0].plot(d, kla, "o-", color="#1f4e79", lw=1.8, ms=5.5, label="CFD (본 연구)")
ax[0].plot(d, est, "s--", color="#999999", lw=1.4, ms=4.5, label="해석추정")
ax[0].invert_xaxis()
ax[0].set_xlabel("수위 $d$ [m]"); ax[0].set_ylabel("$K_La$ [1/h]")
ax[0].set_title("(a) 수위 — 부호가 반대다", fontsize=10.5, pad=7)
ax[0].legend(fontsize=8.6, loc="upper left")
ax[0].annotate("+36.7 %", xy=(0.09, 3.3776), xytext=(0.115, 3.30),
               fontsize=9, color="#1f4e79", fontweight="bold")

# (b) 폭기 침지 높이 (동일 coarse 격자)
z    = [0.01, 0.02, 0.03, 0.04, 0.06]
klaz = [2.6748, 2.5546, 2.5085, 2.3945, 2.1047]
ax[1].plot([x*100 for x in z], klaz, "o-", color="#7b3294", lw=1.8, ms=5.5)
ax[1].set_xlabel("에어스톤 침지 높이 $z_\\mathrm{start}$ [cm]")
ax[1].set_ylabel("$K_La$ [1/h]")
ax[1].set_title("(b) 침지 높이 — 매끈한 단조 레버", fontsize=10.5, pad=7)
ax[1].annotate("−17.6 %", xy=(6, 2.1047), xytext=(4.0, 2.16),
               fontsize=9, color="#7b3294", fontweight="bold")

# (c) Sc_t 밴드
sct  = [0.7, 0.85, 1.0]
klas = [2.4712, 2.4571, 2.4450]
ax[2].plot(sct, klas, "o-", color="#008837", lw=1.8, ms=5.5)
ax[2].set_ylim(2.20, 2.72)
ax[2].set_xlabel("난류 Schmidt 수 $Sc_t$"); ax[2].set_ylabel("$K_La$ [1/h]")
ax[2].set_title("(c) $Sc_t$ 밴드 — 총량도 공간도 둔감", fontsize=10.5, pad=7)
ax[2].text(0.72, 2.27, "밴드 전체에서\n$K_La$ −1.1 %\n장 최대차 0.0047 mg/L",
           fontsize=8.8, color=FG, linespacing=1.55)

for a in ax:
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
fig.tight_layout(pad=0.6)
fig.savefig("fig16_transport_robustness.png", dpi=320, bbox_inches="tight",
            facecolor="white")
print("ok")
