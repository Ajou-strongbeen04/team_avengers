#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 CFD · 가상 재폭기 배치 실행기 — 실측 5런에 1:1 대응

무엇을 도나
    유동해 3개(e02/e08/e17) 위에서 스칼라만 과도적분한다. 유동은 수온과 무관하므로
    (nu 고정) 3개의 동결 유동장으로 **실측 5런을 전부** 덮는다.

        S1  e02  T=24.19  probe (0.455,0.195,0.105)
        S2  e02  T=23.87  probe (0.015,0.015,0.105)
        S3  e02  T=23.89  probe (0.455,0.015,0.105)
        S4  e08  T=23.84  probe (0.455,0.195,0.105)
        S5  e17  T=23.95  probe (0.455,0.195,0.105)

    각 런마다 그 런의 **실측 수온·실측 기압**으로 C*(T)·k_L(T) 를 다시 잡고,
    alpha_g 는 fp_result.csv 의 그 케이스 자기일관 고정점을 쓴다.
    초기조건은 전부 C(x,0)=0 — 실측의 Na2SO3 탈산소 상태에 대응한다.

usage
    python3 run_reaer.py                 # 5런 전부
    python3 run_reaer.py --runs S4,S5    # 일부만
    python3 run_reaer.py --quick         # 성긴 dt (점검용)
    python3 run_reaer.py --dry           # 명령만 출력
"""
import argparse
import csv
import os
import subprocess
import sys

import constants as K
import meshstats

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SOLVER = os.path.join(HERE, "reaer_solver.py")
OUT = os.path.join(HERE, "out")


def load_alpha():
    """케이스별 alpha_g — fp_result.csv(자기일관 고정점) 우선, 없으면 실측 W 되먹임."""
    p = os.path.join(HERE, "fp_result.csv")
    src = {}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                src[r["case"]] = (float(r["alpha_g_fp"]), "fp_result.csv")
    for c in K.CASES:
        if c["cid"] in src:
            continue
        try:
            r = meshstats.analyze(os.path.join(HERE, c["cid"]))
            src[c["cid"]] = (K.alpha_from_W(r["W"]), "W 되먹임(고정점 미산출)")
        except Exception:                                   # noqa: BLE001
            pass
    return src


def kla_0d(cid, alpha_g, T):
    """0-D 해석 K_La [1/s] — 종료시간 산정용."""
    r = meshstats.analyze(os.path.join(HERE, cid))
    a = 6.0 * alpha_g / K.DB
    lx, ly, lz = r["L"]
    dx, dy, dz = r["d"]
    V = lx * ly * lz
    vp = r["nplume"] * dx * dy * dz
    return (vp / V) * K.kl_bubble() * a + K.kl_surf(T) * (lx * ly) / V, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="all", help="S1,S2,... 또는 all")
    ap.add_argument("--n-tau", type=float, default=5.0,
                    help="적분 종료 = n_tau × tau_0D (기본 5 → 99.3 %% 도달, 평탄부 확보)")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true", help="결과 있어도 재실행")
    a = ap.parse_args()

    picks = [r["run"] for r in K.RUNS] if a.runs == "all" else \
        [s.strip().upper() for s in a.runs.split(",")]
    runs = [r for r in K.RUNS if r["run"] in picks]
    if not runs:
        sys.exit(f"모르는 런: {a.runs}")

    alpha = load_alpha()
    os.makedirs(OUT, exist_ok=True)
    py = sys.executable or "python3"

    print("=" * 100)
    print(f" EX2 CFD · 가상 재폭기   C(x,0)=0 에서 출발   P={K.PRESSURE_KPA} kPa (실측)")
    print(f" 유효창 {K.FIT_LO}–{K.FIT_HI} (실측 fit_kla.py 와 동일)   폭기축 {K.PLUME_AXIS}")
    print("=" * 100)

    rows = []
    for r in runs:
        cid = r["cid"]
        if cid not in alpha:
            print(f"\n[건너뜀] {r['run']}: {cid} 유동해 없음 — bash run.sh 를 먼저.")
            continue
        ag, ag_src = alpha[cid]
        k0, mesh = kla_0d(cid, ag, r["T"])
        tau = 1.0 / k0
        end = max(3600.0, a.n_tau * tau)
        dt_max = max(10.0, end / 1800.0)
        tag = f"{r['run']}_{cid}_T{r['T']:g}"
        fitp = os.path.join(OUT, tag, "probe_fit.csv")

        print(f"\n----- {r['run']}  ({cid}, z={r['z_start']:.3f})  "
              f"T={r['T']} °C  probe {r['probe']} [{K.probe_name(r['probe'])}]")
        print(f"      alpha_g {ag:.4f} ({ag_src})  a {6*ag/K.DB:.0f} /m  "
              f"Su(런) {mesh['Su']:.4f}  W {mesh['W']:.5f}")
        print(f"      C*(B-K) {K.benson_krause(r['T']):.4f} mg/L   "
              f"0-D K_La {k0*3600:.3f} /h  τ {tau/60:.1f} 분 → --end {end:.0f} s")

        cmd = [py, SOLVER, "--case", os.path.join(HERE, cid),
               "--T", f"{r['T']:g}", "--P", f"{K.PRESSURE_KPA:g}",
               "--alpha-g", f"{ag:.5f}", "--end", f"{end:.0f}",
               "--dt-max", f"{dt_max:.1f}", "--probe-set", cid,
               "--tag", tag, "--out", OUT, "--noplot"]
        if a.quick:
            cmd.append("--quick")

        if a.dry:
            print("      $ " + " ".join(cmd))
            continue
        if os.path.exists(fitp) and not a.force:
            print("      결과 있음 → 스킵 (--force 로 재실행)")
        else:
            if subprocess.call(cmd) != 0:
                print(f"      [ERROR] reaer_solver 실패")
                continue

        with open(fitp, encoding="utf-8") as f:
            pf = {x["probe"]: x for x in csv.DictReader(f)}
        key = f"{r['run']}_{K.probe_name(r['probe'])}"
        bulk = float(pf["__bulk__"]["kla_1h"])
        loc = float(pf[key]["kla_1h"]) if key in pf else float("nan")
        print(f"      → CFD K_La  체적평균 {bulk:.4f} /h   "
              f"같은좌표 프로브 {loc:.4f} /h   실측 {r['kla_T_meas']:.4f} /h")
        rows.append(dict(run=r["run"], case=cid, z_start=r["z_start"], T=r["T"],
                         probe=key, alpha_g=f"{ag:.5f}",
                         kla_cfd_bulk_1h=f"{bulk:.4f}",
                         kla_cfd_probe_1h=f"{loc:.4f}",
                         kla_meas_1h=f"{r['kla_T_meas']:.4f}",
                         kappa_bulk=f"{r['kla_T_meas']/bulk:.4f}",
                         kappa_probe=f"{r['kla_T_meas']/loc:.4f}" if loc == loc else ""))

    if a.dry or not rows:
        return

    p = os.path.join(HERE, "kla_cfd.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\n  → kla_cfd.csv ({len(rows)} 행)")
    print(f"  다음:  python3 compare_exp.py")


if __name__ == "__main__":
    main()
