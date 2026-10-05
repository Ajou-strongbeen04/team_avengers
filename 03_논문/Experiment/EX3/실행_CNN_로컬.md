# CNN 로컬 GPU 실행 퀵스타트 (Stage 2-B)

> 대상: 김강빈 로컬 PC (CUDA GPU). 상세 배경 `06_ROM_Stage2B_CNN.md`.
> 작업 폴더 = `...\EX3\` (아래 명령은 이 폴더에서 실행)

## 0. 준비 확인

- Python 3.10+, `numpy pandas pyarrow scikit-learn` 설치돼 있어야 함(POD·평가용).
  `pip install numpy pandas pyarrow scikit-learn`
- GPU/CUDA 버전 확인: `nvidia-smi` (오른쪽 위 CUDA Version 확인).

## 1. torch 설치 (GPU)

CUDA 12.x 기준:
```
pip install torch --index-url https://download.pytorch.org/whl/cu121
```
확인: `python -c "import torch; print(torch.cuda.is_available())"` → `True` 여야 함.
(GPU 인식 안 되면 CPU로도 돌지만 느림 → `--pool 2` 권장.)

## 2. npz 데이터 재생성 (약 2.5분, 887MB)

CFD 결과(253케이스) → 정렬 텐서. 출력은 **OneDrive 밖 로컬 스크래치**(예 `C:\rom_npz`)로 — 동기화 부하 회피.
```
python scripts\resample_encode.py --result-dir dataset\result --out-dir C:\rom_npz --skip-existing
```
- `dataset\result` 대신 로컬 `C:\cfd_raw`(더 빠름)를 써도 됨: `--result-dir C:\cfd_raw`.
- 완료 후 `C:\rom_npz\fields\`에 case0000~0260.npz 253개 생성.

## 3. CNN 학습·평가

> **PowerShell 주의:** 줄바꿈 기호 `^`(cmd용)는 PowerShell에서 안 됨 → **한 줄로** 실행할 것.

```powershell
python scripts\rom_cnn.py --fields-dir C:\rom_npz\fields --split dataset\training_dataset\test_split.json --pool 1 --epochs 300 --out dataset\training_dataset\cnn_results.json
```
(여러 줄로 쓰려면 PowerShell은 각 줄 끝에 백틱 `` ` `` 사용)
- `--pool 1` = native 108×48×48(GPU 권장). GPU 메모리 부족·CPU면 `--pool 2`(POD+RF와 동일 격자, 직접비교 가능).
- 진행 중 `ep N val_mse=...` 출력. 조기종료(early stop) 있음. 수 분~수십 분(GPU 사양·pool에 따라).
- 산출: `cnn_results.json`(지표), `rom_cnn.pt`(가중치).

## 4. 결과 해석 — POD+RF 대비 성공 기준

스크립트 끝에 자동 출력됨. 아래를 넘으면 CNN이 A층 주모델:

| 지표 | POD+RF(폴백) | ceiling(상한) | CNN 목표 |
|---|---|---|---|
| anomL2_med | 0.612 | 0.293 | **< 0.612** |
| IoU_med | 0.718 | 0.861 | **> 0.718** |
| IoU_min | 0.197 | 0.494 | **> 0.20** (최악케이스 개선) |
| cdist_mm_med | 7.2 | 2.7 | **< 7.2** |

> `--pool 2`로 돌리면 위 POD+RF 수치와 **같은 격자**라 1:1 비교. `--pool 1`(native)이면 절대치는 다르지만 경향으로 판단.

## 5. 다음

- `cnn_results.json` 을 나한테 보내주면 per-case로 같이 분석(어떤 배치가 안 맞는지 → 데이터 부족인지 구조 문제인지 판정).
- CNN이 목표 미달·불안정 → 학습곡선 미포화가 근거이므로 **Tier3 40~60 층화 추가 생성** 후 재학습.
- 잘 나오면 → B층(동결 유동장 위 DO 이송확산) 착수.

## 트러블슈팅

- `CUDA out of memory` → `--pool 2` 또는 `--batch 8`.
- `No module named torch` → 1단계 재확인(가상환경 쓰면 그 환경에서 설치).
- npz 재생성이 느림 → `--result-dir C:\cfd_raw`(로컬 디스크) 사용.
- 파이프라인 자체는 검증됨(참 POD계수 주입 시 ceiling 0.293/0.861/2.7 재현). 이상수치면 데이터 경로부터 확인.
