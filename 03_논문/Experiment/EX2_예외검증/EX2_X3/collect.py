#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2_X3 · 집계 — 수위 레버 표 + kappa 위치 무의존성 CV

K_La 는 reaer_solver.py 가 3-D 적분으로 내는 값과 **같은 해석식**으로 계산한다
(reaer_solver.py 의 "해석예측" 줄, pos1_상수확정_T20.md §4 와 동일):

    K_La = (V_plume/V) * k_L,b * a  +  k_L,surf * (Lx*Ly)/V
    a = 6*alpha_g/d_b ,  k_L,b = Sh_b*D/d_b ,  Sh_b = 2 + 0.6 Re_b^1/2 Sc^1/3

3-D 확인이 필요하면 개별 케이스에 대해:
    python3 ../EX2/CFD/reaer/reaer_solver.py --case d15 --T 25 --alpha-g <alpha_g>

usage:
    python3 collect.py            # 전체 집계 → results.csv
    python3 collect.py --T 20     # 수온 바꿔서
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


# ---- 물성 (상수_목록 A·C군 / reaer_solver.py 와 동일) ----------------------
DMOL_20 = 2.0e-9
NU_20 = 1.0e-6
KL_SURF_20 = 2.3e-5
THETA_KL = 1.024
DB = 0.5e-3
USLIP = 0.0578          # 25 C (reaer_solver 기본 0.055 는 20 C 값)
G = 9.81
Z_START = 0.02

D_CASES = [("d21", os.path.join(HERE, "..", "EX2_X", "case_su177"))] + \
          [(c, os.path.join(HERE, c)) for c in ("d18", "d15", "d12", "d09")]
# W 분포를 span 하는 3점 (최소 pos15 · 중앙 pos4 · 최대 pos1)
P_CASES = [(c, os.path.join(HERE, c)) for c in ("p15", "p04", "p01")]
P_REF = [(f"pos{n}", os.path.join(HERE, "..", "EX2", "CFD", "flow", f"pos{n}"))
         for n in (15, 4, 1)]
M_CASE = ("m21", os.path.join(HERE, "m21"))


QAIR = 1.2 / 1000 / 60
PLUME_R = 0.01
UGS = QAIR / (np.pi * PLUME_R ** 2)      # 0.0637 m/s — 수위·위치 무관 고정


