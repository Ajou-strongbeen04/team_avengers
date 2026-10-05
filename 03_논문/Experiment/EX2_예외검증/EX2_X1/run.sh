#!/bin/bash
#==============================================================================
# EX2_X · 게이트 원스톱 실행
#
#   bash run.sh          # 필수 케이스만 (case_su168, ≈41분)
#   bash run.sh --all    # + case_su168_T25 (수온 분리, ≈82분)
#
# 대조군 study/coarse_0.02 는 이미 완주돼 있어 다시 안 돈다.
# 실행: 파일럿 돌린 그 OpenFOAM 창에서
#   bash run.sh 2>&1 | tee run.log
#==============================================================================
HERE="$(cd "$(dirname "$0")" && pwd)"
BASE="$HERE/../EX2/CFD/study/coarse_0.02"

if [ ! -d "$BASE/200" ]; then
    echo "[ERROR] 대조군 결과 없음: $BASE/200"
    echo "        study/coarse_0.02 가 완주돼 있어야 합니다."
    exit 1
fi
echo "[ok] 대조군 확인: $BASE/200"

( cd "$HERE/case_su168" && ./Allrun ) || exit 1

if [ "$1" = "--all" ]; then
    ( cd "$HERE/case_su168_T25" && ./Allrun ) || exit 1
    echo; echo "===== 최종 3자 비교 ====="
    python3 "$HERE/compare.py" "$BASE" "$HERE/case_su168" "$HERE/case_su168_T25"
fi

echo
echo "완료 $(date). 판정 결과를 README.md §4 표에 기입하십시오."
