/* =============================================================================
 * 漁벤져스 — 탁도 프로브 demo_v2   (BLE JSON 스트리밍)
 *
 * demo_v1의 구조를 그대로 쓴다. 바꾼 것은 (a) 출력 형식을 JSON으로, (b) 2026-07-30
 * 브링업에서 확정된 상수들, (c) 디버깅용 감시 필드다. 측정 알고리즘·교정 체계·
 * BLE 계층은 demo_v1이 이미 옳게 만들어 놓았으므로 손대지 않았다.
 *
 * ── 배선 (무변경, 04_확정사양 §전기)
 *   SVP=GPIO36 ← 노드 K (22 Ω 션트)     P34=GPIO34 ← 노드 N (R5)
 *   P27/P26/P25 → 150/330/680 Ω → 노드 A     P4 = DS18B20 (4.7 kΩ 풀업)
 *   PT 컬렉터는 3.3 V (5 V 절대 금지)
 *
 * ── demo_v1에서 바뀐 것 (전부 2026-07-30 브링업 실측 근거)
 *   1) R5 = 151 kΩ 확정. 관측된 Ic 전 구간(1.71~3.83 µA)에서 피크가 FS 안에
 *      남고 계단 골이 불감대의 1.7배 이상을 유지하는 유일한 값.
 *   2) 두 ADC 채널 0 dB. 노드 K 상한 0.33 V, 노드 N 목표 0.37 V인데 11 dB는
 *      분해능을 3배 버리고 불감대를 3배 넓게 쓴다.
 *      ★ 감쇠를 바꾸면 볼트 환산 기준(VREF)도 같이 바뀐다. 0 dB의 FS는 3.3 V가
 *        아니라 약 1.1 V다. demo_v1의 VREF=3.3 단일 상수를 채널별로 쪼갰다.
 *   3) 계단을 대좌(pedestal) 상향 파형으로. 골/피크 0.132 → 0.597.
 *      R5=151k에서 피크가 0.37 V인데 원본 파형이면 골이 0.048 V로 불감대에
 *      잠긴다. 그 클리핑은 탁도에 따라 변하므로 S에서 상쇄되지 않는다.
 *   4) L_MM 20 → 50 (동결 규격). demo_v1은 벤치 20 mm로 두었다.
 *   5) 예열 20 s → 60 s. 20 s로는 과도구간이 남았다. 예열 없이 RSD 3.30 %,
 *      60 s 예열 후 0.0536 %. 62배 차이이므로 이건 옵션이 아니다.
 *
 * ── 확인점 3-a 결과 (R5=151k, L=50 mm 공기중)
 *   전체 10회 RSD 0.0536 %,  후반 5회 0.0313 %  →  1σ 0.043 NTU
 *   요구 1 NTU 대비 23배 마진. 잡음 바닥 대비 7배이므로 광량은 문제가 아니다.
 *
 * ── 남은 한계는 회로가 아니라 기구다
 *   A_sense는 런간 0.07 %로 완벽히 안정적인데 A_sig는 31 % 움직인다. 구동계는
 *   무죄이고 광 결합이 기구적으로 흔들린다. 3회차 실측에서 S가 한 번에 11.5 %
 *   떨어지고 그 뒤 0.06 %로 안정된 계단이 관측됐다 — 열은 계단을 못 만든다.
 *   그래서 S의 절대값을 신뢰하면 안 되고 기준선('z') 대비 상대값으로 읽는다.
 *   JSON의 jump_pct / flags:"STEP"이 이 현상을 실시간으로 잡는다.
 *
 * ── 폰 연결 (BLE Nordic UART Service)
 *   기기 이름 "FISHDO-TURB". nRF Connect(iOS/Android) 또는
 *   Serial Bluetooth Terminal(BLE 모드). 연결 후 TX 특성의 Notify를 켠다.
 *   JSON 한 줄이 20 B씩 쪼개져 오므로 '\n'까지 모아서 파싱한다. 'h' = 도움말.
 *
 * ★★★ 컴파일 전 확인 ★★★
 *   Tools → Partition Scheme → "Huge APP (3MB No OTA/1MB SPIFFS)"
 *   BLE 스택이 약 1.3 MB라 기본 파티션(APP 1.2 MB)으로는 링크가 실패한다.
 *   Tools → Board → "ESP32 Dev Module"
 * ========================================================================== */

