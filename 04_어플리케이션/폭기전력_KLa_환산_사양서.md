# 폭기 전력 $P$[W] → $K_La$ 환산 사양서 (SW팀 인계)

> 작성 2026-08-03 · 기계(김강빈) → SW(한규태·신동하)
> 대상: `demo_html/step03/do_engine.js` L84–96 (`KLA_EFF` 4단계 하드코딩) 대체
> 근거: `../03_논문/Experiment/상수_목록.md` D군 · `../03_기계.md` §4.2 · `../03_논문/논문_최종.md` §3
> **`03_논문/` 은 frozen 이다. 이 문서는 그 확정식을 앱 입력으로 잇는 인계 문서이며, 상수를 새로 정의하지 않는다.**

---

## 0. 이 문서가 닫는 구멍

`do_engine.js` L91–92 에 남아 있던 주석:

```
// ⚠ '보통' 3.618 만 CFD 역산 정본이고, 약(÷2)·강(×2)은 물리 근거 없는 임의 배수다.
//   §4.2(폭기 전력 W → Q_air → α_g 역산)이 들어오면 이 4단계를 연속 입력으로 대체.
```

`MERGE_SW팀_물리엔진.md` L164 / `04_소웨.md` §7 의 **"§4.2 펌프동력 역산(N4) — 기계팀 결정 대기"** 항목이 본 문서로 해소된다.

바뀌는 것은 **`aerationLevel` 4단계 열거형 → `pumpPowerW` 연속 스칼라** 하나뿐이다. 그 하류(플룸/수면 분리, $z_\text{start}$ 레버, 수위·수온 보정, ROM)는 **전부 그대로 둔다.**

---

## 1. 사슬 전체

$$P\ \xrightarrow{\ \text{§2 신규}\ }\ Q_\text{air}\ \to\ U_{gs}\ \xrightarrow{\ \text{고정점}\ }\ (\alpha_g,\ W)\ \to\ a=\frac{6\alpha_g}{d_b}\ \to\ K_La\ \to\ \text{DO}$$

`04_소웨.md` §7 이 선언해 둔 경로 그대로이고, 비어 있던 것은 **첫 화살표 하나**였다.

---

## 2. 신규 가정 — 전력↔유량 비례 (유일한 미검증 고리)

$$Q_\text{air}=c\,P,\qquad c=\frac{Q_0}{P_0}=\frac{1.200}{2.5}=\mathbf{0.480}\ \mathrm{L\,min^{-1}\,W^{-1}}$$

| 앵커 | 값 | 출처 |
|---|---|---|
| $P_0$ | 2.5 W | `../03_논문/Experiment/EX1/EX1_방법론.md` §1 (실험 사용 펌프) |
| $Q_0$ | **1.200 ± 0.002 L/min** | 물 치환법 500 mL 3회, SD 0.036 s (±0.14 %) — `../03_논문/Experiment/상수_목록.md` D군 |

**$Q_0$ 는 바로 그 2.5 W 펌프로 측정한 값이다.** 따라서 앵커점 자체는 실측이고, 가정인 것은 **기울기(선형성)와 절편 0** 두 가지다. → §7 리스크.

---

## 3. 확정식 (전부 `03_논문/` 인용, 신규 정의 없음)

| 식 | 출처 |
|---|---|
| $U_{gs}=Q_\text{air}/A_p$ | `상수_목록.md` D군 |
| $\alpha_g=U_{gs}/(W+U_\text{slip})$ | `논문_최종.md` §3, `03_기계.md` §4.2 (drift-flux 고정점) |
| $\mathrm{Su}=\alpha_g\,g$ | `EX2_X1/README.md` §1 · `EX2_X5/gen_cases.py` L46 (`fvOptions: Su = alpha_g*g`) |
| $W=0.2178\,\mathrm{Su}^{0.511}$ | `03_기계.md` §4.2 — 3점 log-log LSQ, 최대잔차 0.28 %. **$n=1/3$ 아님**(운동량 지배 컬럼) |
| $a=6\alpha_g/d_b$ | `CFD_method.md` §2 |

