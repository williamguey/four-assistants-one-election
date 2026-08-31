# -*- coding: utf-8 -*-
"""Pacotes de curadoria humana: discordâncias entre juízes, amostra de trechos, amostra M6.
Saída em human/{wave}/."""
import argparse
import csv
import random

from common import CONFIG, ROOT, read_jsonl


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  {path.name}: {len(rows)} linhas")


def main(wave):
    jdir = ROOT / "data" / "judged" / wave
    rdir = ROOT / "data" / "raw" / wave
    hdir = ROOT / "human" / wave
    rng = random.Random(CONFIG["seed"])
    raw_by_key = {}
    for f in sorted(rdir.glob("*_*.jsonl")):
        if f.name != "citations.jsonl":
            for r in read_jsonl(f):
                raw_by_key[r["key"]] = r

    second = read_jsonl(jdir / "second_judge.jsonl")
    rows = [{**r, "raw_text": (raw_by_key.get(r["key"], {}).get("raw_text") or "")[:1500],
             "veredito_humano": ""}
            for r in second if r["judge1"] != r["judge2"]]
    write_csv(hdir / "juiz_discordancias.csv", rows,
              ["key", "model_key", "method", "judge1", "judge2", "raw_text", "veredito_humano"])

    snips = read_jsonl(jdir / "citations_judged.jsonl")
    rng.shuffle(snips)
    rows = [{**{k: s.get(k) for k in ("snippet_hash", "domain", "proveniencia", "funcao",
                                      "valencia", "url", "title")},
             "funcao_humano": "", "valencia_humano": ""} for s in snips[:100]]
    write_csv(hdir / "trechos_amostra.csv", rows,
              ["snippet_hash", "domain", "proveniencia", "funcao", "valencia", "url", "title",
               "funcao_humano", "valencia_humano"])

    judged = read_jsonl(jdir / "responses.jsonl")
    m6 = [r for r in judged if r["method"] == "m6"]
    rng.shuffle(m6)
    rows = [{**{k: r.get(k) for k in ("key", "model_key", "dim_id", "judge_code")},
             "raw_text": (raw_by_key.get(r["key"], {}).get("raw_text") or "")[:2000],
             "codigo_humano": ""} for r in m6[:100]]
    write_csv(hdir / "m6_amostra.csv", rows,
              ["key", "model_key", "dim_id", "judge_code", "raw_text", "codigo_humano"])
    print(f"pacotes humanos -> {hdir}  (+ data/outlet_registry.csv para curadoria)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    main(**vars(ap.parse_args()))
