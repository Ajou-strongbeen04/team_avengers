/* =============================================================================
 * 漁벤져스 — 탁도 프로브 v3.1  배선 점검 전용 펌웨어  (멀티미터 없이)
 *
 * 목적: 회로도(TURBIDITY_v31.sch / 회로도.svg)대로 납땜한 하드웨어를
 *       ESP32 자신의 ADC만으로 검증한다. 측정은 하지 않는다.
 * 근거: ../../04_확정사양.md (v3.1 freeze, 2026-07-27) — 값 충돌 시 이 표가 이김
 *       ../../02_설계.md §10 브링업 절차
 *
 * ── 핀 (04_확정사양.md §전기 확정)
 *   1번  3V3  ← PT 컬렉터 (5 V 절대 금지)
 *   3번  SVP  = GPIO36  ADC ← 노드 K (22 Ω 션트 상단)     ★SENSE
 *   5번  P34  = GPIO34  ADC ← 노드 N (PT 이미터, 15 kΩ)   ★SIG
 *   9번  P25  → 680 Ω → 노드 A   (b0)
 *   10번 P26  → 330 Ω → 노드 A   (b1)
 *   11번 P27  → 150 Ω → 노드 A   (b2)
 *   14번 GND
 *   오른쪽 13번 P4 = GPIO4  DS18B20 (4.7 kΩ 풀업)
 *
 * ── 안전 규칙 2개 (코드로 강제)
 *   1) LED 비트는 절대 LOW로 두지 않는다. 출력 레벨을 HIGH로 고정하고
 *      '드라이버 인에이블'만 토글해 OFF = 하이임피던스가 되게 한다.
 *   2) 부팅 직후 노드 N이 포화(>4000 카운트)면 즉시 중단하고 경고한다.
 *      PT 컬렉터가 5 V에 물린 경우이며, 이 회로의 유일한 파손 경로다.
 *
 * ── 사용법
 *   115200 baud. 부팅하면 안전검사 후 메뉴가 뜬다.
 *   a = 자동검사 전체 (T0~T5, 손 안 대고 진행)
 *   i = 대화형 검사 (T6~T8, 차광/조명 지시를 따른다)
 *   개별: 0 1 2 3 4 5 6 7 8   |   ? = 요약 다시 보기
 * ========================================================================== */

#define USE_DS18B20  1          // DS18B20을 아직 안 붙였으면 0으로

#include <math.h>
#include "soc/gpio_struct.h"
#if USE_DS18B20
  #include <OneWire.h>
  #include <DallasTemperature.h>
#endif

// ────────────────────────────────────────────────────────────────── 핀·상수
#define PIN_B2      27          // 150 Ω
#define PIN_B1      26          // 330 Ω
#define PIN_B0      25          // 680 Ω
#define PIN_SIG     34          // 노드 N
#define PIN_SENSE   36          // 노드 K  (실크 SVP)
#define PIN_ONEWIRE  4

static const double R_SENSE  = 22.0;      // Ω  (04_확정사양)
static const double R_LOAD   = 15000.0;   // Ω  (04_확정사양, 6.8k 아님)
static const double VREF     = 3.3;
static const double ADC_FS   = 4095.0;

// GPIO36/39 ESP32 에라타: SAR ADC 기동 시 입력이 ~80 ns GND로 끌려
// DC가 약 90 mV 낮게 읽힌다. AC(락인)에는 영향 없음.
static const double ERRATA_V = 0.090;

// ★ ESP32 ADC 11 dB 불감대. 이 아래 입력은 그냥 0 카운트로 읽힌다.
//   노드 K의 저전류 계단(b1=101 mV, b0=48 mV)은 통째로 여기 잠긴다.
//   → 개별 절대값으로 저항을 판정하면 반드시 오진한다. 증분으로만 판정한다.
//     (v1 펌웨어가 이 오진을 냈다: raw 0에 에라타 90 mV를 더해 유령 4.09 mA)
static const double V_DEAD = 0.140;

// 락인 (02_설계 §5)
// 시험 배치의 실제 광로 [mm]. 동결 규격은 50 mm이나 벤치 시험은 짧게 한다.
// 감도가 L에 비례하므로 이 값을 안 고치면 해상도가 낙관적으로 찍힌다.
#define L_TEST_MM   20.0

static const uint16_t F0    = 510;
static const uint8_t  SPC   = 8;
static const uint8_t  STEP[SPC] = { 0b100, 0b110, 0b111, 0b110,
                                    0b100, 0b010, 0b001, 0b010 };
static const int8_t   W[SPC]    = { 0, 90, 127, 90, 0, -90, -127, -90 };

// 설계 예상 전류 [mA] (02_설계 §4.1)
static const double I_EXP_B2  = 10.1, I_EXP_B1 = 4.6, I_EXP_B0 = 2.2, I_EXP_ALL = 14.7;
// 계단 구동 기본파 5.85 mA × 22 Ω = 128.7 mV (04_확정사양 §전기 주석, 실측 124 mV)
static const double A_SENSE_EXP_V = 0.1287;

static const uint32_t M_B2 = 1UL << PIN_B2;
static const uint32_t M_B1 = 1UL << PIN_B1;
static const uint32_t M_B0 = 1UL << PIN_B0;
static const uint32_t M_ALL = M_B2 | M_B1 | M_B0;

#if USE_DS18B20
OneWire oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);
#endif

