#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2_X5 · 케이스 생성기 — kappa(z=0.02) 이상 규명

무엇을 왜 만드나
    본시험 5런(2026-08-01) 결과, kappa 가 두 군으로 갈렸다.
        kappa(z=0.020) = 0.952 +- 0.014  (3런)
        kappa(z=0.080) = 1.063 / kappa(z=0.170) = 1.057   (차이 -0.58 %)
    즉 CFD 는 0.08 -> 0.17 레버를 **-0.6 %** 로 정확히 맞추는데,
    0.02 -> 0.08 레버만 **+11.7 %** 빗나간다. 이상은 z=0.02 **한 점**에 있다.
    (근거: EX2/어항실험/S1-S4_종합분석_20260802.md §A.5)

    ** 2026-08-02 P0 실측: 에어스톤을 바닥에 놓았을 때 기포 방출중심 = 바닥에서 20 mm.
       기록값 0.020 m 과 일치한다 -> 가설 (a) 기준면 불일치 **기각**. **
    남은 가설:
      (b) 바닥 근접 물리 — 플룸 밑 20 mm 를 CFD 는 빈 물로 두지만 실제로는
          에어스톤 몸통 + 바닥이다. 자유 유입을 과대평가해 z=0.02 에서만 10 % 과대예측
      (c) 격자 해상 — coarse 가 0.02->0.08 레버를 제대로 못 푼다

케이스 네 군
    P군 (coarse, **실험 실제 폭기축 (0.035, 0.195)**)   ★2026-08-02 좌표 확정으로 신설
        p13z02 p13z08 p13z17
        -> 기존 z-스윕은 전부 플룸축 (0.13, 0.035) 에서 돌았다. 실험은 다른 자리였다.
           폭 0.21 대칭으로 (0.035, 0.015) = positions.csv **pos13** 과 정확히 일치.
           위치별 3-D 산포 12~14 % 가 kappa 절대값에 **균일 배율**로 실린다.
           (전 5런이 같은 위치이므로 z=0.02 이상의 원인은 아니다.)

    M군 (medium 108x48x48, 템플릿 ../EX2_X3/m21)
        mz08 mz17   -> (c) 를 **완전히 제거**한다.
                       m21(=medium z=0.02) 과 같은 격자에서 z=0.08·0.17 을 직접 풀면
                       coarse->medium 환산 없이 kappa 를 뽑을 수 있다.  ★최우선

    B군 (coarse 84x37x37, 템플릿 ../EX2_X1/case_su177)
        b01 b03 b04 b06  (z_start = 0.010 / 0.030 / 0.040 / 0.060)
        -> 바닥 근방 K_La(z) 를 10 mm 간격으로 해상한다.
           현재 표는 0.02 와 0.05 사이가 비어 있어(30 mm 공백) 실측을 z_eff 로
           역산할 때 3차 보간에 의존한다. 곡선이 매끄러운지 자체가 (b) 의 방증이다.

    C군 (coarse, 차폐 변형)
        c02blk  z_start=0.020 + 플룸 밑 원기둥에 Darcy 싱크 -> (b) 의 **직접 시험**
                목표: 3-D K_La 2.703 -> 2.420 (-10.5 %) 이면 실측과 정합

무엇이 바뀌나 (딱 두 곳 — EX2_X4 와 동일)
    system/topoSetDict : 플룸 원기둥 point1 의 z = z_start (수면 0.21 고정)
    system/fvOptions   : Su = alpha_g*g (stage1 시드, stage2 자기일관)

무엇이 안 바뀌나
    격자·수심 0.21·플룸반경 0.01·표층/바닥층 셀존·
    (플룸축은 P군만 (0.035, 0.195) 로 바뀌고 나머지 군은 (0.13, 0.035) 유지)
    controlDict·fvSchemes/fvSolution·transportProperties/turbulenceProperties

