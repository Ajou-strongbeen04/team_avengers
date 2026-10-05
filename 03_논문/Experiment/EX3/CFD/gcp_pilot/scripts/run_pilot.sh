#!/bin/bash
# ============================================================================
#  漁벤져스 · GCP 파일럿 실행 & 타이밍/비용 측정 (VM 안에서 실행)
#  ★ 엄격모드(set -e/-u) 안 씀: OpenFOAM bashrc 소싱이 set -e 에서 셸을
#     종료시키는 문제(실전 확인) 때문. 아래 방식이 검증된 동작 버전.
#
#  사용:
#    ./run_pilot.sh [CASE_DIR] [MACHINE_VCPU] [PRICE_USD_per_vCPU_hr]
#  예:
#    ./run_pilot.sh ~/case0000_gcp 16 0.010
# ============================================================================

CASE_DIR="${1:-$HOME/case0000_gcp}"
MACHINE_VCPU="${2:-16}"
PRICE="${3:-0.010}"
LOCAL_WALL_S="${LOCAL_WALL_S:-7200}"   # 로컬 7800X3D 8코어 기준 벽시간(2h)
N_CASES="${N_CASES:-700}"
OF_VER="${OF_VER:-openfoam2312}"

# OpenFOAM 환경 (엄격모드 없이 소싱해야 함)
source "/usr/lib/openfoam/${OF_VER}/etc/bashrc"

cd "$CASE_DIR" || { echo "case dir 없음: $CASE_DIR"; exit 1; }
chmod +x ./Allrun 2>/dev/null

NP=$(foamDictionary -entry numberOfSubdomains -value system/decomposeParDict 2>/dev/null)

echo "=================== 하드웨어 ==================="
lscpu | grep -E 'Model name|^CPU\(s\)|Thread\(s\) per core|Core\(s\)|MHz'
echo "분해 랭크(NP)      : $NP"
echo "머신 총 vCPU(과금) : $MACHINE_VCPU"
echo "==============================================="

echo ">> Allrun 시작 ($(date))"
T0=$(date +%s)
./Allrun
T1=$(date +%s)
WALL_TOTAL=$((T1 - T0))

# 솔버 순수 벽시간(반복되는 계산량의 실측치)
CLOCK=$(grep -E "ClockTime" log.pimpleFoam | tail -1 | sed -E 's/.*ClockTime = ([0-9.]+) s.*/\1/')
[ -z "$CLOCK" ] && CLOCK="$WALL_TOTAL"

f=$(awk -v l="$LOCAL_WALL_S" -v c="$CLOCK" 'BEGIN{printf "%.3f", l/c}')
VCPUH=$(awk -v v="$MACHINE_VCPU" -v c="$CLOCK" 'BEGIN{printf "%.2f", v*c/3600.0}')
COST1=$(awk -v x="$VCPUH" -v p="$PRICE" 'BEGIN{printf "%.3f", x*p}')
COSTN=$(awk -v x="$VCPUH" -v p="$PRICE" -v n="$N_CASES" 'BEGIN{printf "%.1f", x*p*n}')
FITS=$(awk -v x="$VCPUH" -v p="$PRICE" 'BEGIN{printf "%d", 300.0/(x*p)}')

echo ""
echo "############## 파일럿 결과 요약 ##############"
echo " 전체 Allrun 벽시간      : ${WALL_TOTAL}s"
echo " 솔버 ClockTime(벽시간)  : ${CLOCK}s"
echo " 로컬(2h) 대비 속도비 f  : ${f}   (1.0=동일, <1=클라우드가 느림)"
echo " 케이스당 청구 vCPU-hr   : ${VCPUH}"
echo " 케이스당 비용           : \$${COST1}"
echo " 700케이스 예상 총비용   : \$${COSTN}   (price=\$${PRICE}/vCPU-hr)"
echo " \$300 크레딧으로 가능 수 : ${FITS} 케이스"
echo "#############################################"