#include <math.h>
#include <stdarg.h>
#include <Preferences.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "soc/gpio_struct.h"

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#include "probe_types.h"        // struct Meas, struct Cal — 반드시 include로

// ────────────────────────────────────────────────────────────────── 핀
#define PIN_B2      27          // 150 Ω  (b2)
#define PIN_B1      26          // 330 Ω  (b1)
#define PIN_B0      25          // 680 Ω  (b0)
#define PIN_SIG     34          // 노드 N
#define PIN_SENSE   36          // 노드 K (실크 SVP)
#define PIN_ONEWIRE  4

// ────────────────────────────────────────────────────────── 전기 상수
static const double ADC_FS = 4095.0;
static const double R_SENSE = 22.0;

/* ★ 두 채널 모두 0 dB. 그래서 볼트 환산 기준이 3.3 V가 아니라 1.1 V다.
 *   demo_v1은 VREF 하나로 두 채널을 처리했는데, 감쇠를 바꾸면 그게 3배 오차가
 *   된다. 채널별로 쪼개는 것이 핵심이다.
 *   "두 채널 감쇠는 반드시 동일"이라는 제약은 없다 — S = aSig/aRef는 비율이라
 *   채널별 고정 배수는 기준선 교정에서 상쇄된다. 필요한 건 '각각 일정'이다. */
static const double VREF_SIG   = 1.100;
static const double VREF_SENSE = 1.100;
static const double VDEAD      = 0.045;   // 0 dB 불감대
static const double VSAT       = 1.000;   // 포화 경보 문턱

// GPIO36/39 에라타: SAR 기동 시 입력이 ~80 ns GND로 끌려 DC가 낮게 읽힌다.
// AC(락인)에는 영향 없다. 노드 N(GPIO34)은 무관.
static const double ERRATA_V = 0.090;

// 노드 N ↔ GND에 실제로 꽂혀 있는 저항. Ic 역산에만 쓴다.
static const double R5_INSTALLED = 151e3;   // 100k + 51k 직렬 — 확정

// isnan()은 툴체인·표준 버전에 따라 매크로가 되기도 std 함수가 되기도 한다.
// NaN은 자기 자신과 같지 않다는 정의를 직접 쓰면 어디서든 동작한다. (demo_v1)
static inline bool is_nan(double x) { return x != x; }

// 광로 [mm]. 동결 규격 50. 감도가 L에 비례하므로 벤치가 다르면 여기를 고친다.
#define L_MM        50.0
static const double SENS_PER_NTU = 0.0125 * (L_MM / 50.0);

// ────────────────────────────────────────────────────────── 락인 파라미터
static const uint16_t F0  = 510;
static const uint8_t  SPC = 8;

/* 계단 파형 — 대좌 상향. 상위 4레벨(100~111)만 쓴다.
 *   컨덕턴스 [mS]: 100=6.67  101=8.14  110=9.70  111=11.17   평균 8.917
 *   골/피크 0.597 (원본 0.132)   기본파/피크 0.246 (원본 0.428)
 *   3고조파 22 %  ← 무해하다. 8점/주기 DFT에서 빈1과 빈3은 직교해 정확히
 *                   소거되고, aRef가 실제 구동 기본파로 정규화한다.
 *
 * 왜 원본이 아닌가: 탁도는 신호를 깎는 방향으로만 움직이므로 청수가 천장이다.
 * 골이 낮으면 신호가 조금 떨어져도 변조 파형의 음의 반주기가 불감대에 잠기고,
 * 그 클리핑 비율은 탁도에 따라 변하므로 S에서 상쇄되지 않는다.
 *   R5=151k 실측 피크 0.366 V →  원본 골 0.048 V (불감대) / 대좌 골 0.219 V
 * AC 진폭 1.74배를 잃지만 잡음 여유가 14배 남으므로 명백히 이득이다. */
static const uint8_t STEP[SPC] = { 0b110, 0b111, 0b111, 0b111,
                                   0b101, 0b100, 0b100, 0b100 };
static const int8_t  W[SPC]    = { 0, 90, 127, 90, 0, -90, -127, -90 };

// DC 평균에서 피크·골을 되짚기 위한 비 (위 컨덕턴스 표에서 유도)
static const double PEAK_OVER_MEAN   = 1.2525;   // 11.168 / 8.917
static const double TROUGH_OVER_MEAN = 0.7477;   //  6.667 / 8.917
static const double FUND_RATIO       = 0.246;    // 기본파진폭 / 피크

