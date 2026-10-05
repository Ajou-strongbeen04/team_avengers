# GCP_v2 실행 런북 (cfd-rom 계정 · 179케이스)

> 팀 漁벤져스 · 2026-07-24 · 새 계정 `cfd-rom` 재셋업
> 생성 대상 = 남은 Tier2 127 + Tier3 52 = **179** (`gen179.txt`). 기존 253과 규격 완전 정합(불변).
> 후속 = 회수 → 재인코딩 → CNN/POD 재학습 (`../07_TIER3_실행.md` 참조)

## 0. 사전 (한 번만)

- Cloud Shell에서 프로젝트가 `cfd-rom`인지: `gcloud config get-value project` → 아니면 `gcloud config set project cfd-rom`.
- **결제 연결 필수**(새 계정): Console → 결제 → cfd-rom에 결제 계정 연결. 안 되면 Compute API가 막힘.
- Compute Engine 할당량: **신규 계정 = 32 vCPU(상향 막힘).** → 기본 **`c2d-highcpu-16 × 2 = 32`(NW=2)** 로 설정됨. 그대로 실행하면 됨.
  - (선택) 더 빠른 처리량: 같은 32 quota로 **`MACHINE=c2d-highcpu-8 NW=4`**(4케이스 동시, 코어당 부하↑). 248k셀 메시엔 8코어도 충분해 총 처리량이 대개 더 높음. 원하면 이 조합으로.

## 1. GCP_v2 폴더를 Cloud Shell로 올리기

로컬 `...\EX3\GCP_v2\` 전체를 Cloud Shell에. 방법 택1:

- **드래그업로드**: Cloud Shell 우상단 ⋮ → "업로드" → GCP_v2 폴더(zip 권장) 올리고 `unzip`.
- **gcloud scp/rsync** 또는 git repo 경유.

Cloud Shell에서 폴더 진입:
```bash
cd ~/GCP_v2      # 업로드한 위치
ls               # cases.csv gen179.txt gen_cases.py batch/ template_case/ 확인
```

## 2. 워커 생성 (버킷·번들·6대 Spot)

```bash
bash batch/create_workers.sh
```
- 자동으로: `cfd-rom-cfdbatch` 버킷 생성 → 번들(cases.csv·gen179.txt·worker.sh·template) 업로드 → 재고 있는 존에 **worker-0,1 생성(Spot, 기본 NW=2)**.
- 처리량 우선이면: `MACHINE=c2d-highcpu-8 NW=4 bash batch/create_workers.sh` (같은 32 quota, 4대).
- 각 VM은 startup에서 OpenFOAM 설치 → 케이스 전개 → **gen179 목록만** 자기 샤드(`idx % NW == shard`) 실행.
- ⚠️ 32 quota에 딱 맞으므로, 다른 VM이 떠 있으면 worker-1이 quota초과로 실패할 수 있음. 그땐 `bash batch/create_workers.sh` 재실행(빠진 것만 채움) 또는 기존 VM 정리.

## 3. 모니터링

```bash
bash batch/status.sh
```
`완료(done): N / 179`. 워커 상태·실패목록도 표시. 몇 분 간격으로 확인.

## 4. Spot 선점 복구 (선점되면 STOP됨)

```bash
bash batch/resume.sh          # 멈춘 워커 재시작(startup이 미완만 이어감)
```
자주 끊기면 워치독 자동화: `bash batch/create_watchdog.sh` (주기적으로 resume 실행하는 VM 1대).

## 5. 완료 후 결과 회수 (→ 로컬)

179개 done 확인되면, 원시 tgz를 로컬 `dataset/result/`로:
```bash
# Cloud Shell에서 로컬로 직접은 불가 → 로컬 PowerShell에서:
gsutil -m cp gs://cfd-rom-cfdbatch/raw/*.tgz "C:\rom_raw_v2\"
# 각 tgz 풀어서 dataset/result/caseXXXX/ 로 배치(기존 253과 동일 위치)
```
(로컬에서 tar 해제: `tar xzf caseXXXX.tgz -C dataset/result/caseXXXX/` — 또는 기존 회수 스크립트 재사용.)

## 6. 정리 (비용 정지)

```bash
bash batch/teardown.sh        # 워커 VM 전부 삭제 (버킷·결과는 유지)
```

## 7. 다음 (ROM 재학습)

`../07_TIER3_실행.md` §"생성 후" 그대로:
1. `resample_encode.py --skip-existing`로 신규만 인코딩(253→432).
2. **test_split 10 동결 유지**, 신규 179는 train_val에만 추가.
3. `rom_cnn.py --pool 1 --energy 0.9` + `rom_pod.py` 재실행 → 동일 test10 비교. **바위 케이스 IoU 개선폭이 판정.**

## 비용 개산

179 × Spot ₩500 ≈ **₩90,000** (온디맨드면 ₩250k). 유료 계정이니 결제 확인 필수.
teardown 잊으면 유휴 VM 과금 → 완료 후 반드시 6번 실행.

---
**변경 요약(GCP → GCP_v2):** PROJECT `cfd-pilot`→`cfd-rom`, 버킷 `cfd-rom-cfdbatch`, MAXIDX 379→699, 워커=케이스-리스트판(`gen179.txt` 179만), status TARGET 179. 그 외 인프라(Spot·샤드·존탐색·재개) 동일.
