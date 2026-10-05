import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams["font.family"] = "Noto Sans CJK JP"
plt.rcParams["axes.unicode_minus"] = False

FG, ON, OFF, VER = "#222222", "#dbe7f3", "#e9e4d8", "#e6ecdf"
fig, ax = plt.subplots(figsize=(9.6, 5.0))
ax.set_xlim(0, 100); ax.set_ylim(0, 56); ax.axis("off")

def box(x, y, w, h, t, fc, fs=9.4, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.2",
                                fc=fc, ec=FG, lw=1.0))
    ax.text(x+w/2, y+h/2, t, ha="center", va="center", fontsize=fs, color=FG,
            linespacing=1.5, fontweight="bold" if bold else "normal")

def arr(x1, y1, x2, y2, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, ls=ls,
                                 mutation_scale=11, lw=1.0, color=FG,
                                 shrinkA=0, shrinkB=0))

# --- 온라인 (기기) ---
ax.text(2, 52.6, "온라인 — 사용자 기기", fontsize=9.6, fontweight="bold", color=FG)
box( 2, 40, 15, 9, "사진\n(정면 1장)", ON)
box(21, 40, 17, 9, "① 기하·위상 인식\n(VLM · 제약 디코딩)", ON)
box(42, 40, 17, 9, "② 정규화 경계조건\n(JSON · 좌표 어댑터)", ON)
box(63, 40, 16, 9, "④ $C=C^*(T)-R\\chi$", ON)
box(83, 40, 15, 9, "⑤ 최저 농도\n3단 배지\n폭기 부족/충분", ON, bold=True)
for a, b in ((17,21),(38,42),(59,63),(79,83)):
    arr(a, 44.5, b, 44.5)

# --- 프록시 입력 ---
box(63, 29.5, 16, 6.5, "수온 $T$ · 사육부하 $R$", ON, fs=9.0)
arr(71, 36, 71, 40)

# --- 오프라인 (A층) ---
ax.text(2, 22.6, "오프라인 — 사전 계산", fontsize=9.6, fontweight="bold", color=FG)
box( 2, 10, 18, 9, "CFD 스윕\n108×48×48 · 315 케이스", OFF)
box(24, 10, 18, 9, "③ A층 회귀\nPCA 6 + RidgeCV", OFF)
box(46, 10, 18, 9, "응답장 $\\chi(\\mathbf{x})$\n8×8×12", OFF, bold=True)
arr(20, 14.5, 24, 14.5); arr(42, 14.5, 46, 14.5)
arr(64, 14.5, 69, 14.5); arr(69, 14.5, 69, 29.5)
ax.text(67.4, 22.5, "동결 후 탑재\n(행렬-벡터 곱 1회)", fontsize=8.4, color=FG,
        va="center", ha="right", linespacing=1.5)

# --- 검증 경로 ---
box(2, 0.5, 62, 6.5,
    "검증 · 캘리브레이션   격자수렴(GCI)  ·  정성 유동검증  ·  "
    "비정상 재폭기 시험 → $\\kappa=K_La_\\mathrm{meas}/K_La_\\mathrm{CFD}$", VER, fs=9.0)
arr(33, 10, 33, 7, ls=(0,(3,2)))

ax.add_patch(FancyBboxPatch((67, 0.5), 31, 6.5,
                            boxstyle="round,pad=0.5,rounding_size=1.2",
                            fc="none", ec=FG, lw=0.9, ls=(0,(4,2.5))))
ax.text(82.5, 3.75, "유동장은 여기서 끝난다 — 기기에 실리지 않는다",
        fontsize=8.8, color=FG, ha="center", va="center", style="italic")

fig.tight_layout(pad=0.4)
fig.savefig("fig00_pipeline.png", dpi=320, bbox_inches="tight", facecolor="white")
print("ok")