static int  n_fail = 0, n_warn = 0, n_pass = 0;
static bool halted = false;     // 안전검사 실패 시 모든 구동 금지

// ────────────────────────────────────────────────────────────────── 도우미
static inline void bits_on(uint32_t mask) {
  if (halted) return;
  GPIO.enable_w1ts = mask;
  GPIO.enable_w1tc = M_ALL & ~mask;      // 나머지는 하이임피던스 (LOW 아님)
}
static inline void bits_off() { GPIO.enable_w1tc = M_ALL; }

static double adc_v(int pin, int n = 64) {
  long acc = 0;
  for (int i = 0; i < n; i++) acc += analogRead(pin);
  return (double)acc / n * VREF / ADC_FS;
}
static double adc_raw(int pin, int n = 64) {
  long acc = 0;
  for (int i = 0; i < n; i++) acc += analogRead(pin);
  return (double)acc / n;
}
static double adc_sd(int pin, int n = 128) {      // 부유핀 판별용 표준편차
  double s = 0, ss = 0;
  for (int i = 0; i < n; i++) { const double x = analogRead(pin); s += x; ss += x * x; }
  const double m = s / n;
  return sqrt(fmax(0.0, ss / n - m * m)) * VREF / ADC_FS;
}
// 노드 K = GPIO36. raw는 보정 없음, vK()는 에라타를 되올린 참고값.
// ★ raw가 V_DEAD 아래면 vK()는 의미가 없다 (0 + 0.090 = 유령 90 mV).
static double vKraw() { return adc_v(PIN_SENSE); }
static double vK()    { return adc_v(PIN_SENSE) + ERRATA_V; }
static double vN()    { return adc_v(PIN_SIG); }
static int    peakN(int n = 400) {          // 펄스광(리모컨 38 kHz) 포착용
  int pk = 0;
  for (int i = 0; i < n; i++) { const int a = analogRead(PIN_SIG); if (a > pk) pk = a; }
  return pk;
}

static void judge(const char *name, int lvl, const char *hint) {
  // lvl: 0=PASS 1=WARN 2=FAIL
  const char *tag = (lvl == 0) ? "[PASS]" : (lvl == 1) ? "[WARN]" : "[FAIL]";
  if (lvl == 0) n_pass++; else if (lvl == 1) n_warn++; else n_fail++;
  Serial.printf("  %s %s", tag, name);
  if (hint && hint[0]) Serial.printf("  → %s", hint);
  Serial.println();
}
static void wait_enter(const char *msg) {
  Serial.printf("  >> %s  (엔터)\n", msg);
  while (Serial.available()) Serial.read();
  while (!Serial.available()) delay(50);
  while (Serial.available()) Serial.read();
}

/* ---------------------------------------------------------------------------
 * T0 — 안전검사. 구동 전, 무조건 먼저.
 *      C2(PT 컬렉터 3.3 V) · C1(단락) · 점퍼 유무를 전원 상태에서 판정한다.
 * ------------------------------------------------------------------------ */
static void t0_safety() {
  Serial.println(F("\n[T0] 안전검사 — LED 전부 하이임피던스"));
  bits_off();
  delay(100);

  const double rawN = adc_raw(PIN_SIG, 128);
  const double rawK = adc_raw(PIN_SENSE, 128);
  const double vn = rawN * VREF / ADC_FS;
  const double vk = rawK * VREF / ADC_FS + ERRATA_V;
  const double sdN = adc_sd(PIN_SIG);
  Serial.printf("  노드 N = %.3f V (raw %.0f, sd %.1f mV)   노드 K = %.3f V (raw %.0f)\n",
                vn, rawN, sdN * 1000.0, vk, rawK);

  if (rawN > 4000) {
    halted = true;
    Serial.println(F("\n  ################ 즉시 USB를 뽑으세요 ################"));
    Serial.println(F("  노드 N이 ADC 포화. 원인 후보:"));
    Serial.println(F("    (1) PT 컬렉터가 5V(VIN)에 물림  ← 이 회로 유일의 파손 경로"));
    Serial.println(F("    (2) PT 극성 반대 (긴 다리=컬렉터)"));
    Serial.println(F("    (3) 노드 N이 3.3V 레일에 직결"));
    Serial.println(F("  #####################################################\n"));
    judge("T0 안전", 2, "구동 전면 금지. 재배선 후 재부팅");
    return;
  }
  if (vn > 0.5)
    judge("T0-a 암전압(노드 N)", 1, "외광 유입 과다 또는 하우징 미장착. 개구를 조일 것");
  else
    judge("T0-a 암전압(노드 N) < 0.5 V", 0, "");

  if (sdN > 0.020)
    judge("T0-b R_L 15k 연결", 2, "노드 N이 부유(잡음 과다). 15 kΩ이 N↔GND에 있는지 확인");
  else
    judge("T0-b R_L 15k 연결(노드 N 안정)", 0, "");

  if (fabs(vk - ERRATA_V) > 0.06)
    judge("T0-c 노드 K 무전류 0 V", 2, "LED OFF인데 K에 전압. A가 3.3V에 직결됐거나 점퍼 오결선");
  else
    judge("T0-c 노드 K 무전류 0 V", 0, "");
}

/* ---------------------------------------------------------------------------
 * T1 — R-DAC 비트별 전류. 저항 3개의 값·순서·GPIO 배정을 한 번에 본다.
 * ------------------------------------------------------------------------ */
