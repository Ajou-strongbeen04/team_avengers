#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 본시험 런너 — 런 하나를 처음부터 끝까지 안내한다.        [2026-08-01]

────────────────────────────────────────────────────────────────────────
 쓰는 법 — 이것만 알면 된다
────────────────────────────────────────────────────────────────────────

  python3 run_ex2.py --port /dev/tty.usbserial-1110 --run S1

  S1 이 끝나면 C*_ref 가 session.json 에 자동 저장되고,
  S2~S5 는 옵션을 하나도 안 줘도 그 값을 알아서 쓴다.

      --run S1   z=0.02  jangchuk   기준런 (평탄부까지, C*_ref 확정)
      --run S2   z=0.02  danchuk    위치
      --run S3   z=0.02  choewon    위치
      --run S4   z=0.08  jangchuk   학습 2수준
      --run S5   z=0.17  jangchuk   hold-out
      --run S6   z=0.02  jangchuk   (선택) 반복 — 재현성 CV 확보용

  부수 명령
      --set-drift-ref     표류 기준물(폭기 켜둔 비커) 판독값 등록
      --check-drift       지금 표류 몇 %인지 + --scale 계산
      --status            session.json 현황
      --refit             이미 받은 CSV 만 다시 피팅

  실행계획: 본시험_실행계획.md 부록 B·C
