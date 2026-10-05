#!/bin/bash
# ============================================================================
#  漁벤져스 · Spot 선점 워치독 (macOS / Mac mini 상주판)   2026-07-20
#
#  Mac mini 가 24시간 켜져 있다면 GCP 에 별도 워치독 VM 을 둘 필요가 없다.
#  이 스크립트가 INTERVAL 초마다:
#    1. 워커 상태 조회(존 자동탐색 — workers.env 불필요)
#    2. 선점되어 꺼진 워커를 병렬 start
#    3. done 마커를 세어 목표 도달 시 워커 전량 삭제 + macOS 알림 + 종료
#
#  사전 준비 (최초 1회):
#    brew install --cask google-cloud-sdk     # 또는 https://cloud.google.com/sdk
#    gcloud auth login
#    gcloud config set project cfd-pilot
#
#  실행:
#    bash spot_watchdog.sh                    # 포그라운드(테스트)
#    screen -dmS wd bash spot_watchdog.sh     # 백그라운드(재부팅 전까지 유지)
#    bash install_launchd.sh                  # 재부팅까지 견디는 상주 등록(권장)
# ============================================================================
set -uo pipefail

PROJECT="${PROJECT:-cfd-pilot}"
BUCKET="${BUCKET:-cfd-pilot-cfdbatch}"
NW="${NW:-6}"
TARGET="${TARGET:-380}"      # Tier0-2 = case0000~0379. Tier3까지면 700
INTERVAL="${INTERVAL:-120}"  # 점검 주기[s]
LOG="${LOG:-$HOME/spot_watchdog.log}"

# launchd 는 PATH 를 물려주지 않으므로 gcloud 를 직접 찾는다
for p in /opt/homebrew/bin /usr/local/bin "$HOME/google-cloud-sdk/bin" \
         /opt/homebrew/share/google-cloud-sdk/bin /usr/local/share/google-cloud-sdk/bin; do
  [ -x "$p/gcloud" ] && export PATH="$p:$PATH"
done

say(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
notify(){ osascript -e "display notification \"$2\" with title \"$1\"" 2>/dev/null || true; }

# ---- 사전 점검 ----
command -v gcloud >/dev/null 2>&1 || { say "!! gcloud 없음. brew install --cask google-cloud-sdk"; exit 1; }
command -v gsutil >/dev/null 2>&1 || { say "!! gsutil 없음(google-cloud-sdk 에 포함)"; exit 1; }
acct=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
[ -z "$acct" ] && { say "!! gcloud 인증 없음. 'gcloud auth login' 먼저 실행"; exit 1; }

say "=== Mac 워치독 기동 | account=$acct project=$PROJECT target=$TARGET interval=${INTERVAL}s ==="
notify "漁벤져스 CFD" "Spot 워치독 시작 (목표 ${TARGET}건)"

cycle=0; revives=0; last=-1; stall=0; ZONE=""

while true; do
  cycle=$((cycle+1))

  # ---- 1) 워커 조회. 존은 자동탐색(전 존 검색) 후 캐시 ----
  if [ -n "$ZONE" ]; then
    states=$(gcloud compute instances list --project="$PROJECT" --zones="$ZONE" \
               --filter="name~^worker-" --format="value(name,zone.basename(),status)" 2>/dev/null)
  else
    states=$(gcloud compute instances list --project="$PROJECT" \
               --filter="name~^worker-" --format="value(name,zone.basename(),status)" 2>/dev/null)
    ZONE=$(echo "$states" | awk 'NR==1{print $2}')
    [ -n "$ZONE" ] && say "워커 존 탐지: $ZONE"
  fi

  if [ -z "$states" ]; then
    say "!! 워커가 하나도 없음. create_workers.sh 를 먼저 실행했는지 확인"
    sleep "$INTERVAL"; continue
  fi

  # ---- 2) 꺼진 워커 병렬 기동 ----
  dead=$(echo "$states" | awk '$3=="TERMINATED"||$3=="STOPPING"||$3=="SUSPENDED"{print $1}')
  if [ -n "$dead" ]; then
    say "선점감지: $(echo $dead | tr '\n' ' ')→ start"
    for w in $dead; do
      ( gcloud compute instances start "$w" --project="$PROJECT" --zone="$ZONE" --quiet \
          >/dev/null 2>&1 && say "  ${w} 복구 OK" || say "  ${w} 복구 실패(존 재고 부족 가능)" ) &
      revives=$((revives+1))
    done
    wait
  fi

  alive=$(echo "$states" | grep -c .)
  [ "$alive" -lt "$NW" ] && say "!! 워커 ${alive}/${NW} 만 존재. 누락 샤드 재생성 필요"

  # ---- 3) 진행률 (매 5주기) ----
  if [ $((cycle % 5)) -eq 1 ]; then
    n=$(gsutil ls "gs://${BUCKET}/done/"   2>/dev/null | grep -c '\.done')
    f=$(gsutil ls "gs://${BUCKET}/failed/" 2>/dev/null | grep -c '\.fail')
    r=$(echo "$states" | grep -c RUNNING)
    say "진행 done=${n}/${TARGET} fail=${f} | RUNNING=${r}/${NW} | 누적복구=${revives}"

    if [ "$n" = "$last" ]; then stall=$((stall+1)); else stall=0; last="$n"; fi
    if [ "$stall" -eq 12 ]; then
      say "!! 진행 정체 — 워커 로그 점검 필요"
      notify "漁벤져스 CFD ⚠️" "진행 정체 감지 (done=${n})"
    fi

    # ---- 4) 목표 달성 → 워커 삭제 → 종료 ----
    if [ "$n" -ge "$TARGET" ]; then
      say "=== 목표 ${TARGET}건 달성. 워커 전량 삭제 ==="
      names=""; for i in $(seq 0 $((NW-1))); do names="$names worker-${i}"; done
      gcloud compute instances delete $names --project="$PROJECT" --zone="$ZONE" --quiet || true
      say "=== 완료. 누적복구 ${revives}회 ==="
      notify "漁벤져스 CFD ✅" "CFD ${n}건 완료. 워커 삭제됨"
      # 상주 등록되어 있으면 스스로 해제(재부팅 후 다시 안 뜨도록)
      launchctl bootout "gui/$(id -u)/com.eobengers.spotwatchdog" 2>/dev/null || true
      exit 0
    fi
  fi

  sleep "$INTERVAL"
done
