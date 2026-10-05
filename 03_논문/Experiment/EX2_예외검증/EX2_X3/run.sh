#!/bin/bash
#==============================================================================
# EX2_X3 · 단계 실행기   (총 ≈7.8 h, 예산 10 h)
#
#   bash run.sh              # stage1 → 고정점 → stage2 → stage3 → stage4 → 집계
#   bash run.sh stage1       # D군 시드런 4개 (Su=1.773)          ≈1.75 h
#   bash run.sh stage2       # D군 자기일관 재실행 4개              ≈1.75 h
#   bash run.sh stage3       # P군 위치 3개                        ≈2.05 h
#   bash run.sh stage4       # M군 medium 앵커 1개                 ≈2.24 h
#   bash run.sh collect      # 집계만
#   bash run.sh d15          # 개별 케이스
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

D_CASES="d18 d15 d12 d09"
P_CASES="p15 p04 p01"
M_CASES="m21"

has_result() {
    # 0/ 외의 **순수 숫자** 시간디렉터리가 있으면 완료로 본다.
    #  ※ 2026-07-29 버그: 예전 구현 `ls -d $1/[0-9]* | grep -qv "/0$"` 은
    #    0.orig 가 [0-9]* 에 걸리고 "/0" 로 끝나지도 않아 **전 케이스를 완료로 오판**했다.
    #    (첫 실행에서 8케이스 전부 스킵됨)
    local t b
    for t in "$1"/[0-9]*; do
        [ -d "$t" ] || continue
        b=$(basename "$t")
        case "$b" in
            0)          continue ;;   # 초기장
            *[!0-9.]*)  continue ;;   # 0.orig / 리터럴 글롭 등 숫자 아닌 것
        esac
        return 0
    done
    return 1
}

run_case() {
    local c="$1"
    if [ ! -d "$c" ]; then
        echo "[ERROR] 케이스 없음: $c  (python3 gen_cases.py 먼저)"; return 1
    fi
    if has_result "$c"; then
        echo "----- $c : 결과 있음 → 스킵(재개) -----"; return 0
    fi
    local su nz lz
    su=$(grep -oE "0 0 [0-9.]+" "$c/system/fvOptions" | awk '{print $3}')
    nz=$(grep -oE "^nz +[0-9]+" "$c/system/blockMeshDict" | awk '{print $2}')
    lz=$(grep -oE "^Lz +[0-9.]+" "$c/system/blockMeshDict" | awk '{print $2}')
    echo
    echo "===== $c   Su=$su  수위=${lz} m  nz=$nz   $(date '+%m-%d %H:%M') ====="
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
    echo "########## stage1 · D군 시드런 (Su=1.773) ##########"
    run_group "$D_CASES" || exit 1
    if [ -n "$PY" ]; then
        echo; echo "########## 수위별 고정점 산출 ##########"
        $PY fixedpoint.py || exit 1
    fi
    [ "$STAGE" = "stage1" ] && exit 0
    ;;&
  stage2|all)
    echo; echo "########## stage2 · D군 자기일관 재실행 ##########"
    if [ -n "$PY" ]; then
        $PY gen_cases.py --stage 2 || exit 1
        # Su 이동이 3 % 를 넘는 수준만 재실행한다(gen_cases 가 목록을 남긴다).
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
  stage3|all)
    echo; echo "########## stage3 · P군 위치 강건성 (d=0.21, Su=1.773) ##########"
    run_group "$P_CASES" || exit 1
    [ "$STAGE" = "stage3" ] && exit 0
    ;;&
  stage4|all)
    echo; echo "########## stage4 · M군 medium 앵커 ##########"
    run_group "$M_CASES" || exit 1
    ;;&
  collect|all)
    if [ -n "$PY" ]; then
        echo; echo "########## 집계 ##########"
        $PY collect.py
    fi
    ;;
  *)
    run_case "$STAGE" || exit 1
    ;;
esac

echo
echo "완료 $(date). 결과를 README.md §5 표에 기입하십시오."
