/* =============================================================================
 * 漁벤져스 — 탁도 프로브 v3.1 펌웨어  (OP앰프 0개 · 커패시터 0개)
 *
 * 설계 진실원: ../02_설계.md      배선: ../03_배선.md      요구: ../01_요구사항.md
 * 보드: DOIT ESP32 DevKit v1 (30핀)
 *
 * ── 배선 (왼쪽 열, USB를 위로 두고 위에서부터)
 *   3번  SVP  = GPIO36  ADC  ← 노드 K (22Ω 션트 양단, 실제 LED 전류)
 *   5번  P34  = GPIO34  ADC  ← 노드 N (PT 이미터, 6.8kΩ 부하)
 *   9번  P25  = GPIO25  →  680Ω → 노드 A   (LED 비트 b0)
 *   10번 P26  = GPIO26  →  330Ω → 노드 A   (LED 비트 b1)
 *   11번 P27  = GPIO27  →  150Ω → 노드 A   (LED 비트 b2)
 *   14번 GND
 *   1번  3V3  (PT 컬렉터도 여기 — 5V 절대 금지)
 *   오른쪽 13번 P4 = GPIO4  DS18B20 (4.7kΩ 풀업)
 *
 * ── 이 펌웨어의 핵심 3가지
 *   1) LED를 끌 때 LOW가 아니라 INPUT(하이임피던스)으로 뗀다. LOW로 두면 그
 *      저항이 다른 비트의 전류를 GND로 빼내는 경로가 되어 R-DAC가 망가진다.
 *   2) 출력은 S = A_sig / A_sense. 실제로 흐른 전류로 나누므로 GPIO 온저항,
 *      LED 순전압, 저항 오차, 레일 드리프트가 전부 상쇄된다. (설계 §5.4)
 *   3) 암(dark) 오프셋은 스칼라가 아니라 (I,Q) 벡터로 뺀다. 미광과 전기적
 *      커플링은 위상이 다르므로 진폭만 빼면 틀린다. (설계 §6.2)
 * ========================================================================== */

#include <Preferences.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>
#include "soc/gpio_struct.h"

// ──────────────────────────────────────────────────────────── 핀
#define PIN_B2      27          // 150 Ω
#define PIN_B1      26          // 330 Ω
#define PIN_B0      25          // 680 Ω
#define PIN_SIG     34          // ADC1_CH6  (실크 P34)
#define PIN_SENSE   35          // ADC1_CH7  (실크 P35)
#define PIN_ONEWIRE  4
// ★ SENSE를 GPIO36(SVP)에서 35로 옮겼다 (2026-07-27 실측 후).
//   GPIO36/39는 RTC 주변장치가 켜질 때 입력이 약 80 ns 동안 GND로 끌린다
//   (ESP32 에라타). 이 글리치는 매 샘플 거의 같은 크기라 DC를 통째로
//   깎아먹는다 — 실측에서 DCsense가 예측 195 mV 대비 104 mV로 나왔다.
//   락인 진폭(AC)은 상수 오프셋에 영향받지 않아 멀쩡했지만, DC 확인점이
//   무용지물이 되므로 평범한 ADC1 핀인 GPIO35로 옮긴다. 35도 입력 전용이다.

static const uint32_t M_B2 = 1UL << PIN_B2;
static const uint32_t M_B1 = 1UL << PIN_B1;
static const uint32_t M_B0 = 1UL << PIN_B0;
static const uint32_t M_ALL = M_B2 | M_B1 | M_B0;

// ──────────────────────────────────────────────────────────── 변조
// f0 조건 (설계 §5.1): 10Hz 배수 && 50Hz 배수 아님 && 60Hz 배수 아님
// 적분시간이 0.1s 정수배면 50·60Hz와 그 고조파가 동시에 널링된다.
//
// ★ f0 상한은 물리가 아니라 analogRead() 속도가 정한다.
//   한 틱에 2채널 = 약 100~120 µs. 틱 주기 1/(SPC·f0)가 그보다 커야 하므로
//   SPC=8에서는 f0 < 약 830 Hz. 더 넓은 스윕이 필요하면 SPC를 4로 낮춘다
//   (f0 < 약 1600 Hz까지 가능, 대신 채널당 유효 표본이 절반).
static const uint16_t F0_TAB[] = { 510, 530, 610, 670, 730, 790 };
static const uint8_t  N_F0 = sizeof(F0_TAB) / sizeof(F0_TAB[0]);
static const uint8_t  SPC  = 8;            // 주기당 단계 수 (8 또는 4)
static const uint32_t T_INT_MS  = 10000;   // 적분 10 s   (0.1 s의 정수배)
static const uint32_t T_STEP_MS = 1600;    // 스윕·교정 1점당 (0.1 s의 정수배)