### 3.1 상수 (변경 금지 — `상수_목록.md` 가 진실원)

| 기호 | 값 | 비고 |
|---|---|---|
| $A_p$ | $3.14\times10^{-4}$ m² | $r_p=0.01$ m |
| $U_\text{slip}$ | 0.0578 m/s | **@25 °C**. 20 °C 는 0.055 — 섞지 말 것 |
| $d_b$ | 0.5 mm | ⚠ 4픽셀 측정, ±1 px = ±25 % (§7) |
| $g$ | 9.81 m/s² | |
| $\alpha_{g0}$ | **0.1785** | medium 앵커 m21 자기일관 고정점 |
| $W_0$ | **0.3009** m/s | 동 고정점 ($\mathrm{Su}_0=1.751$) |
| $n$ | **0.511** | 멱법칙 지수 |

---

## 4. 구현식 — 1변수 대수방정식으로 축약

정규화 변수 $x\equiv\alpha_g/\alpha_{g0}$ 를 쓰면 $\mathrm{Su}/\mathrm{Su}_0=x$ 이므로 **고정점 반복이 스칼라 방정식 1개**가 된다. CFD 를 부르지 않는다.

$$\boxed{\;W_0\,x^{1+n}+U_\text{slip}\,x=(W_0+U_\text{slip})\,\frac{P}{P_0}\;}$$

$$0.3009\,x^{1.511}+0.0578\,x=0.3587\cdot\frac{P}{2.5}$$

**성질:** $P=P_0$ 에서 $x=1$ 이 정확히 성립한다 → 확정 상수(0.1785 / 1.751 / 0.3009 / 2142 / 2.604)를 오차 없이 재현한다. 절대값 정규화가 앵커에 물려 있으므로 SW 쪽에서 별도 보정 불필요.

### 4.1 출력

$$\alpha_g=\alpha_{g0}\,x,\qquad \mathrm{Su}=\alpha_g g,\qquad W=W_0\,x^{0.511},\qquad a=\frac{6\alpha_g}{d_b}=2142\,x\ \ [\mathrm{m^{-1}}]$$

$$\boxed{\;K_La(P)=K_{La,\text{plume}}\cdot x+K_{La,\text{surf}}=\mathbf{2.160\,x+0.444}\;}\quad[\mathrm{h^{-1}}]$$

- **플룸항만 $x$ 로 스케일**한다. $a\propto\alpha_g$ 이므로 계면전달은 $x$ 에 비례.
- **자유수면 0.444 는 고정**이다. `do_engine.js` L95: *"플룸 기하와 무관한 바닥값"* — 폭기를 꺼도 남는다.
- $2.160 = 2.604 - 0.444$. 2.604 /h 는 m21 medium 3-D 앵커 (`../03_논문/Experiment/EX2/이동안내_CFD.md`).

### 4.2 실용 근사 (0.5–6 W 에서 오차 < 1 %)

반복을 돌리기 싫으면:

$$\alpha_g\simeq0.1785\left(\frac{P}{2.5}\right)^{0.70},\qquad K_La\simeq2.160\left(\frac{P}{2.5}\right)^{0.70}+0.444$$

지수 0.70 의 유래: $U_\text{slip}\to0$ 극한이 $1/(1+n)=0.662$ 이고, 슬립항이 이를 0.69~0.71 로 밀어올린다. **UI 슬라이더 실시간 반응용으로만 쓰고, 판정 계산은 §4 정식을 쓴다.**

---

## 5. 참조 구현 (JS — `do_engine.js` 삽입용)

