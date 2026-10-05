#!/bin/bash
# ============================================================================
#  漁벤져스 · [C안] Spot 전환 + Tier2(380케이스) + 무인 워치독
#  2026-07-20  — Cloud Shell 에 통째로 붙여넣기
#
#  왜 이 파일이 있는가:
#   ~/GCP 폴더는 덮어쓰기 업로드가 안 되므로(전체 삭제 후 재업로드만 가능),
#   변경된 스크립트를 heredoc 으로 Cloud Shell 에서 직접 재생성한다.
#   (RUNBOOK 함정 (8) OneDrive 동기화 지연에 의한 업로드 파일 잘림도 함께 회피)
#
#  ── 변경 요약 ─────────────────────────────────────────────────────────────
#   batch/worker.sh          MAXIDX Tier 게이트, 성공판정 하드코딩(200) 제거,
#                            done 마커에 tEnd/tAvg 기록
#   batch/startup.sh         endtime/maxidx 메타데이터 주입 + 전개 후 controlDict 동조
#   batch/watchdog_startup.sh (신규) 워치독 VM 상주 루프
#   batch/create_watchdog.sh  (신규) 무료등급 e2-micro 워치독 VM 생성
#   batch/autoresume.sh       (신규) Cloud Shell 임시 감시용. 주기 600→120s
#   batch/status.sh           grep -c 이중출력 버그 수정 + 잔여비용·워커상태 표시
#
#   template_case/system/controlDict  변경 없음(endTime 200·ascii 유지) → 재업로드 불필요
#   batch/create_workers.sh           패치 불필요. startup.sh 기본값(END=200,
#                                     MAXIDX=379)이 자동 적용됨. PROVISION 만 인자 전달.
#
#  ── 왜 screen 이 아니라 워치독 VM 인가 ────────────────────────────────────
#   Cloud Shell 은 클라이언트 연결이 끊기면 약 20분 뒤 VM 자체가 회수된다.
#   screen/tmux 는 "셸 세션"이 끊겨도 프로세스를 살리는 도구일 뿐이며
#   "머신이 사라지는 것"은 막지 못한다 → 노트북을 끄면 screen 세션도 같이 소멸.
#   따라서 선점 감시 루프는 GCP 쪽 상주 VM(e2-micro, 무료등급)에 둔다.
# ============================================================================
set -e
cd ~/GCP

echo '  → batch/worker.sh 재생성'
cat > batch/worker.sh <<'PATCH_EOF'
#!/bin/bash
# ============================================================================
#  漁벤져스 · 워커 루프 (VM 안, startup이 호출)
#  자기 샤드(index %% NW == SHARD) 케이스만 순회. 완료마커 있으면 스킵(재개).
#  풀이 성공 → 원시 평균필드 tgz 를 gs://BUCKET/raw/ 업로드 + done 마커(ClockTime 기록).
#  인자: worker.sh BUCKET SHARD NW
#
#  2026-07-20 변경 [C안: Spot 전환 + Tier2까지]:
#   - END: 성공판정 하드코딩(200) 제거 → 변수화. 값은 200 유지(평균창 혼재 회피).
#   - MAXIDX: Tier 게이트. cases.csv가 tier 오름차순이라 idx 0~379 = Tier0-2,
#     380~699 = Tier3. 기본값 379로 Tier0-2만 먼저 완주 → ROM 학습 →
#     재구성오차 큰 영역만 MAXIDX=699로 재실행해 Tier3 선별 투입.
# ============================================================================
BUCKET="$1"; SHARD="$2"; NW="$3"
END="${END:-200}"        # controlDict endTime 과 반드시 일치시킬 것
MAXIDX="${MAXIDX:-379}"  # Tier3까지 가려면 MAXIDX=699
OF_VER=openfoam2312
source "/usr/lib/openfoam/${OF_VER}/etc/bashrc"
export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1   # 루트 자동실행 허용

