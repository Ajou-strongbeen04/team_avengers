# L2-Gemini 제안 평가: "사전에서 뽑아 쓰는" 방식의 상한(ceiling) 지도
#   U_pred = sum_k w_k * U_k   (라이브러리 케이스의 선형/볼록 결합)
# 분해:  후보선택(기하 vs 오라클) x 가중치(휴리스틱 vs 오라클) x 사전크기 K
import sys, json, csv, os, collections
import numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0, 'scripts'); import rom_pod as R
R.set_pool(2); NZ, NY, NX = R.NZ, R.NY, R.NX
rows = {r['case_id']: r for r in csv.DictReader(open('CFD/cases.csv'))}
ids = sorted(d for d in os.listdir('dataset/result') if d.startswith('case') and not d.endswith('.tgz'))
U, occ = R.load_fields('/tmp/fields/fields', ids)
lab = pd.read_csv('/tmp/fields/labels.csv')
N = len(ids); idx = {c: i for i, c in enumerate(ids)}
mean_all = U.mean(0)
obs = {c: json.loads(rows[c]['obstacles_json']) for c in ids}
def kindof(c):
    o = obs[c]
    return 'none' if not o else ('rock' if all(x['kind'] == 'rock' for x in o)
           else ('plant' if all(x['kind'] == 'plant' for x in o) else '혼합'))

# --- 기하 특징 거리 (사진에서 알 수 있는 정보만) ---
G = R.geom_features(occ, lab, ids)
G = (G - G.mean(0))/(G.std(0) + 1e-9)
Dg = ((G[:, None, :] - G[None, :, :])**2).sum(-1)
np.fill_diagonal(Dg, np.inf)
# --- 장(場) 거리 (오라클: 정답을 봐야 알 수 있음) ---
nrm = (U*U).sum(1)
Df = nrm[:, None] + nrm[None, :] - 2*(U @ U.T)
np.fill_diagonal(Df, np.inf)
print(f"cases={N}  grid={NZ}x{NY}x{NX}  feat={G.shape[1]}")

def blend_eval(sel_D, K, weights, tag):
    """sel_D 로 후보 K개 선택 → weights('idw'|'lstsq') → LOO 평가."""
    E = []
    for i in range(N):
        cand = np.argsort(sel_D[i])[:K]
        A = U[cand]                                  # (K, P)
        if weights == 'idw':
            d = np.sqrt(np.maximum(sel_D[i][cand], 0)) + 1e-6
            w = (1/d); w /= w.sum()
        else:                                        # 오라클 최소제곱
            w, *_ = np.linalg.lstsq(A.T, U[i], rcond=None)
        E.append(R.eval_case(U[i], w @ A, occ[i, 0], mean_all))
    E = np.array(E)
    return [tag, K, np.nanmedian(E[:, 1]), np.median(E[:, 2]),
            np.percentile(E[:, 2], 10), np.median(E[:, 3])], E

print("\n" + "="*86)
print("사전(라이브러리) 결합의 상한 지도 — LOO 253케이스")
print("="*86)
print(f"{'방식':<34}{'K':>5}{'anomL2':>9}{'IoU med':>9}{'IoU p10':>9}{'cdist mm':>10}")
res = []
r, Em = blend_eval(Dg, 1, 'idw', '(참고) 평균장')  # placeholder 대체
E0 = np.array([R.eval_case(U[i], mean_all, occ[i, 0], mean_all) for i in range(N)])
print(f"{'baseline 평균장':<34}{'-':>5}{np.nanmedian(E0[:,1]):>9.3f}{np.median(E0[:,2]):>9.3f}"
      f"{np.percentile(E0[:,2],10):>9.3f}{np.median(E0[:,3]):>10.1f}")

store = {}
for K in [1, 3, 8, 16, 32, 64, 252]:
    for selD, selname in [(Dg, '기하선택'), (Df, '오라클선택')]:
        for w in (['idw'] if K > 1 else ['idw']) + ['lstsq']:
            if selname == '오라클선택' and w == 'idw' and K > 1:
                continue  # 의미 낮음
            tag = f"{selname} + {'IDW가중' if w=='idw' else '오라클가중'}"
            row, E = blend_eval(selD, K, w, tag)
            print(f"{tag:<34}{K:>5}{row[2]:>9.3f}{row[3]:>9.3f}{row[4]:>9.3f}{row[5]:>10.1f}")
            store[(tag, K)] = E
            res.append(row)

print("\n[참고] 기존 측정치:  pod_rf 0.612/0.718/-/7.2   최근접조회 0.917/0.627/-/10.4   POD ceiling 0.293/0.861/-/2.7")

# 종류별 — 기하선택+오라클가중 K=8/32
print("\n종류별 (기하선택 + 오라클가중):")
print(f"{'구성':<8}{'n':>5}{'K=8 IoU':>10}{'K=32 IoU':>10}{'K=252 IoU':>11}{'K=8 anomL2':>12}")
for g in ['plant', 'rock', '혼합']:
    sel = [i for i, c in enumerate(ids) if kindof(c) == g]
    a = store[('기하선택 + 오라클가중', 8)][sel]
    b = store[('기하선택 + 오라클가중', 32)][sel]
    d = store[('기하선택 + 오라클가중', 252)][sel]
    print(f"{g:<8}{len(sel):>5}{np.median(a[:,2]):>10.3f}{np.median(b[:,2]):>10.3f}"
          f"{np.median(d[:,2]):>11.3f}{np.nanmedian(a[:,1]):>12.3f}")
pd.DataFrame(res, columns=['tag','K','anomL2','IoU','IoU_p10','cdist']).to_csv('/tmp/dict_ceiling.csv', index=False)
