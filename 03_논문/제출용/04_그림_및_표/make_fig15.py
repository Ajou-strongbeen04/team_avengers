# -*- coding: utf-8 -*-
"""
그림 15 — 소스 국소성이 레짐을 가른다 (§3.8, 표 3-11).
case0086 (PL+PL, 25 °C) 을 plant_mode = off / night / day 로 다시 풀어 장을 그린다.
  · 기존 stageB_DO/_viz_*.npz 는 부하 R 이 다른 별개 실행이라 표 3-11 과 맞지 않아 재계산한다.
  · 정답 대조: stageB_DO/compare_photo.json 의 case0086 3행.
실행:  PYTHONPATH=/tmp/pylibs python3 make_fig15.py
"""
import os, sys, json, importlib.util
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SB   = os.path.join(ROOT, "Experiment", "EX3", "dataset", "stageB_DO")
CASE = os.path.join(ROOT, "Experiment", "EX3", "dataset", "result", "case0086")

spec = importlib.util.spec_from_file_location("sd", os.path.join(SB, "solve_do.py"))
sd = importlib.util.module_from_spec(spec); spec.loader.exec_module(sd)

plt.rcParams.update({
    "font.family": ["Noto Sans CJK JP", "DejaVu Sans"],
    "axes.unicode_minus": False, "font.size": 10,
    "savefig.dpi": 300, "figure.dpi": 110,
})

LX, LY, LZ = sd.LX, sd.LY, sd.LZ
NX, NY, NZ = sd.NX, sd.NY, sd.NZ

# ── 3 모드 풀이 ────────────────────────────────────────────────
MODES = [("off",   "off — 균일 소비만",        "유동지배"),
         ("night", "night — 식물 국소 싱크",   "전이대"),
         ("day",   "day — 식물 국소 소스",     "소스지배")]

U   = sd.read_field(os.path.join(CASE, "200/UMean.gz"))
mag = np.linalg.norm(U, axis=1).reshape(NZ, NY, NX)

obst = np.zeros(sd.N, bool)
for nm in ["obs0", "obs1", "obs2", "obs3", "obs4", "obs5"]:
    try: obst[sd.read_zone(CASE, nm)] = True
    except Exception: pass
plant = np.zeros(sd.N, bool)
for cells, _ in sd.read_plant_zones(CASE):
    plant[cells] = True
plume = np.zeros(sd.N, bool); plume[sd.read_plume_cells(CASE)] = True
obst  = obst.reshape(NZ, NY, NX)
plant = plant.reshape(NZ, NY, NX)
plume = plume.reshape(NZ, NY, NX)

CACHE = "/tmp/fig15_cache"
os.makedirs(CACHE, exist_ok=True)

def get_field(m):
    """모드별 해를 /tmp 에 캐시. 한 모드씩 따로 돌려도 이어서 진행된다."""
    p = os.path.join(CACHE, f"{m}.npz")
    if os.path.exists(p):
        z = np.load(p, allow_pickle=True)
        return z["C"], json.loads(str(z["diag"]))
    print(f"[{m}] solving ...", flush=True)
    cfg = dict(sd.CONFIG); cfg["plant_mode"] = m
    C, d = sd.solve_case(CASE, cfg)
    np.savez_compressed(p, C=C.reshape(NZ, NY, NX), diag=json.dumps(d))
    print(f"[{m}] done", flush=True)
    return C.reshape(NZ, NY, NX), d

only = sys.argv[1] if len(sys.argv) > 1 else None
if only and only != "plot":
    get_field(only); sys.exit(0)

fields = {}
for m, _, _ in MODES:
    C, d = get_field(m)
    fields[m] = (C, d)
    print(f"{m:>6}  Cmin={d['C_min']:.3f}  Cmax={d['C_max']:.3f}  "
          f"spread={d['C_max']-d['C_min']:.3f}  corr={d['corr_velDO']:+.3f}", flush=True)

# 대조 (표 3-11 정본)
ref = {r["plant_mode"]: r for r in json.load(open(os.path.join(SB, "compare_photo.json"),
                                                encoding="utf-8")) if r["case"] == "case0086"}
print("\n대조 (compare_photo.json):")
for m, _, _ in MODES:
    r, d = ref[m], fields[m][1]
    print(f"  {m:>6}  dCmin={d['C_min']-r['C_min']:+.2e}  dcorr={d['corr_velDO']-r['corr_velDO']:+.2e}")

# ── 작도 ──────────────────────────────────────────────────────
xs = (np.arange(NX) + 0.5) * LX / NX
ys = (np.arange(NY) + 0.5) * LY / NY
zs = (np.arange(NZ) + 0.5) * LZ / NZ
fluid = ~obst
pj, pi = np.where(plume.any(0))
px, py = xs[pi].mean(), ys[pj].mean()

