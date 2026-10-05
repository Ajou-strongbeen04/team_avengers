# EX1 OpenFOAM 케이스 — 어항크기 스윕 (유동 + DO)

OpenFOAM **ESI v2412** · 로컬 실행 · 근거: `../EX1_방법론.md`, `../../CFD_method.md`

> ⚠️ **완료된 실험 기록(historical).** 아래 생물소비 `S_bio`·`R_bio` 및 25 °C 계수는 EX1 당시 상대 스크리닝용 **placeholder**다. **2026-07-16 방향 전환으로 생물 소비/생성은 어항별 BC로 분리·제거**, 수온은 실측값으로 둔다(`../../CFD_method.md` §2.2). EX1 이후엔 이 항들을 쓰지 않으며, 기록 보존용으로 값만 남긴다.

기본 케이스 = 검증용 **1개 크기(L=0.4, B=d=0.2 m, 25°C)**. 파이프라인 검증 후 `run_sweep.sh`로 크기 스윕.

---

## 0. 먼저 — 이 케이스의 성격

- 이 파일들은 **직접 실행해 검증된 게 아니라**(이 환경엔 OpenFOAM 미설치) 방정식·계수·문법을 근거로 정확히 작성한 것. **첫 실행에서 §4 순서로 검증**하고, §5의 버전 민감 3곳을 확인할 것.
- 물리·부호(특히 재폭기 Robin BC)는 별도로 **수치 검증 완료**(§3).

## 1. 파일 구성

```
case/
 0.orig/       U p k omega nut C        (C = DO, codedMixed Robin/SOD)
 constant/     transportProperties(nu)  turbulenceProperties(kOmegaSST, AWT)
 system/       blockMeshDict(파라미터)  topoSetDict(플룸 셀존)
               fvOptions(폭기 부력소스)  controlDict(scalarTransport+fieldAverage)
               fvSchemes  fvSolution
 postProcess/  computeCV.py             (DO 공간 CV·저산소분율, 파서 검증됨)
 Allrun Allclean run_sweep.sh
```

## 2. 물리 모델 요약

- **유동:** pimpleFoam, 비압축 URANS, SST k-ω + **Automatic Wall Treatment**(nutUSpalding/omega 벽함수). z-상향(바닥 z=0, 자유수면 z=Lz).
- **폭기:** 바닥 중앙 20mm 원기둥 플룸(`topoSet` 셀존) 에 **상향 부력 체적력** `F_air/ρ = α_g·g = 0.1962 m/s²` (`fvOptions`, α_g=0.02 placeholder).
- **DO:** `scalarTransport` FO가 phi로 C를 동시 수송(단방향). `D_eff = alphaD·ν + alphaDt·nut`, alphaD=2e-3(분자), alphaDt=1.4286(=1/Sc_t).
  - 플룸 계면소스 `S_air=kL·a·(C*−C)` (semiImplicit, Su/Sp).
  - 생물소비 `S_bio` = Monod 선형화 싱크(Sp=−1.783e-5/s).
  - 수면 재폭기 Robin·바닥 SOD = `codedMixed` BC.

## 3. 25°C 계수 (검증값) 및 Robin BC 부호

| 계수 | 값 | 근거 |
|---|---|---|
| ν | 1.0e-6 m²/s | 상수목록 A |
| D_mol | 2.0e-9 m²/s | 상수목록 A |
| Sc_t | 0.7 | 상수목록 B |
| C*(25) | 8.24 mg/L | Benson–Krause(≈근사 8.35) |
| kL(25) | 2.590e-5 m/s | kL20·1.024⁵ |
| SOD(25) | 1.5223e-5 g/m²·s (54.8 mg/m²·h) | SOD20·1.065⁵ |
| R_bio(25) | 1.3375e-4 g/m³·s | (OCR·ρ_fish+Y·r_nit)·1.08⁵, **ρ_fish=1 g/L 가정** |
| a=6α_g/d_b | 40 /m | α_g=0.02, d_b=3mm |
| kL·a | 1.036e-3 /s | Su=8.537e-3, Sp=−1.036e-3 |

