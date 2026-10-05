# EX3 · CFD — 구조물 배치 유동/DO 장 생성 (실행 프로토콜)

> **역할: 실행 프로토콜.** 방정식·BC·폐합의 정의는 `../../CFD_method.md`(단일 진실원), 계수 값은 `../../상수_목록.md`, 수치·메시·보정치는 `../../EX2/CFD/docs/CFD_방법론.md` 상속. 본 문서는 **구조물을 어떻게 표현하고 각 케이스를 어떻게 푸는가**만 다룬다. *어떤 케이스를 도는지*는 `sweep_design.md`, 트랙 상위 논리는 `../EX3_방법론.md`.
>
> 팀 漁벤져스 · EX3 데이터 생성 트랙 · CFD 쪽
> 근거: `../../CFD_method.md`(방정식·BC 확정본) · `../../상수_목록.md`(입력) · `../EX3_방법론.md`(상위 논리) · **`../../EX2/CFD/docs/CFD_방법론.md`(상속 대상 — 수치·메시·보정치)**
> 성격: EX2의 과도 URANS 세팅을 **그대로 상속**하고, 도메인에 **구조물(바위·수생식물)** 만 추가해 (배치→DO 장) 데이터를 대량 생성. **새 캘리브레이션 없음.**
> 상태: 방법론(설계 논리) 확정. 케이스 파일·항력/대사 상수는 이후 기입.

---

## 1. EX2로부터의 상속 (변경 금지 목록)

EX3는 다음을 **EX2 확정값으로 고정**한다(재캘리브레이션 금지 — `../EX3_방법론.md` §1):

| 항목 | 상속값 | 출처 |
|---|---|---|
| 기하 $L,B,d$ | 0.47, 0.21, 0.21 m ($z$-상향) | `상수_목록.md` E |
| 솔버 | pimpleFoam(과도 URANS), SST $k$-$\omega$ + AWT | EX2 §5 |
| 이산화 | backward/CN 블렌딩 시간항, limitedLinear 대류, $\mathrm{Co}\lesssim1$ 적응 $\Delta t$ | EX2 §5.1 |
| 폭기 | 코너 $(0.02,0.035)$ 고정, $Q_\text{air}{\approx}2$ L/min, 원기둥 $r_p{=}0.01$, $z{=}0.02$–0.21 | EX2 §2, 상수_목록 D |
| 부력 | $\alpha_g{=}0.29$, $Su{=}\alpha_g g{=}2.86$, $d_b{=}0.5$ mm, $U_\text{slip}{=}0.055$ | 상수_목록 메모 |
| 소스 닫음 계수 | $Sc_t$, 전달쪽 $a{=}6\alpha_g/d_b{\approx}3495$/m | **EX2 캘리브레이션 최종값** |
| 수온 | 25 °C 기준 고정 → $C^*,k_L,\text{SOD},R_\text{bio}$ | EX2, 상수_목록 |
| 경계조건 | 수면 재폭기 Robin · 바닥 SOD Neumann · 측벽 무플럭스 no-slip | EX2 §4 |

> **회귀 테스트:** 구조물 0개($n{=}0$) 케이스를 먼저 돌려 EX2 기준 케이스와 QoI가 일치함을 확인(전이 성립 게이트). 불일치 시 세팅 상속 오류로 간주하고 데이터 생성 중단.

---

## 2. 구조물의 CFD 표현

### 2.1 바위 — 고체 (cut-out)

- **기하:** `snappyHexMesh`(또는 STL cut-out)로 구조물 체적을 격자에서 제거, 표면을 patch로 생성. 형상은 등가 타원체/직육면체 등급(S/M/L)으로 단순화(개별 자연석 형상 해상 불필요 — 유동 차단·후류가 QoI를 지배).
- **유동 BC:** 표면 no-slip $\mathbf U{=}\mathbf 0$.
- **DO BC:** 표면 무플럭스 $\partial C/\partial n{=}0$(불투과·비반응).
- 대안(저비용): 완전 차단 구조물은 **다공성 blockage**($D\to\infty$ 근사)로도 표현 가능하나, 기준은 cut-out(후류 정확).

### 2.2 수생식물 — 다공성 항력체

