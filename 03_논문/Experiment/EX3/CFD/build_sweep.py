#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX3 · A층 전체 스윕 매트릭스 생성기 (漁벤져스)
------------------------------------------------------------------
sweep_design.md §4 계층 스윕(Tier0~3)을 cases.csv(단일 진실원)로 확정한다.
  - Tier0: 대조군 n=0 (1)
  - Tier1: 단일 구조물 완전 스윕 = 종류{rock,plant}×크기{S,M,L}×앵커위치(12)
  - Tier2: 2개 구조물 (공간충전 표집)
  - Tier3: 3~N개 구조물 (공간충전 표집, n 층화)
제약: 벽 이격 · 폭기 플룸 이격 · 구조물 상호 비겹침 · 총 blockage 상한.
좌표는 정규화 [0,1]^2 (x/Lx, y/Ly), 03_BC_출력스키마 obstacles[].region_norm 규약.
ROM은 유동장 전용 → 식물 대사는 유동에 무관하므로 스윕축 아님(라벨 plant_metab=photo 고정).

출력 cases.csv 컬럼:
  case_id, tier, n_obstacles, obstacles_json, blockage_frac, plant_metab, seed
  obstacles_json = '[{"kind":"rock","size":"M","x":0.55,"y":0.50}, ...]'

사용:
  python3 build_sweep.py --total 700 --seed 17000 --out cases.csv
