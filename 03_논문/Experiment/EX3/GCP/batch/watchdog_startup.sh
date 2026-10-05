#!/bin/bash
# ============================================================================
#  漁벤져스 · Spot 선점 워치독 (e2-micro VM 안에서 24/7 상주)  2026-07-20
#
#  이 스크립트는 워치독 VM 의 startup-script 로 등록된다.
#  → VM 이 부팅/재부팅될 때마다 자동 실행되므로 별도 상주 데몬 설정이 불필요하다.
#  → 사용자의 노트북·Cloud Shell 이 꺼져도 무관하게 계속 돈다.
#
#  하는 일 (INTERVAL 초마다):
#   1. 워커 목록을 한 번의 API 호출로 조회
#   2. TERMINATED/STOPPING/SUSPENDED 인 워커를 병렬로 start (Spot 선점 복구)
#   3. 주기적으로 done 마커를 세어 목표 도달 시 → 워커 전량 삭제 → 자기 자신도 삭제
#   4. 상태를 gs://BUCKET/watchdog/status.txt 에 기록(어디서든 확인 가능)
#
#  메타데이터: bucket, zone, nworkers, target, interval
# ============================================================================
set -uo pipefail
META="http://metadata/computeMetadata/v1/instance/attributes"
HDR="Metadata-Flavor: Google"
g() { curl -s -H "$HDR" "$META/$1" 2>/dev/null; }

BUCKET=$(g bucket)
ZONE=$(g zone)
NW=$(g nworkers);      [[ "$NW"       =~ ^[0-9]+$ ]] || NW=6
TARGET=$(g target);    [[ "$TARGET"   =~ ^[0-9]+$ ]] || TARGET=380
INTERVAL=$(g interval);[[ "$INTERVAL" =~ ^[0-9]+$ ]] || INTERVAL=120
SELF=$(curl -s -H "$HDR" http://metadata/computeMetadata/v1/instance/name)
SELFZONE=$(basename "$(curl -s -H "$HDR" http://metadata/computeMetadata/v1/instance/zone)")
PROJECT=$(curl -s -H "$HDR" http://metadata/computeMetadata/v1/project/project-id)

LOG=/var/log/watchdog.log
exec >>"$LOG" 2>&1

# gcloud (GCP 이미지엔 보통 있지만 없으면 설치)
command -v gcloud >/dev/null 2>&1 || snap install google-cloud-cli --classic

say() { echo "[$(date -u +%FT%TZ)] $*"; }

say "=== 워치독 기동 | project=$PROJECT zone=$ZONE NW=$NW target=$TARGET interval=${INTERVAL}s ==="

cycle=0
revives=0
last_done=-1
stall=0

while true; do
  cycle=$((cycle+1))

  # ---- 1) 워커 상태 조회 (API 1회) ----
  states=$(gcloud compute instances list --project="$PROJECT" --zones="$ZONE" \
             --filter="name~^worker-" --format="value(name,status)" 2>/dev/null)

  # ---- 2) 꺼진 워커 병렬 기동 ----
  dead=$(echo "$states" | awk '$2=="TERMINATED"||$2=="STOPPING"||$2=="SUSPENDED"{print $1}')
  if [ -n "$dead" ]; then
    say "선점감지: $(echo $dead | tr '\n' ' ')→ start"
    for w in $dead; do
      ( gcloud compute instances start "$w" --project="$PROJECT" --zone="$ZONE" --quiet \
          >/dev/null 2>&1 && say "  ${w} 복구 OK" || say "  ${w} 복구 실패(존 재고 부족 가능)" ) &
      revives=$((revives+1))
    done
    wait
  fi

  # 워커가 아예 없어진 경우(삭제됨) 경고 — 해당 샤드가 영구 정지되므로 사람이 봐야 함
  alive=$(echo "$states" | grep -c .)
  [ "$alive" -lt "$NW" ] && say "!! 워커 ${alive}/${NW} 만 존재. 누락 샤드는 재생성 필요"

  # ---- 3) 진행률 점검 (매 5주기 = API·과금 절약) ----
  if [ $((cycle % 5)) -eq 1 ]; then
    # ※ grep -c 는 0건일 때 "0" 출력 + exit 1 → `|| echo 0` 금지(0이 두 번 찍힘)
    n=$(gsutil ls "gs://${BUCKET}/done/"   2>/dev/null | grep -c '\.done')
    f=$(gsutil ls "gs://${BUCKET}/failed/" 2>/dev/null | grep -c '\.fail')
    running=$(echo "$states" | grep -c RUNNING)
    say "진행 done=${n}/${TARGET} fail=${f} | RUNNING=${running}/${NW} | 누적복구=${revives}"

    # 상태 파일을 GCS 에 기록 → 어디서든 `gsutil cat` 로 확인
    printf '%s\ndone=%s/%s fail=%s running=%s/%s revives=%s cycle=%s\n%s\n' \
      "watchdog @ $(date -u +%FT%TZ)" "$n" "$TARGET" "$f" "$running" "$NW" "$revives" "$cycle" \
      "$states" | gsutil -q cp - "gs://${BUCKET}/watchdog/status.txt" 2>/dev/null

    # 진행 정체 감지(워커는 살아있는데 done 이 안 늘어남)
    if [ "$n" = "$last_done" ]; then stall=$((stall+1)); else stall=0; last_done="$n"; fi
    [ "$stall" -ge 12 ] && say "!! 진행 정체 ${stall}회 연속 — 워커 로그 점검 필요(/var/log/cfd_worker.log)"

    # ---- 4) 목표 달성 → 워커 삭제 → 자기 자신 삭제 ----
    if [ "$n" -ge "$TARGET" ]; then
      say "=== 목표 ${TARGET}건 달성. 워커 정리 =="
      names=""; for i in $(seq 0 $((NW-1))); do names="$names worker-${i}"; done
      gcloud compute instances delete $names --project="$PROJECT" --zone="$ZONE" --quiet || true
      printf 'COMPLETE done=%s/%s @ %s\n' "$n" "$TARGET" "$(date -u +%FT%TZ)" \
        | gsutil -q cp - "gs://${BUCKET}/watchdog/status.txt"
      gsutil -q cp "$LOG" "gs://${BUCKET}/watchdog/watchdog.log" 2>/dev/null || true
      say "=== 워치독 자체 삭제 ==="
      gcloud compute instances delete "$SELF" --project="$PROJECT" --zone="$SELFZONE" --quiet
      exit 0
    fi
  fi

  # ---- 로그 비대 방지(2분 주기 × 수일이면 수만 줄) ----
  if [ $((cycle % 500)) -eq 0 ]; then
    tail -n 2000 "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"
    gsutil -q cp "$LOG" "gs://${BUCKET}/watchdog/watchdog.log" 2>/dev/null || true
  fi

  sleep "$INTERVAL"
done
