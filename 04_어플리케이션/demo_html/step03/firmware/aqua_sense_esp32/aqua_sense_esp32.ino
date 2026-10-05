/* ============================================================================
 *  AQUA-SENSE Pro  —  ESP32 펌웨어
 *  漁벤져스 스마트 어항 케어 / 수온 + 탁도 센서 노드
 *
 *  배선 기준: TURBIDITY PROBE v3.1 - ESP32 DIRECT-SOLDER WIRING (2026-07-27 freeze)
 *  출처: 05_JEPUM / TAKDO-PROBE / 04_HWAKJEONG-SAYANG.md
 *
 *  [필요 라이브러리]  아두이노 IDE > 라이브러리 관리자에서 설치
 *    - OneWire            (Paul Stoffregen)
 *    - DallasTemperature  (Miles Burton)
 *    * BLE 라이브러리는 ESP32 보드 패키지에 기본 포함 — 따로 설치 불필요
 *
 *  [보드 설정]  Tools > Board > "ESP32 Dev Module"
 *              Partition Scheme > "Huge APP" 권장 (BLE 스택이 커서 기본 설정이면
 *              용량 초과 에러가 납니다. 컴파일 실패 시 여기부터 확인하세요.)
 * ========================================================================= */

#include <OneWire.h>
#include <DallasTemperature.h>

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// 사용자 정의 타입은 반드시 헤더로 분리해야 한다 (헤더 안 주석에 이유 설명)
#include "aqua_sense_types.h"

/* ---------------------------------------------------------------------------
 *  1. 핀 매핑 — 배선도 v3.1과 1:1 대응
 * ------------------------------------------------------------------------ */
static const int PIN_DQ    = 4;   // NET DQ    : DS18B20 데이터 (4K7 풀업 → 3V3)
static const int PIN_SIG   = 34;  // NET SIG   : 포토트랜지스터 Q1 출력 (R5 15k 부하)
static const int PIN_SENSE = 36;  // NET SENSE : IR LED 전류 션트 R4 22R 양단 (SVP)

// R-DAC 구동 핀. 저항이 작을수록 전류가 크므로 150R이 최상위 비트(b2).
static const int PIN_DAC_B2 = 27; // R1 150R
static const int PIN_DAC_B1 = 26; // R2 330R
static const int PIN_DAC_B0 = 25; // R3 680R

static const float R_SHUNT_OHM = 22.0f;  // R4

/* ---------------------------------------------------------------------------
 *  2. 측정 파라미터
 * ------------------------------------------------------------------------ */
static const int   ADC_SAMPLES      = 32;    // 1회 측정당 평균 샘플 수
static const int   LED_SETTLE_US    = 3000;  // LED on/off 후 광학·전기 안정화 대기
static const int   SAMPLE_PERIOD_MS = 1000;  // 측정 및 BLE 통보 주기

// SIG 포화 임계(mV). 11dB 감쇠의 정확 구간 상한(약 2450mV)을 넘으면 값이 뭉개진다.
static const float SIG_SAT_MV = 2400.0f;
// 이 아래면 신호가 너무 약해 정밀도가 떨어진다는 경고만 낸다(더 키울 방법은 없음).
static const float SIG_TARGET_MIN_MV = 250.0f;

/* ---------------------------------------------------------------------------
 *  2-1. 탁도 프로브 모드
 *
 *  광학 프로브가 아직 완성되지 않았을 때 이 값을 바꿔 탁도부를 통째로 끌 수 있다.
 *  수온 측정과 BLE 전송은 어느 모드에서도 정상 동작한다.
 *
 *    0 = 정상 — 프로브를 실제로 측정한다
 *    1 = 미장착 — 탁도를 무효(-1)로 전송한다. 앱은 '측정 불가' 로 표시한다
 *    2 = 시연용 가상값 — 그럴듯한 값을 만들어 보낸다
 *
 *  ★ 모드 2 는 실제 측정이 아니다. 발표·시연에서 사용한다면 반드시 그 사실을 밝힐 것.
 *    측정한 것처럼 보이게 두면 그건 결과 조작이 된다.
 * ------------------------------------------------------------------------ */
#define TURBIDITY_MODE 1

#if (TURBIDITY_MODE != 0) && (TURBIDITY_MODE != 1) && (TURBIDITY_MODE != 2)
  #error "TURBIDITY_MODE 는 0, 1, 2 중 하나여야 합니다."