static double I_all = 0;

static void t1_rdac() {
  if (halted) return;
  Serial.println(F("\n[T1] R-DAC — 저항 판정은 '증분'으로만 한다"));
  Serial.println(F("     (b1=101 mV, b0=48 mV는 ADC 불감대에 잠겨 개별 절대값이 0이 된다)"));

  struct { const char *nm; uint32_t m; } tb[5] = {
    { "000 (전부 OFF)", 0                },
    { "100 (b2만)    ", M_B2             },
    { "110 (b2+b1)   ", M_B2 | M_B1      },
    { "111 (전부)    ", M_ALL            },
    { "010 (b1만)    ", M_B1             },
  };
  double v[5];
  for (int j = 0; j < 5; j++) {
    bits_on(tb[j].m);
    delay(60);
    v[j] = vKraw();
    Serial.printf("  %s : raw V_K=%.3f V%s\n", tb[j].nm, v[j],
                  (v[j] > 0.0 && v[j] < V_DEAD) ? "  (불감대)" : "");
  }
  bits_off();

  // 증분 = 에라타 상수·불감대 오프셋이 상쇄된다
  const double d_b1 = v[2] - v[1];          // b1 추가분
  const double d_b0 = v[3] - v[2];          // b0 추가분
  const double i_b1 = d_b1 / R_SENSE * 1000.0;
  const double i_b0 = d_b0 / R_SENSE * 1000.0;
  const double i_b2 = (v[1] + ERRATA_V) / R_SENSE * 1000.0;
  I_all = (v[3] + ERRATA_V) / R_SENSE * 1000.0;

  Serial.printf("  증분 b1 = %.3f V → %.2f mA (설계 %.1f)\n", d_b1, i_b1, I_EXP_B1);
  Serial.printf("  증분 b0 = %.3f V → %.2f mA (설계 %.1f)\n", d_b0, i_b0, I_EXP_B0);
  Serial.printf("  b2(에라타 보정) = %.2f mA (설계 %.1f)   전전류 = %.2f mA (설계 %.1f)\n",
                i_b2, I_EXP_B2, I_all, I_EXP_ALL);

  if (I_all < 1.0) {
    judge("T1-a LED 도통", 2,
          "전류 0. LED 극성 반대(긴다리=A) 또는 노드 A/K 단선. LED는 역방향으로 안 망가짐");
    return;
  }
  judge("T1-a LED 도통", 0, "");

  // 저항 순서: 680 Ω 가지가 가장 적게 흘러야 한다
  if (d_b1 > d_b0 && d_b0 > 0.005 && v[1] > d_b1)
    judge("T1-b 저항 순서 150<330<680", 0, "");
  else if (d_b0 <= 0.005)
    judge("T1-b 저항 순서", 1, "b0 증분이 너무 작아 판정 보류. P25↔노드 A 결선만 육안 확인");
  else
    judge("T1-b 저항 순서", 2,
          "증분 순서가 뒤집힘 = 저항이 바뀌어 붙음. P27=150R, P26=330R, P25=680R");

  const double r10 = (d_b0 > 1e-4) ? d_b1 / d_b0 : 999.0;
  Serial.printf("  b1/b0 증분비 = %.2f  (설계 %.2f = 680/330)\n", r10, 680.0 / 330.0);
  if (r10 > 1.3 && r10 < 3.2) judge("T1-c 저항비(330:680)", 0, "");
  else                        judge("T1-c 저항비(330:680)", 1, "증분이 작아 오차가 크다. 순서가 맞으면 진행");

  if (fabs(I_all / I_EXP_ALL - 1.0) > 0.35)
    judge("T1-d 전전류 14.7 mA", 2, "22 Ω 션트 값 또는 3.3V 레일 확인. 100 Ω이면 전류가 1/5로 보인다");
  else
    judge("T1-d 전전류 14.7 mA", 0, "");
}

/* ---------------------------------------------------------------------------
 * T2 — 8단계 계단. 인에이블 토글이 실제로 하이임피던스인지 본다.
 * ------------------------------------------------------------------------ */
static void t2_staircase() {
  if (halted) return;
  Serial.println(F("\n[T2] 8단계 계단 — 끌 때 하이임피던스인지 검증"));
  double vmax = 0, vmin = 9;
  bool dead = false;
  for (uint8_t k = 0; k < SPC; k++) {
    uint32_t m = 0;
    if (STEP[k] & 0b100) m |= M_B2;
    if (STEP[k] & 0b010) m |= M_B1;
    if (STEP[k] & 0b001) m |= M_B0;
    bits_on(m);
    delay(40);
    const double v = vKraw();                  // ★ raw로 본다 (에라타 더하지 않음)
    if (v < V_DEAD) dead = true;
    vmax = fmax(vmax, v); vmin = fmin(vmin, v);
    Serial.printf("  k=%u  비트=%c%c%c  raw V_K=%.3f V%s\n", k,
                  (STEP[k] & 4) ? '1' : '0', (STEP[k] & 2) ? '1' : '0',
                  (STEP[k] & 1) ? '1' : '0', v, (v < V_DEAD) ? "  (불감대)" : "");
  }
  bits_off();
  Serial.printf("  raw 최대=%.3f V  최소=%.3f V  진폭=%.3f V\n", vmax, vmin, vmax - vmin);

  // ★ 하위 계단이 불감대에 잠기면 최대/최소 비는 의미가 없다(0으로 나눔).
  //   대신 '계단이 실제로 움직이는가'를 진폭으로 본다. 정량 판정은 T7 락인이 한다.
  if (vmax - vmin > 0.10)
    judge("T2 계단 구동", 0, "OFF 비트가 하이임피던스로 떨어지고 있다");
  else
    judge("T2 계단 구동", 2,
          "계단 진폭 부족 = OFF 비트가 LOW로 남아 다른 가지 전류를 GND로 뺀다. 노드 A 결선 확인");
  if (dead)
    judge("T2-b 불감대", 1,
          "하위 계단이 ADC 불감대(<0.14 V)에 잠김. 설계상 정상이며 T7 A_sense를 약 16% 낮춘다");
}

