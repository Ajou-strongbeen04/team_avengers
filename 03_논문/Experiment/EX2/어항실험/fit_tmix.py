#!/usr/bin/env python3
"""
fit_tmix.py — 산소결손 펄스 추적법으로 혼합시간 t_mix 산출
EX2 / 팀 漁벤져스 · 2026-08-01

원리
----
포화 상태 수조(폭기 ON)에 Na2SO3 슬러그를 코너에 주입하면 Co2+ 촉매로
수 초 내 반응이 끝나 국소 DO 결손이 생긴다. 반응 종료 후 이 결손은
수동 스칼라로 분산되며, 프로브가 도달·평탄화를 기록한다.

측정 신호에서 두 배경을 벗겨야 참 혼합 응답이 남는다:
  1) 주입 전 재폭기 추세 (baseline)
  2) 결손 자체의 재폭기 감쇠 exp(-KLa*t)   <- 이게 핵심. KLa=2.4/h면 10분에 33% 사라진다
그리고 프로브 1차 지연(tau_probe~25s)을 선택적으로 디컨볼루션한다.

판정
----
  D_corr(t) -> 균질 결손 dC_uniform = M/V 로 수렴
  t95 = D_corr 이 최종값의 +-5% 안에 들어와 계속 머무는 첫 시각
  t_mix << 1/KLa 이면 0-D 벌크 축약 성립 (방법론 §6.1-2)

사용법
------
  python3 fit_tmix.py pulse1.csv --t-inject 300 --mass 50
  python3 fit_tmix.py "pulse*.csv" --t-inject 300 --mass 50 --deconv --summary tmix.csv
"""
import argparse, glob, sys
import numpy as np

V_TANK_L = 20.7           # 수조 체적 [L]        (상수_목록.md E)
MG_PER_MG_O2 = 7.88       # Na2SO3 mg / O2 mg    (방법론 §4)
KLA_DEFAULT = 2.417       # [1/h]                (파일럿_결과 §0)
TAU_PROBE_DEFAULT = 25.0  # [s]                  (tau_probe_1.csv 계단응답)


def read_logger_csv(path):
    """로거 CSV 파싱. note 줄은 따옴표로 감싸여 '"#' 로 시작할 수 있고 내부에
    콤마를 포함하므로 단순 '#' 검사만으로는 걸러지지 않는다. 값 3개를 모두
    파싱한 뒤에 append 해 배열 길이 어긋남도 방지한다."""
    t, do, T = [], [], []
    for line in open(path, encoding="utf-8"):
        ls = line.lstrip().lstrip('"\'')
        if ls.startswith("#") or ls.startswith("iso_time") or not ls.strip():
            continue
        p = line.strip().split(",")
        if len(p) < 5:
            continue
        try:
            a, b, c = float(p[1]), float(p[2]), float(p[4])
        except ValueError:
            continue
        t.append(a); do.append(b); T.append(c)
    t, do, T = np.array(t), np.array(do), np.array(T)
    # 로거가 드물게 시각을 되돌려 쓰는 경우가 있다(pulse1 t=1391.7, 1건).
    # np.gradient 가 dt<=0 에서 발산하므로 정렬 + 단조 강제.
    o = np.argsort(t, kind="stable")
    t, do, T = t[o], do[o], T[o]
    keep = np.concatenate(([True], np.diff(t) > 0))
    n_drop = (~keep).sum()
    if n_drop:
        print("  [정리] 비단조/중복 타임스탬프 %d점 제거" % n_drop)
    return t[keep], do[keep], T[keep]


def moving_average(y, n):
    """가장자리 보존 이동평균.

    np.convolve(..., mode="same") 는 배열 양끝을 0으로 패딩하므로 첫/끝 n/2 점이
    0 쪽으로 끌려간다. 최저점 탐지·기울기 산출이 통째로 망가지므로 edge 패딩을 쓴다.
    """
    if n <= 1:
        return np.asarray(y, dtype=float).copy()
    n = int(n)
    if n % 2 == 0:
        n += 1
    pad = n // 2
    yp = np.pad(np.asarray(y, dtype=float), (pad, pad), mode="edge")
    return np.convolve(yp, np.ones(n) / n, mode="valid")


def deconvolve_first_order(t, y, tau):
    """프로브 1차 지연 보정: y_true = y + tau * dy/dt  (노이즈 증폭 주의 -> 사전 평활 필수)"""
    dydt = np.gradient(y, t)
    return y + tau * dydt


def settle_time(t, y, y_inf, tol=0.05, require_s=30.0):
    """|y - y_inf| <= tol*|y_inf| 를 만족하며 이후 require_s 동안 이탈하지 않는 첫 시각"""
    band = tol * abs(y_inf)
    inside = np.abs(y - y_inf) <= band
    for i in range(len(t)):
        if not inside[i]:
            continue
        j = np.searchsorted(t, t[i] + require_s)
        if np.all(inside[i:max(j, i + 1)]):
            return t[i]
    return None


