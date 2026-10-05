#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EX2 CFD · 케이스 생성기 — 실측 3수준 (e02 / e08 / e17)

무엇을 만드나
    어항 실측 5런과 1:1 대조할 CFD 케이스 **3개**만 만든다.
        e02  z_start=0.020   <- S1·S2·S3 (생산 운전점, n=3)
        e08  z_start=0.080   <- S4
        e17  z_start=0.170   <- S5 (hold-out)
    폭기축은 전부 **(0.035, 0.195)** — 실험이 실제로 쓴 자리다.
    유동해는 수온과 무관하므로(nu 고정) 3케이스로 5런을 전부 덮는다.
    수온은 스칼라(재폭기) 단계에서 런별 실측값으로 들어간다 -> run_reaer.py

템플릿
    ../../EX2_예외검증/EX2_X3/m21 의 dict 를 CFD/template/ 로 이미 복사해 뒀다.
    격자 108x48x48 (medium, 249k). medium 을 쓰는 이유는
    "절대값은 medium 앵커, 레버는 coarse" 라는 **환산 규약 자체를 없애기 위해서**다.

무엇이 바뀌나 (딱 세 곳)
    system/topoSetDict : 플룸 원기둥 축 -> (0.035, 0.195), 바닥 z -> z_start
    system/fvOptions   : Su = alpha_g*g   (stage1 시드 -> stage2 자기일관)
    system/controlDict : probes1 -> 실측 프로브 3점 + 진단점

usage
    python3 gen_cases.py --list      # 목록·셀수·예상시간만
    python3 gen_cases.py             # 3케이스 생성 (stage1 시드 Su)
    python3 gen_cases.py --stage 2   # fp_result.csv 의 자기일관 Su 로 fvOptions 갱신
    python3 gen_cases.py --force     # 결과가 있어도 다시 생성
