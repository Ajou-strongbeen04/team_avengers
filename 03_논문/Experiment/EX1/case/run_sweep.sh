#!/bin/bash
#==============================================================================
# EX1 어항크기 스윕 (정상 simpleFoam) — 비율 L:B:d=2:1:1 고정, 스케일만 변경
#  각 크기: 이 case를 복사 → blockMesh/topoSet/controlDict 치환 → 실행 → CV(awk)
#  격자 상수(nx100 x ny50 x nz50 = 250k, 큐빅셀 dx=L/100).
#   → 작은 어항은 플룸 고해상, 큰 어항(L>=0.8)은 플룸(20mm) 저해상(스미어링, 보수적).
#  표층/바닥 재폭기·SOD 소스크기 a=1/cellZ=100/L 로 케이스마다 재계산.
#  CV 는 python 없이 zcat+awk 로 산출(윈도우 MSYS 호환).
#  ※ 반드시 OpenFOAM 환경 로드된 창에서 실행.
#==============================================================================
set -e
LIST="0.20 0.25 0.30 0.35 0.40"      # 레짐경계 세분 (0.2~0.4, 0.05 간격)

TPL="$(cd "$(dirname "$0")" && pwd)"
OUT="$TPL/../sweep_runs"
mkdir -p "$OUT"
RES="$OUT/results.csv"
[ -f "$RES" ] || echo "L,B,d,V_L,Lc,cellZ,DO_mean,DO_CV,DO_min,DO_max,U0,Re,Pe_t" > "$RES"   # 있으면 이어붙임

for L in $LIST; do
  # ---- 파생값 계산 (awk 12필드: B D cz cx cy zs zt sur spr sus VL Lc) ----
  set -- $(awk -v L="$L" 'BEGIN{
     B=L/2; D=L/2; cz=L/100; cx=L/2; cy=L/4;
     zs=L/2-cz; zt=L/2+0.0001;
     a=100/L; kLa=2.59e-5*a;
     sur=kLa*8.24; spr=-kLa; sus=-1.5223e-5*a;
     VL=L*B*D*1000; Lc=0.5*sqrt(L*L+B*B);
     printf "%.4f %.4f %.5f %.4f %.4f %.5f %.5f %.6f %.6f %.6f %.1f %.3f",
            B,D,cz,cx,cy,zs,zt,sur,spr,sus,VL,Lc}')
  B=$1; D=$2; CZ=$3; CX=$4; CY=$5; ZS=$6; ZT=$7; SUR=$8; SPR=$9; SUS=${10}; VL=${11}; LC=${12}

  RUN="$OUT/L${L}"
  rm -rf "$RUN"; mkdir -p "$RUN"
  # 템플릿 복사(자기 자신 sweep_runs 제외)
  ( cd "$TPL" && for x in 0.orig constant system Allrun Allclean postProcess; do cp -r "$x" "$RUN"/; done )

  # ---- blockMeshDict: 치수만(격자수 상수) ----
  bm="$RUN/system/blockMeshDict"
  sed -i "s/^Lx .*/Lx  $L;/; s/^Ly .*/Ly  $B;/; s/^Lz .*/Lz  $D;/" "$bm"

  # ---- topoSetDict: 플룸 중심/높이 + 표층/바닥 박스 z ----
  ts="$RUN/system/topoSetDict"
  sed -i "s/(0.2 0.1 0.0)/($CX $CY 0.0)/;   s/(0.2 0.1 0.2)/($CX $CY $D)/;  s/radius 0.01;/radius 0.01;/" "$ts"
  sed -i "s/box (0 0 0.196) (0.4 0.2 0.2001);/box (0 0 $ZS) ($L $B $ZT);/"   "$ts"
  sed -i "s/box (0 0 -0.0001) (0.4 0.2 0.004);/box (0 0 -0.0001) ($L $B $CZ);/" "$ts"

  # ---- controlDict: 재폭기/SOD 소스크기(a=100/L 종속) ----
  cd_="$RUN/system/controlDict"
  sed -i "s/C (0.053355 -6.475e-3);/C ($SUR $SPR);/" "$cd_"
  sed -i "s/C (-3.8058e-3 0);/C ($SUS 0);/"          "$cd_"

  echo "=== L=$L  V=${VL}L  Lc=${LC}  cellZ=${CZ}  (reaer Su=$SUR) ==="
  ( cd "$RUN" && ./Allclean >/dev/null 2>&1 || true; ./Allrun >/dev/null 2>&1 || ./Allrun )

  # ---- CV + 유동 무차원수(U0,Re,Pe_t) — zcat+awk, python 불필요 ----
  LT=$(cd "$RUN" && ls -d [0-9]*/ | grep -v '^0/' | sed 's#/##' | sort -n | tail -1)
  CF="$RUN/$LT/C.gz";   [ -f "$CF" ] || CF="$RUN/$LT/C"
  UF="$RUN/$LT/U.gz";   [ -f "$UF" ] || UF="$RUN/$LT/U"
  NF="$RUN/$LT/nut.gz"; [ -f "$NF" ] || NF="$RUN/$LT/nut"
  STAT=$(zcat -f "$CF" | awk '/nonuniform/{getline;getline;f=1;next} f&&/^\)/{f=0}
        f{n++;v=$1+0;s+=v;ss+=v*v;if(n==1||v<mn)mn=v;if(v>mx)mx=v}
        END{m=s/n;sd=sqrt(ss/n-m*m);printf "%.4f,%.5f,%.4f,%.4f",m,sd/m,mn,mx}')
  U0=$(zcat -f "$UF" | awk '/nonuniform/{getline;getline;f=1;next} f&&/^\)/{f=0}
        f{gsub(/[()]/,"");m=sqrt($1*$1+$2*$2+$3*$3);n++;s+=m} END{printf "%.5f",s/n}')
  NUT=$(zcat -f "$NF" | awk '/nonuniform/{getline;getline;f=1;next} f&&/^\)/{f=0}
        f{n++;s+=$1} END{printf "%.4e",s/n}')
  RE=$(awk -v u="$U0" -v lc="$LC" 'BEGIN{printf "%.0f",u*lc/1e-6}')
  PE=$(awk -v u="$U0" -v lc="$LC" -v nt="$NUT" 'BEGIN{printf "%.1f",u*lc/(2e-9+nt/0.7)}')
  echo "$L,$B,$D,$VL,$LC,$CZ,$STAT,$U0,$RE,$PE" >> "$RES"
  echo "   -> DO(mean,CV,min,max)=$STAT  U0=$U0  Re=$RE  Pe_t=$PE"
done

echo ""; echo "결과: $RES"; echo "----"; column -t -s, "$RES"
#==============================================================================
