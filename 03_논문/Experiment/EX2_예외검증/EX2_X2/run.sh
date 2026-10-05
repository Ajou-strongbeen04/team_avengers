#!/bin/bash
#==============================================================================
# EX2_X2 · simpleFoam 대조 원스톱 실행
#
#   bash run.sh              # 두 케이스 다 (sf_su286 + sf_su168, ≈10~20분)
#   bash run.sh sf_su286     # 한 케이스만
#   bash run.sh --compare    # 이미 돌아 있으면 판정만 다시
#
# 짝(pimpleFoam)은 이미 완주돼 디스크에 있고 다시 안 돈다:
#   ../EX2/CFD/study/coarse_0.02   (Su 2.86)
#   ../EX2_X1/case_su168     (Su 1.684)
#
# 실행: 파일럿 돌린 그 OpenFOAM 창에서
#   bash run.sh 2>&1 | tee run.log
#==============================================================================
HERE="$(cd "$(dirname "$0")" && pwd)"
P286="$HERE/../EX2/CFD/study/coarse_0.02"
P168="$HERE/../EX2_X1/case_su168"
CMP="$HERE/../EX2_X1/compare.py"

# --- numpy 되는 python 찾기 (Windows Store 스텁 회피) ---
PY=""
for c in python3 python py; do
    if command -v $c >/dev/null 2>&1 && $c -c "import numpy" >/dev/null 2>&1; then
        PY=$c; break
    fi
done
[ -z "$PY" ] && echo "[WARN] numpy 되는 python 없음 - 판정은 수동으로 하십시오."

# --- 짝 존재 확인 ---
for p in "$P286" "$P168"; do
    if [ ! -d "$p" ]; then echo "[ERROR] 짝 없음: $p"; exit 1; fi
    if ! ls -d "$p"/[0-9]* 2>/dev/null | grep -qv "/0$"; then
        echo "[ERROR] 짝이 아직 안 돌았습니다: $p"; exit 1
    fi
done
echo "[ok] 짝 두 개 확인 (pimpleFoam 결과 상주)"

RUN_LIST="sf_su286 sf_su168"
[ "$1" = "--compare" ] && RUN_LIST=""
[ -n "$1" ] && [ "$1" != "--compare" ] && RUN_LIST="$1"

for c in $RUN_LIST; do
    ( cd "$HERE/$c" && ./Allrun ) || exit 1
done

if [ -n "$PY" ]; then
    echo; echo "############ 판정 1 · 같은 Su(2.86)에서 솔버 대조 ############"
    $PY "$CMP" "$P286" "$HERE/sf_su286"

    echo; echo "############ 판정 2 · 같은 Su(1.684)에서 솔버 대조 ############"
    $PY "$CMP" "$P168" "$HERE/sf_su168"

    echo; echo "############ 판정 3 · simpleFoam 내부 Su 섭동 (지수 n 재현) ############"
    echo "   pimpleFoam 실측 n = 0.5064 (2.860→1.684). simpleFoam 이 같은 n 을 주는가?"
    $PY "$CMP" "$HERE/sf_su286" "$HERE/sf_su168"
fi

echo
echo "완료 $(date). 판정 결과를 README.md §4 표에 기입하십시오."
