#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2_X3 · 케이스 생성기

새 운전점(Q_air 실측 1.2 L/min, T=25 C, alpha_g=0.1807, Su=1.773)에서
EX2 가 실제로 필요로 하는 CFD 만 만든다. 16위치 재실행은 하지 않는다(README §1).

만드는 것
  D군  수위 스윕 4케이스  d = 0.18/0.15/0.12/0.09   (d=0.21 은 EX2_X1/case_su177 재사용)
  P군  위치 강건성 3케이스 pos1/pos12/pos13 @ d=0.21 (kappa 위치 무의존성, 방법론 6.2)
  M군  medium 앵커 1케이스 @ d=0.21               (절대 kappa + coarse 편향의 Su 불변성)

템플릿
  coarse : ../EX2_X1/case_su177     (Su=1.773 로 이미 검증된 coarse 케이스)
  medium : ../EX2/CFD/study/medium_0.02   (Su=2.86 → fvOptions 만 교체)

usage:
    python3 gen_cases.py            # 전부 생성
    python3 gen_cases.py --stage 2  # D군의 Su 만 fp_result.csv 값으로 갱신(재생성 아님)
    python3 gen_cases.py --list     # 생성 목록·셀수·예상시간만 출력
"""
import argparse
import csv
import os
import re
import shutil
import sys

# Windows 콘솔(cp949)에서 ✅·— 같은 문자 출력 시 UnicodeEncodeError 로 죽는 것 방지.
# 2026-07-29: MSYS 창은 UTF-8 인데 python 기본 stdout 이 cp949 라 한글도 깨졌다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


HERE = os.path.dirname(os.path.abspath(__file__))
TPL_C = os.path.join(HERE, "..", "EX2_X", "case_su177")
TPL_M = os.path.join(HERE, "..", "EX2", "CFD", "study", "medium_0.02")

# ---- 기준 운전점 (../EX2_X1/README.md §4.2 확정) ---------------------
SU0 = 1.773            # alpha_g = 0.18079, a = 2169 /m
LX, LY = 0.47, 0.21
DZ_REF_C = 0.21 / 37   # coarse 기준 dz = 5.676 mm
DZ_REF_M = 0.21 / 48   # medium 기준 dz = 4.375 mm
PLUME_R = 0.01
Z_START = 0.02         # 에어스톤 바닥 이격 (상수_목록 E군, 전 수준 공통)

# ---- 케이스 정의 -----------------------------------------------------------
#  (id, 격자, 수심 d, 플룸축 (x,y), 비고)
DEPTHS = [0.18, 0.15, 0.12, 0.09]                 # 0.21 = case_su177 재사용
# 위치 3점은 기존 16위치 medium(Su=2.86)의 W 분포를 **span** 하도록 고른다.
#   W 범위 0.3201–0.4153 (CV 7.8 %), 되먹임 alpha_g CV 7.0 %
#   → 최소 pos15 · 중앙 pos4 · 최대 pos1. (상위 3개를 고르면 산포가 0.5 % 로
#     뭉개져 위치 무의존성 검정이 무의미해진다 — 2026-07-29 확인)
POSITIONS = [("p15", 0.035, 0.075),               # positions.csv pos15 (W 최소)
             ("p04", 0.075, 0.035),               #             pos4  (W 중앙)
             ("p01", 0.015, 0.035)]               #             pos1  (W 최대)
PLUME_REF = (0.13, 0.035)                         # study/·case_su177 과 동일 축

# coarse 기준 벽시간 (study/results.csv coarse_0.02 = 2458 s @ 114,996셀)
SEC_PER_CELL_C = 2457.611 / 114996
SEC_PER_CELL_M = 8047.958 / 248832


def nz_for(d, dz_ref):
    """물리 수심 d 를 그대로 지키면서 dz 가 기준에 가장 가깝도록 nz 선정."""
    return max(4, int(round(d / dz_ref)))


def sub(text, pat, repl, flags=re.M):
    new, k = re.subn(pat, repl, text, flags=flags)
    if k == 0:
        raise RuntimeError(f"치환 실패: {pat}")
    return new


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# --------------------------------------------------------------- 딕셔너리 --
def make_blockmesh(tpl, d, nz):
    t = open(os.path.join(tpl, "system", "blockMeshDict"), encoding="utf-8",
             errors="ignore").read()
    t = sub(t, r"^Lz\s+[\d.eE+-]+\s*;.*$", f"Lz  {d};      // 수위(가변)")
    t = sub(t, r"^nz\s+\d+\s*;.*$", f"nz  {nz};      // dz = {1000*d/nz:.3f} mm")
    return t


def make_toposet(tpl, d, nz, px, py):
    dz = d / nz
    t = open(os.path.join(tpl, "system", "topoSetDict"), encoding="utf-8",
             errors="ignore").read()
    # 플룸 원기둥: 바닥이격 Z_START ~ 수면 d
    t = sub(t, r"point1 \([^)]*\)", f"point1 ({px} {py} {Z_START})")
    t = sub(t, r"point2 \([^)]*\)", f"point2 ({px} {py} {d})")
    t = sub(t, r"radius\s+[\d.eE+-]+\s*;", f"radius {PLUME_R};")
    # 표층 1셀 / 바닥층 1셀 박스를 수위에 맞춰 다시 씀
    t = sub(t,
            r"box \(0 0 [\d.eE+-]+\) \([\d.eE+-]+ [\d.eE+-]+ [\d.eE+-]+\); \}\n"
            r"    \{ name surface;",
            f"box (0 0 {d - dz:.6f}) ({LX} {LY} {d + 1e-4:.6f}); }}\n"
            f"    {{ name surface;")
    t = sub(t,
            r"box \(0 0 -0\.0001\) \([\d.eE+-]+ [\d.eE+-]+ [\d.eE+-]+\);",
            f"box (0 0 -0.0001) ({LX} {LY} {dz:.6f});")
    return t


def make_fvoptions(tpl, su, note):
    t = open(os.path.join(tpl, "system", "fvOptions"), encoding="utf-8",
             errors="ignore").read()
    t = sub(t, r"U\s+\(\(0 0 [\d.eE+-]+\) 0\);.*$",
            f"U           ((0 0 {su:.4g}) 0);   // Su = alpha_g*g, Sp=0  [{note}]")
    return t


def make_controldict(tpl, d):
    """프로브 z 를 수위에 비례 축소 (얕은 수조에서 격자 밖 프로브 방지)."""
    t = open(os.path.join(tpl, "system", "controlDict"), encoding="utf-8",
             errors="ignore").read()
    s = d / 0.21

    def scale(m):
        x, y, z = float(m.group(1)), float(m.group(2)), float(m.group(3))
        return f"({x:g} {y:g} {z*s:.4f})"

    body = re.search(r"probeLocations\s*\((.*?)\n\s*\);", t, re.S)
    if body:
        new = re.sub(r"\(([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\)", scale,
                     body.group(1))
        t = t[:body.start(1)] + new + t[body.end(1):]
    return t


# ------------------------------------------------------------------ 생성 --
def build(cid, tpl, d, nz, px, py, su, note):
    dst = os.path.join(HERE, cid)
    # 덮어쓰기 방식(rmtree 하지 않음) — OneDrive 동기화 중 삭제가 막히는 환경 대응.
    # stale 메시/결과는 run.sh 의 Allrun 단계가 지운다.
    os.makedirs(os.path.join(dst, "system"), exist_ok=True)
    shutil.copytree(os.path.join(tpl, "0.orig"), os.path.join(dst, "0.orig"),
                    dirs_exist_ok=True)
    os.makedirs(os.path.join(dst, "constant"), exist_ok=True)
    for f in ("transportProperties", "turbulenceProperties"):
        shutil.copy(os.path.join(tpl, "constant", f),
                    os.path.join(dst, "constant", f))
    for f in ("fvSchemes", "fvSolution", "decomposeParDict"):
        shutil.copy(os.path.join(tpl, "system", f),
                    os.path.join(dst, "system", f))

    write(os.path.join(dst, "system", "blockMeshDict"), make_blockmesh(tpl, d, nz))
    write(os.path.join(dst, "system", "topoSetDict"),
          make_toposet(tpl, d, nz, px, py))
    write(os.path.join(dst, "system", "fvOptions"), make_fvoptions(tpl, su, note))
    write(os.path.join(dst, "system", "controlDict"), make_controldict(tpl, d))
    return dst


def catalog():
    """생성할 전체 케이스 목록."""
    rows = []
    for d in DEPTHS:
        nz = nz_for(d, DZ_REF_C)
        rows.append(dict(cid=f"d{int(round(d*100)):02d}", grp="D", tpl=TPL_C,
                         d=d, nz=nz, nx=84, ny=37,
                         px=PLUME_REF[0], py=PLUME_REF[1], su=SU0,
                         note=f"수위 {d} m · stage1 시드"))
    for cid, px, py in POSITIONS:
        rows.append(dict(cid=cid, grp="P", tpl=TPL_C, d=0.21, nz=37, nx=84, ny=37,
                         px=px, py=py, su=SU0, note=f"위치 강건성 ({px}, {py})"))
    rows.append(dict(cid="m21", grp="M", tpl=TPL_M, d=0.21, nz=48, nx=108, ny=48,
                     px=PLUME_REF[0], py=PLUME_REF[1], su=SU0,
                     note="medium 앵커 (절대 kappa)"))
    for r in rows:
        r["cells"] = r["nx"] * r["ny"] * r["nz"]
        spc = SEC_PER_CELL_M if r["grp"] == "M" else SEC_PER_CELL_C
        r["sec"] = r["cells"] * spc
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="목록만 출력")
    ap.add_argument("--stage", type=int, default=1,
                    help="1=전체 생성(시드 Su), 2=D군 Su만 fp_result.csv 로 갱신")
    a = ap.parse_args()

    rows = catalog()

    if a.stage == 2:
        fp = os.path.join(HERE, "fp_result.csv")
        if not os.path.exists(fp):
            sys.exit("fp_result.csv 없음 — 먼저 stage1 실행 후 fixedpoint.py 를 도십시오.")
        su_of = {r["cid"]: float(r["Su_fp"])
                 for r in csv.DictReader(open(fp, encoding="utf-8"))}
        todo = []
        for r in rows:
            if r["grp"] != "D" or r["cid"] not in su_of:
                continue
            p = os.path.join(HERE, r["cid"], "system", "fvOptions")
            cur = float(re.search(r"0 0 ([\d.eE+-]+)",
                                  open(p, encoding="utf-8").read()).group(1))
            new = su_of[r["cid"]]
            shift = new / cur - 1
            if abs(shift) <= 0.03:
                print(f"  {r['cid']}: Su {cur:.4g} → {new:.4g}  "
                      f"({100*shift:+.1f} %, 3 % 이내) → 재실행 불필요")
                continue
            write(p, make_fvoptions(r["tpl"], new,
                                    f"수위 {r['d']} m · stage2 자기일관"))
            todo.append(r["cid"])
            print(f"  {r['cid']}: Su {cur:.4g} → {new:.4g}  "
                  f"({100*shift:+.1f} %) → fvOptions 갱신, 재실행 필요")

        # run.sh 가 읽는다. 비어 있으면 stage2 전체를 건너뛴다.
        with open(os.path.join(HERE, "stage2_todo.txt"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(" ".join(todo) + "\n")
        if todo:
            print(f"\nstage2 재실행 대상: {' '.join(todo)}"
                  f"  (stage2_todo.txt 기록)")
        else:
            print("\n전 수준이 3 % 이내 → stage2 재실행 없음. stage3 로 넘어갑니다.")
        return

    tot = 0.0
    print(f"{'id':6}{'군':>3}{'격자':>16}{'셀수':>10}{'수심':>7}{'플룸축':>18}"
          f"{'Su':>8}{'예상':>9}")
    print("-" * 78)
    for r in rows:
        if not a.list:
            build(r["cid"], r["tpl"], r["d"], r["nz"], r["px"], r["py"],
                  r["su"], r["note"])
        tot += r["sec"]
        mesh = "{}x{}x{}".format(r["nx"], r["ny"], r["nz"])
        axis = "({}, {})".format(r["px"], r["py"])
        print(f"{r['cid']:6}{r['grp']:>3}{mesh:>16}"
              f"{r['cells']:>10,}{r['d']:>7.2f}{axis:>18}"
              f"{r['su']:>8.4g}{r['sec']/60:>7.0f} 분")
    print("-" * 78)
    print(f"{'합계':6}{len(rows):>3}{'':>16}{'':>10}{'':>7}{'':>18}{'':>8}"
          f"{tot/3600:>7.2f} h   (stage1)")
    print(f"  + D군 stage2 재실행 {sum(r['sec'] for r in rows if r['grp']=='D')/3600:.2f} h"
          f"  → 총 {(tot + sum(r['sec'] for r in rows if r['grp']=='D'))/3600:.2f} h")
    known = {r["cid"] for r in rows}
    stray = sorted(d for d in os.listdir(HERE)
                   if os.path.isdir(os.path.join(HERE, d))
                   and os.path.isdir(os.path.join(HERE, d, "system"))
                   and d not in known)
    if stray:
        print(f"\n  [주의] 카탈로그에 없는 케이스 폴더: {', '.join(stray)}")
        print("         run.sh 는 이들을 돌리지 않습니다. 지워도 됩니다.")

    if not a.list:
        print("\n생성 완료. 다음: bash run.sh")


if __name__ == "__main__":
    main()
