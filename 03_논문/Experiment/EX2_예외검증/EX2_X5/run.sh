#!/bin/bash
#==============================================================================
# EX2_X5 · kappa(z=0.02) 이상 규명 실행기
#
#   bash run.sh P            # ★★ 실험 실제 폭기축 (0.035,0.195) z-스윕 3점 — kappa 절대값 교정
#   bash run.sh C            # ★  바닥 차폐 시험 (가설 b 직접 시험)
#   bash run.sh M            #    medium 격자 z08·z17 (가설 c)
#   bash run.sh B            #    바닥 근방 coarse 스윕 (z=0.01/0.03/0.04/0.06)
#   bash run.sh all          # P → C → M → B
#   bash run.sh collect      # 집계만
#   bash run.sh mz17         # 개별 케이스
#
# 3-D K_La 는 별도 (kappa 의 분모는 3-D 다):
#   python3 run_reaer.py --group P     # 실험 위치 — kappa 분모 교정
#   python3 run_reaer.py --group C
#   python3 run_reaer.py --group M
#   python3 run_reaer.py --group B
#
# 이미 끝난 케이스(시간디렉터리 보유)는 자동 스킵. 중단 후 재개 안전.
# 실행:  bash run.sh M 2>&1 | tee run_M.log
#==============================================================================
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE" || exit 1

PY=""
for c in python3 python py; do
    if command -v $c >/dev/null 2>&1 && $c -c "import numpy" >/dev/null 2>&1; then
        PY=$c; break
    fi
done
[ -z "$PY" ] && echo "[WARN] numpy 되는 python 없음 - 고정점/집계는 수동으로."

if [ -z "$WM_PROJECT_DIR" ]; then
    echo "[ERROR] OpenFOAM 환경이 안 잡혔습니다. bashrc 를 source 한 창에서 도십시오."
    exit 1
fi
. "$WM_PROJECT_DIR/bin/tools/RunFunctions"

P_CASES="p13z02 p13z08 p13z17"
M_CASES="mz08 mz17"
B_CASES="b01 b03 b04 b06"
C_CASES="c02blk c02blkfp"

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
    if [ ! -d "$c" ]; then
        echo "[ERROR] 케이스 없음: $c  ($PY gen_cases.py 먼저)"; return 1
    fi
    if has_result "$c"; then
        echo "----- $c : 결과 있음 → 스킵(재개) -----"; return 0
    fi
    local su z0
    su=$(grep -oE "0 0 [0-9.]+" "$c/system/fvOptions" | awk '{print $3}')
    z0=$(grep -oE "point1 \([0-9.]+ [0-9.]+ [0-9.]+\)" "$c/system/topoSetDict" \
         | head -1 | grep -oE "[0-9.]+\)" | tr -d ')')
    echo
    echo "===== $c   Su=$su  z_start=${z0} m   $(date '+%m-%d %H:%M') ====="
    (
        cd "$c" || exit 1
        rm -rf constant/polyMesh processor* log.*
        restore0Dir
        runApplication blockMesh      || exit 1
        runApplication topoSet        || exit 1
        runApplication decomposePar   || exit 1
        runParallel "$(getApplication)" || exit 1
        runApplication reconstructPar -latestTime || exit 1
        rm -rf processor*
        grep -E "ExecutionTime" log.pimpleFoam | tail -1
    ) || { echo "[ERROR] $c 실패"; return 1; }
    return 0
}

run_family() {
    local fam="$1" cases="$2"
    echo "########## $fam 군 stage1 시드런 ##########"
    [ -d "$(echo $cases | awk '{print $1}')" ] || \
        { [ -n "$PY" ] && $PY gen_cases.py --family "$fam"; }
    for c in $cases; do run_case "$c" || return 1; done
    if [ -n "$PY" ]; then
        echo; echo "########## 고정점 산출 ##########"
        $PY fixedpoint.py || return 1
        echo; echo "########## stage2 자기일관 재실행 ##########"
        $PY gen_cases.py --family "$fam" --stage 2 || return 1
        TODO=$(cat stage2_todo.txt 2>/dev/null)
        if [ -z "$TODO" ]; then
            echo "  → 재실행 대상 없음 (전 케이스 3 % 이내)."
        else
            for c in $TODO; do
                rm -rf "$c"/postProcessing "$c"/0 "$c"/log.*
                for t in "$c"/[0-9]*; do
                    b=$(basename "$t")
                    case "$b" in 0.orig) continue ;; *[!0-9.]*) continue ;; esac
                    rm -rf "$t"
                done
            done
            for c in $TODO; do run_case "$c" || return 1; done
        fi
        echo; $PY fixedpoint.py --verify
    fi
    return 0
}

STAGE="${1:-M}"
case "$STAGE" in
  P)   run_family P "$P_CASES" || exit 1 ;;
  M)   run_family M "$M_CASES" || exit 1 ;;
  B)   run_family B "$B_CASES" || exit 1 ;;
  C)   run_family C "$C_CASES" || exit 1 ;;
  all) run_family P "$P_CASES" || exit 1
       run_family C "$C_CASES" || exit 1
       run_family M "$M_CASES" || exit 1
       run_family B "$B_CASES" || exit 1 ;;
  collect)
       [ -n "$PY" ] && $PY collect.py ;;
  *)   run_case "$STAGE" || exit 1 ;;
esac

echo
echo "완료 $(date)."
echo "  다음 (3-D · kappa 의 분모):  $PY run_reaer.py --group $STAGE"
echo "  결과를 README.md §4 표에 기입하십시오."
