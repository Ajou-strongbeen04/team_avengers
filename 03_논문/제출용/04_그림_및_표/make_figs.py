# -*- coding: utf-8 -*-
"""
논문_최종.md §3 본문 그림 5종 생성.
  Fig1  Pe_t vs L            (EX1 크기 스윕)          -> §3.1
  Fig4  5런 재폭기 곡선       (EX2 실측)              -> §3.4
  Fig5  K_La vs z_start      (실측 vs CFD, kappa)     -> §3.4
  Fig9  학습곡선             (조대 과제 vs 장 과제)    -> §3.6
  Fig15 DO 장 단면           (off vs night)          -> §3.8
출력: 이 스크립트와 같은 폴더의 fig01_*.png ... fig15_*.png (300 dpi)
"""
import os, json, csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))       # 03_논문/
EXP  = os.path.join(ROOT, "Experiment")
OUT  = HERE

plt.rcParams.update({
    "font.family": ["Noto Sans CJK JP", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
    "savefig.dpi": 300,
    "figure.dpi": 120,
})

def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("WROTE", os.path.basename(p))


# ─────────────────────────────────────────────────────────────
# Fig 1 — Pe_t vs L : 자기유사 레짐의 하한  (§3.1, EX1)
#   출처: Experiment/EX1/EX1_결과.md (1차 스윕 / 2차 세분)
#   results.csv 의 1차 5행에는 Re·Pe_t 열이 없어 EX1_결과.md 표를 정본으로 씀
# ─────────────────────────────────────────────────────────────
def fig1():
    # 1차 스윕 (L=0.2~1.0)
    L1  = [0.20, 0.40, 0.60, 0.80, 1.00]
    V1  = [2, 16, 54, 128, 250]
    Pe1 = [67.0, 50.9, 49.9, 48.8, 48.8]
    # 2차 세분 (0.2~0.4, 고해상)
    L2  = [0.20, 0.25, 0.30, 0.35, 0.40]
    V2  = [2, 4, 7, 11, 16]
    Pe2 = [67.0, 60.4, 55.0, 53.2, 50.9]
    dPe = [None, -6.6, -5.4, -1.8, -2.3]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.3),
                                  gridspec_kw={"width_ratios": [1.35, 1]})

    ax.axvspan(0.35, 1.02, color="#2e7d32", alpha=0.07, zorder=0)
    ax.axhspan(48.8, 53.2, color="#2e7d32", alpha=0.10, zorder=0)
    ax.plot(L1, Pe1, "o-", color="#1f4e79", lw=1.8, ms=7,
            label="1차 스윕 (L = 0.2–1.0 m)")
    ax.plot(L2, Pe2, "s--", color="#c0504d", lw=1.6, ms=6, mfc="white",
            label="2차 세분 (L = 0.2–0.4 m, 고해상)")
    ax.axvline(0.35, color="k", ls=":", lw=1.2)
    ax.annotate("자기유사 하한\n$L \\approx 0.35$ m (11 L)",
                xy=(0.35, 53.2), xytext=(0.47, 60.5), fontsize=9.5,
                arrowprops=dict(arrowstyle="->", lw=1.1, color="k"))
    ax.text(0.70, 50.6, "$Pe_t$ = 48.8–53 평탄 수렴", fontsize=9,
            color="#2e7d32", ha="center")
    ax.set_xlabel("수조 장변 $L$ [m]   ($L{:}B{:}d = 2{:}1{:}1$ 고정)")
    ax.set_ylabel("난류 Péclet 수  $Pe_t = U_0 L_c / D_\\mathrm{eff}$")
    ax.set_title("(a) 크기 스윕 — 레짐 경계", fontsize=11)
    ax.set_xlim(0.165, 1.06); ax.set_ylim(45, 70)
    ax.legend(fontsize=9, loc="upper right")

    for L, V in zip(L1, V1):
        ax.annotate(f"{V} L", xy=(L, dict(zip(L1, Pe1))[L]),
                    xytext=(0, -14), textcoords="offset points",
                    fontsize=7.5, ha="center", color="#1f4e79")

    # (b) 구간별 ΔPe_t — 무릎의 위치를 직접 보임
    xs = np.arange(1, 5)
    ax2.bar(xs, [-d for d in dPe[1:]], color=["#c0504d", "#c0504d", "#2e7d32", "#2e7d32"],
            width=0.62, alpha=0.85)
    ax2.set_xticks(xs)
    ax2.set_xticklabels(["0.20→0.25", "0.25→0.30", "0.30→0.35", "0.35→0.40"],
                        fontsize=8.5, rotation=12)
    for x, d in zip(xs, dPe[1:]):
        ax2.text(x, -d + 0.18, f"{-d:.1f}", ha="center", fontsize=9.5)
    ax2.set_ylabel("$|\\Delta Pe_t|$  (구간별 감소량)")
    ax2.set_title("(b) 무릎 = 급락에서 완만으로", fontsize=11)
    ax2.set_ylim(0, 7.6)
    ax2.text(3.5, 5.6, "완만 구간\n(자기유사)", fontsize=9, ha="center", color="#2e7d32")
    ax2.text(1.5, 5.6, "급락 구간", fontsize=9, ha="center", color="#c0504d")

    fig.suptitle("그림 1. 자기유사 레짐의 하한 — 기준 기하 47 × 21 × 21 cm 의 근거 (EX1)",
                 fontsize=12, y=1.02)
    save(fig, "fig01_EX1_Pet_vs_L.png")


