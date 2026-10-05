#!/bin/bash
# ============================================================================
#  漁벤져스 · 워커 루프 (VM 안, startup이 호출)
#  자기 샤드(index %% NW == SHARD) 케이스만 순회. 완료마커 있으면 스킵(재개).
#  풀이 성공 → 원시 평균필드 tgz 를 gs://BUCKET/raw/ 업로드 + done 마커(ClockTime 기록).
#  인자: worker.sh BUCKET SHARD NW
# ============================================================================
BUCKET="$1"; SHARD="$2"; NW="$3"
OF_VER=openfoam2312
source "/usr/lib/openfoam/${OF_VER}/etc/bashrc"
export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1   # 루트 자동실행 허용

cd /opt/cfd/flow || exit 1
for d in case*/; do
  cid="${d%/}"
  idx=$((10#${cid#case}))
  (( idx % NW == SHARD )) || continue
  gsutil -q stat "gs://${BUCKET}/done/${cid}.done" 2>/dev/null && continue   # 이미 완료

  cd "$cid" || continue
  chmod +x Allrun
  ./Allrun > run.log 2>&1

  # 성공 판정: log 끝에 End 또는 최종시간(200) 디렉터리
  if grep -q '^End' log.pimpleFoam 2>/dev/null || [ -d 200 ]; then
    CLOCK=$(grep ClockTime log.pimpleFoam | tail -1 | sed -E 's/.*ClockTime = ([0-9.]+) s.*/\1/')
    tar czf "/tmp/${cid}.tgz" --exclude='processor*' --exclude='log.*' --exclude='run.log' \
        constant system [0-9]* 2>/dev/null
    gsutil -q cp "/tmp/${cid}.tgz" "gs://${BUCKET}/raw/${cid}.tgz"
    echo "${cid} clock=${CLOCK}s $(date -u +%FT%TZ)" | gsutil -q cp - "gs://${BUCKET}/done/${cid}.done"
    rm -f "/tmp/${cid}.tgz"
  else
    echo "${cid} FAIL $(date -u +%FT%TZ)" | gsutil -q cp - "gs://${BUCKET}/failed/${cid}.fail"
  fi

  ./Allclean >/dev/null 2>&1   # 디스크 회수
  cd /opt/cfd/flow
done
echo "== WORKER ${SHARD}/${NW} 샤드 완료 $(date -u) =="