```js
// ================================================ 폭기 전력 → K_La
// 사양: 04_어플리케이션/폭기전력_KLa_환산_사양서.md
// 사슬: P[W] → Q_air → U_gs → 고정점(α_g, W) → a=6α_g/d_b → K_La
// 진실원 상수: 03_논문/Experiment/상수_목록.md D군 (변경 금지)
const PUMP_P0    = 2.5;      // W      앵커 펌프 정격 (EX1 실험 사용기)
const PUMP_C     = 0.480;    // L/min/W  Q_air = c·P  (⚠ 1점 앵커 — 사양서 §7)
const AG0        = 0.1785;   // -      medium 앵커 m21 고정점
const W0_PLUME   = 0.3009;   // m/s    동 고정점 플룸 상승속도
const U_SLIP     = 0.0578;   // m/s    @25 °C (20 °C 는 0.055)
const PLAW_N     = 0.511;    // -      W ∝ Su^n  (1/3 아님)
const KLA_PLUME0 = 2.160;    // 1/h    = 2.604(m21 3-D) − 0.444(자유수면)
// KLA_SURFACE = 0.444 는 기존 상수 재사용 (L96)

// 정규화 기포체적분율 x = α_g/α_g0 를 Newton 3회로 푼다.
// f(x) = W0·x^(1+n) + U_slip·x − (W0+U_slip)·(P/P0) = 0
// P = P0 에서 x = 1 이 정확히 성립한다(앵커 재현).
function bubbleFractionRatio(pumpPowerW) {
    const P = Math.max(0, pumpPowerW);
    if (P <= 0) return 0;                       // 폭기 정지 → 플룸항 소멸
    const rhs = (W0_PLUME + U_SLIP) * (P / PUMP_P0);
    let x = Math.pow(P / PUMP_P0, 0.70);        // §4.2 근사를 초기값으로
    for (let i = 0; i < 3; i++) {               // 0.3~10 W 전 구간 3회면 수렴
        const f  = W0_PLUME * Math.pow(x, 1 + PLAW_N) + U_SLIP * x - rhs;
        const fp = (1 + PLAW_N) * W0_PLUME * Math.pow(x, PLAW_N) + U_SLIP;
        x -= f / fp;
    }
    return x;
}

// 폭기 전력으로부터의 기저 K_La [1/h] — z_start·수위·수온 보정 이전 값.
// 기존 KLA_EFF[state.aerationLevel] 를 그대로 대체한다.
function klaFromPumpPower(pumpPowerW) {
    return KLA_PLUME0 * bubbleFractionRatio(pumpPowerW) + KLA_SURFACE;
}

// 진단용 부산물 (UI 표시·검증용)
function aerationDiagnostics(pumpPowerW) {
    const x = bubbleFractionRatio(pumpPowerW);
    const ag = AG0 * x;
    return {
        Qair:  PUMP_C * pumpPowerW,             // L/min
        alphaG: ag,
        Su:    ag * 9.81,
        W:     W0_PLUME * Math.pow(x, PLAW_N),  // m/s
        a:     6 * ag / 0.0005,                 // 1/m
        kla:   KLA_PLUME0 * x + KLA_SURFACE     // 1/h
    };
}
```

### 5.1 `effectiveKla()` 결선

기존 L160–164 의 첫 줄만 교체한다. 나머지 3단 보정(①$z_\text{start}$ ②수위 ③수온)은 **손대지 않는다.**

```js
function effectiveKla(temp) {
    const base = klaFromPumpPower(state.pumpPowerW);   // ← 여기만 교체
    if (!isFinite(base)) return NaN;
    const plumeK = Math.max(0, base - KLA_SURFACE) * zStartLever(state.zStartM);
    const kla25  = (plumeK + KLA_SURFACE) * klaDepthFactor(state.waterDepthCm / 100);
    // ... 이하 동일
}
```

### 5.2 `state` 변경

```js
const state = {
    // ...
    pumpPowerW: 2.5,      // ← 신규. 에어펌프 정격전력 [W]
    aerationLevel: '보통', // ← 하위호환 폴백용으로 남기되, pumpPowerW 가 있으면 무시
    // ...
};
```

**마이그레이션:** `pumpPowerW` 가 `undefined` 면 기존 `KLA_EFF[aerationLevel]` 로 폴백. 구버전 저장상태·구 데모 HTML 이 깨지지 않는다.