# ─────────────────────────────────────────────────────────────
# 공통 — EX2 런 CSV 로더 (주석 2줄 skip)
# ─────────────────────────────────────────────────────────────
def load_run(path):
    with open(path, encoding="utf-8-sig") as f:
        lines = f.readlines()
    hdr = next(i for i, l in enumerate(lines) if l.startswith("iso_time"))
    rows = list(csv.DictReader(lines[hdr:]))
    t  = np.array([float(r["t_sec"])  for r in rows])
    do = np.array([float(r["do_mgL"]) for r in rows])
    tc = np.array([float(r["temp_C"]) for r in rows])
    return t, do, tc


def load_events(path):
    ev = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ev[r["label"]] = float(r["t_sec"])
    return ev


def read_dicts(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ─────────────────────────────────────────────────────────────
# Fig 4 — 5런 재폭기 곡선 (§3.4, EX2 실측)
# ─────────────────────────────────────────────────────────────
def fig4():
    d = os.path.join(EXP, "EX2", "어항실험")
    runs  = read_dicts(os.path.join(d, "runs.csv"))
    meas  = {r["file"]: r for r in read_dicts(os.path.join(d, "summary_meas.csv"))}
    kap   = {r["run"]: r for r in read_dicts(os.path.join(d, "kappa_결과.csv"))}
    colors = {"S1": "#1f4e79", "S2": "#2e7d32", "S3": "#7b5aa6",
              "S4": "#e07b39", "S5": "#c0504d"}

    fig, (ax, axr) = plt.subplots(1, 2, figsize=(12.0, 4.6),
                                  gridspec_kw={"width_ratios": [1.55, 1]})

    for r in runs:
        run = r["run"]
        t, do, _ = load_run(os.path.join(d, r["file"]))
        m  = meas[r["file"]]
        t0 = float(m["t0_s"])                       # rise_start
        cs = float(m["cstar_mgL"])
        tm = (t - t0) / 60.0
        sel = tm >= -6.0
        ax.plot(tm[sel], do[sel], lw=1.3, color=colors[run],
                label=f"{run}  $z_\\mathrm{{start}}$={float(r['z_start']):.2f} m  "
                      f"($K_La^{{20}}$={float(kap[run]['kla_meas_1_h']):.2f} /h)")
        ax.axhline(cs, color=colors[run], lw=0.6, ls=":", alpha=0.55)

    ax.axvline(0, color="k", lw=1.0, ls="--")
    ax.text(0.8, 4.6, "폭기 개시 ($t_0$)", fontsize=9, rotation=90, va="center")
    ax.annotate("", xy=(0, -0.28), xytext=(17.5, -0.28),
                arrowprops=dict(arrowstyle="<->", lw=1.0, color="#555"))
    ax.annotate("잔류 아황산 소모 지연 (S2·S4·S5)",
                xy=(8.8, -0.28), xytext=(34, 1.25), fontsize=8.4, color="#555",
                arrowprops=dict(arrowstyle="->", lw=0.9, color="#555"))
    ax.set_xlabel("폭기 개시 후 경과시간 $t - t_0$ [min]")
    ax.set_ylabel("용존산소 [mg/L]")
    ax.set_title("(a) 비정상 재폭기 곡선 — 5런", fontsize=11)
    ax.set_xlim(-6, 175); ax.set_ylim(-0.4, 9.2)
    ax.legend(fontsize=8.2, loc="lower right", framealpha=0.92)
    ax.text(120, 8.78, "점선 = 런별 $C^{*}$ (피팅)", fontsize=8, color="#555", ha="center")

    # (b) 1차 지연 선형화 — 유효창 frac 0.15–0.92 (fit_kla.py 규약) 에서만
    LO, HI = 0.15, 0.92
    for r in runs:
        run = r["run"]
        t, do, _ = load_run(os.path.join(d, r["file"]))
        m  = meas[r["file"]]
        t0, cs = float(m["t0_s"]), float(m["cstar_mgL"])
        post = t >= t0
        t, do = t[post], do[post]
        cmin = do.min()
        frac = (do - cmin) / (cs - cmin)
        sel = (frac >= LO) & (frac <= HI)
        tt = (t[sel] - t[sel][0]) / 60.0
        y  = np.log((cs - do[sel]) / (cs - do[sel][0]))
        axr.plot(tt, y, lw=1.4, color=colors[run],
                 label=f"{run}  ({-np.polyfit(tt, y, 1)[0]*60:.2f} /h)")
    axr.set_xlabel("유효창 시작 후 경과시간 [min]")
    axr.set_ylabel("$\\ln\\left[(C^{*}-C)/(C^{*}-C_0)\\right]$")
    axr.set_title("(b) 1차 지연 선형화 — 기울기 = $-K_La$", fontsize=11)
    axr.legend(fontsize=8.2, ncol=1, loc="lower left")
    axr.text(0.97, 0.94, "유효창 frac 0.15–0.92 · 현장 온도 기준 $K_La$\n"
                         "RMSE 0.016–0.046 mg/L",
             transform=axr.transAxes, ha="right", va="top",
             fontsize=8.3, color="#555")

    fig.suptitle("그림 4. 비정상 재폭기 시험 — 실측 앵커 (EX2, 5런 · 총 42,061점 · 1 s 샘플)",
                 fontsize=12, y=1.02)
    save(fig, "fig04_EX2_reaeration_curves.png")


# ─────────────────────────────────────────────────────────────
# Fig 5 — K_La vs z_start : 실측 vs CFD, kappa (§3.4)
# ─────────────────────────────────────────────────────────────
THETA = 1.024
def kla20(k, T):                     # 20 degC 환산
    return k * THETA ** (20.0 - T)

def fig5():
    d = os.path.join(EXP, "EX2", "어항실험")
    kap = read_dicts(os.path.join(d, "kappa_결과.csv"))
    cfd = read_dicts(os.path.join(d, "cfd_fixed.csv"))

    zc  = np.array([float(r["z_start"])       for r in cfd])
    kc25 = np.array([float(r["kla_cfd_1_h"])  for r in cfd])
    kc20 = kla20(kc25, 25.0)                 # CFD 기준온도 25 degC

    zm  = np.array([float(r["z_start"])       for r in kap])
    km  = np.array([float(r["kla_meas_1_h"])  for r in kap])   # 이미 20 degC 환산
    kk  = np.array([float(r["kappa"])         for r in kap])
    rl  = [r["role"] for r in kap]
    rn  = [r["run"]  for r in kap]

    role_style = {"train":    dict(marker="o", color="#1f4e79", label="train"),
                  "position": dict(marker="s", color="#2e7d32", label="position 반복"),
                  "holdout":  dict(marker="D", color="#c0504d", label="hold-out")}

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.4, 4.4))

    ax.plot(zc, kc20, "^-", color="#888", lw=1.6, ms=7, mfc="white",
            label="CFD ($\\alpha_g$ 자기일관, 20 °C 환산)", zorder=2)
    # 같은 z_start 에 3런(S1·S2·S3)이 겹치므로 표시용 x 미세이격
    jit = {"S1": -0.005, "S2": 0.0, "S3": 0.005, "S4": 0.0, "S5": 0.0}
    lbl = {"S1": (0, 9), "S2": (0, -16), "S3": (6, 2), "S4": (7, 3), "S5": (7, 3)}
    seen = set()
    for z, k, r, n in zip(zm, km, rl, rn):
        st = dict(role_style[r])
        lab = st.pop("label")
        ax.plot(z + jit[n], k, ls="none", ms=9, mec="k", mew=0.7, zorder=3,
                label=(lab if lab not in seen else None), **st)
        seen.add(lab)
        ax.annotate(n, xy=(z + jit[n], k), xytext=lbl[n],
                    textcoords="offset points", fontsize=8.5, ha="center")
    ax.text(0.02, 2.62, "$z_\\mathrm{start}$ = 0.02 m 3런\n(표시용 x 미세이격)",
            fontsize=7.6, color="#555", ha="center")
    ax.set_xlabel("에어스톤 침지 높이 $z_\\mathrm{start}$ [m]")
    ax.set_ylabel("$K_La^{20}$ [1/h]")
    ax.set_title("(a) 침지 높이 레버 — 실측 vs CFD", fontsize=11)
    ax.set_xlim(0.0, 0.19); ax.set_ylim(0.7, 2.8)
    ax.legend(fontsize=8.8, loc="upper right")

    # (b) kappa
    for z, k, r, n in zip(zm, kk, rl, rn):
        st = dict(role_style[r]); st.pop("label")
        ax2.plot(z + jit[n], k, ls="none", ms=10, mec="k", mew=0.7, zorder=3, **st)
        ax2.annotate(n, xy=(z + jit[n], k), xytext=lbl[n],
                     textcoords="offset points", fontsize=8.5, ha="center")
    ax2.axhline(1.0, color="k", lw=1.1, ls="--")
    ax2.axhspan(0.9, 1.1, color="#2e7d32", alpha=0.10)
    ax2.set_xlabel("$z_\\mathrm{start}$ [m]")
    ax2.set_ylabel("$\\kappa = K_La^\\mathrm{meas} / K_La^\\mathrm{CFD}$")
    ax2.set_title("(b) 물리 엔진과 현실의 이격", fontsize=11)
    ax2.set_xlim(0.0, 0.19); ax2.set_ylim(0.80, 1.20)
    ax2.text(0.095, 1.145, f"$\\kappa$ = {kk.min():.3f} – {kk.max():.3f}",
             fontsize=10, ha="center")
    ax2.text(0.095, 0.845, "±10 % 밴드", fontsize=8.5, ha="center", color="#2e7d32")

    fig.suptitle("그림 5. 실측 앵커 — 침지 높이 $z_\\mathrm{start}$ 0.02–0.17 m 에 걸친 $K_La$ 대조 (EX2)",
                 fontsize=12, y=1.02)
    save(fig, "fig05_EX2_KLa_vs_zstart.png")