usage:
    python3 gen_cases.py --list          # 목록·셀수·예상시간만
    python3 gen_cases.py                 # 전부 생성 (stage1 시드 Su)
    python3 gen_cases.py --family PC     # P군·C군만
    python3 gen_cases.py --stage 2       # fp_result.csv 의 자기일관 Su 로 갱신
"""
import argparse
import csv
import os
import re
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TPL_COARSE = os.path.join(HERE, "..", "EX2_X", "case_su177")   # 84x37x37
TPL_MEDIUM = os.path.join(HERE, "..", "EX2_X3", "m21")         # 108x48x48

DEPTH = 0.21
PLUME_AXIS = (0.13, 0.035)      # CFD z-스윕 기본축 (m21 · case_su177 · EX2_X4)
PLUME_AXIS_EXP = (0.035, 0.195) # ★ 실험 실측 폭기축 (2026-08-02 확정)
                                #   폭 0.21 대칭 -> 등가 (0.035, 0.015) = positions.csv pos13
PLUME_R = 0.01

# 벽시간 척도: EX2/CFD/study/results.csv coarse_0.02 = 2457.611 s @ 114,996 셀
SEC_PER_CELL = 2457.611 / 114996

# ---- 케이스 정의 -----------------------------------------------------------
#   su_seed = 그 격자의 z=0.02 자기일관 고정점
#     coarse : 1.773  (../EX2_X §4.2, case_su177)
#     medium : 1.751  (m21 고정점, ../상수_목록.md §D 각주 alpha_g=0.1785)
FAMILIES = {
    "M": dict(tpl=TPL_MEDIUM, grid=(108, 48, 48), su_seed=1.751,
              ref=("m21", os.path.join(HERE, "..", "EX2_X3", "m21")),
              levels=[("mz08", 0.080), ("mz17", 0.170)]),
    "B": dict(tpl=TPL_COARSE, grid=(84, 37, 37), su_seed=1.773,
              ref=("z02", os.path.join(HERE, "..", "EX2_X", "case_su177")),
              levels=[("b01", 0.010), ("b03", 0.030),
                      ("b04", 0.040), ("b06", 0.060)]),
    # C군 — 바닥 차폐. 2026-08-02 P0 실측(방출중심 20 mm = 기록값)으로 기하오차 가설이
    #        기각되면서 남은 유일한 물리 가설이다.
    #   현행 CFD 는 z_start 아래 20 mm 를 **빈 물**로 두어 플룸이 밑에서 자유롭게
    #   유입(entrainment)한다. 실제로는 그 자리에 에어스톤 몸통이 있고 바로 밑이 바닥이다.
    #   → 그 원기둥에 Darcy 싱크를 걸어 U→0 으로 만들고 K_La 가 얼마나 깎이는지 본다.
    #   목표: 3-D K_La 2.703 → 2.420 (−10.5 %) 이면 실측과 정합.
    #   stage1/stage2 를 **별도 케이스**로 분리한다 — run.sh 의 stage2 재실행이
    #   stage1 유동장을 지워버려 1:1 대조(같은 Su)를 잃기 때문이다.
    #     c02blk   : Su=1.773  → z02 와 **동일 강제**. 차폐 순효과 1:1 대조
    #     c02blkfp : Su=2.376  → stage1 실측 W=0.17652 로 산출한 예측 고정점
    "C": dict(tpl=TPL_COARSE, grid=(84, 37, 37), su_seed=1.773,
              ref=("z02", os.path.join(HERE, "..", "EX2_X", "case_su177")),
              levels=[("c02blk", 0.020, 1.773), ("c02blkfp", 0.020, 2.376)],
              block=True),
    # P군 — **실험이 실제로 쓴 폭기 위치**. 2026-08-02 좌표 확정으로 신설.
    #   기존 z-스윕은 전부 플룸축 (0.13, 0.035) 에서 돌았는데, 실험은 (0.035, 0.195) 였다.
    #   위치별 3-D 산포가 12~14 % 라 kappa 절대값이 그만큼 흔들린다.
    #   전 5런이 같은 위치이므로 kappa 에는 **균일 배율**로 실린다 — 즉
    #   z=0.02 이상(異常)의 원인은 아니지만, 논문이 보고할 kappa 값 자체를 바꾼다.
    #   p13z02 / p13z08 두 점이면 절대값 + 문제구간(0.02->0.08) 레버를 동시에 얻는다.
    "P": dict(tpl=TPL_COARSE, grid=(84, 37, 37), su_seed=1.773,
              axis=PLUME_AXIS_EXP,
              ref=("z02", os.path.join(HERE, "..", "EX2_X", "case_su177")),
              levels=[("p13z02", 0.020), ("p13z08", 0.080), ("p13z17", 0.170)]),
}

# C군 차폐 원기둥 — 플룸축 아래 z ∈ [0, z_start]
#   반경 기본값은 플룸 반경(0.01 m) = **최소 시험**. 에어스톤 실물 반경을 재면
#   BLOCK_R 을 그 값으로 바꿀 것 (차폐가 클수록 효과가 커진다).
BLOCK_R = 0.02
BLOCK_SP = -1000.0      # [1/s] 반음해 Sp. |Sp|·dt ≫ 1 이면 U→0. 400~2000 에서 결과 불변 확인할 것


def sub(text, pat, repl, flags=re.M):
    new, k = re.subn(pat, repl, text, flags=flags)
    if k == 0:
        raise RuntimeError(f"치환 실패: {pat}")
    return new


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def make_toposet(tpl, z_start, axis=PLUME_AXIS):
    """플룸 원기둥의 바닥 z 만 옮긴다. 표층·바닥층 박스는 격자에 맞춰져 있으므로 건드리지 않는다."""
    t = open(os.path.join(tpl, "system", "topoSetDict"),
             encoding="utf-8", errors="ignore").read()
    px, py = axis
    t = sub(t, r"point1 \([^)]*\)", f"point1 ({px} {py} {z_start})")
    t = sub(t, r"point2 \([^)]*\)", f"point2 ({px} {py} {DEPTH})")
    t = sub(t, r"radius\s+[\d.eE+-]+\s*;", f"radius {PLUME_R};")
    t = re.sub(r"z=0\.02~0\.21", f"z={z_start}~{DEPTH}", t)
    t = re.sub(r"z 시작 0\.02[^\n]*",
               f"z 시작 {z_start} = 에어스톤 침지 높이 "
               f"(플룸 높이 {DEPTH - z_start:.3f} m)  [EX2_X5]", t)
    return t


def make_fvoptions(tpl, su, note, block=False):
    t = open(os.path.join(tpl, "system", "fvOptions"),
             encoding="utf-8", errors="ignore").read()
    t = sub(t, r"U\s+\(\(0 0 [\d.eE+-]+\) 0\);.*$",
            f"U           ((0 0 {su:.4g}) 0);   // Su = alpha_g*g, Sp=0  [{note}]")
    if block:
        blk = (
            "\n// --- EX2_X5 C군: 에어스톤 몸통 차폐 (Darcy 싱크, U->0) ---\n"
            "stoneBlock\n{\n"
            "    type            vectorSemiImplicitSource;\n"
            "    selectionMode   cellZone;\n"
            "    cellZone        stone;\n"
            "    volumeMode      specific;\n"
            "    injectionRateSuSp\n    {\n"
            f"        U           ((0 0 0) {BLOCK_SP:g});"
            "   // Sp<0 = 운동량 싱크. 플룸 밑 자유유입을 막는다\n"
            "    }\n}\n"
        )
        mark = "\n// *********"
        i = t.rfind(mark)
        t = (t[:i] + blk + t[i:]) if i > 0 else (t + blk)
    return t


def add_stone_zone(text, z_start, axis=PLUME_AXIS):
    """topoSetDict 에 플룸축 아래 차폐 원기둥(cellZone `stone`)을 추가한다."""
    px, py = axis
    blk = (
        "\n    // --- EX2_X5 C군: 에어스톤 몸통 차폐 원기둥 "
        f"z in [0, {z_start}] , r={BLOCK_R} ---\n"
        "    { name stoneCells;  type cellSet; action new; source cylinderToCell;\n"
        f"      point1 ({px} {py} -0.0001); point2 ({px} {py} {z_start}); "
        f"radius {BLOCK_R}; }}\n"
        "    { name stone;       type cellZoneSet; action new; "
        "source setToCellZone; set stoneCells; }\n"
    )
    i = text.rfind(");")
    if i < 0:
        raise RuntimeError("topoSetDict actions 종료 ');' 를 못 찾음")
    return text[:i] + blk + text[i:]


def has_result(cid):
    d = os.path.join(HERE, cid)
    if not os.path.isdir(d):
        return False
    for n in os.listdir(d):
        if not os.path.isdir(os.path.join(d, n)) or n == "0" or n == "0.orig":
            continue
        if n.replace(".", "").isdigit():
            return True
    return False


def build(fam, cid, z_start, su, note, force=False):
    tpl = FAMILIES[fam]["tpl"]
    blk = FAMILIES[fam].get("block", False)
    if has_result(cid) and not force:
        return None
    dst = os.path.join(HERE, cid)
    os.makedirs(os.path.join(dst, "system"), exist_ok=True)
    shutil.copytree(os.path.join(tpl, "0.orig"), os.path.join(dst, "0.orig"),
                    dirs_exist_ok=True)
    os.makedirs(os.path.join(dst, "constant"), exist_ok=True)
    for f in ("transportProperties", "turbulenceProperties"):
        shutil.copy(os.path.join(tpl, "constant", f),
                    os.path.join(dst, "constant", f))
    for f in ("blockMeshDict", "controlDict", "decomposeParDict",
              "fvSchemes", "fvSolution"):
        shutil.copy(os.path.join(tpl, "system", f),
                    os.path.join(dst, "system", f))
    axis = FAMILIES[fam].get("axis", PLUME_AXIS)
    ts = make_toposet(tpl, z_start, axis)
    if blk:
        ts = add_stone_zone(ts, z_start, axis)
    write(os.path.join(dst, "system", "topoSetDict"), ts)
    write(os.path.join(dst, "system", "fvOptions"),
          make_fvoptions(tpl, su, note, block=blk))
    return dst


def catalog(families):
    rows = []
    for fam in families:
        F = FAMILIES[fam]
        nx, ny, nz = F["grid"]
        cells = nx * ny * nz
        for lv in F["levels"]:
            cid, z = lv[0], lv[1]
            su = lv[2] if len(lv) > 2 else F["su_seed"]   # 케이스별 Su 지정 허용
            ax = F.get("axis", PLUME_AXIS)
            rows.append(dict(fam=fam, cid=cid, z=z, Hp=DEPTH - z, su=su,
                             axis=f"{ax[0]:.3f},{ax[1]:.3f}",
                             cells=cells, grid=f"{nx}x{ny}x{nz}",
                             nlay=(DEPTH - z) / (DEPTH / nz),
                             sec=cells * SEC_PER_CELL))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="목록만 출력")
    ap.add_argument("--family", default="PCMB", help="P / C / M / B 조합 (기본 PCMB)")
    ap.add_argument("--stage", type=int, default=1,
                    help="1=생성(시드 Su), 2=fp_result.csv 의 자기일관 Su 로 갱신")
    ap.add_argument("--force", action="store_true",
                    help="완주한 케이스도 덮어쓴다 (stage2 Su 가 시드로 되돌아감 — 주의)")
    a = ap.parse_args()

    fams = [c for c in a.family.upper() if c in FAMILIES]
    if not fams:
        sys.exit("--family 는 P / C / M / B 의 조합 (예: P, PC, PCMB)")
    rows = catalog(fams)

    if a.stage == 2:
        fp = os.path.join(HERE, "fp_result.csv")
        if not os.path.exists(fp):
            sys.exit("fp_result.csv 없음 — stage1 실행 후 fixedpoint.py 를 도십시오.")
        su_of = {r["cid"]: float(r["Su_fp"])
                 for r in csv.DictReader(open(fp, encoding="utf-8"))}
        todo = []
        for r in rows:
            if r["cid"] not in su_of:
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
            # 🔴 2026-08-02 버그수정: block=... 를 빼먹어 stage2 가 차폐 소스를
            #    통째로 잃었다. c02blk stage2 가 '차폐 없는 z02 @ Su=2.376' 으로
            #    돌아갔고(W 가 무차폐 멱법칙 예측과 1.2 % 일치), 자기일관 잔차 -34.7 %
            #    가 물리가 아니라 이 누락 때문이었다.
            write(p, make_fvoptions(FAMILIES[r["fam"]]["tpl"], new,
                                    f"z_start {r['z']} m · stage2 자기일관",
                                    block=FAMILIES[r["fam"]].get("block", False)))
            todo.append(r["cid"])
            print(f"  {r['cid']}: Su {cur:.4g} → {new:.4g}  "
                  f"({100*shift:+.1f} %) → fvOptions 갱신, 재실행 필요")
        with open(os.path.join(HERE, "stage2_todo.txt"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(" ".join(todo) + "\n")
        print(f"\nstage2 재실행 대상: {' '.join(todo) if todo else '없음'}")
        return

    for fam in fams:
        if not os.path.isdir(FAMILIES[fam]["tpl"]):
            sys.exit(f"템플릿 없음: {FAMILIES[fam]['tpl']}")

    tot = 0.0
    print(f"{'군':3}{'id':8}{'z_start':>9}{'H_p':>7}{'플룸축(x,y)':>14}{'플룸셀':>8}"
          f"{'격자':>12}{'셀수':>10}{'Su':>8}{'예상':>9}  상태")
    print("-" * 96)
    for r in rows:
        done = has_result(r["cid"])
        if not a.list:
            build(r["fam"], r["cid"], r["z"], r["su"],
                  f"z_start {r['z']} m · stage1 시드 · EX2_X5", a.force)
        if not done:
            tot += r["sec"]
        print(f"{r['fam']:3}{r['cid']:8}{r['z']:>9.3f}{r['Hp']:>7.3f}"
              f"{r['axis']:>14}{r['nlay']:>8.1f}{r['grid']:>12}{r['cells']:>10,}"
              f"{r['su']:>8.4g}{r['sec']/60:>7.0f} 분"
              f"  {'완주(보존)' if done else '신규'}")
    print("-" * 96)
    print(f"  신규 stage1 {tot/3600:.2f} h  (+ stage2 재실행 최대 동량) "
          f"→ 최대 {2*tot/3600:.2f} h")
    print("  기준 케이스는 생성하지 않는다 — "
          "M군: ../EX2_X3/m21 · B군: ../EX2_X1/case_su177 재사용")
    if any(FAMILIES[r["fam"]].get("block") for r in rows):
        print(f"  [C군] 차폐 원기둥 r={BLOCK_R} m · Sp={BLOCK_SP:g} /s. "
              "에어스톤 실물 반경을 재면 BLOCK_R 을 그 값으로 바꿀 것")
    if any(r["nlay"] < 8 for r in rows):
        print("  [주의] 플룸 층수 8셀 미만 케이스 있음 — 격자 해상 경계. "
              "추세 이탈 시 격자를 먼저 의심할 것")
    if not a.list:
        print("\n생성 완료. 다음: bash run.sh M   (M군 최우선)")


if __name__ == "__main__":
    main()
