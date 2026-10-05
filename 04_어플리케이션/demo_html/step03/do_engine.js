/* ===========================================================================
 *  do_engine.js — 용존산소(DO) 물리 엔진   rev.C (2026-08-01)
 *
 *  漁벤져스 / SW 트랙. 기계팀 논문 정본 v2 의 §3.1(지배방정식) · §3.3(2계층 ROM)을
 *  브라우저에서 실행 가능한 형태로 축약 구현한 것이다.
 *
 *  [왜 별도 파일인가]
 *    app_demo.html 은 안드로이드(Capacitor) 셸·BLE·알림 UI 를 담당하고,
 *    이 파일은 물리만 담당한다. 물리 계수가 바뀌어도 앱 코드를 건드리지 않고,
 *    노드에서 단독으로 검산할 수 있다.
 *
 *  [쓰는 법]
 *    <script src="rom_model.js"></script>   <!-- 선택. 없으면 근사식으로 동작 -->
 *    <script src="do_engine.js"></script>
 *
 *    DOEngine.configure({ tank:{width,height,depth}, waterDepthCm, zStartM,
 *                         aerationLevel, objects, dayNight });
 *    const r = DOEngine.estimate(temp, turbidity, species, count);
 *
 *  [검증 범위]  (S3 — 2026-08-01)
 *    · Stage B 산소 방정식을 EX3 A층 CFD 315케이스 "전량"에 풀었다
 *      (phiMean 기반 보존형 유한체적, 질량보존 오차 1e-10, 139.6분 / 6워커)
 *    · 케이스별 단위응답장 χ_fish · χ_sod → PCA(6)+Ridge 로 ROM 학습
 *    · 학습 데이터 구성: n_obs 0/1/2 = 1/60/254 → 유효범위 n_obs ≤ 2
 *    · ROM 상세 사양은 rom_model.js 의 skill_spec 참조
 *
 *  [완전혼합 축약의 근거] (47×21×21 cm, 폭기 ON)
 *    · 폭기 플룸 이류 순환 12.8 s vs 난류확산 3060 s vs 소비 9.5 h
 *      → 이류가 소비보다 2,673배 빠르다. 즉 어디서 산소를 써도 그보다 훨씬
 *        빨리 물이 순환해 채운다 → 공간 풀이 없이 0-D 수지로 축약 가능
 *    · 축약 오차(rev.C 실측): 결핍 기준 3.8 %, DO 기준 0.11 %
 *      (0.0091 mg/L — 위험까지의 여유 2.02 mg/L 의 0.45 %)
 *      축약이 결핍을 '과소평가'하는 방향이므로 안전측이 아니다 → 보수적으로 쓰려면
 *      결핍에 1.04 를 곱한다(현재 미적용, 표시값은 실측 그대로)
 *
 *  [남은 한계]
 *    · ROM 공간 형상은 기준 운전점(폭기 '보통')에서만 검증됨 → romShapeValid()
 *    · 식물은 국소 소스/싱크이나 u_plant 기저 미수령 → 현재 레벨(mean)에만 반영
 * ======================================================================== */
