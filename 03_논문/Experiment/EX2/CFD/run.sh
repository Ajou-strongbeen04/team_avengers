#!/bin/bash
#==============================================================================
# EX2 CFD · 유동해 실행기 (OpenFOAM)
#
#   bash run.sh              # 3케이스 stage1 -> 고정점 -> stage2 (전체)
#   bash run.sh stage1       # stage1 시드런만
#   bash run.sh fp           # 고정점 산출 + stage2 fvOptions 갱신 (실행 안 함)
#   bash run.sh stage2       # stage2 재실행 대상만
#   bash run.sh e08          # 개별 케이스
#   bash run.sh verify       # 자기일관 잔차 검정
#
# 스칼라(재폭기)는 OpenFOAM 없이 파이썬으로 돈다:
#   python3 run_reaer.py     # 5런 전부 -> kla_cfd.csv
#   python3 compare_exp.py   # 실측 대조표
#
# 이미 끝난 케이스(시간디렉터리 보유)는 자동 스킵. 중단 후 재개 안전.
# 실행:  bash run.sh 2>&1 | tee run.log
#==============================================================================
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE" || exit 1

CASES="e02 e08 e17"

PY=""
for c in python3 python py; do
    if command -v $c >/dev/null 2>&1 && $c -c "import numpy" >/dev/null 2>&1; then
        PY=$c; break
    fi
done
[ -z "$PY" ] && { echo "[ERROR] numpy 되는 python 이 없습니다."; exit 1; }

if [ -z "$WM_PROJECT_DIR" ]; then
    echo "[ERROR] OpenFOAM 환경이 안 잡혔습니다. bashrc 를 source 한 창에서 도십시오."
    echo "        예) source /opt/openfoam12/etc/bashrc"
    exit 1
fi
. "$WM_PROJECT_DIR/bin/tools/RunFunctions"

has_result() {
    local t b
    for t in "$1"/[0-9]*; do
        [ -d "$t" ] || continue
        b=$(basename "$t")
        case "$b" in
            0)          continue ;;
            *[!0-9.]*)  continue ;;
        esac
        return 0
    done
    return 1
}

run_case() {
    local c="$1"
    [ -d "$c" ] || { echo "[ERROR] 케이스 없음: $c  ($PY gen_cases.py 먼저)"; return 1; }
    if has_result "$c"; then
        echo "----- $c : 결과 있음 -> 스킵(재개) -----"; return 0
    fi
    local su z0
    su=$(grep -oE "0 0 [0-9.]+" "$c/system/fvOptions" | awk '{print $3}')
    z0=$(grep -oE "point1 \([0-9.]+ [0-9.]+ [0-9.]+\)" "$c/system/topoSetDict" \
         | head -1 | grep -oE "[0-9.]+\)" | tr -d ')')
    echo
    echo "===== $c   Su=$su   z_start=${z0} m   $(date '+%m-%d %H:%M') ====="
    (
        cd "$c" || exit 1
        rm -rf constant/polyMesh processor* log.*
        restore0Dir
        runApplication blockMesh                || exit 1
        runApplication topoSet                  || exit 1
        runApplication decomposePar             || exit 1
        runParallel "$(getApplication)"         || exit 1
        runApplication reconstructPar -latestTime || exit 1
        rm -rf processor*
        grep -E "ExecutionTime" log.pimpleFoam | tail -1
    ) || { echo "[ERROR] $c 실패"; return 1; }
    return 0
}

clear_case() {   # stage2 재실행 준비 — 결과만 지우고 dict 는 남긴다
    local c="$1" t b
    rm -rf "$c"/postProcessing "$c"/0 "$c"/log.*
    for t in "$c"/[0-9]*; do
        [ -d "$t" ] || continue
        b=$(basename "$t")
        case "$b" in 0.orig) continue ;; *[!0-9.]*) continue ;; esac
        rm -rf "$t"
    done
}

do_stage1() {
    [ -d e02 ] || $PY gen_cases.py || return 1
    for c in $CASES; do run_case "$c" || return 1; done
}

do_fp() {
    echo; echo "########## alpha_g 고정점 산출 ##########"
    $PY fixedpoint.py || return 1
    echo; echo "########## stage2 fvOptions 갱신 ##########"
    $PY gen_cases.py --stage 2 || return 1
}

do_stage2() {
    TODO=$(cat stage2_todo.txt 2>/dev/null)
    if [ -z "$TODO" ]; then
        echo "  -> 재실행 대상 없음 (전 케이스 3 % 이내 자기일관)."
    else
        for c in $TODO; do clear_case "$c"; done
        for c in $TODO; do run_case "$c" || return 1; done
    fi
    echo; $PY fixedpoint.py --verify
}

case "${1:-all}" in
  all)     do_stage1 && do_fp && do_stage2 || exit 1 ;;
  stage1)  do_stage1 || exit 1 ;;
  fp)      do_fp || exit 1 ;;
  stage2)  do_stage2 || exit 1 ;;
  verify)  $PY fixedpoint.py --verify ;;
  *)       run_case "$1" || exit 1 ;;
esac

echo
echo "완료 $(date)."
echo "  다음:  $PY run_reaer.py      # 가상 재폭기 5런 (OpenFOAM 불필요)"
echo "         $PY compare_exp.py    # 실측 정량비교표"
