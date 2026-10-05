#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 2-B — 3D CNN 인코더 A층 ROM (점유격자 → POD 계수).

漁벤져스 · 04_어플리케이션/02_BC축소모델 · 2026-07-24
계획 `04_ROM착수_계획.md` §2 Stage2-B · Stage2-A 결과 `05_ROM_Stage2A_결과.md`

■ 왜 이 구조인가 (Stage2-A 진단 반영)
  POD 기저는 이미 충분(projection ceiling anomL2 0.29·IoU 0.86) → 병목은 기하→계수 회귀.
  그래서 full U-Net(장→장)이 아니라 **점유격자 → POD 계수** 회귀만 CNN으로 교체한다.
  출력이 r개 계수로 작아 경량, 검증된 POD 디코더를 재사용. (원하면 --unet로 전장 회귀도 가능하게 확장 여지)
  in-sandbox 실험: 엔지니어드 특징 위 RF가 최선, MLP는 과적합 → **원시 격자+합성곱 귀납편향**이 필요.

■ 실행 환경
  이 스크립트는 torch 필요(3D conv). 샌드박스엔 GPU/torch가 없으니 **팀 GPU(로컬/Colab/GCP)에서 실행**.
    pip install torch --index-url https://download.pytorch.org/whl/cu121   # GPU
    python3 rom_cnn.py --fields-dir <npz폴더> --split test_split.json --labels labels.parquet \
                       --pool 1 --epochs 300 --out cnn_results.json
  npz 폴더 = resample_encode.py 산출(X_occ,Y_U). pool 1=native 108x48x48(GPU 권장), 2=54x24x24.

