#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 CFD · 단일 상수원 (SINGLE SOURCE)

원칙 — **모든 계수와 좌표는 어항 실측을 기준으로 한다.**
    구 EX2/CFD 는 Q_air=2 L/min(스펙 어림값)·alpha_g=0.29·폭기축 (0.13, 0.035) 전제였고
    2026-08-02 통째로 _archive/EX2_CFD_구전제_alphag029/ 로 보냈다.
    이 파일의 값은 전부 실측이거나 실측에서 유도된 것이다. 여기 없는 값은 쓰지 않는다.

출처
    Q_air            EX2/어항실험 물치환법 실측 (2026-07-31, 500 mL/25.000 s ×3, ±0.14 %)
    d_b              기포 이미지 측정 (4 px × 20 mm / 160 px)
    폭기·프로브 좌표  S1-S4_종합분석_20260802.md 부록 C.1 (좌표 진실원)
    수온·기압         같은 문서 §1.2 · 부록 A.3 (런별 실측)
    C*_ref           같은 문서 §1.1 (S1 평탄부 실측 8.659 mg/L @ 23.95 °C)
    수조 기하         ../상수_목록.md §E
    k_L,20 / theta   ../상수_목록.md §B·§C  [R5][R9]

바뀐 것 (구 EX2/CFD 대비)
    Q_air   2      -> 1.2  L/min        (실측이 어림값의 60 %)
    U_gs    0.106  -> 0.0637 m/s
    alpha_g 0.29   -> z별 자기일관 재수렴 (고정값 없음, fixedpoint.py 가 푼다)
    폭기축  (0.13, 0.035) -> (0.035, 0.195)      실험이 실제로 쓴 자리
    수온    20 / 25 고정 -> 런별 실측 23.84~24.19 °C
    기압    101.325 -> 101.0 kPa (실측 입력)
