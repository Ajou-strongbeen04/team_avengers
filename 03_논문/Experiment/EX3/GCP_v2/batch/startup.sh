#!/bin/bash
# ============================================================================
#  漁벤져스 · 워커 VM startup-script (GCP_v2 / cfd-rom)
#  OpenFOAM 설치 → 번들 동기화 → 케이스 전개 → 케이스-리스트 worker 루프.
#  선점 STOP 후 재시작되면 다시 돌아 미완만 이어감(gen179.txt 목록 한정).
# ============================================================================
set -u
META="http://metadata/computeMetadata/v1/instance/attributes"
HDR="Metadata-Flavor: Google"
BUCKET=$(curl -s -H "$HDR" "$META/bucket")
SHARD=$(curl -s -H "$HDR"  "$META/shard")
NW=$(curl -s -H "$HDR"     "$META/nworkers")
END=$(curl -s -H "$HDR"    "$META/endtime"); [[ "$END"    =~ ^[0-9]+$ ]] || END=200
MAXIDX=$(curl -s -H "$HDR" "$META/maxidx");  [[ "$MAXIDX" =~ ^[0-9]+$ ]] || MAXIDX=699
export END MAXIDX
export CASELIST=/opt/cfd/gen179.txt          # ★ 번들에 포함된 179 목록
OF_VER=openfoam2312

command -v gsutil >/dev/null 2>&1 || snap install google-cloud-cli --classic

if [ ! -f /usr/lib/openfoam/${OF_VER}/etc/bashrc ]; then
  apt-get update -y
  curl -fsSL https://dl.openfoam.com/add-debian-repo.sh | bash
  apt-get update -y
  apt-get install -y ${OF_VER}-default
fi

mkdir -p /opt/cfd && cd /opt/cfd
gsutil -m rsync -r "gs://${BUCKET}/bundle" /opt/cfd
chmod +x worker.sh

# 케이스 전개(700 전량 생성은 수 초; 실행은 worker가 gen179 목록·자기 샤드만)
python3 gen_cases.py --csv cases.csv --template template_case --out flow >/var/log/cfd_gen.log 2>&1

sed -i -E "s/^([[:space:]]*endTime[[:space:]]+)[0-9.]+;/\1${END};/" flow/case*/system/controlDict
echo "endTime=${END} 적용 / CASELIST=${CASELIST}($(wc -l < ${CASELIST} 2>/dev/null))" >> /var/log/cfd_gen.log

nohup ./worker.sh "$BUCKET" "$SHARD" "$NW" > /var/log/cfd_worker.log 2>&1 &
