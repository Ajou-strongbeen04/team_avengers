#!/bin/bash
# 선점되어 STOP 된 워커를 다시 start (Cloud Shell). start 시 startup-script 재실행→미완만 이어감.
# 주기 실행 권장(예: watch -n 900 'bash batch/resume.sh'  또는 스케줄).
set -uo pipefail
PROJECT="${PROJECT:-cfd-pilot}"; NW="${NW:-6}"
# 선택된 존: workers.env 우선(create_workers 가 기록), 없으면 ZONE 환경변수/기본값
_ENVF="$(cd "$(dirname "$0")" && pwd)/workers.env"
[ -f "$_ENVF" ] && ZONE="$(sed -n 's/^ZONE=//p' "$_ENVF")"
ZONE="${ZONE:-us-central1-a}"
for i in $(seq 0 $((NW-1))); do
  st=$(gcloud compute instances describe "worker-${i}" --project="$PROJECT" --zone="$ZONE" \
        --format='value(status)' 2>/dev/null || echo MISSING)
  if [ "$st" = "TERMINATED" ] || [ "$st" = "STOPPING" ]; then
    echo "worker-${i}: $st → start"
    gcloud compute instances start "worker-${i}" --project="$PROJECT" --zone="$ZONE" || true
  else
    echo "worker-${i}: $st"
  fi
done