"""
import math

# ---------------------------------------------------------------- 기하 (실측)
# 원점 = 수조 안쪽 바닥 한 모서리. x=길이, y=폭, z=수심.
LX, LY, LZ = 0.47, 0.21, 0.21          # m   47×21×21 cm
VOL = LX * LY * LZ                      # m^3 = 0.020727 -> 20.7 L
DEPTH = LZ                              # 수심 = 수위 21 cm (SOP 확정. "20 cm"는 구 표기)

GRID = (108, 48, 48)                    # medium. dz = 4.375 mm

# ★ 실험이 실제로 쓴 폭기축 (2026-08-02 좌표 확정). 폭 대칭 등가 (0.035, 0.015) = pos13
PLUME_AXIS = (0.035, 0.195)
PLUME_R = 0.01                          # m  (지름 20 mm)
A_P = math.pi * PLUME_R ** 2            # m^2 = 3.1416e-4

# ---------------------------------------------------------------- 폭기 (실측)
QAIR_LPM = 1.200                        # L/min  실측 ±0.002
QAIR = QAIR_LPM / 1000.0 / 60.0         # m^3/s = 2.000e-5
UGS = QAIR / A_P                        # m/s   = 0.06366   (z_start 무관 고정)
DB = 0.5e-3                             # m     기포직경 (이미지 측정)
USLIP = 0.0578                          # m/s   0.5 mm 종단속도 @25 °C (Re~28)
G = 9.81

# alpha_g 자기일관 폐합:  alpha_g = UGS / (W + USLIP),  Su = alpha_g * G
#   W = 플룸 셀존 액상 상승속도(CFD 실측). z_start 마다 다르므로 수준별로 다시 푼다.
#   멱법칙 W ∝ Su^n 의 n 은 z=0.02 에서 Su 를 흔들어 얻은 국소 스케일 가정이다.
N_EXP = 0.511                           # 3점 LSQ, 잔차 0.28 %
SU_SEED = 1.751                         # medium z=0.02 고정점 (alpha_g=0.1785) — 시드일 뿐
TOL_FP = 0.03                           # 자기일관 허용 잔차

# ---------------------------------------------------------------- 물성·모델
DMOL_20 = 2.0e-9                        # m^2/s  O2 분자확산 (물, 20 °C)
NU_20 = 1.0e-6                          # m^2/s
SC_T = 0.7                              # 난류 슈미트수
KL_SURF_20 = 2.3e-5                     # m/s    수면 재폭기 (≈2 m/d)
THETA = 1.024                           # Arrhenius 온도계수

# ---------------------------------------------------------------- 실측 조건
PRESSURE_KPA = 101.0                    # 실측 입력 (--set-pressure 완료)
CSTAR_REF = 8.659                       # mg/L  S1 평탄부 실측
CSTAR_REF_T = 23.95                     # °C
FIT_LO, FIT_HI = 0.15, 0.92             # 유효창 — 실측·CFD 공통 (사과-대-사과)

# ---------------------------------------------------------------- 케이스 정의
#   유동해는 수온과 무관하다(ν 고정) → 3케이스로 5런을 전부 대조한다.
CASES = [
    dict(cid="e02", z_start=0.020, note="S1·S2·S3 (생산 운전점, n=3)"),
    dict(cid="e08", z_start=0.080, note="S4"),
    dict(cid="e17", z_start=0.170, note="S5 (hold-out)"),
]

#   실측 5런 — CFD 대조의 기준. 프로브 좌표·수온이 전부 실측값이다.
#   kla25_meas 는 S1-S4_종합분석 §1.2 / 부록 A.3 의 25 °C 환산값(참고용).
RUNS = [
    dict(run="S1", cid="e02", z_start=0.020, T=24.19, probe=(0.455, 0.195, 0.105),
         kla_T_meas=2.454, kla25_meas=2.502),
    dict(run="S2", cid="e02", z_start=0.020, T=23.87, probe=(0.015, 0.015, 0.105),
         kla_T_meas=2.373, kla25_meas=2.437),
    dict(run="S3", cid="e02", z_start=0.020, T=23.89, probe=(0.455, 0.015, 0.105),
         kla_T_meas=2.432, kla25_meas=2.497),
    dict(run="S4", cid="e08", z_start=0.080, T=23.84, probe=(0.455, 0.195, 0.105),
         kla_T_meas=2.023, kla25_meas=2.079),
    dict(run="S5", cid="e17", z_start=0.170, T=23.95, probe=(0.455, 0.195, 0.105),
         kla_T_meas=1.044, kla25_meas=1.070),
]

#   진단용 추가 프로브 (실측엔 없지만 공간구조를 보려고 같이 뽑는다)
PROBES_EXTRA = {
    "center_mid": (0.235, 0.105, 0.105),
    "nearplume_mid": (0.055, 0.175, 0.105),
    "surface_center": (0.235, 0.105, 0.180),
    "bottom_far": (0.435, 0.015, 0.030),
}


def probe_name(xyz):
    """실측 프로브 3점의 라벨 (S1-S4_종합분석 부록 C.1)."""
    return {(0.455, 0.195, 0.105): "jangchuk",
            (0.015, 0.015, 0.105): "danchuk",
            (0.455, 0.015, 0.105): "choewon"}.get(tuple(xyz), "probe")


def probes_for(cid):
    """케이스에 물릴 프로브 dict — 그 케이스를 쓰는 실측 런의 좌표 + 진단점."""
    d = {}
    for r in RUNS:
        if r["cid"] == cid:
            d[f"{r['run']}_{probe_name(r['probe'])}"] = r["probe"]
    d.update(PROBES_EXTRA)
    return d


def benson_krause(T_c, P_kpa=PRESSURE_KPA):
    """담수 O2 포화농도 [mg/L] — Benson & Krause [R14]. fit_kla.py 와 동일 식."""
    T = T_c + 273.15
    lnC = (-139.34411 + 1.575701e5 / T - 6.642308e7 / T ** 2
           + 1.243800e10 / T ** 3 - 8.621949e11 / T ** 4)
    c0 = math.exp(lnC)
    pw = math.exp(11.8571 - 3840.70 / T - 216961.0 / T ** 2)   # 수증기압 [atm]
    p = P_kpa / 101.325
    return c0 * p * (1.0 - pw / p) * (1.0 - 0.000975 * p) / \
        ((1.0 - pw) * (1.0 - 0.000975))


def kl_surf(T_c):
    return KL_SURF_20 * THETA ** (T_c - 20.0)


def kl_bubble():
    """Frössling: Sh_b = 2 + 0.6 Re^1/2 Sc^1/3 -> k_L,b [m/s]."""
    Re_b = USLIP * DB / NU_20
    Sc = NU_20 / DMOL_20
    Sh_b = 2.0 + 0.6 * Re_b ** 0.5 * Sc ** (1.0 / 3.0)
    return Sh_b * DMOL_20 / DB


def alpha_from_W(W):
    return UGS / (W + USLIP)


if __name__ == "__main__":
    print(f"수조      {LX}×{LY}×{LZ} m = {VOL*1000:.2f} L   격자 {GRID}")
    print(f"폭기축    {PLUME_AXIS}  r={PLUME_R} m   z_start "
          f"{[c['z_start'] for c in CASES]}")
    print(f"Q_air     {QAIR_LPM} L/min = {QAIR:.3e} m3/s   U_gs {UGS:.5f} m/s")
    print(f"k_L,b     {kl_bubble():.4e} m/s   U_slip {USLIP} m/s   d_b {DB*1e3} mm")
    print(f"C*(B-K)   ", end="")
    for T in (23.84, 23.89, 23.95, 24.19):
        print(f"{T}°C→{benson_krause(T):.4f}  ", end="")
    print(f"\nC*_ref    {CSTAR_REF} mg/L @ {CSTAR_REF_T} °C "
          f"(B-K {benson_krause(CSTAR_REF_T):.4f} 의 "
          f"{100*CSTAR_REF/benson_krause(CSTAR_REF_T):.2f} %)")
