#!/bin/bash
# ============================================================================
#  漁벤져스 · GCP 파일럿 프로비저닝 (VM 안에서 1회 실행)
#  Ubuntu 22.04 에 ESI OpenFOAM(openfoam.com) 설치.
#  ※ 로컬에서 쓰는 OpenFOAM 버전과 맞출 것. (딕셔너리가 ESI 단축 libs 문법)
#     .org 버전을 쓴다면 아래 저장소를 openfoam.org 방식으로 교체.
# ============================================================================
set -euo pipefail

OF_VER="${OF_VER:-openfoam2312}"      # 로컬과 동일 버전으로 맞추세요

echo "== apt 업데이트 & 빌드/실행 의존성 =="
sudo apt-get update -y
sudo apt-get install -y curl ca-certificates time

echo "== OpenFOAM(ESI) 저장소 추가 =="
curl -fsSL https://dl.openfoam.com/add-debian-repo.sh | sudo bash

echo "== ${OF_VER} 설치 =="
sudo apt-get update -y
sudo apt-get install -y "${OF_VER}-default"

# 로그인 셸에서 자동 소싱되도록 등록
BASHRC="/usr/lib/openfoam/${OF_VER}/etc/bashrc"
if ! grep -q "${OF_VER}/etc/bashrc" "$HOME/.bashrc"; then
  echo "source ${BASHRC}" >> "$HOME/.bashrc"
fi

echo "== 설치 확인 =="
set +u; source "${BASHRC}"; set -u   # bashrc 가 set -u 에서 unbound variable 로 죽는 것 방지
which pimpleFoam blockMesh foamDictionary
echo "OpenFOAM 준비 완료: ${OF_VER}"
