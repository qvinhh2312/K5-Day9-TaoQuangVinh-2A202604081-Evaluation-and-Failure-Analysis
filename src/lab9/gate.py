"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    rows = pr.get("rows") or []
    man, bman = pr.get("manifest") or {}, base.get("manifest") or {}

    # 1. non-finite metric values (nan < min is False, so a naive gate passes them)
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v}")
    for r in rows:
        if isinstance(r.get("cost"), float) and not math.isfinite(r["cost"]):
            problems.append(f"{r.get('item_id')}@{r.get('seed')}: cost is not finite")
            break

    # 2. row count, duplicates, and the (item, seed) grid versus the manifest and the baseline
    want = int(man.get("items", 0)) * len(man.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {man.get('items')} items x {len(man.get('seeds') or [])} seeds = {want}")
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        problems.append(f"duplicate (item, seed) rows: {dup[:3]}")
    if man.get("seeds") != bman.get("seeds"):
        problems.append(f"manifest seeds {man.get('seeds')} differ from baseline {bman.get('seeds')}")
    if man.get("items") != bman.get("items"):
        problems.append(f"manifest items {man.get('items')} differ from baseline {bman.get('items')}")
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if set(keys) != base_keys:
        problems.append(f"(item, seed) set differs from the baseline: {len(set(keys) ^ base_keys)} cell(s) differ")

    # 3. crashed graders
    structural = bool(problems)
    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures: {len(pr['evaluator_failures'])} (e.g. {pr['evaluator_failures'][0]})")
    spec_ids = {m["id"] for m in spec.get("metrics", [])}
    graded = spec_ids & {k for r in base.get("rows") or [] for k in r}
    for m in sorted(graded):
        miss = [r.get("item_id") for r in rows if r.get(m) is None]
        if miss:
            problems.append(f"metric {m} is None on {len(miss)} row(s), e.g. {miss[0]}")
            structural = True

    # 4. slice tags must be the baseline's
    def tags(report):
        return {r.get("item_id"): sorted(r.get("slices") or []) for r in report.get("rows") or []}
    bt, pt = tags(base), tags(pr)
    moved = sorted(i for i in bt.keys() & pt.keys() if bt[i] != pt[i])
    if moved:
        problems.append(f"slice tags differ from the baseline on {moved[:3]}")

    # 5. the reported metrics must be what the rows say (catches a hand-edited report)
    if graded and rows and not structural:
        try:
            again = aggregate([{"cost": 0.0, **r} for r in rows], sorted(graded), k_values=spec.get("pass_k", []))
            for k, v in again.items():
                got = (pr.get("metrics") or {}).get(k)
                if k != "cost_per_success" and isinstance(v, (int, float)) and isinstance(got, (int, float)) \
                        and math.isfinite(got) and abs(v - got) > 1e-6:
                    problems.append(f"metric {k} is {got} in the report but its rows give {v}")
        except (KeyError, TypeError):
            problems.append("metrics cannot be recomputed from rows")

    # 6. ratchet: same eval-set version => no looser threshold, no dropped metric or slice
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems += _ratchet(spec.get("metrics") or [], base_spec.get("metrics") or [], "id", "metric")
        problems += _ratchet(spec.get("slices") or [], base_spec.get("slices") or [], "name", "slice")
    return problems


def _ratchet(new: list[dict], old: list[dict], key: str, what: str) -> list[str]:
    """Thresholds may only get stricter. `new` / `old` are lists of metric or slice entries."""
    out = []
    by_new = {m[key]: m for m in new}
    for o in old:
        n = by_new.get(o[key])
        if n is None:
            out.append(f"{what} {o[key]} was removed")
            continue
        oth = o.get("threshold") or {} if what == "metric" else o
        nth = n.get("threshold") or {} if what == "metric" else n
        if "max" in oth and ("max" not in nth or nth["max"] > oth["max"]):
            out.append(f"{what} {o[key]}: max {oth['max']} -> {nth.get('max')}")
        if "max_increase" in oth and ("max_increase" not in nth or nth["max_increase"] > oth["max_increase"]):
            out.append(f"{what} {o[key]}: max_increase {oth['max_increase']} -> {nth.get('max_increase')}")
        if "min" in oth and ("min" not in nth or nth["min"] < oth["min"]):
            out.append(f"{what} {o[key]}: min {oth['min']} -> {nth.get('min')}")
        if oth.get("no_significant_drop") and not nth.get("no_significant_drop"):
            out.append(f"{what} {o[key]}: no_significant_drop was dropped")
        if o.get("blocking") and not n.get("blocking"):
            out.append(f"{what} {o[key]}: blocking -> non-blocking")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s["metric"]
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        bad, note = not a, ""                        # an empty slice means items were relabelled away: suspicious
        val = round(sum(a.values()) / len(a), 4) if a else None
        if a and "min" in s and val < s["min"]:
            bad = True
        keys = sorted(set(a) & set(b))
        if a and s.get("no_significant_drop") and keys:
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            bad = bad or hi < 0
        sid = f"slice:{name}/{metric}"
        if bad and s.get("blocking"):
            blocked.append(sid)
        lines.append(f"  {sid:<34} {val!s:<8} {note:<28} {'BLOCK' if bad and s.get('blocking') else 'warn' if bad else 'ok'}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