static const uint32_t M_B2  = 1UL << PIN_B2;
static const uint32_t M_B1  = 1UL << PIN_B1;
static const uint32_t M_B0  = 1UL << PIN_B0;
static const uint32_t M_ALL = M_B2 | M_B1 | M_B0;
static uint32_t EN_MASK[SPC];

/* ★ 예열. 브링업 최대 발견이다. demo_v1은 20 s였는데 그걸로는 과도구간이 남았다.
 *   예열 없이 전체 RSD 3.2991 %, 60 s 예열 후 0.0536 %. 62배다.
 *   LED가 데워지며 Vf↓→전류↑, 광출력은 −0.5 %/°C↓ 로 두 효과가 S를 같은 방향
 *   으로 흘린다. 그리고 acquire()가 측정 사이에도 계단 구동을 이어가므로
 *   (led_off를 하지 않는다) 한 번 예열한 열 상태가 계속 유지된다. */
static uint32_t PREHEAT_MS = 60000;
static uint32_t T_INT_MS   = 1000;     // 적분 = 갱신 주기. 0.1 s 정수배 유지

// ────────────────────────────────────────────────────────────────── BLE
#define NUS_SERVICE "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX      "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"   // 폰 → ESP32
#define NUS_TX      "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"   // ESP32 → 폰

static BLECharacteristic *pTx = nullptr;
static volatile bool bleConnected = false;
// 기본 MTU 23 B에서 실제로 실을 수 있는 건 20 B다. 협상 결과에 의존하지 않고
// 20 B로 쪼개면 어떤 폰에서도 잘리지 않는다. (demo_v1의 판단을 유지)
static const size_t BLE_CHUNK = 20;

static char cmdBuf[16];
static volatile uint8_t cmdLen = 0;

class SrvCB : public BLEServerCallbacks {
  void onConnect(BLEServer *s) override    { bleConnected = true;  }
  void onDisconnect(BLEServer *s) override { bleConnected = false; s->getAdvertising()->start(); }
};
class RxCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    uint8_t *d = c->getData();
    const size_t n = c->getLength();
    for (size_t i = 0; i < n; i++)
      if (d[i] > 32 && cmdLen < sizeof(cmdBuf) - 1) cmdBuf[cmdLen++] = (char)d[i];
  }
};

/* 출력은 char 버퍼로 만든다. String 연결을 1 Hz로 반복하면 힙이 파편화되어
 * 며칠 돌린 뒤 BLE 할당이 실패한다. demo_v1의 방식을 유지한다. */
static void ble_send(const char *s, size_t n) {
  if (!bleConnected || !pTx) return;
  for (size_t off = 0; off < n; off += BLE_CHUNK) {
    const size_t len = (n - off > BLE_CHUNK) ? BLE_CHUNK : (n - off);
    pTx->setValue((uint8_t *)(s + off), len);
    pTx->notify();
    delay(8);                       // 알림 큐 넘침 방지
  }
}
static void out(const char *s) {
  Serial.print(s);
  ble_send(s, strlen(s));
}
static void outf(const char *fmt, ...) {
  char b[512];                      // JSON 한 줄이 약 450 B다
  va_list ap; va_start(ap, fmt);
  vsnprintf(b, sizeof(b), fmt, ap);
  va_end(ap);
  out(b);
}

// ────────────────────────────────────────────────────────────────── 상태
static Cal cal = { 0, 0, 0, 0, 25.0 };
static Preferences prefs;

OneWire oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);
static double lastT = NAN;

static uint32_t seq = 0;
static bool     paused = false;
static bool     debugOn = true;
static double   sPrev = NAN;
static int64_t  epochOffsetMs = 0;    // 'T<epoch_ms>'로 동기하면 실시각 출력

// S의 이동 RSD (품질 지표). 최근 N개를 링버퍼로 유지한다.
#define RSD_WIN 16
static double  hist[RSD_WIN];
static uint8_t histN = 0, histI = 0;

// ────────────────────────────────────────────────────────────────── LED
static inline void led_step(uint8_t k) {
  const uint32_t en = EN_MASK[k];
  GPIO.enable_w1ts = en;
  GPIO.enable_w1tc = M_ALL & ~en;     // OFF = 하이임피던스 (LOW 금지)
}
static inline void led_off() { GPIO.enable_w1tc = M_ALL; }

