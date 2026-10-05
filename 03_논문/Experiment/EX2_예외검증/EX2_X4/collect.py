#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2_X4 · 집계 — z_start 레버 표 (0-D 해석식)

K_La 는 reaer_solver.py 의 "해석예측" 줄과 **같은 식**으로 계산한다
(pos1_상수확정_T20.md §4 · EX2_X3/collect.py 와 동일):

    K_La = (V_plume/V) * k_L,b * a  +  k_L,surf * (Lx*Ly)/V
    a = 6*alpha_g/d_b ,  k_L,b = Sh_b*D/d_b ,  Sh_b = 2 + 0.6 Re_b^1/2 Sc^1/3

  ※ 이 값은 **0-D 해석식**이다. kappa 의 분모로 쓸 3-D 값은 run_reaer.py 가 낸다.
    두 값은 계통적으로 다르다 — 0-D 는 K_La ∝ alpha_g 라 되먹임 산포가 그대로
    실리고, 3-D 는 순환 Q_p 증가가 상쇄해 산포가 좁아진다
    (EX2_X3 §5.2: 위치 CV 12–13 % (0-D) vs 5.1 % (3-D)).

usage:
    python3 collect.py            # T=25 기준 집계 → results_zstart.csv
    python3 collect.py --T 20
"""
import argparse
import csv
import os
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


# ---- 물성 (상수_목록 A·C군 / reaer_solver.py 와 동일) ----------------------
DMOL_20 = 2.0e-9
NU_20 = 1.0e-6
KL_SURF_20 = 2.3e-5
THETA_KL = 1.024
DB = 0.5e-3
USLIP = 0.0578          # 25 C
G = 9.81

QAIR = 1.2 / 1000 / 60
PLUME_R = 0.01
UGS = QAIR / (np.pi * PLUME_R ** 2)      # 0.0637 m/s — z_start·위치 무관 고정

CASES = [("z02", os.path.join(HERE, "..", "EX2_X", "case_su177"))] + \
        [(c, os.path.join(HERE, c))
         for c in ("z05", "z08", "z11", "z14", "z17")]

# 방법론 §6.2 해석추정(Q_p ∝ H_p^5/3). 0.11 은 0.08·0.14 두 점의 멱법칙 내삽.
#   실험계획서_v2.md §7.2 표와 같은 값. 이 표를 CFD 실측으로 **교체**하는 것이 목적.
ANALYTIC = {"z02": 100.0, "z05": 68.0, "z08": 44.0, "z11": 29.4,
            "z14": 17.0, "z17": 8.0}

# 1차 4수준(2026-07-29)에 맞춘 선형모델 예측 [%]:
#     K_La = 0.444 + 2.483*(H_p/0.19)*(a/2178)   (수면항 고정 + 플룸항 ∝ H_p·a)
#   z05/z08/z11 을 각각 0.7/1.5/2.7 % 오차로 재현한다. 연장 수준의 사전 예측치.
PRED = {"z02": 100.0, "z05": 84.7, "z08": 74.4, "z11": 63.0,
        "z14": 50.4, "z17": 36.4}


def kla_of(r, T):
    """해석 K_La [1/h], 플룸 기여비, V[L], alpha_g, a.

    alpha_g 는 입력 Su/g 가 아니라 **실측 W 되먹임** U_gs/(W+U_slip) 을 쓴다.
    이것이 물리 폐합이고, 수준별 K_La 산포가 여기서 나온다.
    """
    alpha_g = UGS / (r["W"] + USLIP)
    a = 6.0 * alpha_g / DB
    kL_surf = KL_SURF_20 * THETA_KL ** (T - 20.0)
    Re_b = USLIP * DB / NU_20
    Sc = NU_20 / DMOL_20
    Sh_b = 2.0 + 0.6 * Re_b ** 0.5 * Sc ** (1.0 / 3.0)
    kL_b = Sh_b * DMOL_20 / DB

    lx, ly, lz = r["L"]
    V = lx * ly * lz
    dx, dy, dz = r["d"]
    vp = r["nplume"] * dx * dy * dz

    kla_p = (vp / V) * kL_b * a
    kla_s = kL_surf * (lx * ly) / V
    kla = kla_p + kla_s
    return kla * 3600, 100 * kla_p / kla, V * 1000, alpha_g, a


def load(pairs):
    out = []
    for cid, p in pairs:
        try:
            r = cx.analyze(p)
            r["cid"] = cid
            out.append(r)
        except Exception as e:                               # noqa: BLE001
            print(f"    [미완] {cid}: {str(e).splitlines()[0]}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--T", type=float, default=25.0, help="수온 [degC]")
    a = ap.parse_args()

    print("\n" + "=" * 104)
    print(f" z_start 레버 — EX2 hold-out 축   (T = {a.T:g} °C, d = 0.21 m 고정, "
          f"V 고정)")
    print("=" * 104)

    zs = load(CASES)
    if not zs:
        sys.exit("케이스 없음 — bash run.sh 를 먼저 도십시오.")

    hdr = (f"{'case':6}{'z0[m]':>7}{'H_p':>6}{'V[L]':>7}{'셀수':>9}{'Su':>8}"
           f"{'α_g':>8}{'a[1/m]':>8}{'W':>8}{'Qp':>7}{'K_La[1/h]':>11}"
           f"{'τ[분]':>8}{'90%[분]':>9}{'플룸%':>7}{'CFD비':>7}{'예측':>7}{'해석':>7}")
    print("\n" + hdr)
    print("-" * len(hdr))

    rows, base = [], None
    for r in sorted(zs, key=lambda x: x["pz"][0]):
        kla, frac, V, ag, aa = kla_of(r, a.T)
        base = base or kla
        z0 = r["pz"][0]
        lever = 100 * kla / base
        t90 = np.log(10.0) / kla * 60
        ana = ANALYTIC.get(r["cid"], float("nan"))
        prd = PRED.get(r["cid"], float("nan"))
        print(f"{r['cid']:6}{z0:>7.2f}{r['pz'][1]-z0:>6.2f}{V:>7.1f}{r['N']:>9,}"
              f"{r['Su']:>8.4g}{ag:>8.4f}{aa:>8.0f}{r['W']:>8.4f}"
              f"{r['Qp']*6e4:>7.2f}{kla:>11.3f}{60/kla:>8.1f}{t90:>9.0f}"
              f"{frac:>7.0f}{lever:>6.0f} %{prd:>6.0f} %{ana:>6.0f} %")
        rows.append(dict(case=r["cid"], z_start=f"{z0:.3f}",
                         Hp=f"{r['pz'][1]-z0:.3f}", cells=r["N"],
                         Su=f"{r['Su']:.4f}", alpha_g=f"{ag:.5f}", a=f"{aa:.0f}",
                         W=f"{r['W']:.5f}", Qp_Lmin=f"{r['Qp']*6e4:.3f}",
                         meanU=f"{r['meanU']:.5f}", KLa_0D_1h=f"{kla:.4f}",
                         tau_min=f"{60/kla:.2f}", t90_min=f"{t90:.1f}",
                         plume_pct=f"{frac:.1f}", lever_pct=f"{lever:.1f}",
                         lever_pred_pct=f"{prd:.1f}",
                         lever_analytic_pct=f"{ana:.1f}"))

    # ---------------- 판정 ----------------
    print("\n" + "-" * 104)
    lev = [float(r["lever_pct"]) for r in rows]
    ana = [float(r["lever_analytic_pct"]) for r in rows]
    dev = max(abs(l - x) for l, x in zip(lev, ana))
    mono = all(lev[i] > lev[i + 1] for i in range(len(lev) - 1))

    print(f"  [판정 1] 단조 감소인가 : {'예' if mono else '아니오 — 축으로 못 씀'}")
    print(f"           z_start 가 올라갈수록 H_p 가 짧아져 K_La 가 줄어야 한다.")
    print(f"           수위 축(EX2_X3 §5.1)은 여기서 부호가 뒤집혀 탈락했다.")
    print(f"\n  [판정 2] 레버 크기      : {lev[0]:.0f} → {lev[-1]:.0f} %"
          f"   (실험 반복 재현성 CV 5–10 % 대비)")
    print(f"           레버가 재현성에 묻히면 hold-out 잔차가 전이성의 증거가 못 된다")
    print(f"           (위치 축 ±9 % 가 그 이유로 탈락했다).")
    prd = [float(r["lever_pred_pct"]) for r in rows]
    dev_p = max(abs(l - x) for l, x in zip(lev, prd))
    print(f"\n  [판정 3] 해석추정 대비   : 최대편차 {dev:.0f} %p")
    print(f"           선형모델 대비   : 최대편차 {dev_p:.0f} %p"
          f"   ({'모델 유효' if dev_p <= 5 else '모델 이탈 — 격자·물리 재점검'})")
    print(f"           편차가 크면 실험계획서_v2.md §7.2 표를 **CFD 값으로 교체**하고,")
    print(f"           런당 로깅 시간(90 % 도달)도 위 표의 CFD 값으로 다시 잡는다.")

    p = os.path.join(HERE, "results_zstart.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n  → results_zstart.csv 기록 ({len(rows)} 행)")
    print("     다음: python3 run_reaer.py --group z   (3-D K_La 확정)")


if __name__ == "__main__":
    main()