#endif

/* ---------------------------------------------------------------------------
 *  3. 탁도 캘리브레이션 상수  ★ 실측 후 반드시 갱신할 것 ★
 *
 *  ratio = (SIG_lit - SIG_dark) [mV] / I_led [mA]      단위: mV/mA
 *    → LED 구동전류로 정규화했기 때문에 LED 열화·온도 드리프트가 상쇄된다.
 *
 *  RATIO_CLEAR = 깨끗한 물(0 NTU)에서 측정된 ratio 값.
 *  시리얼 모니터에 'c' 를 입력하면 현재 값으로 자동 설정된다. (아래 5번 참고)
 * ------------------------------------------------------------------------ */
float RATIO_CLEAR = 0.0f;   // 0이면 미보정 상태 → NTU 대신 -1 을 전송

// 흡광도(A) → NTU 환산 계수.  A = -log10(ratio / RATIO_CLEAR),  NTU = K_NTU * A
// 포르마진 표준액(예: 100 NTU)으로 1점 보정해 구하는 값이다. 아래는 임시 초기값.
float K_NTU = 400.0f;

/* ---------------------------------------------------------------------------
 *  4. BLE 정의
 *
 *  앱(app_demo.html)과 반드시 일치해야 하는 값들.
 *  통보 payload 는 CSV 문자열 "수온,탁도" (예: "25.43,12.1")
 *  → BLE 기본 MTU 23바이트(실 payload 20바이트) 안에 들어가도록 짧게 유지한다.
 *  → 문자열이라 nRF Connect 앱에서 눈으로 바로 읽힌다(디버깅 편의).
 * ------------------------------------------------------------------------ */
#define DEVICE_NAME       "AQUA-SENSE Pro"
#define SERVICE_UUID      "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHAR_DATA_UUID    "beb5483e-36e1-4688-b7f5-ea07361b26a8"  // notify + read
#define CHAR_CMD_UUID     "beb5483e-36e1-4688-b7f5-ea07361b26a9"  // write (캘리브레이션)

BLEServer         *pServer   = nullptr;
BLECharacteristic *pDataChar = nullptr;
bool deviceConnected    = false;
bool oldDeviceConnected = false;

OneWire oneWire(PIN_DQ);
DallasTemperature ds18b20(&oneWire);

// 최근 측정값 (BLE 콜백에서도 참조)
float lastTempC = NAN;
float lastNTU   = -1.0f;
float lastRatio = 0.0f;
int   lastLevel = 7;
// lastRatio 가 '직전 주기의 유효한 측정'인지 표시. 이게 없으면 포화·오류 상태에서
// 보정을 누를 때 수 분 전의 낡은 ratio 가 조용히 기준값으로 저장된다.
bool  lastRatioFresh = false;

// DS18B20 연속 읽기 실패 카운터. 한계를 넘으면 마지막 정상값을 폐기한다.
int              tempFailCount = 0;
static const int TEMP_FAIL_LIMIT = 5;

unsigned long lastSample = 0;   // 마지막 측정 시각 (setup 에서도 참조하므로 여기서 선언)

/* ===========================================================================
 *  R-DAC 제어
 *
 *  ★ 매우 중요 ★  OFF 상태는 반드시 pinMode(INPUT) = 하이임피던스여야 한다.
 *  digitalWrite(LOW) 로 끄면 그 저항이 NODE_A 를 GND 로 끌어내리는 병렬 경로가
 *  되어 나머지 비트의 전류 가중치가 전부 틀어진다. (배선도 CAUTION 항목)
 * ======================================================================== */
void dacSet(uint8_t level) {
  level &= 0x07;

  const int pins[3] = { PIN_DAC_B0, PIN_DAC_B1, PIN_DAC_B2 };
  for (int b = 0; b < 3; b++) {
    if (level & (1 << b)) {
      // HIGH 를 먼저 걸고 OUTPUT 으로 전환한다. 순서를 반대로 하면 출력 레지스터
      // 초기값 0 때문에 수 µs 동안 NODE_A 가 GND 로 끌려가는 글리치가 생긴다.
      digitalWrite(pins[b], HIGH);
      pinMode(pins[b], OUTPUT);
    } else {
      pinMode(pins[b], INPUT);   // hi-Z. 절대 LOW 로 쓰지 말 것.
    }
  }
}