def kla_of(r, T):
    """해석 K_La [1/h] 와 플룸:수면 기여비.

    alpha_g 는 입력 Su/g 가 아니라 **실측 W 되먹임** U_gs/(W+U_slip) 을 쓴다.
    이것이 물리 폐합이고, 위치별 K_La 산포가 여기서 나온다
    (`../EX2/어항실험/16위치_잔차분석.md`: W 가 커지면 holdup 이 줄어드는 자기조절).
    입력 Su 로 계산하면 같은 Su 를 쓴 케이스들이 전부 같은 K_La 가 되어
    산포가 0 으로 사라진다.
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

    rows = []

    # ---------------- 수위 레버 ----------------
    print("\n" + "=" * 100)
    print(f" [1] 수위 레버 — EX2 hold-out 축   (T = {a.T:g} °C)")
    print("=" * 100)
    ds = load(D_CASES)
    if ds:
        hdr = (f"{'case':6}{'d[m]':>7}{'H_p':>7}{'V[L]':>7}{'셀수':>9}"
               f"{'Su':>8}{'α_g':>8}{'a[1/m]':>8}{'W':>8}{'Qp':>7}"
               f"{'K_La[1/h]':>11}{'τ[분]':>8}{'플룸%':>7}{'기준비':>8}")
        print("\n" + hdr)
        print("-" * len(hdr))
        base = None
        for r in sorted(ds, key=lambda x: -x["L"][2]):
            kla, frac, V, ag, aa = kla_of(r, a.T)
            base = base or kla
            d = r["L"][2]
            print(f"{r['cid']:6}{d:>7.2f}{d-Z_START:>7.2f}{V:>7.1f}{r['N']:>9,}"
                  f"{r['Su']:>8.4g}{ag:>8.4f}{aa:>8.0f}{r['W']:>8.4f}"
                  f"{r['Qp']*6e4:>7.2f}{kla:>11.3f}{60/kla:>8.1f}"
                  f"{frac:>7.0f}{100*kla/base:>7.0f} %")
            rows.append(dict(group="D", case=r["cid"], d=f"{d:.3f}",
                             cells=r["N"], Su=f"{r['Su']:.4f}",
                             alpha_g=f"{ag:.5f}", a=f"{aa:.0f}",
                             W=f"{r['W']:.5f}", Qp_Lmin=f"{r['Qp']*6e4:.3f}",
                             meanU=f"{r['meanU']:.5f}",
                             KLa_1h=f"{kla:.4f}", tau_min=f"{60/kla:.2f}",
                             plume_pct=f"{frac:.1f}"))
        print("\n  레버 = 최저수위 K_La / 기준 K_La. §1.2 표(해석추정)와 대조할 것.")

    # ---------------- 위치 무의존성 ----------------
    print("\n" + "=" * 100)
    print(" [2] κ 위치 무의존성 — 방법론 §6.2 '2–3위치에서 κ 일치'")
    print("=" * 100)

    def cv_block(title, items, T):
        got = load(items)
        if len(got) < 2:
            print(f"\n  {title}: 케이스 부족 → 생략")
            return None
        klas = []
        print(f"\n  {title}")
        print(f"    {'case':8}{'플룸축':>18}{'Su':>8}{'W':>9}{'Qp':>8}{'K_La[1/h]':>11}")
        for r in got:
            kla, _, _, _, _ = kla_of(r, T)
            klas.append(kla)
            ax = f"({r['axis'][0]}, {r['axis'][1]})"
            print(f"    {r['cid']:8}{ax:>18}{r['Su']:>8.4g}{r['W']:>9.4f}"
                  f"{r['Qp']*6e4:>8.2f}{kla:>11.3f}")
            rows.append(dict(group=title[:6], case=r["cid"], d="0.210",
                             cells=r["N"], Su=f"{r['Su']:.4f}",
                             alpha_g=f"{r['Su']/G:.5f}", a="",
                             W=f"{r['W']:.5f}", Qp_Lmin=f"{r['Qp']*6e4:.3f}",
                             meanU=f"{r['meanU']:.5f}", KLa_1h=f"{kla:.4f}",
                             tau_min=f"{60/kla:.2f}", plume_pct=""))
        k = np.array(klas)
        cv = 100 * k.std(ddof=1) / k.mean()
        print(f"    → K_La = {k.mean():.3f} ± {k.std(ddof=1):.3f} /h,"
              f"  범위 {k.min():.2f}–{k.max():.2f},  **CV {cv:.1f} %**")
        return cv

    cv_new = cv_block("신규 coarse · Su=1.773", P_CASES, a.T)
    cv_ref = cv_block("기존 medium · Su=2.86 (동일 3위치, 디스크 상주)", P_REF, a.T)

    if cv_new is not None and cv_ref is not None:
        print(f"\n  판정: 위치 산포가 운전점에 보존되는가")
        print(f"    Su=2.86  CV {cv_ref:.1f} %   ↔   Su=1.773  CV {cv_new:.1f} %"
              f"   차이 {abs(cv_new-cv_ref):.1f} %p")
        ok = abs(cv_new - cv_ref) <= 2.0
        print(f"    → {'✅ 보존' if ok else '❌ 미보존'}  (허용 2 %p)")
        print("      보존이면 16위치 medium 스윕(33 h, Su=2.86)의 **상대 산포 결론**을"
              "\n      새 운전점에서도 인용할 수 있다 → 16위치 재실행 불필요.")

    # ---------------- medium 앵커 ----------------
    print("\n" + "=" * 100)
    print(" [3] medium 앵커 — 절대 κ 와 coarse 편향의 Su 불변성")
    print("=" * 100)
    anchor = load([M_CASE])
    c177 = load([("case_su177", os.path.join(HERE, "..", "EX2_X",
                                             "case_su177"))])
    ref_c = load([("coarse@2.86", os.path.join(HERE, "..", "EX2", "CFD",
                                               "study", "coarse_0.02"))])
    ref_m = load([("medium@2.86", os.path.join(HERE, "..", "EX2", "CFD",
                                               "study", "medium_0.02"))])
    if anchor and c177 and ref_c and ref_m:
        b177 = 100 * (c177[0]["W"] / anchor[0]["W"] - 1)
        b286 = 100 * (ref_c[0]["W"] / ref_m[0]["W"] - 1)
        print(f"\n    coarse/medium W 편향 @ Su=2.86  : {b286:+.2f} %")
        print(f"    coarse/medium W 편향 @ Su=1.773 : {b177:+.2f} %")
        ok = abs(b177 - b286) <= 1.0
        print(f"    → {'✅ Su 불변' if ok else '❌ Su 의존'}  (차이 "
              f"{abs(b177-b286):.2f} %p, 허용 1 %p)")
        print("      불변이면 coarse 로 돌린 D·P군에 단일 보정계수를 적용해"
              "\n      medium 급 절대값을 복원할 수 있다.")
        kla, _, _, ag, aa = kla_of(anchor[0], a.T)
        print(f"\n    medium 앵커 절대값: W {anchor[0]['W']:.4f}  "
              f"α_g {ag:.4f}  a {aa:.0f} /m  K_La {kla:.3f} /h  τ {60/kla:.1f} 분")

    if rows:
        p = os.path.join(HERE, "results.csv")
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n  → results.csv 기록 ({len(rows)} 행)")


if __name__ == "__main__":
    main()