### 5.3 `romShapeValid()` 주의

ROM 공간 형상은 **기준 운전점에서만 검증**됐다(`do_engine.js` L224–228, `ROM_REF_LEVEL = '보통'`). 연속 입력으로 바뀌어도 이 제약은 **그대로 유지**해야 한다:

```js
const ROM_REF_POWER_W = 2.5;
const ROM_REF_TOL     = 0.15;   // ±15 % 이내만 히트맵 표시
function romShapeValid() {
    return romAvailable() &&
           Math.abs(state.pumpPowerW - ROM_REF_POWER_W) / ROM_REF_POWER_W <= ROM_REF_TOL;
}
```

허용대역을 벗어나면 **히트맵을 감추고 평균값만** 쓴다 — 기존 '약'·'강' 처리와 동일한 정책이다.

---

## 6. 검증 벡터 (단위테스트에 그대로 넣을 것)

| $P$ [W] | $Q_\text{air}$ [L/min] | $x$ | $\alpha_g$ | $\mathrm{Su}$ | $W$ [m/s] | $a$ [/m] | $K_La$ [1/h] |
|---|---|---|---|---|---|---|---|
| 0.5 | 0.240 | 0.3182 | 0.0568 | 0.557 | 0.1676 | 682 | 1.131 |
| 1.0 | 0.480 | 0.5237 | 0.0935 | 0.917 | 0.2162 | 1122 | 1.575 |
| 1.5 | 0.720 | 0.6982 | 0.1246 | 1.223 | 0.2504 | 1496 | 1.952 |
| 2.0 | 0.960 | 0.8551 | 0.1526 | 1.497 | 0.2778 | 1832 | 2.291 |
| **2.5** | **1.200** | **1.0000** | **0.1785** | **1.751** | **0.3009** | **2142** | **2.604** |
| 3.0 | 1.440 | 1.1359 | 0.2028 | 1.989 | 0.3211 | 2433 | 2.898 |
| 4.0 | 1.920 | 1.3878 | 0.2477 | 2.430 | 0.3558 | 2973 | 3.442 |
| 5.0 | 2.400 | 1.6200 | 0.2892 | 2.837 | 0.3850 | 3470 | 3.943 |
| 6.0 | 2.880 | 1.8377 | 0.3280 | 3.218 | 0.4106 | 3936 | 4.413 |
| 8.0 | 3.840 | 2.2408 | 0.4000 | 3.924 | 0.4544 | 4800 | 5.284 |

**필수 통과 조건**

1. `klaFromPumpPower(2.5)` → **2.604** (±0.001). 앵커 재현.
2. `aerationDiagnostics(2.5)` → $\alpha_g$ 0.1785 · Su 1.751 · $W$ 0.3009 · $a$ 2142. **`상수_목록.md` D군과 완전일치.**
3. `klaFromPumpPower(0)` → **0.444** (자유수면 단독).
4. $K_La(P)$ 단조증가, $P\in(0,10]$ 에서 `isFinite`.

### 6.1 독립 검증 — 구 운전점을 맞히는가

$Q_\text{air}$=2 L/min 은 이 식에서 $P=4.167$ W 에 해당한다.

| | 본 사양 | 문서 기존값 | 편차 |
|---|---|---|---|
| $\alpha_g$ | 0.2548 | **0.257** (16위치 앙상블 고정점, `상수_목록.md` 메모) | −0.9 % |
| $K_La$ | 3.528 /h | **3.618 /h** (앱 정본 '보통', `do_engine.js` L88) | −2.5 % |

구 운전점 값들은 **$n=1/3$** 으로 풀렸는데도 $n=0.511$ 사슬이 3 % 내로 재현한다. 외삽 신뢰의 근거로 쓸 수 있다.

