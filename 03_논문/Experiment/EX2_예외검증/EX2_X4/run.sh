#!/bin/bash
#==============================================================================
# EX2_X4 · z_start 스윕 실행기
#
#   bash run.sh              # stage1 → 고정점 → stage2 → 집계
#   bash run.sh stage1       # Z군 시드런 (미완 케이스만)        z14·z17 ≈1.37 h
#   bash run.sh stage2       # Z군 자기일관 재실행               ≤1.37 h
#   bash run.sh collect      # 집계만 (0-D 레버 표)
#   bash run.sh z08          # 개별 케이스
#
# 3-D K_La 는 별도:  python3 run_reaer.py --group m      (kappa 분모, 최우선)
#                    python3 run_reaer.py --group z
#
# 이미 끝난 케이스(시간디렉터리 보유)는 자동 스킵된다. 중단 후 재개 안전.
# 실행: 파일럿 돌린 그 OpenFOAM 창에서
#   bash run.sh 2>&1 | tee run.log
#==============================================================================
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE" || exit 1

# --- numpy 되는 python 찾기 (Windows Store 스텁 회피) ---
PY=""
for c in python3 python py; do
    if command -v $c >/dev/null 2>&1 && $c -c "import numpy" >/dev/null 2>&1; then
        PY=$c; break
    fi
done
[ -z "$PY" ] && echo "[WARN] numpy 되는 python 없음 - 고정점/집계는 수동으로."

# --- OpenFOAM 환경 ---
if [ -z "$WM_PROJECT_DIR" ]; then
    echo "[ERROR] OpenFOAM 환경이 안 잡혔습니다. bashrc 를 source 한 창에서 도십시오."
    exit 1
fi
. "$WM_PROJECT_DIR/bin/tools/RunFunctions"

Z_CASES="z05 z08 z11 z14 z17"

has_result() {
    # 0/ 외의 **순수 숫자** 시간디렉터리가 있으면 완료로 본다.
    #  ※ 0.orig 를 시간디렉터리로 오판하면 전 케이스가 스킵된다(EX2_X3 실제 사고).
    local t b
    for t in "$1"/[0-9]*; do
        [ -d "$t" ] || continue
        b=$(basename "$t")
        case "$b" in
            0)          continue ;;   # 초기장
            *[!0-9.]*)  continue ;;   # 0.orig / 리터럴 글롭 등
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

run_group() {
    for c in $1; do run_case "$c" || return 1; done
}

STAGE="${1:-all}"

case "$STAGE" in
  stage1|all)
    echo "########## stage1 · Z군 시드런 (신규 수준만, Su=1.773) ##########"
    if [ ! -d z17 ]; then
        [ -n "$PY" ] && $PY gen_cases.py || \
            { echo "[ERROR] 케이스 미생성"; exit 1; }
    fi
    run_group "$Z_CASES" || exit 1
    if [ -n "$PY" ]; then
        echo; echo "########## z_start 별 고정점 산출 ##########"
        $PY fixedpoint.py || exit 1
    fi
    [ "$STAGE" = "stage1" ] && exit 0
    ;;&
  stage2|all)
    echo; echo "########## stage2 · Z군 자기일관 재실행 ##########"
    if [ -n "$PY" ]; then
        $PY gen_cases.py --stage 2 || exit 1
        TODO=$(cat stage2_todo.txt 2>/dev/null)
        if [ -z "$TODO" ]; then
            echo "  → 재실행 대상 없음. stage2 건너뜀."
        else
            for c in $TODO; do
                rm -rf "$c"/postProcessing "$c"/0 "$c"/log.*
                for t in "$c"/[0-9]*; do
                    b=$(basename "$t")
                    case "$b" in 0.orig) continue ;; *[!0-9.]*) continue ;; esac
                    rm -rf "$t"
                done
            done
            run_group "$TODO" || exit 1
        fi
        echo; $PY fixedpoint.py --verify
    else
        echo "[skip] python 없음 - 수동: gen_cases.py --stage 2 후 재실행"
    fi
    [ "$STAGE" = "stage2" ] && exit 0
    ;;&
  collect|all)
    if [ -n "$PY" ]; then
        echo; echo "########## 집계 (0-D 레버 표) ##########"
        $PY collect.py
        echo
        echo "  다음 (3-D):  $PY run_reaer.py --group m    # kappa 분모, 최우선"
        echo "               $PY run_reaer.py --group z"
    fi
    ;;
  *)
    run_case "$STAGE" || exit 1
    ;;
esac

echo
echo "완료 $(date). 결과를 README.md §4 표에 기입하십시오."
