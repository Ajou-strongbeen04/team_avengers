#!/bin/bash
# 워커 전량 삭제(★과금 중지). 버킷(raw/done/dataset)은 유지 — 데이터 보존.
# 버킷까지 지우려면: DELETE_BUCKET=1
set -uo pipefail
PROJECT="${PROJECT:-cfd-trainingdata}"; ZONE="${ZONE:-us-central1-a}"; NW="${NW:-9}"
BUCKET="${BUCKET:-cfd-trainingdata-cfdbatch}"
names=""; for i in $(seq 0 $((NW-1))); do names="$names worker-${i}"; done
echo "삭제: $names"
gcloud compute instances delete $names --project="$PROJECT" --zone="$ZONE" --quiet || true
if [ "${DELETE_BUCKET:-0}" = "1" ]; then
  echo "버킷 삭제: gs://${BUCKET}"; gsutil -m rm -r "gs://${BUCKET}" || true
else
  echo "버킷 유지: gs://${BUCKET} (원시·데이터 보존). 지우려면 DELETE_BUCKET=1"
fi
