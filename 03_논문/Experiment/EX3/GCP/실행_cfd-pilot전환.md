# cfd-trainingdata 정리 → cfd-pilot에서 클린 재시작 (漁벤져스)

**왜:** 96 vCPU 선점 쿼터는 `cfd-pilot`에 걸려 있는데 배치는 `cfd-trainingdata`에서 돌아 엮임.
→ cfd-trainingdata 워커 **전량 삭제**, 완료분(done/raw)은 **cfd-pilot 새 버킷으로 복사해 이어감**,
   이후 배치는 전부 `cfd-pilot`에서 6대(96 vCPU)로 운영.

- 완료 데이터 이관 → **재계산 0**. 남은 케이스만 6대로 처리.
- 크로스 프로젝트 복사지만 둘 다 us-central1 → egress 비용 없음(같은 계정이면 권한 OK).
- 스크립트 기본값은 이미 `cfd-pilot` / `cfd-pilot-cfdbatch`로 갱신됨.
- ⚠️ Cloud Shell의 `GCP/` 사본은 예전 것(create_workers.sh가 40줄에서 잘림)이므로 **이 폴더를 다시 업로드**.

---

## 0. 사전 확인 (Cloud Shell)
```bash
gcloud projects list --format="value(projectId)" | grep -E 'cfd-pilot|cfd-trainingdata'
# cfd-pilot의 선점 vCPU 쿼터 ≥ 96 확인 (IAM & Admin → Quotas → us-central1 'Preemptible CPUs')
gcloud compute regions describe us-central1 --project=cfd-pilot \
  --format="table(quotas.metric,quotas.limit,quotas.usage)" | grep -i preempt
```

## 1. cfd-trainingdata 워커 전량 삭제 (★과금 중지)
```bash
# 먼저 무엇이 도는지 확인 (존 포함)
gcloud compute instances list --project=cfd-trainingdata \
  --filter="name~^worker-" --format="table(name,zone,status)"

# 목록의 존이 us-central1-a라면(다르면 --zone 수정):
NAMES=$(gcloud compute instances list --project=cfd-trainingdata \
  --filter="name~^worker-" --format="value(name)")
gcloud compute instances delete $NAMES \
  --project=cfd-trainingdata --zone=us-central1-a --quiet
```
> 여러 존에 흩어져 있으면 존별로 나눠 delete. 파일럿 인스턴스 `of-pilot`가 cfd-pilot에 남아있으면
> `gcloud compute instances delete of-pilot --project=cfd-pilot --zone=us-central1-a --quiet`.

## 2. cfd-pilot 새 버킷 생성 + 완료데이터 복사 (재계산 스킵의 핵심)
```bash
gsutil ls -b gs://cfd-pilot-cfdbatch >/dev/null 2>&1 \
  || gsutil mb -p cfd-pilot -l us-central1 gs://cfd-pilot-cfdbatch

# done 마커(=완료 판정) + raw 평균필드(=실제 결과) 만 복사. failed/bundle은 복사 불필요.
gsutil -m rsync -r gs://cfd-trainingdata-cfdbatch/done gs://cfd-pilot-cfdbatch/done
gsutil -m rsync -r gs://cfd-trainingdata-cfdbatch/raw  gs://cfd-pilot-cfdbatch/raw

# 복사 검증(개수 일치 확인)
echo "src done:"; gsutil ls gs://cfd-trainingdata-cfdbatch/done/ | grep -c '\.done'
echo "dst done:"; gsutil ls gs://cfd-pilot-cfdbatch/done/       | grep -c '\.done'
```

## 3. cfd-pilot에서 6대 생성 + 자동 시작
```bash
# GCP/ 폴더(복구본) 재업로드 후:
cd ~/GCP
export PROJECT=cfd-pilot REGION=us-central1
export BUCKET=cfd-pilot-cfdbatch
export NW=6
rm -f batch/workers.env         # 옛 존 기록 있으면 초기화(새로 탐색)
bash batch/create_workers.sh
```
→ worker-0~5 Spot 생성. 각 VM이 OpenFOAM 설치 → 케이스 전개 → 자기 샤드(idx%%6) 실행.
   버킷에 이미 있는 done 마커 케이스는 **스킵** → 남은 것만 계산.

## 4. 확인 + 선점 자동복구
```bash
BUCKET=$BUCKET bash batch/status.sh
gcloud compute instances list --project=$PROJECT --filter="name~worker-" --format="table(name,zone,status)"
ZONE=$(sed -n 's/^ZONE=//p' batch/workers.env)
watch -n 900 "PROJECT=$PROJECT ZONE=$ZONE NW=6 bash batch/resume.sh"
```

## 5. 완료 후
```bash
BUCKET=$BUCKET bash batch/status.sh                 # done=700 확인
NW=6 bash batch/teardown.sh                          # cfd-pilot 워커 6대 삭제(버킷 보존)

# cfd-pilot 실행이 정상 확인되면, 옛 버킷 정리(선택):
# gsutil -m rm -r gs://cfd-trainingdata-cfdbatch
```

---

## 기간·비용
- 남은 케이스 / 6슬롯 × 2.04h. 완료분이 N개면 (700−N)/6×2.04h.
  (예: 완료 120 → 남은 580 → 임계경로 ≈ 97케이스 ×2.04h ≈ 198h ≈ **8.2일**)
- 비용: 남은 연산량 기준. 6대든 9대든 총 core-hour 동일이라 대수는 기간만 좌우.

## 주의
- 배치 스크립트 기본값·`dataset/GCP_VM/_config.*` 는 cfd-pilot로 갱신됨. 옛 프로젝트를 다룰 땐
  명령에 `PROJECT=cfd-trainingdata` 를 **명시**해야 함(1번 단계).
- `dataset/GCP_VM/`의 worker-6~8 `.bat` 런처는 6대 체제에선 미사용(무시).
