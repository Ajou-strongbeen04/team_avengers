# 06 · A층 ROM Stage 2-B — 3D CNN (핸드오프)

> 팀 漁벤져스 · 2026-07-24 · 계획 `04_ROM착수_계획.md` §2 Stage2-B · 선행결과 `05_ROM_Stage2A_결과.md`
> 코드 `scripts/rom_cnn.py`

## 1. 왜 CNN이고, 왜 이 구조인가

Stage 2-A 진단: **POD 기저는 충분(projection ceiling anomL2 0.29·IoU 0.86), 병목은 기하→계수 회귀.**
따라서 full U-Net(장→장)이 아니라 **점유격자 → POD 계수** 회귀만 CNN으로 교체한다.

- 출력이 r개 계수(≈108)로 작아 경량, 검증된 POD 디코더 재사용.
- 입력은 **원시 점유격자**(2ch: 점유·kind) — 엔지니어드 특징이 아니라 공간 자체.

**in-sandbox 근거 (회귀기를 바꾼 실험):**

| 회귀기 | anomL2 | IoU med | cdist mm |
|---|---|---|---|
| Ridge(선형) | 0.703 | 0.563 | 11.4 |
| **RF** | **0.612** | **0.718** | **7.2** |
| MLP(FC, 엔지니어드특징) | 0.822 | 0.524 | 12.0 |
| ceiling(목표) | 0.293 | 0.861 | 2.7 |

MLP가 RF보다 나쁜 것이 핵심 신호다 — **수작업 특징 위 완전연결망으론 부족**하다(243샘플 과적합).
즉 남은 개선은 **원시 격자 + 합성곱 귀납편향(CNN)** 에서 나와야 한다. 이것이 Stage 2-B의 정당화다.

## 2. 실행 환경 — 팀 GPU에서 (샌드박스 불가)

이 세션 샌드박스엔 **GPU도 torch도 없고(디스크·다운로드 제약으로 설치 불가)** 3D conv 학습을 못 돌린다.
팀은 이미 GCP를 쓰므로 CNN은 **GPU 환경(로컬 GPU / Colab / GCP VM)** 에서 실행한다. 스크립트는 이식형으로 작성됨.

```bash
# 1) 데이터 준비 — 로컬 result/에서 npz 재생성 (887MB, 재생성 2.5분)
python3 scripts/resample_encode.py --result-dir dataset/result --out-dir <npz폴더> --skip-existing

# 2) GPU에 torch 설치
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 3) CNN 학습·평가 (native 해상 권장; POD/평가 지표는 rom_pod.py와 동일)
python3 scripts/rom_cnn.py --fields-dir <npz폴더> \
    --split dataset/training_dataset/test_split.json \
    --labels dataset/training_dataset/labels.parquet \
    --pool 1 --epochs 300 --out dataset/training_dataset/cnn_results.json
```

- `--pool 1` = native 108×48×48(GPU 메모리 여유 시). CPU/저메모리면 `--pool 2`(54×24×24)로 POD+RF와 동일 격자 직접비교.
- 동일 `test_split.json`(동결 10) 사용 → **POD+RF와 숫자 직접 비교**.
- 산출: `cnn_results.json`(anomL2·IoU·cdist per-case+요약), `rom_cnn.pt`(모델 가중치).

## 3. 아키텍처 (`build_cnn`)

점유격자(2,NZ,NY,NX) → Conv3d-BN-ReLU-MaxPool ×4 (16→32→64→128ch) → GAP →
FC(128→256)→Dropout→FC(256→r). 타깃 = 표준화된 POD 계수(MSE). 검증 조기종료·ReduceLROnPlateau.

> 확장 여지: full 3D U-Net(점유→전장 U) 도 가능하나, ceiling이 저차원임을 보였으므로 **계수회귀가 1차 선택**.
> 데이터 부족(n≤2, 243)이 CNN 발목을 잡으면 → Tier3 40~60 층화 추가(학습곡선 미포화가 근거) 후 재학습.

## ★ 실행 결과 (2026-07-24, 로컬 RTX 4070, native pool=1, energy0.9 r=28)

**학습 성공(스캐폴딩·수정 후):** train 1.01→0.21, val 1.09→0.60(baseline 1.09) → 신호 포착.
**test10 종합:** anomL2_med 0.713 · IoU_med 0.677 · IoU_min 0.191 · cdist_med 6.6mm.
(주의: CNN=native/r28, POD+RF=pool2/r108 → 격자·모드 달라 절대치 직접비교 불가. cdist(mm)만 격자-강건.)

