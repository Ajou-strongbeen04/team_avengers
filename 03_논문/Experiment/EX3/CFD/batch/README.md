# 본 배치 실행 — 700 케이스 GCP 분산 (漁벤져스 / 9× Spot)

파일럿(단일 VM)과 달리 **9대 Spot 워커가 정적 샤딩으로 병렬**. 케이스 index %% 9 로 담당을 나눠
서로 겹치지 않게 돌고, 완료는 GCS 마커로 표시 → **선점(STOP)돼도 start 시 미완만 이어감**.

- 구성: `c2d-highcpu-16` Spot ×9 (각 8코어=1슬롯). 실측 f≈0.98 유지, 케이스당 ≈2.04h.
- 예상: 700×2.04h / 9슬롯 ≈ **6.6일**, 비용 ≈ **228 USD**(Spot 0.010 USD/vCPU-hr) → 300 USD 내.
- 좌표계·저장: 원시 평균필드는 `gs://BUCKET/raw/`에 보관, 리샘플 데이터셋은 후처리에서 생성.

전제: 파일럿과 같은 프로젝트 `cfd-pilot`, 리전 us-central1. **CFD/ 폴더가 통째로 Cloud Shell에 있어야 함**
(`cases.csv`, `gen_cases.py`, `pilot/template_case`, `../../GCP/grid_spec.json`, `batch/`).

---

## 0. 준비 (Cloud Shell)
```bash
# CFD 폴더 업로드(⋮→Upload→Folder) 후 그 안에서:
cd ~/CFD          # cases.csv, gen_cases.py, pilot/, batch/ 가 보이는 위치
export PROJECT=cfd-trainingdata ZONE=us-central1-a REGION=us-central1
export BUCKET=cfd-trainingdata-cfdbatch   # ★전역 유일. 충돌 시 뒤에 숫자 추가
export NW=9
# 선점 vCPU 쿼터 ≥ 144 필요 — IAM&Admin→Quotas 에서 us-central1 'Preemptible CPUs' 확인/상향
```

## 1. 워커 9대 생성 + 자동 시작
```bash
bash batch/create_workers.sh
```
버킷 생성 → 번들 업로드 → worker-0..8 Spot 생성. 각 VM은 startup-script로 **OpenFOAM 설치 →
케이스 전개 → 자기 샤드 자동 실행**. 접속·수동설치 불필요.

## 2. 진행 확인 (수시)
```bash
BUCKET=$BUCKET bash batch/status.sh          # done/700, 실패, 원시 업로드 수
# 특정 워커 로그 보기(선택):
gcloud compute ssh worker-0 --zone=$ZONE --command='tail -n 20 /var/log/cfd_worker.log'
```

## 3. 선점 복구 (배치 도는 동안 주기적)
```bash
bash batch/resume.sh          # STOP 된 워커 start → 미완만 이어감
# 자동화: Cloud Shell에서  watch -n 900 'bash batch/resume.sh'  (15분마다)
```
> Spot은 선점되면 STOP 된다. resume가 다시 켜면 startup-script가 재실행되어 완료마커 없는
> 케이스만 이어 돈다(중복 계산 없음). 방치해도 데이터는 안전, 다만 진행이 멈추니 주기 실행 권장.

## 4. 완료 후 데이터 회수 + 워커 삭제(★과금 중지)
```bash
BUCKET=$BUCKET bash batch/status.sh          # done=700 확인
bash batch/teardown.sh                        # 워커 9대 삭제(버킷=원시데이터 보존)
```
실패 케이스가 있으면 `resume` 한 번 더 돌려 재시도(완료마커 없으니 자동 재실행).

## 5. 후처리 — 리샘플 데이터셋 생성 (배치와 분리, 언제든 재실행)
원시필드는 버킷에 있으므로 CFD 재계산 없이 리샘플만 조정 가능.
```bash
pip install --break-system-packages pyvista numpy
mkdir raw && gsutil -m cp "gs://$BUCKET/raw/*.tgz" raw/
python3 batch/postprocess.py --raw raw --grid pilot/grid_spec.json --csv cases.csv --out dataset
gsutil -m cp dataset/*.npz "gs://$BUCKET/dataset/"      # (선택) 데이터셋도 버킷 보관
```
→ `dataset/case####.npz` : UMean·nutMean·kMean·omegaMean·pMean(96×48×48) + 구조물 마스크(occ/kind)
   + 라벨(case_id·blockage·obstacles). 이게 POD ROM 학습 입력.

---

## 동작·복원력 요약
- **정적 샤딩**: case index %% 9 → 워커 담당 고정, 상호 배타 → 분산 락 불필요.
- **재개**: `gs://BUCKET/done/{case}.done` 있으면 스킵. 선점·재시작에 안전(멱등).
- **성공 판정**: `log.pimpleFoam` 끝 `End` 또는 시간 200 디렉터리. 실패는 `failed/`에 기록.
- **루트 실행**: startup은 root라 `OMPI_ALLOW_RUN_AS_ROOT=1` 로 mpirun 허용(worker.sh).
- **디스크**: 케이스마다 Allclean으로 회수(50GB로 충분).

## 함정(파일럿 런북 계승, RUNBOOK_실전기록.md)
Cloud Shell≠VM · Spot 선점 → resume 필요 · OpenFOAM bashrc는 엄격모드 밖 소싱 ·
버킷명 전역유일 · 선점 vCPU 쿼터 상향.