/* ---------------------------------------------------------------------------
 * T3 — 채널 뒤바뀜 판별. SENSE(GPIO36)와 SIG(GPIO34) 점퍼가 서로 바뀌면
 *      두 핀 모두 LED에 반응하므로 '크기'로만 구분된다.
 *      노드 K는 22 Ω 양단이라 0.3 V를 넘을 수 없다.
 * ------------------------------------------------------------------------ */
static void t3_swap() {
  if (halted) return;
  Serial.println(F("\n[T3] SENSE/SIG 점퍼 교차 판별"));
  bits_on(M_ALL);
  delay(80);
  const double vk = vK(), vn = vN();
  bits_off();
  Serial.printf("  GPIO36(SENSE) = %.3f V   GPIO34(SIG) = %.3f V\n", vk, vn);

  if (vk > 0.60)
    judge("T3 채널 배정", 2,
          "GPIO36이 0.6 V 초과 = 노드 K일 수 없다(22Ω×15mA=0.33V 상한). 두 점퍼가 바뀐 것");
  else if (vk > 0.20 && vk < 0.45)
    judge("T3 채널 배정", 0, "");
  else
    judge("T3 채널 배정", 1, "V_K가 예상창(0.22~0.40 V) 밖. T1 결과와 함께 판단");
}

/* ---------------------------------------------------------------------------
 * T4 — 광 응답 (LED ON/OFF 차). 노드 N의 절대창은 R_L에 비례하므로
 *      02_설계 §10의 1.0~1.4 V는 6.8 kΩ 기준이다. 15 kΩ에서는 약 2.2배.
 * ------------------------------------------------------------------------ */
static void t4_optical() {
  if (halted) return;
  Serial.println(F("\n[T4] 광 응답 — LED ON/OFF"));
  bits_off(); delay(120);
  const double n_off = vN();
  bits_on(M_ALL); delay(120);
  const double n_on = vN();
  bits_off();
  const double d = n_on - n_off;
  Serial.printf("  노드 N : OFF=%.3f V  ON=%.3f V  Δ=%.3f V\n", n_off, n_on, d);
  Serial.println(F("  참고: 공기중 L=50 mm에서 R_L=6.8k일 때 0.366 V였으므로"));
  Serial.println(F("        R_L=15k에서는 대략 0.8 V가 정상. §10의 1.0~1.4 V는 6.8k 기준이다"));

  if (d < 0.05)
    judge("T4-a 광 응답", 2,
          "LED가 안 켜지거나(폰 카메라로 보라색 확인) PT가 안 보고 있음. 정렬·극성 확인");
  else
    judge("T4-a 광 응답", 0, "");

  /* ★ 동작점 판정 — 배선이 맞아도 여기서 막힐 수 있다.
   *   노드 N은 '측정량이 움직이는' 노드다. 동작점이 ADC 불감대 안이면 변조
   *   파형의 음의 반주기가 잘려 나가고, 그 클리핑은 조도에 따라 달라지므로
   *   상수 배수가 아니다 = S에서 상쇄되지 않는다. (노드 K의 클리핑과 성격이 다름)
   *   기준: §10 확인점 2-b(1.0~1.4 V @ R_L=6.8k)를 15 kΩ으로 환산 → 2.2~3.1 V.
   *         현실적 하한은 불감대 0.14 V의 여유 3배 = 0.42 V로 잡는다. */
  if (n_on < V_DEAD)
    judge("T4-c 동작점(불감대 회피)", 2,
          "노드 N 전체가 ADC 불감대 안. 변조 파형이 잘린다 → 정렬·개구 개선 또는 R_L 상향");
  else if (n_on < 0.42)
    judge("T4-c 동작점(불감대 회피)", 1, "불감대 여유 3배 미만. 선형성 위험");
  else
    judge("T4-c 동작점(불감대 회피)", 0, "");

  if (n_on > 3.0)
    judge("T4-b 포화 여유", 2, "노드 N 포화. R_L을 낮추거나 개구를 조일 것");
  else
    judge("T4-b 포화 여유", 0, "");
}

/* ---------------------------------------------------------------------------
 * T5 — analogRead 타이밍 예산. f0 상한은 물리가 아니라 이 속도가 정한다.
 * ------------------------------------------------------------------------ */
static void t5_timing() {
  Serial.println(F("\n[T5] ADC 타이밍"));
  const int N = 500;
  const int64_t t0 = esp_timer_get_time();
  for (int i = 0; i < N; i++) { analogRead(PIN_SIG); analogRead(PIN_SENSE); }
  const double us = (double)(esp_timer_get_time() - t0) / N;
  const double f0max = 1e6 / (us * SPC);
  Serial.printf("  2채널 1틱 = %.1f µs → f0 상한 ≈ %.0f Hz (SPC=8)\n", us, f0max);
  if (f0max > 800.0) judge("T5 f0=510~790 Hz 여유", 0, "");
  else               judge("T5 f0 여유", 1, "스윕 상단 790 Hz가 빠듯. SPC를 4로 낮추는 선택지");
}

