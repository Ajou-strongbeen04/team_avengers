# ① 조대 위험맵 과제 — 출력 차원을 낮추면 253으로 포화하는가
import sys, json, csv, numpy as np, pandas as pd
pd.read_parquet = lambda p, **k: pd.read_csv(p)
sys.path.insert(0, 'scripts')
import rom_pod as R
R.set_pool(2)
NZ, NY, NX = R.NZ, R.NY, R.NX
split = json.load(open('dataset/training_dataset/test_split.json'))
allids = split['train_val'] + split['test']
U, occ = R.load_fields('/tmp/fields/fields', allids)
labels = pd.read_csv('/tmp/fields/labels.csv')
X = R.geom_features(occ, labels, allids)
N = len(allids)
speed = np.linalg.norm(U.reshape(N, 3, NZ, NY, NX), axis=1)      # (N,NZ,NY,NX)
solid = occ[:, 0] > 0.5

def coarse_map(nyc, nxc):
    by, bx = NY // nyc, NX // nxc
    out = np.zeros((N, nyc, nxc))
    for a in range(nyc):
        for b in range(nxc):
            blk = speed[:, :, a*by:(a+1)*by, b*bx:(b+1)*bx]
            msk = ~solid[:, :, a*by:(a+1)*by, b*bx:(b+1)*bx]
            out[:, a, b] = (blk*msk).sum((1,2,3)) / np.maximum(msk.sum((1,2,3)), 1)
    return out.reshape(N, -1)

def metrics(Yt, Yp):
    """top1 = 최저유속(=최위험) 구역 적중률, top1_q = 예측 1위가 실제 하위25%에 드는 비율"""
    at, ap = Yt.argmin(1), Yp.argmin(1)
    q = max(1, Yt.shape[1] // 4)
    rank = np.argsort(np.argsort(Yt, 1), 1)
    inq = np.array([rank[i, ap[i]] < q for i in range(len(Yt))])
    return (at == ap).mean(), inq.mean()

from sklearn.ensemble import RandomForestRegressor
def cv_eval(Y, ntrain=None, folds=5, seed=0):
    rng = np.random.RandomState(seed); order = rng.permutation(N)
    t1 = []; tq = []; t1b = []; tqb = []; t1n = []; tqn = []
    for f in range(folds):
        te = order[f::folds]; tr = np.setdiff1d(order, te)
        if ntrain: tr = tr[:ntrain]
        m = RandomForestRegressor(n_estimators=300, min_samples_leaf=2,
                                  random_state=0, n_jobs=-1).fit(X[tr], Y[tr])
        a, b = metrics(Y[te], m.predict(X[te])); t1.append(a); tq.append(b)
        a, b = metrics(Y[te], np.tile(Y[tr].mean(0), (len(te), 1))); t1b.append(a); tqb.append(b)
        d = ((X[te][:, None, :] - X[tr][None, :, :])**2).sum(-1).argmin(1)
        a, b = metrics(Y[te], Y[tr][d]); t1n.append(a); tqn.append(b)
    return (np.mean(t1), np.std(t1), np.mean(tq), np.mean(t1b), np.mean(tqb), np.mean(t1n), np.mean(tqn))

print("=== 해상도 스윕 (5-fold CV, 전 253케이스) ===")
print(f"{'격자':<9}{'구역수':>6}{'블록cm':>11}{'RF top1':>9}{'평균장':>8}{'조회':>8}{'RF-평균장':>10}{'top1-Q':>9}")
res = {}
for (nyc, nxc) in [(4,9),(6,18),(8,27)]:
    Y = coarse_map(nyc, nxc); res[(nyc,nxc)] = Y
    r = cv_eval(Y)
    print(f"{nyc}x{nxc:<6}{nyc*nxc:>6}{21/nyc:>5.1f}x{47/nxc:<5.1f}{r[0]:>9.3f}{r[3]:>8.3f}{r[5]:>8.3f}{r[0]-r[3]:>10.3f}{r[2]:>9.3f}")
for key in [(4,9),(6,18)]:
    print(f"\n=== 학습곡선 {key[0]}x{key[1]} ({key[0]*key[1]}구역) ===")
    print(f"{'N_train':>8}{'RF top1':>10}{'평균장':>8}{'top1-Q':>9}")
    for n in [30,60,120,180,202]:
        r = cv_eval(res[key], ntrain=n)
        print(f"{n:>8}{r[0]:>10.3f}{r[3]:>8.3f}{r[2]:>9.3f}")
