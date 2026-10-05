#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 재폭기 시험 — 단일지수 피팅으로 K_La_eff, C* 산출   [v2 · 2026-08-01]

모델 (EX2_방법론.md §2):
    dC/dt = KLa (C* - C)   =>   C(t) = C* - (C* - C0) exp(-KLa * t)

유효창: 방법론 §2 — C_frac(t) = (C(t)-C_min)/(C_ref-C_min) 로 lo(0.15)~hi(0.92) 절단.

────────────────────────────────────────────────────────────────────────
v2 변경점 (2026-08-01) — 전부 하위호환. 옵션을 안 주면 v1과 동일 동작.
────────────────────────────────────────────────────────────────────────
 (1) --cstar-ref : **절단 편향 제거.** v1은 C_ref 를 "관측 말미 중앙값"으로
     잡아 유효창을 정규화했다. 평탄부에 못 닿은 런은 창 자체가 어긋나
     KLa 까지 오염된다. 파일럿 원자료(pilot_deox.csv) 실측 편향:

         절단      자유피팅(v1)     --cstar-ref(v2)
         2.5 tau    +8.45 %          -0.22 %
         3.0 tau    +5.39 %          -0.14 %
         4.0 tau    +2.05 %          -0.14 %
         5.0 tau    +0.75 %          -0.14 %

     기준런(평탄부까지 완주) 1회에서 C* 를 확정하고, 나머지 런은
     --cstar-ref 로 그 값을 주입하면 3.3 tau 로 끊어도 편향이 없다.
     (유효창 상한 0.92 는 -ln(0.08)=2.53 tau 에서 닫히므로 그 이후
      데이터는 애초에 피팅에 쓰이지 않는다.)

 (2) 온도 전이 : C*(T_run) = C*_ref * BK(T_run)/BK(T_ref).  --cstar-ref-T

 (3) --events : do_logger.py v2 이벤트 sidecar 에서 t0 자동 취득.
     "폭기 ON 시각 벽시계 받아적기"를 없앤다.

 (4) KLa20 = KLa * theta^(20-T), theta=1.024. 런 간 수온차가 있으면 이걸로 비교.

 (5) 절단 진단 · (6) --scale (스팬 편향. 파일럿 0.95476)

사용
    python3 fit_kla.py run_R1.csv                                   # 기준런(C* 확정)
    python3 fit_kla.py run_R2.csv --cstar-ref 8.336 --cstar-ref-T 25.18
    python3 fit_kla.py "run_*.csv" --cstar-ref 8.336 --cstar-ref-T 25.18 \
            --pressure 101.0 --summary summary_meas.csv