// ────────────────────────────────────────────────────────────────── 측정
static Meas acquire(uint32_t ms, bool applyDark = true) {
  const double period_us = 1e6 / ((double)F0 * SPC);
  uint32_t n = (uint32_t)((double)ms * 1000.0 / period_us);
  n = (n / SPC) * SPC;                       // 부분 주기는 누설을 만든다
  if (n < SPC) n = SPC;

  int64_t Is = 0, Qs = 0, Ir = 0, Qr = 0;
  int64_t Ds = 0, Dr = 0;                    // DC 합 (동작점 감시)
  uint32_t late = 0;
  const int64_t t0 = esp_timer_get_time();
  for (uint32_t i = 0; i < n; i++) {
    const uint8_t k = i & (SPC - 1);
    const int64_t due = t0 + (int64_t)llround(period_us * (double)i);
    if (esp_timer_get_time() > due) late++;
    while (esp_timer_get_time() < due) { }
    led_step(k);
    const int s = analogRead(PIN_SIG);
    const int c = analogRead(PIN_SENSE);
    const int8_t wi = W[k], wq = W[(k + 2) & (SPC - 1)];
    Is += (int64_t)s * wi;  Qs += (int64_t)s * wq;  Ds += s;
    Ir += (int64_t)c * wi;  Qr += (int64_t)c * wq;  Dr += c;
  }
  /* ★ 여기서 led_off()를 하지 않는다 — 열 상태를 정상으로 유지하기 위해
   *   측정 사이에도 계단 구동을 이어간다. demo_v1의 핵심 판단이고, 브링업에서
   *   예열 효과가 62배로 확인됐으므로 더욱 그렇다. 그래서 동작점(피크/골)도
   *   LED를 끄고 재는 대신 적분 중 DC 평균에서 되짚는다 — 공짜이고, 열 상태를
   *   흐트러뜨리지 않으며, 매 사이클 감시할 수 있다. */

  Meas m;
  const double N = (double)n;
  m.Isig = Is / N;  m.Qsig = Qs / N;
  if (applyDark) { m.Isig -= cal.idark; m.Qsig -= cal.qdark; }   // 설계 §6.2
  const double Iref = Ir / N, Qref = Qr / N;

  // 가중치 피크 127, sin 상관 → 진폭 = 2·√(I²+Q²)/127 [카운트]
  m.aSig = 2.0 * sqrt(m.Isig * m.Isig + m.Qsig * m.Qsig) / 127.0 * VREF_SIG   / ADC_FS;
  m.aRef = 2.0 * sqrt(Iref * Iref + Qref * Qref)         / 127.0 * VREF_SENSE / ADC_FS;
  m.S    = (m.aRef > 1e-12) ? (m.aSig / m.aRef) : 0.0;           // 설계 §5.4
  m.nMean = (double)Ds / N * VREF_SIG   / ADC_FS;
  m.kMean = (double)Dr / N * VREF_SENSE / ADC_FS;
  m.late_pct = 100.0 * late / N;
  m.samples = n;
  return m;
}

static double corrected(double S) {
  if (is_nan(lastT) || cal.a_temp == 0.0) return S;
  return S * (1.0 + cal.a_temp * (lastT - cal.t_ref));           // 설계 §7.4
}
/* NTU는 Beer-Lambert의 로그 법칙이다. (s0−s)/s0 같은 선형화는 탁도가 작을 때만
 * 맞는다. demo_v1이 이미 옳게 쓰고 있었다. */
static double to_ntu(double S) {
  const double s = corrected(S);
  if (cal.s0 <= 0.0 || s <= 0.0) return NAN;
  return log(cal.s0 / s) / SENS_PER_NTU;                         // 설계 §3.1
}

// ─────────────────────────────────────────────────────────── 이동 RSD
static void hist_push(double s) {
  hist[histI] = s;  histI = (histI + 1) % RSD_WIN;
  if (histN < RSD_WIN) histN++;
}
static void hist_reset() { histN = histI = 0; sPrev = NAN; }
static double hist_rsd() {
  if (histN < 3) return NAN;
  double sum = 0;
  for (uint8_t i = 0; i < histN; i++) sum += hist[i];
  const double m = sum / histN;
  if (fabs(m) < 1e-12) return NAN;
  double sq = 0;
  for (uint8_t i = 0; i < histN; i++) sq += (hist[i] - m) * (hist[i] - m);
  return sqrt(sq / (histN - 1)) / m;
}

