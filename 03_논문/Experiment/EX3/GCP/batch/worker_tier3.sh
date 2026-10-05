#!/bin/bash
# ============================================================================
#  漁벤져스 · 워커(케이스-리스트판) — Tier3 선별 52케이스 전용
#  기존 worker.sh와 동일하되, CASELIST 파일에 있는 case_id 만 실행.
#  근거: Stage2-B 진단(06_ROM_Stage2B_CNN.md) — 바위·조밀 구성 데이터부족 확정.
#  인자: worker_tier3.sh BUCKET SHARD NW
#  env : CASELIST=/opt/cfd/flow/tier3_ids.txt (한 줄당 case_id), MAXIDX=699
# ============================================================================
BUCKET="$1"; SHARD="$2"; NW="$3"
END="${END:-200}"
MAXIDX="${MAXIDX:-699}"                 # Tier3 포함하려면 699
CASELIST="${CASELIST:-}"                # 비면 기존 worker.sh와 동일 동작
OF_VER=openfoam2312
source "/usr/lib/openfoam/${OF_VER}/etc/bashrc"
export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

# CASELIST 로드 (연관배열 룩업)
declare -A WANT
if [[ -n "$CASELIST" && -f "$CASELIST" ]]; then
  while read -r c; do [[ -n "$c" ]] && WANT["$c"]=1; done < "$CASELIST"
  echo "CASELIST 로드: ${#WANT[@]}개 케이스만 실행"
fi

cd /opt/cfd/flow || exit 1
for d in case*/; do
  cid="${d%/}"
  idx=$((10#${cid#case}))
  (( idx <= MAXIDX )) || continue
  # ★ 케이스-리스트 필터: 목록에 없으면 스킵
  if [[ ${#WANT[@]} -gt 0 && -z "${WANT[$cid]}" ]]; then continue; fi
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
echo "== TIER3 WORKER ${SHARD}/${NW} 샤드 완료 $(date -u) =="