평가 지표는 rom_pod.py와 동일(anomL2·저유속 IoU·무게중심거리) → 직접 비교 가능.
"""
import argparse, json, time
from pathlib import Path
import numpy as np

NX0, NY0, NZ0 = 108, 48, 48
LX, LY, LZ = 0.47, 0.21, 0.21
POOL = 1
NX = NX0; NY = NY0; NZ = NZ0
DX = LX/NX; DY = LY/NY; DZ = LZ/NZ


def set_pool(p):
    global POOL, NX, NY, NZ, DX, DY, DZ
    POOL = p; NX, NY, NZ = NX0//p, NY0//p, NZ0//p
    DX, DY, DZ = LX/NX, LY/NY, LZ/NZ


def _pool3(a):
    if POOL == 1:
        return a
    sh = a.shape[:-3]
    return a.reshape(*sh, NZ, POOL, NY, POOL, NX, POOL).mean(axis=(-5, -3, -1))


def load(fields_dir, ids):
    U = np.empty((len(ids), 3, NZ, NY, NX), np.float32)
    occ = np.empty((len(ids), 2, NZ, NY, NX), np.float32)
    for i, cid in enumerate(ids):
        d = np.load(Path(fields_dir)/f"{cid}.npz")
        U[i] = _pool3(d["Y_U"]); occ[i, 0] = _pool3(d["X_occ"][0]); occ[i, 1] = _pool3(d["X_occ"][1])
    return U, occ


# ---------- POD (numpy, rom_pod.py와 동일 규약) ----------
def pod_basis(Uc, energy=0.99):
    N = Uc.shape[0]
    G = Uc @ Uc.T / N
    w, V = np.linalg.eigh(G); w = w[::-1]; V = V[:, ::-1]; w = np.clip(w, 0, None)
    r = max(int(np.searchsorted(np.cumsum(w)/w.sum(), energy)+1), 3)
    Phi = (Uc.T @ V[:, :r]) / np.sqrt(w[:r]*N)
    return Phi, r


# ---------- 지표 (rom_pod.py와 동일) ----------
def umag(Uv):  # (3,NZ,NY,NX)
    return np.sqrt((Uv**2).sum(0))


def lowvel_mask(Uv, occ0, q=0.10):
    m = umag(Uv); fluid = occ0 <= 0.5
    thr = np.quantile(m[fluid], q)
    return (m <= thr) & fluid


def centroid(mask):
    idx = np.argwhere(mask)
    if not len(idx):
        return np.zeros(3)
    c = idx.mean(0)
    return np.array([c[2]*DX, c[1]*DY, c[0]*DZ])


def eval_case(Ut, Up, occ0, mean_v):
    a = np.linalg.norm((Up-mean_v)-(Ut-mean_v))/(np.linalg.norm(Ut-mean_v)+1e-30)
    mt = lowvel_mask(Ut, occ0); mp = lowvel_mask(Up, occ0)
    iou = (mt & mp).sum()/((mt | mp).sum() or 1)
    cd = np.linalg.norm(centroid(mt)-centroid(mp))*1000
    return a, iou, cd


def build_cnn(in_ch, r):
    import torch.nn as nn
    def blk(ci, co):
        # GroupNorm: 작은 배치·소량데이터서 BatchNorm보다 안정
        return nn.Sequential(nn.Conv3d(ci, co, 3, padding=1), nn.GroupNorm(min(8, co), co),
                             nn.ReLU(), nn.MaxPool3d(2))
    return nn.Sequential(
        blk(in_ch, 16), blk(16, 32), blk(32, 64), blk(64, 128),
        nn.AdaptiveAvgPool3d(1), nn.Flatten(),
        nn.Linear(128, 256), nn.ReLU(), nn.Dropout(0.3), nn.Linear(256, r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fields-dir", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--labels", default=None, help="(미사용; CNN은 원시 점유격자 입력) 호환용")
    ap.add_argument("--pool", type=int, default=1)
    ap.add_argument("--energy", type=float, default=0.90)  # 지배 모드만(잡음모드 과적합 회피)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--out", default="cnn_results.json")
    ap.add_argument("--save-model", default="rom_cnn.pt")
    a = ap.parse_args()
    set_pool(a.pool)

    import torch
    from torch.utils.data import TensorDataset, DataLoader
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("device", dev, "grid", (NZ, NY, NX), flush=True)

    split = json.loads(Path(a.split).read_text())
    tr_ids, te_ids = split["train_val"], split["test"]

    Utr, occtr = load(a.fields_dir, tr_ids)
    Ute, occte = load(a.fields_dir, te_ids)
    D = 3*NZ*NY*NX
    mean_v = Utr.mean(0)                     # (3,NZ,NY,NX)
    Uc = (Utr - mean_v).reshape(len(tr_ids), -1)
    Phi, r = pod_basis(Uc, a.energy)         # (D,r)
    print("POD r", r, flush=True)
    Atr = Uc @ Phi                           # (Ntr,r) 타깃
    # ★ 전역 스칼라 1개로만 스케일(mode별 표준화 금지) — POD 직교성상 원시계수 MSE=장 L2오차.
    #   지배 모드가 loss를 지배해야 재구성이 좋아진다(잡음 모드 과적합 방지).
    a_scale = float(Atr.std())
    Atr_n = Atr / a_scale

    X = torch.tensor(occtr); Y = torch.tensor(Atr_n.astype(np.float32))
    n_val = max(1, int(len(tr_ids)*a.val_frac))
    perm = torch.randperm(len(tr_ids))
    vi, ti = perm[:n_val], perm[n_val:]
    dl = DataLoader(TensorDataset(X[ti], Y[ti]), batch_size=a.batch, shuffle=True)

    net = build_cnn(2, r).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=15, factor=0.5)
    lossf = torch.nn.MSELoss()
    Xv, Yv = X[vi].to(dev), Y[vi].to(dev)
    # 기준선: 계수를 0(=평균장)으로 예측했을 때의 정규화 MSE. 학습이 이걸 밑돌아야 유의미.
    base_mse = float((Yv**2).mean().item())
    print(f"baseline(zero-pred) val_mse={base_mse:.4f}  (학습이 이보다 낮아야 신호 포착)", flush=True)
    best = 1e9; best_state = None; wait = 0
    for ep in range(a.epochs):
        net.train(); tr_loss = 0.0; nb = 0
        for xb, yb in dl:
            opt.zero_grad(); out = net(xb.to(dev)); l = lossf(out, yb.to(dev))
            l.backward(); opt.step(); tr_loss += l.item(); nb += 1
        tr_loss /= max(nb, 1)
        net.eval()
        with torch.no_grad():
            vl = lossf(net(Xv), Yv).item()
        sched.step(vl)
        if vl < best-1e-5:
            best = vl; best_state = {k: v.cpu().clone() for k, v in net.state_dict().items()}; wait = 0
        else:
            wait += 1
        if ep % 10 == 0 or wait == 0:
            print(f"ep{ep:3d} train={tr_loss:.4f} val={vl:.4f} best={best:.4f}", flush=True)
        if wait > 60:
            print("early stop", flush=True); break
    if best_state:
        net.load_state_dict(best_state)

    # ---- test 평가 ----
    net.eval()
    with torch.no_grad():
        Ate_n = net(torch.tensor(occte).to(dev)).cpu().numpy()
    Ate = Ate_n * a_scale
    recon = (mean_v.reshape(-1) + Ate @ Phi.T).reshape(len(te_ids), 3, NZ, NY, NX)
    rows = {}
    ev = []
    for i, cid in enumerate(te_ids):
        aa, iou, cd = eval_case(Ute[i], recon[i], occte[i, 0], mean_v)
        ev.append([aa, iou, cd])
        rows[cid] = {"anomL2": round(float(aa), 3), "iou": round(float(iou), 3),
                     "cdist_mm": round(float(cd), 1)}
    ev = np.array(ev)
    summary = {"pool": a.pool, "grid": [NZ, NY, NX], "r": int(r),
               "anomL2_med": float(np.median(ev[:, 0])),
               "iou_med": float(np.median(ev[:, 1])), "iou_min": float(ev[:, 1].min()),
               "cdist_mm_med": float(np.median(ev[:, 2])), "per_case": rows}
    Path(a.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    torch.save(net.state_dict(), a.save_model)
    print("\n=== CNN test10 ===")
    print(f"anomL2_med={summary['anomL2_med']:.3f}  IoU_med={summary['iou_med']:.3f}  "
          f"IoU_min={summary['iou_min']:.3f}  cdist_med={summary['cdist_mm_med']:.1f}mm")
    print("비교기준(POD+RF, pool2): anomL2 0.612 / IoU 0.718 / cdist 7.2mm | ceiling 0.293/0.861/2.7")
    print(f"→ {a.out}, {a.save_model}")


if __name__ == "__main__":
    main()