"""
import argparse, csv, json, math, random
from pathlib import Path

# ---- 고정 기하 (EX2 상속, generate_cases.py와 동일) ----
LX, LY, LZ = 0.47, 0.21, 0.21
TANK_VOL = LX * LY * LZ
PLUME = dict(x=0.02, y=0.035, r=0.01)          # 벽걸이 코너 폭기
PLUME_BOX = (PLUME["x"]-PLUME["r"], PLUME["x"]+PLUME["r"],
             PLUME["y"]-PLUME["r"], PLUME["y"]+PLUME["r"])

# ---- 구조물 크기 등급 (generate_cases.py와 동일 치수) ----
ROCK = {"S": dict(w=0.04, dp=0.04, h=0.04),
        "M": dict(w=0.07, dp=0.06, h=0.07),
        "L": dict(w=0.11, dp=0.08, h=0.10)}
PLANT = {"S": dict(r=0.02, h=0.08, Cf=2.0),
         "M": dict(r=0.035, h=0.12, Cf=5.0),
         "L": dict(r=0.05, h=0.16, Cf=15.0)}
KINDS = ["rock", "plant"]
SIZES = ["S", "M", "L"]

# ---- 제약 여유 [m] ----
M_WALL   = 0.010   # 벽 이격
G_PLUME  = 0.015   # 폭기 플룸 이격
G_OBS    = 0.010   # 구조물 상호 이격
BMAX     = 0.50    # 총 blockage(체적분율) 상한

# ---- Tier1 앵커 위치 (sweep_design §3: 4×3=12) ----
ANCHORS = [(x, y) for x in (0.15, 0.35, 0.55, 0.75) for y in (0.25, 0.50, 0.75)]


def footprint(o):
    """정규화 중심 → 실치수 bbox (x0,x1,y0,y1) [m]."""
    x, y = o["x"] * LX, o["y"] * LY
    if o["kind"] == "rock":
        g = ROCK[o["size"]]
        return (x-g["w"]/2, x+g["w"]/2, y-g["dp"]/2, y+g["dp"]/2)
    g = PLANT[o["size"]]
    return (x-g["r"], x+g["r"], y-g["r"], y+g["r"])


def volume(o):
    if o["kind"] == "rock":
        g = ROCK[o["size"]]; return g["w"]*g["dp"]*g["h"]
    g = PLANT[o["size"]]; return math.pi*g["r"]**2*g["h"]


def boxes_clear(b1, b2, gap):
    """두 bbox가 gap 이상 떨어져 있으면 True."""
    return (b1[1]+gap <= b2[0] or b2[1]+gap <= b1[0] or
            b1[3]+gap <= b2[2] or b2[3]+gap <= b1[2])


def feasible(o, others):
    b = footprint(o)
    if not (b[0] >= M_WALL and b[1] <= LX-M_WALL and
            b[2] >= M_WALL and b[3] <= LY-M_WALL):
        return False
    if not boxes_clear(b, PLUME_BOX, G_PLUME):
        return False
    for oo in others:
        if not boxes_clear(b, footprint(oo), G_OBS):
            return False
    return True


def blockage(obs):
    return sum(volume(o) for o in obs) / TANK_VOL


def rnd_obstacle(rng):
    return dict(kind=rng.choice(KINDS), size=rng.choice(SIZES),
                x=round(rng.uniform(0.03, 0.97), 3),
                y=round(rng.uniform(0.05, 0.95), 3))


def sample_case(n, rng, tries=4000):
    """n개 구조물을 제약 만족하도록 배치. 실패시 None."""
    for _ in range(tries):
        obs = []
        ok = True
        for _ in range(n):
            placed = False
            for _ in range(200):
                o = rnd_obstacle(rng)
                if feasible(o, obs):
                    obs.append(o); placed = True; break
            if not placed:
                ok = False; break
        if ok and blockage(obs) <= BMAX:
            return obs
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=700)
    ap.add_argument("--seed", type=int, default=17000)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "cases.csv"))
    ap.add_argument("--t3-ns", default="3,4,5,6", help="Tier3 구조물 개수 후보(층화)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = []
    idx = 0

    def add(tier, obs):
        nonlocal idx
        cid = f"case{idx:04d}"
        rows.append(dict(case_id=cid, tier=tier, n_obstacles=len(obs),
                         obstacles_json=json.dumps(obs, separators=(",", ":")),
                         blockage_frac=round(blockage(obs), 4),
                         plant_metab="photo", seed=args.seed + idx))
        idx += 1

    # Tier0
    add(0, [])

    # Tier1: 종류×크기×앵커 (제약 위반 조합은 스킵)
    t1 = 0
    for kind in KINDS:
        for size in SIZES:
            for (x, y) in ANCHORS:
                o = dict(kind=kind, size=size, x=x, y=y)
                if feasible(o, []):
                    add(1, [o]); t1 += 1
    n_t1 = t1

    # 남은 예산 → Tier2/Tier3 반반
    remaining = args.total - idx
    if remaining < 0:
        remaining = 0
    n_t2 = remaining // 2
    n_t3 = remaining - n_t2

    # Tier2: 2개
    made2 = 0
    while made2 < n_t2:
        obs = sample_case(2, rng)
        if obs:
            add(2, obs); made2 += 1

    # Tier3: 3~N개 (n 층화 순환)
    t3_ns = [int(v) for v in args.t3_ns.split(",")]
    made3 = 0
    while made3 < n_t3:
        n = t3_ns[made3 % len(t3_ns)]
        obs = sample_case(n, rng)
        if obs:
            add(3, obs); made3 += 1

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "tier", "n_obstacles",
                                          "obstacles_json", "blockage_frac",
                                          "plant_metab", "seed"])
        w.writeheader(); w.writerows(rows)

    # ---- 요약 ----
    from collections import Counter
    tc = Counter(r["tier"] for r in rows)
    bl = [r["blockage_frac"] for r in rows]
    print(f"[build_sweep] 총 {len(rows)} 케이스 -> {args.out}")
    print(f"  Tier0={tc[0]}  Tier1={tc[1]}(앵커스윕, 유효 {n_t1}/72)  "
          f"Tier2={tc[2]}  Tier3={tc[3]}")
    print(f"  blockage_frac: min={min(bl):.3f} mean={sum(bl)/len(bl):.3f} max={max(bl):.3f}")
    print("  다음: python3 gen_cases.py --csv cases.csv --template pilot/template_case --out flow/")


if __name__ == "__main__":
    main()
