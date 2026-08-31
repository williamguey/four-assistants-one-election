# -*- coding: utf-8 -*-
"""Motor de coleta. Modos: dryrun (2 probes x 2 modelos), pilot (D1, 3 iter, 4 modelos),
full (onda completa; exige prereg_confirmed + --confirm-prereg).
Sanidade roda primeiro; baseline (sem plugin) calibra o limiar de busca_sem_citacao.
M2 em pares formais: mesmo wrapper nas duas chamadas, ordem LF/FL sorteada, execução
consecutiva na mesma thread. Idempotente por chave composta; raw append-only."""
import argparse
import csv
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import (BODY_M10, CONFIG, DIMS, LIKERT_OPTS, M6_DIMS, ROOT, SANIDADE,
                    CostTracker, append_jsonl, balanced_assign, body_m1, body_m2, body_m3,
                    body_m6, chat, draw, file_hash, now_utc, read_jsonl)

PLUGIN = CONFIG["search_plugin"]
P = CONFIG["params"]

_WRAPPERS = None


def wrappers():
    global _WRAPPERS
    if _WRAPPERS is None:
        pools = {}
        with open(ROOT / "data" / "wrappers" / "wrappers.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                pools.setdefault((row["method"], row["kind"]), []).append(row)
        for k in pools:
            pools[k].sort(key=lambda r: r["wrapper_id"])
            assert len(pools[k]) == 12, k
        _WRAPPERS = pools
    return _WRAPPERS


def pick_wrapper(method, kind, model, probe_id, it):
    pool = wrappers().get((method, kind))
    if not pool:
        return None
    return pool[draw(model, probe_id, it, kind, n=len(pool))]


def assemble(prefix_row, body, suffix_row, opt_order=None):
    parts = []
    if prefix_row:
        parts.append(prefix_row["texto"])
    parts.append(body)
    if suffix_row:
        s = suffix_row["texto"]
        if "{OPCOES}" in s:
            opts = LIKERT_OPTS if opt_order == "normal" else list(reversed(LIKERT_OPTS))
            s = s.replace("{OPCOES}", ", ".join(opts))
        parts.append(s)
    return "\n\n".join(parts)


def make_tasks(mode):
    """Lista de tasks. Cada task = 1 chamada, exceto m2 (par com 2 chamadas consecutivas)."""
    it = CONFIG["iterations"]
    if mode == "dryrun":
        model_keys = ["chatgpt", "claude"]
        plan = {"m1": 1, "m2": 1, "m3": 0, "m6": 0, "m10": 0, "sanidade": 1}
        dims = ["D1"]
    elif mode == "pilot":
        model_keys = list(CONFIG["models"])
        plan = {"m1": 3, "m2": 3, "m3": 3, "m6": 3, "m10": 0, "sanidade": it["sanidade"]}
        dims = ["D1"]
    else:  # full
        model_keys = list(CONFIG["models"])
        plan = {k: it[k] for k in ["m1", "m2", "m3", "m6", "m10", "sanidade"]}
        dims = [d[0] for d in DIMS]

    tasks = []
    for mk in model_keys:
        # sanidade (sem wrapper, com plugin) — roda primeiro
        for san_id, pergunta in SANIDADE:
            for i in range(plan["sanidade"]):
                tasks.append({"model": mk, "method": "sanidade", "dim": san_id, "frame": "-",
                              "order": "-", "iter": i, "prompt": pergunta, "wrappers": {},
                              "max_tokens": P["max_tokens_fechados"], "plugin": True,
                              "stage": 0})
        # baseline sem plugin (calibração do limiar de busca_sem_citacao)
        tasks.append({"model": mk, "method": "baseline", "dim": "S3", "frame": "-",
                      "order": "-", "iter": 0, "prompt": SANIDADE[2][1], "wrappers": {},
                      "max_tokens": P["max_tokens_fechados"], "plugin": False, "stage": 0})
        for dim in dims:
            pid1, pid2, pid3, pid6 = (f"m1_{dim}", f"m2_{dim}", f"m3_{dim}", f"m6_{dim}")
            frames = balanced_assign(["af", "rev"], plan["m1"], mk, "m1", dim, "frame")
            opt_orders = balanced_assign(["normal", "inv"], plan["m1"], mk, "m1", dim, "optorder")
            for i in range(plan["m1"]):
                pre = pick_wrapper("m1", "prefix", mk, pid1, i)
                suf = pick_wrapper("m1", "suffix", mk, pid1, i)
                tasks.append({"model": mk, "method": "m1", "dim": dim, "frame": frames[i],
                              "order": opt_orders[i], "iter": i,
                              "prompt": assemble(pre, body_m1(dim, frames[i]), suf, opt_orders[i]),
                              "wrappers": {"prefix": pre["wrapper_id"], "suffix": suf["wrapper_id"]},
                              "max_tokens": P["max_tokens_fechados"], "plugin": True, "stage": 1})
            pair_orders = balanced_assign(["LF", "FL"], plan["m2"], mk, "m2", dim, "order")
            for i in range(plan["m2"]):
                pre = pick_wrapper("m2", "prefix", mk, pid2, i)
                suf = pick_wrapper("m2", "suffix", mk, pid2, i)
                seq = ["L", "F"] if pair_orders[i] == "LF" else ["F", "L"]
                tasks.append({"model": mk, "method": "m2", "dim": dim, "frame": "-",
                              "order": pair_orders[i], "iter": i,
                              "pair_id": f"{mk}|m2|{dim}|i{i}",
                              "subcalls": [(c, assemble(pre, body_m2(dim, c), suf)) for c in seq],
                              "wrappers": {"prefix": pre["wrapper_id"], "suffix": suf["wrapper_id"]},
                              "max_tokens": P["max_tokens_fechados"], "plugin": True, "stage": 1})
            m3_orders = balanced_assign(["LF", "FL"], plan["m3"], mk, "m3", dim, "order")
            for i in range(plan["m3"]):
                pre = pick_wrapper("m3", "prefix", mk, pid3, i)
                suf = pick_wrapper("m3", "suffix", mk, pid3, i)
                tasks.append({"model": mk, "method": "m3", "dim": dim, "frame": "-",
                              "order": m3_orders[i], "iter": i,
                              "prompt": assemble(pre, body_m3(dim, m3_orders[i]), suf),
                              "wrappers": {"prefix": pre["wrapper_id"], "suffix": suf["wrapper_id"]},
                              "max_tokens": P["max_tokens_fechados"], "plugin": True, "stage": 1})
            if dim in M6_DIMS:
                for i in range(plan["m6"]):
                    pre = pick_wrapper("m6", "prefix", mk, pid6, i)
                    tasks.append({"model": mk, "method": "m6", "dim": dim, "frame": "-",
                                  "order": "-", "iter": i,
                                  "prompt": assemble(pre, body_m6(dim), None),
                                  "wrappers": {"prefix": pre["wrapper_id"]},
                                  "max_tokens": P["max_tokens_abertos"], "plugin": True,
                                  "stage": 1})
        for i in range(plan["m10"]):
            pre = pick_wrapper("m10", "prefix", mk, "m10", i)
            tasks.append({"model": mk, "method": "m10", "dim": "-", "frame": "-", "order": "-",
                          "iter": i, "prompt": assemble(pre, BODY_M10, None),
                          "wrappers": {"prefix": pre["wrapper_id"]},
                          "max_tokens": P["max_tokens_abertos"], "plugin": True, "stage": 1})
    return tasks


def task_keys(t):
    if t["method"] == "m2":
        return [f"{t['model']}|m2|{t['dim']}|{c}|{t['iter']}" for c, _ in t["subcalls"]]
    return [f"{t['model']}|{t['method']}|{t['dim']}|{t['frame']}|{t['iter']}"]


def run(mode, confirm_prereg=False):
    if mode == "full":
        if not CONFIG.get("prereg_confirmed"):
            sys.exit("ABORTADO: prereg_confirmed=false no config. Onda completa exige pré-registro.")
        if not confirm_prereg:
            sys.exit("ABORTADO: onda completa exige a flag --confirm-prereg.")
    wave = CONFIG["wave"] if mode == "full" else mode
    rdir = ROOT / "data" / "raw" / wave
    rdir.mkdir(parents=True, exist_ok=True)

    existing = set()
    for f in rdir.glob("*_*.jsonl"):
        if f.name != "citations.jsonl":
            existing.update(r["key"] for r in read_jsonl(f) if "key" in r)

    tasks = make_tasks(mode)
    todo = [t for t in tasks if any(k not in existing for k in task_keys(t))]
    n_skip = len(tasks) - len(todo)
    print(f"modo={mode} wave={wave} | tasks={len(tasks)} | já coletadas={n_skip} | a rodar={len(todo)}")

    tracker = CostTracker(CONFIG["max_cost_usd"])
    sems = {}
    for mk, mc in CONFIG["models"].items():
        prov = mc["provider_order"][0]
        sems.setdefault(prov, threading.BoundedSemaphore(CONFIG["concurrency_per_provider"]))
    stats = {"ok": 0, "fail": 0}
    truncated_keys = []
    obs = {mk: {"models": set(), "providers": set(), "sampling_rejected": 0}
           for mk in CONFIG["models"]}
    baseline_ptok = {}
    lock = threading.Lock()
    window_start = now_utc()

    def do_call(t, cand, prompt, key):
        mc = CONFIG["models"][t["model"]]
        res = chat(mc["id"], mc["provider_order"], prompt, t["max_tokens"],
                   temperature=P["temperature"],
                   plugin=PLUGIN if t["plugin"] else None)
        rec = {"key": key, "wave": wave, "model_key": t["model"],
               "model_string_devolvida": res["model_string_devolvida"],
               "provider_devolvido": res["provider_devolvido"],
               "method": t["method"], "dim_id": t["dim"], "frame": t["frame"],
               "order": t["order"], "iter": t["iter"], "pair_id": t.get("pair_id"),
               "candidate": cand, "wrapper_ids": t["wrappers"], "prompt": prompt,
               "ts_utc": now_utc(),
               "params": {"temperature": P["temperature"], "max_tokens": t["max_tokens"],
                          "plugin": PLUGIN if t["plugin"] else None},
               "raw_text": res["raw_text"], "finish_reason": res["finish_reason"],
               "truncated": res["finish_reason"] == "length",
               "usage": res["usage"], "reasoning_tokens": res["reasoning_tokens"],
               "n_annotations": len(res["annotations"]), "cost_usd": res["cost_usd"],
               "sampling_params_rejected": res["sampling_params_rejected"]}
        append_jsonl(rdir / f"{t['model']}_{t['method']}.jsonl", rec)
        for a in res["annotations"]:
            uc = a.get("url_citation") or a
            append_jsonl(rdir / "citations.jsonl",
                         {"wave": wave, "model_key": t["model"], "method": t["method"],
                          "dim_id": t["dim"], "iter": t["iter"], "key": key,
                          "url": uc.get("url"), "title": uc.get("title"),
                          "content": uc.get("content"),
                          "start_index": uc.get("start_index"),
                          "end_index": uc.get("end_index"), "ts_utc": now_utc()})
        with lock:
            obs[t["model"]]["models"].add(res["model_string_devolvida"])
            obs[t["model"]]["providers"].add(res["provider_devolvido"])
            if res["sampling_params_rejected"]:
                obs[t["model"]]["sampling_rejected"] += 1
            if t["method"] == "baseline":
                baseline_ptok[t["model"]] = res["prompt_tokens"]
            if rec["truncated"]:
                truncated_keys.append(key)
        tracker.add(res["cost_usd"])
        return rec

    def do_task(t):
        if tracker.exceeded():
            return "abort"
        prov = CONFIG["models"][t["model"]]["provider_order"][0]
        with sems[prov]:
            try:
                if t["method"] == "m2":
                    for (cand, prompt), key in zip(t["subcalls"], task_keys(t)):
                        if key in existing:
                            continue
                        do_call(t, cand, prompt, key)
                else:
                    do_call(t, None, t["prompt"], task_keys(t)[0])
                with lock:
                    stats["ok"] += 1
                return "ok"
            except Exception as e:
                with lock:
                    stats["fail"] += 1
                print(f"  FALHA {task_keys(t)[0]}: {str(e)[:180]}")
                return "fail"

    with ThreadPoolExecutor(max_workers=16) as ex:
        for stage in (0, 1):  # sanidade+baseline primeiro, barreira, depois o resto
            batch = [t for t in todo if t["stage"] == stage]
            futs = [ex.submit(do_task, t) for t in batch]
            done = 0
            for f in as_completed(futs):
                f.result()
                done += 1
                if done % 20 == 0:
                    print(f"  etapa {stage}: {done}/{len(batch)} | custo=${tracker.total:.2f}")

    window_end = now_utc()
    # guarda de truncamento: truncada = IF provisório no juiz; >1% da onda exige alerta
    n_exec = max(1, stats["ok"] + stats["fail"])
    trunc_rate = len(truncated_keys) / n_exec
    if trunc_rate > 0.01:
        print(f"\nALERTA: taxa de truncamento {100 * trunc_rate:.1f}% (> 1%). "
              f"Re-executar com limite maior as chamadas:")
        for k in truncated_keys:
            print(f"  {k}")

    import json
    est_path = ROOT / "outputs" / f"estimate_{mode}.json"
    estimate_snapshot = (json.loads(est_path.read_text(encoding="utf-8"))
                         if est_path.exists() else None)
    src_files = sorted((ROOT / "src").glob("*.py"))
    manifest = {"mode": mode, "wave": wave, "window_start_utc": window_start,
                "window_end_utc": window_end,
                "window_event_note": CONFIG.get("window_event_note", ""),
                "registration": CONFIG.get("registration"),
                "estimate": estimate_snapshot,
                "n_truncated": len(truncated_keys), "truncated_keys": truncated_keys,
                "search_plugin": PLUGIN,
                "models": {mk: {"requested": CONFIG["models"][mk]["id"],
                                "provider_order": CONFIG["models"][mk]["provider_order"],
                                "devolvidos": sorted(x for x in obs[mk]["models"] if x),
                                "providers": sorted(x for x in obs[mk]["providers"] if x),
                                "sampling_rejected_count": obs[mk]["sampling_rejected"]}
                           for mk in CONFIG["models"]},
                "deepseek_nota": "first-party 404 na conta; rota Fireworks é decisão final (limitações)",
                "code_hash": file_hash(src_files),
                "probes_hash": file_hash((ROOT / "data" / "probes").glob("*.csv")),
                "wrappers_hash": file_hash([ROOT / "data" / "wrappers" / "wrappers.csv"]),
                "seed": CONFIG["seed"],
                "n_tasks": len(tasks), "n_skipped_existing": n_skip,
                "n_ok": stats["ok"], "n_fail": stats["fail"],
                "cost_run_usd": round(tracker.total, 4),
                "baseline_prompt_tokens": baseline_ptok,
                "manual": {"screenshots_produto": "PENDENTE (HUMAN_TODO)",
                           "tier_produto": "PENDENTE", "window_event_note": ""}}
    (rdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print(f"ok={stats['ok']} falhas={stats['fail']} custo=${tracker.total:.4f} "
          f"janela={window_start}..{window_end}")
    print(f"manifest -> {rdir / 'manifest.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dryrun", "pilot", "full"], required=True)
    ap.add_argument("--confirm-prereg", action="store_true")
    a = ap.parse_args()
    run(a.mode, a.confirm_prereg)