// 8단계 계단 (설계 §4.1 / §5.2)  비트 = b2 b1 b0
//   100=10.1mA  110=12.3mA  111=14.7mA  010=4.6mA  001=2.2mA
static const uint8_t STEP[SPC] = { 0b100, 0b110, 0b111, 0b110,
                                   0b100, 0b010, 0b001, 0b010 };

// 복조 가중치 w[k]=round(127·sin(2πk/8)),  Q는 w[(k+2)&7]
static const int8_t W[SPC] = { 0, 90, 127, 90, 0, -90, -127, -90 };

static uint32_t EN_MASK[SPC];              // 단계별 출력인에이블 마스크

// L=50mm 포르마진 감도 1.25 %/NTU (설계 §3.1)
static const double SENS_PER_NTU = 0.0125;

// ──────────────────────────────────────────────────────────── 교정값
struct Cal {
  double idark[N_F0];   // 암 오프셋 I (샘플당 정규화)  ← f0마다 다르다
  double qdark[N_F0];
  double a_temp;        // 온도계수 [1/degC]   (설계 §7.4)
  double t_ref;
  double s0;            // 기준선 (f0=F0_TAB[0] 기준, 설계 §8)
  double s0f[N_F0];     // 주파수별 기준선  ← 스윕 진단에 반드시 필요
};
static Cal cal;
static Preferences prefs;

OneWire  oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);

// ──────────────────────────────────────────────────────────── 측정 결과
struct Meas {
  double Isig, Qsig;    // 샘플당 정규화 (암 차감 후)
  double Iref, Qref;
  double aSig, aRef;
  double dcSig, dcRef;
  double S;
  uint32_t n;
  uint8_t  fidx;
  double   overrun_pct; // 타이밍 여유 진단
};

/* ---------------------------------------------------------------------------
 * LED 단계 설정 — 레지스터 직접 조작 (2쓰기, ~0.2 µs)
 *   출력 레벨은 setup에서 한 번 HIGH로 걸어두고, 이후에는 '드라이버 인에이블'만
 *   켜고 끈다. 끄면 그 핀은 하이임피던스가 되어 회로에서 완전히 떨어진다.
 * ------------------------------------------------------------------------ */
static inline void led_step(uint8_t k) {
  const uint32_t en = EN_MASK[k];
  GPIO.enable_w1ts = en;              // 이 단계에 쓰는 비트 → 출력 ON
  GPIO.enable_w1tc = M_ALL & ~en;     // 나머지 → 하이임피던스
}
static inline void led_off() { GPIO.enable_w1tc = M_ALL; }

/* ---------------------------------------------------------------------------
 * 취득 — 코어1 전용 busy-wait 루프 (ISR 아님)
 *   adc1은 ISR 안전이 보장되지 않는다. 측정 듀티가 0.3 %뿐이라 그동안 코어를
 *   독점해도 전력·응답 예산에 영향이 없다.
 * ------------------------------------------------------------------------ */
