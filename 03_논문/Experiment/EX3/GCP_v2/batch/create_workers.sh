#!/bin/bash
# ============================================================================
#  漁벤져스 · 워커 생성 (GCP_v2 / cfd-rom 계정) — Cloud Shell, GCP_v2/ 안에서 실행.
#  기존 파일럿과 동일 로직. 차이: PROJECT=cfd-rom 기본, MAXIDX=699, 번들에 gen179.txt,
#  worker=케이스-리스트판(179만). 버킷 생성·번들 업로드·존 탐색·멱등 gap-fill 동일.
# ============================================================================
set -uo pipefail

PROJECT="${PROJECT:-cfd-rom}"                 # ★ 새 계정
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-${PROJECT}-cfdbatch}"       # gs://cfd-rom-cfdbatch
MACHINE="${MACHINE:-c2d-highcpu-16}"
# 신규 계정 할당량 CPUS=32(상향 막힘) → c2d-highcpu-16 × 2 = 32 딱 맞음.
NW="${NW:-2}"
ENDTIME="${ENDTIME:-200}"                     # 평균창 통일(기존 253과 정합) — 변경 금지
MAXIDX="${MAXIDX:-699}"                       # ★ Tier3 포함
PROVISION="${PROVISION:-SPOT}"                # 할인. 선점 시 resume.sh 필요
if [ "$PROVISION" = "SPOT" ]; then
  PROV_FLAGS="--provisioning-model=SPOT --instance-termination-action=STOP"
else
  PROV_FLAGS="--provisioning-model=STANDARD"
fi
ZONES="${ZONES:-us-central1-a us-central1-b us-central1-c us-central1-f us-east1-b us-east1-c us-east1-d us-west1-a}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ENVF="$HERE/batch/workers.env"

echo "== 프로젝트: $PROJECT / 버킷: gs://$BUCKET / 머신: $MACHINE / NW=$NW / $PROVISION / MAXIDX=$MAXIDX =="
gcloud config set project "$PROJECT" >/dev/null 2>&1 || true
echo "== Compute/Storage API 활성 =="
gcloud services enable compute.googleapis.com storage.googleapis.com --project="$PROJECT"

echo "== 버킷 생성(있으면 통과) =="
gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1 || gsutil mb -p "$PROJECT" -l "$REGION" "gs://${BUCKET}"

echo "== 번들 조립·업로드 (gen179.txt 포함) =="
BUN="$(mktemp -d)/bundle"; mkdir -p "$BUN"
cp "$HERE/cases.csv" "$HERE/gen_cases.py" "$HERE/gen179.txt" "$HERE/batch/worker.sh" "$BUN/"
cp "$HERE/batch/postprocess.py" "$HERE/grid_spec.json" "$BUN/" 2>/dev/null || true
cp -r "$HERE/template_case" "$BUN/template_case"
gsutil -m rsync -r -d "$BUN" "gs://${BUCKET}/bundle"

create_one() {
  gcloud compute instances create "$2" \
    --project="$PROJECT" --zone="$1" --machine-type="$MACHINE" \
    $PROV_FLAGS \
    --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB --boot-disk-type=pd-balanced --scopes=cloud-platform \
    --metadata=bucket="${BUCKET}",shard="${2##*-}",nworkers="${NW}",endtime="${ENDTIME}",maxidx="${MAXIDX}" \
    --metadata-from-file=startup-script="$HERE/batch/startup.sh" >/dev/null 2>"/tmp/err_$2"
}
exists() { gcloud compute instances describe "$1" --project="$PROJECT" --zone="$2" >/dev/null 2>&1; }

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
[ -z "$CHOSEN" ] && { echo "!! 전 존 stockout. 잠시 후 재실행 또는 MACHINE=c2d-standard-16"; exit 1; }
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
echo "선택 존: $CHOSEN"
[ "$fail" = "1" ] && echo "일부 실패(재고). 잠시 후 재실행하면 빠진 것만 채웁니다."
echo "진행확인: PROJECT=$PROJECT BUCKET=$BUCKET bash batch/status.sh"
echo "선점복구: PROJECT=$PROJECT ZONE=$CHOSEN NW=$NW bash batch/resume.sh"
