#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 재폭기 시험 — DFRobot SEN0680 (RS485 형광 DO, 담수) ModBus-RTU 로거  [v2]

의존성: pyserial  (pip install pyserial)
  * pymodbus 불필요 — 프레임/CRC 직접 구현 (환경 의존 최소화)

레지스터 맵 (DFRobot wiki, SEN0680/0681 공통 계열)
  0x0000-0x0001  DO 포화도    float32 big-endian, 1.0 = 100%
  0x0002-0x0003  DO 농도      float32 big-endian, mg/L
  0x0004-0x0005  수온         float32 big-endian, degC
  0x1010         보정         write 0x0001 = 영점(0%), 0x0002 = 100% 포화
  0x1022         기압         kPa x100 (기본 10133 = 101.33 kPa)
  0x07D0         장치주소     1..254 (기본 1)
  0x07D1         보레이트     0=2400 1=4800 2=9600 3=19200 4=38400 5=57600 6=115200
통신 기본값: 4800 bps, 8N1, parity none

────────────────────────────────────────────────────────────────────────
v2 변경점 (2026-08-01). Sensor 클래스 API·CSV 열 구성은 v1 그대로(하위호환).
────────────────────────────────────────────────────────────────────────
 (1) --mark : **이벤트 마킹.** 로깅 중 터미널에 Enter 를 치면 그 순간의
     t_sec 이 <log>_events.csv 에 기록된다. 라벨을 입력하면 그 라벨로.
     첫 마크의 기본 라벨은 'aeration_on' — fit_kla.py v2 가 이걸 읽어
     t0 를 자동으로 잡는다. **벽시계 받아적기가 사라진다.**
       빈 Enter        -> 기본 라벨 순서대로 (aeration_on, na2so3_in, ...)
       텍스트 + Enter  -> 그 텍스트가 라벨

 (2) 실시간 KLa/tau/평탄 ETA : 폭기 ON 마크 이후 데이터로 dC/dt 대 C 를
     회귀해 (KLa, C*) 를 실시간 추정한다. 화면에 경과 tau, 말미 기울기
     [mg/L/10min], 목표 기울기 도달 ETA 를 띄운다.
     파일럿은 기울기 0.074(기준 0.02)에서 끊어 C* 를 놓쳤다 — 그 재발 방지.

 (3) --stop-at-tau N / --stop-on-plateau S : 자동 종료.
       --stop-at-tau 3.3     경과가 3.3 tau 를 넘으면 종료 (일반 런)
       --stop-on-plateau 0.02  말미 기울기가 0.02 mg/L/10min 밑이면 종료 (기준런)

 (4) --note 필수필드 검증 : z_start / pos / T / P 가 없으면 실행 거부.
     파일럿은 에어스톤 기하를 안 적어 kappa 를 확정하지 못했다. --force 로 우회.

 (5) 파일 덮어쓰기 방지 · 통신 끊김 시 포트 재연결 재시도.

사용 예
  python3 do_logger.py --port /dev/tty.usbserial-1110 --scan
  python3 do_logger.py --port /dev/tty.usbserial-1110 --read
  python3 do_logger.py --port /dev/tty.usbserial-1110 --calibrate 100
  python3 do_logger.py --port /dev/tty.usbserial-1110 --set-pressure 101.0

  # 본시험 일반 런 (3.3 tau 자동 종료)
  python3 do_logger.py --port /dev/tty.usbserial-1110 --log run_R2.csv \
      --interval 1.0 --mark --stop-at-tau 3.3 \
      --note "R2, z_start=0.020, pos=jangchuk(0.450,0.175,0.105), Na2SO3 2.0g, Co 30mg, T=24.1C, P=101.0kPa"

  # 기준런 (평탄부까지 — C* 확정용)
  python3 do_logger.py --port ... --log run_R1.csv --mark --stop-on-plateau 0.02 \
      --note "R1 기준런, z_start=0.020, pos=..., T=..C, P=101.0kPa"

출력
  <log>.csv          iso_time, t_sec, do_mgL, sat_frac, temp_C      (v1과 동일)
  <log>_events.csv   iso_time, t_sec, label                          (v2 신규)