- **기하:** 식물 군락 점유 체적 $\Omega_\text{plant}$ 를 `cellZone`으로 지정(cut-out 아님 — 유체가 통과).
- **운동량 소스**(`fvOptions`의 `explicitPorositySource` 또는 `meanVelocityForce` 계열 항력):
  $$\mathbf S_\text{drag}=-\Big(\mu D+\tfrac12\rho_l C_F|\mathbf U|\Big)\mathbf U$$
  캐노피 형상항력 $\tfrac12\rho C_D a|\mathbf U|\mathbf U$ [R34]와 대응 → **Forchheimer $C_F=C_D\,a$ [1/m], Darcy $D\approx0$**(형상항력 지배·점성항 무시). $a=m\,d_s$(frontal area density=줄기밀도×줄기폭), $C_D\approx1.0$(줄기 $Re_d{\sim}O(10\text{–}10^3)$). 등급 S/M/L을 $a$(=밀도)로 층화: **$C_F\approx\{2,\,5,\,15\}$/m**(줄기밀도 $m{\approx}\{400,1200,3000\}$/m², 폐합·유도 `../00_구조물폐합_유도.md` Part 3A). 값 미확정 시 사용자 확정 대상.
- **DO:** 기본은 항력만(잎 두께 얇아 확산 차단 무시). 대사 소스는 §2.3.

### 2.3 식물 대사 O2 소스 (ablation 축)

`../EX3_방법론.md` §3.3의 재검토 결과에 따라 **기본 off, ablation으로 on**:

$$S_\text{plant}=\rho_B\,[\,P(I,T)-R(T)\,]\,\mathbb{1}_{\Omega_\text{plant}}\quad[\text{mg/(L·s)}],\qquad P(I)=P_\text{max}\tanh(I/I_k),\ I_k=P_\text{max}/\alpha$$

- 균일 체적 소스(`scalarCodedSource`/`fvOptions`). $P(I)$: Jassby–Platt P–I 쌍곡탄젠트 [R36]. $P_\text{max}$: 온대 수생대형수초 광포화율 0.59–17.98 mg O₂ g⁻¹DW h⁻¹(대표 ~5, 15 °C) [R35]. $R\approx0.2P_\text{max}$(암호흡). $\rho_B$: 군락 생체량밀도 [g DW/L]. 수온 25 °C 고정 → $Q_{10}{\approx}2$ 보정(선택). 캘리브레이션 아님(문헌 닫음, 유도 `../00_구조물폐합_유도.md` Part 3B).
- ablation: {off, 주간(+ $\approx{+}20$ mg O₂/(L·h)), 야간(− $\approx{-}5$)} × 식재밀도 수준(대표 $\rho_B{=}5$). §2.3 결과로 레벨-이동 vs 구조-재편 판정.

---

## 3. 지배방정식 — EX2 상속 + EX3 델타

> **단일 진실원은 `../../CFD_method.md` §2**(방정식·BC·소스 닫음), 좌표 부호·과도 URANS·DO 두 갈래 풀이는 `../../EX2/CFD/docs/CFD_방법론.md` §3의 델타를 그대로 상속한다. 여기 다시 적지 않는다. 아래는 **EX3에서만 추가되는 항** 둘뿐이다.

| 추가항 | 들어가는 식 | 정의 | 기본값 |
|---|---|---|---|
| $\mathbf S_\text{drag}$ | 운동량식 우변에 $+\tfrac1\rho\mathbf S_\text{drag}$ | 식물 다공성 항력(§2.2). 바위는 cut-out이라 없음 | 식물 존에서만 활성 |
| $S_\text{plant}$ | DO식 우변에 $+S_\text{plant}$ | 식물 대사(§2.3) | **0 (기본 off)** — ablation 시에만 on |

$S_\text{air}$, $D_\text{eff}=D_\text{mol}+\nu_t/Sc_t$ 는 EX2와 동일하다. 생물 소비 $S_\text{bio}$ 는 물리엔진에 두지 않는다(제품 단계 B층 몫, 논문 §3.3).

> **DO는 시간평균 유동장 위 정상 스칼라로 푼다.** 준정상 근사(DO 전달 시간척도 ≫ 유동 turnover)는 구조물이 유동을 바꿔도 유지된다.

---

## 4. 메시 — 구조물 해상 추가

EX2의 저셀·고정확 전략(플룸·벽 근처 집중, 벌크 성김; `../../EX2/CFD/docs/CFD_방법론.md` §7)을 상속하고, **구조물 표면·후류에 국부 세분**을 추가한다.

| 영역 | 셀 크기 | 근거 |
|---|---|---|
| 플룸 컬럼(∅20 mm) | 2~3 mm (지름당 4~7셀) | EX2 상속 |
| 바위 표면·후류 | **표면 2~3 mm + 후류 방향 grading** | 박리·후류 정체역(저산소역 원천) 해상 |
| 식물 다공성 경계 | 3~4 mm | 항력 전이층 |
| 바닥 SOD·수면 재폭기 | 얇은 grading(첫 셀 1~2 mm) | 스칼라 flux |
| 벌크 | 8~10 mm | 완만 구배 |

