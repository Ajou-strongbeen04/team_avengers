#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 · CFD 가상 재폭기 (virtual reaeration) — 동결 유동장 위 과도 DO 적분

  목적: 실측 재폭기 시험(`../../EX2_방법론.md` §5)과 **같은 프로토콜**로
        CFD 안에서 C(x,0)=0 → 폭기 ON → 벌크 DO 상승곡선을 만들고,
        같은 단일지수 피팅으로 K_La_eff,CFD · C*_CFD 를 뽑는다.
        실측/CFD 비  κ = K_La_meas / K_La_CFD.

  지배식 (시간평균 유동장 U~, nu_t 는 **얼려 재사용**, 스칼라만 과도):

      dC/dt + div(U~ C) = div(D_eff grad C) + S_plume + S_surf
      D_eff  = D_mol + nu_t / Sc_t
      S_plume= k_L,b * a * (C* - C)      (플룸 셀존 체적소스, a = 6 alpha_g / d_b)
      S_surf : top 면 Robin  -D_eff dC/dn = k_L(C* - C)   (자유수면 재폭기)
      바닥/유리벽 : 무플럭스 (SOD·생물·국소싱크 전부 없음 — 현행 방법론)

  이산화: 균일 정렬격자 108x48x48 유한체적, 이송 1차 풍상, 확산 중심차분,
          연속방정식 보정(보간 div 오차 제거), 시간 backward Euler(무조건 안정),
          단계별 고정 dt (dt 바뀔 때만 ILU 재분해) + BiCGStab/ILU.

  ★ CFD 개정 (2026-08-02) — 모든 계수·좌표를 **어항 실측 기준**으로 바꿨다.
      · alpha_g 기본값 0.29 (Q_air=2 L/min 전제) **삭제** → --alpha-g 필수 인자.
        fp_result.csv 의 케이스별 자기일관 고정점을 넣는다.
      · T 기본 20 → 23.95 °C, P 기본 101.325 → 101.0 kPa (본시험 실측).
      · 프로브 좌표를 **실측이 실제로 꽂았던 3점**으로 교체 (constants.py).
      · 프로브별 국소곡선을 체적평균과 같은 유효창으로 **각각 피팅** →
        실측(1점 판독)과 진짜 1:1 대조가 되는 K_La 를 준다.
      구 버전은 _archive/EX2_CFD_구전제_alphag029/reaer/ 에 원형 보존.

  사용:
      python3 run_reaer.py                     # ← 권장. 5런 전부 자동
      python3 reaer_solver.py --case e02 --alpha-g 0.1785 --T 24.19 --end 9000
      python3 reaer_solver.py --case e17 --alpha-g 0.2436 --T 23.95 --quick

  출력 (out/<tag>/):
      bulk_C_t.csv   t[s], Cbar[mg/L], C_plume, C_min, C_max, 프로브 C(t)
      fit.txt        피팅 결과 + 프로브별 K_La + 해석 예측 대조 + 질량수지
      probe_fit.csv  프로브별 K_La·C*·RMSE (기계 판독용 — compare_exp.py 가 읽는다)
      C_final.npy    최종 3D 필드 (NZ,NY,NX)
      curve.png / slices.png (matplotlib 있으면)

  근거: ./constants.py (단일 상수원) · ../../CFD_method.md (방정식·BC 진실원)
        ../어항실험/S1-S4_종합분석_20260802.md (실측 좌표·수온·K_La)