"""

import argparse
import csv
import datetime as _dt
import math
import os
import queue
import struct
import sys
import threading
import time

try:
    import serial  # pyserial
except ImportError:
    serial = None

# ---------------------------------------------------------------- ModBus 유틸

REG_SAT = 0x0000
REG_DO = 0x0002
REG_TEMP = 0x0004
REG_CAL = 0x1010
REG_SALINITY = 0x1020
REG_PRESSURE = 0x1022
REG_ADDR = 0x07D0
REG_BAUD = 0x07D1

BAUD_CODES = {2400: 0, 4800: 1, 9600: 2, 19200: 3, 38400: 4, 57600: 5, 115200: 6}

DEFAULT_MARK_LABELS = ["aeration_on", "na2so3_in", "co_in", "probe_moved", "note"]

# 평탄 판정 기준량. 원시 DO 는 C*(T) 가 수온과 함께 움직여 오판한다
#   (0.5 C/h 만 변해도 판정기준 0.02 mg/L/10min 의 60 % 를 차지 — 2026-08-01 산정).
# 센서가 주는 포화도 sat = DO/C*(T,P) 로 판정하면 그 항이 상쇄된다.
# C_NOM 은 sat 를 mg/L 등가로 환산하는 눈금(임계값 단위를 바꾸지 않기 위함).
C_NOM = 8.2


def crc16(data: bytes) -> bytes:
    """ModBus RTU CRC-16 (poly 0xA001). 반환은 리틀엔디안 2바이트(저위 먼저)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_read(addr: int, start: int, count: int) -> bytes:
    body = struct.pack(">BBHH", addr, 0x03, start, count)
    return body + crc16(body)


def build_write_single(addr: int, reg: int, value: int) -> bytes:
    body = struct.pack(">BBHH", addr, 0x06, reg, value)
    return body + crc16(body)


def check_crc(frame: bytes) -> bool:
    return len(frame) >= 4 and crc16(frame[:-2]) == frame[-2:]


MODBUS_EXC = {
    0x01: "허용되지 않는 함수코드",
    0x02: "허용되지 않는 레지스터 주소",
    0x03: "허용되지 않는 데이터 값",
    0x04: "슬레이브 장치 오류",
    0x05: "응답 지연(acknowledge)",
    0x06: "장치 사용 중(busy)",
    0x10: "센서가 보정점을 거부 — 현재 매질이 그 보정점의 유효 범위 밖 "
          "(DFRobot 벤더 코드). 배선/주소/보레이트 문제가 아니다",
}


class ModbusException(IOError):
    def __init__(self, code, frame=b""):
        self.code = code
        self.frame = frame
        desc = MODBUS_EXC.get(code, "정의되지 않은 벤더 코드")
        super().__init__(f"ModBus 예외코드 0x{code:02X} — {desc}")


class Sensor:
    def __init__(self, port, baud=4800, addr=1, timeout=1.0):
        if serial is None:
            sys.exit("pyserial 미설치:  pip install pyserial")
        self.port, self.baud, self.addr, self.timeout = port, baud, addr, timeout
        self._open()

    def _open(self):
        self.ser = serial.Serial(
            port=self.port, baudrate=self.baud, bytesize=8,
            parity=serial.PARITY_NONE, stopbits=1, timeout=self.timeout,
        )
        time.sleep(0.2)
        self.ser.reset_input_buffer()

    def reconnect(self):
        """포트가 끊겼을 때 닫고 다시 연다. 실패하면 예외."""
        try:
            self.ser.close()
        except Exception:
            pass
        time.sleep(1.0)
        self._open()

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def _txrx(self, frame: bytes, expect_len: int) -> bytes:
        self.ser.reset_input_buffer()
        self.ser.write(frame)
        self.ser.flush()
        # 머리 3바이트를 먼저 읽어 예외 응답(5바이트)과 정상 응답을 구분한다.
        # v2.1: 예외 프레임은 expect_len 보다 짧아 "응답 길이" 오진을 낳았다.
        head = self.ser.read(3)
        if len(head) < 3:
            raise IOError(f"응답 길이 {len(head)}/3 (타임아웃 또는 배선/보레이트 불일치)")
        if head[1] & 0x80:
            rest = self.ser.read(2)                      # CRC
            frame_ex = head + rest
            code = head[2]
            raise ModbusException(code, frame_ex)
        resp = head + self.ser.read(expect_len - 3)
        if len(resp) != expect_len:
            raise IOError(f"응답 길이 {len(resp)}/{expect_len} (타임아웃 또는 배선/보레이트 불일치)")
        if not check_crc(resp):
            raise IOError(f"CRC 불일치: {resp.hex(' ')}")
        return resp

    def read_all(self):
        """포화도(비율), DO(mg/L), 수온(degC) 동시 읽기 — 레지스터 0x0000 길이 6."""
        resp = self._txrx(build_read(self.addr, 0x0000, 6), 17)
        sat, do, temp = struct.unpack(">fff", resp[3:15])
        return sat, do, temp

    def read_u16(self, reg):
        resp = self._txrx(build_read(self.addr, reg, 1), 7)
        return struct.unpack(">H", resp[3:5])[0]

    def write_u16(self, reg, value):
        self._txrx(build_write_single(self.addr, reg, value), 8)