# ─────────────────────────────────────────────────────────────
# Fig 9 — 학습곡선 : 조대 과제 포화 vs 장 과제 지속 개선 (§3.6)
#   조대: Experiment/EX3/09_검증_조대위험맵_중첩.md
#   장  : dataset/training_dataset/rom_pod_results_lc.json (원본)
# ─────────────────────────────────────────────────────────────
def fig9():
    N_c   = [30, 60, 120, 180, 202]
    t49   = [0.486, 0.692, 0.684, 0.668, 0.672]
    N_c2  = [30, 60, 120, 180]
    t618  = [0.272, 0.423, 0.446, 0.446]

    lc = json.load(open(os.path.join(
        EXP, "EX3", "dataset", "training_dataset", "rom_pod_results_lc.json"),
        encoding="utf-8"))
    Nf   = [d["N"] for d in lc]
    anom = [d["anomL2_med"] for d in lc]
    cd   = [d["cdist_mm_med"] for d in lc]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.4, 4.4))

    ax.plot(N_c, t49, "o-", color="#1f4e79", lw=2.0, ms=8, label="4×9 (36구역, 작동점)")
    ax.plot(N_c2, t618, "s--", color="#7b5aa6", lw=1.6, ms=7, mfc="white",
            label="6×18 (108구역)")
    ax.axvline(60, color="k", ls=":", lw=1.2)
    ax.annotate("$N$ = 60 이후 평탄\n0.692 → 0.672",
                xy=(120, 0.684), xytext=(112, 0.545), fontsize=9.5,
                arrowprops=dict(arrowstyle="->", lw=1.1))
    ax.set_xlabel("학습 케이스 수 $N_\\mathrm{train}$")
    ax.set_ylabel("RF top1 적중률")
    ax.set_title("(a) 조대 위험맵 과제 — 포화", fontsize=11)
    ax.set_ylim(0.20, 0.80); ax.set_xlim(15, 215)
    ax.legend(fontsize=9, loc="lower right")

    ax2.plot(Nf, anom, "o-", color="#c0504d", lw=2.0, ms=8, label="anomL2 median")
    ax2.set_xlabel("학습 케이스 수 $N_\\mathrm{train}$")
    ax2.set_ylabel("anomL2 median  (작을수록 좋음)", color="#c0504d")
    ax2.tick_params(axis="y", labelcolor="#c0504d")
    ax2.set_title("(b) 장(場) 과제 — 지속 개선", fontsize=11)
    ax2.set_xlim(15, 260); ax2.set_ylim(0.58, 0.90)
    ax2.annotate("계속 내려간다\n0.848 → 0.636",
                 xy=(243, 0.636), xytext=(120, 0.70), fontsize=9.5,
                 arrowprops=dict(arrowstyle="->", lw=1.1))

    ax3 = ax2.twinx()
    ax3.plot(Nf, cd, "^--", color="#888", lw=1.4, ms=7, mfc="white",
             label="cdist median [mm]")
    ax3.set_ylabel("정체역 centroid 거리 [mm]", color="#888")
    ax3.tick_params(axis="y", labelcolor="#888")
    ax3.grid(False); ax3.set_ylim(5, 14)
    h1, l1 = ax2.get_legend_handles_labels(); h2, l2 = ax3.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, fontsize=9, loc="upper right")

    fig.suptitle("그림 9. 학습곡선 — 「253 케이스 부족」 진단은 장 과제에만 해당한다 (EX3, 동일 5-fold CV)",
                 fontsize=12, y=1.02)
    save(fig, "fig09_EX3_learning_curve.png")


