#!/bin/bash
# ============================================================================
#  漁벤져스 · GCP 과금 전면 중지 (Cloud Shell 에서 실행)
#
#  기존 teardown.sh 의 한계를 보완:
#    - 프로젝트 2개(cfd-pilot / cfd-trainingdata) 모두 처리
#    - workers.env 가 비어 존을 모르므로 **전 존/전 리전을 스캔**해서 잔여 리소스 색출
#    - 인스턴스뿐 아니라 디스크·고정IP·스냅샷·커스텀이미지까지 (정지된 VM 도 디스크는 과금)
#
#  사용법:
#    bash stop_all_billing.sh              # ① 조회만(dry-run). 아무것도 안 지움
#    bash stop_all_billing.sh --yes        # ② 컴퓨트 전량 삭제 (버킷 데이터는 보존)
#    bash stop_all_billing.sh --yes --bucket   # ③ + GCS 버킷까지 삭제
#    bash stop_all_billing.sh --yes --unlink   # ④ + 결제계정 연결해제(과금 원천 차단)
#    bash stop_all_billing.sh --yes --bucket --unlink --delete-project  # ⑤ 프로젝트 삭제
#
#  ※ ①로 먼저 확인 → ②부터 실행 권장.
# ============================================================================
set -uo pipefail

PROJECTS="${PROJECTS:-cfd-pilot cfd-trainingdata}"
DO=0; DEL_BUCKET=0; UNLINK=0; DEL_PROJECT=0
for a in "$@"; do case "$a" in
  --yes) DO=1;; --bucket) DEL_BUCKET=1;; --unlink) UNLINK=1;;
  --delete-project) DEL_PROJECT=1;;
  *) echo "알 수 없는 옵션: $a"; exit 1;; esac; done

run(){ if [ "$DO" = "1" ]; then echo "  \$ $*"; "$@" || true; else echo "  [dry-run] $*"; fi; }
hdr(){ echo; echo "──────── $* ────────"; }

[ "$DO" = "0" ] && echo "### DRY-RUN 모드 — 조회만 합니다. 실제 삭제는 --yes ###"

TOTAL_FOUND=0

