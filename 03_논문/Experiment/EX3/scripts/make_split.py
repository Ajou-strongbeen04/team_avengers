#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 — 층화 테스트셋 분할.

漁벤져스 · 04_어플리케이션/02_BC축소모델 · 2026-07-24

층화 축: n_obstacles(1/2) · kind(rock/plant/mixed) · size(S/M/L) · blockage 4분위.
- n=0(case0000)은 train 고정(n=0 회귀 게이트 앵커, 테스트 아님).
- test 목표 10개: n=1:n=2 = 전체 비율(≈1:3) 근사, kind·size·blockage 대표성 확보.
출력: test_split.json  {test:[...], train_val:[...], meta:{...}}
"""
import argparse, json, re
from pathlib import Path
import numpy as np
import pandas as pd


def load_cases(csv_path):
    df = pd.read_csv(csv_path)
    # obstacles_json에서 kind/size 요약
    def summarize(row):
        try:
            obs = json.loads(row["obstacles_json"]) if isinstance(row["obstacles_json"], str) else []
        except Exception:
            obs = []
        kinds = sorted({o.get("kind") for o in obs})
        sizes = [o.get("size") for o in obs]
        kind_lbl = "none" if not kinds else (kinds[0] if len(kinds) == 1 else "mixed")
        # 대표 크기 = 가장 큰 것(S<M<L)
        order = {"S": 0, "M": 1, "L": 2}
        size_lbl = max(sizes, key=lambda s: order.get(s, -1)) if sizes else "none"
        return pd.Series({"kind_lbl": kind_lbl, "size_lbl": size_lbl})
    df = pd.concat([df, df.apply(summarize, axis=1)], axis=1)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-csv", required=True)
    ap.add_argument("--labels", required=True, help="Stage0 labels.parquet (완료 케이스 필터)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-test", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = load_cases(args.cases_csv)
    done = pd.read_parquet(args.labels)["case_id"].tolist()
    df = df[df["case_id"].isin(done)].reset_index(drop=True)  # 완료 케이스만
    rng = np.random.default_rng(args.seed)

    n0 = df[df["n_obstacles"] == 0]["case_id"].tolist()  # train 고정
    pool = df[df["n_obstacles"] >= 1].copy()

    # blockage 4분위 라벨
    pool["blk_q"] = pd.qcut(pool["blockage_frac"], 4, labels=False, duplicates="drop")
    # 복합 층 = (n, kind, size, blk_q)
    pool["stratum"] = (pool["n_obstacles"].astype(str) + "|" + pool["kind_lbl"] + "|"
                       + pool["size_lbl"] + "|" + pool["blk_q"].astype(str))

    # n=1:n=2 목표 배분 (전체 비율 근사)
    n1_total = (pool["n_obstacles"] == 1).sum()
    n2_total = (pool["n_obstacles"] == 2).sum()
    frac1 = n1_total / (n1_total + n2_total)
    n_test1 = max(2, round(args.n_test * frac1))
    n_test2 = args.n_test - n_test1

    def stratified_pick(sub, k):
        """sub 내에서 kind/size/blk 대표성 갖춰 k개 추출."""
        picks = []
        # 우선 각 (kind,size) 조합에서 1개씩 순회 커버
        groups = list(sub.groupby(["kind_lbl", "size_lbl"]))
        rng.shuffle(groups)
        gi = 0
        used = set()
        while len(picks) < k and groups:
            _, g = groups[gi % len(groups)]
            cand = g[~g["case_id"].isin(used)]
            if len(cand):
                c = cand.sample(1, random_state=int(rng.integers(1e9)))["case_id"].iloc[0]
                picks.append(c); used.add(c)
            gi += 1
            if gi > 200:
                break
        # 부족분은 무작위 채움
        remain = sub[~sub["case_id"].isin(used)]
        if len(picks) < k and len(remain):
            extra = remain.sample(min(k - len(picks), len(remain)),
                                  random_state=args.seed)["case_id"].tolist()
            picks += extra
        return picks[:k]

    test1 = stratified_pick(pool[pool["n_obstacles"] == 1], n_test1)
    test2 = stratified_pick(pool[pool["n_obstacles"] == 2], n_test2)
    test = sorted(test1 + test2)
    train_val = sorted([c for c in df["case_id"] if c not in test])

    # 검증 요약
    tdf = pool[pool["case_id"].isin(test)]
    meta = {
        "n_test": len(test), "seed": args.seed,
        "test_n_dist": tdf["n_obstacles"].value_counts().to_dict(),
        "test_kind_dist": tdf["kind_lbl"].value_counts().to_dict(),
        "test_size_dist": tdf["size_lbl"].value_counts().to_dict(),
        "test_blk_range": [float(tdf["blockage_frac"].min()), float(tdf["blockage_frac"].max())],
        "pool_blk_range": [float(pool["blockage_frac"].min()), float(pool["blockage_frac"].max())],
        "n0_in_train": n0,
        "n_train_val": len(train_val),
    }
    out = {"test": test, "train_val": train_val, "meta": meta}
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"\ntest({len(test)}):", test)
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