static Meas acquire(uint8_t fidx, uint32_t t_int_ms,
                    bool ledOn = true, bool applyDark = true)
{
  const uint16_t f0 = F0_TAB[fidx];
  const double period_us = 1000000.0 / (double)((uint32_t)f0 * SPC);
  uint32_t n = (uint32_t)((double)t_int_ms * 1000.0 / period_us);
  n = (n / SPC) * SPC;                       // 부분 주기는 누설을 만든다

  int64_t Is = 0, Qs = 0, Ir = 0, Qr = 0, Ds = 0, Dr = 0;
  uint32_t late = 0;
  const int64_t t0 = esp_timer_get_time();

  for (uint32_t i = 0; i < n; i++) {
    const uint8_t k = i & (SPC - 1);
    const int64_t due = t0 + (int64_t)llround(period_us * (double)i);
    if (esp_timer_get_time() > due) late++;   // 이미 늦었다 = 예산 초과
    while (esp_timer_get_time() < due) { }

    if (ledOn) led_step(k); else led_off();

    const int s = analogRead(PIN_SIG);
    const int c = analogRead(PIN_SENSE);

    const int8_t wi = W[k];
    const int8_t wq = W[(k + 2) & (SPC - 1)];
    Is += (int64_t)s * wi;  Qs += (int64_t)s * wq;
    Ir += (int64_t)c * wi;  Qr += (int64_t)c * wq;
    Ds += s;                Dr += c;
  }
  led_off();

  Meas m;
  m.n = n;  m.fidx = fidx;
  m.overrun_pct = 100.0 * (double)late / (double)n;

  const double N = (double)n;
  m.Isig = (double)Is / N;  m.Qsig = (double)Qs / N;
  m.Iref = (double)Ir / N;  m.Qref = (double)Qr / N;
  m.dcSig = (double)Ds / N; m.dcRef = (double)Dr / N;

  if (applyDark) {                            // 설계 §6.2 — 벡터 차감
    m.Isig -= cal.idark[fidx];
    m.Qsig -= cal.qdark[fidx];
  }
  m.aSig = sqrt(m.Isig * m.Isig + m.Qsig * m.Qsig);
  m.aRef = sqrt(m.Iref * m.Iref + m.Qref * m.Qref);
  m.S    = (m.aRef > 1e-9) ? (m.aSig / m.aRef) : 0.0;   // 설계 §5.4
  return m;
}

// ──────────────────────────────────────────────────────────── 온도
static double read_temp() {
  ds.requestTemperatures();
  const double t = ds.getTempCByIndex(0);
  return (t < -100.0) ? NAN : t;              // 센서 없으면 -127
}

// ──────────────────────────────────────────────────────────── 출력 산출
static double corrected(double S_raw, double T) {
  if (isnan(T) || cal.a_temp == 0.0) return S_raw;
  return S_raw * (1.0 + cal.a_temp * (T - cal.t_ref));   // 설계 §7.4
}
static double to_ntu(double S_raw, double T) {
  const double s = corrected(S_raw, T);
  if (cal.s0 <= 0.0 || s <= 0.0) return NAN;
  return log(cal.s0 / s) / SENS_PER_NTU;                 // 설계 §3.1
}

// ──────────────────────────────────────────────────────────── NVS
static void save_cal() {
  prefs.begin("turb", false);
  prefs.putBytes("id", cal.idark, sizeof(cal.idark));
  prefs.putBytes("qd", cal.qdark, sizeof(cal.qdark));
  prefs.putDouble("a",  cal.a_temp);
  prefs.putDouble("tr", cal.t_ref);
  prefs.putDouble("s0", cal.s0);
  prefs.putBytes("s0f", cal.s0f, sizeof(cal.s0f));
  prefs.end();
}
static void load_cal() {
  memset(cal.idark, 0, sizeof(cal.idark));
  memset(cal.qdark, 0, sizeof(cal.qdark));
  prefs.begin("turb", true);
  prefs.getBytes("id", cal.idark, sizeof(cal.idark));
  prefs.getBytes("qd", cal.qdark, sizeof(cal.qdark));
  cal.a_temp = prefs.getDouble("a",  0.0);
  cal.t_ref  = prefs.getDouble("tr", 25.0);
  cal.s0     = prefs.getDouble("s0", 0.0);
  memset(cal.s0f, 0, sizeof(cal.s0f));
  prefs.getBytes("s0f", cal.s0f, sizeof(cal.s0f));
  prefs.end();
}