/* ---------------------------------------------------------------------------
 * T6 — DS18B20
 * ------------------------------------------------------------------------ */
static void t6_ds18b20() {
#if USE_DS18B20
  Serial.println(F("\n[T6] DS18B20 (GPIO4 + 4.7 kΩ 풀업)"));
  ds.begin();
  const int n = ds.getDeviceCount();
  Serial.printf("  검출 %d개\n", n);
  if (n == 0) {
    judge("T6 DS18B20", 2, "4.7 kΩ이 P4↔3V3에 있는지, 노랑=DQ·빨강=3V3·검정=GND인지 확인");
    return;
  }
  ds.requestTemperatures();
  const double t = ds.getTempCByIndex(0);
  Serial.printf("  T = %.2f °C\n", t);
  if (t < -50.0)       judge("T6 DS18B20", 2, "-127 = 통신 실패. 풀업 또는 DQ 배선");
  else if (t < 5.0 || t > 45.0) judge("T6 DS18B20", 1, "실온 범위 밖. 배선 재확인");
  else                 judge("T6 DS18B20", 0, "");
#else
  Serial.println(F("\n[T6] DS18B20 — USE_DS18B20=0 으로 건너뜀"));
#endif
}

/* ---------------------------------------------------------------------------
 * T7 — 락인 종합. A_sense 하나가 22 Ω·R-DAC·GPIO36·ADC 감쇠를 동시에 검증한다.
 *      계단 기본파 5.85 mA × 22 Ω = 128.7 mV, 실측 기준 124 mV (오차 4 %).
 * ------------------------------------------------------------------------ */
static void t7_lockin() {
  if (halted) return;
  Serial.println(F("\n[T7] 락인 2 s @ 510 Hz"));

  // ── 예측: 방금 읽은 DC 계단으로 기본파를 직접 계산한다.
  //    불감대 클리핑까지 포함된 값이라 락인 결과와 이것이 맞아야 복조·타이밍이 옳다.
  double pred_I = 0, pred_Q = 0;
  for (uint8_t k = 0; k < SPC; k++) {
    uint32_t m = 0;
    if (STEP[k] & 0b100) m |= M_B2;
    if (STEP[k] & 0b010) m |= M_B1;
    if (STEP[k] & 0b001) m |= M_B0;
    bits_on(m); delay(30);
    const double v = vKraw();
    pred_I += v * (double)W[k];
    pred_Q += v * (double)W[(k + 2) & (SPC - 1)];
  }
  bits_off();
  const double pred_v = 2.0 * sqrt(pred_I * pred_I + pred_Q * pred_Q) / (double)SPC / 127.0;
  Serial.printf("  DC 계단으로부터의 예측 A_sense = %.1f mV (불감대 클리핑 포함)\n",
                pred_v * 1000.0);

  const double period_us = 1e6 / ((double)F0 * SPC);
  uint32_t n = (uint32_t)(2.0e6 / period_us);  n = (n / SPC) * SPC;

  int64_t Is = 0, Qs = 0, Ir = 0, Qr = 0;
  uint32_t late = 0;
  const int64_t t0 = esp_timer_get_time();
  for (uint32_t i = 0; i < n; i++) {
    const uint8_t k = i & (SPC - 1);
    const int64_t due = t0 + (int64_t)llround(period_us * (double)i);
    if (esp_timer_get_time() > due) late++;
    while (esp_timer_get_time() < due) { }
    uint32_t m = 0;
    if (STEP[k] & 0b100) m |= M_B2;
    if (STEP[k] & 0b010) m |= M_B1;
    if (STEP[k] & 0b001) m |= M_B0;
    bits_on(m);
    const int s = analogRead(PIN_SIG);
    const int c = analogRead(PIN_SENSE);
    const int8_t wi = W[k], wq = W[(k + 2) & (SPC - 1)];
    Is += (int64_t)s * wi;  Qs += (int64_t)s * wq;
    Ir += (int64_t)c * wi;  Qr += (int64_t)c * wq;
  }
  bits_off();

  const double N = (double)n;
  // 가중치 피크 127, sin 상관 → 진폭 = 2·√(I²+Q²)/127  [카운트]
  const double Asig_c = 2.0 * sqrt(pow(Is / N, 2) + pow(Qs / N, 2)) / 127.0;
  const double Aref_c = 2.0 * sqrt(pow(Ir / N, 2) + pow(Qr / N, 2)) / 127.0;
  const double Asig_v = Asig_c * VREF / ADC_FS;
  const double Aref_v = Aref_c * VREF / ADC_FS;
  Serial.printf("  A_sense = %.1f mV  (이론 %.1f mV, %+.1f%%)\n",
                Aref_v * 1000.0, A_SENSE_EXP_V * 1000.0,
                (Aref_v / A_SENSE_EXP_V - 1.0) * 100.0);
  Serial.printf("  A_sig   = %.1f mV     S = A_sig/A_sense = %.4f\n",
                Asig_v * 1000.0, (Aref_v > 1e-9) ? Asig_v / Aref_v : 0.0);
  Serial.printf("  타이밍 초과 %.2f %%\n", 100.0 * late / N);

  // 판정 기준은 이론 128.7 mV가 아니라 '방금 잰 DC 계단의 예측값'이다.
  // 이론과의 차이는 불감대 클리핑이므로 결함이 아니다 (상수 배수 → S에서 상쇄).
  if (pred_v > 1e-6 && fabs(Aref_v / pred_v - 1.0) < 0.10)
    judge("T7-a A_sense (DC 계단과 정합)", 0, "복조·타이밍·22Ω·R-DAC 정상");
  else
    judge("T7-a A_sense (DC 계단과 정합)", 2,
          "락인 결과가 DC 계단 예측과 어긋남 = 타이밍 또는 복조 위상 문제");
  Serial.printf("  참고: 이론 128.7 mV 대비 %+.1f%% — 차이는 불감대 클리핑이며 상수 배수라 S에서 상쇄\n",
                (Aref_v / A_SENSE_EXP_V - 1.0) * 100.0);

  if (Asig_v < 0.005) judge("T7-b A_sig", 2, "변조 광이 PT에 도달하지 않는다. T4 재확인");
  else                judge("T7-b A_sig", 0, "");

  if (100.0 * late / N > 1.0) judge("T7-c 타이밍", 1, "f0를 낮추거나 SPC=4");
  else                        judge("T7-c 타이밍", 0, "");
}

