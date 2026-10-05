#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 0 후처리 — OpenFOAM(시각 200) 유동장 → A층 ROM 정렬 텐서 + QoI 라벨.

漁벤져스 · 04_어플리케이션/02_BC축소모델 · 2026-07-24

전 케이스가 동일 blockMesh 108x48x48(uniform)을 공유 → 리샘플 불필요, 격자 이미 정렬.
구조물은 topoSetDict의 boxToCell(rock)/cylinderToCell(plant)로 정의(plume=폭기, 제외).

출력 per case: fields/caseXXXX.npz
    X_occ : (2, nz, ny, nx) float32  ch0=점유(0/1), ch1=kind(rock=+1/plant=-1)
    Y_U   : (3, nz, ny, nx) float32  UMean (m/s)
    Y_nut : (nz, ny, nx)    float32  nutMean (m^2/s, 생값)
    (옵션 --with-k: Y_k, Y_omega)
공통 격자순서: flat index = i + nx*j + nx*ny*k  →  reshape (nz,ny,nx) [k,j,i]
"""
import argparse, gzip, json, re, sys
from pathlib import Path
import numpy as np

# ---- 격자 규격 (blockMeshDict 상속, 전 케이스 고정) ----
NX, NY, NZ = 108, 48, 48
LX, LY, LZ = 0.47, 0.21, 0.21
NCELL = NX * NY * NZ
DX, DY, DZ = LX / NX, LY / NY, LZ / NZ
# 셀 중심 좌표 (1D)
XC = (np.arange(NX) + 0.5) * DX
YC = (np.arange(NY) + 0.5) * DY
ZC = (np.arange(NZ) + 0.5) * DZ

DEADSPOT_THR = 0.005  # 5 mm/s (QC 문서 dead-spot 정의)


def _open(path: Path):
    return gzip.open(path, "rt") if path.suffix == ".gz" else open(path, "rt")


def parse_internal_field(path: Path, ncomp: int):
    """OpenFOAM internalField(nonuniform/uniform) → (N, ncomp) 또는 (N,) 배열."""
    with _open(path) as f:
        txt = f.read()
    m = re.search(r"internalField\s+uniform\s+(.+?);", txt, re.S)
    if m:  # uniform
        vals = re.findall(r"[-+0-9.eE]+", m.group(1))
        v = np.array(vals[:max(1, ncomp)], dtype=np.float64)
        if ncomp == 1:
            return np.full(NCELL, v[0], dtype=np.float32)
        return np.tile(v[:ncomp], (NCELL, 1)).astype(np.float32)
    # nonuniform
    m = re.search(r"nonuniform\s+List<\w+>\s*\n?\s*(\d+)\s*\(", txt, re.S)
    if not m:
        raise ValueError(f"{path}: internalField 파싱 실패")
    n = int(m.group(1))
    start = m.end()
    body = txt[start:]
    # boundaryField 이전까지만 취해 후행 비수치 데이터 제거
    cut = body.find("boundaryField")
    if cut != -1:
        body = body[:cut]
    for ch in "();":
        body = body.replace(ch, " ")
    nums = np.fromstring(body, sep=" ", dtype=np.float64)
    if ncomp == 1:
        arr = nums[:n]
        assert arr.size == NCELL, f"{path}: {arr.size} != {NCELL}"
        return arr.astype(np.float32)
    arr = nums[: n * ncomp].reshape(n, ncomp)
    assert arr.shape[0] == NCELL, f"{path}: {arr.shape[0]} != {NCELL}"
    return arr.astype(np.float32)


def to_grid_vec(flat_vec):  # (N,3) -> (3,nz,ny,nx)
    g = flat_vec.reshape(NZ, NY, NX, 3)  # [k,j,i,c]
    return np.transpose(g, (3, 0, 1, 2)).copy()


def to_grid_sca(flat):  # (N,) -> (nz,ny,nx)
    return flat.reshape(NZ, NY, NX).copy()


# ---- 구조물 인코딩 ----
_BOX_RE = re.compile(
    r"source\s+boxToCell;\s*box\s*\(([^)]+)\)\s*\(([^)]+)\)", re.S)
_CYL_RE = re.compile(
    r"source\s+cylinderToCell;\s*point1\s*\(([^)]+)\)\s*point2\s*\(([^)]+)\)\s*radius\s+([-+0-9.eE]+)",
    re.S)
_COMMENT_RE = re.compile(r"//\s*obs\d+\s+(rock|plant)\s+([SML])", re.I)


_OBS_KIND_RE = re.compile(r"//\s*obs(\d+)\s+(rock|plant)\s+([SML])", re.I)
_NAME_RE = re.compile(r"name\s+obs(\d+)Cells")
_BOX_RE = re.compile(r"boxToCell;\s*box\s*\(([^)]+)\)\s*\(([^)]+)\)", re.S)
_CYL_RE = re.compile(r"cylinderToCell;\s*point1\s*\(([^)]+)\)[;\s]*point2\s*\(([^)]+)\)[;\s]*"
                     r"radius\s+([-+0-9.eE]+)", re.S)


def parse_obstacles(topo_path: Path):
    """topoSetDict → 구조물 리스트. plume(폭기)은 obsN 이름이 아니므로 자동 제외.
    action 블록 `{ ... }` 단위로 파싱(경계 넘나듦 방지). kind는 comment 우선, 없으면 geometry로 추정."""
    txt = topo_path.read_text(errors="ignore")
    kinds = {int(i): k.lower() for i, k, _ in _OBS_KIND_RE.findall(txt)}
    geo = {}
    for block in re.findall(r"\{[^{}]*\}", txt, re.S):  # 각 action 블록
        nm = _NAME_RE.search(block)
        if not nm:
            continue
        idx = int(nm.group(1))
        mb = _BOX_RE.search(block)
        if mb:
            geo[idx] = {"type": "box",
                        "p0": np.array(mb.group(1).split(), float),
                        "p1": np.array(mb.group(2).split(), float)}
            continue
        mc = _CYL_RE.search(block)
        if mc:
            geo[idx] = {"type": "cyl",
                        "c1": np.array(mc.group(1).split(), float),
                        "c2": np.array(mc.group(2).split(), float),
                        "r": float(mc.group(3))}
    obstacles = []
    for idx in sorted(geo):
        kind = kinds.get(idx) or ("rock" if geo[idx]["type"] == "box" else "plant")
        obstacles.append({"kind": kind, **geo[idx]})
    return obstacles


def encode_occupancy(obstacles):
    occ = np.zeros((NZ, NY, NX), np.float32)
    kindg = np.zeros((NZ, NY, NX), np.float32)
    if not obstacles:
        return np.stack([occ, kindg])
    XX, YY, ZZ = np.meshgrid(XC, YC, ZC, indexing="ij")  # (nx,ny,nz)
    for ob in obstacles:
        sign = 1.0 if ob["kind"] == "rock" else -1.0
        if ob["type"] == "box":
            lo = np.minimum(ob["p0"], ob["p1"]); hi = np.maximum(ob["p0"], ob["p1"])
            mask = ((XX >= lo[0]) & (XX <= hi[0]) & (YY >= lo[1]) & (YY <= hi[1]) &
                    (ZZ >= lo[2]) & (ZZ <= hi[2]))
        else:  # cylinder (축은 z; point1/point2 동일 x,y)
            cx, cy = ob["c1"][0], ob["c1"][1]
            z0, z1 = min(ob["c1"][2], ob["c2"][2]), max(ob["c1"][2], ob["c2"][2])
            rad = np.sqrt((XX - cx) ** 2 + (YY - cy) ** 2)
            mask = (rad <= ob["r"]) & (ZZ >= z0) & (ZZ <= z1)
        m_kji = np.transpose(mask, (2, 1, 0))  # (nx,ny,nz)->(nz,ny,nx)
        occ[m_kji] = 1.0
        kindg[m_kji] = sign
    return np.stack([occ, kindg])


def compute_qoi(Umag, occ):
    fluid = occ < 0.5  # 구조물 셀 제외
    um = Umag.copy(); um[~fluid] = np.nan
    Uflat = um[fluid]
    idx = np.unravel_index(np.nanargmin(um), um.shape)  # (k,j,i)
    k, j, i = idx
    pos_norm = [float(XC[i] / LX), float(YC[j] / LY), float(ZC[k] / LZ)]
    return {
        "U0_max": float(np.nanmax(Umag)),        # 폭기 플룸 최대 (전 셀)
        "Umean_mag": float(np.nanmean(Uflat)),
        "Umin": float(np.nanmin(Uflat)),
        "deadspot_pos_norm": pos_norm,
        "frac_below_5mm": float(np.mean(Uflat < DEADSPOT_THR)),
        "frac_below_2mm": float(np.mean(Uflat < 0.002)),
        "n_fluid_cells": int(fluid.sum()),
    }


def process_case(case_dir: Path, out_dir: Path, with_k=False):
    cid = case_dir.name
    t = "200"
    U = parse_internal_field(case_dir / t / "UMean.gz", 3)
    nut = parse_internal_field(case_dir / t / "nutMean.gz", 1)
    Y_U = to_grid_vec(U)
    Y_nut = to_grid_sca(nut)
    obstacles = parse_obstacles(case_dir / "system" / "topoSetDict")
    X_occ = encode_occupancy(obstacles)
    Umag = np.sqrt((Y_U ** 2).sum(0))
    qoi = compute_qoi(Umag, X_occ[0])
    qoi.update(case_id=cid, n_obstacles=len(obstacles),
               n_rock=sum(o["kind"] == "rock" for o in obstacles),
               n_plant=sum(o["kind"] == "plant" for o in obstacles),
               occ_frac=float(X_occ[0].mean()))
    save = dict(X_occ=X_occ, Y_U=Y_U, Y_nut=Y_nut)
    if with_k:
        save["Y_k"] = to_grid_sca(parse_internal_field(case_dir / t / "kMean.gz", 1))
        save["Y_omega"] = to_grid_sca(parse_internal_field(case_dir / t / "omegaMean.gz", 1))
    np.savez_compressed(out_dir / f"{cid}.npz", **save)
    return qoi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--with-k", action="store_true")
    ap.add_argument("--only", default=None, help="쉼표구분 case id (검증용)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-existing", action="store_true", help="이미 npz 있으면 건너뜀(재개)")
    ap.add_argument("--max-seconds", type=float, default=0, help="이 시간 지나면 정상 종료(청크 실행)")
    args = ap.parse_args()
    import time as _time
    _t0 = _time.time()

    result_dir = Path(args.result_dir)
    out_dir = Path(args.out_dir); (out_dir / "fields").mkdir(parents=True, exist_ok=True)
    cases = sorted([d for d in result_dir.iterdir()
                    if d.is_dir() and d.name.startswith("case")])
    if args.only:
        want = set(args.only.split(","))
        cases = [c for c in cases if c.name in want]
    if args.limit:
        cases = cases[: args.limit]

    import pandas as pd
    fields_dir = out_dir / "fields"
    lab_csv = out_dir / "labels.csv"
    prev = {}
    if lab_csv.exists():
        for r in pd.read_csv(lab_csv).to_dict("records"):
            prev[r["case_id"]] = r
    rows = dict(prev)
    for n, c in enumerate(cases, 1):
        if args.skip_existing and (fields_dir / f"{c.name}.npz").exists() and c.name in prev:
            continue
        if args.max_seconds and (_time.time() - _t0) > args.max_seconds:
            print(f"[중단] 시간예산 {args.max_seconds}s 초과 — 재개 필요", flush=True)
            break
        try:
            q = process_case(c, fields_dir, with_k=args.with_k)
            q["deadspot_pos_norm"] = json.dumps(q["deadspot_pos_norm"])  # csv 안전
            rows[c.name] = q
            print(f"[{n}/{len(cases)}] {c.name}  n={q['n_obstacles']} "
                  f"U0={q['U0_max']:.3f} Umean={q['Umean_mag']:.4f} "
                  f"f5={q['frac_below_5mm']:.3f}", flush=True)
            if n % 20 == 0:  # 중간 체크포인트
                pd.DataFrame(list(rows.values())).to_csv(lab_csv, index=False)
        except Exception as e:
            print(f"[{n}/{len(cases)}] {c.name}  FAIL: {e}", flush=True)
    df = pd.DataFrame(list(rows.values()))
    df.to_csv(lab_csv, index=False)
    df.to_parquet(out_dir / "labels.parquet")
    print(f"\n완료: {len(df)} 케이스 라벨 → {out_dir}")


if __name__ == "__main__":
    main()