**재폭기 Robin `codedMixed` (미분부호 검증됨):**
조건 `D_eff ∂C/∂n = kL(C*−C)` (n 외향, 수면). mixed BC 로:
`valueFraction = β/(β+deltaCoeffs)`, `refValue = C*`, `refGrad = 0`, `β=kL/D_eff`.
1D 유한체적 검산에서 `D_eff·snGrad` = `kL(C*−C_face)` **정확히 일치**, 미포화 시 O2 유입(+) 방향 확인.
바닥 SOD 는 `valueFraction=0`(순수 Neumann), `refGrad=−SOD/D_eff`.

## 4. 첫 실행 순서 (검증 권장)

```bash
source /usr/lib/openfoam/openfoam2412/etc/bashrc   # 환경(설치경로에 맞게)

# (A) 유동만 먼저: controlDict 의 functions{} 에서 scalarTransportC 블록을 잠시 주석처리
./Allclean && ./Allrun
#  -> blockMesh/topoSet/pimpleFoam 이 도는지, 플룸이 순환류를 만드는지 확인
paraFoam &   # U 로 플룸·재순환·저유속 코너 육안 확인

# (B) DO 켜기: scalarTransportC 주석 해제 후 재실행
./Allclean && ./Allrun
cat log.computeCV          # DO mean / CV / hypoxic fraction
```

수렴/평균 판정: `postProcessing/probesUC` 의 속도 시계열에서 진동(Strouhal)이 감쇠하고
`UMean` 이 정상화되면 그 구간 평균 채택(`controlDict` 의 `timeStart` 를 그 시점으로 맞춤).

## 5. 버전 민감 3곳 (에러 시 여기부터)

1. **`fvOptions`/`scalarSemiImplicitSource` 키**: `injectionRateSuSp { U ((Su)(Sp)); }`
   ↔ 일부 버전은 `sources { U (Su Sp); }`. 에러 나면 교체.
2. **`topoSetDict` `cylinderToCell`**: `point1/point2/radius` ↔ 구버전 `p1/p2/radius`.
3. **`scalarTransport` 확산 키**: `alphaD`/`alphaDt` 인식 여부. 미지원 시 `D`(상수) 지정
   후 난류확산은 fvOptions 로 보완(또는 nut 필드명 지정 방식).

기타: `codedMixed` 첫 실행 시 컴파일(수 초). `libsolverFunctionObjects`·`libfieldFunctionObjects` 로드 확인.

## 6. 메시·플룸 해상 주의

기본 격자 ~4mm 균일 → 플룸 r=10mm ≈ 2.5셀(스크리닝 수준, 다소 스미어링).
- **대형 크기**(L≳0.6)는 고정 20mm 플룸이 상대적으로 작아져 **국부 세분 필요**:
  `topoSet`으로 중앙 컬럼 cellSet → `refineMesh -dict` 2× → 이후 플룸 셀존 선택.
- 바닥 SOD 는 얇은 경계층 → coarse 격자에서 과소해상(레짐 스크리닝엔 무방, 절대 DO엔 세분).
- 대표 크기 1개에서 ×2/×0.5 격자로 CV·Pe 불변(간이 독립성) 확인 권장.

## 7. 크기 스윕

`run_sweep.sh` = 이 case를 템플릿으로 각 크기 사본 생성 → blockMesh/topoSet/probe 치환 → 실행 → CV 집계(`../sweep_runs/results.csv`).

```bash
source .../etc/bashrc
./run_sweep.sh          # 1차 5점(L=0.2~1.0). knee 구간만 뒤에 0.05 세분
```

산출 `results.csv`(L,B,d,mesh,V,Lc,DO_mean,DO_CV,hypoxic_frac) → **CV-vs-L 곡선의 knee** +
가정용 현실성으로 유의미 크기범위 확정 → 확정 L,B,d 를 `../../상수_목록.md` E군 기입.

## 8. 열어둔 가정(문서화용)

- α_g=0.02(부력·계면적) placeholder → 실제 2 L/min·20mm 기준 재산정 또는 실측(절대 DO 캘리브레이션).
- ρ_fish=1 g/L 사육밀도 가정(R_bio) → 목표 어종·사육량으로 조정.
- S_bio Monod 선형화 → 정식 Monod 는 `scalarCodedSource`로 후속 교체 가능.
- EX1은 **상대 스윕**이라 위 절대값 불확실성은 크기 경향(knee) 판정에 1차적으로 무해(전 케이스 동일 고정 시).
