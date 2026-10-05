/* =============================================================================
 * 漁벤져스 — 탁도 프로브 demo_v1   (BLE 스트리밍 데모)
 *
 * 목적: 연속 자동 측정을 BLE로 휴대폰(아이폰 포함)에 실시간 송신한다.
 *       사람이 읽는 텍스트와 CSV를 한 줄씩 번갈아 보내므로, 폰에서 보면서
 *       동시에 복사해 엑셀로 그래프를 그릴 수 있다.
 *
 * 근거: ../../04_확정사양.md (v3.1 freeze)  ·  ../../02_설계.md §5 락인
 *       배선 점검은 ../bringup_check/ 로 먼저 통과시킬 것
 *
 * ── 배선 (bringup_check와 동일, 04_확정사양 §전기)
 *   SVP=GPIO36 ← 노드 K (22 Ω 션트)     P34=GPIO34 ← 노드 N (15 kΩ)
 *   P27/P26/P25 → 150/330/680 Ω → 노드 A     P4 = DS18B20 (4.7 kΩ 풀업)
 *   PT 컬렉터는 3.3 V (5 V 절대 금지)
 *
 * ── 폰 연결 (BLE Nordic UART Service)
 *   기기 이름 "FISHDO-TURB". 앱: nRF Connect(iOS/Android) 또는
 *   Serial Bluetooth Terminal(BLE 모드). 연결 후 TX 특성의 Notify를 켠다.
 *   앱에서 문자를 보내면 명령으로 동작한다 ('h' = 도움말).
 *
 * ── 이 펌웨어가 bringup_check와 다른 점 3가지
 *   1) 부팅 시 한 번 예열한 뒤 LED를 계속 변조 구동한다.
 *      2026-07-29 확인점 3-a에서 S가 100 s 동안 −0.335 % 단조 감소했다.
 *      잡음(RSD 0.03 %)이 아니라 LED 예열 과도였다. 열 상태를 정상으로
 *      유지하면 이 항이 사라진다. (제품은 1시간 주기라 매번 예열이 필요하다)
 *   2) ADC1만 쓴다. BLE는 ADC2를 막지만 GPIO34/36은 ADC1이라 무관하다.
 *   3) 락인 루프는 busy-wait이므로 BLE 스택(코어0)의 방해를 받을 수 있다.
 *      매 측정마다 타이밍 초과율을 함께 내보내 이를 감시한다.
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

// ────────────────────────────────────────────────────────────────── 핀·상수
#define PIN_B2      27
#define PIN_B1      26
#define PIN_B0      25
#define PIN_SIG     34          // 노드 N
#define PIN_SENSE   36          // 노드 K (실크 SVP)
#define PIN_ONEWIRE  4

static const double VREF   = 3.3;
static const double ADC_FS = 4095.0;

// isnan()은 툴체인·표준 버전에 따라 매크로가 되기도 std 함수가 되기도 한다.
// NaN은 자기 자신과 같지 않다는 정의를 직접 쓰면 어디서든 동작한다.
static inline bool is_nan(double x) { return x != x; }

// 광로 [mm]. 동결 규격은 50. 벤치가 다르면 여기를 고친다 (감도가 L에 비례).
#define L_MM        20.0
static const double SENS_PER_NTU = 0.0125 * (L_MM / 50.0);

// 락인 (02_설계 §5)
static const uint16_t F0  = 510;
static const uint8_t  SPC = 8;
static const uint8_t  STEP[SPC] = { 0b100, 0b110, 0b111, 0b110,
                                    0b100, 0b010, 0b001, 0b010 };
static const int8_t   W[SPC]    = { 0, 90, 127, 90, 0, -90, -127, -90 };

static const uint32_t M_B2 = 1UL << PIN_B2;
static const uint32_t M_B1 = 1UL << PIN_B1;
static const uint32_t M_B0 = 1UL << PIN_B0;
static const uint32_t M_ALL = M_B2 | M_B1 | M_B0;

static uint32_t EN_MASK[SPC];

static uint32_t PREHEAT_MS = 20000;    // 부팅 예열 (열 시정수 수십 초)
static uint32_t T_INT_MS   = 2000;     // 적분 = 갱신 주기. 0.1 s 정수배 유지

// ────────────────────────────────────────────────────────────────── BLE
#define NUS_SERVICE "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX      "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"   // 폰 → ESP32
#define NUS_TX      "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"   // ESP32 → 폰

static BLECharacteristic *pTx = nullptr;
static volatile bool bleConnected = false;
// 기본 MTU 23 B에서 실제로 실을 수 있는 건 20 B다. 협상 결과에 의존하지 않고
// 20 B로 쪼개면 어떤 폰에서도 잘리지 않는다.
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

// ────────────────────────────────────────────────────────────────── 출력
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
  char b[256];
  va_list ap; va_start(ap, fmt);
  vsnprintf(b, sizeof(b), fmt, ap);
  va_end(ap);
  out(b);
}

// ────────────────────────────────────────────────────────────────── 상태
struct Cal { double idark, qdark, s0, a_temp, t_ref; };
static Cal cal = { 0, 0, 0, 0, 25.0 };
static Preferences prefs;

OneWire oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);
static double lastT = NAN;

static uint32_t seq = 0;
static bool     paused = false;

// ────────────────────────────────────────────────────────────────── LED
static inline void led_step(uint8_t k) {
  const uint32_t en = EN_MASK[k];
  GPIO.enable_w1ts = en;
  GPIO.enable_w1tc = M_ALL & ~en;     // OFF = 하이임피던스 (LOW 금지)
}
static inline void led_off() { GPIO.enable_w1tc = M_ALL; }

// ────────────────────────────────────────────────────────────────── 측정
struct Meas {
  double Isig, Qsig, aSig, aRef, S, late_pct;
};

static Meas acquire(uint32_t ms, bool applyDark = true) {
  const double period_us = 1e6 / ((double)F0 * SPC);
  uint32_t n = (uint32_t)((double)ms * 1000.0 / period_us);
  n = (n / SPC) * SPC;                       // 부분 주기는 누설을 만든다

  int64_t Is = 0, Qs = 0, Ir = 0, Qr = 0;
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
    Is += (int64_t)s * wi;  Qs += (int64_t)s * wq;
    Ir += (int64_t)c * wi;  Qr += (int64_t)c * wq;
  }
  // ★ 여기서 led_off()를 하지 않는다 — 열 상태를 정상으로 유지하기 위해
  //   측정 사이에도 계단 구동을 이어간다 (예열 과도 제거).

  Meas m;
  const double N = (double)n;
  m.Isig = Is / N;  m.Qsig = Qs / N;
  if (applyDark) { m.Isig -= cal.idark; m.Qsig -= cal.qdark; }   // 설계 §6.2 벡터 차감
  const double Iref = Ir / N, Qref = Qr / N;

  // 가중치 피크 127, sin 상관 → 진폭 = 2·√(I²+Q²)/127 [카운트]
  m.aSig = 2.0 * sqrt(m.Isig * m.Isig + m.Qsig * m.Qsig) / 127.0 * VREF / ADC_FS;
  m.aRef = 2.0 * sqrt(Iref * Iref + Qref * Qref)         / 127.0 * VREF / ADC_FS;
  m.S    = (m.aRef > 1e-12) ? (m.aSig / m.aRef) : 0.0;           // 설계 §5.4
  m.late_pct = 100.0 * late / N;
  return m;
}

static double corrected(double S) {
  if (is_nan(lastT) || cal.a_temp == 0.0) return S;
  return S * (1.0 + cal.a_temp * (lastT - cal.t_ref));           // 설계 §7.4
}
static double to_ntu(double S) {
  const double s = corrected(S);
  if (cal.s0 <= 0.0 || s <= 0.0) return NAN;
  return log(cal.s0 / s) / SENS_PER_NTU;                         // 설계 §3.1
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

// ────────────────────────────────────────────────────────────────── 명령
static void print_header() {
  out("\n=== FISHDO 탁도 프로브 demo_v1 ===\n");
  outf("L=%.0f mm  감도 %.2f %%/NTU  f0=%u Hz  적분 %lu ms\n",
       L_MM, SENS_PER_NTU * 100.0, F0, (unsigned long)T_INT_MS);
  outf("기준선 s0=%.6f  암벡터(%.1f, %.1f)  a=%+.5f/degC\n",
       cal.s0, cal.idark, cal.qdark, cal.a_temp);
  out("#HDR,seq,t_ms,S,NTU,T_C,Asig_mV,Asense_mV,late_pct\n");
}
static void print_help() {
  out("\n[명령] z 기준선재설정 | d 암교정(차광) | D 암교정삭제\n");
  out("       1 적분2s | 2 적분10s | s 일시정지 | i 상태 | h 도움말\n");
}

static void do_zero() {
  out("\n[z] 기준선 설정 — 맑은 물(또는 기준 상태)에서만 의미가 있습니다\n");
  double acc = 0;
  for (int i = 0; i < 3; i++) acc += acquire(T_INT_MS, true).S;
  cal.s0 = acc / 3.0;
  if (!is_nan(lastT)) cal.t_ref = lastT;
  save_cal();
  outf("  s0 = %.6f  @ %.2f C\n", cal.s0, cal.t_ref);
}

static void do_dark() {
  out("\n[d] 암 교정 — 광로를 불투명한 것으로 막으세요. 5초 뒤 측정합니다\n");
  for (int i = 5; i > 0; i--) { outf("  %d...\n", i); delay(1000); }
  Meas m = acquire(T_INT_MS, false);        // 차감 전 원시 (I,Q)
  cal.idark = m.Isig; cal.qdark = m.Qsig;
  save_cal();
  outf("  암 벡터 (%.1f, %.1f)  |A_dark| = %.2f mV\n",
       cal.idark, cal.qdark, m.aSig * 1000.0);
  out("  차광을 해제하세요. 잔류가 신호의 5 %% 미만이어야 합격입니다 (V5)\n");
}

static void handle(char c) {
  switch (c) {
  case 'z': do_zero();  break;
  case 'd': do_dark();  break;
  case 'D': cal.idark = cal.qdark = 0; save_cal(); out("\n[D] 암 교정 삭제\n"); break;
  case '1': T_INT_MS = 2000;  outf("\n적분 %lu ms\n", (unsigned long)T_INT_MS); break;
  case '2': T_INT_MS = 10000; outf("\n적분 %lu ms\n", (unsigned long)T_INT_MS); break;
  case 's': paused = !paused; outf("\n%s\n", paused ? "일시정지" : "재개"); break;
  case 'i': print_header(); break;
  case 'h': print_help();   break;
  default: break;
  }
}
static void poll_cmd() {
  while (Serial.available()) handle((char)Serial.read());
  while (cmdLen > 0) {                       // BLE 수신 버퍼
    const char c = cmdBuf[0];
    for (uint8_t i = 1; i < cmdLen; i++) cmdBuf[i - 1] = cmdBuf[i];
    cmdLen--;
    handle(c);
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
  analogSetPinAttenuation(PIN_SIG,   ADC_11db);   // 두 채널 감쇠 동일 (설계 §4.3)
  analogSetPinAttenuation(PIN_SENSE, ADC_11db);

  ds.begin();
  ds.setWaitForConversion(false);            // 750 ms 블로킹 회피
  ds.requestTemperatures();

  load_cal();

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

  /* ── 예열
   *   2026-07-29 실측: 냉시동 후 100 s 동안 S가 −0.335 % 단조 감소했다.
   *   LED가 데워지며 Vf↓→전류↑인데 광출력은 −0.5 %/degC↓ 라 비율이 흐른다.
   *   잡음(RSD 0.03 %)의 10배가 넘는 항이므로 반드시 지나 보내야 한다. */
  Serial.printf("예열 %lu s — 이 구간의 값은 버립니다\n", (unsigned long)(PREHEAT_MS / 1000));
  const int64_t t0 = esp_timer_get_time();
  uint32_t k = 0;
  while (esp_timer_get_time() - t0 < (int64_t)PREHEAT_MS * 1000) {
    led_step(k++ & (SPC - 1));
    delayMicroseconds(245);                  // ≈ 510 Hz × 8단계
  }
  print_header();
  print_help();
}

