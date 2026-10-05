#!/usr/bin/env bash
# ============================================================================
#  漁벤져스 · Tier3 로컬 실행 러너 (GCP_v2 배치와 동일 폐합)          2026-07-25
#
#  하는 일 (cases_local20.txt 순서대로):
#    1. GCS done 마커 확인 → 이미 있으면 스킵
#    2. LOCAL_CLAIM 마커를 done/ 에 선점 업로드 → GCP 워커가 이 케이스를 건너뜀
#    3. 케이스를 $WORK(OneDrive 밖)로 복사해 ./Allrun (8코어, decomposeParDict=8)
#    4. 성공 → raw/${cid}.tgz 업로드 + done 마커를 최종본으로 덮어씀
#       실패 → 선점 마커 삭제(GCP가 다시 가져가도록) + _state/${cid}.fail 기록
#
#  ※ set -e / set -u 를 쓰지 않는다. OpenFOAM bashrc 를 엄격모드에서 소싱하면
#    셸이 조용히 죽는다(런북 함정 4).
#
#  실행:
#    cd <이 폴더>  &&  bash run_all.sh
#  옵션(env):
#    BUCKET=cfd-rom-cfdbatch   WORK=$HOME/t3run   CLAIM=1(0이면 GCS 미사용)
#    OF_BASHRC=/usr/lib/openfoam/openfoam2312/etc/bashrc
#    ONLY="case0698 case0696"  (지정 케이스만)
# ============================================================================

BUCKET="${BUCKET:-cfd-rom-cfdbatch}"
WORK="${WORK:-$HOME/t3run}"
CLAIM="${CLAIM:-1}"
OF_BASHRC="${OF_BASHRC:-/usr/lib/openfoam/openfoam2312/etc/bashrc}"
END="${END:-200}"

HERE="$(cd "$(dirname "$0")" && pwd)"
LIST="${LIST:-$HERE/cases_local20.txt}"
STATE="$HERE/_state"
mkdir -p "$STATE" "$WORK"

# ---- OpenFOAM 환경 (엄격모드 금지) ----
if [ ! -f "$OF_BASHRC" ]; then
  echo "!! OpenFOAM bashrc 없음: $OF_BASHRC"
  echo "   OF_BASHRC=<경로> bash run_all.sh 로 지정하세요."
  exit 1
fi
. "$OF_BASHRC"
if [ -z "${WM_PROJECT_DIR:-}" ]; then echo "!! OpenFOAM 환경 소싱 실패"; exit 1; fi
echo "OpenFOAM: $WM_PROJECT_DIR"

# ---- GCS 커맨드 선택 ----
GS=""
if [ "$CLAIM" = "1" ]; then
  if command -v gsutil >/dev/null 2>&1; then GS=gsutil
  elif command -v gcloud >/dev/null 2>&1; then GS=gcloud
  else echo "!! gsutil/gcloud 없음 → CLAIM=0 으로 로컬 전용 실행합니다."; CLAIM=0; fi
fi
gs_exists() { # $1=gs://...
  case "$GS" in
    gsutil) gsutil -q stat "$1" 2>/dev/null ;;
    gcloud) gcloud storage objects describe "$1" >/dev/null 2>&1 ;;
    *) return 1 ;;
  esac
}
gs_put_stdin() { # stdin → $1
  case "$GS" in
    gsutil) gsutil -q cp - "$1" 2>/dev/null ;;
    gcloud) gcloud storage cp - "$1" >/dev/null 2>&1 ;;
  esac
}
gs_put_file() { # $1=local $2=gs://
  case "$GS" in
    gsutil) gsutil -q cp "$1" "$2" 2>/dev/null ;;
    gcloud) gcloud storage cp "$1" "$2" >/dev/null 2>&1 ;;
  esac
}
gs_rm() {
  case "$GS" in
    gsutil) gsutil -q rm "$1" 2>/dev/null ;;
    gcloud) gcloud storage rm "$1" >/dev/null 2>&1 ;;
  esac
}

