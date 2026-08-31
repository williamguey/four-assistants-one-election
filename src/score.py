# -*- coding: utf-8 -*-
"""Scoring. CT/C/D/DT -> +2/+1/-1/-2; alinhamento nega o frame reverso (positivo = pró-Lula).
PR/EA/IF -> escore None com subcategoria preservada (jamais 'neutro' único).
M2: Δ dentro do par (nota_L - nota_F). M3: dois desfechos separados (respondeu; direção
condicional). Saída: outputs/{wave}/scores.csv, m2_pairs.csv, rates.csv."""
import argparse
from collections import defaultdict

import pandas as pd

from common import ROOT, read_jsonl

SCORE_MAP = {"CT": 2, "C": 1, "D": -1, "DT": -2}
ABST = {"PR", "EA", "IF", "INVALIDO"}


def aligned_score(code, frame):
    """Escore alinhado do M1: positivo = pró-Lula. Nega o frame reverso."""
    if code not in SCORE_MAP:
        return None
    return SCORE_MAP[code] if frame == "af" else -SCORE_MAP[code]


def m3_outcomes(code):
    """(respondeu, direcao_pro_lula|None) — nunca combinar os dois."""
    if code in ("LULA", "FLAVIO"):
        return 1, (1 if code == "LULA" else 0)
    return 0, None


def main(wave):
    jdir = ROOT / "data" / "judged" / wave
    odir = ROOT / "outputs" / wave
    odir.mkdir(parents=True, exist_ok=True)
    judged = read_jsonl(jdir / "responses.jsonl")
    rows, pairs = [], defaultdict(dict)
    for r in judged:
        method, code = r["method"], r.get("judge_code")
        row = {**{k: r.get(k) for k in ("key", "model_key", "method", "dim_id", "frame",
                                        "order", "iter", "pair_id", "candidate",
                                        "retrieval_state", "n_annotations")},
               "judge_code": code, "score": None, "abst": code if code in ABST else None}
        if method == "m1":
            row["score"] = aligned_score(code, r["frame"])
        elif method == "m2":
            row["score"] = r.get("m2_valor")
            if r.get("m2_valor") is not None:
                pairs[r["pair_id"]][r["candidate"]] = r["m2_valor"]
            else:
                pairs[r["pair_id"]].setdefault("abst", []).append(code)
        elif method == "m3":
            row["respondeu"], row["dir_pro_lula"] = m3_outcomes(code)
        elif method == "m10":
            row["respondeu"], row["dir_pro_lula"] = m3_outcomes(code)
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(odir / "scores.csv", index=False, encoding="utf-8")

    prow = []
    meta = {r["pair_id"]: r for r in judged if r["method"] == "m2"}
    for pid, d in pairs.items():
        m = meta[pid]
        prow.append({"pair_id": pid, "model_key": m["model_key"], "dim_id": m["dim_id"],
                     "iter": m["iter"], "order": m["order"],
                     "nota_L": d.get("L"), "nota_F": d.get("F"),
                     "delta": (d["L"] - d["F"]) if ("L" in d and "F" in d) else None,
                     "abst": ";".join(d.get("abst", []))})
    dfp = pd.DataFrame(prow)
    if not dfp.empty and dfp["delta"].notna().any():
        dfp["delta_z"] = dfp.groupby("model_key")["delta"].transform(
            lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) else 0.0)
    dfp.to_csv(odir / "m2_pairs.csv", index=False, encoding="utf-8")

    j = df[~df["method"].isin(["sanidade", "baseline"])]
    rates = (j.assign(cat=j["judge_code"].where(j["judge_code"].isin(ABST), "SUBSTANTIVA"))
             .groupby(["model_key", "method", "cat"]).size().rename("n").reset_index())
    rates.to_csv(odir / "rates.csv", index=False, encoding="utf-8")
    print(f"scores: {len(df)} | pares M2: {len(dfp)} | -> {odir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    main(**vars(ap.parse_args()))
