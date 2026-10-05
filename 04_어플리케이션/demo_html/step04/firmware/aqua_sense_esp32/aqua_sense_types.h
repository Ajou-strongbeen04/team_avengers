#ifndef AQUA_SENSE_TYPES_H
#define AQUA_SENSE_TYPES_H

/* ---------------------------------------------------------------------------
 *  이 구조체가 왜 .ino 가 아니라 별도 헤더에 있는가
 *
 *  아두이노 IDE 는 컴파일 전에 .ino 를 훑어서 모든 함수의 프로토타입을 자동 생성한 뒤,
 *  파일 맨 앞(전처리기 지시문이 아닌 첫 줄)에 끼워 넣는다.
 *  그래서 .ino 안에 struct 를 정의하고 그 타입을 반환하는 함수를 만들면,
 *  자동 생성된 프로토타입이 struct 정의보다 위에 놓여
 *      error: 'TurbidityRaw' does not name a type
 *  가 난다. struct 를 파일 위쪽으로 옮겨도 삽입 지점이 그보다 더 위라 해결되지 않는다.
 *
 *  #include 는 전처리기 지시문이라 삽입 지점이 그 뒤로 밀린다.
 *  따라서 사용자 정의 타입은 헤더로 빼는 것이 표준 해법이다.
 * ------------------------------------------------------------------------ */

// 탁도 1회 측정 결과
struct TurbidityRaw {
  float sigMv;         // LED 기여분만 남은 수광 신호 (mV) = litSig - darkSig
  float iLedMa;        // 실제 LED 구동 전류 (mA) = 션트 전압 / 22Ω
  float ratio;         // sigMv / iLedMa — 구동전류로 정규화한 값 (LED 열화·드리프트 상쇄)
  float litSigRaw;     // 포화 판정용 원시 ADC 값 (mV), LED 점등 상태
  float darkSigRaw;    // 원시 ADC 값 (mV), LED 소등 상태 = 주변광 수준
  bool  valid;         // 계산이 성립하는 측정인가 (LED 가 실제로 켜졌는가)
  bool  saturated;     // LED 점등 상태에서 ADC 포화 → 값 신뢰 불가
  bool  ambientBlind;  // 주변광만으로 이미 포화 → 구동 레벨과 무관하게 측정 불가
};

#endif  // AQUA_SENSE_TYPES_H
