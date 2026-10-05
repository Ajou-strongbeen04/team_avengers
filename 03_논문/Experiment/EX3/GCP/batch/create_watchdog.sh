#!/bin/bash
# ============================================================================
#  漁벤져스 · Spot 선점 워치독 VM 생성 (Cloud Shell). GCP/ 안에서 실행.  2026-07-20
#
#  왜 별도 VM 인가:
#   Cloud Shell 은 클라이언트 연결이 끊기면 ~20분 뒤 VM 이 회수된다.
#   screen/tmux 는 "셸 세션"이 끊겨도 프로세스를 살리는 도구일 뿐,
#   "머신이 사라지는 것"은 막지 못한다 → 노트북을 끄면 같이 죽는다.
#   따라서 감시 루프는 GCP 쪽 상주 VM 에 둔다.
#
#  비용: e2-micro + 30GB pd-standard 는 GCP 무료 등급 대상
#        (us-west1 / us-central1 / us-east1 중 한 리전, 월 1대).
#        워커가 us-west1 에 있으므로 같은 리전에 두면 추가 과금 사실상 0.
#        무료 등급을 이미 소진했더라도 월 $7 수준(4~5일이면 약 ₩1,400).
#
#  워치독은 목표 달성 시 워커를 지우고 자기 자신도 삭제한다(과금 자동 종료).
# ============================================================================
set -uo pipefail

PROJECT="${PROJECT:-cfd-pilot}"
BUCKET="${BUCKET:-${PROJECT}-cfdbatch}"
NW="${NW:-6}"
TARGET="${TARGET:-380}"      # Tier0-2 = case0000~0379. Tier3까지면 700
INTERVAL="${INTERVAL:-120}"  # 점검 주기[s]. Spot 선점이 잦으면 짧게(최소 60 권장)
NAME="${NAME:-watchdog}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
ENVF="$HERE/batch/workers.env"

# 워커 존은 create_workers.sh 가 기록한 workers.env 에서 읽는다
WZONE="${ZONE:-}"
[ -z "$WZONE" ] && [ -f "$ENVF" ] && WZONE="$(sed -n 's/^ZONE=//p' "$ENVF")"
if [ -z "$WZONE" ]; then
  echo "!! 워커 존을 알 수 없습니다. 먼저 create_workers.sh 를 실행하거나 ZONE=us-west1-a 로 지정하세요."
  exit 1
fi
WREGION="${WZONE%-*}"

# 무료 등급 리전 확인(아니면 경고만)
case "$WREGION" in
  us-west1|us-central1|us-east1) FREE="무료 등급 대상" ;;
  *) FREE="※ 무료 등급 리전 아님(월 ~\$7 과금)" ;;
esac

# 워치독은 워커와 같은 존에 둔다(같은 리전이면 무료 등급 조건 충족)
WDZONE="$WZONE"

echo "== 워치독 생성 =="
echo "   project=$PROJECT  bucket=gs://$BUCKET"
echo "   워커존=$WZONE (NW=$NW)  워치독존=$WDZONE  [$FREE]"
echo "   목표=$TARGET건  점검주기=${INTERVAL}s"

# 이미 있으면 삭제 후 재생성(설정 변경 반영)
if gcloud compute instances describe "$NAME" --project="$PROJECT" --zone="$WDZONE" >/dev/null 2>&1; then
  echo "== 기존 워치독 삭제 후 재생성 =="
  gcloud compute instances delete "$NAME" --project="$PROJECT" --zone="$WDZONE" --quiet
fi

gcloud compute instances create "$NAME" \
  --project="$PROJECT" --zone="$WDZONE" \
  --machine-type=e2-micro \
  --provisioning-model=STANDARD \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard \
  --scopes=cloud-platform \
  --metadata=bucket="$BUCKET",zone="$WZONE",nworkers="$NW",target="$TARGET",interval="$INTERVAL" \
  --metadata-from-file=startup-script="$HERE/batch/watchdog_startup.sh"

echo ""
echo "==================== 완료 ===================="
echo "워치독이 ${INTERVAL}초마다 선점된 워커를 되살립니다. 노트북을 꺼도 계속 동작합니다."
echo ""
echo "상태 확인(어디서든):"
echo "  gsutil cat gs://${BUCKET}/watchdog/status.txt"
echo ""
echo "로그 실시간:"
echo "  gcloud compute ssh ${NAME} --zone ${WDZONE} --command 'sudo tail -f /var/log/watchdog.log'"
echo ""
echo "수동 중지(워치독만 삭제, 워커는 유지):"
echo "  gcloud compute instances delete ${NAME} --zone ${WDZONE} --quiet"
echo "=============================================="
