# References (마스터 참고문헌 + 식↔출처 매핑)

> 논문 §3(방법론)의 식·모델·BC와 CFD 입력 상수의 출처. 대부분 선행 연구의 표준 결과이며, 본 연구의 기여는 이들의 **결합·적용(가정 저산소역 도메인, 저가 관측 결합)** 에 있다.
> [R#] 키는 상수표(`../Experiment/상수_목록.md`)와 아래 매핑에서 공용.

---

## Part 1. 방법론 식 ↔ 출처 매핑

### §3.1 유동 (URANS · 비압축 · 단상)

| 식/모델 | 내용 | 출처 |
|---|---|---|
| 연속식 $\nabla\cdot\mathbf{U}=0$ | 비압축 유동 | [R16] |
| 운동량식(레이놀즈 평균 NS) | URANS, 와점성 근사 | [R17][R18] |
| 난류 폐합 SST $k\text{–}\omega$ ($\nu_t$) | 벽·자유전단 블렌딩 | [R15] |
| $\mathbf{F}_\text{air}=-(\rho_l-\rho_g)\alpha_g g\,\hat{\mathbf e}_z\mathbb 1_{\Omega_\text{air}}$ | 에어리프트 부력플룸(void 부력) | [R19][R20] |
| 기포유발 난류 $\mu_\text{BI}$ (선택) | Sato 폐합 | [R8] |
| 자유수면 rigid-lid·free-slip / 5면 no-slip | 저Froude 표준 BC | [R16] |

### §3.1 DO (과도상태 이송-확산)

| 식/모델 | 내용 | 출처 |
|---|---|---|
| $\partial_t C+\nabla\cdot(\mathbf U C)=\nabla\cdot(D_\text{eff}\nabla C)+\sum S$ | DO 물질수지·이송확산 계보 | [R21][R22] |
| $D_\text{eff}=D_\text{mol}+\nu_t/Sc_t$ | 난류확산·슈미트수 폐합 / 분자확산 | [R4][R2] |
| 재폭기 BC $-D_\text{eff}\partial_n C=k_L(C^*-C)$ | 이중막(two-film) 이론 | [R23] |
| $k_L(T)=k_{L,20}\theta_a^{T-20}$ | 재폭기 온도보정 | [R5] |
| $S_\text{air}=k_L a(C^*-C),\ a=6\alpha_g/d_b$ | 이중막 계면전달 + 기포 계면적 | [R23][R12] |
| $C^*(T)$ 포화 DO | Benson–Krause 정확식 | [R14] |

> **생물 소비/생성 항 제거(2026-07-16).** $S_\text{bio}=-R_\text{bio}(T)\,C/(K_b+C)$(Monod), $R_\text{bio}(T)$ 온도의존, 질화 화학량론($Y_{O_2}$)·반포화($K_b$) 매핑은 삭제했다 — 생물기원 소비/생성은 어항별 BC로 분리(`../논문_초안_v2.md` §3.1). 관련 문헌 [R3][R7][R10][R11][R13][R24]는 서지 목록에 **보존하되 모델에서는 미사용**([R#] 번호는 다른 인용과의 정합을 위해 유지). **저서 SOD도 제거(2026-07-16, 무저질 검증)** — 관련 [R6]도 모델 미사용으로 전환.
>
> **인공 국소 산소싱크 제거(2026-07-19).** 전기화학 ORR/화학(Na₂SO₃) 국소싱크 BC $-D_\text{eff}\partial_n C=(I/4F)M_{\mathrm{O_2}}/A_\text{el}$ 도 폐기했다. 물리엔진의 실측 앵커는 **비정상 재폭기 시험의 유효 산소전달계수 $K_La_\text{eff}$·보정계수 $\kappa$**(`../논문_초안_v2.md` §3.5·§4.1)이며, 저산소 진폭은 제품 단계 B층 생물소스가 부여한다. 구 설계는 `../../_archive/EX2_공간매핑_구주제/`.

### §3.2 무차원화 & 검·보정

| 식/방법 | 내용 | 출처 |
|---|---|---|
| 무차원 지배식, $Pe,\ \mathrm{Da},\ \mathrm{Sh}_s$ | 차원해석·수송현상 무차원화 | [R22][R25] |
| $Sr=fL/U_0$ (와류 흘림) | Strouhal 수 | [R26] |
| 무차원군 상사(Buckingham π) | 차원해석 정리 | [R27] |
| 실측 정량대조·캘리브레이션·blind 검증 | 계산과학 V&V | [R28] |

### §3.3 물리기저로 보호한 LLM 추론 (v3 신설 — `../논문_골격_v3.md` §3.3·§1.1)

> v3에서 A층을 학습형 대리모델에서 **LLM in-context 추론 + CFD POD 기저 구속**으로 전환하면서 신설. 아래 [R37]–[R42]는 2026-07-28 부여.

| 식/방법 | 내용 | 출처 |
|---|---|---|
| $\mathbf{U}\approx\overline{\mathbf{U}}+\sum_i a_i\varphi_i$, $\nabla\cdot\varphi_i=0$ | 발산-0 스냅샷의 선형결합이므로 모드·재구성장도 발산 0 (구조적 보장) | (유도) · `../Experiment/EX3/09_검증_조대위험맵_중첩.md` |
| 가중치 갱신 없이 프롬프트 예시로 연산자 학습 | In-Context Operator Networks 계보 | [R37][R38] |
| 사전학습 LLM + 시공간 인코딩으로 비정상 유동 예측 | LLM을 물리 예측에 직접 결합한 선례 | [R39] |
| LLM의 CFD 수행능력 한계 | 지식·수치추론·워크플로 구현 3축 벤치마크 | [R40] |
| VLM의 정량 계측·공간추론 취약성 | 본 방법이 **물리 기저로 보호막을 씌우는** 이유 | [R41][R42] |

> **양날 인용 원칙:** [R37]–[R39]는 방법의 정당성을, [R40]–[R42]는 그 한계를 동시에 근거지운다. 논문 서술은 *"취약점이 알려진 능력을, 물리 기저로 보호막을 씌워 사용한다"* 로 통일한다.

---

## Part 2. 참고문헌 목록

### 물성 · 확산 · 화학량론
- **[R1]** CRC Handbook of Chemistry and Physics; White, F.M., *Fluid Mechanics*, McGraw-Hill. (물·공기 물성)
- **[R2]** Ferrell, R.T. & Himmelblau, D.M. (1967), *J. Chem. Eng. Data* 12(1), 111–115. doi:10.1021/je60032a036. (O₂ 물속 확산계수)
- **[R3]** Tchobanoglous et al. (Metcalf & Eddy), *Wastewater Engineering*, McGraw-Hill. ($Y_{O_2}=4.57$, 질화) — *생물항 제거로 모델 미사용(2026-07-16).*

### 난류 · 모델 계수
- **[R4]** Tominaga, Y. & Stathopoulos, T. (2007), *Atmos. Environ.* 41(37), 8091–8099. doi:10.1016/j.atmosenv.2007.06.054. ($Sc_t$)
- **[R5]** Elmore, H.L. & West, W.F. (1961), *J. Sanit. Eng. Div. ASCE* 87(6), 59–71. ($\theta_a=1.024$)
- **[R6]** Thomann, R.V. & Mueller, J.A. (1987), *Principles of Surface Water Quality Modeling and Control*; Chapra, S.C. (1997), *Surface Water-Quality Modeling*. (SOD, $\theta_s$) — *물리 엔진에서는 미사용. **2026-08-02 제품층(B층)에서 부활** — `../논문_최종.md` §2.3 층 분리 계약. $\chi_\text{sod}$ 의 절대 크기 근거.*
- **[R7]** Clarke, A. & Johnston, N.M. (1999), *J. Animal Ecology* 68(5), 893–905. doi:10.1046/j.1365-2656.1999.00337.x. (어류 대사 $Q_{10}$) — *물리 엔진에서는 미사용. **2026-08-02 제품층에서 부활** — 앱 어류 소비항의 $Q_{10}$ = 2.0 근거. ⚠️ 사용 중인 값은 문헌 추정.*
- **[R8]** Sato, Y. & Sekoguchi, K. (1975), *Int. J. Multiphase Flow* 2(1), 79–95. doi:10.1016/0301-9322(75)90030-0. (기포유발 난류)

### 기준(20°C) 크기 — 캘리브레이션 대상
- **[R9]** Chapra, S.C. (1997), *Surface Water-Quality Modeling*, McGraw-Hill. ($k_L$ 범위)
- **[R10]** Clarke & Johnston (1999, [R7]) 및 어류 표준대사 문헌. (OCR) — *생물항 제거로 모델 미사용(2026-07-16).*
- **[R11]** Metcalf & Eddy ([R3]). (질화 $K_{O_2}\!\approx\!0.5$ mg/L, $r_\text{nit}$) — *생물항 제거로 모델 미사용(2026-07-16).*
- **[R13]** 내부 근거자료 `../Experiment/상수_목록.md`(어항 운전 가정: $Q_\text{air}$, 수조 치수) + 일반 소형 어항 사양. ($M_\text{fish}$ 가정은 생물항 제거로 폐기.)

### 기포 · 플룸
- **[R12]** Clift, R., Grace, J.R. & Weber, M.E. (1978), *Bubbles, Drops, and Particles*, Academic Press. ($d_b$, $U_\text{slip}$, $\alpha_g$)
- **[R19]** Morton, B.R., Taylor, G.I. & Turner, J.S. (1956), *Proc. R. Soc. A* 234, 1–23. doi:10.1098/rspa.1956.0011. (플룸 이론)
- **[R20]** Wüest, A., Brooks, N.H. & Imboden, D.M. (1992), *Water Resour. Res.* 28(12), 3235–3250. doi:10.1029/92WR01681. (기포플룸 모델)

### 지배식 · 이론 기반
- **[R14]** Benson, B.B. & Krause, D. (1984), *Limnol. Oceanogr.* 29(3), 620–632. doi:10.4319/lo.1984.29.3.0620. ($C^*(T)$)
- **[R15]** Menter, F.R. (1994), *AIAA Journal* 32(8), 1598–1605. doi:10.2514/3.12149. (SST $k\text{–}\omega$)
- **[R16]** Batchelor, G.K. (1967), *An Introduction to Fluid Dynamics*, Cambridge. (연속식·BC 표준)
- **[R17]** Reynolds, O. (1895), *Phil. Trans. R. Soc. A* 186, 123–164. doi:10.1098/rsta.1895.0004. (레이놀즈 평균)
- **[R18]** Pope, S.B. (2000), *Turbulent Flows*, Cambridge. (와점성·난류 폐합 개론)
- **[R21]** Streeter, H.W. & Phelps, E.B. (1925), *US Public Health Service, Public Health Bulletin No. 146*. (DO 물질수지 계보; **공용저작물**)
- **[R22]** Bird, R.B., Stewart, W.E. & Lightfoot, E.N. (2002), *Transport Phenomena*, 2nd ed., Wiley. (이송확산·무차원화)
- **[R23]** Lewis, W.K. & Whitman, W.G. (1924), *Ind. Eng. Chem.* 16(12), 1215–1220. doi:10.1021/ie50180a002. (이중막 이론)
- **[R24]** Monod, J. (1949), *Annu. Rev. Microbiol.* 3, 371–394. doi:10.1146/annurev.mi.03.100149.002103. (Monod 동역학) — *생물항 제거로 모델 미사용(2026-07-16).*
- **[R25]** Damköhler, G. (1936), *Z. Elektrochem.* 42, 846–862. (Damköhler 수)
- **[R26]** Strouhal, V. (1878), *Ann. Phys.* 241(10), 216–251. (Strouhal 수)
- **[R27]** Buckingham, E. (1914), *Phys. Rev.* 4(4), 345–376. doi:10.1103/PhysRev.4.345. (차원해석 π 정리)
- **[R28]** Roache, P.J. (1998), *Verification and Validation in Computational Science and Engineering*, Hermosa. (V&V)

### DO-어류 안전 · 도메인 대비 (동기·최초성)
- **[R29a]** Small, K., Kopf, R.K., Watts, R.J. & Howitt, J. (2014), "Hypoxia, Blackwater and Fish Kills: Experimental Lethal Oxygen Thresholds in Juvenile Predatory Lowland River Fishes," *PLoS ONE* **9**(4), e94524. doi:10.1371/journal.pone.0094524. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0094524 . 담수 실험 치사 임계 $\mathrm{LC}_{50}$ = 0.25 ± 0.06 (T. tandanus) ~ 1.58 ± 0.01 mg/L (M. peelii), 48 h, 25–26 °C.
- **[R29b]** Yu, M., Feng, Y., Ouyang, B., Wills, P.S. & Tang, Y. (2025), "Dissolved oxygen in aquaculture ponds: Causal factors, predictive modeling, and intelligent monitoring," *Aquacultural Engineering* **112**, 102634. doi:10.1016/j.aquaeng.2025.102634 . 대부분 어종에서 DO 5 mg/L 이상이 성장·섭이·생존·생리 요구를 만족하는 기준선.
  - **$C_\text{crit}$ = 6.0 mg/L 의 위계:** [R29b] 5 mg/L 기준선 + 안전 여유 → 6.0 단일 임계. [R29a] 치사 임계는 한 자릿수 아래이므로 본 판정은 치사가 아니라 **만성 스트레스 회피** 수준이다. (구 [R29] 항목은 출전 미특정 지침 요약이었으므로 2026-08-02 폐기.)
- **[R30]** Yu, G., Zhang, S., Chen, X., Li, D., Li, W. & Wang, Y. (2024), "Numerical investigations on dissolved oxygen field performance of octagonal culture tank based on computational fluid dynamics," *Computers and Electronics in Agriculture* **218**, 108737. doi:10.1016/j.compag.2024.108737. https://www.sciencedirect.com/science/article/abs/pii/S0168169924001285 . **팔각 산업 RAS 양식조($D{=}6.61$ m·수심 0.7 m·$H{=}0.8$ m)** 의 3D DO 場을 CFD-Euler-Euler-STM(ANSYS Fluent, RNG $k$-$\varepsilon$, UDF)으로 계산, 10점(P1~P10) 실측과 **MAPE 4.40%** 로 검증(최대 DO 5.68 mg/L, gas holdup 0.098; DO가 유선분포와 일치). *원문 PDF 확보(References 폴더).* 참고: 유동장·DO 분포 CFD($R^2{=}0.96$), *Aquacult. Eng.* (2025) https://www.sciencedirect.com/science/article/abs/pii/S0144860925000664 . 기존 3D DO CFD는 모두 산업 양식(원형·팔각·RAS) 대상 — **가정용 어항 저산소역 진단 적용은 본 연구가 최초**(차별점: 구속·단일 플룸 지배로 $Pe$ 공간변동 O(0.1)~O(100)·벽걸이 비대칭 플룸·얕은 수심 단상 근사·저가 관측 결합).
- **[R33]** Yu, G., Zhang, S., Zhang, G., Yin, Y., Li, D. & Wang, Y. (2026), "Numerical simulation of oxygen transfer in recirculating aquaculture system: A CFD-PBM approach," *Aquacultural Engineering* **115**, 102774. doi:10.1016/j.aquaeng.2026.102774. https://www.sciencedirect.com/science/article/abs/pii/S0144860926000907 . **원형 산업 RAS 리액터($D{=}1.5$ m·$H{=}0.4$ m)** 의 산소전달을 2상 CFD + 개체군수지(PBM, 비균일 기포크기분포) + 성분전달로 계산, 다점 실측과 **평균오차 6.81%** 로 검증(계면전달계수 $k_L{=}1.94\times10^{-4}$ m/s에서 최대 DOC 7.7 mg/L; 유선이 DO와 일치, 입구유량·폭기위치로 DO 균일도 개선). *원문 PDF 확보(References 폴더).* 본 연구 대비: 대형·깊은 탱크라 무거운 2상 PBM이 필수인 **벌크 혼합 레짐** — 가정 어항(얕음·구속·단일 플룸)과 무차원 레짐이 다르다(§1 표 1). 국소 구성식($k_L$ 크기대·이중막 $k_La$ 형태·$a{=}6\alpha_g/d_b$)은 검증된 입력으로 전이·인용 가능하나, DO 장·저산소역 결과는 전이 불가.

### 구조물 폐합 — 식물 항력·대사 (EX3 전용, 물리엔진 기본식 아님)

> EX3(A층 ROM)가 도메인에 추가하는 구조물 폐합. 논문 §3.1 지배방정식에는 들어가지 않으며, 식↔출처 상세 매핑·유도는 `../Experiment/EX3/00_구조물폐합_유도.md`.

- **[R34]** Nepf, H.M. (2012), "Flow and Transport in Regions with Aquatic Vegetation," *Annual Review of Fluid Mechanics* **44**, 123–142. doi:10.1146/annurev-fluid-120710-101048. https://www.annualreviews.org/content/journals/10.1146/annurev-fluid-120710-101048 . 캐노피 평균유동을 정면투영면적 밀도 $a$ 분포가 결정, 체적 형상항력 $F_D=\tfrac12\rho C_D a\lvert U\rvert U$, $a=m d_s$. 본 연구는 이를 CFD 다공성(Forchheimer, $C_F=C_D a$·$D\approx0$) 운동량 소스로 전개해 수생식물 군락을 표현.
- **[R35]** Nielsen, S.L. & Sand-Jensen, K. (1989), "Regulation of photosynthetic rates of submerged rooted macrophytes," *Oecologia* **81**(3), 364–368. doi:10.1007/BF00377085. https://link.springer.com/article/10.1007/BF00377085 . 온대 수생대형수초 14종, 광포화 광합성 $P_\text{max}$=0.59–17.98 mg O₂ g⁻¹DW h⁻¹(15 °C, pH 8.3). 식물 대사 O₂ 소스의 크기대 근거.
- **[R36]** Jassby, A.D. & Platt, T. (1976), "Mathematical formulation of the relationship between photosynthesis and light for phytoplankton," *Limnology and Oceanography* **21**(4), 540–547. doi:10.4319/lo.1976.21.4.0540. https://aslopubs.onlinelibrary.wiley.com/doi/10.4319/lo.1976.21.4.0540 . P–I 곡선 최적형이 쌍곡탄젠트 $P=P_\text{max}\tanh(I/I_k)$임을 실증. 주/야·조도 의존 대사의 함수형.

### LLM · VLM의 물리·공간 추론 (v3 §3.3·§1.1 — 2026-07-28 신규 부여)

> **긍정 계보 [R37]–[R39]** = 가중치 갱신 없는 in-context 연산자 학습과 LLM 기반 유동 예측이 이미 성립한다는 근거.
> **한계 계보 [R40]–[R42]** = 그 능력이 정량 계측·공간추론에서 취약하다는 근거 → 격자장 직접 출력을 기각하고 POD 기저로 출력을 구속하는 설계 정당화.

- **[R37]** Yang, L., Liu, S., Meng, T. & Osher, S.J. (2023), "In-Context Operator Learning with Data Prompts for Differential Equation Problems," *PNAS* **120**(39), e2310142120. doi:10.1073/pnas.2310142120. arXiv:2304.07993. https://arxiv.org/abs/2304.07993 . 단일 신경망을 **연산자 학습기**로 훈련해, 추론 시 프롬프트의 예시 데이터만으로 새 연산자를 **가중치 갱신 없이** 적용(ODE·PDE 순/역문제, 평균장 제어). 훈련분포 밖 연산자로의 일반화도 보고. → v3 §3.3.2 in-context 계수 추론의 방법론적 선례.
- **[R38]** Cao, Y., Liu, Y., Yang, L., Yu, R., Schaeffer, H. & Osher, S. (2024), "VICON: Vision In-Context Operator Networks for Multi-Physics Fluid Dynamics Prediction," arXiv:2411.16063. https://arxiv.org/abs/2411.16063 . ICON이 공간점 하나를 토큰 하나로 처리해 고차원 조밀 데이터에서 비효율적인 문제를, **비전 트랜스포머의 패치 단위 처리**로 해소. 3종 유체역학 벤치마크에서 DPOT·MPP 대비 최종스텝 롤아웃 오차 37.9 %·44.7 % 감소. 샘플링 주기가 다르거나 프레임이 빠지는 **불완전 계측 환경**에서 성능 저하가 24.41 %(베이스라인 71–74 %)로 강건. → in-context 계보가 **유동장**으로 확장된 사례.
- **[R39]** Zhu, M., Bazaga, A. & Liò, P. (2024), "FLUID-LLM: Learning Computational Fluid Dynamics with Spatiotemporal-aware Large Language Models," arXiv:2406.04501. https://arxiv.org/abs/2406.04501 . 사전학습 LLM + 시공간 인식 인코딩으로 **비정상(unsteady) 유동**을 예측. LLM의 시간 자기회귀 능력과 공간 인식층을 결합. 저자들 스스로 "LLM은 유체역학 고유의 복잡한 기하에서 어려움을 겪는다"고 명시 → 기하를 LLM에 직접 맡기지 않는 v3 설계와 정합.
- **[R40]** Somasekharan, N., Yue, L., Cao, Y., Li, W., Emami, P., Bhargav, P.S., Acharya, A., Xie, X. & Pan, S. (2025), "CFDLLMBench: A Benchmark Suite for Evaluating Large Language Models in Computational Fluid Dynamics," arXiv:2509.20374. https://arxiv.org/abs/2509.20374 . CFDQuery·CFDCodeBench·FoamBench 3종으로 **대학원 수준 CFD 지식 / 수치·물리 추론 / 맥락의존 워크플로 구현**을 평가. 코드 실행가능성·해 정확도·수치 수렴거동으로 정량화. → LLM에 CFD를 통째로 맡기는 접근의 위험 근거.
- **[R41]** Lin, F., Liu, Y., Xu, H., Yue, C., He, Z., Zhao, M., Chen, M.H., Liu, J., Yao, JG. & Yang, X. (2025), "Do Vision-Language Models Measure Up? Benchmarking Visual Measurement Reading with MeasureBench," arXiv:2510.26865. https://arxiv.org/abs/2510.26865 . 실사 1,272 + 합성 1,170 = **2,442 image–question 쌍**(39종 계측기)에서 최신 VLM이 계측값 판독에 일관되게 실패. 일관된 실패 모드는 **지시자 위치추정(indicator localization)** — 숫자·라벨은 읽지만 바늘·눈금의 핵심 위치를 잘못 짚어 큰 수치오차를 낸다. → 사진에서 **정량 계수**를 직접 읽지 않고 센서·사전분포로 분리하는 §3.2 "정직한 범위" 설계의 직접 근거.
- **[R42]** Jia, M., Qi, Z., Zhang, S., Zhang, W., Yu, X., He, J., Wang, H. & Yi, L. (2025), "OmniSpatial: Towards Comprehensive Spatial Reasoning Benchmark for Vision Language Models," arXiv:2506.03135. https://arxiv.org/abs/2506.03135 . 인지심리학에 기반해 **동적 추론·복잡 공간논리·공간 상호작용·관점 전환** 4범주 50개 세부범주, 8.4K QA 쌍. 좌/우·원근·개수세기 같은 기초 공간관계를 넘어선 층위에서 VLM이 병목임을 보고. → 3D 공간 정량추론을 LLM 출력에 직접 맡기지 않는 근거.

### SW 트랙 — VLM · 축소모델(ROM)

- [x] 멀티모달 VLM structured output / 이미지→구조화 정보 추출 근거 — 논문 §3.2 → **[R47] 확보(2026-07-28)**. 단 §3.2 기술스택 확정 후 최종 인용 재검토
- [x] POD-ROM / 회귀 방법 근거 — **[R49][R50][R51] 확보(2026-08-02)**. 배포 A층이 PCA + Ridge 로 확정되면서 대리 신경망(DeepONet·U-Net) 계보는 불필요해짐
- [ ] (확보 예정) 어종·수질–건강 상관 공개 데이터셋·문헌 — 어류 건강도 트랙
- [x] **건물 BIM/실내공간 → CFD 자동 BC** 계보 — **[R52] 확보(2026-08-02)**. ⚠️ 저자·권호 확인 필요
- [x] **저서 SOD 계수** — **[R6] 부활(2026-08-02)**. 물리 엔진에서는 삭제 유지, 제품층(B층)에서만 사용

### 플룸 단상 근사 타당성 (§5.2·CFD_방법론)
- **[R31]** Bernard, R.S., Maier, R.S. & Falvey, H.T. (1999). 단상 부력 body-force 플룸 모델(2상 대비 계산효율적 등가): 부력플럭스 적분상사(MTT [R19]·Wüest [R20]) + 단상 CFD body-force 구현 — "A simple computational model for bubble plumes," *Appl. Math. Modelling* 23(2):181 (1999) https://www.sciencedirect.com/science/article/pii/S0307904X9900030X ; McCook Reservoir aeration bubble plume models(HES-71). 총 부력플럭스 $=g\,Q_\text{air}$ 가 순환을 결정 → 얕은 수조에서 기포 내부구조 불요.
- **[R32]** 기포 void 분율↔겉보기 기체속도(drift-flux/gas holdup): $\alpha_g\approx U_{gs}/(C_0U_{gs}+U_\text{slip})$ 또는 $U_{gs}/(W+U_\text{slip})$. 본 케이스 $U_{gs}=0.106$ m/s·$U_\text{slip}\approx0.22$ m/s → $\alpha_g\approx0.2$–0.3. (bubble column gas holdup 문헌; 슬립·$d_b$ 는 [R12].)

### 2026-07-28 신규 확보 (논문 검토에서 드러난 인용 공백 보충)

> 각 항목은 **어느 주장을 떠받치는지**를 명시한다. 서지 상세(저자 전체·페이지)는 원문 확보 시 보강 — 아래 ⚠️ 표시 항목.

- **[R43]** ASCE/EWRI **2-06**, *Measurement of Oxygen Transfer in Clean Water* (M.K. Stenstrom, ed.), ASCE, ISBN 978-0-7844-0848-3. https://ascelibrary.org/doi/book/10.1061/9780784408483 · https://pubs.asce.org/Product?isbn=9780784408483 . ANSI/ASCE 2-91의 전면개정. **실험실 규모(수 갤런)부터 전규모까지** 적용 범위 명시 — 20.7 L 어항이 범위 안. **비정상 재폭기 시험의 규약 근거**: 상승부 **~85 %까지가 $K_La$ 에 민감**, **90 % 이상 평탄부가 $C^*$ 에 민감**; 데이터는 **최저 DO ≤ 20 % $C^*$·최고 DO ≥ 98 % $C^*$** 를 span 해야 한다. → 논문 §4.1·`EX2_방법론.md` §2 유효창(하위 제외·상위 90–95 %)·`fit_kla.py` 기본값(lo 0.15/hi 0.92)의 직접 근거. **후속판 ASCE/EWRI 2-22**(ISBN 978-0-7844-1564-1, https://pubs.asce.org/Product?isbn=9780784415641 )가 존재하므로 최종 인용은 2-22로 갱신 검토. ⚠️ 유료 표준 — 도서관 접속으로 원문 확보 후 절 번호까지 특정할 것
  - **주의:** ASCE가 규정하는 것은 **측정이 덮어야 할 범위**(≤20 %→≥98 %)이고, **피팅창(15–92 %)은 그 안에서 우리가 고르는 것**이다. 논문에 이 구분을 명시해야 "임의 선택"이라는 지적을 피한다
  - 프로브 응답지연 판정선 $K_La\cdot\tau_p<0.02$ 도 이 표준 계열 관행 — 원문에서 해당 조항 확인 필요

- **[R44]** 저가 IoT DO 모니터링 = **단일점 시간예측** 계보 (논문 §1.1 ④·§1 신규성 위치)
  - (a) "Preliminary Field Evaluation of a Low-Cost IoT Workflow for Dissolved Oxygen Monitoring and Short-Horizon Forecasting in Nile Tilapia Aquaculture," *Sensors* **26**(13), 4242 (2026). https://www.mdpi.com/1424-8220/26/13/4242 . ESP32 노드가 DO·수온·pH를 **한 지점**에서 연속측정 → 클라우드 → 5분 집계창에서 단기예보. 30분 예보 MAE **0.783 mg/L**, 방향정확도 60.23 %(RF). 
  - (b) "A deep learning-enabled IoT framework for early hypoxia detection in aqua water using light weight spatially shared attention-LSTM network," *J. Supercomputing* (2023). doi:10.1007/s11227-023-05580-x . LSTM 기반 **저산소 조기탐지** — 우리와 목적이 같으나 **시간 축**이고 공간 축이 없음.
  - (c) "Machine Learning on Low-Cost Edge Devices for Real-Time Water Quality Prediction in Tilapia Aquaculture," PMC12526668. https://pmc.ncbi.nlm.nih.gov/articles/PMC12526668/ . MLR/DTR/RFR 비교, ESP32 탑재.
  - → **차별화 문장의 근거:** 저가 DO 선행은 (i) 단일 지점, (ii) 시간 방향 예측, (iii) 순수 데이터구동이다. 본 연구는 (i) 공간 장, (ii) 물리 기반이라 **축이 다르다**. ⚠️ "**모두**"라는 전수 주장은 이 3건으로 지지되지 않으므로 "**우리가 조사한 범위에서는**"으로 완화할 것

- **[R45]** Yang, X. et al. (2025), "AI-powered automated model construction for patient-specific CFD simulations of aortic flows," *Science Advances*. doi:10.1126/sciadv.adw2825 . arXiv:2503.12515. https://www.science.org/doi/10.1126/sciadv.adw2825 . 의료영상(CT)에서 **기하 구성·메시 생성을 자동화**해 환자별 CFD를 세우는 파이프라인. 기존의 중심선 추출·단면 분할·표면 보간 수작업이 "변동성·주관적 해석에 취약"하고 이것이 임상 적용의 **최대 병목**이라고 명시. 관련: "Direct medical image to simulation using auto-segmentation and point cloud-based CFD," PMC12927703. → **논문 §1.1 ③·§1 B5 "사진→CFD 디지털트윈은 타 도메인(의료)에 선례" 의 직접 근거.** 차별점: 의료는 **단층촬영(3D 체적 데이터)** 이고 우리는 **단일 2D 사진**이라 깊이가 미관측 → §3.2의 중앙면 prior가 필요한 이유. ⚠️ 저자 전체 미확인 · 건물(BIM→CFD) 계보는 별도 검색 필요

- **[R46]** 어류 호흡률(OCR) — B층 생물 소스 문헌값 (논문 §4.4·§5, `CFD_method.md` §4에서 분리된 어항별 BC)
  - (a) "Metabolic Rate of Goldfish (*Carassius auratus*) in the Face of Common Aquaculture Challenges," *Biology* **13**(10), 804 (2024). https://www.mdpi.com/2079-7737/13/10/804 · PMC11504095. **금붕어 기준대사율 RMR = 180 mg O₂ kg⁻¹ h⁻¹**(baseline). 30 °C 승온 시 2.5 h 후 **+200 %**. → **가정 어항 대표종의 직접 값**
  - (b) 일반 범위: 성어 **200–500 mg O₂ kg⁻¹ h⁻¹**, 최대(활동대사) ~1000±200. https://www.globalseafood.org/advocate/dissolved-oxygen-requirements-in-aquatic-animal-respiration/ (업계 자료 — 학술 인용은 (a) 우선)
  - → **주의:** 이 값은 **상수율(0차)** 로 쓸 때만 DO 방정식의 선형성이 유지된다. Monod/Michaelis–Menten 형태로 두면 비선형이 되어 중첩·ROM 선형성 논거가 깨진다(논문 §3.3·§5.3(v))

- **[R47]** Geng, S. et al. (2025), "Generating Structured Outputs from Language Models: Benchmark and Studies" (**JSONSchemaBench**), arXiv:2501.10868. https://arxiv.org/abs/2501.10868 . **제약 디코딩(constrained decoding)** — 유효하지 않은 토큰을 마스킹해 출력이 사전정의 스키마를 따르도록 강제하는 기법을 6개 프레임워크(Guidance·Outlines·llama.cpp·XGrammar·OpenAI·**Gemini**)에서 평가. LM 생성은 확률적이라 구조를 보장하지 못하며 이것이 구조화 입력을 요구하는 응용의 배치 장벽이라고 명시. → **논문 §3.2 "프롬프트+구조화 출력, 학습 불필요" 의 방법론 근거.** ⚠️ 저자 전체 미확인. §3.2 기술스택 확정 후 최종 인용 결정

- **[R48]** 미세기포 gas holdup — **[R32] 보완/대체**
  - "Effects of the Microbubble Generation Mode on Hydrodynamic Parameters in Gas–Liquid Bubble Columns," *Processes* **8**(6), 663 (2020). https://www.mdpi.com/2227-9717/8/6/663 . 미세다공 소결판·폼건으로 **미세기포** 생성, 겉보기 기체속도 **$U_{gs}$=0.013–0.100 m/s** 범위 — 우리 실측 $U_{gs}$=**0.0637** m/s가 이 범위 안에 든다.
  - "One-dimensional drift-flux model of gas holdup in fine-bubble jet reactor," *Chem. Eng. J.* (2019). doi:10.1016/j.cej.2019.04.056 계열. https://www.sciencedirect.com/science/article/abs/pii/S1385894719305650 . **미세기포 전용 drift-flux**(Sauter 평균직경·평균상승속도·에너지소산 3개 부모델).
  - → **[R32]의 문제:** 현행 [R32] 항목은 "$U_{gs}=0.106$·$U_\text{slip}\approx0.22$ m/s → $\alpha_g\approx0.2$–0.3"이라 적었는데, $U_\text{slip}$ 0.22 m/s는 **약 2–3 mm 기포** 조건이다. 우리는 $d_b$=0.5 mm·$U_\text{slip}$=0.055 m/s(D군)를 쓰므로 **입력이 다르고 결론만 우연히 겹친다.** [R32]는 관계식 $\alpha_g=U_{gs}/(W+U_\text{slip})$ 만 인용하고 케이스 수치는 삭제, 미세기포 조건은 [R48]로 대체할 것

### 축소모델 · 회귀 방법 (2026-08-02 신규 부여)

> `../논문_최종.md` §2.6(PCA + Ridge 배포 A층) · §3.6(유동장 POD 비교 경로)의 방법 근거.
> ⚠️ 서지 상세는 1차 검증만 거쳤다. 원문 확인 후 확정할 것.

- **[R49]** Berkooz, G., Holmes, P. & Lumley, J.L. (1993), "The Proper Orthogonal Decomposition in the Analysis of Turbulent Flows," *Annual Review of Fluid Mechanics* **25**, 539–575. doi:10.1146/annurev.fl.25.010193.002543 . POD 축소 표현의 표준 문헌.
- **[R50]** Hoerl, A.E. & Kennard, R.W. (1970), "Ridge Regression: Biased Estimation for Nonorthogonal Problems," *Technometrics* **12**(1), 55–67. doi:10.1080/00401706.1970.10488634 . 배포 A층의 잠재계수 회귀(RidgeCV).
- **[R51]** Pedregosa, F. et al. (2011), "Scikit-learn: Machine Learning in Python," *Journal of Machine Learning Research* **12**, 2825–2830. PCA·RidgeCV 구현 및 5-fold CV 프로토콜.

### 건물 도메인 → CFD 자동 BC (2026-08-02 신규 부여)

- **[R52]** "Simulation method for indoor airflow based on the Industry Foundation Classes model," *Journal of Building Engineering* (2021). https://www.sciencedirect.com/science/article/abs/pii/S2352710221001078 . IFC 모델의 의미·기하·관계 정보로 **건물 내부 공간을 자동 추출하고 수치 계산격자를 분할**해 CFD 경계조건을 설정. 논문 §1.1 ③ 의 "의료·**건물**" 서술 중 건물 쪽을 덮는다([R45]는 의료만 덮음). ⚠️ **저자·권호 미확인** — 원문 확인 필요.

---

## Part 3. 원문 PDF 확보 (파일 저장 계획)

> **주의:** 아래 대부분은 저널·출판사 저작권(유료) 문헌이라 자동 다운로드·재배포가 불가하다. 원문 PDF는 아주대 도서관 전자저널/기관 접속으로 DOI를 통해 각자 내려받아 이 폴더에 저장한다. 공용저작물(public domain)만 자유 확보 가능.

| 파일명(예정) | 문헌 | 접근 | PDF |
|---|---|---|---|
| `01_Menter_1994_SST.pdf` | [R15] Menter 1994 | doi:10.2514/3.12149 (AIAA, 유료) | ☐ |
| `02_BensonKrause_1984_DOsat.pdf` | [R14] | doi:10.4319/lo.1984.29.3.0620 (유료) | ☐ |
| `03_LewisWhitman_1924_twofilm.pdf` | [R23] | doi:10.1021/ie50180a002 (공용저작물 가능) | ☐ |
| `04_StreeterPhelps_1925_bulletin146.pdf` | [R21] | 공용저작물(US PHS) | ☐ |
| `05_Sato_Sekoguchi_1975.pdf` | [R8] | doi:10.1016/0301-9322(75)90030-0 (유료) | ☐ |
| `06_MTT_1956_plume.pdf` | [R19] | doi:10.1098/rspa.1956.0011 (유료) | ☐ |
| `07_Wuest_1992_bubbleplume.pdf` | [R20] | doi:10.1029/92WR01681 (유료) | ☐ |
| `08_Monod_1949.pdf` | [R24] | doi:10.1146/annurev.mi.03.100149.002103 (유료) | ☐ |
| `09_Tominaga_2007_Sct.pdf` | [R4] | doi:10.1016/j.atmosenv.2007.06.054 (유료) | ☐ |
| `10_ClarkeJohnston_1999_Q10.pdf` | [R7] | doi:10.1046/j.1365-2656.1999.00337.x (유료) | ☐ |
| `11_ElmoreWest_1961_reaeration.pdf` | [R5] | ASCE (유료) | ☐ |
| `12_Buckingham_1914_pi.pdf` | [R27] | doi:10.1103/PhysRev.4.345 (공용저작물 가능) | ☐ |
| `Numericla investigaions ... octagonal culture tank ....pdf` | [R30] 팔각 RAS 2024 | doi:10.1016/j.compag.2024.108737 | ☑ (확보) |
| `Numerical simulation of oxygen transfer in recirculating aquaculture system.pdf` | [R33] 원형 RAS CFD-PBM 2026 | doi:10.1016/j.aquaeng.2026.102774 | ☑ (확보) |
| `13_Yang_2023_ICON_PNAS.pdf` | [R37] ICON | arXiv:2304.07993 (**arXiv 공개**) | ☐ |
| `14_Cao_2024_VICON.pdf` | [R38] VICON | arXiv:2411.16063 (**arXiv 공개**) | ☐ |
| `15_Zhu_2024_FLUID-LLM.pdf` | [R39] FLUID-LLM | arXiv:2406.04501 (**arXiv 공개**) | ☐ |
| `16_Somasekharan_2025_CFDLLMBench.pdf` | [R40] CFDLLMBench | arXiv:2509.20374 (**arXiv 공개**) | ☐ |
| `17_Lin_2025_MeasureBench.pdf` | [R41] MeasureBench | arXiv:2510.26865 (**arXiv 공개**) | ☐ |
| `18_Jia_2025_OmniSpatial.pdf` | [R42] OmniSpatial | arXiv:2506.03135 (**arXiv 공개**) | ☐ |

> [R37]–[R42]는 **전부 arXiv 공개본**이라 유료 접속 없이 확보 가능하다. 위 6건은 우선 내려받아 폴더에 저장할 것.

*교재([R1][R6][R12][R16][R18][R22] 등)는 도서/저작권 자료로 PDF 저장 대상에서 제외.*
