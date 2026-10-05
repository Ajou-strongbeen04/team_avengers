#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2_X4 · 케이스 생성기 — 에어스톤 침지 높이 z_start 스윕

무엇을 만드나
  Z군  z_start = 0.05 / 0.08 / 0.11  (3케이스, coarse 84x37x37, d=0.21)
       z_start = 0.02 는 ../EX2_X1/case_su177 을 **재사용**한다(이미 완주).

무엇이 바뀌나 (딱 두 곳)
  system/topoSetDict  : 플룸 원기둥의 point1 z = z_start   (수면 z=0.21 은 고정)
  system/fvOptions    : Su = alpha_g*g  (stage1 은 시드 1.773, stage2 는 자기일관값)

무엇이 안 바뀌나
  blockMeshDict(격자 동일 · 셀수 114,996) · controlDict · fvSchemes/fvSolution ·
  transportProperties/turbulenceProperties · 수심 d=0.21 · 플룸축 (0.13, 0.035) ·
  플룸 반경 0.01 m.
  → 수위 축(EX2_X3 D군)과 결정적으로 다른 점: **V 가 고정**이라 수면항
    k_L,s*A_s/V 가 그대로 있고, 플룸 길이 H_p = 0.21 - z_start 만 줄어든다.
    수위 축을 무력화한 1/V 증폭(README §1)이 여기서는 발생하지 않는다.

usage:
    python3 gen_cases.py            # 전부 생성 (stage1 시드 Su)
    python3 gen_cases.py --list     # 목록·셀수·예상시간만
    python3 gen_cases.py --stage 2  # Z군 Su 를 fp_result.csv 값으로 갱신(재생성 아님)
