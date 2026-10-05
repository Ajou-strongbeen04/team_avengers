# GCP 파일럿 — 설정법부터 실행까지 (漁벤져스 / EX3)

목적: **case0000과 동일한 케이스를 GCP Spot VM에서 1회 돌려**, 클라우드 코어의 실제
속도비 `f`와 케이스당 실비를 측정한다. 이 실측값으로 700케이스 총비용과 $300 크레딧
커버 범위를 확정한 뒤 본 배치로 스케일업한다. (견적만으로는 7800X3D의 V-cache 이점 탓에
클라우드 속도를 알 수 없음 → 파일럿이 필수.)

- 파일럿 케이스: `case0000_gcp/` (입력만, 결과·processor·로그 제거. mesh는 VM에서 재생성)
- 스크립트: `scripts/` (provision_openfoam.sh · run_pilot.sh · create_vm.sh · fetch_and_teardown.sh)
- 예상 비용: 파일럿 1회 = **약 $0.2~0.5** (VM 1대 1시간 미만)

---

## 0. 사전 준비 (최초 1회)

1. **결제·크레딧 확인** — [console.cloud.google.com/billing](https://console.cloud.google.com/billing) 에서
   $300 무료 크레딧(90일)이 결제계정에 붙어 있는지 확인. 신용카드 등록은 되어 있어야 하나
   크레딧 소진 전엔 청구되지 않음.
2. **프로젝트 생성** — 콘솔 상단에서 새 프로젝트(예: `eobenjeoseu-cfd`) 생성 후 결제계정 연결.
3. **Compute Engine API 활성화** —
   [console.cloud.google.com/apis/library/compute.googleapis.com](https://console.cloud.google.com/apis/library/compute.googleapis.com)
   에서 사용 설정.
4. **(선택) Spot vCPU 할당량 확인** — IAM & Admin → Quotas 에서 리전 `us-central1` 의
   *Preemptible CPUs* 가 16 이상인지 확인(파일럿엔 16이면 충분, 본 배치 땐 상향 요청).

> 리전은 `us-central1`(미국) 권장. 배치 CFD는 지연시간이 무관하고 Spot 단가가 가장 싸다.
> 한국 위치는 **결과 다운로드(egress)** 에만 영향 → VM 안에서 후처리까지 끝내고 축약 데이터만
> 내려받으면 무시할 수준. 교차리전 전송이 싫으면 `asia-northeast3`(서울, 컴퓨트 ~+10%)로 바꿔도 됨.

---

## 1. gcloud 준비 (둘 중 하나)

- **A. Cloud Shell (권장, 설치 불필요)** — 콘솔 우상단 `>_` 아이콘 클릭. 브라우저 터미널에
  gcloud가 이미 설치되어 있고 임시 스토리지도 있음. Windows 사용자에게 가장 간단.
- **B. 로컬 설치** — [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) 설치 후 PowerShell에서:
  ```
  gcloud auth login
  gcloud config set project <PROJECT_ID>
  ```

이후 명령은 Cloud Shell / PowerShell / bash 어디서든 동일하게 동작.

---

## 2. Spot VM 생성

환경변수 지정 후 `create_vm.sh` 실행 (또는 아래 gcloud 명령을 그대로 복붙):

```bash
export PROJECT=<PROJECT_ID>
export ZONE=us-central1-a
export VM=of-pilot
export MACHINE=c2d-highcpu-16      # 8물리코어/16vCPU/32GB
bash scripts/create_vm.sh
```

수동 실행 버전:
```bash
gcloud compute instances create of-pilot \
  --project=<PROJECT_ID> --zone=us-central1-a \
  --machine-type=c2d-highcpu-16 \
  --provisioning-model=SPOT --instance-termination-action=STOP \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB --boot-disk-type=pd-balanced
```

> 왜 `c2d-highcpu-16`? 500k 셀은 RAM 1GB 미만 → 메모리 큰 standard 불필요, highcpu(2GB/vCPU)면
> 충분하고 더 싸다. 8물리코어 = 로컬과 동일한 8랭크 분해를 그대로 이식.

---

## 3. 케이스 업로드

로컬(또는 Cloud Shell)에서 이 폴더의 `case0000_gcp` 를 tar로 묶어 VM에 전송:

```bash
# 이 gcp_pilot 폴더 위치에서
tar czf case0000_gcp.tgz -C . case0000_gcp
gcloud compute scp case0000_gcp.tgz of-pilot:~/ --project=<PROJECT_ID> --zone=us-central1-a
gcloud compute scp --recurse scripts of-pilot:~/ --project=<PROJECT_ID> --zone=us-central1-a
```

> Cloud Shell을 쓰면, 이 폴더를 먼저 Cloud Shell에 업로드(⋮ → Upload)한 뒤 위 tar/scp를 실행.

---

## 4. 프로비저닝 + 실행 (VM 접속)

```bash
gcloud compute ssh of-pilot --project=<PROJECT_ID> --zone=us-central1-a
```

VM 셸 안에서:
```bash
tar xzf case0000_gcp.tgz
chmod +x scripts/*.sh

# 4-1. OpenFOAM 설치 (로컬과 같은 버전으로. 기본 openfoam2312)
OF_VER=openfoam2312 ./scripts/provision_openfoam.sh

# 4-2. 파일럿 실행 + 타이밍/비용 자동계산 (요약을 파일로도 저장)
#      인자: [CASE_DIR] [MACHINE_VCPU] [PRICE/vCPU-hr]
./scripts/run_pilot.sh ~/case0000_gcp 16 0.010 | tee ~/pilot_summary.txt
```

`run_pilot.sh` 가 출력하는 값:
- **솔버 ClockTime(벽시간)** — 반복되는 계산량의 실측치
- **속도비 f** = 7200s(로컬 2h) / ClockTime  → 1.0이면 로컬과 동일, <1이면 클라우드가 느림
- **케이스당 청구 vCPU-hr** = 16 × (ClockTime/3600)
- **케이스당 비용 / 700케이스 총비용 / $300로 가능한 케이스 수**

---

## 5. 결과 회수 + VM 삭제 (★과금 중지)

```bash
# 로컬/Cloud Shell 에서
export PROJECT=<PROJECT_ID>; export ZONE=us-central1-a; export VM=of-pilot
bash scripts/fetch_and_teardown.sh
```
→ `pilot_result/` 에 `log.pimpleFoam`, `pilot_summary.txt` 가 저장되고 VM이 삭제된다.

> **중요:** Spot이라도 켜져 있으면 과금된다. 파일럿이 끝나면 즉시 삭제할 것.
> `--instance-termination-action=STOP` 이라 선점 시 자동 종료(디스크 요금만 소액 유지)되지만,
> 명시적으로 삭제해야 완전히 멈춘다.

---

## 6. 파일럿 후 판단 (이 숫자로 본 배치 확정)

측정된 `케이스당 비용` × 700 이 실제 총비용. 아래 순서로 최적화:

1. **16랭크(HT) 비교** — `decomposeParDict` 의 `numberOfSubdomains` 를 16으로 바꿔 재실행.
   같은 16 vCPU 과금이므로 벽시간이 줄면 그만큼 싸진다.
2. **C3D 비교** — `MACHINE=c3d-highcpu-16` 으로 VM 재생성 후 동일 실행. Genoa가 코어당 빨라
   vCPU-hr가 줄면 총액이 오히려 쌀 수 있다.
3. **endTime 재검토** — 프로브 시계열에서 준정상 도달이 200s보다 빠르면 평균창 단축 →
   비용에 선형으로 직결되는 최대 단일 레버.
4. **본 배치 스케일업** — 1주 마감 기준 ~18개 동시 슬롯(≈288 vCPU) 필요. 예: `c2d-highcpu-112`
   Spot 3대 + flock 잡큐(케이스 리스트 소비, 선점 시 `-latestTime` 재시작).

---

## 참고 · 케이스 사양 (case0000 동일)

| 항목 | 값 |
|---|---|
| 솔버 | `pimpleFoam` (과도 URANS, SST k-ω, AWT) |
| 셀 수 | ~500k (blockMesh+topoSet로 VM에서 재생성) |
| 분해 | scotch, 8 subdomains |
| 물리시간 | endTime 200s, adjustTimeStep maxCo 1.0, maxDeltaT 0.02 |
| 소스항 | `vectorSemiImplicitSource` (plume cellZone, U +z 2.86) |
| 평균 | fieldAverage timeStart 40s (UMean 등 → Stage B 입력) |
| 로컬 기준 | 7800X3D 8코어 2h/케이스 = 16 물리코어-hour |