/* ---------------------------------------------------------------------------
 * 주파수 스윕 + 중앙값 (설계 §6.3)
 *   특정 f0에서만 값이 튀면 그 주파수에 외부 간섭이 있다는 뜻이다.
 *
 * ★ 반드시 주파수별 기준선 s0f[]로 나눠서 비교한다.
 *   PT는 고유의 저역 롤오프가 있어 S가 f0에 따라 원래 10 % 남짓 변한다.
 *   원시 S의 산포를 그냥 보면 그 롤오프를 '간섭'으로 오진한다 (실측 확인).
 *   s0f[]가 아직 없으면(전부 0) 원시값으로 돌리되 산포 판정은 하지 않는다.
 * ------------------------------------------------------------------------ */
static double sweep(double *spread, bool *valid) {
  double raw[N_F0], v[N_F0];
  bool norm = true;
  for (uint8_t i = 0; i < N_F0; i++) {
    raw[i] = acquire(i, T_STEP_MS).S;
    if (cal.s0f[i] <= 0.0) norm = false;
  }
  for (uint8_t i = 0; i < N_F0; i++) v[i] = norm ? raw[i] / cal.s0f[i] : raw[i];

  for (uint8_t i = 1; i < N_F0; i++) {           // 삽입정렬
    double x = v[i]; int8_t j = i - 1;
    while (j >= 0 && v[j] > x) { v[j + 1] = v[j]; j--; }
    v[j + 1] = x;
  }
  const double med = 0.5 * (v[N_F0 / 2 - 1] + v[N_F0 / 2]);
  if (spread) *spread = (med > 0) ? (v[N_F0 - 1] - v[0]) / med : 0.0;
  if (valid)  *valid  = norm;
  // 정규화한 경우 med는 '기준선 대비 비율'이므로 S 단위로 되돌려 반환
  return norm ? med * cal.s0f[0] : med;
}

/* ---------------------------------------------------------------------------
 * V5 암 교정 — 광로를 물리적으로 차광한 상태에서 1회 실행 (설계 §6.2)
 *   차광 상태에서 남는 (I,Q)는 전부 미광 + 전기 커플링이다. 둘 다 f0에
 *   코히런트한 상수 벡터이므로 구분하지 않고 통째로 빼면 된다.
 * ------------------------------------------------------------------------ */
static void calibrate_dark() {
  Serial.println(F("[V5] 광로를 불투명 판으로 완전히 차단하고 엔터"));
  while (!Serial.available()) delay(50);
  while (Serial.available()) Serial.read();

  for (uint8_t i = 0; i < N_F0; i++) {
    Meas on  = acquire(i, T_STEP_MS, true,  false);   // 차광 + 구동 ON
    Meas off = acquire(i, T_STEP_MS, false, false);   // 차광 + 구동 OFF
    cal.idark[i] = on.Isig;
    cal.qdark[i] = on.Qsig;
    Serial.printf("  f0=%4u Hz  dark|A|=%8.3f  (구동OFF 잔류 %8.3f)",
                  F0_TAB[i], sqrt(on.Isig*on.Isig + on.Qsig*on.Qsig),
                  sqrt(off.Isig*off.Isig + off.Qsig*off.Qsig));
    if (sqrt(off.Isig*off.Isig + off.Qsig*off.Qsig) >
        0.3 * sqrt(on.Isig*on.Isig + on.Qsig*on.Qsig))
      Serial.print(F("  ← 외부 간섭 의심"));
    Serial.println();
  }
  save_cal();
  Serial.println(F("[V5] 차광 해제 후 'm'. 합격 기준: 차광 잔류 < 신호의 5 %"));
}

/* ---------------------------------------------------------------------------
 * 기준선·온도계수 학습 (설계 §8, §7.4)
 *   맑은 물 전제. 하루 중 수온 변동(1~2 degC)이 자연스러운 가진 신호가 된다.
 * ------------------------------------------------------------------------ */
static uint32_t ln_n = 0;
static double ln_sT = 0, ln_sS = 0, ln_sTT = 0, ln_sTS = 0;
static bool   learning = false;

