# -*- coding: utf-8 -*-
"""case0086 을 off/night/day 3모드로 풀어 /tmp/fig15_cache 에 저장.
행렬 A 는 3모드 공통이고 우변 b 만 바뀌므로 ILU 는 한 번만 만든다.
실행: PYTHONPATH=/tmp/pylibs python3 solve3.py
"""
import os, sys, time, json, importlib.util
import numpy as np
import scipy.sparse.linalg as spla

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SB   = os.path.join(ROOT, "Experiment", "EX3", "dataset", "stageB_DO")
CASE = os.path.join(ROOT, "Experiment", "EX3", "dataset", "result", "case0086")
CACHE = "/tmp/fig15_cache"; os.makedirs(CACHE, exist_ok=True)

spec = importlib.util.spec_from_file_location("sd", os.path.join(SB, "solve_do.py"))
sd = importlib.util.module_from_spec(spec); spec.loader.exec_module(sd)

T0 = time.time()
def log(*a):
    print(f"[{time.time()-T0:7.1f}s]", *a, flush=True)

# spilu 결과를 재사용하도록 가로챈다 (A 는 3모드 공통)
#   drop_tol=1e-4/ff=10 은 23 s 걸린다. 1e-3/ff=3 으로 낮춰도 bicgstab info=0 수렴하고
#   off 모드 결과가 compare_photo.json 과 소수 셋째자리까지 일치한다 → 채택.
_spilu = spla.spilu
_cache = {}
def spilu_once(A, **kw):
    if "M" not in _cache:
        log("spilu 시작")
        _cache["M"] = _spilu(A, drop_tol=1e-3, fill_factor=3)
        log("spilu 완료")
    return _cache["M"]
spla.spilu = spilu_once

_bicg = spla.bicgstab
def bicg_log(*a, **k):
    log("bicgstab 시작")
    r = _bicg(*a, **k)
    log(f"bicgstab 완료 info={r[1]}")
    return r
spla.bicgstab = bicg_log

MODE_LIST = sys.argv[1:] or ["off", "night", "day"]
for m in MODE_LIST:
    p = os.path.join(CACHE, f"{m}.npz")
    if os.path.exists(p):
        log(f"{m}: 캐시 있음, 건너뜀"); continue
    log(f"=== {m} ===")
    cfg = dict(sd.CONFIG); cfg["plant_mode"] = m
    C, d = sd.solve_case(CASE, cfg)
    np.savez_compressed(p, C=C.reshape(sd.NZ, sd.NY, sd.NX), diag=json.dumps(d))
    log(f"{m}: Cmin={d['C_min']:.3f} Cmax={d['C_max']:.3f} "
        f"spread={d['C_max']-d['C_min']:.3f} corr={d['corr_velDO']:+.3f}  -> 저장")
log("ALL DONE")