for P in $PROJECTS; do
  echo; echo "════════════ 프로젝트: $P ════════════"
  if ! gcloud projects describe "$P" >/dev/null 2>&1; then
    echo "  (프로젝트 없음/접근불가 — 건너뜀)"; continue
  fi

  # ── 1) 인스턴스 (전 존) ── 정지(STOP)된 SPOT VM 도 부팅디스크 과금이 계속됨
  hdr "1) Compute 인스턴스 (전 존 스캔)"
  mapfile -t INST < <(gcloud compute instances list --project="$P" \
      --format='value(name,zone,status)' 2>/dev/null)
  if [ "${#INST[@]}" -eq 0 ]; then echo "  없음"; else
    printf '  %s\n' "${INST[@]}"; TOTAL_FOUND=$((TOTAL_FOUND+${#INST[@]}))
    for row in "${INST[@]}"; do
      n=$(echo "$row"|awk '{print $1}'); z=$(echo "$row"|awk '{print $2}')
      run gcloud compute instances delete "$n" --project="$P" --zone="$z" --quiet
    done
  fi

  # ── 2) 영구 디스크 (인스턴스 지워도 남는 고아 디스크) ──
  hdr "2) 영구 디스크 (고아 디스크 = 계속 과금)"
  mapfile -t DISKS < <(gcloud compute disks list --project="$P" \
      --format='value(name,zone,region,sizeGb)' 2>/dev/null)
  if [ "${#DISKS[@]}" -eq 0 ]; then echo "  없음"; else
    printf '  %s\n' "${DISKS[@]}"; TOTAL_FOUND=$((TOTAL_FOUND+${#DISKS[@]}))
    for row in "${DISKS[@]}"; do
      n=$(echo "$row"|awk '{print $1}'); z=$(echo "$row"|awk '{print $2}'); r=$(echo "$row"|awk '{print $3}')
      if [ -n "$z" ]; then run gcloud compute disks delete "$n" --project="$P" --zone="$z" --quiet
      else                run gcloud compute disks delete "$n" --project="$P" --region="$r" --quiet; fi
    done
  fi

  # ── 3) 고정 외부 IP (미사용 예약 IP 는 오히려 더 비쌈) ──
  hdr "3) 예약 고정 IP"
  mapfile -t ADDRS < <(gcloud compute addresses list --project="$P" \
      --format='value(name,region,status)' 2>/dev/null)
  if [ "${#ADDRS[@]}" -eq 0 ]; then echo "  없음"; else
    printf '  %s\n' "${ADDRS[@]}"; TOTAL_FOUND=$((TOTAL_FOUND+${#ADDRS[@]}))
    for row in "${ADDRS[@]}"; do
      n=$(echo "$row"|awk '{print $1}'); r=$(echo "$row"|awk '{print $2}')
      if [ -n "$r" ]; then run gcloud compute addresses delete "$n" --project="$P" --region="$r" --quiet
      else               run gcloud compute addresses delete "$n" --project="$P" --global --quiet; fi
    done
  fi

  # ── 4) 스냅샷 · 커스텀 이미지 ──
  hdr "4) 스냅샷 / 커스텀 이미지"
  for s in $(gcloud compute snapshots list --project="$P" --format='value(name)' 2>/dev/null); do
    echo "  snapshot: $s"; TOTAL_FOUND=$((TOTAL_FOUND+1))
    run gcloud compute snapshots delete "$s" --project="$P" --quiet
  done
  for im in $(gcloud compute images list --project="$P" --no-standard-images --format='value(name)' 2>/dev/null); do
    echo "  image: $im"; TOTAL_FOUND=$((TOTAL_FOUND+1))
    run gcloud compute images delete "$im" --project="$P" --quiet
  done

  # ── 5) GCS 버킷 (기본 보존) ──
  hdr "5) GCS 버킷"
  BUCKETS=$(gcloud storage ls --project="$P" 2>/dev/null || gsutil ls -p "$P" 2>/dev/null)
  if [ -z "$BUCKETS" ]; then echo "  없음"; else
    echo "$BUCKETS" | sed 's/^/  /'
    for b in $BUCKETS; do
      sz=$(gcloud storage du -s "$b" 2>/dev/null | awk '{print $1}')
      echo "  ↳ $b  (약 ${sz:-?} bytes)"
    done
    if [ "$DEL_BUCKET" = "1" ]; then
      echo "  ※ --bucket 지정 → 삭제합니다. 로컬 C:\\cfd_raw 백업 확인 필수!"
      for b in $BUCKETS; do run gcloud storage rm -r "$b"; done
    else
      echo "  → 보존(기본). 저장비용은 소액이나 지우려면 --bucket"
    fi
  fi

  # ── 6) 결제계정 연결해제 (과금 원천 차단) ──
  if [ "$UNLINK" = "1" ]; then
    hdr "6) 결제계정 연결해제"
    echo "  현재: $(gcloud billing projects describe "$P" --format='value(billingAccountName,billingEnabled)' 2>/dev/null)"
    run gcloud billing projects unlink "$P"
  fi

  # ── 7) 프로젝트 삭제 (최종 수단, 30일 내 복구 가능) ──
  if [ "$DEL_PROJECT" = "1" ]; then
    hdr "7) 프로젝트 삭제"
    run gcloud projects delete "$P" --quiet
  fi
done

# ── 최종 검증 ──
echo; echo "════════════ 검증 (잔여 리소스가 0 이어야 함) ════════════"
for P in $PROJECTS; do
  gcloud projects describe "$P" >/dev/null 2>&1 || { echo "$P: (없음)"; continue; }
  i=$(gcloud compute instances list --project="$P" --format='value(name)' 2>/dev/null | wc -l)
  d=$(gcloud compute disks     list --project="$P" --format='value(name)' 2>/dev/null | wc -l)
  a=$(gcloud compute addresses list --project="$P" --format='value(name)' 2>/dev/null | wc -l)
  s=$(gcloud compute snapshots list --project="$P" --format='value(name)' 2>/dev/null | wc -l)
  be=$(gcloud billing projects describe "$P" --format='value(billingEnabled)' 2>/dev/null)
  echo "$P: 인스턴스=$i 디스크=$d 고정IP=$a 스냅샷=$s | billingEnabled=${be:-?}"
done

echo
if [ "$DO" = "0" ]; then
  echo "▶ DRY-RUN 이었습니다. 위 목록이 맞으면:  bash $0 --yes"
else
  echo "▶ 완료. 위 검증에서 전부 0 이고 billingEnabled=False 면 신규 과금 없음."
  echo "  (이미 발생한 당월 사용분은 청구서에 남습니다 — 소급 취소 아님)"
fi
