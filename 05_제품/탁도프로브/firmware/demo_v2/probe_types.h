/* =============================================================================
 * probe_types.h — demo_v2 공용 타입
 *
 * ★ 왜 별도 헤더인가 (2026-07-30)
 *
 *   Arduino IDE는 .ino를 전처리할 때 함수 프로토타입을 자동 생성해 파일 앞쪽에
 *   끼워 넣는다. 사용자 정의 구조체를 함수 인자·반환 타입으로 쓰면서 구조체
 *   정의가 파일 중간에 있으면
 *       static void lockin(uint32_t ms, LockinResult *r);   ← 자동 삽입
 *       struct LockinResult { ... };                        ← 실제 정의
 *   순서가 되어 "error: 'LockinResult' has not been declared"로 실패한다.
 *
 *   demo_v1은 struct Meas를 .ino 안에 두고도 통과했지만 그건 삽입 지점에
 *   의존한 우연이다. #include는 프로토타입 삽입보다 반드시 먼저 처리되므로
 *   헤더로 빼는 것이 유일하게 확실하다.
 * ========================================================================== */

#ifndef PROBE_TYPES_H
#define PROBE_TYPES_H

#include <stdint.h>

// 락인 1회 적분 결과
struct Meas {
  double   Isig, Qsig;   // 카운트 — 암벡터 차감 후 노드 N의 I/Q
  double   aSig;          // V — 노드 N(PT 이미터)의 f0 진폭
  double   aRef;          // V — 노드 K(22 Ω 션트)의 f0 진폭 = 구동 기준
  double   S;             // aSig / aRef — 구동 변동이 상쇄된 무차원 비
  double   nMean;         // V — 적분 중 노드 N의 DC 평균 (동작점 감시용)
  double   kMean;         // V — 적분 중 노드 K의 DC 평균
  double   late_pct;      // % — 계단 타이밍을 놓친 샘플 비율
  uint32_t samples;
};

// NVS에 저장되는 교정값
struct Cal {
  double idark, qdark;   // 암 벡터 (설계 §6.2 — 스칼라가 아니라 벡터로 차감)
  double s0;             // 기준선 (청수 등)
  double a_temp, t_ref;  // 온도 보정 계수와 기준 온도 (설계 §7.4)
};

#endif // PROBE_TYPES_H