> ⚠ 이 3.618 /h 는 **구 운전점**($Q_\text{air}$ 2 L/min · $\alpha_g$ 0.257) 값이다(`논문_최종.md` §3 경고 박스). 본 사양 도입 시 앱의 기본 운전점은 **2.604 /h @ 2.5 W** 로 내려간다 — 이 변화는 버그가 아니라 **실측 유량 반영**이다. 시연 시나리오(`04_소웨.md` §8)의 DO 절대값이 함께 내려가므로 **재계산 필수.**

---

## 7. 리스크 — UI 또는 문서에 반드시 병기

| # | 리스크 | 내용 | 해소 방법 |
|---|---|---|---|
| **R-1** | **1점 회귀** | $c=0.480$ 은 앵커 1점을 원점과 이은 기울기다. 다이어프램 펌프는 스톨 전력이 있어 실제로는 $Q=c(P-P_\text{dead})$ 일 가능성이 크고, 1점으로는 $c$ 와 $P_\text{dead}$ 를 분리할 수 없다 | **펌프 1~2종 추가 물치환 실측**(SOP 기보유: 500 mL, `EX2_X1/README.md` §1). 반나절 작업 |
| **R-2** | 정격 ≠ 실소비 | 배압(수심·에어스톤 기공 막힘)이 다르면 같은 정격에서 $Q$ 가 달라진다 | 사용자 입력 라벨을 "정격전력"으로 명시, 오차 고지 |
| **R-3** | **$d_b$ 지배 불확도** | 4픽셀 측정 ±1 px = **±25 %** → $a$ 가 ±25 % (`논문_최종.md` 표). **$K_La$ 절대값의 지배 불확도는 $P$ 가 아니라 $d_b$ 다** | 기계팀 미해결. 이 사양의 정확도 개선으로 해결 불가 |
| **R-4** | $P=0$ 불연속 | 식은 $P\to0$ 에서 $K_La\to0.444$ 로 연속이나, 실제 펌프는 스톨 전력 아래에서 $Q=0$ 으로 끊긴다 | 저전력 구간(<0.3 W) 경고 표시 |
| **R-5** | 검증 범위 밖 외삽 | CFD 실측 $\mathrm{Su}$ 는 1.684~2.86 (즉 $P\approx$ 2.4~4.9 W). 표의 0.5 W·8 W 행은 **멱법칙 외삽**이다 | 0.5–6 W 를 "검증", 그 밖을 "외삽"으로 UI 구분 |
| **R-6** | ROM 형상 | §5.3 — 기준 운전점 ±15 % 밖에서는 히트맵 무효, 평균값만 | 코드로 강제 |

---

## 8. 인계 체크리스트

- [ ] `do_engine.js` 에 §5 블록 삽입, `state.pumpPowerW` 추가 (폴백 유지)
- [ ] `effectiveKla()` 첫 줄 교체 (§5.1) — **하류 3단 보정은 무수정**
- [ ] `romShapeValid()` 를 전력 허용대역 판정으로 교체 (§5.3)
- [ ] §6 검증 벡터 10행 단위테스트 통과
- [ ] 앱 UI: `aerationLevel` 4버튼 → 정격전력 입력(기본 2.5 W) + R-2·R-5 고지
- [ ] `www/` · `android/app/src/main/assets/public/` 동기화 (`npm run sync`)
- [ ] **시연 시나리오 3단 DO 절대값 재계산** (§6.1 경고)
- [ ] `04_소웨.md` §7 "§4.2 펌프동력 역산(N4) 대기" 항목 해소 표기
- [ ] `MERGE_SW팀_물리엔진.md` L164 동일 항목 갱신

---

## 9. 미결 (기계팀 잔여)

본 사양은 **N4(펌프동력 역산)만** 닫는다. 함께 대기 중이던 항목은 그대로다:

- `U_slip(T)` 온도의존 — 현재 25 °C 단일값 0.0578 고정
- `u_plant` 기저 (S2 근본해결)
- 운전점별 $\chi$ (S1)
- U1~U4 출처 귀속 (`TURB_BOD_COEF` · `ocr25` · `massG` · Q10)
