#!/bin/bash
# 진행률 확인 (Cloud Shell). done/failed 마커 집계 + 누적 ClockTime.
set -uo pipefail
BUCKET="${BUCKET:-cfd-rom-cfdbatch}"   # ★ GCP_v2 / cfd-rom
TARGET="${TARGET:-179}"   # 이번 배치 = 남은 Tier2 127 + Tier3 52 = 179 (gen179.txt)
# ※ grep -c 는 0건일 때 "0"을 출력하면서 exit 1 → `|| echo 0` 을 붙이면 0이 두 번 찍힌다
#   (2026-07-20 수정. 이전 출력의 "실패(fail): 0 / 0 원시업로드..." 줄바꿈 원인)
count() { gsutil ls "$1" 2>/dev/null | grep -c "$2"; }
done=$(count "gs://${BUCKET}/done/"   '\.done')
fail=$(count "gs://${BUCKET}/failed/" '\.fail')
raw=$( count "gs://${BUCKET}/raw/"    '\.tgz')
echo "완료(done): ${done} / ${TARGET} (Tier2잔여+Tier3)   실패(fail): ${fail}   원시업로드(raw): ${raw}"
# Spot 단가 ₩500/케이스(=온디맨드 실측 ₩1,407 × 0.36) 기준 잔여비용 개산
rem=$(( TARGET - done )); [ "$rem" -lt 0 ] && rem=0
echo "잔여 ${rem}건 · Spot 개산 ₩$(( rem * 500 ))  (온디맨드였다면 ₩$(( rem * 1407 )))"
echo "워커 상태:"; gcloud compute instances list --filter="name~worker-" \
  --format="table(name,zone,status,scheduling.provisioningModel)" 2>/dev/null
echo "실패 목록:"; gsutil ls "gs://${BUCKET}/failed/" 2>/dev/null | sed 's#.*/##' 