#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 -> kappa 산출 · hold-out 전이 잔차 · 위치 강건성           [2026-08-01]

방법론 §5:  kappa = K_La_eff,meas / K_La_eff,CFD

입력
  1) summary_meas.csv  — fit_kla.py v2 --summary 산출
  2) runs.csv          — 런 조건표 (file, run, z_start, probe, role)
                         role: train | holdout | position
  3) --cfd             — z_start 별 CFD K_La [1/h] 표 (CSV: z_start,kla_cfd_1_h)
                         미지정 시 내장 기본값(EX2_X4 2026-07-30, 3-D)

산출
  · 조건별 kappa
  · 학습셋 kappa_bar +- SD, CV            <- 판정선의 분자
  · 동일조건 반복 CV                       <- 판정선의 분모(잡음 기준선)
  · hold-out 전이 잔차: 재피팅 없이 kappa_bar 를 적용했을 때
        pred = kappa_bar * KLa_CFD(z),  잔차 = (meas - pred)/pred
    -> 이것이 반복 CV 와 같은 자릿수면 "kappa 는 전이된다"
  · 위치 강건성: 같은 z 에서 프로브 위치를 바꿨을 때 kappa 산포가
    반복 CV 이내인가 (방법론 §6.1-3 / 계획서 v2 §7.3)

주의 — 온도  [2026-08-02 기본값 변경]
  런 간 수온이 다르면 KLa 를 그대로 비교하면 안 된다. CFD 는 25 degC 고정이므로
  **기본을 --basis kla20 으로 바꿨다** (양쪽 20 degC 환산, --cfd-T 로 CFD 기준온도 지정).
  구 기본값 raw 는 23.8~24.2 degC 실측을 25 degC CFD 로 그냥 나눠 kappa 가
  약 2 % 낮게 나왔다(부록 D.1 이 명시한 금지사항). raw 는 진단용으로만 남긴다.

사용
  python3 calc_kappa.py summary_meas.csv runs.csv                    # kla20 기본
  python3 calc_kappa.py summary_meas.csv runs.csv --out kappa_결과.csv