### 진단 — per-case 이봉 분포 + 원인 분해

CNN IoU가 **식물 케이스 우수(0.76~0.89) / 바위 케이스 실패(0.19~0.45)** 로 갈림.

| case | 구성 | CNN IoU | ceil@r28 | ceil@r108 | 판정 |
|---|---|---|---|---|---|
| 0038 | plant S | 0.892 | 0.914 | 0.934 | 우수 |
| 0164 | plant×2 | 0.835 | 0.908 | 0.938 | 우수 |
| 0092 | plant×2 | 0.832 | 0.911 | 0.931 | 우수 |
| 0099 | plant M+L | 0.758 | 0.825 | 0.876 | 양호 |
| 0031 | **rock L** | 0.349 | 0.559 | 0.616 | 실패 |
| 0158 | **rock×2 S** | 0.448 | 0.686 | **0.810** | 실패(절단민감) |
| 0204 | **rock S+M** | 0.391 | 0.643 | **0.786** | 실패(절단민감) |
| 0141 | **rock L×2, blk0.085** | 0.191 | 0.421 | **0.494** | 실패(ceiling 자체 낮음) |

**두 원인이 겹침:**
1. **POD 절단(r=28).** 바위 후류가 모드 28~108에 존재 → 바위는 r28→r108서 IoU +0.06~0.16(0158 +0.12, 0204 +0.14), 식물은 +0.02뿐. → **바위엔 energy↑(더 많은 모드) 필요.**
2. **회귀 간극·표본부족.** ceiling−CNN이 바위 ~0.20~0.24 ≫ 식물 ~0.05~0.09. 특히 0141(대형바위2·고차단)은 r108 ceiling조차 0.49 → **조밀·바위 구성 자체가 데이터에 희박(Tier3 영역).**

> 물리적으로 저산소역을 만드는 주체는 **바위 후류**(식물은 약항력이라 유동≈평균장). 즉 CNN이 **정작 중요한 곳에서 약하다.** 해결은 (a) energy↑ + (b) 바위·조밀 데이터(Tier3) — 상호보완(모드를 늘리면 회귀할 데이터도 더 필요).

### energy 0.99 재실행 결과 (절단가설 검증, `cnn_results_e99.json`)

r=111로 바위후류 모드를 회귀대상에 넣었으나 **전반적으로 오히려 악화**: anomL2_med 0.713→**0.758**, IoU_med 0.677→0.682(동일), cdist 6.6→**7.9mm**. 바위 케이스도 거의 불변(0031 0.349→0.305, 0158 0.448→0.468, 0204 0.391→0.403).

**→ 절단가설 기각, 데이터 병목 확정.** r=111엔 바위후류 모드가 있으나(ceiling 0.79~0.81) CNN이 243샘플로 **회귀하지 못해** ~0.40에 정체. 모드를 줘도 맞힐 데이터가 없으면 무효. train0.30≪val0.68로 과적합만 심화. **r=28(energy0.9)이 더 나은 작동점.**

### 다음 (확정)

1. ~~energy 0.99 테스트~~ → 완료, 데이터 병목 확정.
2. **[핵심·진행] Tier3 52케이스 생성** — 바위우세49/52·all-rock12·blk중앙0.082 선별(`tier3_selection.csv`, idx 385~698). GCP 실행 → `06_TIER3_실행.md`(또는 `GCP/batch/worker_tier3.sh`).
3. Tier3 반영(253→305) 후 재인코딩 → CNN 재학습(energy는 0.9 유지 권장) → POD+RF와 **동일 pool·energy**로 최종 head-to-head. 바위 IoU 개선폭이 판정.
4. 폴백: 개선 미미하면 **POD+RF(pool2)를 A층 주모델**로 확정하고 B층 착수 — 저산소역 영역 IoU 0.72·무게중심 7mm면 계기판 포지션엔 실용 가능.

## 4. 성공 기준 (POD+RF 대비)

CNN이 아래를 달성하면 A층 주모델로 승격:

- **anomL2 < 0.612** (RF 이김), 목표는 ceiling 0.293 접근.
- **IoU_med > 0.718** 및 **IoU_min > 0.20**(최악케이스 개선 = RF의 미해결점).
- cdist_med < 7.2mm.

미달 시: (a) 데이터 부족이면 Tier3 보충 후 재학습, (b) 구조 문제면 U-Net/증강 검토. 어느 쪽이든 **POD+RF가 안전한 폴백**.
