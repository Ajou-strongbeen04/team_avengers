#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 본시험 — 사전점검 (go / no-go)                          [2026-08-01]

do_logger.py 와 같은 폴더에서 실행 (Sensor 클래스 재사용).

만든 이유: 2026-07-31 파일럿과 2026-08-01 t_mix 측정에서 물린 함정이
전부 "런 시작 전에 30초면 확인됐을 것"이었다.
  · 온도 상승 중인 매질에서 100% 보정 -> 스팬 +4.7% 편향, 전 런 절대DO 오염
  · --read 없이 --calibrate 재실시 -> 표류값 영구 소실
  · --set-pressure 미실시 -> C* 기준압 불일치
  · baseline 표류 -> t95 회수율 148~324%, 산출 실패
  · --note 에 에어스톤 기하 누락 -> kappa 확정 불가
이 스크립트는 그걸 자동으로 막는다.

────────────────────────────────────────────────────────────────────────
게이트
────────────────────────────────────────────────────────────────────────
  --gate comm      통신 확립 + 값의 물리적 타당성            (30 s)
  --gate calib     100%/0% 보정 직전 온도 안정 판정          (3 min)
                   SOP §3-2: 3분간 dT < 0.05 degC
  --gate verify    보정 후 검증 — 폭기 중 수조 포화 99~101%  (2 min)
                   SOP §3.2. --expect-sat 로 허용대역 조정
  --gate baseline  주입/런 시작 전 DO 표류 판정              (5 min)
                   SOP §5.4 함정0: |기울기| < 0.002 mg/L/100s
  --gate drift     런 간 보정 프레임 표류 -> --scale 산출     (1 min)
                   C*_ref 를 1회만 잴 때 필수. 실행계획 부록 B
  --gate run       런 직전 종합 — comm + 기압 + 노트 + 파일명 (1 min)
  --gate all       comm -> verify -> (기압/노트 확인)

사용
  python3 preflight.py --port /dev/tty.usbserial-1110 --gate comm
  python3 preflight.py --port /dev/tty.usbserial-1110 --gate calib
  python3 preflight.py --port /dev/tty.usbserial-1110 --gate verify --pressure 101.0
  python3 preflight.py --port /dev/tty.usbserial-1110 --gate baseline
  python3 preflight.py --port /dev/tty.usbserial-1110 --gate run \
      --pressure 101.0 --log run_R2.csv \
      --note "R2, z_start=0.020, pos=jangchuk(0.450,0.175,0.105), T=24.1C, P=101.0kPa"