// ────────────────────────────────────────────────────────────────── NVS
static void save_cal() {
  prefs.begin("demo", false);
  prefs.putDouble("id", cal.idark); prefs.putDouble("qd", cal.qdark);
  prefs.putDouble("s0", cal.s0);
  prefs.putDouble("a",  cal.a_temp); prefs.putDouble("tr", cal.t_ref);
  prefs.end();
}
static void load_cal() {
  prefs.begin("demo", true);
  cal.idark  = prefs.getDouble("id", 0.0);
  cal.qdark  = prefs.getDouble("qd", 0.0);
  cal.s0     = prefs.getDouble("s0", 0.0);
  cal.a_temp = prefs.getDouble("a",  0.0);
  cal.t_ref  = prefs.getDouble("tr", 25.0);
  prefs.end();
}

// ─────────────────────────────────────────────────────── 시각 문자열
static void time_str(char *b, size_t n) {
  if (epochOffsetMs == 0) {                    // 동기 안 됨 → 부팅 후 경과
    const uint32_t ms = millis();
    snprintf(b, n, "%02lu:%02lu:%02lu.%03lu",
             (unsigned long)(ms / 3600000UL), (unsigned long)((ms / 60000UL) % 60),
             (unsigned long)((ms / 1000UL) % 60), (unsigned long)(ms % 1000UL));
    return;
  }
  const int64_t now = epochOffsetMs + (int64_t)millis();
  const time_t sec = (time_t)(now / 1000);
  struct tm tmv;
  gmtime_r(&sec, &tmv);
  snprintf(b, n, "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
           tmv.tm_year + 1900, tmv.tm_mon + 1, tmv.tm_mday,
           tmv.tm_hour, tmv.tm_min, tmv.tm_sec, (int)(now % 1000));
}

// JSON에서 NaN은 문법 위반이다. null로 내보낸다.
static void jnum(char *b, size_t n, double v, int digits) {
  if (is_nan(v) || isinf(v)) { snprintf(b, n, "null"); return; }
  snprintf(b, n, "%.*f", digits, v);
}

// ────────────────────────────────────────────────────────────────── 명령
static void print_help() {
  out("{\"cmd\":\"help\",\"z\":\"set baseline s0\",\"d\":\"dark cal (block path)\","
      "\"D\":\"clear dark\",\"1\":\"1s\",\"2\":\"2s\",\"3\":\"10s\","
      "\"s\":\"pause\",\"v\":\"toggle dbg\",\"p\":\"re-preheat\","
      "\"T<ms>\":\"set clock\",\"i\":\"info\",\"h\":\"help\"}\n");
}
static void print_info() {
  outf("{\"cmd\":\"info\",\"L_mm\":%.0f,\"sens_pct_ntu\":%.3f,\"f0\":%u,"
       "\"int_ms\":%lu,\"R5_k\":%.0f,\"atten\":\"0dB\",\"step\":\"pedestal\","
       "\"s0\":%.6f,\"idark\":%.1f,\"qdark\":%.1f,\"a_temp\":%+.5f,\"t_ref\":%.2f,"
       "\"preheat_ms\":%lu}\n",
       (double)L_MM, SENS_PER_NTU * 100.0, F0, (unsigned long)T_INT_MS,
       R5_INSTALLED / 1e3, cal.s0, cal.idark, cal.qdark, cal.a_temp, cal.t_ref,
       (unsigned long)PREHEAT_MS);
}

static void do_zero() {
  double acc = 0;
  for (int i = 0; i < 3; i++) acc += acquire(T_INT_MS, true).S;
  cal.s0 = acc / 3.0;
  if (!is_nan(lastT)) cal.t_ref = lastT;
  save_cal();
  hist_reset();
  outf("{\"cmd\":\"zero\",\"ok\":true,\"s0\":%.6f,\"t_ref\":%.2f,"
       "\"note\":\"clear water only\"}\n", cal.s0, cal.t_ref);
}