static void learn_reset() {
  ln_n = 0; ln_sT = ln_sS = ln_sTT = ln_sTS = 0; learning = true;
  Serial.println(F("[학습] 시작. 맑은 물에 담근 채로 두세요. 'e'로 종료·확정"));
}
static void learn_feed(double S, double T) {
  if (!learning || isnan(T)) return;
  ln_n++; ln_sT += T; ln_sS += S; ln_sTT += T * T; ln_sTS += T * S;
}
static void learn_finish() {
  learning = false;
  if (ln_n < 8) { Serial.println(F("[학습] 표본 부족 (8회 미만). 폐기")); return; }
  const double n = ln_n, mT = ln_sT / n, mS = ln_sS / n;
  const double den = ln_sTT - n * mT * mT;
  double a = 0.0;
  if (den > 1e-6) a = -(ln_sTS - n * mT * mS) / den / mS;   // 설계 §7.4

  if (fabs(a) > 0.015) {                                   // 안전장치
    Serial.printf("[학습] |a|=%.4f/degC 가 한계 0.015 초과 → a=0으로 폐기\n", fabs(a));
    a = 0.0;
  }
  cal.a_temp = a;  cal.t_ref = mT;  cal.s0 = mS;
  save_cal();
  Serial.printf("[학습] n=%lu  a=%+.5f /degC  T_ref=%.2f C  s0=%.6f\n",
                (unsigned long)ln_n, a, mT, mS);
}

// ──────────────────────────────────────────────────────────── 출력 도우미
static void print_meas(const Meas &m, double T) {
  Serial.printf("f0=%4u  A_sig=%8.3f  A_sense=%8.3f  S=%.6f  "
                "DCsig=%6.1f  DCsense=%6.1f  T=%.2fC  NTU=%+.2f\n",
                F0_TAB[m.fidx], m.aSig, m.aRef, m.S, m.dcSig, m.dcRef,
                T, to_ntu(m.S, T));
  if (m.dcSig > 3800) Serial.println(F("  ! SIG DC 포화 임박 → 개구 축소 또는 RL 인하"));
  if (m.dcRef < 50)   Serial.println(F("  ! SENSE 값이 너무 작다 → 22Ω 션트 배선 확인"));
  if (m.overrun_pct > 1.0)
    Serial.printf("  ! 타이밍 초과 %.1f%% → f0를 낮추거나 적분시간을 늘릴 것\n",
                  m.overrun_pct);
}

// ──────────────────────────────────────────────────────────── setup / loop
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
  // 출력 레벨은 HIGH로 고정해 두고, 이후에는 인에이블만 토글한다
  pinMode(PIN_B2, OUTPUT); pinMode(PIN_B1, OUTPUT); pinMode(PIN_B0, OUTPUT);
  GPIO.out_w1ts = M_ALL;
  led_off();

  analogReadResolution(12);
  // 두 채널의 감쇠는 반드시 동일 (설계 §4.3) — 다르면 비율측정 상쇄가 깨진다
  analogSetPinAttenuation(PIN_SIG,   ADC_11db);
  analogSetPinAttenuation(PIN_SENSE, ADC_11db);

  ds.begin();
  load_cal();

  Serial.println(F("\n=== 탁도 프로브 v3.1 (OP앰프 0 · 커패시터 0) ==="));
  Serial.println(F("m 1회측정 | w 스윕측정 | d V5암교정 | r 원시덤프(단계1·2)"));
  Serial.println(F("b 대역스윕 | L 학습시작 | e 학습종료 | z 기준선즉시설정 | ? 상태"));
}

