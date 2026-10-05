# 07 · Tier3 보충 생성 실행 가이드

> 팀 漁벤져스 · 2026-07-24 · 근거 `06_ROM_Stage2B_CNN.md`(데이터 병목 확정)
> 선별 `dataset/training_dataset/tier3_selection.csv`(52) · 케이스ID `GCP/tier3_ids.txt` · 워커 `GCP/batch/worker_tier3.sh`

## 왜 이 52케이스인가

Stage2-B에서 **CNN이 바위 후류 저산소역에서 실패**(IoU 0.19~0.45), 데이터 병목 확정.
따라서 실패 구성을 정조준해 tier3(320) 중 **바위·조밀·고차단** 편향으로 52를 선별:

- n=3/4/5/6 각 13 균등
- 바위 우세 49/52, all-rock 12
- blockage 중앙 0.082(설계 0.064보다 높게), 최대 0.148 — 0141형(대형바위·고차단) 포함
- cases.csv 인덱스 385~698 중 52개(흩어짐)

## GCP 실행 (기존 파일럿 셋업 재사용)

기존 batch는 `MAXIDX`로 tier 게이트(0~379=Tier0-2). Tier3는 흩어진 부분집합이라
**케이스-리스트 워커**(`worker_tier3.sh`)로 목록만 실행한다. 나머지 인프라(Spot·샤드·done마커·재개)는 동일.

1. **케이스ID 업로드** — `GCP/tier3_ids.txt`(52줄)를 각 워커 VM의 `/opt/cfd/flow/tier3_ids.txt`로.
   (startup.sh의 gen_cases.py가 700케이스 전부 생성하므로 디렉터리는 이미 존재. 리스트로 실행만 거른다.)
2. **워커 교체** — `worker.sh` 대신 `worker_tier3.sh` 사용(startup.sh의 `CFD/batch/worker.sh` → `local_T3/worker_tier3.sh`(⟨후속 생성⟩)).
3. **환경변수**:
   - `MAXIDX=699` (Tier3 게이트 통과; 메타데이터 `maxidx=699`)
   - `CASELIST=/opt/cfd/flow/tier3_ids.txt`
   - `END=200` (평균창 통일 — 기존과 동일, 절대 변경 금지)
4. **실행·모니터** — 기존 `status.sh`로 done/failed 집계. 52개 done마커 확인.
5. **회수** — `gs://BUCKET/raw/caseXXXX.tgz` 52개 → 로컬 `dataset/result/`에 병합(기존 253과 같은 위치).

> 규격 불변: blockMesh 108×48×48, 폭기 (0.02,0.035)·r10mm, endTime200·tAvg40-200. tier3_ids만 추가 생성이라 기존 253과 완전 정합.

## 생성 후 (ROM 재학습)

1. **재인코딩**: `python scripts\resample_encode.py --result-dir dataset\result --out-dir C:\rom_npz --skip-existing`
   (기존 253 스킵, 신규 52만 추가 → 305 npz)
2. **분할 갱신**: 기존 test10 유지(공정 비교). 신규 52는 전부 train으로. `test_split.json`은 그대로 두고 train_val에 52 추가되게 재생성하거나, 수동 병합.
   > 주의: test_split은 **동결**이 원칙. 신규 케이스는 train_val에만 넣어 test10 불변 유지.
3. **재학습**: `python scripts\rom_cnn.py --fields-dir C:\rom_npz\fields --split <갱신split> --pool 1 --energy 0.9 --out ...\cnn_results_t3.json`
   그리고 POD+RF도 `rom_pod.py`로 재실행 → 동일 test10에서 비교.
4. **판정**: 바위 케이스(0031·0141·0158·0204) IoU 개선이 핵심 지표. 개선되면 CNN 채택, 미미하면 POD+RF 확정 후 B층.

## 비용 메모

52케이스 × 케이스당 clock(파일럿 기록 참조) — Spot으로 단가 ~1/3. 전량 320(불필요) 대비 6배 절감.
학습곡선 미포화가 근거이므로, 52 반영 후에도 미포화면 추가 배치 검토(그때 다시 학습곡선).