inline void dacOff() { dacSet(0); }

/* ===========================================================================
 *  ADC 읽기 — 공장 캘리브레이션이 적용된 mV 단위로 평균
 * ======================================================================== */
float readMilliVoltsAvg(int pin, int samples) {
  uint32_t sum = 0;
  for (int i = 0; i < samples; i++) sum += analogReadMilliVolts(pin);
  return (float)sum / (float)samples;
}

/* ===========================================================================
 *  탁도 1회 측정
 *
 *  절차: LED off 상태에서 암(dark) 기준값 → LED on 상태값 → 차분.
 *  이렇게 하면 수조 조명·햇빛 같은 주변광이 상쇄된다.
 *  (어항은 조명이 켜졌다 꺼지므로 이 보정이 없으면 값이 크게 흔들린다.)
 *
 *  반환 타입 TurbidityRaw 는 aqua_sense_types.h 에 정의되어 있다.
 *  (아두이노 IDE 의 자동 프로토타입 생성 때문에 .ino 안에 두면 컴파일이 깨진다 — 헤더 주석 참고)
 * ======================================================================== */
TurbidityRaw measureTurbidityAt(uint8_t level) {
  // 지정 초기화 — 나중에 헤더의 멤버 순서가 바뀌어도 엉뚱한 필드에 들어가지 않는다
  TurbidityRaw r = { .sigMv = 0, .iLedMa = 0, .ratio = 0, .litSigRaw = 0, .darkSigRaw = 0,
                     .valid = false, .saturated = false, .ambientBlind = false };

  // --- 암 기준값 ---
  dacOff();
  delayMicroseconds(LED_SETTLE_US);
  float darkSig   = readMilliVoltsAvg(PIN_SIG,   ADC_SAMPLES);
  float darkSense = readMilliVoltsAvg(PIN_SENSE, ADC_SAMPLES);

  // --- 점등 상태 ---
  dacSet(level);
  delayMicroseconds(LED_SETTLE_US);
  float litSig   = readMilliVoltsAvg(PIN_SIG,   ADC_SAMPLES);
  float litSense = readMilliVoltsAvg(PIN_SENSE, ADC_SAMPLES);

  dacOff();   // 측정 외 시간에는 항상 소등 (LED 발열·열화 억제)

  r.sigMv      = litSig - darkSig;
  r.litSigRaw  = litSig;
  r.darkSigRaw = darkSig;
  // 션트 양단 mV / 22Ω = mA
  r.iLedMa = (litSense - darkSense) / R_SHUNT_OHM;

  /* ★ 포화 판정은 반드시 '차분값'이 아니라 '원시값'으로 해야 한다.
   * 어항 조명이 켜져 darkSig 가 이미 높으면, litSig 가 완전히 포화해도
   * 차분값(sigMv)은 정상 범위처럼 보인다. 그러면 포화된 쓰레기 값으로
   * NTU 를 계산하게 되고, 최악의 경우 둘 다 포화 → sigMv≈0 → 항상 최대 NTU 가 뜬다. */
  r.saturated = (litSig > SIG_SAT_MV);

  // 주변광만으로 이미 포화 = 측정 불가 (수조 조명이 프로브를 직사하는 상황).
  // 이건 구동 레벨과 무관하므로 오토레인징이 재시도해봐야 소용없다 → ambientBlind 로 표시.
  if (darkSig > SIG_SAT_MV) {
    r.ambientBlind = true;
    return r;                           // valid = false
  }

  // LED 가 실제로 켜졌는지 확인. 가장 어두운 레벨1의 정상 전류가 약 2.5mA 이므로
  // 그보다 충분히 낮되 ADC 노이즈(≈0.05mA 상당)보다는 확실히 높은 값으로 잡는다.
  if (r.iLedMa > 0.8f) {
    r.ratio = r.sigMv / r.iLedMa;
    r.valid = true;
  }
  return r;
}