void loop() {
  if (!Serial.available()) { delay(80); return; }
  const char c = Serial.read();
  while (Serial.available()) Serial.read();

  switch (c) {

  case 'm': {                                   // 1회 측정
    const double T = read_temp();
    Meas m = acquire(0, T_INT_MS);
    print_meas(m, T);
    learn_feed(m.S, T);        // 학습은 '원시' S로 한다 — 보정값을 넣으면 순환참조
    break;
  }

  case 'w': {                                   // 주파수 스윕 (설계 §6.3)
    const double T = read_temp();
    double sp; bool ok;
    const double S = sweep(&sp, &ok);
    Serial.printf("S(median)=%.6f  spread=%.2f%%  T=%.2fC  NTU=%+.2f\n",
                  S, sp * 100.0, T, to_ntu(S, T));
    if (!ok) Serial.println(F("  (주파수별 기준선 없음 — 'z' 먼저. 산포 판정 보류)"));
    else if (sp > 0.03) Serial.println(F("  ! 정규화 후 편차 3% 초과 → 외부 간섭 의심"));
    break;
  }

  case 'd': calibrate_dark(); break;

  case 'b': {                                   // PT 대역폭 확인 (설계 §4.4)
    Serial.println(F("f0별 A_sig — 평탄한 구간에서 f0를 고른다"));
    for (uint8_t i = 0; i < N_F0; i++) {
      Meas m = acquire(i, 2000, true, false);
      Serial.printf("  %4u Hz : A_sig=%8.3f  A_sense=%8.3f  S=%.6f\n",
                    F0_TAB[i], m.aSig, m.aRef, m.S);
    }
    Serial.println(F("  높은 f0에서 A_sig만 떨어지면 PT 대역 한계. 낮은 쪽을 쓸 것"));
    break;
  }

  case 'r': {                                   // 브링업 단계 1·2용 원시 관찰
    Serial.println(F("단계1-a: b2만 → 노드K ~0.22V | 1-b: 전부 → ~0.32V"));
    Serial.println(F("단계2-b: LED ON에서 노드N 1.0~1.4V | 2-c: ON-OFF 차 > 0.8V"));
    const char *nm[4] = { "OFF   ", "b2    ", "b2b1  ", "b2b1b0" };
    const uint32_t mk[4] = { 0, M_B2, M_B2 | M_B1, M_ALL };
    for (uint8_t j = 0; j < 4; j++) {
      GPIO.enable_w1ts = mk[j];
      GPIO.enable_w1tc = M_ALL & ~mk[j];
      delay(50);
      long ss = 0, cc = 0;
      for (int i = 0; i < 64; i++) { ss += analogRead(PIN_SIG); cc += analogRead(PIN_SENSE); }
      const double vs = ss / 64.0 * 3.3 / 4095.0, vc = cc / 64.0 * 3.3 / 4095.0;
      Serial.printf("  %s  노드N=%.3fV  노드K=%.3fV  (I_LED=%.1fmA)\n",
                    nm[j], vs, vc, vc / 22.0 * 1000.0);
    }
    led_off();
    Serial.println(F("  노드K가 단계별로 안 오르면: 끌 때 LOW로 두고 있는지 확인"));
    break;
  }

  case 'L': learn_reset(); break;
  case 'e': learn_finish(); break;

  case 'z': {                       // 기준선 즉시 설정 — 6개 주파수 전부
    const double T = read_temp();
    if (!isnan(T)) cal.t_ref = T;
    for (uint8_t i = 0; i < N_F0; i++) {
      Meas m = acquire(i, T_STEP_MS);
      cal.s0f[i] = corrected(m.S, T);
      Serial.printf("  s0f[%4u Hz] = %.6f\n", F0_TAB[i], cal.s0f[i]);
    }
    cal.s0 = cal.s0f[0];
    save_cal();
    Serial.printf("기준선 설정 완료 @ %.2fC (맑은 물 상태에서만 의미 있음)\n", cal.t_ref);
    break;
  }

  case '?': {
    Serial.printf("s0=%.6f  a=%+.5f/degC  T_ref=%.2fC  학습=%s(n=%lu)\n",
                  cal.s0, cal.a_temp, cal.t_ref,
                  learning ? "진행중" : "정지", (unsigned long)ln_n);
    for (uint8_t i = 0; i < N_F0; i++)
      Serial.printf("  dark[%4u Hz] I=%9.3f Q=%9.3f\n",
                    F0_TAB[i], cal.idark[i], cal.qdark[i]);
    break;
  }
  }
}

/* =============================================================================
 * 아직 없는 것 — 브링업 단계 3(V5)을 통과한 뒤에 붙인다. 순서를 지킨다.
 *   - 매시 1회 자동 측정 + 딥슬립 (T9: 평균 5 mA 미만)
 *   - 기준선 추종 L3: s0를 30일 이동 중앙값으로 갱신하되
 *       현재 NTU < 3 일 때만 갱신 (갱신 게이트 — 설계 §8)
 *   - 세척 이벤트 → 학습 24 h 축약 재실행 (V6 대응)
 *   - 앱 전송 (등급 판정은 SW팀 협의)
 * ========================================================================== */