fig, axes = plt.subplots(3, 3, figsize=(14.6, 9.6))
for row, (m, title, regime) in enumerate(MODES):
    C, d = fields[m]
    Cf = C.copy(); Cf[obst] = 1e9
    k0, j0, i0 = np.unravel_index(np.argmin(Cf), C.shape)
    vmin, vmax = C[fluid].min(), C[fluid].max()
    spread = vmax - vmin
    rho = d["corr_velDO"]

    def deco(a, pl_mask):
        a.contourf(*pl_mask[:2], pl_mask[2].astype(float), levels=[0.5, 1.5],
                   colors="none", hatches=["////"], alpha=0)
    # (1) 수평 단면 @ 최저 DO 층
    a = axes[row, 0]
    im = a.pcolormesh(xs, ys, np.ma.masked_where(obst[k0], C[k0]),
                      cmap="RdYlBu", vmin=vmin, vmax=vmax, shading="auto")
    a.contourf(xs, ys, obst[k0].astype(float), levels=[0.5, 1.5], colors="#4a4a4a")
    if plant[k0].any():
        a.contour(xs, ys, plant[k0].astype(float), levels=[0.5], colors="#00c853", linewidths=1.6)
    a.plot(px, py, "^", ms=10, mfc="cyan", mec="k")
    a.plot(xs[i0], ys[j0], "*", ms=17, mfc="yellow", mec="k")
    a.set_aspect("equal"); a.set_xlabel("x [m]"); a.set_ylabel("y [m]")
    a.set_title(f"({row+1}a) 수평 단면  z = {zs[k0]*100:.1f} cm", fontsize=10)
    fig.colorbar(im, ax=a, label="DO [mg/L]", fraction=0.031, pad=0.02)

    # (2) 연직 단면
    b = axes[row, 1]
    im2 = b.pcolormesh(xs, zs, np.ma.masked_where(obst[:, j0, :], C[:, j0, :]),
                       cmap="RdYlBu", vmin=vmin, vmax=vmax, shading="auto")
    b.contourf(xs, zs, obst[:, j0, :].astype(float), levels=[0.5, 1.5], colors="#4a4a4a")
    if plant[:, j0, :].any():
        b.contour(xs, zs, plant[:, j0, :].astype(float), levels=[0.5],
                  colors="#00c853", linewidths=1.6)
    pk, pi2 = np.where(plume[:, j0, :])
    if len(pi2): b.plot(xs[pi2].mean(), zs[pk].mean(), "^", ms=10, mfc="cyan", mec="k")
    b.plot(xs[i0], zs[k0], "*", ms=17, mfc="yellow", mec="k")
    b.set_aspect("equal"); b.set_xlabel("x [m]"); b.set_ylabel("z [m]  (0 = 바닥)")
    b.set_title(f"({row+1}b) 연직 단면  y = {ys[j0]*100:.1f} cm", fontsize=10)
    fig.colorbar(im2, ax=b, label="DO [mg/L]", fraction=0.031, pad=0.02)

    # (3) |U|–DO 산점
    c = axes[row, 2]
    ss = (slice(None, None, 2),) * 3
    u  = mag[ss][fluid[ss]].ravel() * 1000
    cc = C[ss][fluid[ss]].ravel()
    c.plot(u, cc, ".", ms=1.1, alpha=0.16, color="#1f4e79", rasterized=True)
    c.set_xscale("log"); c.grid(alpha=0.25)
    c.set_xlabel("|U| [mm/s]"); c.set_ylabel("DO [mg/L]")
    col = {"유동지배": "#1f4e79", "전이대": "#e07b39", "소스지배": "#c0504d"}[regime]
    c.set_title(f"({row+1}c)  $\\rho_{{UC}}$ = {rho:+.2f}   —  {regime}",
                fontsize=10.5, color=col, fontweight="bold")

    axes[row, 0].text(-0.34, 0.5,
                      f"{title}\n$C_\\mathrm{{min}}$ {vmin:.3f} · 스프레드 {spread:.3f} mg/L",
                      transform=axes[row, 0].transAxes, fontsize=10.2,
                      rotation=90, va="center", ha="center")

fig.suptitle("그림 15. 소스 국소성이 레짐을 가른다 — case0086 (PL+PL, 25 °C) 동일 유동장 위 소스 배치만 교체\n"
             "★ = 최저 DO · ▲ = 폭기 플룸 · 초록 윤곽 = 수초 · 회색 = 장애물",
             fontsize=12.5, y=0.995)
fig.tight_layout(rect=[0.025, 0, 1, 0.945])
out = os.path.join(HERE, "fig15_stageB_regime_transition.png")
fig.savefig(out, bbox_inches="tight", facecolor="white")
print("\nWROTE", os.path.basename(out))
