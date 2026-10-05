#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX3 · A층 전체 스윕 케이스 생성기 (漁벤져스) — 다중 구조물 지원
------------------------------------------------------------------
cases.csv(obstacles_json) → 각 case{NNNN}/ OpenFOAM 케이스 디렉터리.
pilot/generate_cases.py 의 폐합을 그대로 계승하되 **여러 구조물(obs0..obsK)** 지원.
  - 폭기 플룸(고정): cylinderToCell (0.02,0.035) r=0.01 z 0.02..0.21, Su=2.86 (EX2 상속)
  - 바위: explicitPorositySource DarcyForchheimer d=1e6 f=1e3 (near-solid), box 기하
  - 식물: explicitPorositySource DarcyForchheimer d=0 f=Cf{2,5,15}, cylinder 기하 [R34]
  - 불변 파일(blockMesh/fvSchemes/fvSolution/controlDict/constant/0.orig)은 template에서 복사
  - 케이스별 생성: system/topoSetDict, system/fvOptions, Allrun, Allclean

사용:
  python3 gen_cases.py --csv cases.csv --template pilot/template_case --out flow
"""
import argparse, csv, json, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

LX, LY, LZ = 0.47, 0.21, 0.21
PLUME = dict(x=0.02, y=0.035, r=0.01, z0=0.02, z1=0.21)
SU_AIR = 2.86

ROCK = {"S": dict(w=0.04, dp=0.04, h=0.04),
        "M": dict(w=0.07, dp=0.06, h=0.07),
        "L": dict(w=0.11, dp=0.08, h=0.10)}
PLANT = {"S": dict(r=0.02, h=0.08, Cf=2.0),
         "M": dict(r=0.035, h=0.12, Cf=5.0),
         "L": dict(r=0.05, h=0.16, Cf=15.0)}
ROCK_D, ROCK_F = 1.0e6, 1.0e3

FOAM_HEADER = (
    "/*--------------------------------*- C++ -*----------------------------------*\\\n"
    "| 漁벤져스 EX3 A층 · 자동생성 (gen_cases.py) — 수정 금지                       |\n"
    "\\*---------------------------------------------------------------------------*/\n"
)
def foam_file(obj):
    return f"FoamFile {{ version 2.0; format ascii; class dictionary; object {obj}; }}\n"


def toposet_obstacle(i, o):
    """obs{i} cellZone 액션 (box=rock / cylinder=plant)."""
    x, y = o["x"] * LX, o["y"] * LY
    nc, nz = f"obs{i}Cells", f"obs{i}"
    if o["kind"] == "rock":
        g = ROCK[o["size"]]
        x0, x1 = x-g["w"]/2, x+g["w"]/2
        y0, y1 = y-g["dp"]/2, y+g["dp"]/2
        return (f"    // obs{i} rock {o['size']} @({x:.3f},{y:.3f}) box\n"
                f"    {{ name {nc}; type cellSet; action new; source boxToCell;\n"
                f"      box ({x0:.4f} {y0:.4f} {-1e-4:.4f}) ({x1:.4f} {y1:.4f} {g['h']:.4f}); }}\n"
                f"    {{ name {nz}; type cellZoneSet; action new; source setToCellZone; set {nc}; }}\n")
    g = PLANT[o["size"]]
    return (f"    // obs{i} plant {o['size']} @({x:.3f},{y:.3f}) cylinder r={g['r']} h={g['h']}\n"
            f"    {{ name {nc}; type cellSet; action new; source cylinderToCell;\n"
            f"      point1 ({x:.4f} {y:.4f} 0.0); point2 ({x:.4f} {y:.4f} {g['h']:.4f}); radius {g['r']}; }}\n"
            f"    {{ name {nz}; type cellZoneSet; action new; source setToCellZone; set {nc}; }}\n")


def make_toposet(obs):
    a = [FOAM_HEADER, foam_file("topoSetDict"), "\nactions\n(\n"]
    a.append(
        "    { name plumeCells; type cellSet; action new; source cylinderToCell;\n"
        f"      point1 ({PLUME['x']} {PLUME['y']} {PLUME['z0']}); "
        f"point2 ({PLUME['x']} {PLUME['y']} {PLUME['z1']}); radius {PLUME['r']}; }}\n"
        "    { name plume; type cellZoneSet; action new; source setToCellZone; set plumeCells; }\n")
    for i, o in enumerate(obs):
        a.append(toposet_obstacle(i, o))
    a.append(");\n")
    return "".join(a)


def porosity_block(name, zone, dvec, fvec):
    return (f"{name}\n{{\n"
            "    type            explicitPorositySource;\n"
            "    explicitPorositySourceCoeffs\n    {\n"
            f"        selectionMode   cellZone;\n        cellZone        {zone};\n"
            "        type            DarcyForchheimer;\n"
            f"        d               ({dvec[0]} {dvec[1]} {dvec[2]});\n"
            f"        f               ({fvec[0]} {fvec[1]} {fvec[2]});\n"
            "        coordinateSystem\n        {\n"
            "            type        cartesian;\n            origin      (0 0 0);\n"
            "            rotation    { type axesRotation; e1 (1 0 0); e2 (0 1 0); }\n"
            "        }\n    }\n}\n")


def make_fvoptions(obs):
    a = [FOAM_HEADER, foam_file("fvOptions"), "\n"]
    a.append(
        "airLift\n{\n"
        "    type            vectorSemiImplicitSource;\n"
        "    selectionMode   cellZone;\n    cellZone        plume;\n"
        "    volumeMode      specific;\n    injectionRateSuSp\n"
        f"    {{ U ((0 0 {SU_AIR}) 0); }}\n}}\n\n")
    for i, o in enumerate(obs):
        if o["kind"] == "rock":
            a.append(porosity_block(f"rockBlock{i}", f"obs{i}",
                                    (ROCK_D,)*3, (ROCK_F,)*3))
        else:
            cf = PLANT[o["size"]]["Cf"]
            a.append(porosity_block(f"plantDrag{i}", f"obs{i}",
                                    (0, 0, 0), (cf, cf, cf)))
    return "".join(a)


ALLRUN = """#!/bin/sh
cd "${0%/*}" || exit 1
. ${WM_PROJECT_DIR:?}/bin/tools/RunFunctions
# 漁벤져스 EX3 A층 · Stage A 유동(pimpleFoam 과도 URANS, 8코어). EX2 절차 상속.
restore0Dir
runApplication blockMesh
runApplication topoSet
runApplication decomposePar
runParallel $(getApplication)
runApplication reconstructPar -latestTime
grep -E "ExecutionTime|ClockTime" log.pimpleFoam | tail -3
"""
ALLCLEAN = """#!/bin/sh
cd "${0%/*}" || exit 1
. ${WM_PROJECT_DIR:?}/bin/tools/CleanFunctions
cleanCase
rm -rf 0
"""


def build_case(row, template, outdir):
    cid = row["case_id"]
    obs = json.loads(row["obstacles_json"]) if row.get("obstacles_json") else []
    dst = outdir / cid
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(template, dst)
    (dst / "system" / "topoSetDict").write_text(make_toposet(obs), encoding="utf-8")
    (dst / "system" / "fvOptions").write_text(make_fvoptions(obs), encoding="utf-8")
    for fn, txt in (("Allrun", ALLRUN), ("Allclean", ALLCLEAN)):
        p = dst / fn
        p.write_text(txt, encoding="utf-8"); p.chmod(0o755)
    return cid, len(obs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(HERE / "cases.csv"))
    ap.add_argument("--template", default=str(HERE / "pilot" / "template_case"))
    ap.add_argument("--out", default=str(HERE / "flow"))
    args = ap.parse_args()

    template, outdir = Path(args.template), Path(args.out)
    assert template.exists(), f"template 없음: {template}"
    outdir.mkdir(parents=True, exist_ok=True)

    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"[gen_cases] {len(rows)} 케이스 -> {outdir}")
    hist = {}
    for r in rows:
        _, n = build_case(r, template, outdir)
        hist[n] = hist.get(n, 0) + 1
    print(f"[done] 구조물수 분포(개수:케이스): {dict(sorted(hist.items()))}")
    print("       각 케이스에서 ./Allrun (OpenFOAM ESI).")


if __name__ == "__main__":
    main()
