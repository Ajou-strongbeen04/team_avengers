# local_T3 — Tier3 20케이스 로컬 실행 (漁벤져스 EX3 A층)

> 상위: `../GCP_v2/README.md` · 폐합 `../CFD/CFD_방법론.md` · 매니페스트 `../GCP_v2/cases.csv`
> 목적: GCP_v2 배치(gen179)의 **Tier3 뒤쪽 20건**을 로컬 8코어에서 흡수. GCP는 남은 159건에 집중.

---

## 대상 20케이스

`case0580 0584 0595 0599 0602 0605 0607 0608 0612 0614 0646 0658 0659 0667 0673 0680 0689 0694 0696 0698`

gen179 Tier3 52건 중 **인덱스 최상위 20건**. 워커는 샤드 내 오름차순으로 도니
이 구간이 GCP에서 가장 늦게 도달 → 중복 위험이 가장 낮습니다.

## 폐합 (GCP 배치와 100% 동일 — 변경 금지)

| 항목 | 값 |
|---|---|
| 격자 | blockMesh 108×48×48 (template_case 그대로) |
| 솔버 | pimpleFoam 과도 URANS, SST k-ω + AWT |
| 폭기 | cylinderToCell (0.02,0.035) r=0.01, z 0.02–0.21, Su=2.86 |
| 구조물 | explicitPorositySource DarcyForchheimer (바위 d=1e6·f=1e3 / 식물 d=0·f=Cf) |
| endTime | 200 s (스핀업 40 + 평균창 160) — **건드리면 기존 253건과 정합 깨짐** |
| 분해 | decomposeParDict = 8 (로컬 8코어에 그대로 맞음) |

## 폴더

```
local_T3/
├── run_all.sh          ← 실행 러너 (선점·업로드·재개 포함)
├── cases_local20.txt   ← 실행 목록
├── cases_local20.csv   ← 20건 매니페스트(cases.csv에서 추출)
├── gen_cases.py        ← 재생성용(이미 생성돼 있어 보통 불필요)
├── template_case/      ← 불변 템플릿
├── flow/case0580 … case0698   ← 실행 준비 완료된 20 케이스
└── _state/             ← 완료·실패 기록(자동 생성, 재개용)
```

## 실행

WSL(또는 Linux) 셸에서:

```bash
cd "/mnt/c/Users/김강빈/OneDrive/문서/ajou university/2026/2학기/AI-Integrated-Capston-Design/Claude/03_논문/Experiment/EX3/local_T3"

# 0) 한 건만 먼저 게이트 (약 2시간)
ONLY=case0698 bash run_all.sh

# 1) 통과하면 전량 (약 40시간, 순차)
nohup bash run_all.sh > ~/t3run.log 2>&1 &
tail -f ~/t3run.log
```

OpenFOAM 경로가 다르면: `OF_BASHRC=/경로/etc/bashrc bash run_all.sh`

### 러너가 하는 일

1. GCS `done/${cid}.done` 확인 → 있으면 스킵(GCP가 이미 처리한 경우)
2. **선점 마커 업로드** → GCP 워커가 그 케이스를 건너뜀 (중복 계산 방지)
3. 케이스를 `$WORK`(기본 `~/t3run`, **OneDrive 밖**)로 복사해 `./Allrun`
4. 성공 → `raw/${cid}.tgz` 업로드 + done 마커 최종본으로 덮어쓰기 → 작업본 삭제
   실패 → **선점 마커 삭제**(GCP가 다시 가져감) + `_state/${cid}.fail` + 작업본 유지

중단해도 `_state/`와 GCS 마커 덕에 다시 `bash run_all.sh` 하면 이어서 갑니다.

## 주의

- **OneDrive 안에서 직접 돌리지 마세요.** `processor*/`가 케이스당 수 GB라 동기화가 터집니다.
  러너가 자동으로 `~/t3run`에 복사해 돌립니다.
- `set -e`/`set -u` 상태에서 OpenFOAM bashrc를 소싱하면 셸이 조용히 죽습니다(런북 함정 4).
  러너는 엄격모드를 쓰지 않습니다 — 수동 실행 시에도 동일하게 주의.
- 로컬에서 gcloud 인증이 안 돼 있으면: `gcloud auth login && gcloud config set project cfd-rom`
  인증 없이 돌리려면 `CLAIM=0 bash run_all.sh` (중복 방지 없음, 결과는 나중에 수동 업로드).
- 케이스당 ~2h(EX2 실측 기준). 20건 ≈ 40h. 그 사이 PC 절전 진입 금지.

## 완료 후

`raw/*.tgz`가 GCS에 모이면 나머지와 함께 `../CFD/batch/postprocess.py`(pyvista 96×48×48 리샘플 → npz)로
`dataset/training_dataset/`에 적재합니다.

`CLAIM=0`으로 돌렸다면 완료 후 수동 업로드:

```bash
for c in $(cat cases_local20.txt); do
  gcloud storage cp ~/t3run/${c}.tgz gs://cfd-rom-cfdbatch/raw/${c}.tgz
  echo "${c} LOCAL $(date -u +%FT%TZ)" | gcloud storage cp - gs://cfd-rom-cfdbatch/done/${c}.done
done
```
