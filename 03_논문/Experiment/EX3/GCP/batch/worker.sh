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
