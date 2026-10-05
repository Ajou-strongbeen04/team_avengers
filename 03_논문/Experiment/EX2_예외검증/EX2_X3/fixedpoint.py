#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2_X3 · 수위별 alpha_g 자기일관 고정점

왜 수위마다 다시 풀어야 하나
    alpha_g = U_gs / (W + U_slip) 인데 U_gs = Q_air/A_p 는 수위와 무관하게 고정이다
    (같은 에어스톤·같은 Q_air·같은 플룸 반경). 반면 수위가 낮아지면 플룸 길이
    H_p = d - 0.02 가 짧아져 W 가 줄고, 따라서 alpha_g 는 **커진다**.
    d=0.21 에서 확정한 Su=1.773 을 전 수준에 그대로 쓰면 얕은 수조에서 부력을
    과소평가한다.

어떻게 푸나
    stage1 시드런(전 수준 Su=1.773)에서 W_seed(d) 를 재고,
    ../EX2_X §4.2 에서 확정된 멱법칙 W ∝ Su^n (n=0.511, 3점 LSQ 잔차 0.28%)
    을 각 수준의 국소 스케일로 가정해
        W(Su) = W_seed * (Su/1.773)^n,   alpha_g = U_gs/(W+U_slip),   Su = alpha_g*g
    를 수렴할 때까지 반복한다. 결과를 fp_result.csv 로 쓰고
    gen_cases.py --stage 2 가 그 Su 로 fvOptions 를 갱신한다.

usage:
    python3 fixedpoint.py            # d18..d09 시드런 읽어 고정점 산출
    python3 fixedpoint.py --verify   # stage2 완료 후 잔차 검정 (합격선 3 %)
"""
import argparse
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "EX2_X"))
import compare as cx                                        # noqa: E402

# Windows 콘솔(cp949)에서 ✅·— 같은 문자 출력 시 UnicodeEncodeError 로 죽는 것 방지.
# 2026-07-29: MSYS 창은 UTF-8 인데 python 기본 stdout 이 cp949 라 한글도 깨졌다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ---- 운전점 상수 (../EX2_X1/README.md §1·§4.2, ../상수_목록.md) -------
QAIR = 1.2 / 1000 / 60          # m3/s   실측 500 mL / 25 s 3회 평균
USLIP = 0.0578                  # m/s    0.5 mm 기포 종단속도 @25 C
PLUME_R = 0.01                  # m
DB = 0.5e-3                     # m
G = 9.81
N_EXP = 0.511                   # W ∝ Su^n  (3점 LSQ, 잔차 0.28 %)
SU_SEED = 1.773
Z_START = 0.02
TOL = 0.03                      # alpha_g 자기일관 허용 잔차

UGS = QAIR / (np.pi * PLUME_R ** 2)

CASES = [("d21", os.path.join(HERE, "..", "EX2_X", "case_su177")),
         ("d18", os.path.join(HERE, "d18")),
         ("d15", os.path.join(HERE, "d15")),
         ("d12", os.path.join(HERE, "d12")),
         ("d09", os.path.join(HERE, "d09"))]


def fixed_point(w_seed, su_seed=SU_SEED, n=N_EXP):
    w = w_seed
    for _ in range(500):
        ag = UGS / (w + USLIP)
        w = w_seed * (ag * G / su_seed) ** n
    return ag, ag * G, w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="stage2 결과의 자기일관 잔차 검정")
    a = ap.parse_args()

    rows, missing = [], []
    for cid, path in CASES:
        try:
            r = cx.analyze(path)
        except Exception as e:                               # noqa: BLE001
            missing.append((cid, str(e).split(chr(10))[0]))
            continue
        d = r["L"][2]
        rows.append(dict(cid=cid, path=path, d=d, nz=r["nz"], W=r["W"],
                         Su_in=r["Su"], Qp=r["Qp"], meanU=r["meanU"],
                         Hp=d - Z_START, V=r["V"] * 1000))

    if missing:
        print("[미완] 아직 결과가 없는 케이스:")
        for cid, msg in missing:
            print(f"    {cid}: {msg}")
        if not rows:
            sys.exit(1)
        print()

    print("=" * 92)
    print(f" 수위별 alpha_g 자기일관 고정점    U_gs = {UGS:.4f} m/s (수위 무관)"
          f"    n = {N_EXP}")
    print("=" * 92)

    if a.verify:
        hdr = (f"{'case':6}{'d[m]':>7}{'Su 입력':>9}{'W 실측':>9}"
               f"{'α_g 입력':>10}{'α_g 되먹임':>12}{'잔차':>9}  판정")
        print("\n" + hdr)
        print("-" * len(hdr))
        bad = 0
        for r in rows:
            ag_in = r["Su_in"] / G
            ag_fb = UGS / (r["W"] + USLIP)
            res = (ag_fb - ag_in) / ag_in
            ok = abs(res) <= TOL
            bad += (not ok)
            print(f"{r['cid']:6}{r['d']:>7.2f}{r['Su_in']:>9.4g}{r['W']:>9.4f}"
                  f"{ag_in:>10.4f}{ag_fb:>12.4f}{100*res:>8.1f} %  "
                  f"{'✅' if ok else '❌ 재반복'}")
        print(f"\n  → {'✅ 전 수준 자기일관' if not bad else f'❌ {bad}개 수준 미수렴'}"
              f"  (허용 ±{100*TOL:.0f} %)")
        return

    hdr = (f"{'case':6}{'d[m]':>7}{'H_p[m]':>8}{'V[L]':>7}{'W 시드':>9}"
           f"{'α_g':>9}{'Su 고정점':>11}{'W 예측':>9}{'a[1/m]':>9}{'Su 변화':>9}")
    print("\n" + hdr)
    print("-" * len(hdr))
    out = []
    for r in rows:
        ag, su, w = fixed_point(r["W"])
        out.append(dict(cid=r["cid"], d=f"{r['d']:.4f}", nz=r["nz"],
                        W_seed=f"{r['W']:.5f}", Su_seed=f"{r['Su_in']:.4f}",
                        alpha_g_fp=f"{ag:.5f}", Su_fp=f"{su:.4f}",
                        W_pred=f"{w:.5f}", a_fp=f"{6*ag/DB:.0f}"))
        print(f"{r['cid']:6}{r['d']:>7.2f}{r['Hp']:>8.2f}{r['V']:>7.1f}"
              f"{r['W']:>9.4f}{ag:>9.4f}{su:>11.4f}{w:>9.4f}{6*ag/DB:>9.0f}"
              f"{100*(su/r['Su_in']-1):>8.1f} %")

    p = os.path.join(HERE, "fp_result.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        wtr = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        wtr.writeheader()
        wtr.writerows(out)
    print(f"\n  → {os.path.basename(p)} 기록 ({len(out)} 수준)")
    print("     다음: python3 gen_cases.py --stage 2   (D군 fvOptions 갱신)")
    print("           bash run.sh stage2")

    big = [o for o in out
           if abs(float(o["Su_fp"]) / SU_SEED - 1) > TOL]
    if big:
        print(f"\n  [주의] Su 이동이 3 % 를 넘는 수준: "
              f"{', '.join(o['cid'] for o in big)} → stage2 재실행 필수")
    else:
        print("\n  [참고] 전 수준 Su 이동이 3 % 이내 → stage2 생략 가능")


if __name__ == "__main__":
    main()