# ─────────────────────────────────────────────────────────────
# Fig 15 — DO 장 단면 : off vs night (§3.8)
# ─────────────────────────────────────────────────────────────
LX, LY, LZ = 0.47, 0.21, 0.21
def fig15():
    d = os.path.join(EXP, "EX3", "dataset", "stageB_DO")
    files = [("_viz_case0231_off.npz",   "off — 균일 소비",        "유동지배"),
             ("_viz_case0086_night.npz", "night — 식물 국소 싱크", "전이대")]

    fig, axes = plt.subplots(2, 3, figsize=(15.0, 7.2))
    for row, (fn, title, regime) in enumerate(files):
        z = np.load(os.path.join(d, fn))
        C, mag, obst, plume = z["C"], z["mag"], z["obst"], z["plume"]
        NZ, NY, NX = C.shape
        xs = (np.arange(NX) + 0.5) * LX / NX
        ys = (np.arange(NY) + 0.5) * LY / NY
        zs = (np.arange(NZ) + 0.5) * LZ / NZ

        Cf = C.copy(); Cf[obst] = 1e9
        k0, j0, i0 = np.unravel_index(np.argmin(Cf), C.shape)
        fluid = ~obst
        rho = np.corrcoef(mag[fluid].ravel(), C[fluid].ravel())[0, 1]
        vmin, vmax = C[fluid].min(), C[fluid].max()
        spread = float(z["spread"])

        pj, pi = np.where(plume.any(0))
        px, py = xs[pi].mean(), ys[pj].mean()

        # (A) 수평 단면 @ 최저 DO 층
        a = axes[row, 0]
        im = a.pcolormesh(xs, ys, np.ma.masked_where(obst[k0], C[k0]),
                          cmap="RdYlBu", vmin=vmin, vmax=vmax, shading="auto")
        a.contourf(xs, ys, obst[k0].astype(float), levels=[0.5, 1.5], colors="#444")
        a.plot(px, py, "^", ms=11, mfc="cyan", mec="k")
        a.plot(xs[i0], ys[j0], "*", ms=18, mfc="yellow", mec="k")
        a.set_aspect("equal"); a.set_xlabel("x [m]"); a.set_ylabel("y [m]")
        a.set_title(f"({'AD'[row]}1) 수평 단면  z = {zs[k0]*100:.1f} cm", fontsize=10)
        fig.colorbar(im, ax=a, label="DO [mg/L]", fraction=0.033)

        # (B) 연직 단면
        b = axes[row, 1]
        im2 = b.pcolormesh(xs, zs, np.ma.masked_where(obst[:, j0, :], C[:, j0, :]),
                           cmap="RdYlBu", vmin=vmin, vmax=vmax, shading="auto")
        b.contourf(xs, zs, obst[:, j0, :].astype(float), levels=[0.5, 1.5], colors="#444")
        pk, pi2 = np.where(plume[:, j0, :])
        if len(pi2):
            b.plot(xs[pi2].mean(), zs[pk].mean(), "^", ms=11, mfc="cyan", mec="k")
        b.plot(xs[i0], zs[k0], "*", ms=18, mfc="yellow", mec="k")
        b.set_aspect("equal"); b.set_xlabel("x [m]"); b.set_ylabel("z [m]  (0 = 바닥)")
        b.set_title(f"({'AD'[row]}2) 연직 단면  y = {ys[j0]*100:.1f} cm", fontsize=10)
        fig.colorbar(im2, ax=b, label="DO [mg/L]", fraction=0.033)

        # (C) |U| – DO 산점 : 상관 부호
        c = axes[row, 2]
        sub = (slice(None, None, 2),) * 3
        u = mag[sub][~obst[sub]].ravel() * 1000
        cc = C[sub][~obst[sub]].ravel()
        c.plot(u, cc, ".", ms=1.2, alpha=0.20, color="#1f4e79", rasterized=True)
        c.set_xlabel("|U| [mm/s]"); c.set_ylabel("DO [mg/L]")
        c.set_title(f"({'AD'[row]}3) $\\rho_{{UC}}$ = {rho:+.2f}   ({regime})", fontsize=10)
        c.set_xscale("log")
        c.grid(alpha=0.25)

        axes[row, 0].text(-0.30, 0.5, f"{title}\n스프레드 {spread:.3f} mg/L",
                          transform=axes[row, 0].transAxes, fontsize=11,
                          rotation=90, va="center", ha="center")

    fig.suptitle("그림 15. 소스 국소성이 레짐을 가른다 — 균일 소비(위) vs 식물 국소 싱크(아래)  "
                 "★ = 최저 DO, ▲ = 폭기 플룸", fontsize=12.5, y=0.99)
    fig.tight_layout(rect=[0.02, 0, 1, 0.96])
    save(fig, "fig15_stageB_DO_field_off_vs_night.png")


if __name__ == "__main__":
    # 그림 15 는 case0086 3모드 재계산이 필요해 별도 스크립트로 분리했다:
    #   PYTHONPATH=/tmp/pylibs python3 solve3.py        (off·night·day 풀이 → /tmp 캐시)
    #   PYTHONPATH=/tmp/pylibs python3 make_fig15.py plot
    fig1(); fig4(); fig5(); fig9()
    print("\n=== 완료 (그림 15 는 make_fig15.py) ===")