/* ---------------------------------------------------------------------------
 * T8 — 대화형: 차광 / 외광. 하우징 유무를 여기서 본다.
 * ------------------------------------------------------------------------ */
static void t8_interactive() {
  if (halted) return;
  Serial.println(F("\n[T8] 대화형 — 차광·외광"));

  bits_on(M_ALL); delay(100);
  const double open_v = vN();
  bits_off();
  Serial.printf("  개방 상태 노드 N = %.3f V\n", open_v);

  wait_enter("광로를 불투명한 것으로 완전히 막으세요");
  bits_on(M_ALL); delay(150);
  const double blk_v = vN();
  bits_off();
  const double resid = (open_v > 1e-6) ? blk_v / open_v : 1.0;
  Serial.printf("  차광 상태 노드 N = %.3f V  (잔류 %.0f %%)\n", blk_v, resid * 100.0);
  if (resid < 0.05)      judge("T8-a 미광(V5 예비)", 0, "");
  else if (resid < 0.35) judge("T8-a 미광(V5 예비)", 1,
        "하우징 없는 상태의 예상 결과(공기중 실측 28%). 스파인 M3 스테인리스로 잡는다");
  else                   judge("T8-a 미광(V5 예비)", 2, "우회광 과다. 개구·배플·스파인 재점검");

  wait_enter("차광은 유지한 채, 실내등을 켜고 손전등을 프로브에 직사하세요");
  const double amb_v = vN();
  Serial.printf("  외광 노드 N = %.3f V (차광 대비 %+.3f V)\n", amb_v, amb_v - blk_v);
  if (amb_v - blk_v < 0.10) judge("T8-b 외광 차단(T8 요구)", 0, "");
  else                      judge("T8-b 외광 차단", 1, "락인이 흡수할 수 있으나 개구를 조이는 편이 낫다");

  wait_enter("차광을 해제하세요");
}

/* ---------------------------------------------------------------------------
 * R — 확인점 3-a. 이 회로가 쓸 만한가를 가르는 단 하나의 숫자.
 *
 *     신호 절대크기가 아니라 '반복 재현성'이 요구(T3 드리프트 2.5 %, T6 1 NTU)를
 *     결정한다. 1 NTU가 ADC 1 LSB 아래라도 락인이 40,800 샘플을 평균하면
 *     뚫릴 수 있다 — 디더가 있다면. 그 여부는 계산이 아니라 이 시험이 답한다.
 *
 *     합격: S의 RSD < 0.1 %   (02_설계.md §10 확인점 3-a)
 * ------------------------------------------------------------------------ */
static void lockin_once(uint32_t ms, double *Asig_v, double *Aref_v, double *late_pct) {
  const double period_us = 1e6 / ((double)F0 * SPC);
  uint32_t n = (uint32_t)((double)ms * 1000.0 / period_us);  n = (n / SPC) * SPC;
  int64_t Is = 0, Qs = 0, Ir = 0, Qr = 0;
  uint32_t late = 0;
  const int64_t t0 = esp_timer_get_time();
  for (uint32_t i = 0; i < n; i++) {
    const uint8_t k = i & (SPC - 1);
    const int64_t due = t0 + (int64_t)llround(period_us * (double)i);
    if (esp_timer_get_time() > due) late++;
    while (esp_timer_get_time() < due) { }
    uint32_t m = 0;
    if (STEP[k] & 0b100) m |= M_B2;
    if (STEP[k] & 0b010) m |= M_B1;
    if (STEP[k] & 0b001) m |= M_B0;
    bits_on(m);
    const int s = analogRead(PIN_SIG);
    const int c = analogRead(PIN_SENSE);
    const int8_t wi = W[k], wq = W[(k + 2) & (SPC - 1)];
    Is += (int64_t)s * wi;  Qs += (int64_t)s * wq;
    Ir += (int64_t)c * wi;  Qr += (int64_t)c * wq;
  }
  bits_off();
  const double N = (double)n;
  *Asig_v = 2.0 * sqrt(pow(Is / N, 2) + pow(Qs / N, 2)) / 127.0 * VREF / ADC_FS;
  *Aref_v = 2.0 * sqrt(pow(Ir / N, 2) + pow(Qr / N, 2)) / 127.0 * VREF / ADC_FS;
  *late_pct = 100.0 * late / N;
}