"""

import argparse
import csv
import os
import statistics as st
import sys

# ─────────────────────────────────────────────────────────────────────────
# CFD 표 — 2026-08-02 전면 교체 (S1-S4_종합분석_20260802.md §3.1)
#
# 규약 (상수_목록.md §D-1 각주): **절대값은 medium 앵커(m21=2.604 /h),
#                                 상대(레버)는 coarse.**
#         KLa_CFD(z) = 2.604 * KLa_coarse_3D(z) / KLa_coarse_3D(0.02)
#
# coarse 3-D 원값 (EX2_예외검증/EX2_X4/README.md §4.2, 84x37x37):
#   0.02 2.703 | 0.05 2.305 | 0.08 2.030 | 0.11 1.743 | 0.14 1.382 | 0.17 1.051
#
# 구 표의 결함 3건 (전부 이 교체로 해소):
#   · 0.08 = 2.030 은 coarse 원값 그대로였다 → 격자편향 +3.8 % 이중계상
#   · 0.14 = 1.312, 0.17 = 0.948 은 **구 선형모델 예측값**이었다.
#     3-D CFD 는 이미 완료돼 있다(EX2_X4 §4.2) → 실측 3-D 로 교체
#   · 그 결과 hold-out(z=0.17) 분모가 −6.4 % 틀린 채로 판정될 뻔했다
# ─────────────────────────────────────────────────────────────────────────
_CFD_COARSE_3D = {                      # EX2_X4 §4.2, 84x37x37, 25 degC
    0.02: 2.703, 0.05: 2.305, 0.08: 2.030,
    0.11: 1.743, 0.14: 1.382, 0.17: 1.051,
}
_ANCHOR_MEDIUM = 2.604                  # m21, 108x48x48, z=0.02, 25 degC
CFD_DEFAULT = {z: _ANCHOR_MEDIUM * k / _CFD_COARSE_3D[0.02]
               for z, k in _CFD_COARSE_3D.items()}
#  -> 0.02 2.6040 | 0.05 2.2206 | 0.08 1.9557 | 0.11 1.6792 | 0.14 1.3313 | 0.17 1.0124
CFD_PREDICTED = set()            # 전 수준 3-D 실행 완료 (2026-07-30)
THETA = 1.024


def kla20(kla, T_c, theta=THETA):
    return kla * theta ** (20.0 - T_c)


def read_csv_dicts(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f)
                if r and not (list(r.values())[0] or "").startswith("#")]


def interp_cfd(z, table):
    """표에 없는 z 는 이웃 2점 선형보간."""
    if z in table:
        return table[z], False
    ks = sorted(table)
    if z < ks[0] or z > ks[-1]:
        raise ValueError(f"z_start={z} 가 CFD 표 범위 {ks[0]}~{ks[-1]} 밖 — 외삽 불가")
    for a, b in zip(ks, ks[1:]):
        if a <= z <= b:
            w = (z - a) / (b - a)
            return table[a] * (1 - w) + table[b] * w, True
    raise ValueError(z)


def fnum(row, *keys, default=None):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            try:
                return float(row[k])
            except ValueError:
                pass
    if default is None:
        raise KeyError(f"필요한 열이 없음: {keys}")
    return default


def main():
    p = argparse.ArgumentParser(description="EX2 kappa · hold-out 전이 잔차")
    p.add_argument("summary", help="fit_kla.py --summary 산출 CSV")
    p.add_argument("runs", help="런 조건표 CSV (file,run,z_start,probe,role)")
    p.add_argument("--cfd", help="z_start,kla_cfd_1_h CSV (미지정 시 내장 기본값)")
    p.add_argument("--basis", choices=["raw", "kla20"], default="kla20",
                   help="kla20 = 양쪽 20C 환산 (기본, 온도 정합) / "
                        "raw = 실측 원값 대 25C CFD (진단용. 런 수온이 25C 가 아니면 "
                        "kappa 가 약 2 %% 낮게 나온다 — 부록 D.1)")
    p.add_argument("--cfd-T", type=float, default=25.0, help="CFD 기준 수온 [degC]")
    p.add_argument("--cv-floor", type=float, default=3.0,
                   help="판정선에 쓸 CV 하한 [%%] (기본 3.0). 반복이 우연히 "
                        "좁게 나와 판정선이 비현실적으로 조여지는 것을 막는다")
    p.add_argument("--out", help="결과 CSV 경로")
    a = p.parse_args()

    # ── CFD 표
    cfd = dict(CFD_DEFAULT)
    if a.cfd:
        cfd = {}
        for r in read_csv_dicts(a.cfd):
            cfd[float(r["z_start"])] = float(r["kla_cfd_1_h"])

    # ── 실측 요약 (파일명 키)
    meas = {}
    for r in read_csv_dicts(a.summary):
        meas[os.path.basename(r["file"])] = r

    rows = []
    for cond in read_csv_dicts(a.runs):
        fname = os.path.basename(cond["file"])
        if fname not in meas:
            print(f"[skip] {fname}: summary 에 없음")
            continue
        m = meas[fname]
        z = float(cond["z_start"])
        role = (cond.get("role") or "train").strip().lower()
        probe = (cond.get("probe") or "").strip()
        run = (cond.get("run") or fname).strip()

        T = fnum(m, "T_mean_C")
        k_meas_raw = fnum(m, "kla_1_h")
        k_cfd_raw, interp = interp_cfd(z, cfd)

        if a.basis == "kla20":
            k_meas = fnum(m, "kla20_1_h", default=kla20(k_meas_raw, T))
            k_cfd = kla20(k_cfd_raw, a.cfd_T)
        else:
            k_meas, k_cfd = k_meas_raw, k_cfd_raw

        rows.append({
            "run": run, "file": fname, "role": role, "probe": probe,
            "z_start": z, "T_mean_C": T,
            "kla_meas_1_h": k_meas, "kla_cfd_1_h": k_cfd,
            "kappa": k_meas / k_cfd,
            "cstar_source": m.get("cstar_source", ""),
            "t_end_tau": fnum(m, "t_end_tau", default=float("nan")),
            "rmse_mgL": fnum(m, "rmse_mgL", default=float("nan")),
            "cfd_interp": int(interp),
            "cfd_predicted": int(z in CFD_PREDICTED),
        })

    if not rows:
        sys.exit("대조할 런이 없습니다.")

    basis_note = ("실측 원값 대 CFD 25C" if a.basis == "raw"
                  else f"양쪽 20C 환산 (theta={THETA}, CFD 기준 {a.cfd_T}C)")
    print(f"\n{'='*78}\n EX2 kappa 산출   기준: {basis_note}\n{'='*78}")
    print(f"{'run':<8}{'role':<10}{'z':>7}  {'probe':<26}"
          f"{'KLa_meas':>10}{'KLa_CFD':>10}{'kappa':>8}")
    for r in sorted(rows, key=lambda x: (x["role"], x["z_start"], x["run"])):
        flag = "*" if r["cfd_predicted"] else (" i" if r["cfd_interp"] else "")
        print(f"{r['run']:<8}{r['role']:<10}{r['z_start']:>7.3f}  "
              f"{r['probe'][:26]:<26}{r['kla_meas_1_h']:>10.3f}"
              f"{r['kla_cfd_1_h']:>10.3f}{r['kappa']:>8.3f}{flag}")
    if any(r["cfd_predicted"] for r in rows):
        print("  * = CFD 값이 선형모델 예측(실행 대기). 이 런의 kappa 는 잠정.")
    if any(r["cfd_interp"] for r in rows):
        print("  i = CFD 표에 없는 z 를 선형보간.")

    # ── 1) 반복 재현성 CV (동일 z + 동일 probe)
    print(f"\n{'-'*78}\n [1] 동일조건 반복 재현성 — hold-out 판정선의 분모\n{'-'*78}")
    groups = {}
    for r in rows:
        groups.setdefault((r["z_start"], r["probe"]), []).append(r)
    rep_cvs = []
    for (z, pr), g in sorted(groups.items()):
        if len(g) < 2:
            continue
        ks = [x["kla_meas_1_h"] for x in g]
        cv = 100 * st.stdev(ks) / st.mean(ks)
        rep_cvs.append(cv)
        print(f"  z={z:.3f} probe={pr or '-':<22} n={len(g)}  "
              f"KLa {st.mean(ks):.3f} +- {st.stdev(ks):.3f} /h  CV = {cv:.2f} %")
    cv_measured = True
    if rep_cvs:
        cv_obs = max(rep_cvs)
        cv_base = max(cv_obs, a.cv_floor)
        print(f"  -> 관측 CV_rep = {cv_obs:.2f} %  "
              f"(성공기준 <=10 %, 계획서 v2 §8)")
        if cv_base > cv_obs:
            print(f"  -> 판정선에는 하한 {a.cv_floor:.1f} % 를 적용 "
                  f"(반복 n 이 적어 관측 CV 를 그대로 믿을 수 없음)")
        if cv_obs > 10:
            print(f"  [경고] CV {cv_obs:.2f} % > 10 % — 재현성 기준 미달. "
                  f"hold-out 판정 전에 원인부터 볼 것.")
    else:
        cv_base = a.cv_floor
        cv_measured = False
        print(f"  [경고] 동일조건 반복이 없습니다. 판정선에 하한 "
              f"{a.cv_floor:.1f} % 만 적용합니다 — 이것은 측정된 잡음이 아닙니다.")
        print("  (원문) 동일조건 반복이 없습니다. hold-out 잔차를 비교할 "
              "잡음 기준선이 없어 전이성 판정이 불가능합니다.")

    # ── 2) 학습셋 kappa
    print(f"\n{'-'*78}\n [2] 학습셋 kappa\n{'-'*78}")
    train = [r for r in rows if r["role"] == "train"]
    if not train:
        sys.exit("role=train 런이 없습니다.")
    kt = [r["kappa"] for r in train]
    kbar = st.mean(kt)
    ksd = st.stdev(kt) if len(kt) > 1 else 0.0
    print(f"  n={len(kt)}  kappa_bar = {kbar:.4f} +- {ksd:.4f}  "
          f"(CV = {100*ksd/kbar:.2f} %)" if kbar else "")
    zs = sorted({r["z_start"] for r in train})
    print(f"  학습 z 수준: {zs}")
    if len(zs) < 2:
        print("  [경고] 학습 z 가 1수준 — kappa 의 조건 무의존성을 학습셋 안에서 "
              "확인할 수 없습니다.")

    # ── 3) hold-out 전이 잔차
    print(f"\n{'-'*78}\n [3] hold-out 전이 잔차 (재피팅 없음)\n{'-'*78}")
    hold = [r for r in rows if r["role"] == "holdout"]
    if not hold:
        print("  role=holdout 런 없음 — 전이성 검증 미실시.")
    else:
        print(f"{'run':<8}{'z':>7}{'CFD':>9}{'pred':>9}{'meas':>9}"
              f"{'잔차%':>9}{'판정':>10}")
        for r in sorted(hold, key=lambda x: x["z_start"]):
            pred = kbar * r["kla_cfd_1_h"]
            res = 100 * (r["kla_meas_1_h"] - pred) / pred
            if abs(res) <= cv_base:
                verdict = "통과"
            elif abs(res) <= 2 * cv_base:
                verdict = "경계"
            else:
                verdict = "미통과"
            if not cv_measured:
                verdict += "?"
            lev = 100 * r["kla_cfd_1_h"] / cfd[min(cfd)]
            print(f"{r['run']:<8}{r['z_start']:>7.3f}{r['kla_cfd_1_h']:>9.3f}"
                  f"{pred:>9.3f}{r['kla_meas_1_h']:>9.3f}{res:>+9.2f}{verdict:>10}"
                  f"   (레버 {lev:.0f} %)")
        print(f"  판정선: |잔차| <= CV_rep({cv_base:.2f} %) 통과 / "
              f"<= 2xCV 경계 / 초과 미통과")
        if not cv_measured:
            print("  🔴 '?' = **잡음 기준선이 측정되지 않았다.** 위 판정은 "
                  "가정한 하한에 기댄 것이며 증거가 아니다.")
            print("     동일조건 반복 1회(z=0.02 기준위치, 3.3tau, 약 2.5 h)만 "
                  "추가하면 판정이 실측 기반이 된다.")
        print("  ※ 외삽 폭이 잡음의 몇 배인지 함께 보고할 것 — 외삽이 작으면 "
              "잔차가 작아도 '전이된다'가 아니라 '조건이 안 변했다'의 증거다"
              "(계획서 v2 §7.2).")

    # ── 4) 위치 강건성
    print(f"\n{'-'*78}\n [4] 위치 강건성 — kappa 가 기하가 아니라 전달물리의 계수인가\n{'-'*78}")
    pos = [r for r in rows if r["role"] in ("position", "train")]
    byz = {}
    for r in pos:
        byz.setdefault(r["z_start"], []).append(r)
    done = False
    for z, g in sorted(byz.items()):
        probes = {r["probe"] for r in g if r["probe"]}
        if len(probes) < 2:
            continue
        done = True
        # 같은 프로브의 반복은 먼저 평균 — 반복 수가 위치 산포에 섞이지 않게
        byp = {}
        for r in g:
            byp.setdefault(r["probe"], []).append(r)
        ks = [st.mean([x["kappa"] for x in v]) for v in byp.values()]
        cvp = 100 * st.stdev(ks) / st.mean(ks) if len(ks) > 1 else 0.0
        print(f"  z={z:.3f}  프로브 {len(byp)}점  kappa "
              f"{st.mean(ks):.4f} +- {st.stdev(ks) if len(ks)>1 else 0:.4f}  "
              f"CV = {cvp:.2f} %")
        for pr, v in sorted(byp.items()):
            kk = st.mean([x["kappa"] for x in v])
            print(f"      {pr:<28} kappa={kk:.4f} (n={len(v)})  "
                  f"KLa={st.mean([x['kla_meas_1_h'] for x in v]):.3f}")
        if not cv_measured:
            print(f"      -> 참고: 위치 산포 {cvp:.2f} % vs 가정 하한 "
                  f"{cv_base:.2f} % (실측 잡음 기준선 없음)")
        elif cvp <= cv_base:
            print(f"      -> 통과: 위치 산포({cvp:.2f} %)가 반복 산포"
                  f"({cv_base:.2f} %) 이내. kappa 는 위치 무의존.")
        else:
            print(f"      -> 미통과: 위치 산포({cvp:.2f} %) > 반복 산포"
                  f"({cv_base:.2f} %). 위치효과를 불확도에 합산할 것"
                  f"(방법론 §6.1 말미 (b)).")
            print(f"      ※ t_mix 판정이 이미 불성립이므로(2026-08-01) 이 결과는 "
                  f"예상 범위다. 산포 자체를 결과로 보고할 것.")
    if not done:
        print("  같은 z 에서 2점 이상 잰 프로브 위치가 없습니다 — 강건성 축 미실시.")

    # ── 5) dC*
    print(f"\n{'-'*78}\n [5] C* 대조\n{'-'*78}")
    for r in sorted(rows, key=lambda x: x["run"]):
        m = meas[r["file"]]
        print(f"  {r['run']:<8} C*={fnum(m,'cstar_mgL'):.3f} "
              f"({m.get('cstar_source','')}) "
              f"B-K={fnum(m,'cstar_bk_mgL'):.3f}  "
              f"dC*={fnum(m,'dcstar_mgL'):+.3f} mg/L")
    print("  ※ 기준압을 통일했는지 확인할 것 — 서로 다른 기준압을 빼면 "
          "단위 규약 차이가 dC* 에 섞인다(파일럿_결과 §5.1).")

    if a.out:
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n저장: {a.out}")


if __name__ == "__main__":
    main()