"""

import argparse
import csv
import glob
import os
import sys

import numpy as np

try:
    from scipy.optimize import curve_fit
except ImportError:
    sys.exit("scipy 필요:  pip install scipy")


THETA_DEFAULT = 1.024      # Arrhenius 온도보정 계수 (ASCE 청수시험 관례)


# ---------------------------------------------------------------- 입출력

def load_csv(path):
    t, do, temp = [], [], []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#") or row[0] == "iso_time":
                continue
            try:
                t.append(float(row[1]))
                do.append(float(row[2]))
                temp.append(float(row[4]))
            except (ValueError, IndexError):
                continue
    if not t:
        raise ValueError(f"{path}: 유효 데이터 행 없음")
    return np.array(t), np.array(do), np.array(temp)


def load_events(path):
    """do_logger.py v2 이벤트 sidecar → [(t_sec, label), ...]"""
    out = []
    if not path or not os.path.exists(path):
        return out
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#") or row[0] == "iso_time":
                continue
            try:
                out.append((float(row[1]), row[2].strip()))
            except (ValueError, IndexError):
                continue
    return out


def auto_events_path(csv_path):
    return os.path.splitext(csv_path)[0] + "_events.csv"


def pick_event(events, key):
    """label 에 key(쉼표구분 가능) 가 포함된 마지막 이벤트의 t_sec. 없으면 None."""
    keys = [k.strip().lower() for k in str(key).split(",") if k.strip()]
    hits = [t for t, lab in events
            if any(k in lab.lower() for k in keys)]
    return hits[-1] if hits else None


def moving_average(t, y, window_s):
    """비균일 시간축 대응 이동평균 (window_s 초 폭). 누적합 기반 O(n)."""
    if window_s <= 0:
        return y.copy()
    order = np.argsort(t, kind="stable")
    ts, ys = t[order], y[order]
    cs = np.concatenate([[0.0], np.cumsum(ys)])
    half = window_s / 2.0
    lo = np.searchsorted(ts, ts - half, side="left")
    hi = np.searchsorted(ts, ts + half, side="right")
    out_sorted = (cs[hi] - cs[lo]) / np.maximum(hi - lo, 1)
    out = np.empty_like(y, dtype=float)
    out[order] = out_sorted
    return out


# ---------------------------------------------------------------- 물리

def benson_krause_cstar(T_c, P_kpa=101.325):
    """담수 산소 포화농도 [mg/L] — Benson & Krause (APHA 표준식) [R14]."""
    T = T_c + 273.15
    ln_c = (-139.34411
            + 1.575701e5 / T
            - 6.642308e7 / T**2
            + 1.243800e10 / T**3
            - 8.621949e11 / T**4)
    c0 = np.exp(ln_c)                      # 1 atm 기준 mg/L
    return c0 * (P_kpa / 101.325)          # 기압 선형보정 (수증기압 무시, <0.5%)


def model(t, cstar, kla, c0):
    return cstar - (cstar - c0) * np.exp(-kla * t)


def kla20(kla, T_c, theta=THETA_DEFAULT):
    """Arrhenius 20 degC 환산."""
    return kla * theta ** (20.0 - T_c)


# ---------------------------------------------------------------- 피팅

def fit_window(t, c, lo, hi, c_ref=None):
    """유효창 마스크 산출. 반환 (mask, c_min, c_top, truncated)."""
    c_min = np.percentile(c[: max(3, len(c) // 50)], 50)      # 초반부 중앙값
    c_plateau = np.percentile(c[-max(3, len(c) // 20):], 50)  # 말미 중앙값
    c_top = c_plateau if c_ref is None else c_ref
    span = c_top - c_min
    if span <= 0:
        raise ValueError("상승이 없음 — 곡선/시각/C*_ref 확인")
    frac = (c - c_min) / span
    mask = (frac >= lo) & (frac <= hi)
    idx = np.where(mask)[0]
    if len(idx) < 10:
        raise ValueError(
            f"유효창 내 점 부족 ({len(idx)}개) — lo/hi 또는 --cstar-ref 확인 "
            f"(도달 최대 frac = {frac.max():.3f})")
    mask = np.zeros_like(mask)
    mask[idx[0]: idx[-1] + 1] = True
    truncated = bool(frac[-1] < hi)   # 창 상한 전에 데이터가 끝남
    return mask, c_min, c_top, truncated


def gap_report(t, expect_dt=1.0, gap_th=5.0):
    """로깅 공백 통계. 반환 (n_gap, lost_s, lost_frac, biggest_s)."""
    if len(t) < 3:
        return 0, 0.0, 0.0, 0.0
    d = np.diff(t)
    big = d[d > gap_th]
    lost = float(big.sum() - gap_th * len(big)) if len(big) else 0.0
    span = float(t[-1] - t[0])
    return len(big), lost, (lost / span if span > 0 else 0.0), \
        (float(big.max()) if len(big) else 0.0)


def fit_one(t, c, lo, hi, cstar_fixed=None, cstar_mode="window",
            time_weight=False):
    """cstar_fixed 사용 방식 (2026-08-01 S1 실측으로 확정):

      cstar_mode="window" (기본, **규약 C**)
          유효창 정규화에만 참 점근값을 쓰고 모델 C* 는 자유.
          절단 면역 + 모델 적합도 유지. 파일럿 절단시험:
            3.0tau -0.25 % / 3.3tau -0.90 % / 5.0tau -0.90 % (평탄)
          장기록 자유피팅과 0.9 % 내 일치.

      cstar_mode="fix" (구 규약 B)
          모델 C* 까지 고정. 절단 면역이지만 곡선이 이중지수라
          RMSE 가 3배 나빠지고 KLa 가 -11 % 어긋난다. 진단용으로만.

      cstar_fixed=None -> 규약 A (v1 자유 피팅). 절단 시 +4~8 % 편향.
    """
    mask, c_min, c_top, truncated = fit_window(t, c, lo, hi, cstar_fixed)
    _tw_full = t
    if cstar_fixed is not None and cstar_mode == "window":
        cstar_fixed = None          # 창 정규화에만 썼고 모델은 자유
    tw, cw = t[mask], c[mask]
    tw = tw - tw[0]
    # 시간가중: 각 점의 국소 시간간격을 가중치로 (공백 구간의 저대표성 보정).
    # 보간으로 없는 데이터를 만들지 않고 가중만 고친다 — 2026-08-01 S2.
    sig = None
    if time_weight and len(tw) > 3:
        dtl = np.maximum(np.gradient(tw), 1e-9)
        sig = 1.0 / np.sqrt(dtl)

    if cstar_fixed is None:
        p0 = [c_top, 1.0 / max(tw[-1] / 3.0, 1e-3), cw[0]]
        bounds = ([c_top * 0.5, 1e-6, -1.0], [c_top * 2.0 + 5.0, 1.0, c_top])
        popt, pcov = curve_fit(model, tw, cw, p0=p0, bounds=bounds,
                               sigma=sig, absolute_sigma=False, maxfev=20000)
        cstar, kla, c0 = popt
        perr = np.sqrt(np.diag(pcov))
        cstar_se, kla_se = float(perr[0]), float(perr[1])
        cstar_source = "fit"
    else:
        cs_fix = float(cstar_fixed)

        def f(tt, kla_, c0_):
            return cs_fix - (cs_fix - c0_) * np.exp(-kla_ * tt)

        p0 = [1.0 / max(tw[-1] / 3.0, 1e-3), cw[0]]
        popt, pcov = curve_fit(f, tw, cw, p0=p0,
                               bounds=([1e-6, -1.0], [1.0, cs_fix]),
                               sigma=sig, absolute_sigma=False, maxfev=20000)
        kla, c0 = popt
        cstar = cs_fix
        perr = np.sqrt(np.diag(pcov))
        kla_se, cstar_se = float(perr[0]), 0.0
        cstar_source = "ref"

    resid = cw - model(tw, cstar, kla, c0)
    rmse = float(np.sqrt(np.mean(resid**2)))
    return {
        "cstar": float(cstar), "kla": float(kla), "c0": float(c0),
        "cstar_se": cstar_se, "kla_se": kla_se,
        "cstar_source": cstar_source,
        "rmse": rmse, "n": int(mask.sum()),
        "t_window": (float(t[mask][0]), float(t[mask][-1])),
        "c_min": float(c_min),
        "c_plateau_obs": float(np.percentile(c[-max(3, len(c) // 20):], 50)),
        "truncated": truncated,
        "mask": mask,
    }


def plateau_slope(t, c, tail_s=600.0, min_density=0.2):
    """말미 tail_s 초의 선형 기울기 [mg/L per 10 min]. 종료기준 판정용.

    min_density: 창 안 점밀도(점/초) 하한. 로깅 공백(절전 등)으로 창이
    희박하면 회귀가 허수를 낸다 — 2026-08-01 S1_re 에서 +0.355 mg/L/10min
    라는 물리적으로 불가능한 값이 이 이유로 나왔다.
    """
    m = t >= (t[-1] - tail_s)
    if m.sum() < 5 or m.sum() / tail_s < min_density:
        return float("nan")
    a = np.polyfit(t[m], c[m], 1)[0]      # mg/L per s
    return float(a * 600.0)


# ---------------------------------------------------------------- 본체

def analyze(path, t0, smooth, lo, hi, sweep, plot, cstar_ref=None,
            cstar_ref_T=None, pressure=None, theta=THETA_DEFAULT,
            scale=1.0, events_path=None, t0_event="aeration,rise",
            plateau_tol=0.02, cstar_mode="window", basis="do",
            time_weight=False):
    t_raw, do_raw, temp = load_csv(path)
    if scale != 1.0:
        do_raw = do_raw * scale

    # ── 폭기 ON 기준 시각: 명시 > 이벤트 > DO 최저점
    t0_src = "지정"
    if t0 is None:
        ev_path = events_path or auto_events_path(path)
        ev = load_events(ev_path)
        t0 = pick_event(ev, t0_event)
        if t0 is not None:
            t0_src = f"이벤트 '{t0_event}' ({os.path.basename(ev_path)})"
    if t0 is None:
        t0 = float(t_raw[int(np.argmin(do_raw))])
        t0_src = "DO 최저점 자동추정"

    keep = t_raw >= t0
    t = t_raw[keep] - t0
    c = do_raw[keep]
    T_mean = float(np.mean(temp[keep]))
    T_sd = float(np.std(temp[keep]))
    P = pressure if pressure is not None else 101.325

    # ── C*_ref 온도 전이
    cstar_used = None
    ref_note = ""
    if cstar_ref is not None:
        if cstar_ref_T is not None and abs(cstar_ref_T - T_mean) > 1e-6:
            fac = benson_krause_cstar(T_mean, P) / benson_krause_cstar(cstar_ref_T, P)
            cstar_used = cstar_ref * fac
            ref_note = (f"  (기준 {cstar_ref:.3f} @ {cstar_ref_T:.2f} C "
                        f"→ x{fac:.4f} → {cstar_used:.3f} @ {T_mean:.2f} C)")
        else:
            cstar_used = cstar_ref
            ref_note = "  (온도 환산 없음)"

    # ── basis: sat 이면 포화도 S = DO/C*_BK(T,P) 로 피팅 (C*(T) 이동 상쇄)
    if basis == "sat":
        bkv = np.array([benson_krause_cstar(x, P) for x in temp[keep]])
        c_fit = c / bkv
        cstar_fit = None if cstar_used is None else cstar_ref / benson_krause_cstar(
            cstar_ref_T if cstar_ref_T is not None else T_mean, P)
        ref_note += "  [basis=sat]"
    else:
        c_fit, cstar_fit = c, cstar_used

    c_s = moving_average(t, c_fit, smooth)
    r = fit_one(t, c_s, lo, hi, cstar_fit, cstar_mode, time_weight)
    if basis == "sat":       # 보고는 mg/L 로 되돌린다
        f_bk = benson_krause_cstar(T_mean, P)
        for k in ("cstar", "c0", "c_min", "c_plateau_obs", "rmse", "cstar_se"):
            r[k] = r[k] * f_bk
        c_s = c_s * f_bk

    cstar_bk = benson_krause_cstar(T_mean, P)
    tau = 1.0 / r["kla"]
    t_end_tau = t[-1] / tau
    slope10 = plateau_slope(t, c_s)
    k20 = kla20(r["kla"], T_mean, theta)

    print(f"\n=== {os.path.basename(path)} ===")
    print(f"  데이터        : {len(t_raw)}점, t0(폭기ON) = {t0:.1f}s [{t0_src}], "
          f"평활 {smooth:.0f}s" + (f", 스케일 x{scale}" if scale != 1.0 else ""))
    print(f"  수온          : {T_mean:.2f} +- {T_sd:.2f} degC   기압 {P:.2f} kPa")
    conv = ("A 자유피팅" if cstar_used is None else
            ("C 창만 정규화(권장)" if cstar_mode == "window" else "B 모델C*고정"))
    print(f"  피팅 규약     : {conv}{ref_note}")
    print(f"  유효창        : frac {lo:.2f}-{hi:.2f} -> t {r['t_window'][0]:.0f}"
          f"-{r['t_window'][1]:.0f}s, {r['n']}점")
    print(f"  K_La_eff      : {r['kla']:.5e} 1/s  (+- {r['kla_se']:.1e}) "
          f"= {r['kla']*3600:.3f} 1/h,  tau = {tau/60:.1f} min")
    print(f"  K_La(20 degC) : {k20*3600:.3f} 1/h   (theta={theta}, "
          f"보정 x{theta**(20.0-T_mean):.4f})")
    if r["cstar_source"] == "fit":
        print(f"  C* (fit)      : {r['cstar']:.3f} mg/L  (+- {r['cstar_se']:.3f})")
    else:
        print(f"  C* (ref 고정) : {r['cstar']:.3f} mg/L")
    print(f"  C* (B-K,{T_mean:.1f}C): {cstar_bk:.3f} mg/L  "
          f"-> dC* = {r['cstar']-cstar_bk:+.3f} mg/L "
          f"({100*(r['cstar']-cstar_bk)/cstar_bk:+.1f}%)")
    print(f"  피팅 RMSE     : {r['rmse']:.4f} mg/L "
          f"({100*r['rmse']/max(r['cstar']-r['c_min'],1e-9):.2f}% of span)")
    print(f"  기록 길이     : {t[-1]/60:.0f} min = {t_end_tau:.2f} tau   "
          f"말미10분 기울기 {slope10:+.4f} mg/L/10min")
    ng, lost, lostf, gmax = gap_report(t_raw)
    if ng:
        print(f"  로깅 공백     : {ng}개, 결손 {lost/60:.1f} min "
              f"({100*lostf:.1f} %), 최대 {gmax:.0f} s"
              + ("  [--time-weight 적용]" if time_weight else ""))

    # ── 진단
    warn = []
    if r["truncated"]:
        warn.append(f"유효창 상한 {hi:.2f} 도달 전에 데이터가 끝났다(창이 잘림). "
                    f"KLa 가 편향된다 — 기록을 늘리거나 --hi 를 낮출 것.")
    if t_end_tau < 2.6:
        warn.append(f"기록이 {t_end_tau:.2f} tau — 유효창 상한이 닫히는 2.53 tau 에 "
                    f"여유가 없다. 최소 3.0 tau (권장 3.3) 로 잡을 것.")
    if cstar_used is None and abs(slope10) > plateau_tol:
        warn.append(f"평탄부 미도달(|기울기| {abs(slope10):.3f} > {plateau_tol}) 인데 "
                    f"C* 를 자유 피팅했다 -> 절단 편향. 기준런 C* 를 --cstar-ref 로 줄 것.")
    if cstar_used is not None and abs(slope10) <= plateau_tol:
        d = 100 * (r["c_plateau_obs"] - r["cstar"]) / r["cstar"]
        if abs(d) > 1.0:
            warn.append(f"평탄부에 도달했는데 관측 평탄값({r['c_plateau_obs']:.3f})이 "
                        f"주입한 C*_ref 와 {d:+.1f}% 어긋난다 — C*_ref 재검토.")
    if ng and lostf > 0.10 and not time_weight:
        warn.append(f"로깅 공백이 기록의 {100*lostf:.1f} % — 최소제곱 가중이 "
                    f"데이터 있는 구간으로 쏠린다. `--time-weight` 로 민감도를 "
                    f"확인할 것 (보간은 하지 말 것: 곡률 구간을 직선으로 이어 "
                    f"오히려 오차를 넣는다).")
    if T_sd > 0.3:
        warn.append(f"런 중 수온 표류 SD {T_sd:.2f} degC — C*(T)/k_L(T) 오염. "
                    f"런 간 비교는 KLa20 으로 할 것.")
    for w in warn:
        print(f"  [경고] {w}")
    if not warn:
        print("  [OK] 진단 통과")

    if sweep:
        print("\n  [유효창 민감도] KLa 1/h")
        print("     hi\\lo   " + "".join(f"{x:>10.2f}" for x in (0.05, 0.10, 0.15, 0.20, 0.30)))
        for h in (0.85, 0.90, 0.92, 0.95, 0.98):
            cells = []
            for l in (0.05, 0.10, 0.15, 0.20, 0.30):
                try:
                    rr = fit_one(t, c_s, l, h, cstar_used, cstar_mode,
                                 time_weight)
                    cells.append(f"{rr['kla']*3600:>7.3f}")
                except Exception:
                    cells.append("      --")
            print(f"     {h:.2f}   " + "".join(f"{x:>10}" for x in cells))
        print("  -> 값이 평탄한 (lo,hi) 영역을 최종 유효창으로 확정 (방법론 §9)")

    if plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(2, 1, figsize=(7, 6), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
            ax[0].plot(t, c, ".", ms=2, alpha=0.3, label="raw")
            ax[0].plot(t, c_s, "-", lw=1, label=f"smoothed ({smooth:.0f}s)")
            tw = t[r["mask"]]
            ax[0].plot(tw, model(tw - tw[0], r["cstar"], r["kla"], r["c0"]),
                       "r-", lw=2, label="fit")
            ax[0].axhline(r["cstar"], color="r", ls=":", lw=1,
                          label=f"C* ({r['cstar_source']})")
            ax[0].axhline(cstar_bk, color="g", ls="--", lw=1, label="C* Benson-Krause")
            ax[0].axvspan(tw[0], tw[-1], color="k", alpha=0.05)
            ax[0].set_ylabel("DO [mg/L]")
            ax[0].legend(fontsize=8)
            ax[0].set_title(f"{os.path.basename(path)}  "
                            f"KLa={r['kla']*3600:.3f}/h  "
                            f"KLa20={k20*3600:.3f}/h  "
                            f"C*={r['cstar']:.2f} ({r['cstar_source']})")
            ax[1].plot(tw, c_s[r["mask"]] - model(tw - tw[0], r["cstar"],
                                                  r["kla"], r["c0"]), "k.", ms=2)
            ax[1].axhline(0, color="r", lw=0.8)
            ax[1].set_ylabel("residual")
            ax[1].set_xlabel("t since aeration ON [s]")
            out = os.path.splitext(path)[0] + "_fit.png"
            fig.tight_layout()
            fig.savefig(out, dpi=140)
            plt.close(fig)
            print(f"  그림 저장     : {out}")
        except ImportError:
            print("  (matplotlib 없음 — 그림 생략)")

    return {
        "file": os.path.basename(path),
        "t0_s": t0, "t0_source": t0_src,
        "T_mean_C": T_mean, "T_sd_C": T_sd, "P_kPa": P,
        "kla_1_s": r["kla"], "kla_1_h": r["kla"] * 3600,
        "kla20_1_h": k20 * 3600,
        "kla_se_1_s": r["kla_se"],
        "tau_min": tau / 60.0,
        "cstar_mgL": r["cstar"], "cstar_source": r["cstar_source"],
        "cstar_bk_mgL": cstar_bk,
        "dcstar_mgL": r["cstar"] - cstar_bk,
        "c_plateau_obs_mgL": r["c_plateau_obs"],
        "rmse_mgL": r["rmse"], "n_points": r["n"],
        "t_win_start_s": r["t_window"][0], "t_win_end_s": r["t_window"][1],
        "t_end_tau": t_end_tau,
        "slope_tail_mgL_10min": slope10,
        "n_gap": ng, "gap_lost_min": lost / 60.0, "gap_lost_frac": lostf,
        "time_weight": int(time_weight),
        "truncated": int(r["truncated"]),
        "n_warn": len(warn),
    }


def main():
    p = argparse.ArgumentParser(description="EX2 재폭기 곡선 KLa 피팅 (v2)")
    p.add_argument("files", nargs="+", help="로거 CSV (glob 가능)")
    p.add_argument("--t0", type=float, default=None,
                   help="폭기 ON 시각 [s] (미지정 시 이벤트 파일 -> DO 최저점)")
    p.add_argument("--events", default=None,
                   help="이벤트 sidecar CSV (미지정 시 <log>_events.csv 자동)")
    p.add_argument("--t0-event", default="aeration,rise",
                   help="t0 로 쓸 이벤트 라벨 키워드, 쉼표구분 (기본 aeration,rise)")
    p.add_argument("--smooth", type=float, default=5.0, help="이동평균 창 [s]")
    p.add_argument("--lo", type=float, default=0.15, help="유효창 하한 (분율)")
    p.add_argument("--hi", type=float, default=0.92, help="유효창 상한 (분율)")
    p.add_argument("--cstar-ref", type=float, default=None,
                   help="기준런에서 확정한 C* [mg/L]. 주면 C* 고정 + 창 정규화 (절단 편향 제거)")
    p.add_argument("--cstar-ref-T", type=float, default=None,
                   help="--cstar-ref 를 측정한 수온 [degC]. Benson-Krause 로 런 수온에 환산")
    p.add_argument("--pressure", type=float, default=None,
                   help="현지기압 [kPa] (기본 101.325)")
    p.add_argument("--theta", type=float, default=THETA_DEFAULT,
                   help="Arrhenius theta (기본 1.024)")
    p.add_argument("--scale", type=float, default=1.0,
                   help="DO 스케일 보정계수 (스팬 편향. 파일럿은 0.95476)")
    p.add_argument("--cstar-mode", choices=["window", "fix"], default="window",
                   help="--cstar-ref 사용법. window=유효창 정규화만(기본, 규약 C) / "
                        "fix=모델 C* 도 고정(규약 B, 진단용)")
    p.add_argument("--basis", choices=["do", "sat"], default="do",
                   help="피팅 기준량. do=원시 DO(기본) / sat=포화도(수온 표류 상쇄)")
    p.add_argument("--plateau-tol", type=float, default=0.02,
                   help="평탄 판정 기울기 [mg/L per 10min] (기본 0.02)")
    p.add_argument("--time-weight", action="store_true",
                   help="각 점을 국소 시간간격으로 가중 (로깅 공백 보정). 보간 아님")
    p.add_argument("--sweep", action="store_true", help="유효창 민감도 스윕")
    p.add_argument("--noplot", action="store_true")
    p.add_argument("--summary", help="결과 요약 CSV 경로")
    a = p.parse_args()

    paths = []
    for f in a.files:
        paths.extend(sorted(glob.glob(f)) or [f])

    rows = []
    for path in paths:
        try:
            rows.append(analyze(
                path, a.t0, a.smooth, a.lo, a.hi, a.sweep, not a.noplot,
                cstar_ref=a.cstar_ref, cstar_ref_T=a.cstar_ref_T,
                pressure=a.pressure, theta=a.theta, scale=a.scale,
                events_path=a.events, t0_event=a.t0_event,
                plateau_tol=a.plateau_tol, cstar_mode=a.cstar_mode,
                basis=a.basis, time_weight=a.time_weight))
        except Exception as e:
            print(f"\n[skip] {path}: {e}")

    if len(rows) > 1:
        kla = np.array([r["kla_1_h"] for r in rows])
        k20 = np.array([r["kla20_1_h"] for r in rows])
        print(f"\n=== {len(rows)}런 종합 ===")
        print(f"  KLa      = {kla.mean():.4f} +- {kla.std(ddof=1):.4f} 1/h "
              f"(CV = {100*kla.std(ddof=1)/kla.mean():.2f}%)")
        print(f"  KLa(20C) = {k20.mean():.4f} +- {k20.std(ddof=1):.4f} 1/h "
              f"(CV = {100*k20.std(ddof=1)/k20.mean():.2f}%)  <- 런 간 비교는 이 값")
        cs = np.array([r["cstar_mgL"] for r in rows])
        print(f"  C*       = {cs.mean():.3f} +- {cs.std(ddof=1):.3f} mg/L")
        nw = sum(r["n_warn"] for r in rows)
        if nw:
            print(f"  [경고] 총 {nw}건 — 위 개별 출력 확인")

    if a.summary and rows:
        with open(a.summary, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\n요약 저장: {a.summary}")


if __name__ == "__main__":
    main()
