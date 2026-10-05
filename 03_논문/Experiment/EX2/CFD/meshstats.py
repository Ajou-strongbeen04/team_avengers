#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2_X · Su 섭동 판정 — baseline(Su=2.86) vs 시험케이스(Su=1.684)

usage:
    python3 compare.py <baselineDir> <testDir> [testDir2 ...] [--time 200]

전제
    - 균일격자(simpleGrading 1 1 1) → 산술평균 = 체적가중평균
    - 셀 순서 i(x) fastest, then j(y), then k(z)
    - 비교 케이스들은 baseline 과 **동일 격자·동일 플룸 위치**여야 한다
      (그래야 셀 대 셀 IoU 가 정의된다). 다르면 IoU 는 건너뛴다.

판정 두 가지
    ① W 스케일링   : W ∝ Su^(1/3) 이 성립하는가        (tol 3 %)
    ② 공간구조 불변 : 정체역 위치가 Su 에 안 움직이는가  (tol 1셀)

②는 절대마스크와 정규화마스크를 **둘 다** 본다.
    - 절대마스크  |U| < 1 cm/s        : 크기효과 + 구조효과가 섞여 있음
    - 정규화마스크 하위 p % 셀 (p = baseline 의 절대마스크 분율)
      → 전체 유속이 느려지는 효과를 제거하고 **구조만** 본다. 이쪽이 본 판정이다.
