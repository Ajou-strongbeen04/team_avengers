#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漁벤져스 · A층 후처리(리샘플) — 원시 raw/{case}.tgz → dataset npz
------------------------------------------------------------------
배치 실행과 분리(원시필드는 버킷 보관 → 이 단계는 언제든 재실행/조정 가능).
grid_spec.json(96x48x48, cell-centered, 정규화 [0,1]^3)로 시간평균장을 리샘플하고
구조물 점유마스크·라벨을 붙여 case별 .npz 로 저장.

저장 배열:
  UMean(nz,ny,nx,3) · nutMean · kMean · omegaMean · pMean (nz,ny,nx)
  mask_occ(nz,ny,nx) 0/1 · mask_kind(nz,ny,nx) {0 none,1 rock,2 plant}
  meta: case_id, n_obstacles, blockage_frac, obstacles(list)
※ phiMean(면플럭스)은 정규격자에서 UMean으로부터 B층에서 재구성(FV 일관) — 여기선 U 저장.

의존: pip install --break-system-packages pyvista numpy
사용: python3 postprocess.py --raw raw_dir --grid grid_spec.json --csv cases.csv --out dataset
      (raw_dir 는 gs://BUCKET/raw 를 gsutil로 내려받은 로컬 폴더, 또는 gcsfuse 마운트)
"""
import argparse, csv, json, tarfile, tempfile
from pathlib import Path
import numpy as np

LX, LY, LZ = 0.47, 0.21, 0.21
ROCK = {"S": (0.04, 0.04, 0.04), "M": (0.07, 0.06, 0.07), "L": (0.11, 0.08, 0.10)}   # w,dp,h
PLANT = {"S": (0.02, 0.08), "M": (0.035, 0.12), "L": (0.05, 0.16)}                    # r,h
CELL_FIELDS = ["UMean", "nutMean", "kMean", "omegaMean", "pMean"]


def grid_centers(nx, ny, nz):
    xs = (np.arange(nx) + 0.5) / nx * LX
    ys = (np.arange(ny) + 0.5) / ny * LY
    zs = (np.arange(nz) + 0.5) / nz * LZ
    return xs, ys, zs


def build_masks(obstacles, nx, ny, nz):
    xs, ys, zs = grid_centers(nx, ny, nz)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")   # (nx,ny,nz)
    occ = np.zeros((nx, ny, nz), np.uint8)
    kind = np.zeros((nx, ny, nz), np.uint8)
    for o in obstacles:
        cx, cy = o["x"] * LX, o["y"] * LY
        if o["kind"] == "rock":
            w, dp, h = ROCK[o["size"]]
            m = (np.abs(X-cx) <= w/2) & (np.abs(Y-cy) <= dp/2) & (Z <= h)
            occ[m] = 1; kind[m] = 1
        else:
            r, h = PLANT[o["size"]]
            m = ((X-cx)**2 + (Y-cy)**2 <= r**2) & (Z <= h)
            occ[m] = 1; kind[m] = 2
    # 저장은 (nz,ny,nx) 규약
    return np.transpose(occ, (2, 1, 0)), np.transpose(kind, (2, 1, 0))


def resample_case(case_dir, nx, ny, nz):
    import pyvista as pv
    foam = Path(case_dir) / "case.foam"
    foam.write_text("")
    rd = pv.OpenFOAMReader(str(foam))
    rd.set_active_time_value(max(rd.time_values))    # latestTime
    mesh = rd.read()["internalMesh"]
    xs, ys, zs = grid_centers(nx, ny, nz)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    pts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    probe = pv.PolyData(pts).sample(mesh)
    out = {}
    for f in CELL_FIELDS:
        if f not in probe.point_data:
            continue
        a = np.asarray(probe.point_data[f])
        if a.ndim == 2 and a.shape[1] == 3:
            out[f] = a.reshape(nx, ny, nz, 3).transpose(2, 1, 0, 3)
        else:
            out[f] = a.reshape(nx, ny, nz).transpose(2, 1, 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, help="raw/{case}.tgz 로컬 폴더")
    ap.add_argument("--grid", default="grid_spec.json")
    ap.add_argument("--csv", default="cases.csv")
    ap.add_argument("--out", default="dataset")
    args = ap.parse_args()

    g = json.load(open(args.grid, encoding="utf-8"))
    res = g["resolution"][g["active"]]
    nx, ny, nz = res["nx"], res["ny"], res["nz"]
    meta = {r["case_id"]: r for r in csv.DictReader(open(args.csv, encoding="utf-8"))}
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)

    for tgz in sorted(Path(args.raw).glob("*.tgz")):
        cid = tgz.stem
        row = meta.get(cid, {})
        obs = json.loads(row.get("obstacles_json", "[]"))
        with tempfile.TemporaryDirectory() as td:
            with tarfile.open(tgz) as t:
                t.extractall(td)
            fields = resample_case(td, nx, ny, nz)
        occ, kind = build_masks(obs, nx, ny, nz)
        np.savez_compressed(
            outdir / f"{cid}.npz",
            mask_occ=occ, mask_kind=kind,
            case_id=cid, n_obstacles=int(row.get("n_obstacles", len(obs))),
            blockage_frac=float(row.get("blockage_frac", 0.0)),
            obstacles=json.dumps(obs), **fields)
        print(f"  {cid}: fields={list(fields)} occ={int(occ.sum())}")
    print(f"[done] → {outdir}")


if __name__ == "__main__":
    main()