"""
import argparse
import csv
import os
import re
import shutil
import sys

import constants as K

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "template")

# 벽시간 — **2026-08-02 stage1 실측** (8프로세스). 셀수 선형 외삽은 틀렸다:
#   dt 가 Courant 제한이라 플룸이 길수록(W 클수록) 스텝이 잘게 쪼개져 더 오래 걸린다.
#   구 추정(coarse 41분 × 셀수비 = 89분)은 e02 실제 116분을 30 % 과소평가했다.
WALL_MEASURED_S = {"e02": 6987.4, "e08": 5932.7, "e17": 3346.7}
SEC_PER_CELL = 2457.611 / 114996        # 미측정 케이스용 폴백


def sub(text, pat, repl, flags=re.M):
    new, n = re.subn(pat, repl, text, flags=flags)
    if n == 0:
        raise RuntimeError(f"치환 실패: {pat}")
    return new


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def make_toposet(z_start):
    """플룸 원기둥의 축과 바닥 z 를 바꾼다. 표층·바닥층 박스는 격자 종속이라 안 건드린다."""
    t = open(os.path.join(TPL, "system", "topoSetDict"),
             encoding="utf-8", errors="ignore").read()
    px, py = K.PLUME_AXIS
    t = sub(t, r"point1 \([^)]*\)", f"point1 ({px} {py} {z_start})")
    t = sub(t, r"point2 \([^)]*\)", f"point2 ({px} {py} {K.DEPTH})")
    t = sub(t, r"radius\s+[\d.eE+-]+\s*;", f"radius {K.PLUME_R};")
    # 헤더 주석을 실제 값으로 갱신 (구 주석이 남으면 다음 사람이 속는다)
    t = re.sub(r"\|.*기본 = pos5.*\n", "", t)
    t = re.sub(r"// --- 폭기 플룸[^\n]*\n[^\n]*\n",
               f"// --- 폭기 플룸(벽걸이 원기둥): 축 ({px}, {py}) = **실험 실측 폭기축**, "
               f"z={z_start}~{K.DEPTH} ---\n"
               f"    //     z 시작 {z_start} = 에어스톤 기포 방출중심 "
               f"(플룸 높이 {K.DEPTH - z_start:.3f} m)  [CFD]\n", t)
    return t


def make_fvoptions(su, note):
    t = open(os.path.join(TPL, "system", "fvOptions"),
             encoding="utf-8", errors="ignore").read()
    t = sub(t, r"U\s+\(\(0 0 [\d.eE+-]+\) 0\);.*$",
            f"U           ((0 0 {su:.4g}) 0);   // Su = alpha_g*g, Sp=0  [{note}]")
    # 헤더의 구 alpha_g=0.29 주석 제거 — 폐기값이다
    t = re.sub(r"\|\s*F_air/rho[^\n]*\n", "", t)
    t = re.sub(r"\|\s*Su = 0\.29[^\n]*\n", "", t)
    t = t.replace("| EX2 · 폭기 부력 소스(운동량). 플룸 셀존에 상향 체적력",
                  "| EX2 CFD · 폭기 부력 소스. F_air/rho = alpha_g*g [m/s^2]\n"
                  "| alpha_g 는 Q_air=1.2 L/min 실측 + W 되먹임의 자기일관 고정점")
    return t


def make_controldict(cid):
    """probes1 을 실측 프로브 좌표로 교체한다. CFD 대조는 라벨이 아니라 좌표로 한다."""
    t = open(os.path.join(TPL, "system", "controlDict"),
             encoding="utf-8", errors="ignore").read()
    pr = K.probes_for(cid)
    body = "\n".join(f"            ({x:.4f} {y:.4f} {z:.4f})   // {n}"
                     for n, (x, y, z) in pr.items())
    t = sub(t, r"probeLocations\s*\n\s*\(\n.*?\n\s*\);",
            f"probeLocations\n        (\n{body}\n        );",
            flags=re.S)
    t = re.sub(r"//\s*※ 폭기위치가 이동하므로[^\n]*\n[^\n]*\n",
               "//  ※ CFD: 실측 프로브 3점(S1-S4_종합분석 부록 C.1) + 진단점.\n", t)
    return t


def has_result(cid):
    d = os.path.join(HERE, cid)
    if not os.path.isdir(d):
        return False
    for n in os.listdir(d):
        if not os.path.isdir(os.path.join(d, n)) or n in ("0", "0.orig"):
            continue
        if n.replace(".", "").isdigit():
            return True
    return False


def build(cid, z_start, su, note, force=False):
    if has_result(cid) and not force:
        return None
    dst = os.path.join(HERE, cid)
    os.makedirs(os.path.join(dst, "system"), exist_ok=True)
    os.makedirs(os.path.join(dst, "constant"), exist_ok=True)
    shutil.copytree(os.path.join(TPL, "0.orig"), os.path.join(dst, "0.orig"),
                    dirs_exist_ok=True)
    for f in ("transportProperties", "turbulenceProperties"):
        shutil.copy(os.path.join(TPL, "constant", f),
                    os.path.join(dst, "constant", f))
    for f in ("blockMeshDict", "decomposeParDict", "fvSchemes", "fvSolution"):
        shutil.copy(os.path.join(TPL, "system", f),
                    os.path.join(dst, "system", f))
    write(os.path.join(dst, "system", "topoSetDict"), make_toposet(z_start))
    write(os.path.join(dst, "system", "fvOptions"), make_fvoptions(su, note))
    write(os.path.join(dst, "system", "controlDict"), make_controldict(cid))
    return dst


def catalog():
    nx, ny, nz = K.GRID
    cells = nx * ny * nz
    rows = []
    for c in K.CASES:
        z = c["z_start"]
        rows.append(dict(cid=c["cid"], z=z, Hp=K.DEPTH - z,
                         nlay=(K.DEPTH - z) / (K.DEPTH / nz),
                         cells=cells, grid=f"{nx}x{ny}x{nz}",
                         sec=WALL_MEASURED_S.get(c["cid"], cells * SEC_PER_CELL),
                         meas=c["cid"] in WALL_MEASURED_S, note=c["note"]))
    return rows


def load_fp():
    p = os.path.join(HERE, "fp_result.csv")
    if not os.path.exists(p):
        sys.exit("fp_result.csv 없음 — stage1 실행 후 `python3 fixedpoint.py` 를 먼저.")
    with open(p, encoding="utf-8") as f:
        return {r["case"]: r for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="목록만 출력")
    ap.add_argument("--stage", type=int, default=1, choices=(1, 2),
                    help="1=시드 생성 / 2=자기일관 Su 로 fvOptions 갱신")
    ap.add_argument("--force", action="store_true", help="결과 있어도 재생성")
    a = ap.parse_args()

    rows = catalog()
    print("=" * 88)
    print(f" EX2 CFD · 실측 3수준   폭기축 {K.PLUME_AXIS} (실험 실측)   "
          f"격자 {rows[0]['grid']}")
    print("=" * 88)
    print(f"{'case':>6}{'z_start':>9}{'H_p':>8}{'플룸층':>8}{'셀수':>10}"
          f"{'벽시간[분]':>11}   대응 실측")
    tot = 0.0
    for r in rows:
        tot += r["sec"]
        mark = "" if r["meas"] else "~"
        print(f"{r['cid']:>6}{r['z']:>9.3f}{r['Hp']:>8.3f}{r['nlay']:>8.1f}"
              f"{r['cells']:>10,}{mark + format(r['sec']/60, '.0f'):>11}   {r['note']}")
    print(f"{'합계':>6}{'':>35}{'':>10}{tot/60:>10.0f} 분 "
          f"(= {tot/3600:.1f} h. 실측값 · ~ 는 추정. stage2 재실행분 별도)")

    if a.list:
        return

    if a.stage == 2:
        fp = load_fp()
        n = 0
        todo = []
        for c in K.CASES:
            cid = c["cid"]
            if cid not in fp:
                print(f"  [건너뜀] {cid}: fp_result.csv 에 없음")
                continue
            su_new = float(fp[cid]["Su_fp"])
            su_old = float(fp[cid]["Su_in"])
            drift = (su_new - su_old) / su_old            # 부호 보존 (구 버전 abs 버그)
            # 게이트는 **1스텝 잔차** — fixedpoint.py --verify 와 같은 지표여야 한다.
            res1 = float(fp[cid].get("res_1step_pct") or 100 * drift) / 100.0
            rerun = abs(res1) > K.TOL_FP
            # ★ 재실행할 케이스만 fvOptions 를 고친다.
            #   안 고치면 그 케이스의 fvOptions 는 **실제로 돌린 Su** 를 그대로 유지하고,
            #   --verify 가 (돌린 Su) vs (그 해의 W) 를 정직하게 대조하게 된다.
            #   구 버전은 전 케이스를 덮어써서, 안 돌린 케이스가 --verify 에서
            #   엉뚱한 짝(새 Su vs 옛 W)으로 비교돼 잔차가 작게 나왔다.
            if rerun:
                write(os.path.join(HERE, cid, "system", "fvOptions"),
                      make_fvoptions(su_new, f"stage2 자기일관 alpha_g="
                                             f"{float(fp[cid]['alpha_g_fp']):.4f}"))
                todo.append(cid)
            n += 1
            print(f"  {cid}: 1스텝 잔차 {100*res1:+.2f} %  |  "
                  f"Su {su_old:.4f} -> {su_new:.4f} ({100*drift:+.2f} %)  "
                  f"{'재실행 (fvOptions 갱신)' if rerun else '수렴 — fvOptions 유지'}")
        write(os.path.join(HERE, "stage2_todo.txt"), " ".join(todo) + "\n")
        print(f"\n  {n}개 fvOptions 갱신. 재실행 대상: "
              f"{' '.join(todo) if todo else '없음'}  -> stage2_todo.txt")
        return

    made = []
    for c in K.CASES:
        d = build(c["cid"], c["z_start"], K.SU_SEED,
                  f"stage1 시드 Su={K.SU_SEED} (medium z=0.02 고정점)", a.force)
        made.append((c["cid"], "생성" if d else "결과 있음 → 스킵"))
    print()
    for cid, s in made:
        print(f"  {cid}: {s}")
    print(f"\n  다음:  bash run.sh          (stage1 -> 고정점 -> stage2)")


if __name__ == "__main__":
    main()
