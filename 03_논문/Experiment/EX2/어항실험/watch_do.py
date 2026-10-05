#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watch_do.py — SEN0680 DO 실시간 워칭 (영점 도달 관찰용)
do_logger.py 와 같은 폴더에서 실행 (Sensor 클래스 재사용).

사용:
  python3 watch_do.py --port /dev/tty.usbserial-1110
  python3 watch_do.py --port /dev/tty.usbserial-1110 --interval 2 --log zero_watch.csv
Ctrl+C 로 종료 → 요약(시작→최저, 경과) 출력.

한 줄이 계속 갱신됨:
  [경과] DO | 포화% | 수온 | 최저DO | 시작대비Δ | 산포(최근창) | 상태
상태: (안정) = 최근 창이 평평함 / ★ = 안정 + DO<임계 → 지금 --calibrate 0 가능
"""
import argparse, sys, time, csv, datetime as dt
from collections import deque
from do_logger import Sensor


def main():
    p = argparse.ArgumentParser(description="SEN0680 DO 실시간 워칭")
    p.add_argument("--port", required=True)
    p.add_argument("--baud", type=int, default=4800)
    p.add_argument("--addr", type=int, default=1)
    p.add_argument("--interval", type=float, default=1.0, help="폴링 주기 s (기본 1.0)")
    p.add_argument("--window", type=int, default=15, help="안정 판정 창 샘플수 (기본 15)")
    p.add_argument("--stable-band", type=float, default=0.05, help="안정 폭 mg/L (기본 0.05)")
    p.add_argument("--zero-th", type=float, default=0.3, help="영점 판정 임계 mg/L (기본 0.3)")
    p.add_argument("--log", metavar="CSV", help="CSV 기록 (선택)")
    a = p.parse_args()

    s = Sensor(a.port, baud=a.baud, addr=a.addr)
    recent = deque(maxlen=a.window)
    t0 = time.time()
    n = 0
    min_do = float("inf")
    start_do = None
    fails = 0
    fh = writer = None
    if a.log:
        fh = open(a.log, "w", newline="", encoding="utf-8")
        writer = csv.writer(fh)
        writer.writerow(["iso_time", "t_sec", "do_mgL", "sat_frac", "temp_C"])

    print("실시간 워칭 시작 (Ctrl+C 종료). 영점 안정 시 ★ 표시.\n")
    try:
        while True:
            try:
                sat, do, temp = s.read_all()
                fails = 0
            except Exception as e:
                fails += 1
                sys.stdout.write(f"\r  읽기 실패 {fails}/10 재시도... ({e})            ")
                sys.stdout.flush()
                if fails >= 10:
                    print("\n연속 10회 실패 — 배선/포트/보레이트 확인 후 재시작.")
                    break
                time.sleep(a.interval)
                continue

            n += 1
            t = time.time() - t0
            if start_do is None:
                start_do = do
            min_do = min(min_do, do)
            recent.append(do)
            spread = (max(recent) - min(recent)) if len(recent) > 1 else float("inf")
            full = len(recent) == recent.maxlen
            stable = full and spread <= a.stable_band
            delta = do - start_do
            mm, ss = divmod(int(t), 60)

            if stable and do <= a.zero_th:
                flag = "  ★ 영점 안정 → 지금 --calibrate 0 하세요"
            elif stable:
                flag = "  (안정)"
            else:
                flag = ""

            if a.log:
                writer.writerow([dt.datetime.now().isoformat(timespec="seconds"),
                                 f"{t:.1f}", f"{do:.3f}", f"{sat:.4f}", f"{temp:.2f}"])
                fh.flush()

            sp = 0.0 if spread == float("inf") else spread
            sys.stdout.write(
                f"\r[{mm:02d}:{ss:02d}] DO {do:6.3f} mg/L | 포화 {sat*100:5.1f}% "
                f"| {temp:5.2f}C | 최저 {min_do:6.3f} | Δ{delta:+6.3f} "
                f"| 산포 {sp:5.3f}{flag}      ")
            sys.stdout.flush()
            time.sleep(a.interval)
    except KeyboardInterrupt:
        pass
    finally:
        s.close()
        if fh:
            fh.close()
        el = time.time() - t0
        mm, ss = divmod(int(el), 60)
        sd = start_do if start_do is not None else float("nan")
        md = min_do if min_do != float("inf") else float("nan")
        print(f"\n\n요약: 샘플 {n}개 · 경과 {mm:02d}:{ss:02d} · "
              f"시작 {sd:.3f} → 최저 {md:.3f} mg/L")
        if a.log:
            print(f"CSV 저장: {a.log}")


if __name__ == "__main__":
    main()