static void r_repeat() {
  if (halted) return;
  const int REP = 10;
  const uint32_t T_INT = 10000;      // 확인점 3-a와 동일한 10 s 적분
  Serial.printf("\n[R] 확인점 3-a — %d회 × %lu s (약 %lu s 소요). 프로브를 건드리지 마세요\n",
                REP, (unsigned long)(T_INT / 1000),
                (unsigned long)(REP * T_INT / 1000));

  double s[REP], sum = 0, sumsq = 0;
  for (int i = 0; i < REP; i++) {
    double asig, aref, late;
    lockin_once(T_INT, &asig, &aref, &late);
    s[i] = (aref > 1e-12) ? asig / aref : 0.0;
    sum += s[i]; sumsq += s[i] * s[i];
    Serial.printf("  %2d/%d  A_sig=%7.2f mV  A_sense=%7.2f mV  S=%.6f\n",
                  i + 1, REP, asig * 1000.0, aref * 1000.0, s[i]);
  }
  const double m  = sum / REP;
  const double sd = sqrt(fmax(0.0, sumsq / REP - m * m)) * sqrt((double)REP / (REP - 1.0));
  const double rsd = (m > 1e-12) ? sd / m : 1.0;

  Serial.printf("\n  S 평균 = %.6f   표준편차 = %.3e   RSD = %.4f %%\n",
                m, sd, rsd * 100.0);
  // ★ 감도는 광로 L에 비례한다 (50 mm에서 1.25 %/NTU). 시험 배치가 20 mm면
  //   감도는 0.5 %/NTU이고 해상도는 2.5배 나빠진다. L을 안 넣으면 낙관 오판.
  const double sens = 0.0125 * (L_TEST_MM / 50.0);
  Serial.printf("  → 시험 배치 L=%.0f mm (감도 %.2f %%/NTU)에서 1σ ≈ %.3f NTU\n",
                L_TEST_MM, sens * 100.0, rsd / sens);
  Serial.printf("     동결 규격 L=50 mm(1.25 %%/NTU)로 환산하면 1σ ≈ %.3f NTU\n",
                rsd / 0.0125);

  // 단조 추세 = 잡음이 아니라 예열 드리프트. 둘을 구분하지 않으면 오판한다.
  double first3 = (s[0] + s[1] + s[2]) / 3.0;
  double last3  = (s[REP - 3] + s[REP - 2] + s[REP - 1]) / 3.0;
  const double trend = (m > 1e-12) ? (last3 - first3) / m : 0.0;
  Serial.printf("  추세(마지막3 − 처음3) = %+.4f %%", trend * 100.0);
  if (fabs(trend) > 1.5 * rsd) {
    Serial.println(F("  ← 산포보다 큼 = 예열 드리프트, 잡음 아님"));
    Serial.println(F("     (LED가 데워지며 Vf↓→전류↑, 광출력은 −0.5 %/°C↓ → S가 흐른다)"));
    Serial.println(F("     대책: 측정 전 예열 후 적분 시작. 잡음 바닥은 후반부 산포로 볼 것"));
  } else {
    Serial.println(F("  ← 산포 이내 = 열적으로 안정"));
  }

  if (rsd < 0.001)
    judge("R 확인점 3-a (RSD < 0.1 %)", 0,
          "잡음은 문제가 아니다. 신호가 작아도 진행 가능 — 남은 관문은 드리프트(T3)와 V5");
  else if (rsd < 0.004)
    judge("R 확인점 3-a", 1,
          "T6(1 NTU, 1σ)는 통과하나 여유가 없다. 적분 30 s로 늘려 재시험(T7 한도 60 s)");
  else
    judge("R 확인점 3-a", 2,
          "잡음이 지배적이다. 광량을 올려야 한다 — 여기서 '출력은 나온다'는 근거가 무너진다");
}

/* ---------------------------------------------------------------------------
 * P — PT 단독 생존 시험. LED 구동을 완전히 끄고 '외부' 적외선만 쏜다.
 *     D1(LED)을 방정식에서 제거하므로, 노드 N 무반응의 원인을
 *     [PT 배선] 과 [LED 발광/정렬] 로 정확히 두 갈래로 가른다.
 *
 *     광원: TV 리모컨(버튼 누른 채 Q1 렌즈에 5 mm까지 접근) — 38 kHz 펄스라
 *           평균이 아니라 피크를 본다. 직사광선·백열등도 가능(정상광).
 *           흰색 LED 손전등은 근적외가 거의 없어 부적합.
 * ------------------------------------------------------------------------ */