"""
import gzip
import os
import re
import sys

import numpy as np

# Windows 콘솔(cp949)에서 ✅·— 같은 문자 출력 시 UnicodeEncodeError 로 죽는 것 방지.
# 2026-07-29: MSYS 창은 UTF-8 인데 python 기본 stdout 이 cp949 라 한글도 깨졌다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ---- 도메인 (상수_목록 E군) ------------------------------------------------
LX, LY, LZ = 0.47, 0.21, 0.21
PLUME_R = 0.01
PLUME_Z = (0.02, 0.21)
SCT = 0.7
G = 9.81

# ---- 폭기 실측 (2026-07-28: 500 mL / 25 s, 3회 평균) -----------------------
QAIR = 1.2 / 1000 / 60          # m3/s  = 1.2 L/min
USLIP = 0.0578                  # m/s   0.5 mm 기포 종단속도 @25 C
DB = 0.5e-3                     # m

TOL_W = 0.03                    # W 스케일링 허용오차
TOL_CELL = 1.0                  # 정체역 centroid 허용 이동 [셀]
TOL_IOU = 0.80                  # 정규화마스크 IoU 하한


# ---------------------------------------------------------------- readers --
def dims(case):
    t = open(f"{case}/system/blockMeshDict", errors="ignore").read()
    return tuple(int(re.search(rf"^{k}\s+(\d+)\s*;", t, re.M).group(1))
                 for k in ("nx", "ny", "nz"))


def domain(case):
    """blockMeshDict 의 Lx/Ly/Lz. 수위 가변 케이스(EX2_X3) 대응 — 없으면 기본값."""
    t = open(f"{case}/system/blockMeshDict", errors="ignore").read()
    out = []
    for k, dflt in (("Lx", LX), ("Ly", LY), ("Lz", LZ)):
        m = re.search(rf"^{k}\s+([\d.eE+-]+)\s*;", t, re.M)
        out.append(float(m.group(1)) if m else dflt)
    return tuple(out)


def plume_z(case):
    """topoSetDict 플룸 원기둥의 z 구간 (z_start, z_end)."""
    t = open(f"{case}/system/topoSetDict", errors="ignore").read()
    m1 = re.search(r"point1\s*\([^)]*?([\d.eE+-]+)\s*\)", t)
    m2 = re.search(r"point2\s*\([^)]*?([\d.eE+-]+)\s*\)", t)
    if not (m1 and m2):
        return PLUME_Z
    return float(m1.group(1)), float(m2.group(1))


def plume_r(case):
    t = open(f"{case}/system/topoSetDict", errors="ignore").read()
    m = re.search(r"radius\s+([\d.eE+-]+)\s*;", t)
    return float(m.group(1)) if m else PLUME_R


def read_field(case, time, name, n):
    for p in (f"{case}/{time}/{name}", f"{case}/{time}/{name}.gz"):
        if os.path.exists(p):
            op = gzip.open(p, "rt", errors="ignore") if p.endswith(".gz") \
                else open(p, errors="ignore")
            txt = op.read()
            break
    else:
        raise FileNotFoundError(f"{case}/{time}/{name}[.gz] 없음")
    m = re.search(r"internalField\s+nonuniform\s+List<(vector|scalar)>\s*\n?\s*(\d+)\s*\(", txt)
    if not m:
        raise RuntimeError(f"{name}: uniform field — 시간평균장이 아님")
    kind, nn = m.group(1), int(m.group(2))
    body = txt[m.end():]
    end = body.find("\n)")
    if kind == "vector":
        a = np.array(re.findall(
            r"\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)", body[:end]), dtype=float)
    else:
        a = np.fromstring(body[:end].replace("\n", " "), sep=" ")
    if len(a) != nn or nn != n:
        raise RuntimeError(f"{name}: 파싱 {len(a)} / 헤더 {nn} / 격자 {n} 불일치")
    return a


def read_field_any(case, time, names, n):
    """names 를 순서대로 시도. 정상해(simpleFoam)는 UMean 이 없고 U 가 곧 평균장이다."""
    last = None
    for nm in names:
        try:
            return read_field(case, time, nm, n), nm
        except FileNotFoundError as e:
            last = e
    raise last


def plume_axis(case):
    t = open(f"{case}/system/topoSetDict", errors="ignore").read()
    m = re.search(r"point1\s*\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)", t)
    return float(m.group(1)), float(m.group(2))


def su_of(case):
    t = open(f"{case}/system/fvOptions", errors="ignore").read()
    m = re.search(r"U\s+\(\(\s*[-\d.eE+]+\s+[-\d.eE+]+\s+([-\d.eE+]+)\s*\)", t)
    return float(m.group(1))


def application_of(case):
    t = open(f"{case}/system/controlDict", errors="ignore").read()
    m = re.search(r"^application\s+(\w+)\s*;", t, re.M)
    return m.group(1) if m else "?"


def nu_of(case):
    t = open(f"{case}/constant/transportProperties", errors="ignore").read()
    m = re.search(r"^nu\s+\[[^\]]*\]\s+([-\d.eE+]+)\s*;", t, re.M)
    return float(m.group(1))


def latest_time(case):
    ts = [d for d in os.listdir(case)
          if re.fullmatch(r"\d+(\.\d+)?", d) and d != "0"]
    return max(ts, key=float) if ts else None


# ------------------------------------------------------------------- QoI ---
def analyze(case, time=None):
    nx, ny, nz = dims(case)
    N = nx * ny * nz
    time = time or latest_time(case)
    if time is None:
        raise RuntimeError(f"{case}: 시간디렉터리 없음 (아직 안 돌았거나 reconstructPar 미실행)")
    U, usrc = read_field_any(case, time, ("UMean", "U"), N)
    nut, _ = read_field_any(case, time, ("nutMean", "nut"), N)

    lx, ly, lz = domain(case)
    dx, dy, dz = lx / nx, ly / ny, lz / nz
    i = np.arange(N)
    xc = (i % nx + .5) * dx
    yc = ((i // nx) % ny + .5) * dy
    zc = (i // (nx * ny) + .5) * dz

    px, py = plume_axis(case)
    pr = plume_r(case)
    pz = plume_z(case)
    mag = np.linalg.norm(U, axis=1)
    inpl = (((xc - px) ** 2 + (yc - py) ** 2) <= pr ** 2) \
        & (zc >= pz[0]) & (zc <= pz[1])
    zmid = .5 * (pz[0] + pz[1])
    sel = inpl & (np.abs(zc - zmid) < dz / 2)

    return dict(
        name=os.path.basename(os.path.abspath(case)), case=case, time=time,
        nx=nx, ny=ny, nz=nz, N=N, d=(dx, dy, dz), xyz=(xc, yc, zc),
        L=(lx, ly, lz), pz=pz, pr=pr, V=lx * ly * lz,
        Su=su_of(case), nu=nu_of(case), axis=(px, py), src=usrc,
        app=application_of(case),
        mag=mag, W=float(U[inpl, 2].mean()),
        Qp=float((U[sel, 2] * dx * dy).sum()),
        meanU=float(mag.mean()), maxU=float(mag.max()),
        nut=float(nut.mean()), Deff=2.0e-9 + float(nut.mean()) / SCT,
        nplume=int(inpl.sum()),
    )


def centroid(r, mask):
    xc, yc, zc = r["xyz"]
    if not mask.any():
        return (np.nan,) * 3
    return float(xc[mask].mean()), float(yc[mask].mean()), float(zc[mask].mean())


def fixed_point(W_ref, Su_ref, n=1/3.0):
    """Q_air 실측 기준 자기일관 고정점 (alpha_g, Su, W)."""
    Ugs = QAIR / (np.pi * PLUME_R ** 2)
    W = W_ref
    for _ in range(200):
        ag = Ugs / (W + USLIP)
        W = W_ref * (ag * G / Su_ref) ** n
    return ag, ag * G, W, Ugs


# ------------------------------------------------------------------ main ---
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    time = None
    for a in sys.argv[1:]:
        if a.startswith("--time"):
            time = a.split("=")[-1] if "=" in a else None
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    base = analyze(args[0], time)
    tests = [analyze(a, time) for a in args[1:]]

    print("\n" + "=" * 78)
    print(" EX2_X · Su 섭동 판정   (Q_air 실측 1.2 L/min · T = 25 °C)")
    print("=" * 78)

    hdr = (f"{'case':18}{'solver':>12}{'field':>7}{'Su':>7}{'nu':>10}{'t':>6}"
           f"{'mean|U|':>9}{'max|U|':>8}{'W':>8}{'Qp[L/m]':>9}{'nu_t':>10}{'stag%':>7}")
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in [base] + tests:
        print(f"{r['name']:18}{r['app']:>12}{r['src']:>7}"
              f"{r['Su']:7.3f}{r['nu']:10.3e}{r['time']:>6}"
              f"{r['meanU']:9.5f}{r['maxU']:8.4f}{r['W']:8.4f}"
              f"{r['Qp']*6e4:9.2f}{r['nut']:10.3e}"
              f"{100*(r['mag']<0.01).mean():7.2f}")

    # 정상해(U)와 과도평균(UMean)을 섞어 비교하면 그게 곧 판정 대상이다 - 명시만 한다.
    if len({r["src"] for r in [base] + tests}) > 1:
        print("\n  [note] 평균장(UMean)과 정상해(U)를 섞어 비교 중 - "
              "이 조합의 차이가 곧 '정상 근사' 오차다(EX2_X2).")

    # ---- 멱법칙 지수 실측 (Su 가 서로 다른 점이 2개 이상일 때) --------------
    pts = [(r["Su"], r["W"], r["name"]) for r in [base] + tests]
    pairs = [(a, b) for i, a in enumerate(pts) for b in pts[i + 1:]
             if abs(a[0] - b[0]) > 1e-9]
    if pairs:
        print("\n" + "-" * 78)
        print(" 멱법칙 지수 n  (W ∝ Su^n, 쌍별 실측)")
        print("-" * 78)
        # 쌍별 n 은 Su 간격이 좁으면 조건수가 폭발한다.
        #   Δn = δ(lnW) / ln(Su_b/Su_a)  →  간격 5 %(ln비 0.05)면 W 오차 0.3 %가 Δn 0.06
        # 따라서 쌍별 산포로 "지수 안정성"을 재는 것은 잘못이다(2026-07-29 su177 에서 확인).
        # 판정은 **전체 점 log-log 최소제곱 + 잔차**로 한다.
        ns, wide = [], []
        for a, b in pairs:
            L = abs(np.log(b[0] / a[0]))
            n = np.log(b[1] / a[1]) / np.log(b[0] / a[0])
            ns.append(n)
            cond = 0.003 / L          # W 오차 0.3 % 당 Δn
            tag = "" if L >= 0.2 else f"  ⚠ 단폭({L:.3f}) — W 0.3%당 Δn={cond:.3f}"
            if L >= 0.2:
                wide.append(n)
            print(f"    {a[2]:>14} ↔ {b[2]:<14}  Su {a[0]:.3f}→{b[0]:.3f}   n = {n:.4f}{tag}")

        if len(pts) > 2:
            su = np.array([p[0] for p in pts])
            w = np.array([p[1] for p in pts])
            A = np.vstack([np.log(su), np.ones(len(su))]).T
            (nf, cf) = np.linalg.lstsq(A, np.log(w), rcond=None)[0]
            resid = w / (np.exp(cf) * su ** nf) - 1
            ok_n = np.max(np.abs(resid)) <= 0.01
            print(f"\n    전체 {len(pts)}점 log-log 최소제곱: n = {nf:.4f}")
            print("      점별 잔차 " + "  ".join(
                f"{p[2]}:{100*r:+.2f}%" for p, r in zip(pts, resid)))
            print(f"      최대 |잔차| = {100*np.max(np.abs(resid)):.2f} %  → "
                  f"{'✅ 단일 멱법칙으로 설명됨' if ok_n else '❌ 단일 멱법칙 아님'}  (허용 1 %)")

        n_use = float(np.mean(wide)) if wide else float(np.mean(ns))
        ag, su, w, ugs = fixed_point(base["W"], base["Su"], n_use)
        print(f"\n    실측 n = {n_use:.4f} 로 다시 푼 자기일관 고정점")
        print(f"      α_g = {ag:.5f}   Su = {su:.3f}   W_pred = {w:.4f} m/s"
              f"   a = 6α_g/d_b = {6*ag/DB:.0f} /m")

    # baseline 정체역 분율 → 정규화마스크 기준 p
    p_base = float((base["mag"] < 0.01).mean())
    m_abs_b = base["mag"] < 0.01
    thr_b = np.quantile(base["mag"], p_base)
    m_nrm_b = base["mag"] <= thr_b
    cb_abs = centroid(base, m_abs_b)
    cb_nrm = centroid(base, m_nrm_b)

    for r in tests:
        print("\n" + "=" * 78)
        print(f" 판정 : {r['name']}   (baseline = {base['name']})")
        print("=" * 78)

        # --- ① W 스케일링 ---
        W_pred = base["W"] * (r["Su"] / base["Su"]) ** (1 / 3.0)
        err = (r["W"] - W_pred) / W_pred
        ok1 = abs(err) <= TOL_W
        print(f"\n[①] W ∝ Su^(1/3)")
        print(f"    baseline : Su = {base['Su']:.3f} → W = {base['W']:.4f} m/s")
        print(f"    예측     : Su = {r['Su']:.3f} → W = {W_pred:.4f} m/s")
        print(f"    실측     :               W = {r['W']:.4f} m/s   → 오차 {100*err:+.2f} %")
        print(f"    → {'✅ 합격' if ok1 else '❌ 불합격'} (허용 ±{100*TOL_W:.0f} %)")

        # --- alpha_g 자기일관 ---
        Ugs = QAIR / (np.pi * PLUME_R ** 2)
        ag_sc = Ugs / (r["W"] + USLIP)
        ag_in = r["Su"] / G
        ag_fp, su_fp, w_fp, _ = fixed_point(base["W"], base["Su"])
        print(f"\n    [α_g 자기일관]  U_gs = {Ugs:.4f} m/s")
        print(f"      입력 α_g          = {ag_in:.4f}  (a = {6*ag_in/DB:.0f} /m)")
        res = (ag_sc - ag_in) / ag_in
        print(f"      실측 W 되먹임 α_g = {ag_sc:.4f}  (a = {6*ag_sc/DB:.0f} /m)"
              f"   → 잔차 {100*res:+.1f} %"
              f"   {'✅ 자기일관' if abs(res) <= 0.03 else '❌ 미수렴(재반복 필요)'}")
        print(f"      이 격자 기준 고정점 = {ag_fp:.4f} (Su {su_fp:.3f}, W {w_fp:.4f})")

        # --- ② 공간구조 ---
        if (r["nx"], r["ny"], r["nz"]) != (base["nx"], base["ny"], base["nz"]) \
                or r["axis"] != base["axis"]:
            print("\n[②] 격자/플룸위치 불일치 → 셀 대 셀 비교 건너뜀")
            continue

        dx, dy, dz = base["d"]
        m_abs_t = r["mag"] < 0.01
        thr_t = np.quantile(r["mag"], p_base)
        m_nrm_t = r["mag"] <= thr_t

        def iou(a, b):
            u = (a | b).sum()
            return float((a & b).sum() / u) if u else float("nan")

        print(f"\n[②] 정체역 공간구조  (baseline 분율 p = {100*p_base:.2f} %)")
        for tag, mb, mt, thr in (("절대  |U|<1cm/s", m_abs_b, m_abs_t, 0.01),
                                 ("정규화 하위 p%", m_nrm_b, m_nrm_t, thr_t)):
            cb = centroid(base, mb)
            ct = centroid(r, mt)
            shift = np.array(ct) - np.array(cb)
            ncell = shift / np.array([dx, dy, dz])
            print(f"\n    · {tag}   (임계 {thr*100:.3f} cm/s)")
            print(f"      분율   base {100*mb.mean():6.2f} %   test {100*mt.mean():6.2f} %")
            print(f"      centroid base ({cb[0]:.3f}, {cb[1]:.3f}, {cb[2]:.3f})"
                  f"  test ({ct[0]:.3f}, {ct[1]:.3f}, {ct[2]:.3f})")
            print(f"      이동   ({1000*shift[0]:+.1f}, {1000*shift[1]:+.1f}, "
                  f"{1000*shift[2]:+.1f}) mm = ({ncell[0]:+.2f}, {ncell[1]:+.2f}, "
                  f"{ncell[2]:+.2f}) 셀")
            print(f"      IoU    {iou(mb, mt):.3f}")

        shift_n = np.abs((np.array(centroid(r, m_nrm_t)) - np.array(cb_nrm))
                         / np.array([dx, dy, dz]))
        iou_n = iou(m_nrm_b, m_nrm_t)
        ok2 = (shift_n.max() <= TOL_CELL) and (iou_n >= TOL_IOU)
        print(f"\n    → {'✅ 합격' if ok2 else '❌ 불합격'}  "
              f"(정규화마스크 centroid 최대이동 {shift_n.max():.2f} 셀 ≤ {TOL_CELL:.0f}, "
              f"IoU {iou_n:.3f} ≥ {TOL_IOU:.2f})")

        # --- 종합 ---
        print("\n" + "-" * 78)
        if ok1 and ok2:
            print("  ✅ 종합 합격 — 부력측 미보정 면제 성립.")
            print("     16위치 · EX3 253케이스 유동장 **유지**.")
            print(f"     전달측만 교체: a = 6·α_g/d_b → {6*ag_fp/DB:.0f} /m (α_g = {ag_fp:.4f})")
        else:
            print("  ❌ 종합 불합격 — 부력측 미보정 면제 불성립.")
            print("     16위치 coarse 재실행(≈10.9 h) + EX3 253케이스 재생성 필요.")
            if not ok1:
                print("     · Su^(1/3) 멱법칙 자체가 안 맞음 → 고정점 반복의 근거 재검토")
            if not ok2:
                print("     · 정체역이 Su 에 따라 이동 → A층 ROM 학습데이터 무효화")
        print("-" * 78 + "\n")


if __name__ == "__main__":
    main()
