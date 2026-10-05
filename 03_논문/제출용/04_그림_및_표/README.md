# 04_그림_및_표 — 논문_최종.md §3 삽화

## 그림 (본문)

| 파일 | 논문 절 | 내용 | 데이터 출처 |
|---|---|---|---|
| `fig01_EX1_Pet_vs_L.png` | §3.1 | 자기유사 레짐의 하한 — $Pe_t$ vs $L$, 구간별 $\lvert\Delta Pe_t\rvert$ | `EX1/EX1_결과.md` (1차·2차 스윕) |
| `fig04_EX2_reaeration_curves.png` | §3.4 | 5런 재폭기 곡선 + 1차 지연 선형화 | `EX2/어항실험/run_S1~S5.csv` (42,061점) |
| `fig05_EX2_KLa_vs_zstart.png` | §3.4 | $K_La^{20}$ vs $z_\text{start}$ 실측 대 CFD, $\kappa$ | `kappa_결과.csv` · `cfd_fixed.csv` |
| `fig09_EX3_learning_curve.png` | §3.6 | 조대 과제 포화 vs 장 과제 지속 개선 | `09_검증_조대위험맵_중첩.md` · `rom_pod_results_lc.json` |
| `fig15_stageB_regime_transition.png` | §3.8 | case0086 off/night/day — DO 장 + $\rho_{UC}$ 부호 붕괴 | `result/case0086` 재계산 (아래 참조) |

## 표

| 파일 | 내용 |
|---|---|
| `본문_표.md` | 표 3(격자) · 6(재폭기 5런) · 10(해상도 스윕) · 12(공간 진폭) · 13(배치 민감도) · 14(수위 $K_La$) · 16(레짐 전이) · 17(레짐 지도) |
| `참고자료_표.md` | 표 R1(정체역 최저점 253케이스 분포) · R2(펄스 결손 산포) — 본문 밖 |

## 재현

```bash
# 그림 1·4·5·9
python3 make_figs.py

# 그림 15 — case0086 을 3모드로 다시 풀어야 한다 (모드당 ~26 s)
PYTHONPATH=/tmp/pylibs python3 solve3.py off
PYTHONPATH=/tmp/pylibs python3 solve3.py night
PYTHONPATH=/tmp/pylibs python3 solve3.py day
PYTHONPATH=/tmp/pylibs python3 make_fig15.py plot
```

필요 패키지: `numpy`, `matplotlib`, `scipy`(그림 15만). 한글 폰트 `Noto Sans CJK`.

---

## 그림 15 를 재계산한 이유

`stageB_DO/_viz_case0231_off.npz` · `_viz_case0086_night.npz` 는 **부하 $R$ 이 다른 별개 실행**이고
케이스도 서로 달라(case0231 vs case0086) 표 3-11 의 통제 비교가 아니다. 그대로 그리면
스프레드가 0.301 / 0.204 mg/L 로 표 3-11(0.028 / 0.063)과 한 자릿수 어긋난다.

따라서 `dataset/result/case0086` 의 원 유동장에서 `solve_do.py` 를 `plant_mode` = off / night / day 로
다시 풀었다. ILU 전처리는 `drop_tol` 1e-4 → 1e-3, `fill_factor` 10 → 3 으로 낮췄고
(bicgstab `info=0` 수렴 유지), 결과가 `compare_photo.json` 과 일치함을 확인했다.

| 모드 | $C_\text{min}$ | $C_\text{max}$ | $\rho_{UC}$ | compare_photo.json 대비 |
|---|---|---|---|---|
| off | 7.959 | 7.987 | +0.708 | $\Delta C_\text{min}$ = −2.8e−08 |
| night | 7.608 | 7.671 | +0.481 | −2.8e−08 |
| day | 9.249 | 9.389 | −0.107 | −2.5e−09 |

---

## 미결 · 확인 필요

1. **표 3(격자 수렴)의 원 산출 로그 `study.log` 를 이 폴더에서 찾지 못했다.** 값은
   `논문_최종.md` 표 3-2 에서 옮겼다. 원본 위치를 확인하면 출처를 갱신할 것.
2. **그림 9 오른쪽 패널의 IoU 계열은 쓰지 않았다.** `rom_pod_results_lc.json` 의
   $N$ = 243 IoU median 은 **0.716** 인데 논문 표 3-8 의 $N$ = 202 행은 **0.632** 로 적혀 있다.
   anomL2 는 0.636 vs 0.639 로 사실상 같아 그림에는 anomL2 를 썼다.
   두 값이 다른 실행인지 확인이 필요하다.
3. `results.csv`(EX1 sweep_runs)의 **1차 스윕 5행에는 $Re$·$Pe_t$ 열이 없다.** 그림 1 은
   두 값이 모두 있는 `EX1_결과.md` 표를 정본으로 썼다.