/* ===========================================================================
 *  DAC 단계 프로파일링 (부팅 시 1회)
 *
 *  "레벨 숫자가 클수록 전류가 크다" 는 가정은 어느 GPIO 에 어느 저항이 물렸는지에
 *  따라 쉽게 깨진다. 실제로 150R 과 680R 의 위치가 배선도 노트와 반대이면
 *  레벨별 전류가 뒤죽박죽이 되어 오토레인징이 엉뚱한 순서로 탐색한다.
 *
 *  그래서 부팅할 때 7개 단계의 전류를 직접 재서 '전류 내림차순' 탐색 순서를 만든다.
 *  이렇게 하면 배선 순서가 어떻든 항상 올바르게 동작하고,
 *  덤으로 각 비트에 실제로 물린 저항값을 시리얼로 확인할 수 있다.
 * ======================================================================== */
uint8_t scanOrder[7]    = { 7, 6, 5, 4, 3, 2, 1 };  // 기본값(프로파일링 전)
float   levelCurrent[8] = { 0 };

void profileDacLevels() {
  Serial.println(F("\n--- DAC 단계 프로파일링 ---"));

  for (int lv = 1; lv <= 7; lv++) {
    levelCurrent[lv] = measureTurbidityAt((uint8_t)lv).iLedMa;
  }

  // 전류 내림차순 정렬 (삽입 정렬, 원소 7개라 충분)
  for (int i = 0; i < 7; i++) scanOrder[i] = i + 1;
  for (int i = 1; i < 7; i++) {
    uint8_t key = scanOrder[i];
    int j = i - 1;
    while (j >= 0 && levelCurrent[scanOrder[j]] < levelCurrent[key]) {
      scanOrder[j + 1] = scanOrder[j];
      j--;
    }
    scanOrder[j + 1] = key;
  }

  /* 단일 비트 구동에서 환산 저항을 추정해 배선을 역으로 확인한다.
   * R_total = (3V3 - Vf) / I  이고 R4(22Ω)를 빼면 R-DAC 저항이 나온다. Vf 는 850nm 기준 약 1.4V. */
  const int   bitPin[3]   = { PIN_DAC_B0, PIN_DAC_B1, PIN_DAC_B2 };
  const int   bitLevel[3] = { 1, 2, 4 };
  int dead = 0;
  for (int b = 0; b < 3; b++) {
    float i = levelCurrent[bitLevel[b]];
    if (i > 0.8f) {
      Serial.printf("  b%d (GPIO%2d) : I=%5.2fmA  → 환산 저항 약 %.0f R\n",
                    b, bitPin[b], i, 1900.0f / i - R_SHUNT_OHM);
    } else {
      dead++;
      Serial.printf("  b%d (GPIO%2d) : I=%5.2fmA  ← ✗ 전류 없음 (배선 개방/납땜 불량 의심)\n",
                    b, bitPin[b], i);
    }
  }

  if (dead > 0) {
    Serial.printf("[WARN] 구동 비트 %d개가 동작하지 않습니다.\n", dead);
    Serial.println(F("       측정은 계속되지만 구동 세기 선택 폭이 좁아져,"));
    Serial.println(F("       물이 탁해졌을 때 신호를 키울 수단이 없습니다."));
    Serial.println(F("       확인 순서: (1) GPIO↔저항↔LED 애노드 도통  (2) 해당 GPIO 단독 블링크 테스트"));
  }
  if (dead == 3) {
    Serial.println(F("[FATAL] 모든 구동 비트가 죽었습니다. IR LED 또는 션트(R4) 배선을 확인하세요."));
  }

  Serial.print(F("  탐색 순서(전류 큰 것부터): "));
  for (int i = 0; i < 7; i++) Serial.printf("%d ", scanOrder[i]);
  Serial.println(F("\n---------------------------\n"));
}

/* 오토레인징: 전류가 큰 단계부터 내려오며 SIG 가 포화되지 않는 첫 단계를 선택.
 * 물이 탁해지면 수광량이 줄어 더 센 구동이 필요하므로 자동 조정이 유리하다. */
TurbidityRaw measureTurbidityAuto(int &usedLevel) {
  TurbidityRaw best = { 0, 0, 0, 0, 0, false, false, false };
  usedLevel = scanOrder[0];

  for (int i = 0; i < 7; i++) {
    int lv = scanOrder[i];
    TurbidityRaw r = measureTurbidityAt((uint8_t)lv);

    // 주변광 포화는 레벨을 바꿔도 해결되지 않는다 → 즉시 중단 (7회 헛측정 방지)
    if (r.ambientBlind) {
      Serial.println(F("[WARN] 주변광 포화 — 프로브에 조명이 직사되고 있습니다. 차광이 필요합니다"));
      return r;
    }
    if (!r.valid) continue;
    best = r;
    usedLevel = lv;

    if (r.saturated) continue;   // 포화 → 전류가 더 작은 단계로 재시도

    // 여기 도달 = 포화가 아님. 전류가 큰 단계부터 훑어 내려왔으므로
    // 신호가 약하더라도 더 키울 방법이 없다 → 경고만 남기고 확정한다.
    if (r.sigMv < SIG_TARGET_MIN_MV) {
      Serial.println(F("[WARN] SIG 미달 — 물이 매우 탁하거나 광학 경로가 오염됐을 수 있습니다"));
    }
    return r;
  }
  return best;   // 전 구간 포화/무효
}

