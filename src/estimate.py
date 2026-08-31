# -*- coding: utf-8 -*-
"""Estimativa de custo ANTES de qualquer coleta (regra do protocolo). Usa custos unitários
medidos no smoke de 28/08 e compara com o teto (max_cost_usd) e com o saldo real (/credits).
Aborta (exit 1) se a projeção estourar qualquer um dos dois."""
import argparse
import json
import sys

from collect import make_tasks
from common import CONFIG, ROOT, credits_balance

# medidos no smoke 28/08 (USD/chamada, com plugin Exa max_results=5)
UNIT = {"closed": 0.013, "open": 0.035, "judge_resp": 0.0025, "judge_snip": 0.002}
UNIQUE_SNIPPET_RATE = 0.95  # medido no dry-run 28/08: 67/70 únicos (content varia por chamada)


def estimate(mode):
    tasks = make_tasks(mode)
    calls = sum(2 if t["method"] == "m2" else 1 for t in tasks)
    open_calls = sum(1 for t in tasks if t["method"] in ("m6", "m10"))
    closed_calls = calls - open_calls
    plugin_calls = sum((2 if t["method"] == "m2" else 1) for t in tasks if t["plugin"])
    judged = sum(2 if t["method"] == "m2" else 1 for t in tasks
                 if t["method"] not in ("sanidade", "baseline"))
    snippets = plugin_calls * CONFIG["search_plugin"]["max_results"] * UNIQUE_SNIPPET_RATE
    cost = (closed_calls * UNIT["closed"] + open_calls * UNIT["open"]
            + judged * UNIT["judge_resp"] + snippets * UNIT["judge_snip"])
    return {"mode": mode, "n_tasks": len(tasks), "n_calls": calls,
            "n_calls_abertas": open_calls, "n_julgamentos_resposta": judged,
            "n_trechos_estimados": int(snippets), "cost_projected_usd": round(cost, 2)}


def main(mode):
    est = estimate(mode)
    bal = credits_balance()
    ceiling = CONFIG["max_cost_usd"]
    est["saldo_openrouter_usd"] = round(bal, 2)
    est["max_cost_usd"] = ceiling
    out = ROOT / "outputs" / f"estimate_{mode}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(est, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(est, ensure_ascii=False, indent=2))
    if est["cost_projected_usd"] > ceiling:
        sys.exit(f"ABORTAR: projeção ${est['cost_projected_usd']} > teto ${ceiling}")
    if est["cost_projected_usd"] > bal:
        sys.exit(f"ABORTAR: projeção ${est['cost_projected_usd']} > saldo ${bal:.2f} "
                 f"(recarga necessária — HUMAN_TODO)")
    print("estimativa dentro do teto e do saldo — liberado")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dryrun", "pilot", "full"], required=True)
    main(**vars(ap.parse_args()))