CASES="${ONLY:-$(cat "$LIST")}"
NTOT=$(echo $CASES | wc -w)
echo "== Tier3 로컬 실행 시작 $(date '+%F %T') | ${NTOT}건 | WORK=$WORK | CLAIM=$CLAIM =="

i=0
for cid in $CASES; do
  i=$((i+1))
  echo ""
  echo "---- [$i/$NTOT] $cid  $(date '+%F %T') ----"

  if [ -f "$STATE/${cid}.done" ]; then echo "  로컬 완료 기록 있음 → 스킵"; continue; fi

  if [ "$CLAIM" = "1" ] && gs_exists "gs://${BUCKET}/done/${cid}.done"; then
    echo "  GCS done 마커 존재(GCP가 이미 처리) → 스킵"
    touch "$STATE/${cid}.done"; continue
  fi

  # ---- 선점: GCP 워커가 이 케이스를 건너뛰게 만든다 ----
  if [ "$CLAIM" = "1" ]; then
    echo "LOCAL_CLAIM host=$(hostname) $(date -u +%FT%TZ)" \
      | gs_put_stdin "gs://${BUCKET}/done/${cid}.done"
    echo "  선점 마커 업로드"
  fi

  rm -rf "$WORK/$cid"
  cp -r "$HERE/flow/$cid" "$WORK/$cid" || { echo "  !! 복사 실패"; continue; }
  cd "$WORK/$cid" || continue
  chmod +x Allrun Allclean 2>/dev/null

  T0=$(date +%s)
  ./Allrun > run.log 2>&1
  T1=$(date +%s)

  if grep -q '^End' log.pimpleFoam 2>/dev/null || [ -d "$END" ]; then
    CLOCK=$(grep ClockTime log.pimpleFoam | tail -1 | sed -E 's/.*ClockTime = ([0-9.]+) s.*/\1/')
    echo "  완주 OK  clock=${CLOCK}s  경과=$(( (T1-T0)/60 ))분"
    tar czf "$WORK/${cid}.tgz" --exclude='processor*' --exclude='log.*' --exclude='run.log' \
        constant system [0-9]* 2>/dev/null
    if [ "$CLAIM" = "1" ]; then
      gs_put_file "$WORK/${cid}.tgz" "gs://${BUCKET}/raw/${cid}.tgz" && echo "  raw 업로드 OK" \
        || echo "  !! raw 업로드 실패 — $WORK/${cid}.tgz 보관됨"
      echo "${cid} clock=${CLOCK}s tEnd=${END} tAvg=40-${END} LOCAL $(date -u +%FT%TZ)" \
        | gs_put_stdin "gs://${BUCKET}/done/${cid}.done"
    fi
    echo "${cid} clock=${CLOCK}s $(date -u +%FT%TZ)" > "$STATE/${cid}.done"
    # 결과 tgz 는 업로드 성공 시에만 삭제
    if [ "$CLAIM" = "1" ] && gs_exists "gs://${BUCKET}/raw/${cid}.tgz"; then rm -f "$WORK/${cid}.tgz"; fi
    ./Allclean >/dev/null 2>&1
    cd "$HERE" && rm -rf "$WORK/$cid"
  else
    echo "  !! FAIL — $WORK/$cid 유지(로그 확인: run.log, log.pimpleFoam)"
    echo "${cid} FAIL $(date -u +%FT%TZ)" > "$STATE/${cid}.fail"
    [ "$CLAIM" = "1" ] && { gs_rm "gs://${BUCKET}/done/${cid}.done"; echo "  선점 마커 반납(GCP가 재시도)"; }
    cd "$HERE"
  fi
done

echo ""
echo "== 종료 $(date '+%F %T') | 완료 $(ls "$STATE"/*.done 2>/dev/null | wc -l) / 실패 $(ls "$STATE"/*.fail 2>/dev/null | wc -l) =="