/* ratio → NTU 환산 */
float ratioToNTU(float ratio) {
  if (RATIO_CLEAR <= 0.0f || ratio <= 0.0f) return -1.0f;  // 미보정 / 무효

  float t = ratio / RATIO_CLEAR;            // 투과율
  if (t > 1.0f) t = 1.0f;                   // 0 NTU 보다 맑을 수는 없음
  if (t < 0.0005f) t = 0.0005f;             // log 발산 방지

  float ntu = K_NTU * (-log10f(t));
  // t == 1.0 이면 -log10f 가 -0.0 을 돌려주고, IEEE 규칙상 (-0.0 < 0.0) 은 거짓이라
  // 아래 비교를 그냥 통과해 화면에 "-0.0" 이 찍힌다. 부호를 확실히 털어낸다.
  if (!(ntu > 0.0f)) ntu = 0.0f;
  return ntu;
}

/* ===========================================================================
 *  BLE 콜백
 * ======================================================================== */
class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *s) override {
    deviceConnected = true;
    Serial.println(F("[BLE] 앱 연결됨"));
  }
  void onDisconnect(BLEServer *s) override {
    deviceConnected = false;
    Serial.println(F("[BLE] 연결 끊김"));
  }
};

// 앱에서 캘리브레이션 명령을 보낼 수 있게 하는 write 특성
//   "CAL_CLEAR"   → 현재 ratio 를 0 NTU 기준으로 저장
//   "K=<숫자>"    → NTU 환산 계수 변경
class CmdCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String v = String(c->getValue().c_str());
    v.trim();
    if (v.equalsIgnoreCase("CAL_CLEAR")) {
      // 직전 측정이 유효할 때만 보정한다. 포화·오류 상태에서 낡은 값으로
      // 기준을 잡으면 이후 모든 NTU 가 조용히 틀어진다.
      if (lastRatio > 0 && lastRatioFresh) {
        RATIO_CLEAR = lastRatio;
        Serial.printf("[CAL] RATIO_CLEAR = %.2f 로 설정됨\n", RATIO_CLEAR);
      } else {
        Serial.println(F("[CAL] 현재 측정이 무효합니다 — 보정하지 않았습니다"));
      }
    } else if (v.startsWith("K=")) {
      K_NTU = v.substring(2).toFloat();
      Serial.printf("[CAL] K_NTU = %.2f 로 설정됨\n", K_NTU);
    }
  }
};