static void do_dark() {
  out("{\"cmd\":\"dark\",\"stage\":\"block the optical path, 5s\"}\n");
  for (int i = 5; i > 0; i--) { outf("{\"cmd\":\"dark\",\"countdown\":%d}\n", i); delay(1000); }
  Meas m = acquire(T_INT_MS, false);        // 차감 전 원시 (I,Q)
  cal.idark = m.Isig; cal.qdark = m.Qsig;
  save_cal();
  hist_reset();
  outf("{\"cmd\":\"dark\",\"ok\":true,\"idark\":%.1f,\"qdark\":%.1f,"
       "\"A_dark_mV\":%.3f,\"note\":\"unblock now; residual <5%% of signal = V5 pass\"}\n",
       cal.idark, cal.qdark, m.aSig * 1000.0);
}

static void preheat_now() {
  outf("{\"cmd\":\"preheat\",\"ms\":%lu}\n", (unsigned long)PREHEAT_MS);
  const int64_t t0 = esp_timer_get_time();
  uint32_t k = 0;
  while (esp_timer_get_time() - t0 < (int64_t)PREHEAT_MS * 1000) {
    led_step(k++ & (SPC - 1));
    delayMicroseconds(245);                  // ≈ 510 Hz × 8단계
  }
  hist_reset();
  out("{\"cmd\":\"preheat\",\"ok\":true}\n");
}

static void handle(char c) {
  switch (c) {
  case 'z': do_zero();  break;
  case 'd': do_dark();  break;
  case 'D': cal.idark = cal.qdark = 0; save_cal();
            out("{\"cmd\":\"cleardark\",\"ok\":true}\n"); break;
  case '1': T_INT_MS = 1000;  hist_reset(); print_info(); break;
  case '2': T_INT_MS = 2000;  hist_reset(); print_info(); break;
  case '3': T_INT_MS = 10000; hist_reset(); print_info(); break;
  case 's': paused = !paused;
            outf("{\"cmd\":\"pause\",\"on\":%s}\n", paused ? "true" : "false"); break;
  case 'v': debugOn = !debugOn;
            outf("{\"cmd\":\"dbg\",\"on\":%s}\n", debugOn ? "true" : "false"); break;
  case 'p': preheat_now(); break;
  case 'i': print_info();  break;
  case 'h': print_help();  break;
  default: break;
  }
}

/* 'T<epoch_ms>'는 여러 문자를 모아야 하므로 별도로 처리한다. handle()은 한
 * 글자씩 받으므로, 'T'가 오면 뒤따르는 숫자를 이 버퍼에 모은다. */
static char  tsBuf[16];
static uint8_t tsLen = 0;
static bool  tsMode = false;

static void feed(char c) {
  if (tsMode) {
    if (c >= '0' && c <= '9' && tsLen < sizeof(tsBuf) - 1) { tsBuf[tsLen++] = c; return; }
    tsBuf[tsLen] = 0;
    if (tsLen) {
      const int64_t v = atoll(tsBuf);
      if (v > 0) {
        epochOffsetMs = v - (int64_t)millis();
        out("{\"cmd\":\"clock\",\"ok\":true}\n");
      }
    }
    tsMode = false; tsLen = 0;
    if (c != ';' && c != '\n' && c != '\r') handle(c);
    return;
  }
  if (c == 'T') { tsMode = true; tsLen = 0; return; }
  handle(c);
}

static void poll_cmd() {
  while (Serial.available()) feed((char)Serial.read());
  while (cmdLen > 0) {                       // BLE 수신 버퍼
    const char c = cmdBuf[0];
    for (uint8_t i = 1; i < cmdLen; i++) cmdBuf[i - 1] = cmdBuf[i];
    cmdLen--;
    feed(c);
  }
  if (tsMode && tsLen > 0) {                 // 구분자 없이 끝난 경우 정리
    tsBuf[tsLen] = 0;
    const int64_t v = atoll(tsBuf);
    if (v > 0) { epochOffsetMs = v - (int64_t)millis();
                 out("{\"cmd\":\"clock\",\"ok\":true}\n"); }
    tsMode = false; tsLen = 0;
  }
}

