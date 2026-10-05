# Figure / Table 목록 (제작 트래커)

> 프리프린트·Sensors 공용. 캡션은 **영문**.
> 상태: ☐ 미착수 / ◐ 작업중 / ☑ 완료

---

## Figures

| # | 제목(가안) | 내용 | 소스 | 담당 | 상태 |
|---|---|---|---|---|---|
| 1 | System pipeline | 사진→VLM→BC→LLM 추론→POD 재구성→이송확산→4×9 위험맵. ③④를 v2 대비 변경점으로 색 구분 | `../../논문_골격_v3.md` §2 | | ☐ |
| 2 | Hardware configuration | 카메라 + DS18B20 + IR 탁도 + 단일점 DO 프로브 (**Sensors 전용, 스코프 방어용**) | `../../../05_제품/` | | ☐ |
| 3 | Experimental setup | 수조 47×21×21, 폭기 위치, 16 측정위치 | `../../Experiment/EX2/` | | ☐ |
| 4 | Re-aeration DO curves | 실측 DO 시계열 + $K_La_\text{eff}$ 피팅 | EX2 7/29 실측 | | ☐ |
| 5 | Time-averaged flow field | 대표 케이스 유동장 + 정체역 표시 | EX3 CFD | | ☐ |
| 6 | POD modes | 상위 모드 시각화 | EX3 | | ☐ |
| 7 | Coarse risk map (4×9) | 예측 vs 실제 | `../../Experiment/EX3/09_검증_조대위험맵_중첩.md` | | ☐ |
| 8 | Baseline comparison | ⓐ~ⓖ + LLM 성능 (top1 / top1-Q) | EX3 5-fold CV | | ☐ |
| 9 | Grid convergence (GCI) | 격자수렴 | `../../../01_문서/정성실험_CFD/` | | ☐ |
| 10 | Uncertainty propagation | 잔차 → 확률맵 | §3.5 | | ☐ |

## Tables

| # | 제목(가안) | 내용 | 소스 | 상태 |
|---|---|---|---|---|
| 1 | Regime comparison | 선행 RAS DO-CFD vs 본 연구 (특성길이·수심·체적·위상·다상닫음) | `../../논문_초안_v2.md` §1 표1 | ☐ |
| 2 | Layer-A approaches attempted | 5종 접근 결과 요약 — "왜 LLM인가" | `../../논문_골격_v3.md` §2 | ☐ |
| 3 | Physical constants & properties | 수조 제원, $Q_\text{air}$, $\alpha_g$ 등 | **`../../Experiment/상수_목록.md`** (진실원) | ☐ |
| 4 | Boundary conditions | BC 요약 | **`../../Experiment/CFD_method.md`** (진실원) | ☐ |
| 5 | Re-aeration results | $K_La_\text{eff}$, $C^*$, κ, 잔차 | EX2 | ☐ |
| 6 | Baseline vs LLM (5-fold CV) | top1 / top1-Q, k 스윕 | EX3 | ☐ |
| 7 | Ablation & negative results | CNN 실패, 중첩 실패 | `06`·`09` | ☐ |

---

## 제작 규칙

- 해상도 **300 dpi 이상**, 벡터 가능하면 벡터(PDF/EPS)
- 컬러맵은 색각이상 대응 (viridis 계열). jet 금지
- 축 라벨·단위 영문, 폰트 크기 본문 대비 과소하지 않게
- 캡션은 그림만 보고도 이해되게 (self-contained)
- **모든 수치는 진실원 문서와 대조 후 기입** — 그림에서 새 값을 만들지 않는다