// ────────────────────────────────────────────────────────────────── loop
void loop() {
  poll_cmd();
  if (paused) { led_off(); delay(200); return; }

  // 직전 사이클에 요청해 둔 온도를 읽고, 다음 변환을 즉시 요청한다
  const double t = ds.getTempCByIndex(0);
  lastT = (t < -100.0) ? NAN : t;
  ds.requestTemperatures();

  Meas m = acquire(T_INT_MS, true);
  seq++;

  const double ntu = to_ntu(m.S);

  // 사람이 읽는 줄
  outf("[%4lu] S=%.6f  NTU=%s%.2f  T=%.2fC  Asig=%6.1fmV  Asense=%6.1fmV\n",
       (unsigned long)seq, m.S,
       is_nan(ntu) ? "--" : (ntu >= 0 ? "+" : ""), is_nan(ntu) ? 0.0 : ntu,
       is_nan(lastT) ? -99.0 : lastT, m.aSig * 1000.0, m.aRef * 1000.0);

  // 기계가 읽는 줄
  outf("#CSV,%lu,%lu,%.6f,%.3f,%.2f,%.2f,%.2f,%.3f\n",
       (unsigned long)seq, (unsigned long)millis(), m.S,
       is_nan(ntu) ? 0.0 : ntu, is_nan(lastT) ? -99.0 : lastT,
       m.aSig * 1000.0, m.aRef * 1000.0, m.late_pct);

  if (cal.s0 <= 0.0 && seq == 1)
    out("  ! 기준선이 없습니다. 기준 상태에서 'z'를 보내면 NTU가 나옵니다\n");
  if (m.late_pct > 1.0)
    outf("  ! 타이밍 초과 %.1f %% — BLE 부하로 락인 표본이 밀렸습니다\n", m.late_pct);
}

/* =============================================================================
 * 데모에서 유의할 것
 *   - 제품은 1시간 주기·듀티 0.28 %다. 이 데모는 LED를 계속 구동하므로
 *     소비전류가 T9(5 mA) 기준을 넘는다. 시연 전용이다.
 *   - 하우징 없이 쓰면 실내광에서 A_sig가 −22 % 압축된다(2026-07-29 실측).
 *     외부광 조건을 바꾸며 시연하면 값이 크게 흔들린다. T8·V5의 몫이다.
 *   - NTU는 기준선 대비 상대값이다('z'). 표준액 교정은 설계상 하지 않는다(D3).
 * ========================================================================== */
