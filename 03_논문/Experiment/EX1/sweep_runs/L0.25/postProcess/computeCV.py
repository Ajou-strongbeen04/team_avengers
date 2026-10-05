#!/usr/bin/env python3
# EX1 : DO 공간 변동계수(CV)와 저산소 체적분율
# usage: python computeCV.py <time>        (예: python computeCV.py 5)
# 균일격자(simpleGrading 1 1 1) 전제 -> 비가중 통계 = 부피가중 통계.
# C 또는 C.gz, CMean 또는 CMean.gz 자동 처리.
import sys, os, re, gzip, statistics

HYPOXIA = 2.0   # mg/L 미만 = 저산소(임계값)

def read_text(base):
    if os.path.exists(base):
        return open(base, "r", errors="ignore").read()
    if os.path.exists(base + ".gz"):
        return gzip.open(base + ".gz", "rt", errors="ignore").read()
    raise FileNotFoundError(base + " (nor .gz)")

def parse_internal(txt):
    m = re.search(r"internalField\s+uniform\s+([-\d.eE+]+)\s*;", txt)
    if m:
        return [float(m.group(1))]
    m = re.search(r"internalField\s+nonuniform\s+List<scalar>\s*\n?\s*(\d+)\s*\(", txt)
    if not m:
        raise RuntimeError("internalField parse failed")
    n = int(m.group(1))
    vals = []
    for tok in re.findall(r"[-\d.eE+]+", txt[m.end():]):
        vals.append(float(tok))
        if len(vals) >= n:
            break
    return vals

def main():
    t = sys.argv[1] if len(sys.argv) > 1 else "."
    exists_any = lambda b: os.path.exists(b) or os.path.exists(b + ".gz")
    cmean = os.path.join(t, "CMean")
    base = cmean if exists_any(cmean) else os.path.join(t, "C")
    vals = parse_internal(read_text(base))
    n = len(vals)
    mean = sum(vals) / n
    std = statistics.pstdev(vals) if n > 1 else 0.0
    cv = std / mean if mean else float("nan")
    hyp = sum(1 for v in vals if v < HYPOXIA) / n
    print("file       : " + base)
    print("cells      : {0}".format(n))
    print("DO mean    : {0:.4f} mg/L".format(mean))
    print("DO std     : {0:.4f} mg/L".format(std))
    print("DO CV      : {0:.4f}   (dead-spot severity)".format(cv))
    print("DO min/max : {0:.4f} / {1:.4f} mg/L".format(min(vals), max(vals)))
    print("hypoxic(<{0}) volfrac : {1:.4f}".format(HYPOXIA, hyp))

if __name__ == "__main__":
    main()