/* ===========================================================================
 *  setup
 * ======================================================================== */
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println(F("\n=== AQUA-SENSE Pro / probe v3.1 ==="));

  // --- ADC ---
  analogReadResolution(12);

  // SIG: 포토트랜지스터 이미터 팔로워라 최대 3V 가까이 오른다 → 11dB (정확 구간 약 150~2450mV)
  analogSetPinAttenuation(PIN_SIG, ADC_11db);

  /* SENSE: R4=22Ω 션트라 전체 스윙이 56~355mV 밖에 안 된다.
   * 11dB 로 읽으면 유효 범위의 8%만 쓰게 되고 저레벨은 정확 구간(150mV) 아래로 떨어진다.
   * 0dB (정확 구간 약 100~950mV) 로 낮추면 실효 분해능이 약 3배 좋아진다.
   * ※ R4 를 100Ω 으로 바꾸면 스윙이 231~950mV 가 되어 전 구간이 정확 구간에 들어온다.
   *   (LED 전류는 16→9.5mA 로 줄지만 측정에는 충분하다. 하드웨어 여유가 되면 권장) */
  analogSetPinAttenuation(PIN_SENSE, ADC_0db);

  // --- R-DAC 초기화: 전원 인가 직후부터 소등 상태 보장 ---
  dacOff();

  // --- DS18B20 ---
  ds18b20.begin();
  ds18b20.setResolution(12);       // 12비트 = 0.0625°C 분해능
  ds18b20.setWaitForConversion(false);  // 논블로킹: 요청 후 다음 루프에서 수거
  if (ds18b20.getDeviceCount() == 0) {
    Serial.println(F("[WARN] DS18B20 미검출 — DQ 배선과 4K7 풀업을 확인하세요"));
  }
  ds18b20.requestTemperatures();

  // --- BLE ---
  BLEDevice::init(DEVICE_NAME);
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);

  pDataChar = pService->createCharacteristic(
      CHAR_DATA_UUID,
      BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  pDataChar->addDescriptor(new BLE2902());   // 앱이 notify 를 켤 수 있게 하는 필수 디스크립터

  BLECharacteristic *pCmdChar = pService->createCharacteristic(
      CHAR_CMD_UUID, BLECharacteristic::PROPERTY_WRITE);
  pCmdChar->setCallbacks(new CmdCallbacks());

  pService->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(SERVICE_UUID);   // 앱이 서비스 UUID 로 필터링할 수 있도록 광고에 포함
  adv->setScanResponse(true);
  adv->setMinPreferred(0x06);          // iPhone 연결 안정성 관련 권장값
  BLEDevice::startAdvertising();

  Serial.println(F("[BLE] 광고 시작 — 앱 또는 nRF Connect 로 연결하세요"));
  Serial.println(F("[TIP] 시리얼에 'c' 입력 = 현재 값을 깨끗한 물(0 NTU) 기준으로 저장"));

#if TURBIDITY_MODE == 0
  // 각 구동 단계의 실제 전류를 재서 탐색 순서를 정한다.
  // 출력되는 '환산 저항' 으로 어느 GPIO 에 어느 저항이 물렸는지 확인할 수 있다.
  profileDacLevels();
#elif TURBIDITY_MODE == 1
  Serial.println(F("[MODE] 탁도 프로브 미장착 — 수온만 측정합니다 (탁도는 무효값 전송)"));
#else
  Serial.println(F("[MODE] ★ 탁도 시연 모드 — 가상값입니다. 실제 측정이 아닙니다 ★"));
#endif

  // 첫 측정을 1주기 뒤로 미룬다. DS18B20 12비트 변환에 750ms 가 걸리므로
  // 바로 읽으면 파워온 기본값 85.00°C 가 나온다.
  lastSample = millis();
}

/* ===========================================================================
 *  loop
 * ======================================================================== */