"""
import argparse
import csv
import os
import re
import shutil
import sys

# Windows 콘솔(cp949)에서 한글·이모지 출력 시 UnicodeEncodeError 로 죽는 것 방지.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "..", "EX2_X", "case_su177")

# ---- 기준 운전점 (../EX2_X1/README.md §4.2 · ../EX2_X3 §5.3) ----
SU0 = 1.773            # stage1 시드 Su (= d21 coarse 고정점)
DEPTH = 0.21           # 수심 고정
PLUME_AXIS = (0.13, 0.035)
PLUME_R = 0.01

# z_start 수준. 0.02 는 case_su177 재사용.
#   1차(2026-07-29): 0.05/0.08/0.11 — 레버가 100→65 % 밖에 안 나와 hold-out 외삽이
#                    잡음의 1–2배에 그쳤다(README §4.3).
#   2차 연장(2026-07-30): 0.14·0.17 추가 → span 100→36 % 목표.
#     ※ 1차에서 0.14 를 뺀 이유("90 % 도달 292분")는 해석추정 기반이었고,
#       CFD 실측 레버가 훨씬 약해 실제로는 ~98분이다. 전제가 뒤집혀 복원한다.
Z_LEVELS = [0.05, 0.08, 0.11, 0.14, 0.17]

# coarse 기준 벽시간 (EX2/CFD/study/results.csv coarse_0.02 = 2458 s @ 114,996셀)
SEC_PER_CELL = 2457.611 / 114996
NX, NY, NZ = 84, 37, 37


def cid_of(z):
    return "z{:02d}".format(int(round(z * 100)))


def sub(text, pat, repl, flags=re.M):
    new, k = re.subn(pat, repl, text, flags=flags)
    if k == 0:
        raise RuntimeError(f"치환 실패: {pat}")
    return new


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def make_toposet(z_start):
    """플룸 원기둥의 바닥 z 만 z_start 로 올린다. 표층·바닥층 박스는 건드리지 않는다."""
    t = open(os.path.join(TPL, "system", "topoSetDict"),
             encoding="utf-8", errors="ignore").read()
    px, py = PLUME_AXIS
    t = sub(t, r"point1 \([^)]*\)", f"point1 ({px} {py} {z_start})")
    t = sub(t, r"point2 \([^)]*\)", f"point2 ({px} {py} {DEPTH})")
    t = sub(t, r"radius\s+[\d.eE+-]+\s*;", f"radius {PLUME_R};")
    # 주석의 z 범위 표기도 갱신 (읽는 사람이 헷갈리지 않게)
    t = re.sub(r"z=0\.02~0\.21", f"z={z_start}~{DEPTH}", t)
    t = re.sub(r"z 시작 0\.02[^\n]*",
               f"z 시작 {z_start} = 에어스톤 침지 높이 (플룸 높이 "
               f"{DEPTH - z_start:.2f} m)", t)
    return t


def make_fvoptions(su, note):
    t = open(os.path.join(TPL, "system", "fvOptions"),
             encoding="utf-8", errors="ignore").read()
    t = sub(t, r"U\s+\(\(0 0 [\d.eE+-]+\) 0\);.*$",
            f"U           ((0 0 {su:.4g}) 0);   // Su = alpha_g*g, Sp=0  [{note}]")
    return t


def has_result(cid):
    """0/ 외의 순수 숫자 시간디렉터리가 있으면 이미 완주한 케이스."""
    d = os.path.join(HERE, cid)
    if not os.path.isdir(d):
        return False
    for n in os.listdir(d):
        if not os.path.isdir(os.path.join(d, n)) or n == "0":
            continue
        if n.replace(".", "").isdigit() and n != "0.orig":
            return True
    return False


def build(z_start, su, note, force=False):
    cid = cid_of(z_start)
    # ★ 완주한 케이스를 덮어쓰면 stage2 로 갱신된 Su 가 시드값으로 되돌아간다
    #   (z11 은 Su=1.906 로 재실행된 상태다). 결과가 있으면 건드리지 않는다.
    if has_result(cid) and not force:
        return None
    dst = os.path.join(HERE, cid)
    # 덮어쓰기 방식(rmtree 하지 않음) — OneDrive 동기화 중 삭제가 막히는 환경 대응.
    # stale 메시/결과는 run.sh 의 실행단계가 지운다.
    os.makedirs(os.path.join(dst, "system"), exist_ok=True)
    shutil.copytree(os.path.join(TPL, "0.orig"), os.path.join(dst, "0.orig"),
                    dirs_exist_ok=True)
    os.makedirs(os.path.join(dst, "constant"), exist_ok=True)
    for f in ("transportProperties", "turbulenceProperties"):
        shutil.copy(os.path.join(TPL, "constant", f),
                    os.path.join(dst, "constant", f))
    for f in ("blockMeshDict", "controlDict", "decomposeParDict",
              "fvSchemes", "fvSolution"):
        shutil.copy(os.path.join(TPL, "system", f),
                    os.path.join(dst, "system", f))
    write(os.path.join(dst, "system", "topoSetDict"), make_toposet(z_start))
    write(os.path.join(dst, "system", "fvOptions"), make_fvoptions(su, note))
    return dst


def catalog():
    cells = NX * NY * NZ
    return [dict(cid=cid_of(z), z=z, Hp=DEPTH - z, su=SU0, cells=cells,
                 sec=cells * SEC_PER_CELL) for z in Z_LEVELS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="목록만 출력")
    ap.add_argument("--stage", type=int, default=1,
                    help="1=생성(시드 Su), 2=fp_result.csv 의 자기일관 Su 로 갱신")
    ap.add_argument("--force", action="store_true",
                    help="완주한 케이스도 덮어쓴다 (stage2 Su 가 시드로 되돌아감 — 주의)")
    a = ap.parse_args()

    rows = catalog()

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
            write(p, make_fvoptions(new, f"z_start {r['z']} m · stage2 자기일관"))
            todo.append(r["cid"])
            print(f"  {r['cid']}: Su {cur:.4g} → {new:.4g}  "
                  f"({100*shift:+.1f} %) → fvOptions 갱신, 재실행 필요")

        with open(os.path.join(HERE, "stage2_todo.txt"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(" ".join(todo) + "\n")
        if todo:
            print(f"\nstage2 재실행 대상: {' '.join(todo)}  (stage2_todo.txt 기록)")
        else:
            print("\n전 수준이 3 % 이내 → stage2 재실행 없음. collect 로 넘어갑니다.")
        return

    if not os.path.isdir(TPL):
        sys.exit(f"템플릿 없음: {TPL}")

    tot = 0.0
    print(f"{'id':6}{'z_start':>9}{'H_p':>7}{'플룸셀':>8}{'격자':>14}{'셀수':>10}"
          f"{'Su(시드)':>10}{'예상':>9}  상태")
    print("-" * 82)
    for r in rows:
        done = has_result(r["cid"])
        if not a.list:
            build(r["z"], r["su"], f"z_start {r['z']} m · stage1 시드", a.force)
        if not done:
            tot += r["sec"]
        mesh = f"{NX}x{NY}x{NZ}"
        nlay = r["Hp"] / (DEPTH / NZ)
        print(f"{r['cid']:6}{r['z']:>9.2f}{r['Hp']:>7.2f}{nlay:>8.1f}{mesh:>14}"
              f"{r['cells']:>10,}{r['su']:>10.4g}{r['sec']/60:>7.0f} 분"
              f"  {'완주(보존)' if done else '신규'}")
    print("-" * 82)
    print(f"  신규분 stage1 {tot/3600:.2f} h  + stage2 재실행(전 수준 가정) "
          f"{tot/3600:.2f} h  → 최대 {2*tot/3600:.2f} h")
    if any(r["Hp"] / (DEPTH / NZ) < 8 for r in rows):
        print("  [주의] 플룸 층수 8셀 미만 수준이 있다 — coarse 해상도 경계."
              "\n         추세에서 벗어나면 격자 문제를 먼저 의심할 것.")
    print(f"\n  z_start=0.02 은 ../EX2_X1/case_su177 재사용 (생성하지 않음)")

    known = {r["cid"] for r in rows}
    stray = sorted(d for d in os.listdir(HERE)
                   if os.path.isdir(os.path.join(HERE, d))
                   and os.path.isdir(os.path.join(HERE, d, "system"))
                   and d not in known)
    if stray:
        print(f"\n  [주의] 카탈로그에 없는 케이스 폴더: {', '.join(stray)}")
        print("         run.sh 는 이들을 돌리지 않습니다.")

    if not a.list:
        print("\n생성 완료. 다음: bash run.sh")


if __name__ == "__main__":
    main()