"""

import argparse
import datetime as _dt
import json
import math
import os
import sys

SESSION = "session.json"

# ── 런 매트릭스 (실행계획 부록 B.3) ─────────────────────────────────
PROBES = {
    "jangchuk": (0.450, 0.035, 0.105),
    "danchuk":  (0.020, 0.175, 0.105),
    "choewon":  (0.450, 0.175, 0.105),
}
MATRIX = {
    "S1": dict(z=0.020, probe="jangchuk", mode="plateau", role="train",
               desc="기준런 — C*_ref 확정 + 학습셋"),
    "S2": dict(z=0.020, probe="danchuk",  mode="tau", role="position",
               desc="위치 강건성"),
    "S3": dict(z=0.020, probe="choewon",  mode="tau", role="position",
               desc="위치 강건성"),
    "S4": dict(z=0.080, probe="jangchuk", mode="tau", role="train",
               desc="학습 2수준"),
    "S5": dict(z=0.170, probe="jangchuk", mode="tau", role="holdout",
               desc="hold-out (레버 36 %) — 전이 잔차"),
    "S6": dict(z=0.020, probe="jangchuk", mode="tau", role="train",
               desc="(선택) 반복 — 재현성 CV"),
}
KLA_CFD = {0.020: 2.604, 0.080: 2.030, 0.170: 0.948}   # 상수_목록 D-1, 3-D
KAPPA0 = 0.928           # 파일럿 잠정 — 시간 예측용일 뿐
THETA = 1.024
N_TAU_RUN = 3.3          # 일반 런 절단 (유효창 상한이 2.53tau 에서 닫힘)
N_TAU_PLATEAU = 5.12     # 기준런: 기울기 0.02 mg/L/10min 도달
PRESSURE = 101.0
NA2SO3_G = 2.0
CO_MG = 30
PLATEAU_TOL = 0.02


# ── 유틸 ────────────────────────────────────────────────────────────

def bk(T_c, P_kpa=PRESSURE):
    """Benson-Krause 담수 포화농도 [mg/L]."""
    T = T_c + 273.15
    ln_c = (-139.34411 + 1.575701e5 / T - 6.642308e7 / T**2
            + 1.243800e10 / T**3 - 8.621949e11 / T**4)
    return math.exp(ln_c) * (P_kpa / 101.325)


def load_session():
    if os.path.exists(SESSION):
        with open(SESSION, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_session(d):
    with open(SESSION, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def hr(title=""):
    print("\n" + "=" * 70)
    if title:
        print(f" {title}")
        print("=" * 70)


def ask(prompt, default_yes=True):
    tail = "[Y/n]" if default_yes else "[y/N]"
    while True:
        a = input(f"  {prompt} {tail} ").strip().lower()
        if not a:
            return default_yes
        if a in ("y", "yes", "ㅛ"):
            return True
        if a in ("n", "no", "ㅜ"):
            return False


def ask_float(prompt, default=None):
    while True:
        d = f" [{default}]" if default is not None else ""
        a = input(f"  {prompt}{d}: ").strip()
        if not a and default is not None:
            return default
        try:
            return float(a)
        except ValueError:
            print("    숫자를 입력하세요.")


def predict(z, T):
    """수온 T 에서 예상 KLa·tau·런 길이."""
    k25 = KLA_CFD[z] * KAPPA0                     # 25.18 C 기준 예상 실측값
    k = k25 * THETA ** (T - 25.18)
    tau = 60.0 / k                                 # 분
    return k, tau


# ── 본체 ────────────────────────────────────────────────────────────

def cmd_status(sess):
    hr("session.json 현황")
    if not sess:
        print("  아직 비어 있습니다. `--run S1` 부터 시작하세요.")
        return
    c = sess.get("cstar_ref")
    if c:
        print(f"  C*_ref      = {c['cstar']:.4f} mg/L @ {c['T']:.2f} C  "
              f"(출처 {c['file']})")
        print(f"  B-K 대조    = {100*c['cstar']/bk(c['T']):.2f} %"
              f"   스팬계수 s = {c.get('span_factor', float('nan')):.5f}")
    else:
        print("  C*_ref 없음 — S1 을 먼저 돌려야 S2~S5 가 무편향으로 나옵니다.")
    d = sess.get("drift_ref")
    if d:
        print(f"  표류 기준물 = {d['do']:.4f} mg/L @ {d['T']:.2f} C")
    else:
        print("  표류 기준물 없음 — `--set-drift-ref` 로 등록 권장")
    done = sess.get("runs", {})
    if done:
        print(f"\n  {'런':<5}{'z':>7}{'프로브':>11}{'KLa[1/h]':>11}"
              f"{'KLa20':>9}{'C*':>9}{'tau배':>8}")
        for k in sorted(done):
            r = done[k]
            print(f"  {k:<5}{r['z']:>7.3f}{r['probe']:>11}"
                  f"{r['kla_1_h']:>11.3f}{r['kla20_1_h']:>9.3f}"
                  f"{r['cstar']:>9.3f}{r['t_end_tau']:>8.2f}")
    left = [k for k in MATRIX if k not in done and k != "S6"]
    print(f"\n  남은 런: {', '.join(left) if left else '없음 — calc_kappa.py 로'}")


def open_sensor(a):
    from do_logger import Sensor
    return Sensor(a.port, baud=a.baud, addr=a.addr)


def quick_read(sensor, n=20):
    """n 회 판독 평균. (do, T, sat, dT)"""
    import time
    do, T, sat = [], [], []
    for i in range(n):
        s_, d_, t_ = sensor.read_all()
        do.append(d_); T.append(t_); sat.append(s_)
        print(f"\r    [{i+1}/{n}] DO {d_:6.3f} 포화 {s_*100:6.2f}% "
              f"{t_:6.2f}C   ", end="", flush=True)
        time.sleep(1.0)
    print()
    return (sum(do)/n, sum(T)/n, sum(sat)/n, max(T)-min(T))


def cmd_set_drift_ref(a, sess):
    hr("표류 기준물 등록")
    print("  프로브를 **에어펌프를 계속 돌리는 소형 비커**에 넣으세요.")
    print("  (수온이 변해도 항상 평형을 추종하므로 17 h 기준물로 적합합니다)")
    if not ask("준비됐습니까?"):
        return
    s = open_sensor(a)
    try:
        do, T, sat, dT = quick_read(s, 60)
    finally:
        s.close()
    print(f"\n  평균 {do:.4f} mg/L @ {T:.2f} C  (dT={dT:.3f})  "
          f"B-K 대조 {100*do/bk(T):.2f} %")
    if dT > 0.1:
        print("  [주의] dT > 0.1 — 비커가 열평형이 아닙니다. 값이 오염될 수 있습니다.")
    sess["drift_ref"] = {"do": do, "T": T,
                         "at": _dt.datetime.now().isoformat(timespec="seconds")}
    save_session(sess)
    print(f"  → session.json 에 저장. 이후 `--check-drift` 로 감시합니다.")


def cmd_check_drift(a, sess):
    d = sess.get("drift_ref")
    if not d:
        sys.exit("표류 기준물이 없습니다. 먼저 `--set-drift-ref`")
    hr("표류 점검")
    print("  프로브를 표류 기준물(폭기 비커)에 넣으세요.")
    if not ask("준비됐습니까?"):
        return None
    s = open_sensor(a)
    try:
        do, T, sat, dT = quick_read(s, 40)
    finally:
        s.close()
    n_ref = d["do"] / bk(d["T"])
    n_now = do / bk(T)
    drift = 100 * (n_now / n_ref - 1.0)
    scale = n_ref / n_now
    print(f"\n  기준 {d['do']:.4f} @ {d['T']:.2f} C  →  현재 {do:.4f} @ {T:.2f} C")
    print(f"  **표류 {drift:+.3f} %**   →  KLa 환산 {-3.1*drift:+.2f} % (게인 3.1)")
    print(f"  보정계수 --scale {scale:.5f}")
    if abs(drift) > 2.0:
        print("  🔴 2 % 초과 — 재보정 + C*_ref 재측정이 불가피합니다.")
    elif abs(drift) > 0.5:
        print("  ⚠ 0.5 % 초과 — **재보정하지 말고** --scale 로 보정하십시오.")
    else:
        print("  ✅ 0.5 % 이내 — 그대로 진행.")
    sess["last_scale"] = scale
    save_session(sess)
    return scale


def analyze(path, cstar_ref=None, cstar_ref_T=None, scale=1.0, plot=True):
    """fit_kla.py v2 를 그대로 호출."""
    import fit_kla
    return fit_kla.analyze(
        path, None, 5.0, 0.15, 0.92, False, plot,
        cstar_ref=cstar_ref, cstar_ref_T=cstar_ref_T,
        pressure=PRESSURE, scale=scale,
        events_path=None, t0_event="aeration", plateau_tol=PLATEAU_TOL)


def cmd_run(a, sess):
    key = a.run.upper()
    if key not in MATRIX:
        sys.exit(f"--run 은 {', '.join(MATRIX)} 중 하나")
    spec = MATRIX[key]
    z, probe, mode = spec["z"], spec["probe"], spec["mode"]
    xyz = PROBES[probe]
    csv_path = a.log or f"run_{key}.csv"

    hr(f"{key} — {spec['desc']}")
    print(f"  z_start   = {z:.3f} m")
    print(f"  프로브    = {probe} (x,y,z) = ({xyz[0]:.3f}, {xyz[1]:.3f}, {xyz[2]:.3f}) m")
    print(f"  종료      = " + ("평탄부 (기울기 < 0.02 mg/L/10min, 포화도 기준)"
                               if mode == "plateau" else f"{N_TAU_RUN} tau"))
    print(f"  출력      = {csv_path}")

    if os.path.exists(csv_path) and not a.overwrite:
        sys.exit(f"\n[중단] {csv_path} 이미 존재. 다른 --log 또는 --overwrite")

    # C*_ref 확인
    cref = sess.get("cstar_ref")
    if mode == "plateau":
        print("\n  이 런은 C*_ref 를 만드는 런입니다 (자유 피팅).")
        if cref:
            print(f"  [주의] session.json 에 이미 C*_ref 가 있습니다 "
                  f"({cref['cstar']:.4f} @ {cref['T']:.2f} C). 덮어씁니다.")
    else:
        if not cref:
            print("\n  🔴 C*_ref 가 없습니다. S1 을 먼저 돌리지 않으면 절단 편향이")
            print("     +5 % 들어갑니다(실행계획 §2.2).")
            if not ask("그래도 진행합니까?", default_yes=False):
                sys.exit("중단")
        else:
            print(f"\n  C*_ref    = {cref['cstar']:.4f} mg/L @ {cref['T']:.2f} C "
                  f"(S1 에서 확정)")
    scale = a.scale if a.scale is not None else sess.get("last_scale", 1.0)
    if abs(scale - 1.0) > 1e-6:
        print(f"  스팬 보정 = --scale {scale:.5f} (표류 점검 결과)")

    # ── 하드웨어 체크리스트
    hr("준비 확인 — 하나라도 아니면 지금 맞추세요")
    checks = [
        f"에어스톤을 z_start = {z*1000:.0f} mm 에 고정했고, 자로 재서 확인했습니까?",
        f"프로브를 {probe} = ({xyz[0]*1000:.0f}, {xyz[1]*1000:.0f}, "
        f"{xyz[2]*1000:.0f}) mm 에 고정했습니까? (벽·바닥에 안 닿게)",
        "수조에 물 20.7 L (수심 210 mm) 채웠습니까?",
        "**폭기 OFF** 상태입니까?",
        f"Na2SO3 {NA2SO3_G} g 과 CoCl2·6H2O {CO_MG} mg 을 미리 칭량했습니까?",
        "장갑·보안경 착용, 폐액통 준비됐습니까?",
    ]
    for c in checks:
        if not ask(c):
            sys.exit("  → 맞춘 뒤 다시 실행하세요.")
    z_meas = ask_float("실측 z_start [mm]", z * 1000)

    # ── 통신 · 기압
    hr("통신 · 기압 확인")
    from do_logger import REG_PRESSURE
    s = open_sensor(a)
    try:
        do0, T0, sat0, dT0 = quick_read(s, 15)
        preg = s.read_u16(REG_PRESSURE) / 100.0
        print(f"\n  현재 수조: DO {do0:.3f} mg/L, 포화 {sat0*100:.2f} %, "
              f"수온 {T0:.2f} C")
        print(f"  센서 기압 레지스터 = {preg:.2f} kPa")
        if abs(preg - PRESSURE) > 0.05:
            print(f"  🔴 지정 {PRESSURE} 와 {preg-PRESSURE:+.2f} kPa 불일치 — "
                  f"`do_logger.py --set-pressure {PRESSURE}` 를 먼저 실행하세요.")
            if not ask("무시하고 진행합니까?", default_yes=False):
                sys.exit("중단")

        k, tau = predict(z, T0)
        n_tau = N_TAU_PLATEAU if mode == "plateau" else N_TAU_RUN
        log_min = n_tau * tau
        print(f"\n  예상 (수온 {T0:.1f} C): KLa ≈ {k:.3f} /h, tau ≈ {tau:.1f} 분")
        print(f"  → 로깅 {log_min:.0f} 분 ({n_tau} tau)  "
              f"+ 탈산소·안정 34분  = 런당 약 {(log_min+34)/60:.1f} h")

        note = (f"{key}, z_start={z:.3f}(실측 {z_meas:.0f}mm), "
                f"pos={probe}({xyz[0]:.3f},{xyz[1]:.3f},{xyz[2]:.3f}), "
                f"Na2SO3 {NA2SO3_G}g, Co {CO_MG}mg, "
                f"T={T0:.2f}C, P={PRESSURE}kPa, role={spec['role']}")
        print(f"\n  --note: {note}")

        # ── 진행 안내
        hr("로깅 시작 — 지금부터 끝까지 창을 닫지 마세요")
        print("  ① 시작하면 2~3분 baseline 이 기록됩니다. 그냥 두세요.")
        print(f"  ② Na2SO3 {NA2SO3_G} g + Co {CO_MG} mg 투입 · 교반 30초")
        print("     → 투입하는 순간 터미널에   na2so3_in  을 **타이핑**하고 Enter")
        print("     🔴 빈 Enter 를 치면 안 됩니다 (t0 가 어긋납니다)")
        print("  ③ DO 가 0 으로 떨어지는 것 확인(~14분) → **20분 더 대기**")
        print("  ④ 폭기 ON — 켜는 순간 **빈 Enter** (= aeration_on = t0)")
        print("  ⑤ 그 뒤 아무것도 하지 않습니다. 처음 5분은 DO 가 안 오릅니다(정상).")
        if mode == "plateau":
            print(f"     기울기 < {PLATEAU_TOL} 이면 자동 종료 (약 {log_min:.0f}분)")
        else:
            print(f"     {N_TAU_RUN} tau 경과 시 자동 종료 (약 {log_min:.0f}분)")
        print("  ⑥ 종료되면 이 스크립트가 자동으로 피팅까지 합니다.")
        if not ask("\n  시작합니까?"):
            sys.exit("중단")

        import do_logger
        do_logger.do_log(
            s, csv_path, interval=1.0, note=note, duration=a.duration,
            mark=True,
            stop_at_tau=None if mode == "plateau" else N_TAU_RUN,
            stop_on_plateau=PLATEAU_TOL if mode == "plateau" else None,
            plateau_tail=600.0, overwrite=True, plateau_on="sat")
    finally:
        s.close()

    # ── 자동 피팅
    hr(f"{key} 피팅")
    try:
        if mode == "plateau":
            res = analyze(csv_path, scale=scale)
        else:
            res = analyze(csv_path, cstar_ref=cref["cstar"],
                          cstar_ref_T=cref["T"], scale=scale)
    except Exception as e:
        print(f"  [피팅 실패] {e}")
        print(f"  원자료는 {csv_path} 에 있습니다. 수동으로:")
        print(f"    python3 fit_kla.py {csv_path} --pressure {PRESSURE}")
        return

    # ── 판정
    hr(f"{key} 판정")
    ratio = 100 * res["cstar_mgL"] / res["cstar_bk_mgL"]
    ok = True
    print(f"  KLa      = {res['kla_1_h']:.4f} /h   (KLa20 = {res['kla20_1_h']:.4f})")
    print(f"  tau      = {res['tau_min']:.1f} 분")
    print(f"  C*       = {res['cstar_mgL']:.4f} mg/L  ({res['cstar_source']})")
    print(f"  B-K 대조 = {ratio:.2f} %")
    print(f"  기록     = {res['t_end_tau']:.2f} tau,  말미 기울기 "
          f"{res['slope_tail_mgL_10min']:+.4f}")
    print(f"  RMSE     = {res['rmse_mgL']:.4f} mg/L")

    if mode == "plateau":
        if res["t_end_tau"] < 5.0:
            print(f"\n  🔴 기록이 {res['t_end_tau']:.2f} tau — 5.0 미달. "
                  f"평탄부 미도달이므로 C* 를 쓸 수 없습니다.")
            ok = False
        if abs(res["slope_tail_mgL_10min"]) > PLATEAU_TOL * 1.5:
            print(f"\n  🔴 말미 기울기 {res['slope_tail_mgL_10min']:+.4f} — "
                  f"평탄 아님.")
            ok = False
        span = 1.003 / (ratio / 100.0)
        if ratio > 101.0:
            print(f"\n  ⚠ B-K 대조 {ratio:.2f} % > 101 — 스팬이 높게 박혀 있습니다.")
            print(f"     **재보정하지 마십시오.** KLa·kappa 에서는 상쇄됩니다"
                  f"(실행계획 §2.3 규칙 2).")
            print(f"     절대 DO·dC* 보고용 스팬계수 s = {span:.5f} "
                  f"(이 값은 --cstar-ref 에 곱하지 **않습니다**)")
        elif ratio < 98.0:
            print(f"\n  🔴 B-K 대조 {ratio:.2f} % < 98 — 평탄부 미도달이 아니라면")
            print(f"     스팬이 낮게 박힌 것입니다. 재보정 + S1 재실행을 검토하세요.")
            ok = False
        else:
            print(f"\n  ✅ B-K 대조 정상 (98–101 %)")

        if ok:
            sess["cstar_ref"] = {"cstar": res["cstar_mgL"], "T": res["T_mean_C"],
                                 "file": os.path.basename(csv_path),
                                 "bk_ratio_pct": ratio, "span_factor": span}
            print(f"\n  ✅ C*_ref = {res['cstar_mgL']:.4f} mg/L @ "
                  f"{res['T_mean_C']:.2f} C  → session.json 에 저장")
            print(f"     S2~S5 는 이 값을 자동으로 씁니다. 따로 적을 필요 없습니다.")
        else:
            print(f"\n  ❌ C*_ref 로 채택하지 않았습니다. 위 사유를 해소하고 재실행.")
    else:
        if res["truncated"]:
            print(f"\n  🔴 유효창이 잘렸습니다 — 기록을 늘리거나 --hi 를 낮춰야 합니다.")
            ok = False
        elif res["t_end_tau"] < 2.6:
            print(f"\n  🔴 기록 {res['t_end_tau']:.2f} tau — 유효창 상한(2.53) 여유 없음.")
            ok = False
        else:
            print(f"\n  ✅ 유효창 정상")
        kap = res["kla_1_h"] / KLA_CFD[z]
        print(f"  kappa (잠정) = {kap:.4f}   [CFD {KLA_CFD[z]:.3f} /h 대비]")

    sess.setdefault("runs", {})[key] = {
        "z": z, "probe": probe, "role": spec["role"],
        "file": os.path.basename(csv_path), "z_meas_mm": z_meas,
        "kla_1_h": res["kla_1_h"], "kla20_1_h": res["kla20_1_h"],
        "cstar": res["cstar_mgL"], "cstar_source": res["cstar_source"],
        "T_mean_C": res["T_mean_C"], "t_end_tau": res["t_end_tau"],
        "rmse_mgL": res["rmse_mgL"], "scale": scale,
        "at": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    save_session(sess)
    write_runs_csv(sess)

    # ── 다음 단계
    hr("다음")
    if mode == "plateau" and ok:
        print("  1) 프로브를 폭기 켜둔 비커로 옮기고:")
        print(f"       python3 run_ex2.py --port {a.port} --set-drift-ref")
        print("  2) 물 교체 후 다음 런:")
        print(f"       python3 run_ex2.py --port {a.port} --run S2")
    else:
        order = ["S1", "S2", "S3", "S4", "S5"]
        done = sess.get("runs", {})
        nxt = next((k for k in order if k not in done), None)
        if nxt:
            print(f"  물 교체 후:")
            print(f"       python3 run_ex2.py --port {a.port} --check-drift")
            print(f"       python3 run_ex2.py --port {a.port} --run {nxt}")
        else:
            print("  전 런 완료. 종합:")
            print(f"       python3 calc_kappa.py summary_meas.csv runs.csv "
                  f"--out kappa_결과.csv")
            print("  (summary_meas.csv 는 아래로 생성)")
            print(f"       python3 fit_kla.py \"run_S*.csv\" --pressure {PRESSURE} \\")
            c = sess["cstar_ref"]
            print(f"           --cstar-ref {c['cstar']:.4f} --cstar-ref-T "
                  f"{c['T']:.2f} --summary summary_meas.csv")


def write_runs_csv(sess):
    """calc_kappa.py 입력용 runs.csv 자동 생성."""
    import csv
    rows = []
    for k in sorted(sess.get("runs", {})):
        r = sess["runs"][k]
        rows.append({"file": r["file"], "run": k, "z_start": r["z"],
                     "probe": r["probe"], "role": r["role"]})
    if not rows:
        return
    with open("runs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "run", "z_start", "probe", "role"])
        w.writeheader(); w.writerows(rows)
    print(f"\n  runs.csv 갱신 ({len(rows)}런)")


def cmd_refit(a, sess):
    hr("재피팅")
    cref = sess.get("cstar_ref")
    for key in sorted(sess.get("runs", {})):
        r = sess["runs"][key]
        p = r["file"]
        if not os.path.exists(p):
            print(f"  [skip] {p} 없음"); continue
        if r["cstar_source"] == "fit":
            analyze(p, scale=r.get("scale", 1.0))
        elif cref:
            analyze(p, cstar_ref=cref["cstar"], cstar_ref_T=cref["T"],
                    scale=r.get("scale", 1.0))


def main():
    p = argparse.ArgumentParser(
        description="EX2 본시험 런너 — 런 하나를 처음부터 끝까지 안내",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="예:  python3 run_ex2.py --port /dev/tty.usbserial-1110 --run S1")
    p.add_argument("--port", help="예 /dev/tty.usbserial-1110")
    p.add_argument("--baud", type=int, default=4800)
    p.add_argument("--addr", type=int, default=1)
    p.add_argument("--run", help=f"{', '.join(MATRIX)} 중 하나")
    p.add_argument("--log", help="출력 CSV (기본 run_<런>.csv)")
    p.add_argument("--scale", type=float, default=None,
                   help="스팬 보정계수 (미지정 시 --check-drift 결과 자동 사용)")
    p.add_argument("--duration", type=float, default=12000,
                   help="안전 백스톱 [s] (기본 12000 = 200분)")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--set-drift-ref", action="store_true",
                   help="표류 기준물(폭기 비커) 판독값 등록")
    p.add_argument("--check-drift", action="store_true",
                   help="지금 표류 몇 %% 인지 + --scale 계산")
    p.add_argument("--status", action="store_true", help="session.json 현황")
    p.add_argument("--refit", action="store_true", help="받은 CSV 만 다시 피팅")
    a = p.parse_args()

    sess = load_session()

    if a.status:
        cmd_status(sess); return
    if a.refit:
        cmd_refit(a, sess); return
    if not a.port:
        p.error("--port 가 필요합니다")
    if a.set_drift_ref:
        cmd_set_drift_ref(a, sess); return
    if a.check_drift:
        cmd_check_drift(a, sess); return
    if a.run:
        cmd_run(a, sess); return
    p.print_help()


if __name__ == "__main__":
    main()