"""

import argparse
import gzip
import os
import re
import sys
import time

import numpy as np

try:
    from scipy.sparse import csr_matrix, identity
    from scipy.sparse.linalg import bicgstab, spilu, LinearOperator
    from scipy.optimize import curve_fit
except ImportError:
    sys.exit("scipy 필요:  pip install scipy   (Windows: py -m pip install scipy)")

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ 격자/도메인
#  기본값 = EX2 16위치 스윕(medium 108x48x48, 수조 47x21x21, V=20.7 L).
#  2026-07-29: coarse 격자와 수위 가변 케이스(EX2_X3)를 위해
#  케이스의 system/blockMeshDict 에서 자동 인식하도록 확장. 읽기 실패 시 아래 기본값 유지.
NX, NY, NZ = 108, 48, 48
LX, LY, LZ = 0.47, 0.21, 0.21
N = NX * NY * NZ
dx, dy, dz = LX / NX, LY / NY, LZ / NZ
VC = dx * dy * dz                       # 셀 체적
Ax, Ay, Az = dy * dz, dx * dz, dx * dy
VTOT = LX * LY * LZ


try:
    # Windows 콘솔은 cp949 라 보고문의 en-dash(–)·기호에서 UnicodeEncodeError 로 죽는다.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                           # noqa: BLE001
    pass


def set_grid_from_case(case):
    """system/blockMeshDict 의 nx/ny/nz·Lx/Ly/Lz 로 모듈 전역 격자를 재설정."""
    global NX, NY, NZ, LX, LY, LZ, N, dx, dy, dz, VC, Ax, Ay, Az, VTOT
    p = os.path.join(case, "system", "blockMeshDict")
    if not os.path.exists(p):
        print(f"      [warn] {p} 없음 → 기본격자 {NX}x{NY}x{NZ}, "
              f"{LX}x{LY}x{LZ} 유지")
        return False
    t = open(p, errors="ignore").read()

    def _i(k):
        m = re.search(rf"^{k}\s+(\d+)\s*;", t, re.M)
        return int(m.group(1)) if m else None

    def _f(k):
        m = re.search(rf"^{k}\s+([\d.eE+-]+)\s*;", t, re.M)
        return float(m.group(1)) if m else None

    nx, ny, nz = _i("nx"), _i("ny"), _i("nz")
    lx, ly, lz = _f("Lx"), _f("Ly"), _f("Lz")
    if None in (nx, ny, nz, lx, ly, lz):
        print("      [warn] blockMeshDict 파싱 실패 → 기본격자 유지")
        return False
    NX, NY, NZ, LX, LY, LZ = nx, ny, nz, lx, ly, lz
    N = NX * NY * NZ
    dx, dy, dz = LX / NX, LY / NY, LZ / NZ
    VC = dx * dy * dz
    Ax, Ay, Az = dy * dz, dx * dz, dx * dy
    VTOT = LX * LY * LZ
    return True

# ------------------------------------------------------------------ 물성 (상수_목록 A군)
# ★ CFD: 물성을 constants.py 한 곳에서만 읽는다.
#   구 버전은 여기에 USLIP=0.055 (@20 °C) 를 박아 뒀는데, alpha_g 폐합(fixedpoint.py)은
#   0.0578 (@25 °C) 을 썼다. 같은 물리량에 두 값이 돌아다니면 k_L,b 가 2.3 % 어긋나고
#   그만큼 K_La 가 틀어진다. 본시험 수온이 23.8~24.2 °C 이므로 0.0578 로 통일한다.
#   (상수_목록.md §D 각주 "스크립트별 사용 온도 확인" 이 경고하던 바로 그 함정이다.)
try:
    import constants as _K
    DMOL_20 = _K.DMOL_20
    NU_20 = _K.NU_20
    SCT = _K.SC_T
    KL_SURF_20 = _K.KL_SURF_20
    THETA_KL = _K.THETA
    DB = _K.DB
    USLIP = _K.USLIP
except Exception:                                           # noqa: BLE001
    DMOL_20, NU_20, SCT = 2.0e-9, 1.0e-6, 0.7
    KL_SURF_20, THETA_KL = 2.3e-5, 1.024
    DB, USLIP = 0.5e-3, 0.0578


# ------------------------------------------------------------------ 유틸
def benson_krause_cstar(T_c, P_kpa=101.325):
    """담수 산소 포화농도 [mg/L] — Benson & Krause [R14]. fit_kla.py 와 동일 식."""
    T = T_c + 273.15
    ln_c = (-139.34411 + 1.575701e5 / T - 6.642308e7 / T**2
            + 1.243800e10 / T**3 - 8.621949e11 / T**4)
    return float(np.exp(ln_c) * (P_kpa / 101.325))


def read_field(case, t, name, ncomp):
    """OpenFOAM volField 내부장 파싱 (uniform / nonuniform 모두)."""
    for p in (f"{case}/{t}/{name}", f"{case}/{t}/{name}.gz"):
        if os.path.exists(p):
            txt = (gzip.open(p, "rt", errors="ignore") if p.endswith(".gz")
                   else open(p, "r", errors="ignore")).read()
            break
    else:
        raise FileNotFoundError(f"{case}/{t}/{name}[.gz] 없음 — 유동 런이 끝났는지 확인")
    m = re.search(r"internalField\s+nonuniform\s+List<\w+>\s*\n\s*(\d+)\s*\n\(", txt)
    if not m:
        mu = re.search(r"internalField\s+uniform\s+(.+?);", txt)
        val = np.array(mu.group(1).strip().strip("()").split(), float)
        return np.tile(val, (N, 1)) if ncomp > 1 else np.full(N, val[0])
    nc = int(m.group(1))
    assert nc == N, f"{name}: 셀수 {nc} != {N} (격자 불일치)"
    body = txt[m.end():]
    # 내부장 리스트의 끝 = 단독으로 ')' 만 있는 줄. (파일 끝 괄호를 잡으면
    # boundaryField 텍스트까지 숫자 파싱에 들어가 numpy>=2 에서 ValueError)
    e = re.search(r"^\s*\)\s*$", body, re.M)
    seg = body[: e.start()] if e else body
    seg = re.sub(r"[()]", " ", seg)
    try:
        nums = np.fromstring(seg, sep=" ")
    except ValueError:
        nums = np.array(seg.split(), dtype=float)
    if nums.size < nc * ncomp:                       # 혹시 모를 조기절단 방어
        nums = np.array(re.findall(r"[-+]?[\d.]+(?:[eE][-+]?\d+)?", seg), dtype=float)
    if nums.size != nc * ncomp:
        raise ValueError(f"{name}: 파싱된 값 {nums.size} != 기대 {nc*ncomp} — 파일 형식 확인")
    return nums.reshape(nc, ncomp) if ncomp > 1 else nums


def read_zone(case, name):
    with gzip.open(f"{case}/constant/polyMesh/cellZones.gz", "rt") as f:
        txt = f.read()
    m = re.search(name + r"\s*\{.*?cellLabels\s+List<label>\s*\n\s*(\d+)\s*\n\((.*?)\)",
                  txt, re.S)
    if not m:
        raise RuntimeError(f"cellZone '{name}' 없음 — topoSet 실행됐는지 확인")
    labs = np.fromstring(m.group(2), sep=" ", dtype=int)
    assert len(labs) == int(m.group(1))
    return labs


def flat(k, j, i):
    return i + NX * j + NX * NY * k


def build_precond(M, kind):
    """BiCGStab 전처리자. amg(권장·저메모리) → ilu → jacobi 순으로 폴백."""
    if kind in ("amg", "auto"):
        try:
            import pyamg
            ml = pyamg.smoothed_aggregation_solver(M.tocsr(), max_coarse=500,
                                                   symmetry="nonsymmetric")
            return ml.aspreconditioner(cycle="V")
        except Exception as e:
            if kind == "amg":
                raise
            print(f" [amg 실패: {e} → ilu]", end="")
    if kind in ("ilu", "auto"):
        try:
            ilu = spilu(M.tocsc(), drop_tol=1e-3, fill_factor=3)
            return LinearOperator(M.shape, ilu.solve)
        except Exception as e:
            print(f" [ilu 실패: {e} → jacobi]", end="")
    d = M.diagonal()
    return LinearOperator(M.shape, lambda x: x / d)


def model(t, cstar, kla, c0):
    return cstar - (cstar - c0) * np.exp(-kla * t)


def _probe_set(name, case):
    """프로브 좌표 결정 — 기본은 constants.py 의 실측 좌표.

    --probe-set e02|e08|e17 : 그 케이스를 쓴 실측 런의 프로브 + 진단점
    --probe-set auto        : 케이스 디렉터리 이름에서 추정 (실패 시 전체 실측 3점)
    --probe-set "n:x,y,z;…" : 직접 지정
    """
    if ":" in name:
        d = {}
        for part in name.split(";"):
            if not part.strip():
                continue
            k, v = part.split(":")
            d[k.strip()] = tuple(float(s) for s in v.split(","))
        return d
    try:
        import constants as _K
    except Exception:                                       # noqa: BLE001
        return {"mid_center": (0.235, 0.105, 0.105)}
    cid = name
    if name == "auto":
        cid = os.path.basename(os.path.abspath(case))
    pr = _K.probes_for(cid)
    if not pr:                       # 모르는 케이스 → 실측 3점 전부 + 진단점
        pr = {f"{_K.probe_name(r['probe'])}": r["probe"] for r in _K.RUNS}
        pr.update(_K.PROBES_EXTRA)
    return pr


def fit_exp(t, c, lo=0.15, hi=0.92):
    """fit_kla.py 와 동일한 유효창 규약으로 단일지수 피팅."""
    c_min = float(np.percentile(c[: max(3, len(c) // 50)], 50))
    c_pla = float(np.percentile(c[-max(3, len(c) // 20):], 50))
    frac = (c - c_min) / (c_pla - c_min)
    idx = np.where((frac >= lo) & (frac <= hi))[0]
    if len(idx) < 10:
        raise ValueError("유효창 내 점 부족 — --end 를 늘려 평탄부까지 적분하세요")
    m = slice(idx[0], idx[-1] + 1)
    tw, cw = t[m] - t[m][0], c[m]
    p0 = [c_pla, 1.0 / max(tw[-1] / 3.0, 1e-3), cw[0]]
    popt, pcov = curve_fit(model, tw, cw, p0=p0,
                           bounds=([c_pla * 0.5, 1e-8, -1.0],
                                   [c_pla * 2 + 5, 1.0, c_pla]), maxfev=20000)
    resid = cw - model(tw, *popt)
    return dict(cstar=popt[0], kla=popt[1], c0=popt[2],
                kla_se=float(np.sqrt(np.diag(pcov))[1]),
                rmse=float(np.sqrt(np.mean(resid**2))), n=len(tw),
                window=(float(t[m][0]), float(t[m][-1])))


# ------------------------------------------------------------------ 본체
def main():
    ap = argparse.ArgumentParser(description="EX2 CFD 가상 재폭기 (DO=0 → 포화)")
    ap.add_argument("--case", default=os.path.join(HERE, "e02"),
                    help="유동 케이스 디렉토리 (기본 ./e02)")
    ap.add_argument("--time", default="200", help="시간평균장 시각 (기본 200)")
    ap.add_argument("--T", type=float, default=23.95,
                    help="수온 [degC] (기본 23.95 = S5 실측. 런별 실측값을 넣을 것)")
    ap.add_argument("--P", type=float, default=101.0,
                    help="기압 [kPa] (기본 101.0 = EX2 본시험 실측)")
    ap.add_argument("--alpha-g", type=float, required=True,
                    help="플룸 기체체적분율 (a=6*alpha_g/d_b). **필수** — "
                         "fp_result.csv 의 그 케이스 자기일관 고정점을 넣는다. "
                         "구 기본값 0.29 는 Q_air=2 L/min 전제라 폐기됐다")
    ap.add_argument("--probe-set", default="auto",
                    help="프로브 좌표. auto(케이스명에서 추정) / e02|e08|e17 / "
                         "\"name:x,y,z;name2:x,y,z\"")
    ap.add_argument("--C0", type=float, default=0.0, help="초기 DO [mg/L] (기본 0 = 탈산소)")
    ap.add_argument("--end", type=float, default=3600.0, help="적분 종료시간 [s]")
    ap.add_argument("--dt-max", type=float, default=10.0, help="최대 dt [s]")
    ap.add_argument("--no-surface", action="store_true", help="자유수면 재폭기 채널 끄기")
    ap.add_argument("--sct", type=float, default=0.0,
                    help="난류 슈미트수 Sc_t 덮어쓰기 (0 = constants.SC_T). "
                         "논문 §4.3 G10 'Sc_t 밴드 하 위치 불변성' 검정용")
    ap.add_argument("--tag", default=None, help="출력 하위폴더 이름")
    ap.add_argument("--out", default=os.path.join(HERE, "out"), help="출력 루트 (기본 ./out)")
    ap.add_argument("--quick", action="store_true", help="빠른 점검(dt 성기게, 정확도↓)")
    ap.add_argument("--scheme", default="cn", choices=["cn", "be"],
                    help="시간이산화. cn=Crank-Nicolson(2차, 기본) / be=backward Euler(1차, 강건)")
    ap.add_argument("--precond", default="auto", choices=["auto", "amg", "ilu", "jacobi"],
                    help="선형해 전처리자. auto=amg→ilu→jacobi 폴백 (amg 권장: pip install pyamg)")
    ap.add_argument("--noplot", action="store_true")
    ap.add_argument("--wall-limit", type=float, default=0.0,
                    help="이 벽시간[s] 초과 시 체크포인트 저장 후 중단 (0=무제한). "
                         "샌드박스처럼 실행시간 제한이 있을 때만 사용")
    ap.add_argument("--resume", action="store_true", help="체크포인트에서 이어서 적분")
    ap.add_argument("--snapshots", default="",
                    help="3D 필드를 저장할 시각들 [s], 쉼표구분 (예: 30,120,300,600,1200,2400). "
                         "공간 시각화(visualize.py)용 snapshots.npz 생성")
    args = ap.parse_args()

    global SCT
    if args.sct > 0:
        SCT = args.sct                  # Sc_t 밴드 검정 (기본은 constants.SC_T=0.7)

    case = os.path.abspath(args.case)
    set_grid_from_case(case)            # 격자·도메인을 케이스에서 인식 (수위 가변 대응)
    tag = args.tag or f"{os.path.basename(case)}_T{args.T:g}_ag{args.alpha_g:g}"
    out = os.path.join(args.out, tag)
    os.makedirs(out, exist_ok=True)

    # ---------------- 온도 종속 상수 ----------------
    Cstar = benson_krause_cstar(args.T, args.P)
    kL_surf = KL_SURF_20 * THETA_KL ** (args.T - 20.0)
    Dmol = DMOL_20
    a_int = 6.0 * args.alpha_g / DB                     # 계면적 [1/m]
    Re_b = USLIP * DB / NU_20
    Sc = NU_20 / Dmol
    Sh_b = 2.0 + 0.6 * Re_b**0.5 * Sc**(1.0 / 3.0)      # Frössling
    kL_b = Sh_b * Dmol / DB                             # 기포 k_L [m/s]

    print("=" * 68)
    print(f" EX2 가상 재폭기 · case={os.path.basename(case)} · T={args.T} degC")
    print("=" * 68)
    print(f" C*(Benson-Krause)  = {Cstar:.3f} mg/L")
    print(f" k_L,surf({args.T}C)   = {kL_surf:.3e} m/s   (20C값 x {THETA_KL}^dT)")
    print(f" Re_b={Re_b:.1f} Sc={Sc:.0f} Sh_b={Sh_b:.1f} -> k_L,b = {kL_b:.3e} m/s")
    print(f" alpha_g={args.alpha_g}  a=6ag/db = {a_int:.0f} 1/m   k_L,b*a = {kL_b*a_int:.4f} 1/s")

    # ---------------- 유동장 ----------------
    print("\n[1/5] 동결 유동장 읽는 중 ...")
    U = read_field(case, args.time, "UMean", 3)
    nut = read_field(case, args.time, "nutMean", 1)
    plume = read_zone(case, "plume")
    U3 = U.reshape(NZ, NY, NX, 3)
    Deff = Dmol + nut.reshape(NZ, NY, NX) / SCT
    umag = np.linalg.norm(U, axis=1)
    print(f"      |U| mean {umag.mean():.4f}  max {umag.max():.3f} m/s | "
          f"D_eff mean {Deff.mean():.3e} m2/s | plume {len(plume)} cells "
          f"(V_p/V = {len(plume)*VC/VTOT:.4e})")

    # 해석 예측 (0-D 축약, pos1_상수확정_T20.md §4 와 동일 계산)
    kla_plume = (len(plume) * VC / VTOT) * kL_b * a_int
    kla_surf = 0.0 if args.no_surface else kL_surf * (LX * LY) / VTOT
    kla_pred = kla_plume + kla_surf
    print(f"      해석예측 K_La = {kla_pred:.4e} /s = {kla_pred*3600:.2f} /h "
          f"(플룸 {kla_plume/kla_pred*100:.0f}% : 수면 {kla_surf/kla_pred*100:.0f}%), "
          f"tau = {1/kla_pred/60:.1f} min")

    # ---------------- 이산 연산자 ----------------
    print("\n[2/5] 이송-확산 행렬 조립 ...")
    Fx = 0.5 * (U3[:, :, 1:, 0] + U3[:, :, :-1, 0]) * Ax
    Fy = 0.5 * (U3[:, 1:, :, 1] + U3[:, :-1, :, 1]) * Ay
    Fz = 0.5 * (U3[1:, :, :, 2] + U3[:-1, :, :, 2]) * Az
    Dfx = 0.5 * (Deff[:, :, 1:] + Deff[:, :, :-1]) * Ax / dx
    Dfy = 0.5 * (Deff[:, 1:, :] + Deff[:, :-1, :]) * Ay / dy
    Dfz = 0.5 * (Deff[1:, :, :] + Deff[:-1, :, :]) * Az / dz

    diag = np.zeros(N)
    b = np.zeros(N)
    _r, _c, _v = [], [], []

    def add(ip, jp, v):
        _r.append(np.asarray(ip).ravel()); _c.append(np.asarray(jp).ravel())
        _v.append(np.asarray(v, float).ravel())

    def do_faces(F, Df, axis):
        if axis == "x":
            kk, jj, ii = np.meshgrid(np.arange(NZ), np.arange(NY), np.arange(NX - 1), indexing="ij")
            P, Nb = flat(kk, jj, ii), flat(kk, jj, ii + 1)
        elif axis == "y":
            kk, jj, ii = np.meshgrid(np.arange(NZ), np.arange(NY - 1), np.arange(NX), indexing="ij")
            P, Nb = flat(kk, jj, ii), flat(kk, jj + 1, ii)
        else:
            kk, jj, ii = np.meshgrid(np.arange(NZ - 1), np.arange(NY), np.arange(NX), indexing="ij")
            P, Nb = flat(kk, jj, ii), flat(kk + 1, jj, ii)
        P, Nb, Ff, Dff = P.ravel(), Nb.ravel(), F.ravel(), Df.ravel()
        fpos, fneg = np.maximum(Ff, 0.0), np.minimum(Ff, 0.0)   # 1차 풍상
        np.add.at(diag, P, fpos); add(P, Nb, fneg)
        np.add.at(diag, Nb, -fneg); add(Nb, P, -fpos)
        np.add.at(diag, P, Dff); add(P, Nb, -Dff)
        np.add.at(diag, Nb, Dff); add(Nb, P, -Dff)

    do_faces(Fx, Dfx, "x"); do_faces(Fy, Dfy, "y"); do_faces(Fz, Dfz, "z")

    # 소스: 플룸 체적소스 + 자유수면 Robin (둘 다 (C*-C) 형태 → 반음함수)
    Sp_cell = kL_b * a_int * VC
    diag[plume] += Sp_cell
    b[plume] += Sp_cell * Cstar
    jjb, iib = np.meshgrid(np.arange(NY), np.arange(NX), indexing="ij")
    Ptop = (iib + NX * jjb + NX * NY * (NZ - 1)).ravel()
    if not args.no_surface:
        np.add.at(diag, Ptop, kL_surf * Az)
        b[Ptop] += kL_surf * Az * Cstar
    # 바닥·유리벽: 무플럭스 (아무것도 안 더함)

    # 연속방정식 보정 — 보간 div(U) 오차로 상수장이 안 보존되는 것 제거
    divout = np.zeros((NZ, NY, NX))
    divout[:, :, :-1] += Fx; divout[:, :, 1:] -= Fx
    divout[:, :-1, :] += Fy; divout[:, 1:, :] -= Fy
    divout[:-1, :, :] += Fz; divout[1:, :, :] -= Fz
    diag -= divout.ravel()

    A = csr_matrix((np.concatenate([diag] + _v),
                    (np.concatenate([np.arange(N)] + _r),
                     np.concatenate([np.arange(N)] + _c))), shape=(N, N))
    del _r, _c, _v
    print(f"      nnz = {A.nnz:,}")

    # ---------------- 시간적분 ----------------
    # dt 단계: 초반 플룸 충전(초단위) → 후반 벌크 상승(분단위). dt 바뀔 때만 ILU 재분해.
    if args.quick:
        stages = [(20.0, 1.0), (120.0, 5.0), (args.end, max(args.dt_max, 20.0))]
    else:
        stages = [(10.0, 0.25), (60.0, 1.0), (300.0, 5.0), (args.end, args.dt_max)]
    stages = [(min(te, args.end), d) for te, d in stages if te > 0]

    # ★ CFD: 프로브 = **실측이 실제로 꽂았던 좌표** (constants.py, S1-S4_종합분석 부록 C.1).
    #   실측 K_La 는 프로브 1점 판독에서 나온 값이므로, 체적평균만 대조하면 사과-대-오렌지다.
    #   여기서 같은 좌표의 국소 곡선을 같은 유효창으로 피팅해 1:1 대조를 만든다.
    probes = _probe_set(args.probe_set, case)
    pid = {k: flat(min(int(z / dz), NZ - 1), min(int(y / dy), NY - 1), min(int(x / dx), NX - 1))
           for k, (x, y, z) in probes.items()}
    plume_mask = np.zeros(N, bool); plume_mask[plume] = True

    ckpt = os.path.join(out, "checkpoint.npz")
    C = np.full(N, args.C0)
    rec = [[0.0, C.mean(), C[plume_mask].mean(), C.min(), C.max()] + [C[i] for i in pid.values()]]
    t_now = 0.0
    if args.resume and os.path.exists(ckpt):
        z = np.load(ckpt)
        C, rec, t_now = z["C"], [list(r) for r in z["rec"]], float(z["t"])
        print(f"      [resume] t = {t_now:.1f} s 에서 이어감 (Cbar={C.mean():.4f})")
    I = identity(N, format="csr")

    def save_ckpt():
        np.savez(ckpt, C=C, rec=np.array(rec), t=t_now)

    # 3D 필드 스냅샷 (공간 시각화용)
    snap_t = sorted(float(s) for s in args.snapshots.split(",") if s.strip())
    snap_file = os.path.join(out, "snapshots.npz")
    snaps = {}
    if snap_t and args.resume and os.path.exists(snap_file):
        snaps = {k: v for k, v in np.load(snap_file).items()}

    def take_snap(prev_t):
        """[prev_t, t_now) 구간을 지난 스냅샷 시각을 저장."""
        for st in snap_t:
            key = f"t{st:g}"
            if key not in snaps and prev_t < st <= t_now + 1e-9:
                snaps[key] = C.reshape(NZ, NY, NX).astype(np.float32).copy()
                np.savez_compressed(snap_file, **snaps)
                print(f"      [snapshot] t={st:g} s 저장 (실제 {t_now:.1f} s)")

    print(f"\n[3/5] 과도 적분  {t_now:g} → {args.end:g} s  "
          f"({'Crank-Nicolson' if args.scheme == 'cn' else 'backward Euler'})")
    wall0 = time.time()
    for t_end, dt in stages:
        if t_now >= t_end:
            continue
        th = 1.0 if args.scheme == "be" else 0.5      # theta: 1=backward Euler, 0.5=Crank-Nicolson
        M = (th * A + (VC / dt) * I).tocsr()
        print(f"      dt={dt:g} s → 전처리자({args.precond}) 구성 ...", end="", flush=True)
        Mop = build_precond(M, args.precond)
        print(" done")
        while t_now < t_end - 1e-9:
            t_prev = t_now
            rhs = b + (VC / dt) * C - (1.0 - th) * (A @ C)
            C, info = bicgstab(M, rhs, M=Mop, x0=C, rtol=1e-9, maxiter=300)
            if info != 0:
                print(f"      [warn] t={t_now:.1f}s bicgstab info={info}")
            t_now += dt
            rec.append([t_now, C.mean(), C[plume_mask].mean(), C.min(), C.max()]
                       + [C[i] for i in pid.values()])
            take_snap(t_prev)
            if abs(t_now % 300.0) < dt * 0.5:
                print(f"      t={t_now:7.1f} s   Cbar={C.mean():.4f} mg/L "
                      f"({C.mean()/Cstar*100:5.1f}% sat)   [{time.time()-wall0:.0f}s]")
            if args.wall_limit and time.time() - wall0 > args.wall_limit:
                save_ckpt()
                print(f"      [wall-limit] t={t_now:.1f} s 에서 체크포인트 저장 → "
                      f"같은 명령에 --resume 붙여 재실행")
                return
    save_ckpt()
    rec = np.array(rec)
    print(f"      적분 완료 · {len(rec)-1} 스텝 · 벽시간 {time.time()-wall0:.0f} s")

    # ---------------- 저장 · 피팅 ----------------
    print("\n[4/5] 저장 · 피팅 ...")
    hdr = "t_s,C_bulk,C_plume,C_min,C_max," + ",".join(pid.keys())
    np.savetxt(os.path.join(out, "bulk_C_t.csv"), rec, delimiter=",", header=hdr,
               comments="", fmt="%.9g")   # 9자리: 피팅 잔차(~1e-8)가 반올림에 묻히지 않게
    np.save(os.path.join(out, "C_final.npy"), C.reshape(NZ, NY, NX))

    t, cb = rec[:, 0], rec[:, 1]
    fit = fit_exp(t, cb)
    kappa_hint = fit["kla"]
    # 프로브 후보 평가: 어느 점이 체적평균을 가장 잘 대표하나 (방법론 §6.1-1)
    prow = {}
    pfit = {}
    for n, name in enumerate(pid.keys()):
        cp = rec[:, 5 + n]
        prow[name] = (float(np.sqrt(np.mean((cp - cb) ** 2))),
                      float(np.max(np.abs(cp - cb))))
        # ★ 국소 곡선을 체적평균과 **같은 유효창 규약**으로 따로 피팅한다.
        #   실측은 프로브 1점 판독이므로 이게 진짜 1:1 대조 상대다.
        try:
            pfit[name] = fit_exp(t, cp)
        except Exception:                                   # noqa: BLE001
            pfit[name] = None
    best = min(prow, key=lambda k: prow[k][0])

    lines = []
    P = lines.append
    P("EX2 · CFD 가상 재폭기 결과")
    P(f"  case         : {case}  (time {args.time}, 동결 UMean/nutMean)")
    P(f"  T            : {args.T} degC,  P = {args.P} kPa")
    P(f"  alpha_g      : {args.alpha_g}  → a = {a_int:.0f} 1/m,  k_L,b = {kL_b:.3e} m/s")
    P(f"  C0           : {args.C0} mg/L (탈산소 상태에서 출발)")
    P(f"  수면채널     : {'OFF' if args.no_surface else 'ON'}")
    P("")
    P("[해석 0-D 예측]")
    P(f"  K_La_plume = {kla_plume:.4e} /s ({kla_plume*3600:.3f} /h)")
    P(f"  K_La_surf  = {kla_surf:.4e} /s ({kla_surf*3600:.3f} /h)")
    P(f"  K_La_pred  = {kla_pred:.4e} /s ({kla_pred*3600:.3f} /h),  tau = {1/kla_pred/60:.2f} min")
    P("")
    P("[3D 과도해 피팅]  (fit_kla.py 와 동일 유효창 0.15–0.92)")
    P(f"  K_La_eff,CFD = {fit['kla']:.4e} /s = {fit['kla']*3600:.3f} /h  (SE {fit['kla_se']:.2e})")
    P(f"  C*_CFD       = {fit['cstar']:.4f} mg/L   (입력 C* = {Cstar:.4f})")
    P(f"  tau          = {1/fit['kla']/60:.2f} min,  95% 도달 {3/fit['kla']/60:.1f} min")
    P(f"  초기상승률   = {fit['kla']*(Cstar-args.C0)*60:.3f} mg/L/min")
    P(f"  피팅 RMSE    = {fit['rmse']:.4e} mg/L (n={fit['n']}, 창 {fit['window'][0]:.0f}–{fit['window'][1]:.0f} s)")
    P(f"  3D/0-D 비    = {fit['kla']/kla_pred:.4f}  (1.0 이면 0-D 축약이 3D 해와 일치)")
    P(f"  최종 t={t[-1]:.0f}s: Cbar={cb[-1]:.4f} ({cb[-1]/Cstar*100:.2f}% sat), "
      f"공간편차 C_max-C_min = {rec[-1,4]-rec[-1,3]:.4f} mg/L")
    P("")
    P("[프로브 국소곡선 — 실측과 1:1 대조할 값]")
    P("  실측 K_La 는 프로브 **1점 판독**에서 나온다. 체적평균이 아니라 이 열을 쓸 것.")
    P("  point              x,y,z [m]          K_La[/h]  vs체적평균   RMSE_fit   RMSEvsCbar  max|Δ|")
    for name in pid:
        x, y, z = probes[name]
        f2 = pfit.get(name)
        if f2 is None:
            P(f"  {name:16s} ({x:.3f},{y:.3f},{z:.3f})   [피팅 실패]")
            continue
        P(f"  {name:16s} ({x:.3f},{y:.3f},{z:.3f})   {f2['kla']*3600:8.4f}  "
          f"{100*(f2['kla']/fit['kla']-1):+8.2f} %  {f2['rmse']:.3e}   "
          f"{prow[name][0]:.4f}     {prow[name][1]:.4f}")
    P(f"  → 체적평균 대표성이 가장 좋은 점: {best}  {probes[best]}")
    kl_p = [f2["kla"] for f2 in pfit.values() if f2]
    if len(kl_p) >= 2:
        kl_p = np.array(kl_p)
        P(f"  → 프로브 간 K_La 산포: {kl_p.mean()*3600:.4f} ± "
          f"{kl_p.std(ddof=1)*3600:.4f} /h  = **CV {100*kl_p.std(ddof=1)/kl_p.mean():.2f} %**"
          f"  (실측 위치 산포 1.44 % 의 CFD 대조군)")
    P("")
    P("[κ 계산법] 실측 fit_kla.py 의 kla_meas 를 얻으면:")
    P(f"  체적평균 기준 : kappa = kla_meas[/h] / {fit['kla']*3600:.4f}")
    for name in pid:
        f2 = pfit.get(name)
        if f2 and not name.startswith(("center", "nearplume", "surface", "bottom")):
            P(f"  {name:16s}: kappa = kla_meas[/h] / {f2['kla']*3600:.4f}   "
              f"← 같은 좌표 대조 (권장)")
    txt = "\n".join(lines)
    # 기계 판독용 — compare_exp.py 가 이 파일만 읽는다
    import csv as _csv
    with open(os.path.join(out, "probe_fit.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["probe", "x", "y", "z", "kla_1h", "cstar_mgL", "rmse_mgL",
                    "n", "t_win_lo_s", "t_win_hi_s", "rmse_vs_bulk", "maxabs_vs_bulk"])
        w.writerow(["__bulk__", "", "", "", f"{fit['kla']*3600:.6f}",
                    f"{fit['cstar']:.6f}", f"{fit['rmse']:.4e}", fit["n"],
                    f"{fit['window'][0]:.1f}", f"{fit['window'][1]:.1f}", "0", "0"])
        for name in pid:
            f2 = pfit.get(name)
            if not f2:
                continue
            x, y, z = probes[name]
            w.writerow([name, x, y, z, f"{f2['kla']*3600:.6f}",
                        f"{f2['cstar']:.6f}", f"{f2['rmse']:.4e}", f2["n"],
                        f"{f2['window'][0]:.1f}", f"{f2['window'][1]:.1f}",
                        f"{prow[name][0]:.6f}", f"{prow[name][1]:.6f}"])

    with open(os.path.join(out, "fit.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print("\n" + txt)

    # ---------------- 그림 ----------------
    if not args.noplot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
            ax[0].plot(t / 60, cb, "k-", lw=2, label="CFD bulk mean")
            tw0 = fit["window"][0]
            mw = t >= tw0
            ax[0].plot(t[mw] / 60, model(t[mw] - tw0, fit["cstar"], fit["kla"], fit["c0"]),
                       "r--", lw=1.2, label=f"fit  K_La={fit['kla']*3600:.2f} /h")
            ax[0].plot(t / 60, rec[:, 2], "b:", lw=1, label="plume zone mean")
            ax[0].axhline(Cstar, color="gray", ls=":", lw=1, label=f"C*={Cstar:.2f}")
            ax[0].set_xlabel("t [min]"); ax[0].set_ylabel("DO [mg/L]")
            ax[0].set_title(f"virtual reaeration · {tag}"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
            for n, name in enumerate(pid):
                ax[1].plot(t / 60, rec[:, 5 + n] - cb, lw=1, label=name)
            ax[1].set_xlabel("t [min]"); ax[1].set_ylabel("C_probe - C_bulk [mg/L]")
            ax[1].set_title("probe deviation from volume mean"); ax[1].legend(fontsize=6, ncol=2)
            ax[1].grid(alpha=.3)
            fig.tight_layout(); fig.savefig(os.path.join(out, "curve.png"), dpi=140)

            C3 = C.reshape(NZ, NY, NX)
            fig2, axs = plt.subplots(1, 3, figsize=(14, 3.2))
            for a_, (kz, lab) in zip(axs, [(1, "z=bottom"), (NZ // 2, "z=mid"), (NZ - 1, "z=surface")]):
                im = a_.imshow(C3[kz], origin="lower", aspect="auto",
                               extent=[0, LX, 0, LY], cmap="viridis")
                a_.set_title(f"{lab}  (t={t[-1]:.0f}s)"); fig2.colorbar(im, ax=a_)
            fig2.tight_layout(); fig2.savefig(os.path.join(out, "slices.png"), dpi=140)
            print(f"\n[5/5] 그림 저장: {out}/curve.png, slices.png")
        except ImportError:
            print("\n[5/5] matplotlib 없음 → 그림 생략 (CSV 는 저장됨)")

    print(f"\n출력 폴더: {out}")


if __name__ == "__main__":
    main()