static void p_pt_probe() {
  Serial.println(F("\n[P] PT 단독 시험 — LED 구동 OFF"));
  Serial.println(F("    TV 리모컨 버튼을 누른 채 Q1(검정 5 mm)에 바짝 대세요. 아무 키나 누르면 종료"));
  bits_off();
  int pk_all = 0;
  const int64_t t0 = esp_timer_get_time();
  while (esp_timer_get_time() - t0 < 30000000LL) {
    if (Serial.available()) { while (Serial.available()) Serial.read(); break; }
    const int pk = peakN();
    if (pk > pk_all) pk_all = pk;
    Serial.printf("  N peak = %5d (%.3f V)   누적최대 %5d (%.3f V)\n",
                  pk, pk * VREF / ADC_FS, pk_all, pk_all * VREF / ADC_FS);
    delay(200);
  }
  Serial.printf("  누적 최대 = %d counts (%.3f V)\n", pk_all, pk_all * VREF / ADC_FS);
  if (pk_all > 60)
    judge("P PT 생존·배선", 0,
          "PT는 정상. 노드 N 무반응의 원인은 D1 발광 또는 광축 정렬 → 't' 로 진행");
  else
    judge("P PT 생존·배선", 2,
          "외부 IR에도 무반응. (1)PT 컬렉터 3V3 냉납 (2)극성반대(긴다리=컬렉터) "
          "(3)Q1 자리에 LED를 꽂음 (4)이미터↔노드N 미접속");
}

/* ---------------------------------------------------------------------------
 * T — LED 상시 ON + 노드 N 라이브. 폰 카메라 발광 확인과 광축 정렬을 동시에.
 *     60 s 후 자동 소등 (LED 연속 점등은 설계 듀티 0.28 %를 크게 벗어나므로).
 * ------------------------------------------------------------------------ */
static void t_led_steady() {
  if (halted) return;
  Serial.println(F("\n[T] LED 상시 ON 60 s — 폰 카메라로 D1을 보세요(850 nm는 보라/흰 점)"));
  Serial.println(F("    동시에 노드 N을 찍습니다. 두 부품을 마주보게 움직이며 최대값을 찾으세요"));
  bits_on(M_ALL);
  double mx = 0;
  const int64_t t0 = esp_timer_get_time();
  while (esp_timer_get_time() - t0 < 60000000LL) {
    if (Serial.available()) { while (Serial.available()) Serial.read(); break; }
    const double v = vN();
    if (v > mx) mx = v;
    Serial.printf("  N = %.3f V   최대 %.3f V\n", v, mx);
    delay(250);
  }
  bits_off();
  Serial.println(F("  LED 소등"));
  if (mx > 0.05) judge("T 정렬", 0, "광 결합 확인. T4 재실행");
  else           judge("T 정렬", 2, "정렬로도 반응 없음. 폰 카메라에서 D1이 빛나는지가 갈림길");
}

// ────────────────────────────────────────────────────────────────── 요약
static void summary() {
  Serial.println(F("\n──────────────────────────────────────────"));
  Serial.printf("  PASS %d   WARN %d   FAIL %d\n", n_pass, n_warn, n_fail);
  if (halted)      Serial.println(F("  ★ 안전검사 실패 — 배선을 고치고 재부팅"));
  else if (n_fail) Serial.println(F("  ★ FAIL 항목을 먼저 해결. 다음 단계로 넘어가지 않는다"));
  else if (n_warn) Serial.println(F("  ★ 배선은 정상. WARN(특히 T4-c 동작점)을 해결해야 단계 3"));
  else             Serial.println(F("  ★ 배선·광 예산 모두 정상. 02_설계.md §10 단계 3(락인)으로 진행"));
  Serial.println(F("──────────────────────────────────────────"));
  Serial.println(F("a 자동전체 | R 확인점3-a(반복10회) | i 대화형(T8)"));
  Serial.println(F("p PT단독(외부IR) | t LED상시ON | 0~8 개별 | ? 요약"));
}
static void reset_counters() { n_pass = n_warn = n_fail = 0; }

// ────────────────────────────────────────────────────────────────── setup/loop
void setup() {
  Serial.begin(115200);
  delay(400);

  // 출력 레벨을 HIGH로 고정하고 인에이블만 토글한다 (LOW 금지)
  pinMode(PIN_B2, OUTPUT); pinMode(PIN_B1, OUTPUT); pinMode(PIN_B0, OUTPUT);
  GPIO.out_w1ts = M_ALL;
  bits_off();

  analogReadResolution(12);
  analogSetPinAttenuation(PIN_SIG,   ADC_11db);   // 두 채널 감쇠는 반드시 동일
  analogSetPinAttenuation(PIN_SENSE, ADC_11db);

  Serial.println(F("\n=== 탁도 프로브 v3.1 — 배선 점검 펌웨어 ==="));
  Serial.println(F("SENSE=GPIO36(SVP)  SIG=GPIO34  b2/b1/b0=27/26/25  DS18B20=GPIO4"));
  t0_safety();
  summary();
}

void loop() {
  if (!Serial.available()) { delay(80); return; }
  const char c = Serial.read();
  while (Serial.available()) Serial.read();

  switch (c) {
  case 'a':
    reset_counters();
    t0_safety(); t1_rdac(); t2_staircase(); t3_swap();
    t4_optical(); t5_timing(); t6_ds18b20(); t7_lockin();
    summary();
    break;
  case 'i': t8_interactive(); summary(); break;
  case 'R': r_repeat();       break;
  case 'p': p_pt_probe();     break;
  case 't': t_led_steady();   break;
  case '0': t0_safety();      break;
  case '1': t1_rdac();        break;
  case '2': t2_staircase();   break;
  case '3': t3_swap();        break;
  case '4': t4_optical();     break;
  case '5': t5_timing();      break;
  case '6': t6_ds18b20();     break;
  case '7': t7_lockin();      break;
  case '8': t8_interactive(); break;
  case '?': summary();        break;
  default: break;
  }
}
