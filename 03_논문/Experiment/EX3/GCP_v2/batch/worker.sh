#!/bin/bash
# ============================================================================
#  漁벤져스 · 워커 루프 (GCP_v2 / cfd-rom 계정 · 케이스-리스트판)
#  gen179.txt(남은 Tier2 127 + Tier3 52)에 있는 case_id 만 실행. 나머지 인프라 동일.
#  근거: Stage2-B 데이터병목 확정(../06_ROM_Stage2B_CNN.md).
#  인자: worker.sh BUCKET SHARD NW   env: CASELIST, MAXIDX(기본699), END(기본200)
# ============================================================================
BUCKET="$1"; SHARD="$2"; NW="$3"
END="${END:-200}"
MAXIDX="${MAXIDX:-699}"                        # Tier3 포함
CASELIST="${CASELIST:-/opt/cfd/gen179.txt}"    # 실행할 case_id 목록(한 줄당 1개)
OF_VER=openfoam2312
source "/usr/lib/openfoam/${OF_VER}/etc/bashrc"
export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

declare -A WANT
if [[ -n "$CASELIST" && -f "$CASELIST" ]]; then
  while read -r c; do c="${c//[$'\r\n ']/}"; [[ -n "$c" ]] && WANT["$c"]=1; done < "$CASELIST"
  echo "CASELIST 로드: ${#WANT[@]}개만 실행 ($CASELIST)"
else
  echo "!! CASELIST 없음($CASELIST) → 전체 실행 위험. 중단." ; exit 1
fi

cd /opt/cfd/flow || exit 1
for d in case*/; do
  cid="${d%/}"
  idx=$((10#${cid#case}))
  (( idx <= MAXIDX )) || continue
  [[ -n "${WANT[$cid]}" ]] || continue          # ★ 목록에 없으면 스킵
  (( idx % NW == SHARD )) || continue
  gsutil -q stat "gs://${BUCKET}/done/${cid}.done" 2>/dev/null && continue

  cd "$cid" || continue
  chmod +x Allrun
  ./Allrun > run.log 2>&1

  if grep -q '^End' log.pimpleFoam 2>/dev/null || [ -d "$END" ]; then
    CLOCK=$(grep ClockTime log.pimpleFoam | tail -1 | sed -E 's/.*ClockTime = ([0-9.]+) s.*/\1/')
    tar czf "/tmp/${cid}.tgz" --exclude='processor*' --exclude='log.*' --exclude='run.log' \
        constant system [0-9]* 2>/dev/null
    gsutil -q cp "/tmp/${cid}.tgz" "gs://${BUCKET}/raw/${cid}.tgz"
    echo "${cid} clock=${CLOCK}s tEnd=${END} tAvg=40-${END} $(date -u +%FT%TZ)" \
      | gsutil -q cp - "gs://${BUCKET}/done/${cid}.done"
    rm -f "/tmp/${cid}.tgz"
  else
    echo "${cid} FAIL $(date -u +%FT%TZ)" | gsutil -q cp - "gs://${BUCKET}/failed/${cid}.fail"
  fi

  ./Allclean >/dev/null 2>&1
  cd /opt/cfd/flow
done
echo "== GCP_v2 WORKER ${SHARD}/${NW} 샤드 완료 $(date -u) =="
