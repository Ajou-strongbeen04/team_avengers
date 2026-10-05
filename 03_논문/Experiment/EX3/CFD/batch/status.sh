#!/bin/bash
# 진행률 확인 (Cloud Shell). done/failed 마커 집계 + 누적 ClockTime.
set -uo pipefail
BUCKET="${BUCKET:-cfd-trainingdata-cfdbatch}"
done=$(gsutil ls "gs://${BUCKET}/done/" 2>/dev/null | grep -c '\.done' || echo 0)
fail=$(gsutil ls "gs://${BUCKET}/failed/" 2>/dev/null | grep -c '\.fail' || echo 0)
raw=$(gsutil ls "gs://${BUCKET}/raw/" 2>/dev/null | grep -c '\.tgz' || echo 0)
echo "완료(done): ${done} / 700    실패(fail): ${fail}    원시업로드(raw): ${raw}"
echo "실패 목록:"; gsutil ls "gs://${BUCKET}/failed/" 2>/dev/null | sed 's#.*/##' | head
