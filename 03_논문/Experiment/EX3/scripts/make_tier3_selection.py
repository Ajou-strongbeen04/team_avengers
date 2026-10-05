#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tier3 보충 선별 — 바위·조밀·고차단 편향 층화 표집.

漁벤져스 · 04_어플리케이션/02_BC축소모델 · 2026-07-24
근거: Stage2-B 진단(`06_ROM_Stage2B_CNN.md`) — CNN이 바위 후류에서 실패,
      0141형(대형바위·고blockage)은 ceiling 자체 낮음 → 이 구성이 데이터에 희박.
목표: cases.csv tier3(320) 중 ~50을 우선생성 후보로. n∈{3,4,5,6} 균등 + 바위비중·blockage 상위 편향.
출력: tier3_selection.csv (case_id·구성·점수) + 요약.
"""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd


def comp(s):
    try:
        o = json.loads(s)
    except Exception:
        o = []
    nr = sum(x["kind"] == "rock" for x in o)
    npl = sum(x["kind"] == "plant" for x in o)
    return nr, npl, len(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-csv", required=True)
    ap.add_argument("--n-select", type=int, default=50)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    cs = pd.read_csv(a.cases_csv)
    t3 = cs[cs.tier == 3].copy()
    t3[["nr", "npl", "no"]] = t3["obstacles_json"].apply(lambda s: pd.Series(comp(s)))
    # 점수: 바위비중(0.6) + 정규화 blockage(0.4). 바위후류·조밀이 실패모드.
    rock_frac = t3["nr"] / t3["no"].clip(lower=1)
    blk_n = (t3["blockage_frac"] - t3["blockage_frac"].min()) / (
        t3["blockage_frac"].max() - t3["blockage_frac"].min() + 1e-9)
    t3["score"] = 0.6 * rock_frac + 0.4 * blk_n

    per_n = a.n_select // 4  # n=3,4,5,6 균등 배분
    rng = np.random.default_rng(a.seed)
    picks = []
    for n in (3, 4, 5, 6):
        sub = t3[t3.no == n].sort_values("score", ascending=False)
        top = sub.head(per_n * 2)                       # 상위 후보풀
        k = min(per_n, len(top))
        # 상위풀에서 blockage 스펙트럼 유지하며 표집(상·중·하 포함)
        chosen = top.sample(k, random_state=int(rng.integers(1e9)))
        picks.append(chosen)
    sel = pd.concat(picks).sort_index()
    out = sel[["case_id", "tier", "no", "nr", "npl", "blockage_frac", "score", "obstacles_json"]]
    out.to_csv(a.out, index=False)

    print(f"선별 {len(sel)}/{len(t3)} (tier3)")
    print("n분포:", sel["no"].value_counts().sort_index().to_dict())
    print("바위수분포:", sel["nr"].value_counts().sort_index().to_dict())
    print("all-rock(npl=0):", int((sel.npl == 0).sum()),
          " rock우세(nr>=npl):", int((sel.nr >= sel.npl).sum()))
    print("blockage: min %.3f med %.3f max %.3f"
          % (sel.blockage_frac.min(), sel.blockage_frac.median(), sel.blockage_frac.max()))
    print("cases.csv 인덱스:", sorted(sel.index.tolist()))
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
