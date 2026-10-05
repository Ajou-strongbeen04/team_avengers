#!/bin/bash
# ============================================================================
#  漁벤져스 · 파일럿 로그 회수 + VM 삭제(과금 중지)
#  (로컬 PowerShell/Cloud Shell 에서 실행)
# ============================================================================
set -euo pipefail

PROJECT="${PROJECT:?PROJECT 환경변수 필요}"
VM="${VM:-of-pilot}"
ZONE="${ZONE:-us-central1-a}"
OUT="${OUT:-./pilot_result}"

mkdir -p "$OUT"
echo "== 로그/타이밍 회수 =="
gcloud compute scp --project="$PROJECT" --zone="$ZONE" \
  "$VM:~/case0000_gcp/log.pimpleFoam"     "$OUT/" || true
gcloud compute scp --project="$PROJECT" --zone="$ZONE" \
  "$VM:~/pilot_summary.txt"               "$OUT/" || true

echo "== VM 삭제 (★과금 중지) =="
gcloud compute instances delete "$VM" --project="$PROJECT" --zone="$ZONE" --quiet

echo "완료. 결과: $OUT/  (log.pimpleFoam, pilot_summary.txt)"