# ---------------------------------------------------------------- 실시간 추정

class LiveFit:
    """폭기 ON 이후 데이터로 (KLa, C*) 를 실시간 추정.

    dC/dt = KLa (C* - C)  ->  구간기울기 s_j 를 구간평균농도 c_j 에 회귀하면
        s = -KLa * c + KLa * C*
    numpy 없이 순수 파이썬 최소제곱. 30초마다 갱신.
    """

    def __init__(self, bin_s=60.0, min_bins=6):
        self.bin_s = bin_s
        self.min_bins = min_bins
        self.pts = []           # (t, c) — 폭기 ON 이후
        self.kla = None         # 1/s
        self.cstar = None
        self._last_update = -1e9

    def add(self, t, c):
        self.pts.append((t, c))

    def _bins(self):
        if not self.pts:
            return []
        t0 = self.pts[0][0]
        buckets = {}
        for t, c in self.pts:
            k = int((t - t0) // self.bin_s)
            buckets.setdefault(k, []).append((t, c))
        out = []
        for k in sorted(buckets):
            seg = buckets[k]
            if len(seg) < 5:
                continue
            n = len(seg)
            st = sum(p[0] for p in seg); sc = sum(p[1] for p in seg)
            stt = sum(p[0] * p[0] for p in seg); stc = sum(p[0] * p[1] for p in seg)
            den = n * stt - st * st
            if den <= 0:
                continue
            slope = (n * stc - st * sc) / den          # mg/L per s
            out.append((sc / n, slope))
        return out

    def update(self, now):
        if now - self._last_update < 30.0:
            return
        self._last_update = now
        b = self._bins()
        if len(b) < self.min_bins:
            return
        n = len(b)
        sx = sum(p[0] for p in b); sy = sum(p[1] for p in b)
        sxx = sum(p[0] ** 2 for p in b); sxy = sum(p[0] * p[1] for p in b)
        den = n * sxx - sx * sx
        if den == 0:
            return
        a = (n * sxy - sx * sy) / den      # = -KLa
        b0 = (sy - a * sx) / n             # = KLa * C*
        if a >= 0:
            return                          # 상승 아님
        self.kla = -a
        self.cstar = b0 / self.kla

    def tail_slope10(self, tail_s=600.0):
        """말미 tail_s 초의 기울기 [mg/L per 10 min]."""
        if len(self.pts) < 10:
            return float("nan")
        t_end = self.pts[-1][0]
        seg = [p for p in self.pts if p[0] >= t_end - tail_s]
        if len(seg) < 10:
            return float("nan")
        n = len(seg)
        st = sum(p[0] for p in seg); sc = sum(p[1] for p in seg)
        stt = sum(p[0] ** 2 for p in seg); stc = sum(p[0] * p[1] for p in seg)
        den = n * stt - st * st
        if den <= 0:
            return float("nan")
        return (n * stc - st * sc) / den * 600.0

    def eta_to_slope(self, target10, now_t):
        """목표 기울기(mg/L/10min)까지 남은 시간 [s]. 추정 불가면 None."""
        if not self.kla or not self.cstar:
            return None
        cur = self.tail_slope10()
        if not (cur == cur) or cur <= 0:      # NaN 또는 비상승
            return None
        if cur <= target10:
            return 0.0
        return math.log(cur / target10) / self.kla


# ---------------------------------------------------------------- 동작 모드

def do_scan(port):
    print("보레이트 x 주소 스캔 (주소 1..8)")
    for baud in (4800, 9600, 19200, 2400, 38400, 57600, 115200):
        for addr in range(1, 9):
            s = None
            try:
                s = Sensor(port, baud=baud, addr=addr, timeout=0.35)
                sat, do, temp = s.read_all()
                s.close()
                print(f"  * 발견: baud={baud} addr={addr} "
                      f"-> DO {do:.2f} mg/L, {sat*100:.1f}%, {temp:.1f} C")
                return baud, addr
            except Exception:
                if s is not None:
                    try:
                        s.close()
                    except Exception:
                        pass
    print("  발견 실패 — 결선(A/B 극성), 12V 전원, 포트명 확인")
    return None


def do_read(sensor, n=5):
    for _ in range(n):
        sat, do, temp = sensor.read_all()
        print(f"DO {do:7.3f} mg/L | 포화 {sat*100:6.2f} % | 수온 {temp:6.2f} C")
        time.sleep(1.0)


def _bk(T_c, P_kpa=101.325):
    T = T_c + 273.15
    ln_c = (-139.34411 + 1.575701e5 / T - 6.642308e7 / T**2
            + 1.243800e10 / T**3 - 8.621949e11 / T**4)
    return math.exp(ln_c) * (P_kpa / 101.325)


def do_calibrate(sensor, which, force=False):
    """보정. v2.1: 쓰기 전에 현재 매질이 그 보정점에 맞는지 먼저 판정한다.

    2026-08-01 에 100 % 보정이 예외 0x10 으로 거부됐다. 0x10 은 코드 오류가
    아니라 **센서가 유효하지 않은 보정점을 거부**한 것이다(2026-07-31 영점
    거부와 같은 메커니즘, 보정로그.md). 그때는 매질 DO 가 91 % 라 무산소가
    아니었다. 아래 사전 판정이 같은 실패를 쓰기 전에 잡는다.
    """
    print("현재 매질 판독 (5초)...")
    sats, dos, temps = [], [], []
    for _ in range(5):
        sat, do, temp = sensor.read_all()
        sats.append(sat * 100); dos.append(do); temps.append(temp)
        time.sleep(1.0)
    sat_m = sum(sats) / len(sats)
    do_m = sum(dos) / len(dos)
    T_m = sum(temps) / len(temps)
    dT = max(temps) - min(temps)
    try:
        p_kpa = sensor.read_u16(REG_PRESSURE) / 100.0
    except Exception:
        p_kpa = 101.325
    bk = _bk(T_m, p_kpa)
    print(f"  DO {do_m:.3f} mg/L | 센서 포화 {sat_m:.2f} % | 수온 {T_m:.2f} C "
          f"(5초 dT={dT:.3f}) | 기압 {p_kpa:.2f} kPa")
    print(f"  Benson-Krause C*({T_m:.2f}C, {p_kpa:.2f}kPa) = {bk:.3f} mg/L "
          f"-> 대조 포화 {100*do_m/bk:.2f} %")

    blocking = []
    if which == 100:
        print("\n100 % 포화 보정 — 공기포화수 또는 수증기포화 공기여야 합니다.")
        code = 0x0002
        ratio = 100 * do_m / bk
        if not (75.0 <= ratio <= 130.0):
            blocking.append(
                f"현재 매질이 포화의 {ratio:.1f} % 입니다. 센서가 유효 범위 밖으로 "
                f"보고 0x10 으로 거부할 가능성이 큽니다.\n"
                f"      -> 프로브가 정말 공기포화 매질에 있습니까? "
                f"검은 보호캡을 벗겼습니까? 탈산소수/마른 공기가 아닙니까?")
        if dT > 0.05:
            blocking.append(
                f"5초 dT={dT:.3f} > 0.05 degC — 온도가 움직입니다. "
                f"`preflight.py --gate calib` 로 3분 판정을 통과시킨 뒤 하십시오.\n"
                f"      -> 2026-07-31 에 이걸 건너뛰어 스팬이 +4.7 % 높게 박혔습니다.")
    else:
        print("\n영점(0 %) 보정 — 5 % Na2SO3 무산소액이어야 합니다.")
        code = 0x0001
        if abs(do_m) > 0.30:
            blocking.append(
                f"현재 DO {do_m:.3f} mg/L — 무산소 미도달. 센서가 0x10 으로 "
                f"거부합니다(2026-07-31 실제 사례).\n"
                f"      -> Na2SO3 추가 + CoCl2 촉매, 정치 후 재시도. "
                f"`watch_do.py` 로 관찰하면 별표가 뜹니다.")

    if blocking:
        print("\n  [NO-GO] 쓰기 전에 막았습니다:")
        for b in blocking:
            print(f"    - {b}")
        if not force:
            print("\n  보정을 실행하지 않았습니다. 조건을 맞춘 뒤 다시 실행하십시오. "
                  "(무시하려면 --force)")
            return
        print("\n  --force 로 강행합니다.")

    print("\n  ** SOP §3.1: 재보정 전에 --read 로 표류값을 먼저 기록했습니까? "
          "--calibrate 는 쓰기 명령이라 그냥 돌리면 전후 차이를 영구히 잃습니다. **")
    ans = input("값이 안정되었고 표류값도 기록했습니까? 진행하려면 yes 입력: ").strip().lower()
    if ans != "yes":
        print("취소")
        return
    try:
        sensor.write_u16(REG_CAL, code)
    except ModbusException as e:
        print(f"\n  [거부] {e}")
        if e.code == 0x10:
            print("  이것은 스크립트/배선 문제가 아닙니다. 센서가 현재 매질을 "
                  "그 보정점으로 인정하지 않은 것입니다.")
            print("  확인할 것:")
            if which == 100:
                print("   1) 프로브가 공기포화수 또는 수증기포화 공기에 있는가 "
                      "(마른 공기·탈산소수 아님)")
                print("   2) 형광막 보호캡을 벗겼는가")
                print("   3) 매질과 프로브가 열평형인가 (--gate calib)")
                print("   4) 기압 레지스터가 현지기압인가 (--set-pressure)")
            else:
                print("   1) DO 가 ~0 로 안정됐는가 (watch_do.py 로 확인)")
                print("   2) Na2SO3 5 % + CoCl2 촉매를 넣고 1시간 정치했는가")
            print("\n  ** 중요: 기존 보정은 그대로 살아 있습니다. **")
            print("  현행 프레임이 `preflight.py --gate verify` 를 통과한다면 "
                  "재보정하지 말고 그대로 쓰는 것이 낫습니다 — "
                  "잘못된 재보정이 07-31 스팬 편향의 원인이었습니다.")
        return
    print("보정 명령 전송 완료. 30초 후 재확인:")
    time.sleep(30)
    do_read(sensor, n=3)


# ---------------------------------------------------------------- 노트 검증

REQUIRED_NOTE_KEYS = {
    "z_start": ["z_start", "zstart", "z="],
    "pos":     ["pos=", "pos ", "probe="],
    "T":       ["t=", "temp"],
    "P":       ["p=", "kpa"],
}


def validate_note(note):
    """--note 에 필수 조건이 들어있는지. 반환: 누락 키 목록."""
    low = (note or "").lower()
    missing = []
    for key, pats in REQUIRED_NOTE_KEYS.items():
        if not any(pat in low for pat in pats):
            missing.append(key)
    return missing


# ---------------------------------------------------------------- 로깅

def _mark_reader(q, stop_evt):
    """표준입력 한 줄 = 마크 하나. 별도 스레드."""
    while not stop_evt.is_set():
        try:
            line = sys.stdin.readline()
        except Exception:
            return
        if not line:
            return
        q.put(line.strip())


def do_log(sensor, path, interval, note, duration, mark=False,
           stop_at_tau=None, stop_on_plateau=None, plateau_tail=600.0,
           overwrite=False, plateau_on="sat"):
    if os.path.exists(path) and not overwrite:
        sys.exit(f"[중단] {path} 가 이미 있습니다. 다른 이름을 쓰거나 --overwrite 를 주세요.")

    ev_path = os.path.splitext(path)[0] + "_events.csv"
    t0 = time.time()
    fails = 0
    live = LiveFit()
    last_sat = None
    t_aer = None                 # 폭기 ON 마크 시각
    pending = list(DEFAULT_MARK_LABELS)   # 빈 Enter 가 소비할 기본 라벨 큐
    mark_n = 0

    print(f"로깅 시작 -> {path}   (Ctrl+C 종료)")
    if note:
        print(f"메모: {note}")
    if mark:
        print(f"이벤트 -> {os.path.basename(ev_path)}")
        print(f"  빈 Enter    = 미사용 기본라벨을 순서대로 소비 "
              f"({'/'.join(DEFAULT_MARK_LABELS)})")
        print("  텍스트+Enter = 그 텍스트가 라벨 (기본라벨 순서는 안 밀림)")
        print("  ** t0 라벨: 'aeration_on' 또는 'rise_start' 중 아무거나 **")
        print("     · 폭기를 껐다 켜는 프로토콜  -> 켜는 순간 빈 Enter (aeration_on)")
        print("     · 폭기를 계속 켜두는 프로토콜 -> **DO 가 최저점을 찍고 오르기")
        print("       시작하는 순간** `rise_start` 를 타이핑. (S1 이 이 방식)")
        print("  ** Na2SO3 투입은 `na2so3_in` 을 타이핑 (빈 Enter 쓰지 말 것) **")
        print("  (화면 오른쪽 [Enter]->'...' 가 다음 빈 Enter 의 라벨을 알려줍니다)")
    if stop_at_tau:
        print(f"자동 종료: 폭기 ON 후 {stop_at_tau} tau 경과 시")
    if stop_on_plateau:
        print(f"자동 종료: 말미 {plateau_tail/60:.0f}분 기울기 < "
              f"{stop_on_plateau} mg/L/10min (평탄 판정)")
        if plateau_on == "sat":
            print(f"  판정 기준량 = **포화도** sat x {C_NOM} (수온 표류 면역). "
                  f"원시 DO 로 하려면 --plateau-on do")
        else:
            print("  판정 기준량 = 원시 DO. [주의] 수온이 0.5 C/h 움직이면 "
                  "C*(T) 이동이 기준의 60 % 를 차지해 오판할 수 있다")

    q = queue.Queue()
    stop_evt = threading.Event()
    if mark:
        threading.Thread(target=_mark_reader, args=(q, stop_evt), daemon=True).start()

    evf = open(ev_path, "w", newline="", encoding="utf-8") if mark else None
    evw = None
    if evf:
        evw = csv.writer(evf)
        evw.writerow(["iso_time", "t_sec", "label"])
        evf.flush()

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if note:
            w.writerow([f"# note: {note}"])
        w.writerow([f"# start_iso: {_dt.datetime.now().isoformat(timespec='seconds')}"])
        w.writerow(["iso_time", "t_sec", "do_mgL", "sat_frac", "temp_C"])
        f.flush()
        try:
            while True:
                loop_start = time.time()

                # ── 이벤트 마크 처리
                while mark and not q.empty():
                    txt = q.get()
                    mark_n += 1
                    if txt:
                        label = txt
                        # 타이핑한 라벨은 큐에서 빼기만 한다 (포인터 안 밂).
                        # v2.2 버그: 여기서 포인터를 밀어 'aeration_on' 이
                        # 건너뛰어지고 t0 가 영구히 유실됐다.
                        if txt in pending:
                            pending.remove(txt)
                    else:
                        label = pending.pop(0) if pending else f"mark{mark_n}"
                    tm = loop_start - t0
                    evw.writerow([_dt.datetime.now().isoformat(timespec="milliseconds"),
                                  f"{tm:.3f}", label])
                    evf.flush()
                    print(f"\n  [MARK] t={tm:.1f}s  '{label}'")
                    if (any(k in label.lower() for k in ("aeration", "rise"))
                            and t_aer is None):
                        t_aer = tm
                        live = LiveFit()
                        print(f"  -> t0 = {tm:.1f}s 로 잡았습니다. 실시간 추정 시작.")
                        if last_sat is not None and last_sat > 0.30:
                            print(f"  [주의] 이 순간 포화도가 {last_sat*100:.1f} % 입니다. "
                                  f"탈산소 런이면 ~0 % 여야 합니다 — 마크 시점을 "
                                  f"잘못 찍었는지 확인하십시오. "
                                  f"(폭기만 하는 C* 런이면 정상)")

                # ── 센서 읽기
                try:
                    sat, do, temp = sensor.read_all()
                    fails = 0
                    last_sat = sat
                    t = loop_start - t0
                    w.writerow([
                        _dt.datetime.now().isoformat(timespec="milliseconds"),
                        f"{t:.3f}", f"{do:.4f}", f"{sat:.5f}", f"{temp:.3f}",
                    ])
                    f.flush()

                    line = (f"\rt={t:8.1f}s  DO {do:6.3f} mg/L  "
                            f"포화 {sat*100:6.2f}%  {temp:5.2f}C")
                    if mark:
                        nxt = pending[0] if pending else f"mark{mark_n+1}"
                        line += f" | [Enter]->'{nxt}'"
                    if t_aer is not None:
                        live.add(t - t_aer,
                                 sat * C_NOM if plateau_on == "sat" else do)
                        live.update(t)
                        s10 = live.tail_slope10(plateau_tail)
                        unit = "sat" if plateau_on == "sat" else "DO"
                        line += f" | 기울기({unit}) {s10:+.3f}/10min"
                        if live.kla:
                            tau = 1.0 / live.kla
                            el = (t - t_aer) / tau
                            line += (f" | KLa~{live.kla*3600:.2f}/h "
                                     f"C*~{live.cstar:.2f} | {el:.2f}tau")
                            tgt = stop_on_plateau or 0.02
                            eta = live.eta_to_slope(tgt, t)
                            if eta is not None:
                                line += f" | 평탄ETA {eta/60:.0f}min"
                            # 자동 종료 판정
                            if stop_at_tau and el >= stop_at_tau:
                                print(f"\n{stop_at_tau} tau 도달 (경과 "
                                      f"{(t-t_aer)/60:.0f}분) — 종료")
                                break
                        if stop_on_plateau and s10 == s10 and \
                                abs(s10) < stop_on_plateau and (t - t_aer) > 1800:
                            print(f"\n평탄 판정 (기울기 {s10:+.4f} < "
                                  f"{stop_on_plateau}) — 종료")
                            break
                    print(line + "   ", end="", flush=True)

                except IOError as e:
                    fails += 1
                    print(f"\n[warn] 읽기 실패 {fails}회: {e}")
                    if fails in (5, 8):
                        print("[info] 포트 재연결 시도...")
                        try:
                            sensor.reconnect()
                            print("[info] 재연결 성공")
                        except Exception as e2:
                            print(f"[warn] 재연결 실패: {e2}")
                    if fails >= 12:
                        print("[error] 연속 실패 12회 — 중단 (데이터는 저장됨)")
                        break

                if duration and (time.time() - t0) >= duration:
                    print("\n지정 시간 도달 — 종료")
                    break
                sleep = interval - (time.time() - loop_start)
                if sleep > 0:
                    time.sleep(sleep)
        except KeyboardInterrupt:
            print("\n사용자 중단 — 파일 저장됨")

    stop_evt.set()
    if evf:
        evf.close()
    print(f"\n저장 완료: {path}")
    if mark:
        print(f"이벤트  : {ev_path}")
        if t_aer is None:
            print("  [경고] 'aeration_on' 마크가 없습니다. "
                  "fit_kla.py 가 t0 를 DO 최저점으로 자동추정합니다 — 정확도 저하.")
    if live.kla:
        cs = (f"포화 {live.cstar/C_NOM*100:.2f} %" if plateau_on == "sat"
              else f"C* ~ {live.cstar:.3f} mg/L")
        print(f"현장 추정: KLa ~ {live.kla*3600:.3f} /h, tau ~ "
              f"{1/live.kla/60:.1f} min, 상한 {cs}  (정식 산출은 fit_kla.py)")


def main():
    p = argparse.ArgumentParser(description="SEN0680 DO 로거 (EX2 재폭기 시험, v2)")
    p.add_argument("--port", required=True, help="COM3 또는 /dev/tty.usbserial-XXXX")
    p.add_argument("--baud", type=int, default=4800)
    p.add_argument("--addr", type=int, default=1)
    p.add_argument("--scan", action="store_true", help="보레이트/주소 탐색")
    p.add_argument("--read", action="store_true", help="단발 읽기 5회")
    p.add_argument("--calibrate", type=int, choices=[0, 100], help="보정 (100 먼저, 그다음 0)")
    p.add_argument("--set-pressure", type=float, help="기압 kPa 입력 (예 101.0)")
    p.add_argument("--set-addr", type=int, help="장치 주소 변경")
    p.add_argument("--set-baud", type=int, choices=sorted(BAUD_CODES), help="보레이트 변경")
    p.add_argument("--log", metavar="CSV", help="로깅 시작, 출력 파일 경로")
    p.add_argument("--interval", type=float, default=1.0, help="폴링 주기 s (기본 1.0)")
    p.add_argument("--duration", type=float, default=0, help="자동 종료 초 (0=무제한)")
    p.add_argument("--note", default="", help="CSV 헤더에 남길 조건 메모")
    p.add_argument("--mark", action="store_true",
                   help="이벤트 마킹 활성 (Enter = 마크). 첫 마크 = aeration_on = t0")
    p.add_argument("--stop-at-tau", type=float, default=None,
                   help="폭기 ON 후 N tau 경과 시 자동 종료 (일반 런: 3.3)")
    p.add_argument("--stop-on-plateau", type=float, default=None,
                   help="말미 기울기가 이 값[mg/L/10min] 밑이면 종료 (기준런: 0.02)")
    p.add_argument("--plateau-tail", type=float, default=600.0,
                   help="평탄 판정에 쓸 말미 구간 [s] (기본 600)")
    p.add_argument("--plateau-on", choices=["sat", "do"], default="sat",
                   help="평탄 판정 기준량. sat=포화도(기본, 수온 표류 면역) / do=원시 DO")
    p.add_argument("--overwrite", action="store_true", help="기존 로그 파일 덮어쓰기 허용")
    p.add_argument("--force", action="store_true",
                   help="--note 필수필드 검증 / 보정 사전판정 무시")
    a = p.parse_args()

    if a.scan:
        do_scan(a.port)
        return

    # --note 필수필드 검증 (로깅일 때만)
    if a.log:
        miss = validate_note(a.note)
        if miss and not a.force:
            sys.exit(
                f"[중단] --note 에 필수 항목이 없습니다: {', '.join(miss)}\n"
                f"  파일럿은 에어스톤 기하를 안 적어 kappa 를 확정하지 못했습니다"
                f"(파일럿_결과 §6.1-6).\n"
                f"  예: --note \"R2, z_start=0.020, "
                f"pos=jangchuk(0.450,0.175,0.105), Na2SO3 2.0g, Co 30mg, "
                f"T=24.1C, P=101.0kPa\"\n"
                f"  검증을 끄려면 --force")
        if miss:
            print(f"[경고] --force 로 필수필드 검증을 건너뜁니다 (누락: {', '.join(miss)})")

    s = Sensor(a.port, baud=a.baud, addr=a.addr)
    try:
        if a.read:
            do_read(s)
        elif a.calibrate is not None:
            do_calibrate(s, a.calibrate, force=a.force)
        elif a.set_pressure is not None:
            s.write_u16(REG_PRESSURE, int(round(a.set_pressure * 100)))
            print(f"기압 설정: {a.set_pressure} kPa (읽기값 "
                  f"{s.read_u16(REG_PRESSURE)/100:.2f})")
        elif a.set_addr is not None:
            s.write_u16(REG_ADDR, a.set_addr)
            print(f"주소 변경 -> {a.set_addr} (다음 접속부터 --addr {a.set_addr})")
        elif a.set_baud is not None:
            s.write_u16(REG_BAUD, BAUD_CODES[a.set_baud])
            print(f"보레이트 변경 -> {a.set_baud} (다음 접속부터 --baud {a.set_baud})")
        elif a.log:
            do_log(s, a.log, a.interval, a.note, a.duration,
                   mark=a.mark, stop_at_tau=a.stop_at_tau,
                   stop_on_plateau=a.stop_on_plateau,
                   plateau_tail=a.plateau_tail, overwrite=a.overwrite,
                   plateau_on=a.plateau_on)
        else:
            p.print_help()
    finally:
        s.close()


if __name__ == "__main__":
    main()