cd /opt/cfd/flow || exit 1
for d in case*/; do
  cid="${d%/}"
  idx=$((10#${cid#case}))
  (( idx <= MAXIDX )) || continue            # Tier 게이트
  (( idx % NW == SHARD )) || continue
  gsutil -q stat "gs://${BUCKET}/done/${cid}.done" 2>/dev/null && continue   # 이미 완료

  cd "$cid" || continue
  chmod +x Allrun
  ./Allrun > run.log 2>&1

  # 성공 판정: log 끝에 End 또는 최종시간($END) 디렉터리
  if grep -q '^End' log.pimpleFoam 2>/dev/null || [ -d "$END" ]; then
    CLOCK=$(grep ClockTime log.pimpleFoam | tail -1 | sed -E 's/.*ClockTime = ([0-9.]+) s.*/\1/')
    tar czf "/tmp/${cid}.tgz" --exclude='processor*' --exclude='log.*' --exclude='run.log' \
        constant system [0-9]* 2>/dev/null
    gsutil -q cp "/tmp/${cid}.tgz" "gs://${BUCKET}/raw/${cid}.tgz"
    # tEnd 를 마커에 기록 → 평균창 혼재(선행 123케이스=200s) 추적용
    echo "${cid} clock=${CLOCK}s tEnd=${END} tAvg=40-${END} $(date -u +%FT%TZ)" \
      | gsutil -q cp - "gs://${BUCKET}/done/${cid}.done"
    rm -f "/tmp/${cid}.tgz"
  else
    echo "${cid} FAIL $(date -u +%FT%TZ)" | gsutil -q cp - "gs://${BUCKET}/failed/${cid}.fail"
  fi

  ./Allclean >/dev/null 2>&1   # 디스크 회수
  cd /opt/cfd/flow
done
echo "== WORKER ${SHARD}/${NW} 샤드 완료 $(date -u) =="
PATCH_EOF

echo '  → batch/startup.sh 재생성'
cat > batch/startup.sh <<'PATCH_EOF'
#!/bin/bash
# ============================================================================
#  漁벤져스 · 워커 VM startup-script (부팅/재시작마다 자동 실행)
#  OpenFOAM 설치(없으면) → 버킷 번들 동기화 → 케이스 전개 → worker 루프(분리)
#  선점으로 STOP 후 start 되면 이 스크립트가 다시 돌아 미완 케이스만 이어감.
# ============================================================================
set -u
META="http://metadata/computeMetadata/v1/instance/attributes"
HDR="Metadata-Flavor: Google"
BUCKET=$(curl -s -H "$HDR" "$META/bucket")
SHARD=$(curl -s -H "$HDR"  "$META/shard")
NW=$(curl -s -H "$HDR"     "$META/nworkers")
# 2026-07-20 추가: 평균창(endTime)·Tier 게이트를 메타데이터로 주입(없으면 기본값)
#   (미설정 키는 404 본문이 오므로 숫자인지 검사 후 채택)
END=$(curl -s -H "$HDR"    "$META/endtime"); [[ "$END"    =~ ^[0-9]+$ ]] || END=200
MAXIDX=$(curl -s -H "$HDR" "$META/maxidx");  [[ "$MAXIDX" =~ ^[0-9]+$ ]] || MAXIDX=379
export END MAXIDX
OF_VER=openfoam2312

# gcloud/gsutil
command -v gsutil >/dev/null 2>&1 || snap install google-cloud-cli --classic

# OpenFOAM (디스크 유지 시 재설치 안 함)
if [ ! -f /usr/lib/openfoam/${OF_VER}/etc/bashrc ]; then
  apt-get update -y
  curl -fsSL https://dl.openfoam.com/add-debian-repo.sh | bash
  apt-get update -y
  apt-get install -y ${OF_VER}-default
fi

mkdir -p /opt/cfd && cd /opt/cfd
gsutil -m rsync -r "gs://${BUCKET}/bundle" /opt/cfd
chmod +x worker.sh

# 케이스 전개(전량 생성은 수 초; 실행은 worker가 자기 샤드만)
python3 gen_cases.py --csv cases.csv --template template_case --out flow >/var/log/cfd_gen.log 2>&1

# 전개된 모든 케이스의 endTime 을 $END 로 강제 동조(템플릿과 메타데이터 불일치 방지)
sed -i -E "s/^([[:space:]]*endTime[[:space:]]+)[0-9.]+;/\1${END};/" flow/case*/system/controlDict
echo "endTime=${END} 적용: $(grep -h '^endTime' flow/case0000/system/controlDict)" >> /var/log/cfd_gen.log

nohup ./worker.sh "$BUCKET" "$SHARD" "$NW" > /var/log/cfd_worker.log 2>&1 &
PATCH_EOF

echo '  → batch/autoresume.sh 재생성'
cat > batch/autoresume.sh <<'PATCH_EOF'
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
PATCH_EOF

echo '  → batch/status.sh 재생성'
cat > batch/status.sh <<'PATCH_EOF'
#!/bin/bash
# 진행률 확인 (Cloud Shell). done/failed 마커 집계 + 누적 ClockTime.
set -uo pipefail
BUCKET="${BUCKET:-cfd-pilot-cfdbatch}"
TARGET="${TARGET:-380}"   # [C안] 현 목표 = Tier0-2(case0000~0379). Tier3까지면 TARGET=700
# ※ grep -c 는 0건일 때 "0"을 출력하면서 exit 1 → `|| echo 0` 을 붙이면 0이 두 번 찍힌다
#   (2026-07-20 수정. 이전 출력의 "실패(fail): 0 / 0 원시업로드..." 줄바꿈 원인)
count() { gsutil ls "$1" 2>/dev/null | grep -c "$2"; }
done=$(count "gs://${BUCKET}/done/"   '\.done')
fail=$(count "gs://${BUCKET}/failed/" '\.fail')
raw=$( count "gs://${BUCKET}/raw/"    '\.tgz')
echo "완료(done): ${done} / ${TARGET} (Tier0-2)   실패(fail): ${fail}   원시업로드(raw): ${raw}"
# Spot 단가 ₩500/케이스(=온디맨드 실측 ₩1,407 × 0.36) 기준 잔여비용 개산
rem=$(( TARGET - done )); [ "$rem" -lt 0 ] && rem=0
echo "잔여 ${rem}건 · Spot 개산 ₩$(( rem * 500 ))  (온디맨드였다면 ₩$(( rem * 1407 )))"
echo "워커 상태:"; gcloud compute instances list --filter="name~worker-" \
  --format="table(name,zone,status,scheduling.provisioningModel)" 2>/dev/null
echo "실패 목록:"; gsutil ls "gs://${BUCKET}/failed/" 2>/dev/null | sed 's#.*/##' PATCH_EOF

echo '  → batch/watchdog_startup.sh 재생성'
cat > batch/watchdog_startup.sh <<'PATCH_EOF'
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
PATCH_EOF

echo '  → batch/create_watchdog.sh 재생성'
cat > batch/create_watchdog.sh <<'PATCH_EOF'
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
PATCH_EOF

chmod +x batch/*.sh
echo ""
echo "== 기본값 확인 (END=200 / MAXIDX=379 여야 정상) =="
grep -n 'END:-\|MAXIDX:-' batch/worker.sh batch/startup.sh

cat <<'NEXT'

================================================================
 다음 순서대로 실행하세요
================================================================

 1) 온디맨드 워커 전량 삭제 (★과금 즉시 중지)
      bash batch/teardown.sh

 2) 존 기록 삭제 — Spot 재고는 온디맨드와 다른 존일 수 있음
      rm -f batch/workers.env

 3) Spot 워커 6대 생성 (번들은 create_workers 가 rsync -d 로 자동 재업로드)
      PROVISION=SPOT NW=6 bash batch/create_workers.sh

 4) ★무인 워치독 기동 — 이후 노트북을 꺼도 무방
      bash batch/create_watchdog.sh
    (선점 감시 120초 주기. 380건 달성 시 워커·워치독 모두 자동 삭제)

 5) 상태 확인 — 어디서든, Cloud Shell 없이도
      gsutil cat gs://cfd-pilot-cfdbatch/watchdog/status.txt
      bash batch/status.sh

 참고) 선점이 더 잦으면 주기를 더 짧게:
      INTERVAL=60 bash batch/create_watchdog.sh
 참고) Tier3 까지 확장할 때:
      TARGET=700 bash batch/create_watchdog.sh
      + batch/worker.sh 의 MAXIDX 기본값을 699 로 바꾸고 워커 재생성

================================================================
NEXT
