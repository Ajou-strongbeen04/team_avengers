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

nohup ./worker.sh "$BUCKET" "$SHARD" "$NW" > /var/log/cfd_worker.log 2>&1 &