void loop() {
  // --- 시리얼 캘리브레이션 명령 ---
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'c' || c == 'C') {
      if (lastRatio > 0 && lastRatioFresh) {
        RATIO_CLEAR = lastRatio;
        Serial.printf("[CAL] RATIO_CLEAR = %.2f  (이 값을 소스의 RATIO_CLEAR 에 적어두세요)\n",
                      RATIO_CLEAR);
      } else {
        Serial.println(F("[CAL] 유효한 측정값이 없습니다 — 위 경고를 먼저 해결하세요"));
      }
    }
  }

  if (millis() - lastSample >= SAMPLE_PERIOD_MS) {
    lastSample = millis();

    // --- 수온 (직전 루프에서 요청해 둔 변환 결과 수거) ---
    float t = ds18b20.getTempCByIndex(0);
    ds18b20.requestTemperatures();          // 다음 회차 변환 시작
    /* 오류값 필터.
     *  -127.0 = 센서 미검출(배선 불량)
     *   85.0  = 파워온 리셋 기본값. 변환(12비트 = 750ms)이 끝나기 전에 읽으면 이 값이 나온다.
     *           상한을 90 으로 두면 85 가 정상값으로 통과해 버리므로 84 로 자른다.
     *           (어항 수온이 84°C 를 넘을 일은 없다) */
    if (t > -50.0f && t < 84.0f) {
      lastTempC = t;
      tempFailCount = 0;
    } else if (++tempFailCount >= TEMP_FAIL_LIMIT) {
      // 연속 실패가 쌓이면 마지막 정상값을 버린다. 이게 없으면 운용 중 센서가 빠져도
      // 앱에는 마지막 온도가 계속 전송돼 화면이 "정상"인 채로 얼어붙는다.
      lastTempC = NAN;
    }

    // --- 탁도 ---
    int level = 0;
    TurbidityRaw raw = { 0, 0, 0, 0, 0, false, false, false };

#if TURBIDITY_MODE == 1
    // 프로브 미장착: 무효값을 보낸다. 앱이 '측정 불가' 로 표시하고 수온만 정상 동작한다.
    lastNTU        = -1.0f;
    lastRatioFresh = false;

#elif TURBIDITY_MODE == 2
    /* 시연용 가상값. 실제 물을 측정한 값이 아니다.
     * 8 NTU 부근을 느리게 오가도록 만들어 그래프가 자연스럽게 보이게 한다. */
    static float simNtu = 8.0f;
    // 순수 랜덤워크는 몇 분 뒤 상·하한에 붙어 머문다. 8 NTU 로 살짝 되돌리는 항을 넣어
    // 그 근처를 오가게 만든다.
    simNtu += (8.0f - simNtu) * 0.03f;
    simNtu += (random(-100, 101) / 100.0f) * 0.4f;
    if (simNtu < 1.0f)  simNtu = 1.0f;
    if (simNtu > 22.0f) simNtu = 22.0f;
    lastNTU        = simNtu;
    lastRatioFresh = false;   // 가상값으로 영점 보정이 되는 일은 없어야 한다

#else
    raw = measureTurbidityAuto(level);
    lastLevel = level;
    if (raw.valid && !raw.saturated) {
      lastRatio      = raw.ratio;
      lastRatioFresh = true;
      lastNTU        = ratioToNTU(raw.ratio);
    } else {
      // 포화됐거나 무효한 측정은 값을 갱신하지 않고 -1(무효)로 전송한다.
      // 포화된 litSig 는 위쪽이 잘려 sigMv 가 실제보다 작게 나오므로,
      // 그대로 계산하면 멀쩡한 물인데도 "매우 탁함" 으로 뜬다.
      lastRatioFresh = false;
      lastNTU        = -1.0f;
      // ambientBlind 는 이미 measureTurbidityAuto 에서 별도 경고를 냈으므로 중복 출력하지 않는다
      if (raw.saturated && !raw.ambientBlind)
                              Serial.println(F("[WARN] SIG 포화 — 최저 구동단에서도 수광량이 과다합니다"));
      else if (!raw.valid && !raw.ambientBlind)
                              Serial.println(F("[WARN] LED 구동 전류 미검출 — R-DAC / IR LED 배선을 확인하세요"));
    }
#endif  // TURBIDITY_MODE

    // --- 시리얼 진단 출력 ---
#if TURBIDITY_MODE == 0
    // ratio 는 lastRatio(낡을 수 있음)가 아니라 이번 회차 실측값을 찍는다
    Serial.printf("T=%.2fC | lvl=%d  I=%.2fmA  SIG=%.1fmV(raw %.0f)  ratio=%.2f  NTU=%.1f\n",
                  lastTempC, lastLevel, raw.iLedMa, raw.sigMv, raw.litSigRaw, raw.ratio, lastNTU);
#elif TURBIDITY_MODE == 1
    Serial.printf("T=%.2fC | 탁도 미장착\n", lastTempC);
#else
    Serial.printf("T=%.2fC | NTU=%.1f [SIM·가상값]\n", lastTempC, lastNTU);
#endif

    // --- BLE 통보 ---  "수온,탁도"
    if (deviceConnected && pDataChar) {
      char payload[24];
      // 수온을 못 읽었으면 0 이 아니라 -99 를 보낸다. 0 을 보내면 앱이 "0.0°C 위험"
      // 으로 표시해 버려서 센서 고장인지 진짜 저온인지 구분이 안 된다.
      snprintf(payload, sizeof(payload), "%.2f,%.1f",
               isnan(lastTempC) ? -99.0f : lastTempC, lastNTU);
      pDataChar->setValue((uint8_t *)payload, strlen(payload));
      pDataChar->notify();
    }
  }

  // --- 연결이 끊기면 광고 재시작 (없으면 재연결이 불가능해진다) ---
  if (!deviceConnected && oldDeviceConnected) {
    delay(500);                     // 스택이 정리될 시간을 준다
    pServer->startAdvertising();
    Serial.println(F("[BLE] 광고 재시작"));
  }
  oldDeviceConnected = deviceConnected;
}