- 구현: 성근 베이스 blockMesh → `snappyHexMesh`(바위 STL) + `topoSet`/`refineMesh`(플룸·후류·식물존). 예상 총 셀 배치당 **≈ 200~500k**(구조물 수·크기에 따라).
- **격자수렴 재점검(GCI):** EX2가 고정한 medium을 기본으로 쓰되, 구조물은 새 QoI(후류 저산소역)를 만드므로 **대표 배치 1~2개**(예: 중앙 바위 1개, 플룸 하류 바위 1개)에서 3격자 GCI를 재수행([R28] 절차, EX2 §7.5 동일). 목표 허용: $\overline C{\lesssim}2\%$, $CV{\lesssim}10\%$, 저산소역 좌표 $\lesssim1$셀. 미달 시 세분 상향.

---

## 5. 수치·과도 관리 · 유동 재사용

- **초기·준정상:** EX2 §5.2 동일. 초기 $C{=}C^*$ → 폭기 순환 형성 → 준정상 창에서 `fieldAverage`.
- **DO 정상 스칼라:** 시간평균 유동장 위에서 DO 수렴(EX2 §3·§5.2b).
- **비용 절감(대규모 스윕 핵심):**
  - **유동 1회/배치:** 각 구조물 배치마다 무거운 URANS 유동을 1회 풀어 `flow/caseNNN/`에 저장, 그 위 DO 스칼라만 계산. (수온 고정이라 EX2식 수온 8배 재계산은 불필요 — 배치당 유동 1 + DO 1.)
  - **warm-start:** 인접 배치(구조물 1개 위치 이동)의 수렴 유동을 초기장으로 매핑 → 과도 단축.
  - **대칭 활용:** 구조물 배치가 폭기 대칭면을 보존하는 경우만 반도메인(대부분 비대칭이라 제한적).
  - **자동화:** 배치 파라미터(→ §sweep_design) → 케이스 디렉터리 생성 → 메시 → 유동 → DO → QoI 추출 → 데이터셋 append 를 스크립트화(EX2 `run_sweep16.sh` 계열 확장).

---

## 6. 후처리 · 데이터셋 추출

각 케이스에서(EX2 §5.4 도구 재사용):

- `fieldAverage` → 시간평균 $\overline C(\mathbf x), \overline{\mathbf U}$.
- **전장 export**: $\overline C$ 를 ROM 학습용 규격(정규격자 리샘플 또는 원격자+메타)으로 저장 → `dataset/`(스키마 `../dataset/README.md`).
- `probes` FO → EX2 공용 프로브 격자 값(경량 라벨).
- QoI: `computeCV.py` 계열로 $CV$·저산소 체적분율·$\min\overline C$·저산소역 좌표. 유동 $U_0$·Strouhal $f$(선택).

---

## 7. 물성치 · 케이스 파일 (이후 기입)

| 항목 | 값 / 상태 |
|---|---|
| 상속 상수 전부($C^*,k_L,\text{SOD},R_\text{bio},a,Sc_t,\alpha_g,\ldots$) | **EX2 확정값 상속** (`../../상수_목록.md`, `../../EX2/CFD/docs/CFD_방법론.md` §10) |
| 바위 형상 등급 S/M/L | ⟨사용자 확정 — 등가 치수·투영면적. 제안: S~4×4×h4, M~7×6×h7, L~11×8×h10 cm⟩ |
| 식물 항력 $D, C_F$ | **$D\approx0$, $C_F=C_D a\approx\{2,5,15\}$/m (S/M/L)** [R34]. 유도 `../00_구조물폐합_유도.md` Part 3A |
| 식물 대사 $P_\text{max}, R, \rho_B$ | **$P_\text{max}{\approx}5$, $R{\approx}1$ mg O₂ g⁻¹DW h⁻¹, $\rho_B{\approx}5$ g DW/L** [R35][R36]. 유도 `../00_구조물폐합_유도.md` Part 3B |
| 케이스 파일(0/·system/·constant/) | ⟨후속 — 스윕 자동화 스크립트 산출⟩ |

---

**요약:** EX3 CFD = EX2 과도 URANS 세팅·보정치 **무변경 상속** + 도메인에 바위(cut-out 고체)·식물(다공성 항력, 대사 ablation) 추가 · 배치당 유동 1회+DO 1회 · warm-start·자동화로 대규모 스윕 · 구조물 후류 국부세분·GCI 재점검 · 전장+QoI를 ROM 데이터셋으로 추출. 새 캘리브레이션 없음.
