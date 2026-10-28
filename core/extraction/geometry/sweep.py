"""Parameter sweep (PRD/04 §3.6): K candidate parameter sets run in parallel, results in index order."""

import itertools
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

STRATEGIES = ("S2", "S1")  # S2 first: double-line plans (Gatsu); S1 covers poche plans
SAUVOLA_K = (0.2, 0.34)
T_MIN = (80, 150)
T_MAX = (450,)
L_FIX = (0, 5)


def sweep_params(max_candidates: int, profile: dict | None = None) -> list[dict]:
    combos = [{"strategy": st, "sauvola_k": k, "t_min": tn, "t_max": tx, "l_fix": lf}
              for st, k, tn, tx, lf in itertools.product(STRATEGIES, SAUVOLA_K, T_MIN, T_MAX, L_FIX)]
    if profile:  # a style profile and its neighbours first (stable: ties keep the default order)
        combos.sort(key=lambda c: sum(c[k] != profile.get(k, c[k]) for k in c))
    return combos[:max(1, max_candidates)]


def _call(job: tuple[Callable, int, dict]) -> dict:
    fn, index, params = job
    try:
        return fn(index, params)
    except Exception as e:  # noqa: BLE001 - one bad candidate must not sink the sweep
        return {"error": f"{type(e).__name__}: {e}", "params": params}


def run_sweep(fn: Callable[[int, dict], dict], params_list: list[dict], workers: int | None = None) -> list[dict]:
    # SWEEP_WORKERS: a caller that already runs drawings in parallel (benchmarks) keeps each sweep in-process
    workers = workers or int(os.environ.get("SWEEP_WORKERS") or 0) or max(1, (os.cpu_count() or 2) - 1)
    jobs = [(fn, i, p) for i, p in enumerate(params_list)]
    if workers == 1 or len(jobs) == 1:
        return [_call(j) for j in jobs]
    try:
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
            return list(pool.map(_call, jobs))  # map keeps the input order
    except BrokenProcessPool:  # e.g. a host whose __main__ cannot be re-imported by spawn: run in-process
        return [_call(j) for j in jobs]