// ────────────────────────────────────────────────────────────────── setup
void setup() {
  Serial.begin(115200);
  delay(300);

  for (uint8_t k = 0; k < SPC; k++) {
    uint32_t e = 0;
    if (STEP[k] & 0b100) e |= M_B2;
    if (STEP[k] & 0b010) e |= M_B1;
    if (STEP[k] & 0b001) e |= M_B0;
    EN_MASK[k] = e;
  }
  pinMode(PIN_B2, OUTPUT); pinMode(PIN_B1, OUTPUT); pinMode(PIN_B0, OUTPUT);
  GPIO.out_w1ts = M_ALL;                     // 레벨은 HIGH 고정, 인에이블만 토글
  led_off();

  analogReadResolution(12);
  analogSetPinAttenuation(PIN_SIG,   ADC_0db);   // ★ 11 dB 아님. VREF도 1.1 V
  analogSetPinAttenuation(PIN_SENSE, ADC_0db);

  ds.begin();
  ds.setWaitForConversion(false);            // 750 ms 블로킹 회피 (demo_v1)
  ds.requestTemperatures();

  load_cal();

  // ── 안전검사. 노드 N 포화는 PT 컬렉터가 5 V에 물린 경우이며
  //    이 회로 유일의 파손 경로다. 구동 전에 확인한다.
  long acc = 0;
  for (int i = 0; i < 64; i++) acc += analogRead(PIN_SIG);
  const double n0 = (double)acc / 64.0 * VREF_SIG / ADC_FS;
  Serial.printf("\n암전압 노드 N = %.4f V\n", n0);
  if (n0 > 0.95 * VREF_SIG) {
    Serial.println(F("#### 즉시 USB를 뽑으세요 — 노드 N 포화 ####"));
    Serial.println(F("  PT 컬렉터가 5V(VIN)에 물렸거나 극성이 반대입니다."));
    while (true) delay(1000);                // 구동 전면 금지
  }

  // ── BLE (Nordic UART Service)
  BLEDevice::init("FISHDO-TURB");
  BLEDevice::setMTU(185);                    // 협상은 폰이 정한다. 실패해도 20 B로 동작
  BLEServer *srv = BLEDevice::createServer();
  srv->setCallbacks(new SrvCB());
  BLEService *svc = srv->createService(NUS_SERVICE);

  pTx = svc->createCharacteristic(NUS_TX, BLECharacteristic::PROPERTY_NOTIFY);
  pTx->addDescriptor(new BLE2902());
  BLECharacteristic *pRx = svc->createCharacteristic(
      NUS_RX, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  pRx->setCallbacks(new RxCB());

  svc->start();
  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(NUS_SERVICE);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();

  Serial.println(F("BLE 광고 시작: FISHDO-TURB (Nordic UART Service)"));
  Serial.printf("예열 %lu s — 이 구간의 값은 버립니다\n", (unsigned long)(PREHEAT_MS / 1000));

  const int64_t t0 = esp_timer_get_time();
  uint32_t k = 0;
  while (esp_timer_get_time() - t0 < (int64_t)PREHEAT_MS * 1000) {
    led_step(k++ & (SPC - 1));
    delayMicroseconds(245);
  }
  print_info();
  print_help();
}

// ────────────────────────────────────────────────────────────────── loop
void loop() {
  poll_cmd();
  if (paused) { led_off(); delay(200); return; }

  // 직전 사이클에 요청해 둔 온도를 읽고, 다음 변환을 즉시 요청한다.
  // 동기 호출은 750 ms를 잡아먹어 1 s 주기를 깨뜨린다.
  const double t = ds.getTempCByIndex(0);
  lastT = (t < -100.0) ? NAN : t;
  ds.requestTemperatures();

  Meas m = acquire(T_INT_MS, true);
  seq++;

  const double ntu = to_ntu(m.S);

  // ── 동작점. LED를 끄지 않고 적분 중 DC 평균에서 되짚는다.
  const double nPeak   = m.nMean * PEAK_OVER_MEAN;
  const double nTrough = m.nMean * TROUGH_OVER_MEAN;
  const double ic      = nPeak / R5_INSTALLED;              // A (암전압 무시)
  const double iLed    = (m.kMean * PEAK_OVER_MEAN + ERRATA_V) / R_SENSE;

  // ── 품질 지표
  hist_push(m.S);
  const double rsd = hist_rsd();
  const double jump = (is_nan(sPrev) || fabs(sPrev) < 1e-12)
                    ? NAN : (m.S - sPrev) / sPrev;
  sPrev = m.S;

  /* ★ 계단형 불연속 감지. 브링업 3회차에서 S가 한 번에 11.5 % 떨어지고 그 뒤
   *   0.06 %로 안정된 사례가 있었다. 열 드리프트는 계단을 못 만든다.
   *   aRef가 같이 튀지 않았다면 구동계는 무죄이고 원인은 광축 정렬 또는
   *   R5/PT 납땜이다. 이걸 실시간으로 잡는 것이 이 펌웨어의 핵심 감시 항목이다. */
  const bool stepJump = (!is_nan(jump) && !is_nan(rsd) && rsd > 1e-9
                         && fabs(jump) > 20.0 * rsd);

  // ── 플래그
  char flags[64]; flags[0] = 0;
  if (nPeak   > VSAT)        strcat(flags, "SAT,");
  if (nPeak   < VDEAD)       strcat(flags, "DEAD,");
  if (nTrough < 2.0 * VDEAD) strcat(flags, "TROUGH,");
  if (m.late_pct > 1.0)      strcat(flags, "LATE,");
  if (stepJump)              strcat(flags, "STEP,");
  if (cal.s0 <= 0.0)         strcat(flags, "NOBASE,");
  if (is_nan(lastT))         strcat(flags, "NOTEMP,");
  const size_t fl = strlen(flags);
  if (fl && flags[fl - 1] == ',') flags[fl - 1] = 0;

  // ── JSON
  char ts[32];  time_str(ts, sizeof(ts));
  char bT[16], bIR[16], bN[16], bR[16], bJ[16], bNtu[16], bSig[16];
  jnum(bT,   sizeof(bT),   lastT, 2);
  jnum(bIR,  sizeof(bIR),  m.S,   6);
  jnum(bNtu, sizeof(bNtu), ntu,   3);
  jnum(bR,   sizeof(bR),   is_nan(rsd)  ? NAN : rsd * 100.0,  4);
  jnum(bJ,   sizeof(bJ),   is_nan(jump) ? NAN : jump * 100.0, 3);
  jnum(bSig, sizeof(bSig), is_nan(rsd)  ? NAN : rsd / SENS_PER_NTU, 4);
  (void)bN;

  if (debugOn) {
    outf("{\"time\":\"%s\",\"temperature\":%s,\"IR\":%s,"
         "\"dbg\":{\"seq\":%lu,\"ntu\":%s,\"A_sig_mV\":%.3f,\"A_sense_mV\":%.3f,"
         "\"N_mean_V\":%.4f,\"N_peak_V\":%.4f,\"N_trough_V\":%.4f,"
         "\"K_mean_V\":%.4f,\"Ic_nA\":%.1f,\"I_led_mA\":%.2f,"
         "\"rsd_pct\":%s,\"rsd_n\":%u,\"sigma_ntu\":%s,\"jump_pct\":%s,"
         "\"late_pct\":%.3f,\"samples\":%lu,\"s0\":%.6f,\"int_ms\":%lu,"
         "\"up_s\":%lu,\"heap\":%lu,\"ble\":%s,\"flags\":\"%s\"}}\n",
         ts, bT, bIR,
         (unsigned long)seq, bNtu, m.aSig * 1000.0, m.aRef * 1000.0,
         m.nMean, nPeak, nTrough, m.kMean, ic * 1e9, iLed * 1000.0,
         bR, (unsigned)histN, bSig, bJ,
         m.late_pct, (unsigned long)m.samples, cal.s0, (unsigned long)T_INT_MS,
         (unsigned long)(millis() / 1000UL), (unsigned long)ESP.getFreeHeap(),
         bleConnected ? "true" : "false", flags);
  } else {
    outf("{\"time\":\"%s\",\"temperature\":%s,\"IR\":%s}\n", ts, bT, bIR);
  }
}

/* =============================================================================
 * 데모에서 유의할 것
 *   - 제품은 1시간 주기·듀티 0.28 %다. 이 데모는 LED를 계속 구동하므로
 *     소비전류가 T9(5 mA) 기준을 넘는다. 시연 전용이다.
 *   - 하우징 없이 쓰면 실내광에서 A_sig가 −22 % 압축된다(2026-07-29 실측).
 *     외부광 조건을 바꾸며 시연하면 값이 크게 흔들린다. T8·V5의 몫이다.
 *   - NTU는 기준선 대비 상대값이다('z'). 표준액 교정은 설계상 하지 않는다(D3).
 *     런간 S가 31 % 움직이므로 절대값 환산은 불가능하다. 매 세션 'z'가 필요하다.
 *   - flags:"STEP"이 뜨면 기구를 의심한다. A_sense가 안 튀는데 A_sig만 튄 것이면
 *     광축 정렬 또는 R5/PT 납땜이다. 't' 상태에서 배선을 톡톡 쳐 보면 갈린다.
 * ========================================================================== */
