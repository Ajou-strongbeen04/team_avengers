# 대조군: 동일 CV 프로토콜에서 '장(場)' 과제의 학습곡선 (포화 여부 직접 비교)
import sys, json, numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0, 'scripts'); import rom_pod as R
R.set_pool(2)
split = json.load(open('dataset/training_dataset/test_split.json'))
allids = split['train_val'] + split['test']
U, occ = R.load_fields('/tmp/fields/fields', allids)
labels = pd.read_csv('/tmp/fields/labels.csv')
X = R.geom_features(occ, labels, allids); N = len(allids)
rng = np.random.RandomState(0); order = rng.permutation(N)
print(f"{'N_train':>8}{'anomL2_med':>12}{'IoU_med':>9}{'cdist_mm':>10}  (3-fold CV, 전 253)")
for n in [60, 202]:
    rows = []
    for f in range(3):
        te = order[f::3]; tr = np.setdiff1d(order, te)[:n]
        mean = U[tr].mean(0)
        Phi, A, w, r = R.pod_basis(U[tr] - mean, 0.99)
        reg = R.fit_regressors(X[tr], A, 'rf')
        P = mean + reg.predict(X[te]) @ Phi.T
        rows += [R.eval_case(U[te[i]], P[i], occ[te[i], 0], mean) for i in range(len(te))]
    e = np.array(rows)
    print(f"{n:>8}{np.nanmedian(e[:,1]):>12.3f}{np.median(e[:,2]):>9.3f}{np.median(e[:,3]):>10.1f}")
