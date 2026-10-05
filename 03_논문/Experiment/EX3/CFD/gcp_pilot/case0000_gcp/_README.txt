case0000_gcp — GCP 파일럿용 clean 케이스
=========================================
원본 pilot/cases/case0000 과 입력이 100% 동일. 결과/processor*/log.* 는 제외했다.
mesh 는 Allrun 안의 blockMesh + topoSet 로 VM에서 재생성되므로 constant/polyMesh 는 불필요.

포함:  Allrun, 0.orig/, system/(딕셔너리 7종), constant/(transport·turbulenceProperties)
실행:  ../scripts/run_pilot.sh (README_GCP_설정_및_파일럿.md 참고)
