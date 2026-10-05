#!/bin/bash
# ============================================================================
#  漁벤져스 · Spot 선점 자동복구 루프 (2026-07-20 [C안] 추가)
#
#  Spot VM 은 선점되면 STOP 되고 스스로 다시 켜지지 않는다.
#  이 스크립트를 백그라운드로 띄워 두면 N초마다 resume.sh 를 돌려
#  꺼진 워커를 되살리고, 전량 완료되면 스스로 종료한다.
#
#  ※★ 무인 운용에는 이 스크립트가 아니라 batch/create_watchdog.sh 를 쓸 것.
#     Cloud Shell 은 클라이언트 연결이 끊기면 ~20분 뒤 VM 자체가 회수된다.
#     screen/tmux 는 "셸 세션" 유지 도구라 "머신 회수"는 못 막는다 → 노트북 끄면 같이 죽음.
#     이 스크립트는 사람이 붙어 있는 동안의 임시·수동 감시용이다.
#
#  실행(Cloud Shell, 임시):
#    cd ~/GCP
#    nohup bash batch/autoresume.sh > ~/autoresume.log 2>&1 &
#    tail -f ~/autoresume.log
# ============================================================================
set -uo pipefail
PROJECT="${PROJECT:-cfd-pilot}"
BUCKET="${BUCKET:-${PROJECT}-cfdbatch}"
NW="${NW:-6}"
TARGET="${TARGET:-380}"      # Tier0-2 = case0000~0379. Tier3까지면 700
INTERVAL="${INTERVAL:-120}"  # 점검 주기[s]. Spot 선점이 잦아 600→120 단축(2026-07-20)
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "== autoresume 시작 $(date -u +%FT%TZ) | 목표 ${TARGET}건 | 주기 ${INTERVAL}s =="
while true; do
  # ※ grep -c 는 0건일 때 "0" 출력 + exit 1 → `|| echo 0` 금지(0이 두 번 찍힘)
  n=$(gsutil ls "gs://${BUCKET}/done/"   2>/dev/null | grep -c '\.done')
  f=$(gsutil ls "gs://${BUCKET}/failed/" 2>/dev/null | grep -c '\.fail')
  echo "[$(date -u +%FT%TZ)] done=${n}/${TARGET} fail=${f}"

  if [ "$n" -ge "$TARGET" ]; then
    echo "== 목표 달성. 워커 정리 후 종료 =="
    PROJECT="$PROJECT" NW="$NW" bash "$HERE/teardown.sh" || true
    break
  fi

  PROJECT="$PROJECT" NW="$NW" bash "$HERE/resume.sh" 2>&1 | sed 's/^/    /'
  sleep "$INTERVAL"
done
echo "== autoresume 종료 $(date -u +%FT%TZ) =="