종료코드: 0 = GO, 1 = NO-GO.  결과는 preflight_log.md 에 append 된다.
"""

import argparse
import datetime as _dt
import math
import os
import sys
import time

from do_logger import Sensor, REG_PRESSURE, validate_note

LOGFILE = "preflight_log.md"


# ---------------------------------------------------------------- 물리

def benson_krause_cstar(T_c, P_kpa=101.325):
    """담수 산소 포화농도 [mg/L] — Benson & Krause [R14]."""
    T = T_c + 273.15
    ln_c = (-139.34411 + 1.575701e5 / T - 6.642308e7 / T**2
            + 1.243800e10 / T**3 - 8.621949e11 / T**4)
    return math.exp(ln_c) * (P_kpa / 101.325)


def linreg(xs, ys):
    n = len(xs)
    sx = sum(xs); sy = sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    den = n * sxx - sx * sx
    if den == 0:
        return 0.0, sy / n
    a = (n * sxy - sx * sy) / den
    return a, (sy - a * sx) / n


# ---------------------------------------------------------------- 수집

def collect(sensor, seconds, interval=1.0, label=""):
    """seconds 초 동안 (t, do, sat, temp) 수집. 진행상황 한 줄 갱신."""
    t0 = time.time()
    rows = []
    fails = 0
    while time.time() - t0 < seconds:
        try:
            sat, do, temp = sensor.read_all()
            fails = 0
            t = time.time() - t0
            rows.append((t, do, sat, temp))
            left = seconds - t
            print(f"\r  {label} [{int(t):3d}/{int(seconds)}s] DO {do:6.3f} "
                  f"포화 {sat*100:6.2f}% {temp:6.3f}C  (남은 {int(left)}s)   ",
                  end="", flush=True)
        except Exception as e:
            fails += 1
            print(f"\n  [warn] 읽기 실패 {fails}: {e}")
            if fails >= 8:
                raise
        time.sleep(interval)
    print()
    return rows


# ---------------------------------------------------------------- 게이트

def gate_comm(sensor):
    """통신 확립 + 값의 물리적 타당성."""
    print("\n[게이트 comm] 통신 · 값 타당성 (30 s)")
    rows = collect(sensor, 30, label="comm ")
    if len(rows) < 20:
        return False, [f"샘플 {len(rows)}/30 — 통신 불안정. A/B 극성·12V·보레이트 확인"]
    do = [r[1] for r in rows]; temp = [r[3] for r in rows]
    sat = [r[2] * 100 for r in rows]
    msgs = [f"샘플 {len(rows)}개, DO {min(do):.3f}~{max(do):.3f} mg/L, "
            f"포화 {min(sat):.1f}~{max(sat):.1f} %, 수온 {min(temp):.2f}~{max(temp):.2f} C"]
    ok = True
    if not (0.0 <= min(do) and max(do) < 25.0):
        ok = False; msgs.append(f"DO 값이 물리적 범위를 벗어남 ({min(do):.2f}~{max(do):.2f})")
    if not (0.0 < min(temp) < 45.0):
        ok = False; msgs.append(f"수온 이상 ({min(temp):.2f}~{max(temp):.2f} C)")
    if max(do) - min(do) > 1.0:
        msgs.append(f"[주의] 30초 DO 산포 {max(do)-min(do):.2f} mg/L — 프로브가 "
                    f"아직 평형이 아니거나 유동 교란")
    return ok, msgs


def gate_calib(sensor, dt_tol=0.05, window_s=180):
    """SOP §3-2 — 3분간 dT < 0.05 degC 여야 보정 가능."""
    print(f"\n[게이트 calib] 온도 안정 판정 — {window_s/60:.0f}분간 dT < {dt_tol} degC")
    print("  (2026-07-31: 27.07 C 로 '상승 중'인 매질에 100% 를 앵커해 "
          "스팬이 +4.7% 높게 박혔다. 전 런의 절대 DO 가 오염됐다.)")
    rows = collect(sensor, window_s, label="calib")
    if len(rows) < window_s * 0.7:
        return False, [f"샘플 부족 ({len(rows)}) — 통신 확인"]
    ts = [r[0] for r in rows]; T = [r[3] for r in rows]; do = [r[1] for r in rows]
    span = max(T) - min(T)
    slopeT = linreg(ts, T)[0] * window_s        # degC per window
    do_span = max(do) - min(do)
    msgs = [f"수온 {min(T):.3f}~{max(T):.3f} C  (범위 {span:.3f}, "
            f"추세 {slopeT:+.3f} C/{window_s/60:.0f}min)",
            f"DO   {min(do):.3f}~{max(do):.3f} mg/L (범위 {do_span:.3f})"]
    ok = True
    if span > dt_tol:
        ok = False
        msgs.append(f"NO-GO: 온도 범위 {span:.3f} > {dt_tol}. "
                    f"매질과 프로브가 열평형이 될 때까지 더 기다릴 것.")
    if abs(slopeT) > dt_tol:
        ok = False
        msgs.append(f"NO-GO: 온도가 {slopeT:+.3f} C/{window_s/60:.0f}min 로 추세를 "
                    f"갖는다. **값이 안정된 것만으로는 부족하다 — 온도가 평평해야 한다.**")
    if do_span > 0.15:
        msgs.append(f"[주의] DO 산포 {do_span:.3f} mg/L — 매질이 아직 안정 아님")
    if ok:
        msgs.append("GO: 지금 --calibrate 하십시오. "
                    "단 재보정이면 --read 로 표류값을 먼저 기록했는지 확인(SOP §3.1).")
    return ok, msgs


def gate_verify(sensor, pressure, lo=99.0, hi=101.0, seconds=120):
    """SOP §3.2 — 보정 후 폭기 중 수조를 읽어 Benson-Krause 와 대조."""
    print(f"\n[게이트 verify] 보정 후 검증 — 폭기 중 수조 포화 {lo}~{hi} % (2 min)")
    print("  프로브가 폭기 평형 수조에 잠겨 있어야 합니다.")
    rows = collect(sensor, seconds, label="verify")
    if len(rows) < seconds * 0.7:
        return False, [f"샘플 부족 ({len(rows)})"]
    tail = rows[len(rows) // 2:]                  # 후반부만 (평형 도달분)
    sat = sum(r[2] for r in tail) / len(tail) * 100
    do = sum(r[1] for r in tail) / len(tail)
    T = sum(r[3] for r in tail) / len(tail)
    bk = benson_krause_cstar(T, pressure)
    sat_bk = 100 * do / bk
    msgs = [f"후반부 평균: DO {do:.3f} mg/L, 센서 포화 {sat:.2f} %, 수온 {T:.2f} C",
            f"Benson-Krause C*({T:.2f}C, {pressure:.2f}kPa) = {bk:.3f} mg/L "
            f"-> 대조 포화 {sat_bk:.2f} %"]
    ok = lo <= sat_bk <= hi
    if not ok:
        if sat_bk > hi:
            msgs.append(f"NO-GO: {sat_bk:.2f} % > {hi}. 과포화로 읽힙니다. "
                        f"온도 상승 중에 100% 를 앵커했을 가능성 (SOP §3-2). 재보정 필요.")
        else:
            msgs.append(f"NO-GO: {sat_bk:.2f} % < {lo}. 수조가 아직 평형이 아니거나 "
                        f"스팬이 낮게 박혔습니다.")
    else:
        msgs.append("GO: 스팬 정상.")
    if abs(sat - sat_bk) > 1.0:
        msgs.append(f"[주의] 센서 내부 포화({sat:.2f}%)와 B-K 대조({sat_bk:.2f}%)가 "
                    f"{sat-sat_bk:+.2f}%p 어긋남 — 센서 기압/염분 레지스터 확인")
    return ok, msgs


def gate_drift(sensor, ref_do, ref_T, pressure, seconds=60, tol=0.5):
    """런 간 보정 표류 감시 — 100 % 비커를 기준물로 재판독.

    C*_ref 를 세션에 1회만 재면(2026-08-01 지시) 그 뒤 런들은 S1 의 보정
    프레임을 빌려 쓴다. 프레임이 표류하면 그 오차가 게인 3.1배로 KLa 에
    실린다(실행계획 §2.3). 이 게이트가 표류를 재고, fit_kla.py 에 넘길
    --scale 보정계수를 출력한다.

    원리: 100 % 비커의 참값은 B-K(T). 센서 판독 r 을 B-K 로 정규화하면
    프레임 자체만 남는다.  scale = (r_ref/BK(T_ref)) / (r_now/BK(T_now))
    """
    print(f"\n[게이트 drift] 보정 프레임 표류 — 100 % 기준 비커 재판독 "
          f"({seconds} s)")
    print(f"  기준(S1 시점): {ref_do:.4f} mg/L @ {ref_T:.2f} C")
    print("  프로브가 **100 % 포화 기준 비커**에 있어야 합니다(수조 아님).")
    rows = collect(sensor, seconds, label="drift")
    if len(rows) < seconds * 0.7:
        return False, [f"샘플 부족 ({len(rows)})"]
    tail = rows[len(rows) // 3:]
    do = sum(r[1] for r in tail) / len(tail)
    T = sum(r[3] for r in tail) / len(tail)
    dT = max(r[3] for r in tail) - min(r[3] for r in tail)

    n_ref = ref_do / benson_krause_cstar(ref_T, pressure)
    n_now = do / benson_krause_cstar(T, pressure)
    drift = 100 * (n_now / n_ref - 1.0)
    scale = n_ref / n_now

    msgs = [f"현재: {do:.4f} mg/L @ {T:.2f} C (dT={dT:.3f})",
            f"B-K 정규화  기준 {n_ref:.5f} -> 현재 {n_now:.5f}",
            f"**표류 {drift:+.3f} %**  ->  KLa 환산 {-3.1*drift:+.2f} % "
            f"(게인 3.1)",
            f"보정계수: fit_kla.py 에 `--scale {scale:.5f}` 를 줄 것"]
    ok = abs(drift) <= tol
    if not ok:
        msgs.append(f"NO-GO: |{drift:+.3f}| > {tol} %. 보정하지 말고 "
                    f"**--scale 로 보정**하십시오 — 재보정하면 C*_ref 프레임이 "
                    f"끊겨 이후 런 전체를 잃습니다. 표류가 2 % 를 넘으면 "
                    f"그때는 재보정 + C*_ref 재측정이 불가피합니다.")
    else:
        msgs.append(f"GO: 표류 {tol} % 이내. --scale 없이 진행 가능 "
                    f"(적용해도 무방).")
    if dT > 0.1:
        msgs.append(f"[주의] 판독 중 dT={dT:.3f} — 비커가 열평형이 아닙니다. "
                    f"표류값이 오염됐을 수 있습니다.")
    return ok, msgs


def gate_baseline(sensor, tol_per100s=0.002, seconds=300):
    """SOP §5.4 함정0 — 주입/런 시작 전 DO 표류."""
    print(f"\n[게이트 baseline] DO 표류 판정 — {seconds/60:.0f}분, "
          f"|기울기| < {tol_per100s} mg/L/100s")
    print("  (2026-08-01: 네 런 모두 주입 전 DO 가 +0.012~+0.022 mg/L/100s 로 "
          "상승 중이었고, 그것 하나로 t95 산출이 무너졌다.)")
    rows = collect(sensor, seconds, label="base ")
    if len(rows) < seconds * 0.7:
        return False, [f"샘플 부족 ({len(rows)})"]
    ts = [r[0] for r in rows]; do = [r[1] for r in rows]; T = [r[3] for r in rows]
    slope = linreg(ts, do)[0] * 100.0            # mg/L per 100 s
    mean = sum(do) / len(do)
    sd = (sum((x - mean) ** 2 for x in do) / (len(do) - 1)) ** 0.5
    slopeT = linreg(ts, T)[0] * 100.0
    msgs = [f"DO {mean:.4f} +- {sd:.4f} mg/L,  기울기 {slope:+.4f} mg/L/100s",
            f"수온 기울기 {slopeT:+.4f} C/100s"]
    ok = abs(slope) < tol_per100s
    if not ok:
        msgs.append(f"NO-GO: |{slope:+.4f}| >= {tol_per100s}. "
                    f"폭기 평형이 덜 됐거나 수온이 움직입니다. 더 기다릴 것.")
    else:
        msgs.append("GO: baseline 평평함.")
    return ok, msgs


def gate_run(sensor, pressure, note, logpath):
    """런 직전 종합 점검."""
    print("\n[게이트 run] 런 직전 종합")
    ok_all = True
    msgs = []

    # 1) 통신
    ok, m = gate_comm(sensor)
    ok_all &= ok
    msgs += ["--- comm ---"] + m

    # 2) 기압 레지스터
    msgs.append("--- 기압 레지스터 ---")
    try:
        reg = sensor.read_u16(REG_PRESSURE) / 100.0
        msgs.append(f"센서 내부 기압 = {reg:.2f} kPa")
        if pressure is not None and abs(reg - pressure) > 0.05:
            ok_all = False
            msgs.append(f"NO-GO: 지정 기압 {pressure:.2f} 와 {reg-pressure:+.2f} kPa "
                        f"불일치. `--set-pressure {pressure}` 를 먼저 실행할 것. "
                        f"감도 ~1 %/kPa 로 C* 에 직접 들어갑니다.")
        elif pressure is None:
            msgs.append("[주의] --pressure 미지정 — 당일 기상청 현지기압과 대조하십시오.")
        else:
            msgs.append("OK: 기압 일치.")
    except Exception as e:
        ok_all = False
        msgs.append(f"NO-GO: 기압 레지스터 읽기 실패 — {e}")

    # 3) --note 필수필드
    msgs.append("--- --note 필수필드 ---")
    miss = validate_note(note)
    if miss:
        ok_all = False
        msgs.append(f"NO-GO: 누락 {', '.join(miss)}. "
                    f"파일럿은 에어스톤 기하를 안 적어 kappa 를 확정하지 못했습니다.")
    else:
        msgs.append(f"OK: {note}")
    if note and "(" not in note:
        msgs.append("[주의] 프로브 위치가 좌표 (x,y,z)[m] 로 안 적혔습니다. "
                    "'장축_코너' 같은 상대 라벨로는 재현도 CFD 대조도 안 됩니다"
                    "(tmix_결과 §5.4).")

    # 4) 파일명 충돌
    msgs.append("--- 출력 파일 ---")
    if logpath:
        if os.path.exists(logpath):
            ok_all = False
            msgs.append(f"NO-GO: {logpath} 이미 존재 — 덮어쓰면 이전 런을 잃습니다.")
        else:
            msgs.append(f"OK: {logpath} (신규)")
    else:
        msgs.append("[주의] --log 미지정 — 파일명 충돌 확인 못 함")

    return ok_all, msgs


# ---------------------------------------------------------------- 기록

def append_log(gate, ok, msgs, extra=""):
    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"\n### {stamp} — 게이트 `{gate}` — "
                f"**{'GO' if ok else 'NO-GO'}**\n\n")
        if extra:
            f.write(f"{extra}\n\n")
        for m in msgs:
            f.write(f"- {m}\n")


def main():
    p = argparse.ArgumentParser(description="EX2 본시험 사전점검 (go/no-go)")
    p.add_argument("--port", required=True)
    p.add_argument("--baud", type=int, default=4800)
    p.add_argument("--addr", type=int, default=1)
    p.add_argument("--gate", required=True,
                   choices=["comm", "calib", "verify", "baseline", "drift",
                            "run", "all"])
    p.add_argument("--pressure", type=float, default=None, help="현지기압 kPa (예 101.0)")
    p.add_argument("--note", default="", help="런 --note (gate run 에서 검증)")
    p.add_argument("--log", default="", help="런 출력 파일명 (gate run 에서 충돌 확인)")
    p.add_argument("--dt-tol", type=float, default=0.05, help="calib 온도 허용 [degC]")
    p.add_argument("--calib-window", type=float, default=180, help="calib 관찰 [s]")
    p.add_argument("--expect-sat", default="99,101",
                   help="verify 허용 포화대역, 쉼표구분 (기본 99,101)")
    p.add_argument("--baseline-tol", type=float, default=0.002,
                   help="baseline 허용 기울기 [mg/L per 100s]")
    p.add_argument("--baseline-window", type=float, default=300, help="baseline 관찰 [s]")
    p.add_argument("--ref-do", type=float, default=None,
                   help="gate drift: S1 시점 100%% 비커 판독 [mg/L]")
    p.add_argument("--ref-T", type=float, default=None,
                   help="gate drift: 그때의 수온 [degC]")
    p.add_argument("--drift-tol", type=float, default=0.5,
                   help="gate drift 허용 표류 [%%] (기본 0.5 -> KLa 1.6%%)")
    p.add_argument("--nolog", action="store_true", help="preflight_log.md 기록 생략")
    a = p.parse_args()

    lo, hi = (float(x) for x in a.expect_sat.split(","))
    s = Sensor(a.port, baud=a.baud, addr=a.addr)
    try:
        if a.gate == "comm":
            ok, msgs = gate_comm(s)
        elif a.gate == "calib":
            ok, msgs = gate_calib(s, a.dt_tol, a.calib_window)
        elif a.gate == "verify":
            if a.pressure is None:
                sys.exit("verify 는 --pressure 필요 (Benson-Krause 대조)")
            ok, msgs = gate_verify(s, a.pressure, lo, hi)
        elif a.gate == "drift":
            if a.ref_do is None or a.ref_T is None or a.pressure is None:
                sys.exit("drift 는 --ref-do --ref-T --pressure 가 모두 필요합니다")
            ok, msgs = gate_drift(s, a.ref_do, a.ref_T, a.pressure,
                                  tol=a.drift_tol)
        elif a.gate == "baseline":
            ok, msgs = gate_baseline(s, a.baseline_tol, a.baseline_window)
        elif a.gate == "run":
            ok, msgs = gate_run(s, a.pressure, a.note, a.log)
        else:  # all
            ok1, m1 = gate_comm(s)
            msgs = ["--- comm ---"] + m1
            ok2 = True
            if a.pressure is not None:
                ok2, m2 = gate_verify(s, a.pressure, lo, hi)
                msgs += ["--- verify ---"] + m2
            else:
                msgs += ["--- verify 생략 (--pressure 미지정) ---"]
            ok = ok1 and ok2
    finally:
        s.close()

    print("\n" + "=" * 66)
    for m in msgs:
        print("  " + m)
    print("=" * 66)
    print(f"  판정: {'GO — 진행하십시오' if ok else 'NO-GO — 위 사유 해소 후 재실행'}")
    print("=" * 66)

    if not a.nolog:
        append_log(a.gate, ok, msgs,
                   extra=(f"`--note`: {a.note}" if a.note else ""))
        print(f"  기록: {LOGFILE}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
