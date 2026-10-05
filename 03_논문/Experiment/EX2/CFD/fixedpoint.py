#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 CFD · alpha_g 자기일관 고정점 (수준별 재수렴)

왜 수준마다 다시 푸나
    alpha_g = U_gs / (W + U_slip) 이고 U_gs = Q_air/A_p 는 z_start 와 무관하게 고정이다
    (같은 에어스톤·같은 Q_air·같은 플룸 반경). 반면 z_start 가 올라가면
    플룸 길이 H_p = 0.21 - z_start 가 짧아져 W 가 줄고, 따라서 alpha_g 는 **커진다**.
    게다가 CFD 는 폭기축을 (0.13, 0.035) -> (0.035, 0.195) 로 옮겼다.
    벽/코너 근접이 달라지면 W 가 달라지므로 **구 고정점을 그대로 쓸 수 없다.**

어떻게 푸나
    stage1 시드런(전 수준 Su=1.751)에서 W_seed(z) 를 재고, 멱법칙 W ∝ Su^n (n=0.511) 을
    각 수준의 국소 스케일로 가정해
        W(Su) = W_seed * (Su/Su_seed)^n,  alpha_g = U_gs/(W+U_slip),  Su = alpha_g*g
    를 수렴할 때까지 반복. 결과를 fp_result.csv 로 쓰고
    gen_cases.py --stage 2 가 그 Su 로 fvOptions 를 갱신한다.

    ※ n 은 z_start=0.02 에서 Su 를 흔들어 얻은 지수다. z_start 나 폭기축을 흔든 것이
      아니므로 "국소 스케일 가정"이며, --verify 의 되먹임 잔차가 그 가정의 검정이다.

usage
    python3 fixedpoint.py            # stage1 시드런 읽어 고정점 산출 -> fp_result.csv
    python3 fixedpoint.py --verify   # stage2 완료 후 잔차 검정 (합격선 3 %)
"""
import argparse
import csv
import os
import sys

import numpy as np

import constants as K
import meshstats

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))


def fixed_point(w_seed, su_seed, n=K.N_EXP):
    """W ∝ Su^n 국소 스케일로 alpha_g = U_gs/(W+U_slip) 의 고정점을 반복해 푼다."""
    w = w_seed
    for _ in range(500):
        ag = K.UGS / (w + K.USLIP)
        w = w_seed * (ag * K.G / su_seed) ** n
    return ag, ag * K.G, w


def collect():
    rows = []
    for c in K.CASES:
        path = os.path.join(HERE, c["cid"])
        try:
            r = meshstats.analyze(path)
        except Exception as e:                              # noqa: BLE001
            print(f"  [건너뜀] {c['cid']}: {str(e).splitlines()[0]}")
            continue
        rows.append((c, r))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="stage2 완료 후 되먹임 잔차 검정")
    a = ap.parse_args()

    rows = collect()
    if not rows:
        sys.exit("분석 가능한 케이스가 없습니다 — stage1 유동해를 먼저 도십시오.")

    print("=" * 104)
    print(f" EX2 CFD · alpha_g 자기일관   U_gs = {K.UGS:.5f} m/s "
          f"(Q_air {K.QAIR_LPM} L/min 실측)   U_slip = {K.USLIP} m/s")
    print("=" * 104)

    if a.verify:
        hdr = (f"{'case':>6}{'z':>7}{'Su(런)':>9}{'W(실측)':>10}"
               f"{'a_g(Su)':>10}{'a_g(W)':>10}{'잔차%':>9}  판정")
        print(hdr); print("-" * len(hdr))
        ok = True
        for c, r in rows:
            su_in = r["Su"]
            ag_su = su_in / K.G                       # 런이 강제한 alpha_g
            ag_w = K.alpha_from_W(r["W"])             # 그 해가 되돌려준 alpha_g
            res = (ag_w - ag_su) / ag_su
            good = abs(res) <= K.TOL_FP
            ok &= good
            print(f"{c['cid']:>6}{c['z_start']:>7.3f}{su_in:>9.4f}{r['W']:>10.5f}"
                  f"{ag_su:>10.4f}{ag_w:>10.4f}{100*res:>9.2f}  "
                  f"{'OK' if good else 'NG'}")
        print(f"\n  자기일관 판정: {'통과' if ok else '미통과'} "
              f"(허용 ±{100*K.TOL_FP:.0f} %)")
        if not ok:
            print("  -> 미통과 케이스는 fixedpoint.py 재산출 + gen_cases.py --stage 2 "
                  "+ 재실행을 한 번 더 돌리십시오.")
        return

    hdr = (f"{'case':>6}{'z':>7}{'H_p':>7}{'Su(런)':>9}{'W_seed':>9}"
           f"{'a_g(런)':>9}{'a_g(W)':>9}{'★1스텝%':>10}"
           f"{'a_g_fp':>9}{'Su_fp':>9}{'고정점%':>9}{'a[1/m]':>9}")
    print(hdr); print("-" * len(hdr))
    out = []
    for c, r in rows:
        su_seed = r["Su"]
        ag, su, w = fixed_point(r["W"], su_seed)
        drift = (su - su_seed) / su_seed
        # ★ 1스텝 잔차 = --verify 가 쓰는 바로 그 지표.
        #   "그 런이 자기가 받은 Su 를 스스로 재현했는가". 재실행 게이트는 이걸로 판정한다.
        #   고정점 이동(drift)은 멱법칙으로 감쇠된 예측치라 항상 더 작게 나온다 —
        #   그걸로 게이트를 걸면 게이트는 통과하고 --verify 는 떨어지는 사태가 생긴다.
        ag_run = su_seed / K.G
        ag_w = K.alpha_from_W(r["W"])
        res1 = (ag_w - ag_run) / ag_run
        a_int = 6.0 * ag / K.DB
        print(f"{c['cid']:>6}{c['z_start']:>7.3f}{K.DEPTH-c['z_start']:>7.3f}"
              f"{su_seed:>9.4f}{r['W']:>9.5f}{ag_run:>9.4f}{ag_w:>9.4f}"
              f"{100*res1:>10.2f}{ag:>9.4f}{su:>9.4f}{100*drift:>9.2f}{a_int:>9.0f}")
        out.append(dict(case=c["cid"], z_start=f"{c['z_start']:.3f}",
                        Hp=f"{K.DEPTH-c['z_start']:.3f}",
                        Su_in=f"{su_seed:.4f}", W_seed=f"{r['W']:.5f}",
                        alpha_g_run=f"{ag_run:.5f}", alpha_g_W=f"{ag_w:.5f}",
                        res_1step_pct=f"{100*res1:.2f}",
                        alpha_g_fp=f"{ag:.5f}", Su_fp=f"{su:.4f}",
                        W_fp=f"{w:.5f}", a_1m=f"{a_int:.0f}",
                        nplume=r["nplume"], drift_pct=f"{100*drift:.2f}"))

    p = os.path.join(HERE, "fp_result.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        wtr = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        wtr.writeheader(); wtr.writerows(out)
    mx = max(abs(float(r["res_1step_pct"])) for r in out)
    bad = [r["case"] for r in out
           if abs(float(r["res_1step_pct"])) > 100 * K.TOL_FP]
    print(f"\n  -> fp_result.csv ({len(out)} 행). **최대 1스텝 잔차 {mx:.1f} %** "
          f"(허용 ±{100*K.TOL_FP:.0f} %)")
    print(f"     재실행 대상: {' '.join(bad) if bad else '없음 — stage2 불필요'}")
    print(f"  다음:  python3 gen_cases.py --stage 2")


if __name__ == "__main__":
    main()
