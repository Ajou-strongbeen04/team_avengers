#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2_X4 · 3-D K_La 배치 실행기 — kappa 의 분모를 확정한다

왜 필요한가
    현재 문서에 있는 K_La 는 **전부 0-D 해석식**이다
    (EX2_X3 README §7 미결: "kappa = K_La_meas/K_La_CFD 의 분모가 이 값이므로
     7/29 실측과 대조하기 전에 3-D 로 확정할 것").
    0-D 와 3-D 는 계통적으로 다르다 — 0-D 는 K_La ∝ alpha_g 라 되먹임 산포가 그대로
    실리고, 3-D 는 순환 Q_p 증가가 상쇄해 산포가 좁아진다
    (위치 CV: 0-D 12–13 % vs 3-D 5.1 %).  **논문에 쓰는 값은 3-D 쪽이다.**

무엇을 도나
    ../EX2/CFD/reaer/reaer_solver.py 를 케이스마다 호출한다.
    케이스별 alpha_g 는 입력 Su/g 가 아니라 **실측 W 되먹임** U_gs/(W+U_slip) 으로
    계산한다 — collect.py·EX2_X3/collect.py 와 같은 폐합이다.
    적분 종료시간은 0-D tau 의 5배(최소 3600 s)로 자동 설정한다.

케이스 군
    z    z02(=../EX2_X1/case_su177) z05 z08 z11   z_start 레버의 3-D 확인
    m    m21 (../EX2_X3)                          ★ 생산 운전점 medium 앵커
                                                           = kappa 의 분모 절대값
    p    p15 p04 p01 (../EX2_X3)                  신 운전점 위치 3점 (Su=1.773)
    pref pos15 pos4 pos1 (../EX2/CFD/flow)               구 운전점 위치 3점 (Su=2.86)
                                                           → p 와 대조해 CV 보존 재검정

usage:
    python3 run_reaer.py --group m            # 앵커 1개만 (가장 급한 것)
    python3 run_reaer.py --group z            # z_start 4수준
    python3 run_reaer.py --group p,pref       # 위치 CV 3-D 6케이스
    python3 run_reaer.py --group all
    python3 run_reaer.py --group all --dry    # 명령만 출력 (실행 안 함)
    python3 run_reaer.py --group m --quick    # 성긴 dt 로 빠른 점검
"""
import argparse
import csv
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "EX2_X"))
import compare as cx                                        # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SOLVER = os.path.join(HERE, "..", "EX2", "CFD", "reaer", "reaer_solver.py")
OUT = os.path.join(HERE, "reaer_out")

# ---- 물성 (collect.py / reaer_solver.py 와 동일) ---------------------------
DMOL_20, NU_20 = 2.0e-9, 1.0e-6
KL_SURF_20, THETA_KL = 2.3e-5, 1.024
DB, USLIP = 0.5e-3, 0.0578
QAIR, PLUME_R = 1.2 / 1000 / 60, 0.01
UGS = QAIR / (np.pi * PLUME_R ** 2)

E3 = os.path.join(HERE, "..", "EX2_X3")
FLOW = os.path.join(HERE, "..", "EX2", "CFD", "flow")

GROUPS = {
    "z": [("z02", os.path.join(HERE, "..", "EX2_X", "case_su177")),
          ("z05", os.path.join(HERE, "z05")),
          ("z08", os.path.join(HERE, "z08")),
          ("z11", os.path.join(HERE, "z11")),
          ("z14", os.path.join(HERE, "z14")),
          ("z17", os.path.join(HERE, "z17"))],
    "m": [("m21", os.path.join(E3, "m21"))],
    "p": [("p15", os.path.join(E3, "p15")),
          ("p04", os.path.join(E3, "p04")),
          ("p01", os.path.join(E3, "p01"))],
    "pref": [("pos15", os.path.join(FLOW, "pos15")),
             ("pos4", os.path.join(FLOW, "pos4")),
             ("pos1", os.path.join(FLOW, "pos1"))],
}


def kla_0d(r, T, alpha_override=None):
    """0-D 해석 K_La [1/s] 와 alpha_g (기본 = 실측 W 되먹임)."""
    alpha_g = UGS / (r["W"] + USLIP) if alpha_override is None else alpha_override
    a = 6.0 * alpha_g / DB
    kL_surf = KL_SURF_20 * THETA_KL ** (T - 20.0)
    Re_b, Sc = USLIP * DB / NU_20, NU_20 / DMOL_20
    Sh_b = 2.0 + 0.6 * Re_b ** 0.5 * Sc ** (1.0 / 3.0)
    kL_b = Sh_b * DMOL_20 / DB
    lx, ly, lz = r["L"]
    V = lx * ly * lz
    dx, dy, dz = r["d"]
    vp = r["nplume"] * dx * dy * dz
    return (vp / V) * kL_b * a + kL_surf * (lx * ly) / V, alpha_g, a


FIT_PATS = {
    "KLa_3D_1h": r"K_La_eff,CFD\s*=\s*[\d.eE+-]+\s*/s\s*=\s*([\d.eE+-]+)\s*/h",
    "Cstar_3D": r"C\*_CFD\s*=\s*([\d.eE+-]+)",
    "ratio_3D_0D": r"3D/0-D 비\s*=\s*([\d.eE+-]+)",
    "RMSE": r"피팅 RMSE\s*=\s*([\d.eE+-]+)",
}


def parse_fit(path):
    if not os.path.exists(path):
        return {}
    t = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for k, pat in FIT_PATS.items():
        m = re.search(pat, t)
        out[k] = float(m.group(1)) if m else float("nan")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="m",
                    help="z / m / p / pref / all, 쉼표 조합 가능")
    ap.add_argument("--T", type=float, default=25.0, help="수온 [degC]")
    ap.add_argument("--P", type=float, default=101.325, help="기압 [kPa]")
    ap.add_argument("--n-tau", type=float, default=5.0,
                    help="적분 종료 = n_tau × tau_0D (기본 5)")
    ap.add_argument("--alpha-g", type=float, default=None,
                    help="alpha_g 를 이 값으로 고정(전 케이스 공통). 기본은 케이스별 "
                         "W 되먹임 U_gs/(W+U_slip). 앵커의 자기일관 고정점 0.1785 를 "
                         "쓰려면 --alpha-g 0.1785 (되먹임값 0.1776 과 0.5 % 차이)")
    ap.add_argument("--quick", action="store_true", help="reaer_solver --quick")
    ap.add_argument("--dry", action="store_true", help="명령만 출력")
    ap.add_argument("--force", action="store_true", help="fit.txt 있어도 재실행")
    ap.add_argument("--wall-limit", type=float, default=0.0,
                    help="케이스당 벽시간 상한 [s] (0=무제한, 솔버로 전달)")
    a = ap.parse_args()

    picks = ["z", "m", "p", "pref"] if "all" in a.group else \
        [g.strip() for g in a.group.split(",")]
    cases = []
    for g in picks:
        if g not in GROUPS:
            sys.exit(f"모르는 군: {g}  (z/m/p/pref/all)")
        cases += [(g, cid, p) for cid, p in GROUPS[g]]

    py = sys.executable or "python3"
    os.makedirs(OUT, exist_ok=True)

    print("=" * 96)
    print(f" EX2_X4 · 3-D K_La 배치   T={a.T:g} °C   "
          f"종료시간 = {a.n_tau:g}×tau_0D   출력 {os.path.relpath(OUT, HERE)}/")
    print("=" * 96)

    rows = []
    for grp, cid, path in cases:
        path = os.path.abspath(path)
        tag = f"{cid}_T{a.T:g}"
        fit_path = os.path.join(OUT, tag, "fit.txt")

        try:
            r = cx.analyze(path)
        except Exception as e:                               # noqa: BLE001
            print(f"\n[건너뜀] {cid}: {str(e).splitlines()[0]}")
            continue

        k0, ag, aa = kla_0d(r, a.T, a.alpha_g)
        tau = 1.0 / k0
        end = max(3600.0, a.n_tau * tau)
        dt_max = max(10.0, end / 1800.0)

        print(f"\n----- [{grp}] {cid}  ({os.path.relpath(path, HERE)})")
        print(f"      격자 {r['nx']}x{r['ny']}x{r['nz']}  Su(입력) {r['Su']:.4g}"
              f"  W {r['W']:.4f}  → α_g {ag:.4f}  a {aa:.0f} /m")
        print(f"      0-D K_La {k0*3600:.3f} /h  τ {tau/60:.1f} 분"
              f"  → --end {end:.0f} s  --dt-max {dt_max:.1f} s")

        cmd = [py, SOLVER, "--case", path, "--T", f"{a.T:g}", "--P", f"{a.P:g}",
               "--alpha-g", f"{ag:.5f}", "--end", f"{end:.0f}",
               "--dt-max", f"{dt_max:.1f}", "--tag", tag, "--out", OUT,
               "--noplot"]
        if a.quick:
            cmd.append("--quick")
        if a.wall_limit > 0:
            cmd += ["--wall-limit", f"{a.wall_limit:g}"]

        if a.dry:
            print("      $ " + " ".join(cmd))
            continue
        if os.path.exists(fit_path) and not a.force:
            print(f"      결과 있음 → 스킵 (--force 로 재실행)")
        else:
            rc = subprocess.call(cmd)
            if rc != 0:
                print(f"      [ERROR] reaer_solver 실패 (rc={rc})")
                continue

        f = parse_fit(fit_path)
        if not f:
            print("      [ERROR] fit.txt 없음")
            continue
        print(f"      → 3-D K_La {f['KLa_3D_1h']:.3f} /h"
              f"  (0-D 대비 {f['ratio_3D_0D']:.3f})"
              f"  C* {f['Cstar_3D']:.3f} mg/L  τ {60/f['KLa_3D_1h']:.1f} 분")
        rows.append(dict(group=grp, case=cid, path=os.path.relpath(path, HERE),
                         nx=r["nx"], ny=r["ny"], nz=r["nz"],
                         Su_in=f"{r['Su']:.4f}", W=f"{r['W']:.5f}",
                         alpha_g=f"{ag:.5f}", a=f"{aa:.0f}",
                         KLa_0D_1h=f"{k0*3600:.4f}",
                         KLa_3D_1h=f"{f['KLa_3D_1h']:.4f}",
                         tau_3D_min=f"{60/f['KLa_3D_1h']:.2f}",
                         Cstar_3D=f"{f['Cstar_3D']:.4f}",
                         ratio_3D_0D=f"{f['ratio_3D_0D']:.4f}",
                         fit_RMSE=f"{f['RMSE']:.3e}"))

    if a.dry or not rows:
        return

    # ---------------- 요약 ----------------
    print("\n" + "=" * 96)
    print(" 요약")
    print("=" * 96)
    hdr = (f"{'군':>5}{'case':>8}{'α_g':>9}{'0-D[1/h]':>10}{'3-D[1/h]':>10}"
           f"{'3D/0D':>8}{'τ_3D[분]':>10}{'C*':>9}")
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['group']:>5}{r['case']:>8}{float(r['alpha_g']):>9.4f}"
              f"{float(r['KLa_0D_1h']):>10.3f}{float(r['KLa_3D_1h']):>10.3f}"
              f"{float(r['ratio_3D_0D']):>8.3f}{float(r['tau_3D_min']):>10.1f}"
              f"{float(r['Cstar_3D']):>9.3f}")

    for g, label in (("p", "신 운전점 Su=1.773 (coarse)"),
                     ("pref", "구 운전점 Su=2.86 (medium)")):
        k = np.array([float(r["KLa_3D_1h"]) for r in rows if r["group"] == g])
        if len(k) >= 2:
            cv = 100 * k.std(ddof=1) / k.mean()
            print(f"\n  위치 CV (3-D) · {label}: {k.mean():.3f} ± "
                  f"{k.std(ddof=1):.3f} /h → **CV {cv:.1f} %**")
    cvs = {}
    for g in ("p", "pref"):
        k = np.array([float(r["KLa_3D_1h"]) for r in rows if r["group"] == g])
        if len(k) >= 2:
            cvs[g] = 100 * k.std(ddof=1) / k.mean()
    if len(cvs) == 2:
        d = abs(cvs["p"] - cvs["pref"])
        print(f"    → 두 운전점 CV 차이 {d:.1f} %p "
              f"({'보존' if d <= 2.0 else '미보존'}, 허용 2 %p). "
              f"EX2_X3 §5.2 의 0-D 판정(1.0 %p)을 3-D 로 대체한다.")

    anchor = [r for r in rows if r["case"] == "m21"]
    if anchor:
        k3 = float(anchor[0]["KLa_3D_1h"])
        print(f"\n  ★ kappa 분모 (생산 운전점 medium 앵커 m21):")
        print(f"      K_La_eff,CFD = {k3:.3f} /h,  τ = {60/k3:.1f} 분")
        print(f"      kappa = K_La_meas[/h] / {k3:.3f}")
        print(f"      (0-D 값 {float(anchor[0]['KLa_0D_1h']):.3f} /h 는 "
              f"이제 분모로 쓰지 않는다.)")

    p = os.path.join(HERE, "kla_3d.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n  → kla_3d.csv 기록 ({len(rows)} 행)")


if __name__ == "__main__":
    main()
