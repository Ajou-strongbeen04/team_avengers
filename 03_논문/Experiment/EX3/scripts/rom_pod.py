#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 2-A — POD + 회귀 A층 ROM 베이스라인.

漁벤져스 · 04_어플리케이션/02_BC축소모델 · 2026-07-24
계획: 04_ROM착수_계획.md §2 Stage2-A · §3 평가 게이트

파이프라인:
  1) train_val UMean 스냅샷 → 스냅샷법 POD(평균차감, 에너지 컷)
  2) 기하특징 X(스칼라 + 조대 점유격자) → 모드계수 회귀 (Ridge/RF 비교)
  3) test10 재구성 → field relL2 · dead-spot 위치오차(셀·mm)
  4) 베이스라인 대조: 평균장 예측 / 최근접 조회(retrieval)
격자순서 [k,j,i] = resample_encode.py 규약. dead-spot = 유체셀 min|U|.
"""
import argparse, json, time
from pathlib import Path
import numpy as np

# 원본 CFD 격자
NX0, NY0, NZ0 = 108, 48, 48
LX, LY, LZ = 0.47, 0.21, 0.21
DEADSPOT_THR = 0.005

# POOL로 축소된 작업 격자 (set_pool로 설정; 기본 2 = 54x24x24)
POOL = 2
NX = NX0 // POOL; NY = NY0 // POOL; NZ = NZ0 // POOL
DX, DY, DZ = LX/NX, LY/NY, LZ/NZ


def set_pool(p):
    global POOL, NX, NY, NZ, DX, DY, DZ
    POOL = p
    NX, NY, NZ = NX0//p, NY0//p, NZ0//p
    DX, DY, DZ = LX/NX, LY/NY, LZ/NZ


def _pool3(a):  # (...,NZ0,NY0,NX0) -> (...,NZ,NY,NX) block-mean
    if POOL == 1:
        return a
    sh = a.shape[:-3]
    return a.reshape(*sh, NZ, POOL, NY, POOL, NX, POOL).mean(axis=(-5, -3, -1))


def load_fields(fields_dir, case_ids):
    """UMean(3ch)·occ(2ch)를 POOL 축소해 로드. U:(N,3*NZ*NY*NX), occ:(N,2,NZ,NY,NX)."""
    U = np.empty((len(case_ids), 3*NZ*NY*NX), np.float32)
    occ = np.empty((len(case_ids), 2, NZ, NY, NX), np.float32)
    for i, cid in enumerate(case_ids):
        d = np.load(Path(fields_dir)/f"{cid}.npz")
        U[i] = _pool3(d["Y_U"]).reshape(-1)          # (3,NZ,NY,NX)->flat
        occ[i, 0] = _pool3(d["X_occ"][0])            # 점유율(0~1)
        occ[i, 1] = _pool3(d["X_occ"][1])            # kind 평균
    return U, occ


def geom_features(occ, labels_df, case_ids, coarse=(3, 3, 6)):
    """기하특징: 스칼라(n,occ_frac,centroid,spread) + 조대 점유/kind 풀링."""
    cz, cy, cx = coarse
    feats = []
    lab = labels_df.set_index("case_id")
    for i, cid in enumerate(case_ids):
        oc = occ[i, 0]; kd = occ[i, 1]
        r = lab.loc[cid]
        scal = [r["n_obstacles"], r.get("n_rock", 0), r.get("n_plant", 0), r["occ_frac"]]
        # 점유 무게중심·퍼짐 (정규화)
        idx = np.argwhere(oc > 0.5)
        if len(idx):
            c = idx.mean(0)/np.array([NZ, NY, NX])
            s = idx.std(0)/np.array([NZ, NY, NX])
        else:
            c = np.zeros(3); s = np.zeros(3)
        # 조대 풀링 (blockwise mean)
        def pool(a):
            return a.reshape(cz, NZ//cz, cy, NY//cy, cx, NX//cx).mean((1, 3, 5)).reshape(-1)
        feats.append(np.concatenate([scal, c, s, pool(oc), pool(kd)]))
    return np.array(feats, np.float32)


def pod_basis(Uc, energy=0.99):
    """스냅샷법 POD. Uc=(N,D) 평균차감. 반환 Phi(D,r), coeff A(N,r), 에너지."""
    N = Uc.shape[0]
    G = Uc @ Uc.T / N                      # (N,N) Gram
    w, V = np.linalg.eigh(G)               # 오름차순
    w = w[::-1]; V = V[:, ::-1]
    w = np.clip(w, 0, None)
    cum = np.cumsum(w)/w.sum()
    r = int(np.searchsorted(cum, energy) + 1)
    r = max(r, 3)
    lam = w[:r]
    Phi = (Uc.T @ V[:, :r]) / np.sqrt(lam*N)   # (D,r) 정규직교
    A = Uc @ Phi                                # (N,r)
    return Phi, A, w, r


def umag(Uflat):
    U = Uflat.reshape(3, NZ, NY, NX)
    return np.sqrt((U**2).sum(0))


def deadspot(Uflat, occ0):
    m = umag(Uflat); m = m.copy(); m[occ0 > 0.5] = np.nan
    k, j, i = np.unravel_index(np.nanargmin(m), m.shape)
    return np.array([i, j, k]), np.array([(i+.5)*DX, (j+.5)*DY, (k+.5)*DZ])


def lowvel_mask(Uflat, occ0, q=0.10):
    """유체셀 중 하위 q 분위 저유속 = dead-zone 마스크."""
    m = umag(Uflat); fluid = occ0 <= 0.5
    thr = np.quantile(m[fluid], q)
    return (m <= thr) & fluid


def lowvel_centroid(mask):
    idx = np.argwhere(mask)
    if not len(idx):
        return np.zeros(3)
    c = idx.mean(0)  # (k,j,i)
    return np.array([c[2]*DX, c[1]*DY, c[0]*DZ])  # x,y,z (m)


def eval_case(U_true, U_pred, occ0, mean=None):
    relL2 = np.linalg.norm(U_pred - U_true)/np.linalg.norm(U_true)
    # 이상장(공통평균 제거) relL2 — 학습된 신호 직접 측정. meanfield=1.0
    relL2_anom = np.nan
    if mean is not None:
        num = np.linalg.norm((U_pred-mean) - (U_true-mean))
        den = np.linalg.norm(U_true-mean) + 1e-30
        relL2_anom = num/den
    # dead-zone(저유속 하위10%) IoU + 무게중심 거리
    mt = lowvel_mask(U_true, occ0); mp = lowvel_mask(U_pred, occ0)
    inter = (mt & mp).sum(); union = (mt | mp).sum()
    iou = inter/union if union else 0.0
    cdist_mm = np.linalg.norm(lowvel_centroid(mt) - lowvel_centroid(mp))*1000
    # 전역 argmin(참고용, 불안정)
    idt, _ = deadspot(U_true, occ0); idp, _ = deadspot(U_pred, occ0)
    argmin_cell = np.linalg.norm(idt - idp)
    return [relL2, relL2_anom, iou, cdist_mm, argmin_cell]


def fit_regressors(Xtr, Atr, kind="ridge"):
    if kind == "ridge":
        from sklearn.linear_model import RidgeCV
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
        m = make_pipeline(StandardScaler(),
                          RidgeCV(alphas=np.logspace(-3, 4, 20)))
        m.fit(Xtr, Atr); return m
    if kind == "rf":
        from sklearn.ensemble import RandomForestRegressor
        m = RandomForestRegressor(n_estimators=300, max_depth=None,
                                  n_jobs=-1, random_state=0)
        m.fit(Xtr, Atr); return m
    if kind == "mlp":
        from sklearn.neural_network import MLPRegressor
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
        m = make_pipeline(StandardScaler(),
                          MLPRegressor(hidden_layer_sizes=(256, 128), activation="relu",
                                       alpha=1e-3, max_iter=2000, early_stopping=True,
                                       n_iter_no_change=30, random_state=0))
        m.fit(Xtr, Atr); return m
    raise ValueError(kind)


def run(fields_dir, split_path, labels_path, energy, out_json):
    import pandas as pd
    split = json.loads(Path(split_path).read_text())
    labels = pd.read_parquet(labels_path)
    tr_ids = split["train_val"]; te_ids = split["test"]
    t0 = time.time()
    Utr, occtr = load_fields(fields_dir, tr_ids)
    Ute, occte = load_fields(fields_dir, te_ids)
    print(f"load {len(tr_ids)}tr+{len(te_ids)}te  {time.time()-t0:.1f}s")

    mean = Utr.mean(0)
    Uc = Utr - mean
    Phi, Atr, w, r = pod_basis(Uc, energy)
    print(f"POD modes r={r} (energy {energy}), λ1/λr={w[0]/w[r-1]:.1e}")

    Xtr = geom_features(occtr, labels, tr_ids)
    Xte = geom_features(occte, labels, te_ids)

    results = {"r": r, "energy": energy, "n_train": len(tr_ids), "pool": POOL,
               "grid": [NZ, NY, NX]}

    def ev_all(pred_fn):
        return [eval_case(Ute[i], pred_fn(i), occte[i, 0], mean) for i in range(len(te_ids))]

    # --- 베이스라인 1: 평균장 예측 ---
    results["baseline_meanfield"] = summarize(ev_all(lambda i: mean), te_ids)

    # --- 베이스라인 2: 최근접 조회(feature L2) ---
    from scipy.spatial.distance import cdist
    nn = cdist(Xte, Xtr).argmin(1)
    results["baseline_nn_retrieval"] = summarize(ev_all(lambda i: Utr[nn[i]]), te_ids)

    # --- POD 재구성 상한(참 계수 투영) ---
    recon_true = mean + ((Ute - mean) @ Phi) @ Phi.T
    results["pod_projection_ceiling"] = summarize(ev_all(lambda i: recon_true[i]), te_ids)

    # --- POD-ROM: Ridge / RF / MLP ---
    for kind in ["ridge", "rf", "mlp"]:
        reg = fit_regressors(Xtr, Atr, kind)
        recon = mean + reg.predict(Xte) @ Phi.T
        results[f"pod_{kind}"] = summarize(ev_all(lambda i: recon[i]), te_ids)

    Path(out_json).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print_report(results)
    return results


_MET = ["relL2", "relL2_anom", "iou", "cdist_mm", "argmin_cell"]


def summarize(ev, ids):
    ev = np.array(ev)  # (N,5)
    out = {}
    for j, m in enumerate(_MET):
        out[m + "_med"] = float(np.nanmedian(ev[:, j]))
        out[m + ("_min" if m == "iou" else "_max")] = float(
            np.nanmin(ev[:, j]) if m == "iou" else np.nanmax(ev[:, j]))
    out["per_case"] = {ids[i]: {m: round(float(ev[i, j]), 3) for j, m in enumerate(_MET)}
                       for i in range(len(ids))}
    return out


def print_report(r):
    print("\n=== A층 ROM 베이스라인 (test 10, pool=%d grid %s) ===" % (r["pool"], r["grid"]))
    print(f"POD modes r={r['r']} @ energy {r['energy']}\n")
    hdr = (f"{'method':<24}{'relL2':>8}{'anomL2 med':>11}{'IoU med':>9}"
           f"{'IoU min':>9}{'cdist_mm':>10}{'argmin_cell':>12}")
    print(hdr); print("-" * len(hdr))
    order = ["baseline_meanfield", "baseline_nn_retrieval", "pod_projection_ceiling",
             "pod_ridge", "pod_rf", "pod_mlp"]
    for k in order:
        if k in r:
            s = r[k]
            print(f"{k:<24}{s['relL2_med']:>8.3f}{s['relL2_anom_med']:>11.3f}"
                  f"{s['iou_med']:>9.3f}{s['iou_min']:>9.3f}"
                  f"{s['cdist_mm_med']:>10.1f}{s['argmin_cell_med']:>12.1f}")
    print("\n해석: anomL2<1 = 평균장 대비 학습신호 포착 | IoU↑ = 저유속영역 일치 | "
          "cdist=저유속 무게중심거리 | argmin_cell=전역최소점(불안정, 참고)")


def learning_curve(fields_dir, split_path, labels_path, energy, out_json,
                   Ns=(30, 60, 120, 180, 243), seed=0):
    """train N을 늘리며 test(고정) 성능 → 포화 판정. RF 회귀 사용."""
    import pandas as pd
    split = json.loads(Path(split_path).read_text())
    labels = pd.read_parquet(labels_path)
    tr_all = split["train_val"]; te = split["test"]
    Utr, occtr = load_fields(fields_dir, tr_all)
    Ute, occte = load_fields(fields_dir, te)
    Xtr_all = geom_features(occtr, labels, tr_all)
    Xte = geom_features(occte, labels, te)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(tr_all))
    rows = []
    for N in Ns:
        N = min(N, len(tr_all)); idx = order[:N]
        U = Utr[idx]; mean = U.mean(0)
        Phi, A, w, r = pod_basis(U - mean, energy)
        reg = fit_regressors(Xtr_all[idx], A, "rf")
        recon = mean + reg.predict(Xte) @ Phi.T
        ev = np.array([eval_case(Ute[i], recon[i], occte[i, 0], mean)
                       for i in range(len(te))])
        rows.append({"N": int(N), "r": int(r),
                     "anomL2_med": float(np.nanmedian(ev[:, 1])),
                     "iou_med": float(np.median(ev[:, 2])),
                     "iou_min": float(ev[:, 2].min()),
                     "cdist_mm_med": float(np.median(ev[:, 3]))})
        print(f"N={N:3d} r={r:3d}  anomL2={rows[-1]['anomL2_med']:.3f}  "
              f"IoU_med={rows[-1]['iou_med']:.3f}  IoU_min={rows[-1]['iou_min']:.3f}  "
              f"cdist={rows[-1]['cdist_mm_med']:.1f}mm", flush=True)
    Path(out_json).write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"→ {out_json}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fields-dir", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--energy", type=float, default=0.99)
    ap.add_argument("--pool", type=int, default=2)
    ap.add_argument("--out", default="/tmp/rom_pod_results.json")
    ap.add_argument("--learning-curve", action="store_true")
    a = ap.parse_args()
    set_pool(a.pool)
    if a.learning_curve:
        learning_curve(a.fields_dir, a.split, a.labels, a.energy,
                       a.out.replace(".json", "_lc.json"))
    else:
        run(a.fields_dir, a.split, a.labels, a.energy, a.out)