(function (root) {
    'use strict';

    // ---------------------------------------------------------------- 상태
    // 앱이 configure() 로 밀어넣는다. 물리 함수들은 전역을 참조하지 않는다.
    const state = {
        tank: { width: 60, height: 36, depth: 30 },  // 사용자 수조 실측 [cm]
        waterDepthCm: 21,        // 수위 [cm]
        zStartM: 0.02,           // 에어스톤 설치 높이 [m]
        aerationLevel: '보통',    // 정지 / 약 / 보통 / 강
        objects: null,           // 사진 분석 결과 (ROM 입력). null = 미분석
        dayNight: null           // null = 시각 자동, true = 주간, false = 야간
    };

    function configure(patch) {
        if (!patch) return state;
        for (const k of Object.keys(patch)) {
            if (patch[k] !== undefined) state[k] = patch[k];
        }
        return state;
    }

    // =================================================== 포화 용존산소
    // 담수 포화 DO [mg/L] — Benson–Krause (1 atm) [R14]
    // 진실원: EX3_ROM/dataset/stageB_DO/solve_do.py :: do_saturation()
    // 구 3차 다항식은 25 °C 에서 8.1757 mg/L → −1.06 % 계통편향이 있어 교체 (C6)
    function doSaturation(T) {
        const Ta = T + 273.15;
        return Math.exp(-139.34411 + 1.575701e5 / Ta - 6.642308e7 / (Ta * Ta)
                        + 1.243800e10 / Math.pow(Ta, 3) - 8.621949e11 / Math.pow(Ta, 4));
    }

    // ============================================ 어종 산소 파라미터
    // C_crit 단일 기준 6.0 mg/L (EX1 "> 6 = 안전"). [R29] 밴드 5/3/2 는 참고용 (C7)
    const DO_CRIT = 6.0;

    // 탁도 → 유기물 산소요구량 환산계수 [mg/h per NTU]
    // ⚠ U1: 근거 문서 없는 임시값 (25 NTU 에서 10 mg/h 가 되도록 역설정)
    const TURB_BOD_COEF = 0.4;

    // 대사율 온도의존 계수
    // ⚠ U4: 근거 없음. 어류 문헌값 2~3 중 선택 후 출처 부여 필요
    const Q10 = 2.0;

    // ================================================ K_La (산소전달)
    const TANK_VOLUME_L = 20.7;   // 47×21×21 cm 기준 수조 부피 [L] (C8) — 폴백용

    // 수조 전체 유효 산소전달계수 [1/h] — CFD 기준 운전점 Q_air=2 L/min, α_g=0.257
    //   보통 = 3.618 /h (정본, 플룸 3.174 + 자유수면 0.444)
    //   정지 = 자유수면 재폭기만 (0.444 /h — 어떤 플룸 기하로도 제거 불가한 바닥)
    // 진실원: stageB_DO/summary.csv 역산, 315케이스 DO 필드와 자기일관 (C1~C4)
    // ⚠ '보통' 3.618 만 CFD 역산 정본이고, 약(÷2)·강(×2)은 물리 근거 없는 임의 배수다.
    //   §4.2(폭기 전력 W → Q_air → α_g 역산)이 들어오면 이 4단계를 연속 입력으로 대체.
    const KLA_EFF = { 정지: 0.444, 약: 1.809, 보통: 3.618, 강: 7.235 };

    // 자유수면 재폭기 k_L,s·A_s/V — 플룸 기하와 무관한 바닥값 (전체의 15.2 % @ z=0.02)
    const KLA_SURFACE = 0.444;

    // N2: 수위(d)에 따른 K_La 보정. 실측표 (실험후검토사항.md §1.2) d[m] → K_La[1/h]
    // 기준 수위 0.21 m 대비 '비율'로 적용한다. KLA_EFF 가 이미 그 수위에서 교정된
    // 값이므로 절대값을 그대로 쓰면 이중계산이 된다.
    const KLA_DEPTH_TABLE = [[0.09, 1.66], [0.12, 1.85], [0.15, 2.19], [0.18, 2.63], [0.21, 3.12]];
    const KLA_DEPTH_REF = 3.12;

    // N4: 상수_목록 A~D군. 앱에서 직접 쓰는 것은 θ_a 뿐이고 나머지는 근거 추적용.
    const CONST_A_D = {
        Sc_t:    0.7,      // 난류 슈미트수 (CFD 확산항. 완전혼합 모델에서는 미사용)
        D_mol:   2.0e-9,   // 산소 분자확산계수 [m2/s]
        k_L_20:  2.3e-5,   // 자유수면 전달계수 @20 °C [m/s]
        theta_a: 1.024,    // 폭기 전달계수 온도보정 (Arrhenius)
        k_L_b:   1.08e-4,  // 기포 전달계수 [m/s]   (§4.2 역산용)
        d_b:     0.5e-3    // 기포 직경 [m]         (§4.2 역산용)
        // U_slip(T) : 미수령
    };
    // 검산: k_L,20 × θ_a^(25−20) = 2.590e-5 m/s, × A_s/V(4.76) × 3600 = 0.444 /h
    //       → 문서의 수면항과 일치하므로 이 온도보정 체인은 검증됨

    // N3: 에어스톤 설치 높이(z_start). 상수_목록.md D-1 표.
    // ⚠ 표의 절대 K_La 는 coarse 격자값(z=0.02 에서 2.703)으로 medium 앵커 2.604 대비
    //   +3.8 % 격자 편향이 있다 → 절대값은 쓰지 않고 '레버(상대비)' 열만 사용한다.
    // ⚠ 3D/0D 비(coarse 0.913~0.923, medium 0.951~0.966)는 격자 의존이므로
    //   "0.92 를 곱한다" 식의 일반화는 금지.
    const Z_START_TABLE = [   // [z_start(m), 레버 = K_La_3D(z) / K_La_3D(0.02)]
        [0.02, 1.000], [0.05, 0.853], [0.08, 0.751],
        [0.11, 0.645], [0.14, 0.511], [0.17, 0.389]
    ];

    // 표를 선형보간. 범위 밖은 양 끝값으로 고정(외삽 금지)
    function interp(table, x) {
        const T = table;
        if (x <= T[0][0]) return T[0][1];
        if (x >= T[T.length - 1][0]) return T[T.length - 1][1];
        for (let i = 0; i < T.length - 1; i++) {
            if (x >= T[i][0] && x <= T[i + 1][0]) {
                const t = (x - T[i][0]) / (T[i + 1][0] - T[i][0]);
                return T[i][1] + t * (T[i + 1][1] - T[i][1]);
            }
        }
        return T[T.length - 1][1];
    }

    function klaDepthFactor(depth_m) { return interp(KLA_DEPTH_TABLE, depth_m) / KLA_DEPTH_REF; }
    function zStartLever(z)          { return interp(Z_START_TABLE, z); }

    // 폭기 전달계수의 수온 의존. 기준 25 °C (정본 K_La 가 25 °C 값).
    // 물이 따뜻하면 전달은 빨라지지만 포화농도 C* 는 떨어져 서로 반대로 작용한다.
    function klaTempFactor(T) { return Math.pow(CONST_A_D.theta_a, T - 25); }

    // 현재 수위 기준 실제 수량 [L]. 바닥면적은 사용자 수조 치수를 그대로 쓴다
    // (부피는 순수 기하량이라 교정 불필요. 단 K_La 는 기준 형상에서 교정된 값)
    function waterVolumeL() {
        const v = state.tank.width * state.tank.depth * state.waterDepthCm / 1000;
        return v > 0 ? v : TANK_VOLUME_L;
    }

    // 폭기 세기 · 에어스톤 높이 · 수위 · 수온을 모두 반영한 유효 K_La [1/h]
    //   ① z_start(N3): 레버는 플룸 성분에만. 자유수면 0.444 는 플룸 기하와 무관하므로 제외
    //   ② 수위(N2): 실측표가 전체 K_La 기준이므로 (플룸+수면) 총량에 적용
    //   ③ 수온(N4): θ_a^(T−25) 를 전체에 적용
    // ※ ①②를 동시에 크게 벗어난 조합은 결합 실측표가 없어 미검증 영역이다.
    function effectiveKla(temp) {
        const base = KLA_EFF[state.aerationLevel];
        if (base === undefined) return NaN;
        const plumeK = Math.max(0, base - KLA_SURFACE) * zStartLever(state.zStartM);
        const kla25 = (plumeK + KLA_SURFACE) * klaDepthFactor(state.waterDepthCm / 100);
        return kla25 * klaTempFactor(temp === undefined ? 25 : temp);
    }

    // ============================================== N1: 식물 광합성 / 호흡
    // 주간엔 광합성으로 산소를 만들고(순생산 = P_max − R_resp), 야간엔 호흡만 남아 소비한다.
    const PLANT_P_MAX  = 5.0;   // 주간 총광합성 [mg O2 / (g DW·h)]
    const PLANT_R_RESP = 1.0;   // 호흡 (주·야 공통) [mg O2 / (g DW·h)]
    const PLANT_RHO_B  = { S: 2.0, M: 5.0, L: 10.0 };   // 건중량 밀도 [g DW / L]
    // 크기 등급 경계 [L] — CFD 데이터셋 실측 수초 부피(S 0.101/M 0.462/L 1.257)의 기하평균
    const PLANT_SIZE_BOUNDS = { SM: 0.215, ML: 0.762 };

    function isDaytime() {
        if (state.dayNight !== null && state.dayNight !== undefined) return !!state.dayNight;
        const h = new Date().getHours();
        return h >= 6 && h < 18;
    }

    // 사진에서 인식한 수초들의 총 건중량 [g DW]
    function plantBiomassG() {
        if (!state.objects) return 0;
        let total = 0;
        for (const o of state.objects) {
            if (o.type !== 'plant' || !o.rel) continue;
            // 상대크기(%) → 실제 치수(cm) → 타원기둥 부피 → L
            const w = o.rel.w / 100 * state.tank.width;
            const h = o.rel.h / 100 * state.tank.height;
            const d = o.rel.d / 100 * state.tank.depth;
            const V_L = (Math.PI / 4 * w * d * h) / 1000;
            if (!(V_L > 0)) continue;
            const cls = V_L < PLANT_SIZE_BOUNDS.SM ? 'S'
                      : V_L < PLANT_SIZE_BOUNDS.ML ? 'M' : 'L';
            total += V_L * PLANT_RHO_B[cls];
        }
        return total;
    }

    // ================================ A층 ROM: 장애물 배치 → 산소 부족량 분포
    // rom_model.js 가 로드돼 있으면 사용. 없으면 null 을 돌려 공식만으로 동작한다.
    /* rom_model.js 는 `const ROM_MODEL = {...}` 로 선언한다. 고전 스크립트의 top-level
     * const/let 은 스크립트 렉시컬 스코프에 묶여 window 에 붙지 않으므로
     * window.ROM_MODEL 로는 절대 보이지 않는다 (실측 확인). 맨이름으로 참조해야 한다.
     * 파일이 아예 없을 때는 ReferenceError 가 나므로 typeof 로 감싼다. */
    function romModel() {
        try {
            return (typeof ROM_MODEL !== 'undefined' && ROM_MODEL) ? ROM_MODEL
                 : (root.ROM_MODEL || null);          // var/window 로 넣은 변형도 허용
        } catch (e) {
            return null;
        }
    }
    function romAvailable() {
        const M = romModel();
        return !!(M && M.u_fish);
    }

    // S1: ROM 의 χ 는 기준 운전점(Q_air 2 L/min · α_g 0.257 · Su 2.86) 한 점에서만
    // 학습됐다. 폭기 강도를 바꾸면 유동장이 바뀌어 공간 '형상'이 달라진다 — 이는 측정된
    // 사실로, EX_exception 게이트에서 Su 2.86 → 1.684 일 때 정규화마스크 IoU 0.597
    // (기준 0.80 불합격), 정체분율 6.16 % → 10.66 % (+73 %) 였다.
    // 따라서 '약'·'강'에서는 히트맵을 표시하지 않고 평균값만 쓴다.
    const ROM_REF_LEVEL = '보통';
    function romShapeValid() {
        return romAvailable() && state.aerationLevel === ROM_REF_LEVEL;
    }

    // 물체 이름으로 종류 추정 (Gemini 가 type 을 안 준 경우 대비)
    function classifyObject(name) {
        const s = (name || '').toLowerCase();
        if (/plant|moss|수초|풀|식물|weed|grass/.test(s)) return 'plant';
        if (/rock|stone|wood|driftwood|바위|돌|ornament|decor/.test(s)) return 'rock';
        return 'other';
    }

    // 사진에서 얻은 물체들을 ROM 입력 격자(점유율)로 변환.
    // 학습 데이터는 CFD 좌표계(x=길이, y=폭, z=수심 상향)이고 앱 좌표계는
    // (x=가로, y=수면부터 아래로, z=앞유리부터 뒤로)이므로 축을 교환한다.
    //   CFD x ← 앱 x,  CFD y ← 앱 z,  CFD z ← (100 − 앱 y)
    // ※ 이 축 교환은 기계팀 검토에서 현행 z-up 규약에 맞다고 확인된 것이다 — 바꾸지 말 것.
    function buildOccupancy(objects) {
        const M = romModel();
        const g = M.grid;                          // nz, ny, nx
        const occ = new Float64Array(g.nz * g.ny * g.nx);
        const useful = (objects || []).filter(o => o.type === 'rock' || o.type === 'plant');
        if (!useful.length) return occ;            // 장애물 없음 → 전부 0

        // 1차원 구간 겹침 비율 (0~1)
        const overlap1d = (lo, hi, cellLo, cellHi) => {
            const a = Math.max(lo, cellLo), b = Math.min(hi, cellHi);
            return b > a ? (b - a) / (cellHi - cellLo) : 0;
        };
        const SUB = 8;   // 원기둥 단면만 부분샘플 (육면체는 해석적으로 정확)

        for (const o of useful) {
            const r = o.rel;
            if (!r) continue;
            // CFD 좌표계에서의 중심·크기 (0~100 상대값)
            const cx = r.x,        sw = r.w;
            const cy = r.z,        sd = r.d;       // 폭 방향 ← 앱의 깊이
            const cz = 100 - r.y,  sh = r.h;       // 수심 방향(바닥=0) ← 앱의 높이 반전
            const isCyl = (o.type === 'plant');    // 수초는 원기둥, 바위는 육면체

            const x0 = cx - sw / 2, x1 = cx + sw / 2;
            const y0 = cy - sd / 2, y1 = cy + sd / 2;
            const z0 = cz - sh / 2, z1 = cz + sh / 2;
            const dx = 100 / g.nx, dy = 100 / g.ny, dz = 100 / g.nz;

            for (let k = 0; k < g.nz; k++) {
                const fz = overlap1d(z0, z1, k * dz, (k + 1) * dz);
                if (fz <= 0) continue;
                for (let j = 0; j < g.ny; j++) for (let i = 0; i < g.nx; i++) {
                    let fxy;
                    if (!isCyl) {
                        fxy = overlap1d(x0, x1, i * dx, (i + 1) * dx) *
                              overlap1d(y0, y1, j * dy, (j + 1) * dy);
                    } else {
                        // 원기둥: 셀 단면을 SUB × SUB 로 나눠 원 안에 드는 비율
                        let hit = 0;
                        for (let a = 0; a < SUB; a++) for (let b = 0; b < SUB; b++) {
                            const px = (i + (b + 0.5) / SUB) * dx;
                            const py = (j + (a + 0.5) / SUB) * dy;
                            const ux = (px - cx) / (sw / 2), uy = (py - cy) / (sd / 2);
                            if (ux * ux + uy * uy <= 1) hit++;
                        }
                        fxy = hit / (SUB * SUB);
                    }
                    if (fxy <= 0) continue;
                    const idx = (k * g.ny + j) * g.nx + i;
                    occ[idx] = Math.min(1, occ[idx] + fxy * fz);
                }
            }
        }
        return occ;
    }

    // y = y_mean + (coef·x + intercept) · components
    function romPredictField(key, occ) {
        const M = romModel();
        const m = M[key];
        const nc = M.ncomp;
        const n = m.y_mean.length;
        const z = new Float64Array(nc);
        for (let c = 0; c < nc; c++) {
            let s = m.intercept[c];
            const row = m.coef[c];
            for (let f = 0; f < row.length; f++) s += row[f] * occ[f];
            z[c] = s;
        }
        const out = new Float64Array(n);
        for (let c = 0; c < nc; c++) {
            const comp = m.components[c], zc = z[c];
            for (let p = 0; p < n; p++) out[p] += zc * comp[p];
        }
        for (let p = 0; p < n; p++) out[p] += m.y_mean[p];
        return out;
    }

    // 실제 소비량을 곱해 산소 분포를 만들고 최저 지점을 찾는다 (선형성 이용)
    function romDOField(Csat, fishMgH, sodMgH) {
        if (!romAvailable()) return null;
        const M = romModel();
        const occ = buildOccupancy(state.objects);
        const uf = romPredictField('u_fish', occ);
        const us = romPredictField('u_sod', occ);
        const g = M.grid;
        const field = new Float64Array(uf.length);
        let worst = Infinity, wi = 0;
        for (let p = 0; p < uf.length; p++) {
            const c = Csat - (uf[p] * fishMgH + us[p] * sodMgH);
            field[p] = c;
            if (c < worst) { worst = c; wi = p; }
        }
        const i = wi % g.nx, j = Math.floor(wi / g.nx) % g.ny, k = Math.floor(wi / (g.nx * g.ny));
        const T = M.tank;
        return {
            field, grid: g, worst: Math.max(0, worst),
            // CFD 좌표 → 사람이 읽는 위치 (cm). z 는 바닥에서의 높이
            worstPos: {
                x: (i + 0.5) / g.nx * T.lx * 100,
                y: (j + 0.5) / g.ny * T.ly * 100,
                z: (k + 0.5) / g.nz * T.lz * 100
            }
        };
    }

    // 공간 편차 계수 [mg/L per (mg/h)] — ROM 미사용 시 폴백
    // stageB 11케이스 최악값 0.000986 (case0231) 기준 (C5)
    const SPATIAL_DROP_COEF = 1.0e-3;

    // ============================================= 수지 계산 (B층)
    // 수온·탁도·어종·마릿수로부터 용존산소를 추정
    function estimateDO(temp, turbidity, species, count) {
        const Csat = doSaturation(temp);
        const q10 = Math.pow(Q10, (temp - 25) / 10);   // 대사율 온도의존

        const fishMgH = (species.massG / 1000) * species.ocr25 * q10 * count;
        const organicMgH = TURB_BOD_COEF * turbidity * q10;

        // N1: 식물 항. 주간엔 순생산(음수 = 공급), 야간엔 호흡(양수 = 소비)
        const biomassG = plantBiomassG();
        const daytime = isDaytime();
        const plantMgH = daytime
            ? -(PLANT_P_MAX - PLANT_R_RESP) * biomassG * q10
            : PLANT_R_RESP * biomassG * q10;

        const demand = fishMgH + organicMgH + plantMgH;   // 순 산소요구량 [mg/h]

        // N2 수위 + N3 에어스톤 높이를 함께 반영. 수량도 수위에 따라 변한다
        const V = waterVolumeL();
        const depthFactor = klaDepthFactor(state.waterDepthCm / 100);
        const zLever = zStartLever(state.zStartM);
        const kla = effectiveKla(temp);                   // [1/h] (수온 보정 포함)
        const capacity = V * kla * Csat;                  // 최대 공급능력 [mg/h]

        // 완전혼합 정상상태:  공급 = 소비  →  C = C* − R_total/(V·K_La)
        let mean = Csat - demand / (V * kla);
        const anoxic = mean <= 0;                         // 공급능력 초과 = 무산소
        mean = Math.max(0, mean);

        // 최저 지점: 사진 분석 결과가 있으면 ROM 으로 실제 분포를 예측하고,
        // 없으면 CFD 에서 얻은 평균 여유값으로 근사한다.
        let worst, spatialDrop, rom = null, source = '근사', romGated = false;
        if (state.objects && romAvailable()) {
            if (romShapeValid()) {
                /* S2 임시 처리: plantMgH 를 ROM 인자에서 제외한다.
                 *   식물은 사진에서 위치·크기가 특정되는 '국소' 소스/싱크인데
                 *   균일항(u_fish)에 합산하면 두 가지가 동시에 깨진다.
                 *   (a) 공간 신호 소멸 — CFD 는 식물을 켜면 스프레드가 0.028→0.140 mg/L (5배)
                 *   (b) 주간 부호반전 — plantMgH<0 이면 계수합이 음수가 되어 u_fish 가
                 *       클수록 값이 커지고, 최저점이 원거리 코너 → 플룸 근처로 오표시
                 *   식물은 레벨(mean)에만 반영하고, 공간 분포는 u_plant 기저 수령 후 적용. */
                rom = romDOField(Csat, fishMgH, organicMgH);
            } else {
                romGated = true;   // 형상 미검증 운전점 → 근사식으로 폴백
            }
        }
        if (rom) {
            // ROM 은 폭기 ON·47×21×21 cm 학습 조건 기준. 평균 수준은 수지식에 맞춰 이동
            const romMean = rom.field.reduce((a, b) => a + b, 0) / rom.field.length;
            const shift = mean - romMean;
            for (let p = 0; p < rom.field.length; p++) rom.field[p] += shift;
            worst = Math.max(0, rom.worst + shift);
            spatialDrop = mean - worst;
            source = 'ROM';
        } else {
            // 순생산(demand<0) 상황에서는 여유를 빼지 않는다
            spatialDrop = Math.min(mean, SPATIAL_DROP_COEF * Math.max(0, demand));
            worst = Math.max(0, mean - spatialDrop);
        }

        return { Csat, demand, fishMgH, organicMgH, plantMgH, biomassG, daytime,
                 capacity, mean, worst, spatialDrop, anoxic,
                 usage: demand / capacity, supersaturated: mean > Csat,
                 volumeL: V, kla, depthFactor, waterDepthCm: state.waterDepthCm,
                 zStartM: state.zStartM, zLever, aerationLevel: state.aerationLevel,
                 temp, turbidity, count,
                 rom, source, romGated };
    }

    // ==================================== 진단 축: 폭기 부족 / 충분
    // 이 제품이 판정하는 것은 "폭기가 지금의 사육 부하에 충분한가" 이다.
    // 폭기 정지는 시나리오 조건이 아니며(폭기 없는 가정용 어항은 없음),
    // KLA_EFF.정지 는 정전·고장 알림 경로로만 남긴다.
    //
    //   K_La_req = 총 산소요구량 / ( V · (C*(T) − C_crit) )
    //   판정: K_La_eff >= K_La_req 면 충분
    function aerationDiagnosis(r, doCrit) {
        const crit = (doCrit === undefined) ? DO_CRIT : doCrit;
        const denom = r.volumeL * (r.Csat - crit);        // [mg/h per (1/h)]
        if (!(denom > 0)) return null;                    // C* < C_crit 이면 판정 불가
        const req = Math.max(0, r.demand) / denom;
        const margin = req > 0 ? r.kla / req : Infinity;  // 여유 배수
        return { req, denom, margin, sufficient: r.kla >= req, capacityMgH: r.kla * denom };
    }

    // 부족할 때 무엇을 하면 되는지 — 각 조치의 효과를 실제로 계산해 제시
    function aerationPrescriptions(r, diag) {
        const list = [];
        const levels = ['약', '보통', '강'];
        const idx = levels.indexOf(state.aerationLevel);
        if (idx >= 0 && idx < levels.length - 1) {
            const next = levels[idx + 1];
            const nextKla = r.kla / KLA_EFF[state.aerationLevel] * KLA_EFF[next];
            list.push(`폭기를 '${next}'으로 상향 → 여유 ${(nextKla / diag.req).toFixed(2)}배 확보 ` +
                      `(DO ${(r.Csat - r.demand / (r.volumeL * nextKla)).toFixed(2)})`);
        }
        if (state.zStartM > 0.03) {
            const gain = zStartLever(0.02) / zStartLever(state.zStartM);
            list.push(`에어스톤을 바닥 쪽으로 (z ${(state.zStartM * 100).toFixed(0)} → 2 cm) → K_La 최대 ${gain.toFixed(1)}배`);
        }
        if (r.turbidity > 10) {
            const cut = TURB_BOD_COEF * (r.turbidity - 10) * Math.pow(Q10, (r.temp - 25) / 10);
            list.push(`탁도 ${r.turbidity.toFixed(0)} → 10 NTU 로 환수 → 부하 ${cut.toFixed(0)} mg/h 감소`);
        }
        if (r.count > 1) {
            const per = r.fishMgH / r.count;
            const cut = Math.min(r.count - 1, Math.ceil((r.demand - diag.capacityMgH) / per));
            if (cut > 0) list.push(`마릿수 ${r.count} → ${r.count - cut} 로 조정 → 부하 ${(per * cut).toFixed(0)} mg/h 감소`);
        }
        return list;
    }

    // ============================================== 앱이 부르는 단일 창구
    // 수지 + 진단 + 처방 + 등급을 한 번에 돌려준다.
    function estimate(temp, turbidity, species, count) {
        const r = estimateDO(temp, turbidity, species, count);
        const crit = (species && species.doCrit !== undefined) ? species.doCrit : DO_CRIT;

        // 등급은 '최저 지점' 기준이다. 평균이 안전해도 바닥 구석이 임계 미만이면 위험.
        let status;
        if (r.worst >= crit + 1.5)  status = { label: '양호', cls: 'badge-green' };
        else if (r.worst >= crit)   status = { label: '주의', cls: 'badge-yellow' };
        else                        status = { label: '위험', cls: 'badge-red' };

        const diag = aerationDiagnosis(r, crit);
        const out = { ...r, doCrit: crit, doEstimate: r.mean, status, diag };
        out.prescriptions = (diag && !diag.sufficient) ? aerationPrescriptions(r, diag) : [];
        return out;
    }

    root.DOEngine = {
        configure, state, estimate, estimateDO,
        doSaturation, effectiveKla, waterVolumeL, klaDepthFactor, zStartLever, klaTempFactor,
        aerationDiagnosis, aerationPrescriptions,
        romAvailable, romShapeValid, romDOField, buildOccupancy, classifyObject,
        isDaytime, plantBiomassG,
        DO_CRIT, KLA_EFF, KLA_SURFACE, ROM_REF_LEVEL, TANK_VOLUME_L,
        TURB_BOD_COEF, Q10, CONST_A_D, SPATIAL_DROP_COEF,
        PLANT_P_MAX, PLANT_R_RESP, PLANT_RHO_B, PLANT_SIZE_BOUNDS,
        rev: 'C'
    };
})(typeof window !== 'undefined' ? window : globalThis);
