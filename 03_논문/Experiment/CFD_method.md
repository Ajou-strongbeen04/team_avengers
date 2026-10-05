# CFD_method — 방정식 · BC · 폐합 (단일 진실원)

> ★ **역할: 물리 정의의 단일 진실원.** 지배방정식·경계조건·소스 닫음·계수 정의는 **오직 이 문서**에 있다.
> EX1·EX2·EX3의 `CFD_방법론.md`는 **실행 프로토콜**(무엇을 어떻게 돌리는가)이며, 방정식을 다시 적지 않고 여기를 참조한 뒤 **자기 실험의 델타만** 기술한다.
>
> | 문서 | 역할 |
> |---|---|
> | **`CFD_method.md`** (본 문서) | 방정식·BC·폐합·계수 **정의** |
> | `상수_목록.md` | 그 계수들의 **값** |
> | `EX2/CFD/docs/CFD_방법론.md` | EX2 실행 — 좌표 부호·과도 URANS·DO 두 갈래·메시·GCI |
> | `EX3/CFD/CFD_방법론.md` | EX3 실행 — EX2 상속 + 구조물 항력·대사 |
>
> 팀 漁벤져스 · 어항 수질 스칼라 진단 트랙
> 근거(확정본): `../논문_초안_v2.md` §3 · 입력상수 `상수_목록.md` · 출처 `../References/00_References.md`
> 상태: **§1–§4 방정식·BC·폐합 확정(DO 트랙, blk02 대상).** **§5 다항목 일반화 = 설계안(미검증, 2026-08-07 추가).**
>
> **⚠ §1–§4는 건드리지 않는다.** blk02 재현성이 여기에 걸려 있다. 다항목 확장은 §4까지를 **DO라는 한 인스턴스**로
> 두고 §5에서 스칼라 일반형으로 승격하는 방식으로만 기술한다. §5의 계수·화학량론은 [R#] 미배정이므로
> 논문 본문·특허에 정량으로 쓰지 않는다(미배정 목록 = `../../02a_다항목확장_검토_20260807.md` §10).

---

## 1. 좌표계 · 해석영역 · 규약

- 해석영역: $\Omega=\{(x,y,z)\mid 0\le x\le L,\ 0\le y\le B,\ 0\le z\le d\}$. 치수 $L,B,d$ 는 `상수_목록.md` E군(직접설정).
- **$z$축 하향(중력 방향) 양(+)**: 자유수면 $z=0$, 바닥 $z=d$, $\mathbf{g}=g\,\hat{\mathbf{e}}_z\ (g>0)$.
- 유체: 비압축·뉴턴($\rho,\mu$ 상수) [R16], 난류 → 유효점성 $\mu_\text{eff}=\mu+\mu_t$, 유효확산 $D_\text{eff}$ 사용.
- 확산 플럭스 규약 $\mathbf{J}=-D_\text{eff}\nabla C$. 소스 부호는 항에 내장(공급 $\ge0$, 소비 $\le0$).
- 설계 범위: 가정용 어항 0.2~1 m 급.
- **스윕(고정 안 함):** 운전 수온 $T$, 폭기구 위치(→$\Omega_\text{air}$ 위치). `상수_목록.md` 상단 참조.

> 구현 노트: 솔버에서 $z$ 상향을 쓰면 중력 방향·자유수면 위치만 일관되게 뒤집으면 동일하다.

## 2. 지배방정식 (확정)

### 2.1 유동 (URANS · 비압축 · 단상)

$$\nabla\cdot\mathbf{U}=0$$

$$\frac{\partial \mathbf{U}}{\partial t}+(\mathbf{U}\cdot\nabla)\mathbf{U}=-\frac{1}{\rho}\nabla p^*+\nabla\cdot\big[(\nu+\nu_t)\nabla\mathbf{U}\big]+\frac{1}{\rho}\mathbf{F}_\text{air}$$

- $\nu_t$: SST $k\text{–}\omega$(Menter) 와점성 [R15].
- 공간 등온($T$ 균질) → **열부력 무시**. 정수압은 $p^*$ 에 흡수.
- 외력은 폭기 소스 $\mathbf{F}_\text{air}$ 만(여과가 폭기와 일체형 → 별도 $\mathbf{F}_\text{filter}$ 없이 합산).

**폭기 에어리프트 부력플룸** [R19][R20]:

$$\mathbf{F}_\text{air}=-(\rho_l-\rho_g)\,\alpha_g\,g\,\hat{\mathbf{e}}_z\,\mathbb{1}_{\Omega_\text{air}}\approx-\rho_l\,\alpha_g\,g\,\hat{\mathbf{e}}_z\,\mathbb{1}_{\Omega_\text{air}}\quad[\text{N/m}^3]$$

($z$ 하향이므로 상승 부력이 $-\hat{\mathbf{e}}_z$, 플룸 영역 $\Omega_\text{air}$, 기포체적분율 $\alpha_g$.)

### 2.2 DO (과도상태 이송-확산) [R21][R22]

$$\frac{\partial C}{\partial t}+\nabla\cdot(\mathbf{U}C)=\nabla\cdot\left(D_\text{eff}\nabla C\right)+S_\text{air}$$

- **폭기 계면전달(국소 소스)** [R23]: $\ S_\text{air}=k_L(T)\,a\,(C^*(T)-C)\,\mathbb{1}_{\Omega_\text{air}},\quad a=6\alpha_g/d_b$.
- **유효확산** [R4]: $\ D_\text{eff}=D_\text{mol}(T)+D_t,\quad D_t=\nu_t/Sc_t$.
- 비압축이므로 $\nabla\cdot(\mathbf{U}C)=\mathbf{U}\cdot\nabla C$.
- **생물 소비/생성 및 저서 SOD 항은 두지 않는다.** 어류 호흡·부유 미생물·식물 대사 등 생물기원 소비/생성은 어항마다 다른 조건(사육밀도·식재)에 종속되므로 지배방정식의 고정 물리로 두지 않고, 제품 단계에서 **기하인식/센서가 공급하는 BC**로 분리한다. 저서 SOD도 제거한다(무생물·무저질 검증). **인공 국소 산소싱크(전기화학·화학)도 쓰지 않는다(2026-07-19 폐기, 구 설계는 `../../_archive/EX2_공간매핑_구주제/`).** 물리엔진 검증은 **비정상 재폭기 시험**으로 $K_La_\text{eff}$·$\kappa$ 를 대조하며(`../논문_초안_v2.md` §3.5·§4.1), 저산소 진폭은 제품 단계 B층 생물소스가 부여한다.
- **DO 구배의 공간 구조는 유속장(이송)이 만든다.** 국소 폭기 소스 $S_\text{air}$ 로 들어온 산소와 소비로 생긴 결손을 유동장이 공간적으로 재분배하고, 저유속 정체역에서 재산소화가 지연된다. 표층 재폭기(입력)와 소비(B층 생물소스)는 이 장의 배경 수준·구배 진폭을 정하며, 공간 구배 구조 자체(어디가 최소인지)는 대부분 이송이 만든다.

## 3. 경계조건 (확정)

### 3.1 유동 BC

| 경계 | 조건 | 출처 |
|---|---|---|
| 자유수면 $z=0$ | **rigid-lid + free-slip**: $w=0,\ \partial u/\partial z=\partial v/\partial z=0$ | [R16] |
| 유리벽·바닥 (나머지 5면) | **no-slip**: $\mathbf{U}=\mathbf{0}$ | [R16] |

### 3.2 DO BC

| 경계 | 조건 | 출처 |
|---|---|---|
| 자유수면 $z=0$ | 대기-수체 재폭기(Robin): $-D_\text{eff}\,\partial C/\partial z=k_L(T)\left(C^*(T)-C\right)$ | [R23][R5] |
| 바닥 $z=d$ | 무플럭스(Neumann): $\partial C/\partial n=0$ (무저질) | — |
| 측면 4면 | 무플럭스(Neumann): $\partial C/\partial n=0$ | — |

> 구 설계의 **국소 싱크 전극면 BC**($-D_\text{eff}\partial_n C=(I/4F)M_{\mathrm{O_2}}/A_\text{el}$)는 인공 국소싱크 폐기(2026-07-19)와 함께 제거했다. 원설계는 `../../_archive/EX2_공간매핑_구주제/`.

## 4. 폐합 · 계수 (확정)

**난류 폐합:** SST $k\text{–}\omega$ [R15]. (선택) 기포유발 난류 Sato: $\mu_\text{BI}=\rho\,C_{\mu B}\,\alpha_g\,d_b\,|\mathbf{U}_g-\mathbf{U}_l|$ → $\mu_\text{eff}=\mu+\mu_{t,\text{SST}}+\mu_\text{BI}$ [R8]. $Sc_t$: `상수_목록.md` B군 [R4].

**온도의존 함수(수온 $T$ 로 닫음):**

$$k_L(T)=k_{L,20}\,\theta_a^{\,T-20}\ \text{[R5]}$$

$$C^*(T):\ \text{Benson–Krause(담수·1 atm) [R14]},\quad \text{운용역 근사 }C^*\approx12.6-0.17\,T$$

(수온 $T$ 는 고정하지 않고 실측·스윕값으로 둔다. 온도항 $k_L(T),C^*(T)$ 는 그 $T$ 에서 평가한다.)

**폭기 · 플룸 규정 입력(단상 Route B)** [R12]: 기포체적분율 $\alpha_g$, 기포직경 $d_b$, 슬립속도 $U_\text{slip}$, 플룸 영역 $\Omega_\text{air}$(형상 고정·위치 스윕), 계면적 밀도 $a=6\alpha_g/d_b$.

**생물 소비/생성·저서 SOD 처리:** 어류 호흡·부유 미생물·식물 대사 등 생물기원 소비/생성은 지배방정식의 고정 물리 항으로 두지 않는다(어항마다 다른 조건에 종속 → 제품 단계에서 기하인식/센서가 공급하는 BC로 분리). 저서 SOD도 제거한다(무생물·무저질). CFD 검증 실험은 **생물·저질·인공싱크 없이** 수행하며, 물리엔진의 실측 앵커는 비정상 재폭기 시험의 $K_La_\text{eff}$·$\kappa$ 다(`../논문_초안_v2.md` §3.5·§4.1).

**입력 상수값:** 전부 `상수_목록.md`(A~E군) 참조. 값 미확정($T$·폭기구 위치·$Q_\text{air}$·$L,B,d$)은 실험/스윕에서 지정. C군(기준-20°C 크기)은 전형값 시작점 → 실측·캘리브레이션으로 대체.

---

## 5. 다항목 일반화 (설계안 · 2026-08-07)

> **상태: 미검증 설계안.** §1–§4(DO)는 실측 앵커($K_La_\text{eff}$·$\kappa$)를 가진 확정본이고,
> 본 절은 그 틀이 다른 수질 스칼라로 어떻게 승격되는지의 **형식 정의만** 담는다.
> 계수 값·화학량론의 [R#] 배정 전에는 정량 결과를 산출하지 않는다.
> 계기: 2026-08-07 회의 — "DO 문제는 오로지 논문의 증명을 위한 것."

### 5.1 스칼라 일반형

§2.2의 DO 식은 항목 인덱스 $i$ 를 붙이면 그대로 일반형이 된다.

$$\frac{\partial C_i}{\partial t}+\nabla\cdot\left(\mathbf{U}\,C_i\right)
=\nabla\cdot\left(D_{\text{eff},i}\,\nabla C_i\right)+S_i,
\qquad D_{\text{eff},i}=D_{\text{mol},i}(T)+\frac{\nu_t}{Sc_t}$$

$\mathbf{U}$, $\nu_t$ 는 §2.1 URANS의 해이며 **항목 수와 무관하게 한 번만 계산한다.**
$Sc_t$ 를 전 항목에 동일하게 두면 난류확산 $D_t=\nu_t/Sc_t$ 도 항목에 무관하다
(이 전제의 근거 [R#] 미배정 — 검토문서 §10 M10).
어항 유동의 대부분 영역에서 $D_t \gg D_{\text{mol}}$ 이므로 **항목이 달라도 확산 연산자는 사실상 같다.**

> **따라서 항목을 가르는 것은 확산이 아니라 $S_i$ 와 경계조건이다.** 이것이 §5.4 레짐 판정의 전제다.

### 5.2 항목이 갈리는 네 지점

| 구분 | 갈리는 요소 | 어항에서의 예 |
|---|---|---|
| (a) 자유수면 BC | 휘발성인가 | 휘발: $\mathrm{O_2}$·$\mathrm{CO_2}$·$\mathrm{N_2}$·$\mathrm{NH_3}$·$\mathrm{Cl_2}$ → Robin / 비휘발 이온종: 무플럭스 |
| (b) 체적 소스 | 플룸·생물 대사 | $S_\text{air}$, 어류 호흡·배설 |
| (c) 면 소스 | 여과재·저질·기벽 생물막 | 질산화(여과재 표면), SOD(바닥), 퇴적 플럭스 |
| (d) 커플링 | 다른 항목에 의존하는가 | 질산화가 $\mathrm{O_2}$ 소비 / pH가 $\mathrm{NH_3}$ 분율 결정 |

**이송항 자체가 바뀌는 항목은 입자상 하나뿐이다**(§5.5).

### 5.3 항목별 규정

#### (i) 휘발성 기체 — DO와 동형

자유수면·플룸 소스 모두 §2.2·§3.2의 형태를 그대로 쓰고 물성만 바꾼다.

$$S_{\text{air},i}=k_{L,i}(T)\,a\left(C_i^{*}(T)-C_i\right)\mathbb{1}_{\Omega_\text{air}},
\qquad a=\frac{6\alpha_g}{d_b}$$

$$-D_{\text{eff},i}\frac{\partial C_i}{\partial z}\bigg|_{z=0}
=k_{L,i}(T)\left(C_i^{*}(T)-C_i\right)$$

$$k_{L,i}(T)=k_{L,\mathrm{O_2}}(T)\left(\frac{D_{\text{mol},i}}{D_{\text{mol},\mathrm{O_2}}}\right)^{n}$$

- $a=6\alpha_g/d_b$ 는 **DO 트랙에서 이미 닫힌 값을 그대로 쓴다**($\alpha_g$ = 0.1785, `상수_목록.md`). 신규 실측 불필요.
- $\mathrm{CO_2}$ 는 어항 물이 통상 **과포화**라 괄호가 음수 → 폭기가 **stripping**으로 작용한다.
  같은 $\Omega_\text{air}$ 에서 $\mathrm{O_2}$ 공급과 $\mathrm{CO_2}$ 제거가 동시에 일어난다.
- **미확정:** 환산지수 $n$($1/2$ vs $1$) — 검토문서 §10 M1. $C^{*}_{\mathrm{CO_2}}(T)$ Henry 상수 — M2.

#### (ii) 질소 사슬 — DO와 직접 커플링

$$\mathrm{NH_4^+}+1.5\,\mathrm{O_2}\ \longrightarrow\ \mathrm{NO_2^-}+2\,\mathrm{H^+}+\mathrm{H_2O}$$

$$\mathrm{NO_2^-}+0.5\,\mathrm{O_2}\ \longrightarrow\ \mathrm{NO_3^-}$$

이중 Monod로 닫는다.

$$r_1=\mu_1 X_1\,\frac{C_\text{TAN}}{K_\text{TAN}+C_\text{TAN}}\cdot\frac{C_{\mathrm{O_2}}}{K_{\mathrm{O_2},1}+C_{\mathrm{O_2}}},
\qquad
r_2=\mu_2 X_2\,\frac{C_{\mathrm{NO_2}}}{K_{\mathrm{NO_2}}+C_{\mathrm{NO_2}}}\cdot\frac{C_{\mathrm{O_2}}}{K_{\mathrm{O_2},2}+C_{\mathrm{O_2}}}$$

$$S_\text{TAN}=P_\text{TAN}-r_1,\qquad S_{\mathrm{NO_2}}=r_1-r_2,\qquad S_{\mathrm{NO_3}}=r_2$$

- **$r_1,r_2$ 는 체적 소스가 아니라 면 플럭스다.** 질산화 세균은 여과재 표면 생물막에 산다.

$$-D_\text{eff}\frac{\partial C_\text{TAN}}{\partial n}\bigg|_{\Gamma_\text{filter}}=J_\text{TAN}\!\left(C_\text{TAN},C_{\mathrm{O_2}},T\right)$$

- **DO 인자가 이 프로젝트의 핵심 고리다.** $C_{\mathrm{O_2}}$ 가 낮으면 $r_1,r_2$ 가 꺼져 TAN·$\mathrm{NO_2^-}$ 가 쌓인다.
  즉 저산소역은 그 자체보다 **암모니아 처리 능력이 죽는 구역**이라 위험하다.
- $P_\text{TAN}$(어류 배설)은 §4의 원칙을 그대로 따른다 — 고정 물리가 아니라 **제품 단계에서 기하인식이 공급하는 BC**.
- **미확정:** 화학량론 질량기준값 M3 · Monod 상수 6개 M4 · $P_\text{TAN}$ 스케일링 M7.

#### (iii) pH — 이송하지 않는다

pH는 보존량이 아니므로 이송 방정식에 넣지 않는다. **보존량 두 개를 이송하고 셀마다 대수 평형을 푼다.**

$$\mathrm{DIC}=[\mathrm{CO_2^*}]+[\mathrm{HCO_3^-}]+[\mathrm{CO_3^{2-}}],
\qquad
\mathrm{Alk}\approx[\mathrm{HCO_3^-}]+2[\mathrm{CO_3^{2-}}]+[\mathrm{OH^-}]-[\mathrm{H^+}]$$

| 항목 | 자유수면 $z=0$ | 플룸 $\Omega_\text{air}$ | 근거 |
|---|---|---|---|
| DIC | Robin — **$\mathrm{CO_2}$ 성분에만** | $\mathrm{CO_2}$ 성분만 stripping | $\mathrm{HCO_3^-}$·$\mathrm{CO_3^{2-}}$ 는 비휘발 |
| Alk | **무플럭스** | 무플럭스 | $\mathrm{CO_2}$ 교환은 알칼리도를 바꾸지 않는다 |

pH가 정해지면 TAN이 분배된다.

$$f_{\mathrm{NH_3}}=\frac{1}{1+10^{\,\mathrm{p}K_a(T)-\mathrm{pH}}},
\qquad C_{\mathrm{NH_3}}=f_{\mathrm{NH_3}}\,C_\text{TAN}$$

- $\mathrm{p}K_a \approx 9$ 대이므로 운용역(pH 6.5–8)에서 $f_{\mathrm{NH_3}}$ 는 **pH 1당 약 10배**로 변한다.
- **미확정:** $K_1(T),K_2(T),K_w(T)$ M5 · $\mathrm{p}K_a(T)$ M6 · $D_{\text{mol},i}(T)$ M9.

#### (iv) 알칼리도 소비

질산화는 질소 1 mol당 $\mathrm{H^+}$ 2 mol을 낸다(§5.3 (ii)). $\mathrm{Alk}$ 의 체적 싱크로 들어가며,
$\mathrm{Alk}$ 고갈은 완충 붕괴 → pH 급락으로 이어진다. 화학량론 [R#] 미배정(M3).

### 5.4 레짐 판정의 스칼라 일반화 — **본 절의 핵심**

논문 §3.8·§4.4는 DO에서 다음을 **측정**했다.

- **소스 국소성**이 유동지배 ↔ 소스지배 레짐 전이를 지배한다.
- $\rho_{UC}=\mathrm{corr}(\lvert U\rvert, C)$ 의 **부호 붕괴**가 그 전이의 관측 가능한 지표다.
- 균일 소비에서 DO 공간 진폭 $A$ = 1.5 % 로 소멸한다.

이 판정은 **DO 고유가 아니라 수동 스칼라 일반의 성질**이다. $\rho_{UC}$ 를 항목별로 정의하면

$$\rho_{UC,i}=\mathrm{corr}\!\left(\lvert \mathbf{U}\rvert,\ C_i\right)$$

가 되고, 각 항목은 자기 $S_i$ 의 국소성에 따라 레짐 지도(논문 표 3-12) 위의 서로 다른 자리에 놓인다.

**항목별 소스 국소성 — 구조적 예상(미검증).**

| 항목 | 소스/싱크의 공간 성격 | 예상 레짐 |
|---|---|---|
| DO (균일 소비) | 체적 균일 $R$ + 플룸 소스, $\mathrm{Da}_\text{plume}$ 작음 | **유동지배·균질** — 측정됨($A$ = 1.5 %) |
| $\mathrm{CO_2}$ | 생성 분산 · 제거는 $\Omega_\text{air}$ 국소 | 소스지배 쪽 |
| TAN·$\mathrm{NO_2^-}$ | 생성 국소(어류·저질) · 소비 **면 국소**($\Gamma_\text{filter}$) | 소스지배 |
| pH | DIC·Alk의 결과. $\mathrm{CO_2}$ 구조를 물려받음 | 소스지배 쪽 |
| 입자(탁도) | 침강으로 바닥 축적 | 구조적으로 비균질 |
| 약품·사료 | 점 투여, 소스항 없음 | 초기 극도 비균질 → 혼합시간 문제 |

> **이것이 다항목 확장의 논거다.** 논문의 음성 결과는 "공간을 볼 필요 없다"가 아니라
> **"소스가 균일한 항목에서는 공간을 볼 필요 없다"**였다. DO는 그 균일 극한에 놓인 항목이었고,
> 위 표의 나머지 항목은 **소스가 구조적으로 국소적**이다.
> 즉 **논문의 판정 기준이 그대로 확장의 근거**가 된다.
>
> ⚠ 위 표는 소스 배치로부터의 **구조적 예상이며 계산도 측정도 하지 않았다.** 검정 설계는 §5.6.

### 5.5 입자상 — 이송항이 바뀌는 유일한 항목

$z$ 하향 양(§1)이므로 침강속도는 $+w_s\hat{\mathbf{e}}_z$ 다.

$$\frac{\partial C_p}{\partial t}+\nabla\cdot\left[\left(\mathbf{U}+w_s\hat{\mathbf{e}}_z\right)C_p\right]
=\nabla\cdot\left(D_{\text{eff},p}\nabla C_p\right)+S_p$$

- $w_s$ 는 Stokes 침강($d_p$, 밀도차, $T$ 를 통한 점성)으로 닫는다.
- 바닥 BC가 무플럭스가 아니라 **퇴적 플럭스** $J_\text{bed}=w_s C_p$ 가 된다(저유속이라 재부상 무시).
- **정체역 = 침전물이 쌓이는 곳** → 쌓인 유기물이 §5.3 (ii)의 $P_\text{TAN}$ 과 SOD를 국소화한다.
  §4에서 검증 목적으로 제거했던 SOD가 제품 단계에서 **탁도 센서로 관측되는 항**으로 부활한다.

### 5.6 검정 설계 (미실행)

| # | 대상 | 설계 | 비용 |
|---|---|---|---|
| V1 | 소스 없는 순수 이송-확산 | 점 투여 초기조건 → 혼합시간 $t_{95}$. 색소 + 카메라 대조 | 기존 동결장 재활용, 추가 CFD 0 |
| V2 | $\mathrm{CO_2}$ / $k_L$ 환산지수 $n$ | 과포화 후 탈기 시험. EX2 장비 그대로, pH 프로브로 추적 | EX2 재사용 |
| V3 | $\rho_{UC,i}$ 레짐 지도 | 항목별 소스 배치를 스윕 축으로 승격(논문 §4.8 후속 1번과 동일 경로) | 추가 CFD 0 |
| V4 | 질소 사슬 | 여과재 면 BC + 이중 Monod, TAN 시계열 대조 | 상용 시험지 |

**V1·V3은 추가 CFD 없이 기존 동결 유동장 위에서 수행 가능하다.** 착수 순서는 여기서부터다.

---
