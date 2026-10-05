#!/bin/bash
# ============================================================================
#  漁벤져스 · 본 배치 워커 9대 생성 (Cloud Shell). CFD/ 안에서 실행.
#  - 버킷 생성 + 번들 업로드
#  - 재고(stockout) 대응: 여러 존을 자동 탐색해 '한 존'에 전량 배치
#  - 멱등: 이미 있는 워커는 건너뛰고, 빠진 것만 채움(재실행으로 gap-fill)
#  선택된 존은 batch/workers.env 에 기록(resume/status/런처가 참조).
# ============================================================================
set -uo pipefail

PROJECT="${PROJECT:-cfd-trainingdata}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-${PROJECT}-cfdbatch}"
MACHINE="${MACHINE:-c2d-highcpu-16}"
NW="${NW:-9}"
# 탐색할 존 후보(재고 있는 첫 존에 전량 배치)
ZONES="${ZONES:-us-central1-a us-central1-b us-central1-c us-central1-f us-east1-b us-east1-c us-east1-d us-west1-a}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ENVF="$HERE/batch/workers.env"

echo "== 프로젝트: $PROJECT / 버킷: gs://$BUCKET / 머신: $MACHINE =="
echo "== Compute/Storage API 활성(이미 켜졌으면 즉시 통과) =="
gcloud services enable compute.googleapis.com storage.googleapis.com --project="$PROJECT"

echo "== 버킷 생성(있으면 통과) =="
gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1 || gsutil mb -p "$PROJECT" -l "$REGION" "gs://${BUCKET}"

echo "== 번들 조립·업로드 =="
BUN="$(mktemp -d)/bundle"; mkdir -p "$BUN"
cp "$HERE/cases.csv" "$HERE/gen_cases.py" "$HERE/batch/worker.sh" "$BUN/"
cp "$HERE/batch/postprocess.py" "$HERE/pilot/grid_spec.json" "$BUN/" 2>/dev/null || true
cp -r "$HERE/pilot/template_case" "$BUN/template_case"
gsutil -m rsync -r -d "$BUN" "gs://${BUCKET}/bundle"

create_one() {  # $1=zone $2=name  → 성공 0 / 실패 비0
  gcloud compute instances create "$2" \
    --project="$PROJECT" --zone="$1" --machine-type="$MACHINE" \
    --provisioning-model=SPOT --instance-termination-action=STOP \
    --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB --boot-disk-type=pd-balanced --scopes=cloud-platform \
    --metadata=bucket="${BUCKET}",shard="${2##*-}",nworkers="${NW}" \
    --metadata-from-file=startup-script="$HERE/batch/startup.sh" >/dev/null 2>"/tmp/err_$2"
}
exists() { gcloud compute instances describe "$1" --project="$PROJECT" --zone="$2" >/dev/null 2>&1; }

# ---- 존 결정: workers.env 있으면 그 존, 없으면 worker-0로 재고 있는 존 탐색 ----
CHOSEN=""
[ -f "$ENVF" ] && CHOSEN="$(sed -n 's/^ZONE=//p' "$ENVF")"
if [ -n "$CHOSEN" ] && exists worker-0 "$CHOSEN"; then
  echo "== 기존 존 재사용: $CHOSEN =="
else
  echo "== 재고 있는 존 탐색(worker-0) =="
  for z in $ZONES; do
    printf "  %s ... " "$z"
    if exists worker-0 "$z"; then CHOSEN="$z"; echo "이미 있음"; break; fi
    if create_one "$z" worker-0; then CHOSEN="$z"; echo "OK"; break
    else echo "재고없음"; fi
  done
fi
[ -z "$CHOSEN" ] && { echo "!! 모든 후보 존에서 stockout. 잠시 후 재실행하거나 MACHINE=c2d-standard-16 로 재시도"; exit 1; }
echo "ZONE=$CHOSEN" > "$ENVF"

echo "== 나머지 워커 생성(빠진 것만) in $CHOSEN =="
fail=0
for i in $(seq 1 $((NW-1))); do
  if exists "worker-$i" "$CHOSEN"; then echo "  worker-$i 이미 있음"; continue; fi
  if create_one "$CHOSEN" "worker-$i"; then echo "  worker-$i OK"
  else echo "  worker-$i 실패: $(tail -1 /tmp/err_worker-$i)"; fail=1; fi
done

echo ""; echo "==================== 요약 ===================="
gcloud compute instances list --project="$PROJECT" --filter="name~worker-" --format="table(name,zone,status)"
echo "선택 존: $CHOSEN  (→ dataset/GCP_VM/_config.bat·_config.sh 의 ZONE 을 이걸로 맞추세요)"
[ "$fail" = "1" ] && echo "일부 실패(재고). 잠시 후 'bash batch/create_workers.sh' 재실행하면 빠진 것만 채웁니다."
echo "진행확인: BUCKET=$BUCKET bash batch/status.sh"
echo "선점복구: PROJECT=$PROJECT ZONE=$CHOSEN NW=$NW bash batch/resume.sh"
