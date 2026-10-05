# GCP 파일럿 실전 런북 (검증된 동작 순서 + 함정)

2026-07-17 실제 구동 성공한 순서. 본 700케이스 배치 스케일업 때도 이 순서/교훈을 재사용.
프로젝트 `cfd-pilot`, 리전 `us-central1-a`, 머신 `c2d-highcpu-16`, OpenFOAM `openfoam2312`(ESI).

---

## 겪은 함정 5가지 (다음엔 바로 피하기)

1. **Cloud Shell ≠ VM.** 프롬프트 `@cloudshell`=게이트웨이, `@of-pilot`=계산 VM. 파일 업로드·gcloud는
   Cloud Shell에서, 설치·실행은 VM 안에서. 헷갈리면 파일이 "없다"고 나온다.
2. **Spot은 선점되어 꺼진다.** 파일럿(몇 시간 연속 측정)은 **온디맨드**로. `--provisioning-model` 빼면 온디맨드.
   (본 배치만 Spot + 재시작 큐.)
3. **VM 재생성 직후 scp는 실패.** 부팅(=sshd 준비)에 30~60초. `port 22 Connection refused` 나오면
   잠시 뒤 scp 재시도. ssh는 그 사이 성공하기도 함.
4. **OpenFOAM bashrc 를 `set -e`/`set -u` 상태에서 소싱하면 셸이 조용히 죽는다.**
   → 반드시 엄격모드 없이 소싱: `bash -c 'source .../etc/bashrc; ...'` 또는 스크립트에서 set -e/-u 미사용.
   (`WM_PROJECT_DIR: unbound variable`, 또는 출력 없이 Exit 1 이 이 증상.)
5. **Allrun 실행권한.** tar로 푼 Allrun은 실행비트가 없을 수 있음 → `chmod +x Allrun` 또는 `bash ./Allrun`.
   ( `sed` 로 스크립트 패치할 때 `\&` 는 리터럴 &, 통째 매치는 `&`. 헷갈리면 python 문자열 replace 사용. )

---

## A. 최초 준비 (1회)
- 결제계정에 $300 크레딧 확인, 프로젝트 `cfd-pilot` 생성·연결.
- Compute Engine API 사용 설정. (`gcloud services enable compute.googleapis.com`)
- Cloud Shell 사용(설치 불필요). 프롬프트 `@cloudshell`.

## B. VM 생성 (온디맨드, Cloud Shell에서)
```bash
gcloud compute instances create of-pilot \
  --project=cfd-pilot --zone=us-central1-a \
  --machine-type=c2d-highcpu-16 \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB --boot-disk-type=pd-balanced
```

## C. 파일 업로드 (Cloud Shell → VM)
1. Cloud Shell 우상단 ⋮ → Upload → Folder 로 `gcp_pilot` 업로드 (→ `~/gcp_pilot/`).
2. 압축·전송 (VM 부팅 30~60초 대기 후):
```bash
cd ~/gcp_pilot
tar czf ~/case0000_gcp.tgz -C . case0000_gcp
gcloud compute scp ~/case0000_gcp.tgz of-pilot:~/ --project=cfd-pilot --zone=us-central1-a
gcloud compute scp --recurse ~/gcp_pilot/scripts of-pilot:~/ --project=cfd-pilot --zone=us-central1-a
```

## D. 접속 + 설치 (VM 안, 프롬프트 @of-pilot)
```bash
gcloud compute ssh of-pilot --project=cfd-pilot --zone=us-central1-a
# --- 이하 VM 안 ---
tar xzf case0000_gcp.tgz
chmod +x scripts/*.sh case0000_gcp/Allrun
OF_VER=openfoam2312 ./scripts/provision_openfoam.sh   # apt로 ESI OpenFOAM 설치(수 분)
```
설치 확인(대화형 셸은 set -u 없어 소싱 OK):
```bash
source /usr/lib/openfoam/openfoam2312/etc/bashrc
which pimpleFoam blockMesh foamDictionary
```

## E. 실행 (검증된 방식 · 분리 실행)
방법 1 — 정리된 스크립트(타이밍·비용 자동계산):
```bash
nohup ./scripts/run_pilot.sh ~/case0000_gcp 16 0.010 > ~/pilot_summary.txt 2>&1 &
echo "PID=$!"
```
방법 2 — Allrun 직접(가장 튼튼, 실전에서 이걸로 성공):
```bash
cd ~/case0000_gcp
nohup bash -c 'source /usr/lib/openfoam/openfoam2312/etc/bashrc; ./Allrun' > ~/run.log 2>&1 &
echo "PID=$!"
```
모니터:
```bash
tail -f ~/case0000_gcp/log.pimpleFoam   # Time = ... 가 200으로 상승하면 진행중
```
`Restore 0/ → blockMesh → topoSet → decomposePar → pimpleFoam (8 processes)` 순으로 뜨면 정상.

## F. 완료 후 타이밍/비용
```bash
grep -E 'ClockTime|ExecutionTime' ~/case0000_gcp/log.pimpleFoam | tail -3
```
- 속도비 f = 7200 / (Time=200 도달 ClockTime[s])
- 케이스당 청구 vCPU-hr = 16 × ClockTime/3600
- 700케이스 총비용 = (케이스당 vCPU-hr) × 700 × $0.010(Spot 대략가)

## G. 결과 회수 + VM 삭제 (★과금 중지)
```bash
# Cloud Shell 에서
gcloud compute scp of-pilot:~/case0000_gcp/log.pimpleFoam ./ --project=cfd-pilot --zone=us-central1-a
gcloud compute instances delete of-pilot --project=cfd-pilot --zone=us-central1-a --quiet
```

---

## 다음 비교 (파일럿 기준선 확보 후)
- **16랭크(HT):** `system/decomposeParDict` 의 `numberOfSubdomains` 8→16 후 재실행. 같은 16 vCPU 과금이라 벽시간 줄면 그만큼 저렴.
- **C3D:** VM을 `c3d-highcpu-16` 으로 재생성 후 동일 실행. Genoa가 코어당 빨라 총 vCPU-hr↓ 가능.
- **본 배치:** Spot 다대 + flock 잡큐(케이스 리스트 소비, 선점 시 `-latestTime` 재시작).