def find_circulation_peaks(t, y, y_inf, min_sep_s=20.0):
    """수렴값 주변 진동의 국소 극값 -> 순환 주기 추정"""
    r = y - y_inf
    peaks = []
    for i in range(1, len(r) - 1):
        if (r[i] > r[i - 1] and r[i] >= r[i + 1]) or (r[i] < r[i - 1] and r[i] <= r[i + 1]):
            if not peaks or (t[i] - peaks[-1][0]) >= min_sep_s:
                peaks.append((t[i], r[i]))
    return peaks


def analyse(path, args):
    t, do, T = read_logger_csv(path)
    if len(t) < 60:
        print("  [건너뜀] 데이터 부족 (%d점)" % len(t)); return None

    ti = args.t_inject
    if ti is None:
        # 자동 탐지: 최대 하강 기울기 시각
        s = moving_average(do, args.smooth)
        d = np.gradient(s, t)
        ti = t[np.argmin(d)]
        print("  [자동] 주입시각 추정 t_inject = %.1f s (최대 하강 기울기)" % ti)

    pre = t < ti - args.guard
    post = t >= ti
    if pre.sum() < 30:
        print("  [경고] 주입 전 baseline 구간이 %ds 미만 — 정확도 저하" % int(pre.sum()))
    if post.sum() < 120:
        print("  [건너뜀] 주입 후 데이터 부족"); return None

    # --- 1) baseline: 주입 전 선형 추세를 외삽 (포화 근방이라 거의 평탄) ---
    if pre.sum() >= 10:
        c = np.polyfit(t[pre], do[pre], 1)
        base = np.polyval(c, t)
        base0 = np.polyval(c, ti)
    else:
        base = np.full_like(t, do[pre].mean() if pre.sum() else do[0])
        base0 = base[0]

    y = moving_average(do, args.smooth)

    # --- 2) 프로브 지연 디컨볼루션 (선택) ---
    if args.deconv:
        y = deconvolve_first_order(t, y, args.tau_probe)
        y = moving_average(y, args.smooth)

    # --- 3) 결손 신호 + 재폭기 감쇠 보정 ---
    D = base - y                                   # 결손 [mg/L], 주입 전 ~0
    kla_s = args.kla / 3600.0
    tt = t - ti
    D_corr = np.where(tt >= 0, D * np.exp(kla_s * np.maximum(tt, 0)), D)

    m = (tt >= 0) & (tt <= args.window)
    tm, Dm = tt[m], D_corr[m]
    if len(tm) < 60:
        print("  [건너뜀] 해석 구간 부족"); return None

    # --- 4) 수렴값: 후반 30% 평균 ---
    tail = tm >= tm[-1] - 0.30 * (tm[-1] - tm[0])
    D_inf = Dm[tail].mean()
    D_inf_sd = Dm[tail].std()

    dC_theory = args.mass / MG_PER_MG_O2 / args.volume   # mg/L
    t95 = settle_time(tm, Dm, D_inf, 0.05, args.require)
    t99 = settle_time(tm, Dm, D_inf, 0.01, args.require)
    peaks = find_circulation_peaks(tm, Dm, D_inf)

    inv_kla_min = 60.0 / args.kla

    print("  주입시각 t_inject      : %.1f s" % ti)
    print("  baseline @주입         : %.3f mg/L" % base0)
    print("  균질 결손 dC (실측)    : %.4f +- %.4f mg/L" % (D_inf, D_inf_sd))
    print("  균질 결손 dC (이론)    : %.4f mg/L  (Na2SO3 %.0f mg / %.1f L)" % (dC_theory, args.mass, args.volume))
    if dC_theory > 0:
        print("  회수율                 : %.1f %%" % (100 * D_inf / dC_theory))
    if t95 is not None:
        print("  ** t95 = %.1f s (%.2f min)" % (t95, t95 / 60))
        print("     t95 / (1/KLa)       = %.3f      [1/KLa = %.1f min]" % (t95 / 60 / inv_kla_min, inv_kla_min))
        verdict = ("성립 (t_mix << 1/KLa)" if t95 / 60 / inv_kla_min < 0.10 else
                   "경계 — 주의 필요" if t95 / 60 / inv_kla_min < 0.30 else
                   "** 불성립 — 0-D 축약 재검토 필요 **")
        print("     0-D 판정            : %s" % verdict)
    else:
        print("  ** t95: 해석 구간(%ds) 내 미수렴 — --window 를 늘릴 것" % args.window)
    if t99 is not None:
        print("     t99 = %.1f s (%.2f min)" % (t99, t99 / 60))

    if t95 is not None and t95 < 3 * args.tau_probe:
        print("  [!] t95 가 프로브 시상수(%.0f s)의 3배 미만 — 측정한 것은 대부분 프로브 지연이다." % args.tau_probe)
        print("      이 경우 't_mix < %.0f s' 라는 상한만 주장할 것 (--deconv 로 보정 시도 가능)." % (3 * args.tau_probe))

    if len(peaks) >= 2:
        per = np.diff([p[0] for p in peaks])
        print("  순환 주기 추정         : %.1f +- %.1f s (극값 %d개)" % (per.mean(), per.std(), len(peaks)))

    print("  수온                   : %.2f +- %.2f degC" % (T.mean(), T.std()))

    if not args.noplot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
            ax[0].plot(tt, do, lw=.6, color="0.7", label="raw DO")
            ax[0].plot(tt, base, "--", lw=1, color="C1", label="baseline")
            ax[0].axvline(0, color="C3", lw=1)
            ax[0].set_ylabel("DO [mg/L]"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
            ax[1].plot(tm, Dm, lw=.8, color="C0", label="deficit (KLa-corrected)")
            ax[1].axhline(D_inf, color="C2", lw=1, label="D_inf = %.3f" % D_inf)
            ax[1].axhspan(D_inf * .95, D_inf * 1.05, color="C2", alpha=.15)
            if t95: ax[1].axvline(t95, color="C3", lw=1.2, label="t95 = %.0f s" % t95)
            ax[1].set_xlabel("t - t_inject [s]"); ax[1].set_ylabel("deficit [mg/L]")
            ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
            fig.suptitle(path)
            out = path.rsplit(".", 1)[0] + "_tmix.png"
            fig.tight_layout(); fig.savefig(out, dpi=130)
            print("  그래프 저장            : %s" % out)
        except Exception as e:
            print("  (그래프 생략: %s)" % e)

    return dict(file=path, t_inject=ti, D_inf=D_inf, D_theory=dC_theory,
                t95=t95, t99=t99, ratio=(t95 / 60 / inv_kla_min) if t95 else None,
                T=T.mean())


def main():
    p = argparse.ArgumentParser(description="산소결손 펄스 추적법 t_mix 산출")
    p.add_argument("files", nargs="+", help="로거 CSV (glob 가능)")
    p.add_argument("--t-inject", type=float, default=None, help="슬러그 주입 시각 [s] (미지정 시 자동탐지)")
    p.add_argument("--mass", type=float, default=50.0, help="Na2SO3 투입량 [mg] (기본 50)")
    p.add_argument("--volume", type=float, default=V_TANK_L, help="수조 체적 [L] (기본 20.7)")
    p.add_argument("--kla", type=float, default=KLA_DEFAULT, help="K_La_eff [1/h] (기본 2.417)")
    p.add_argument("--tau-probe", type=float, default=TAU_PROBE_DEFAULT, help="프로브 시상수 [s] (기본 25)")
    p.add_argument("--deconv", action="store_true", help="프로브 1차 지연 디컨볼루션")
    p.add_argument("--smooth", type=int, default=5, help="이동평균 창 [점] (기본 5)")
    p.add_argument("--guard", type=float, default=10.0, help="주입 직전 제외 구간 [s]")
    p.add_argument("--window", type=float, default=1800.0, help="주입 후 해석 구간 [s] (기본 1800)")
    p.add_argument("--require", type=float, default=30.0, help="정착 판정 유지 시간 [s]")
    p.add_argument("--noplot", action="store_true")
    p.add_argument("--summary", help="결과 요약 CSV 경로")
    a = p.parse_args()

    files = []
    for f in a.files:
        files.extend(sorted(glob.glob(f)) or [f])
    rows = []
    for f in files:
        print("\n=== %s ===" % f)
        try:
            r = analyse(f, a)
        except Exception as e:
            print("  [오류] %s" % e); r = None
        if r: rows.append(r)

    if len(rows) >= 2:
        v = [r["t95"] for r in rows if r["t95"]]
        if len(v) >= 2:
            v = np.array(v)
            print("\n=== 반복 요약 (n=%d) ===" % len(v))
            print("  t95 = %.1f +- %.1f s (%.2f +- %.2f min),  CV = %.1f %%"
                  % (v.mean(), v.std(ddof=1), v.mean()/60, v.std(ddof=1)/60, 100*v.std(ddof=1)/v.mean()))
            print("  t95 / (1/KLa) = %.3f" % (v.mean()/60/(60/a.kla)))

    if a.summary and rows:
        import csv
        with open(a.summary, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print("\n요약 저장: %s" % a.summary)


if __name__ == "__main__":
    main()
