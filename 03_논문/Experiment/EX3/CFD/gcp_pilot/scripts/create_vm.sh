#!/bin/bash
# ============================================================================
#  漁벤져스 · GCP 파일럿 VM 생성 (로컬 PowerShell/Cloud Shell 에서 실행)
#  Spot VM 1대를 띄운다. 파일럿이 끝나면 반드시 fetch_and_teardown.sh 로 삭제.
# ============================================================================
set -euo pipefail

PROJECT="${PROJECT:?PROJECT 환경변수에 GCP 프로젝트 ID 를 넣으세요}"
VM="${VM:-of-pilot}"
ZONE="${ZONE:-us-central1-a}"          # batch → 지연 무관, 최저가 리전
MACHINE="${MACHINE:-c2d-highcpu-16}"   # 8물리코어/16vCPU/32GB. C3D 비교시 c3d-highcpu-16
DISK_GB="${DISK_GB:-50}"

gcloud compute instances create "$VM" \
  --project="$PROJECT" \
  --zone="$ZONE" \
  --machine-type="$MACHINE" \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size="${DISK_GB}GB" \
  --boot-disk-type=pd-balanced

echo ""
echo "생성됨: $VM ($MACHINE, SPOT) in $ZONE"
echo "다음: 케이스 업로드 → 프로비저닝 → 실행 (README 3~4단계)"
