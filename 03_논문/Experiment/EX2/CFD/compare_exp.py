#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 CFD · 실측 대 CFD 정량비교 — 최종 산출표

무엇을 내나
    1) 런별 kappa = K_La_meas / K_La_CFD   (체적평균 기준 · 같은좌표 프로브 기준 두 벌)
    2) 구간별 레버 (0.02->0.08, 0.08->0.17, 0.02->0.17) 실측 vs CFD, 초과율 eps
    3) 위치 강건성 대조 — 실측 CV 1.44 % (S1·S2·S3) vs CFD 같은 3좌표의 CV
    4) 곡선 모양 — 프로브 곡선의 단일지수 적합도(RMSE/span)

왜 "같은좌표 프로브 기준"을 같이 내나
    실측 K_La 는 프로브 **1점 판독**에서 나온 값이다. 체적평균 CFD 와만 비교하면
    프로브 위치 편향이 kappa 에 통째로 실린다. 두 기준을 나란히 놓아야
    "총량이 다른가" 와 "프로브가 다른 걸 봤는가" 를 분리할 수 있다.

usage
    python3 compare_exp.py
    python3 compare_exp.py --md      # 마크다운 표로 (문서에 붙여넣기용)
"""
import argparse
import csv
import os
import sys

import numpy as np

import constants as K

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def load():
    p = os.path.join(HERE, "kla_cfd.csv")
    if not os.path.exists(p):
        sys.exit("kla_cfd.csv 없음 — python3 run_reaer.py 를 먼저 도십시오.")
    with open(p, encoding="utf-8") as f:
        return {r["run"]: r for r in csv.DictReader(f)}


def probe_table(run, cid, T):
    p = os.path.join(OUT, f"{run}_{cid}_T{T:g}", "probe_fit.csv")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return {r["probe"]: r for r in csv.DictReader(f)}


def lever(a, b):
    return b / a if a else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true", help="마크다운 표 출력")
    a = ap.parse_args()
    D = load()
    md = a.md

    def hr(c="="):
        print(c * 100)

    hr()
    print(" EX2 · 실측 대 CFD 정량비교")
    print(f"   폭기축 {K.PLUME_AXIS} (실측)   격자 {K.GRID}   Q_air {K.QAIR_LPM} L/min (실측)")
    print(f"   유효창 {K.FIT_LO}–{K.FIT_HI} 공통   C(x,0)=0 공통   P {K.PRESSURE_KPA} kPa 공통")
    print("   수온은 런별 실측값 — CFD·실측 양쪽 다 그 온도로, Arrhenius 환산 없음")
    hr()

    # ---------------- 1) 런별 kappa ----------------
    print("\n[1] 런별 K_La 와 kappa   (전부 그 런의 실측 수온 기준, 환산 없음)\n")
    if md:
        print("| 런 | case | z_start | T [°C] | 프로브 | 실측 K_La [1/h] | CFD 체적평균 | "
              "CFD 같은좌표 | κ(체적) | κ(좌표) |")
        print("|---|---|---|---|---|---|---|---|---|---|")
    else:
        print(f"{'런':>4}{'case':>6}{'z':>7}{'T':>7}{'프로브':>12}"
              f"{'실측':>9}{'CFD벌크':>10}{'CFD좌표':>10}{'κ(벌크)':>10}{'κ(좌표)':>10}")
        print("-" * 96)
    for r in K.RUNS:
        d = D.get(r["run"])
        if not d:
            continue
        pn = K.probe_name(r["probe"])
        if md:
            print(f"| {r['run']} | {d['case']} | {r['z_start']:.3f} | {r['T']} | {pn} | "
                  f"{float(d['kla_meas_1h']):.4f} | {float(d['kla_cfd_bulk_1h']):.4f} | "
                  f"{float(d['kla_cfd_probe_1h']):.4f} | {float(d['kappa_bulk']):.4f} | "
                  f"{float(d['kappa_probe'] or 'nan'):.4f} |")
        else:
            print(f"{r['run']:>4}{d['case']:>6}{r['z_start']:>7.3f}{r['T']:>7.2f}{pn:>12}"
                  f"{float(d['kla_meas_1h']):>9.4f}{float(d['kla_cfd_bulk_1h']):>10.4f}"
                  f"{float(d['kla_cfd_probe_1h']):>10.4f}{float(d['kappa_bulk']):>10.4f}"
                  f"{float(d['kappa_probe'] or 'nan'):>10.4f}")

    # z=0.02 는 3런 평균으로 묶는다 (실측 n=3)
    def agg(z, key):
        v = [float(D[r["run"]][key]) for r in K.RUNS
             if r["run"] in D and abs(r["z_start"] - z) < 1e-9]
        return (np.mean(v), np.std(v, ddof=1) if len(v) > 1 else 0.0, len(v)) if v \
            else (float("nan"), 0.0, 0)

    print("\n[2] z 수준별 집계 (z=0.020 은 S1·S2·S3 평균)\n")
    lv = []
    for z in (0.020, 0.080, 0.170):
        m, sd, n = agg(z, "kla_meas_1h")
        cb, cbsd, _ = agg(z, "kla_cfd_bulk_1h")
        cp, cpsd, _ = agg(z, "kla_cfd_probe_1h")
        kb, kbsd, _ = agg(z, "kappa_bulk")
        kp, kpsd, _ = agg(z, "kappa_probe")
        if n == 0:
            continue
        lv.append(dict(z=z, meas=m, meas_sd=sd, n=n, bulk=cb, probe=cp,
                       kb=kb, kb_sd=kbsd, kp=kp, kp_sd=kpsd))
        cvs = f" (CV {100*sd/m:.2f} %)" if n > 1 else ""
        print(f"  z={z:.3f}  n={n}  실측 {m:.4f}{'±%.4f' % sd if n>1 else ''} /h{cvs}")
        print(f"            CFD 벌크 {cb:.4f}  좌표 {cp:.4f}   "
              f"κ(벌크) {kb:.4f}{'±%.4f' % kbsd if n>1 else ''}  "
              f"κ(좌표) {kp:.4f}{'±%.4f' % kpsd if n>1 else ''}")

    # ---------------- 3) 구간별 레버 ----------------
    if len(lv) >= 2:
        print("\n[3] 구간별 레버 — 이 표가 논문의 핵심 결과다")
        print("    레버 = K_La(z_j)/K_La(z_i).  eps = 실측레버/CFD레버 - 1  (양수 = CFD 과대예측)\n")
        if md:
            print("| 구간 | 실측 레버 | CFD 레버(벌크) | eps(벌크) | CFD 레버(좌표) | eps(좌표) |")
            print("|---|---|---|---|---|---|")
        else:
            print(f"{'구간':>16}{'실측':>10}{'CFD벌크':>10}{'eps%':>9}"
                  f"{'CFD좌표':>10}{'eps%':>9}")
            print("-" * 64)
        for i in range(len(lv)):
            for j in range(i + 1, len(lv)):
                A, B = lv[i], lv[j]
                lm = lever(A["meas"], B["meas"])
                lb = lever(A["bulk"], B["bulk"])
                lp = lever(A["probe"], B["probe"])
                eb, ep = 100 * (lm / lb - 1), 100 * (lm / lp - 1)
                lab = f"{A['z']:.3f}→{B['z']:.3f}"
                if md:
                    print(f"| {lab} | {lm:.4f} | {lb:.4f} | **{eb:+.2f} %** | "
                          f"{lp:.4f} | **{ep:+.2f} %** |")
                else:
                    print(f"{lab:>16}{lm:>10.4f}{lb:>10.4f}{eb:>9.2f}"
                          f"{lp:>10.4f}{ep:>9.2f}")

    # ---------------- 4) 위치 강건성 ----------------
    e02 = [r for r in K.RUNS if r["cid"] == "e02" and r["run"] in D]
    if len(e02) >= 2:
        print("\n[4] 위치 강건성 — 실측 CV 1.44 % 의 CFD 대조군 (미결 #10 이 요구하던 값)")
        pt = probe_table("S1", "e02", 24.19)
        keys = [f"{r['run']}_{K.probe_name(r['probe'])}" for r in e02]
        # S1 해에서 세 좌표를 동시에 뽑은 값(같은 유동장·같은 수온) = 순수 위치효과
        same = [float(pt[k]["kla_1h"]) for k in keys if k in pt]
        if len(same) >= 2:
            v = np.array(same)
            print(f"    같은 해(S1, T=24.19) 안에서 세 좌표: "
                  f"{v.mean():.4f} ± {v.std(ddof=1):.4f} /h → **CV {100*v.std(ddof=1)/v.mean():.2f} %**")
            print(f"      → 이것이 순수 위치효과다 (수온·유동장 동일).")
        run3 = np.array([float(D[r["run"]]["kla_cfd_probe_1h"]) for r in e02])
        m3 = np.array([float(D[r["run"]]["kla_meas_1h"]) for r in e02])
        print(f"    런별(수온 다름) CFD 3점: {run3.mean():.4f} ± {run3.std(ddof=1):.4f} /h "
              f"→ CV {100*run3.std(ddof=1)/run3.mean():.2f} %")
        print(f"    실측          3점: {m3.mean():.4f} ± {m3.std(ddof=1):.4f} /h "
              f"→ CV {100*m3.std(ddof=1)/m3.mean():.2f} %")

    # ---------------- 5) 곡선 모양 ----------------
    print("\n[5] 곡선 모양 — 단일지수 적합도 (실측 2구획 응답과 대조)")
    print("    실측 RMSE/span: S1 0.19 % · S2 0.16 % · S3 0.30 % · S4 0.24 % · S5 0.53 %")
    print("    S1~S4 는 2지수로 25~47 % 개선, S5 는 개선 0 % (부호 뒤집힘)\n")
    for r in K.RUNS:
        if r["run"] not in D:
            continue
        pt = probe_table(r["run"], r["cid"], r["T"])
        key = f"{r['run']}_{K.probe_name(r['probe'])}"
        if key not in pt:
            continue
        cs = float(pt[key]["cstar_mgL"])
        rm = float(pt[key]["rmse_mgL"])
        bulk_rm = float(pt["__bulk__"]["rmse_mgL"])
        print(f"  {r['run']}  프로브 RMSE {rm:.3e} mg/L = span의 "
              f"{100*rm/cs*(1/(K.FIT_HI-K.FIT_LO)):.4f} %  |  체적평균 RMSE {bulk_rm:.3e}")
    print("\n    (CFD 는 선형계라 단일지수와 거의 완전일치하는 것이 정상이다. "
          "여기서 RMSE 가 크게 나오면\n     그것 자체가 '프로브가 벌크와 다른 것을 본다'는 "
          "공간구조의 증거다 — 특히 S5.)")

    print()
    hr()
    print(" ⚠ 이 표를 인용할 때 반드시 같이 적을 것")
    print("   · 실측 재현성 CV 는 영구 미측정 — 판정선의 분모가 없다 (대리 3종 병기)")
    print("   · z=0.080·0.170 은 n=1")
    print("   · S5 는 프로브가 폭기원보다 아래인 유일한 런 (z 만 바뀐 게 아니다)")
    print("   · S5 원자료는 화면로그 복원본")
    hr()


if __name__ == "__main__":
    main()
