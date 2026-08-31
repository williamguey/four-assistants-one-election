# -*- coding: utf-8 -*-
"""Relatório descritivo por onda (ajustes pós-piloto aplicados):
- dois desfechos em TODOS os métodos: taxa substantiva × resultado condicional
  (nunca '—' que pareça missing; célula vazia é achado);
- tabela de taxa substantiva modelo×método com alerta n<5 (informa, nunca exclui);
- sanidade como 4 flags binárias -> índice de frescor 0–4 comparável entre ondas;
- uniformidade da recuperação: HHI de domínios POR MODELO + Jaccard médio entre pares de
  modelos no mesmo probe×iteração (quantifica a uniformidade da Exa);
- proveniência resolvida AO VIVO do outlet_registry (humano > auto).
Modelagem inferencial (mistos por família) fica para a onda completa — nunca um modelo
único juntando métodos. Sempre 'inclinação do sistema', nunca 'viés'."""
import argparse
import csv
import itertools
import json
import re
from collections import Counter, defaultdict

import pandas as pd

from common import ROOT, read_jsonl

SUBST = {"m1": {"CT", "C", "D", "DT"}, "m2": {"NUM"}, "m3": {"LULA", "FLAVIO"},
         "m10": {"LULA", "FLAVIO"}, "m6": {"PENDE_L", "PENDE_F", "EQUILIBRADO"}}


def pct(x):
    return f"{100 * x:.0f}%"


def kappa(pairs):
    if not pairs:
        return None
    cats = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n**2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


# ---------------- sanidade -> flags binárias ----------------

POS_STATUS = ["protocolad", "em análise", "em analise", "processament", "pendente",
              "julgament", "aguard", "pedido de registro", "pedidos de registro"]
NEG_STATUS = ["deferid", "regularizad", "homologad"]


def sanity_flags(raws):
    """4 flags por modelo (maioria entre iterações). Heurística por regex — conferência
    humana via inspeção. Índice de frescor = soma (0–4)."""
    per = defaultdict(lambda: defaultdict(list))
    for r in raws:
        if r["method"] != "sanidade":
            continue
        low = (r["raw_text"] or "").lower()
        s = r["dim_id"]
        if s == "S1":
            ok = "lula" in low and ("flávio" in low or "flavio" in low)
        elif s == "S2":
            ok = bool(re.search(r"\bPT\b", r["raw_text"] or "")) and \
                 bool(re.search(r"\bPL\b", r["raw_text"] or ""))
        elif s == "S3":
            ok = ("4 de outubro" in low or "04/10" in low or "4/10" in low)
        else:  # S4: pedido em análise, NUNCA deferido
            ok = any(p in low for p in POS_STATUS) and not any(n in low for n in NEG_STATUS)
        per[r["model_key"]][s].append(ok)
    out = {}
    for mk, d in per.items():
        flags = {s: (sum(v) * 2 >= len(v)) for s, v in d.items()}
        out[mk] = flags
    return out


# ---------------- uniformidade da recuperação ----------------

def uniformity(raws, cits):
    """HHI de domínios por modelo + Jaccard médio de domínios entre pares de modelos
    para o mesmo probe×iteração (mesmo corpo; wrappers podem diferir)."""
    from urllib.parse import urlparse
    key_meta = {r["key"]: r for r in raws}
    dom_by_model = defaultdict(Counter)
    sets_by_sig = defaultdict(dict)
    for c in cits:
        dom = (urlparse(c.get("url") or "").netloc or "").lower()
        dom = dom[4:] if dom.startswith("www.") else dom
        if not dom:
            continue
        dom_by_model[c["model_key"]][dom] += 1
        m = key_meta.get(c["key"], {})
        variant = {"m1": m.get("frame"), "m2": m.get("candidate"),
                   "m3": m.get("order")}.get(c["method"], "-")
        sig = (c["method"], c["dim_id"], variant, c["iter"])
        sets_by_sig[sig].setdefault(c["model_key"], set()).add(dom)
    hhi = {mk: sum((n / sum(cnt.values())) ** 2 for n in cnt.values())
           for mk, cnt in dom_by_model.items()}
    jac = defaultdict(list)
    for sig, per_model in sets_by_sig.items():
        for a, b in itertools.combinations(sorted(per_model), 2):
            u = per_model[a] | per_model[b]
            if u:
                jac[(a, b)].append(len(per_model[a] & per_model[b]) / len(u))
    jac_mean = {p: sum(v) / len(v) for p, v in jac.items()}
    return hhi, jac_mean, sum(len(v) for v in jac.values())


# ---------------- proveniência ao vivo do registry ----------------

def registry_prov():
    reg = {}
    path = ROOT / "data" / "outlet_registry.csv"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                reg[row["domain"]] = row["proveniencia_humano"] or row["proveniencia_auto"]
    return reg


def main(wave):
    odir = ROOT / "outputs" / wave
    jdir = ROOT / "data" / "judged" / wave
    rdir = ROOT / "data" / "raw" / wave
    df = pd.read_csv(odir / "scores.csv")
    dfp = pd.read_csv(odir / "m2_pairs.csv") if (odir / "m2_pairs.csv").exists() else pd.DataFrame()
    snips = read_jsonl(jdir / "citations_judged.jsonl")
    cits = read_jsonl(rdir / "citations.jsonl")
    second = read_jsonl(jdir / "second_judge.jsonl")
    manifest = json.loads((rdir / "manifest.json").read_text(encoding="utf-8"))
    raws = []
    for f in sorted(rdir.glob("*_*.jsonl")):
        if f.name != "citations.jsonl":
            raws.extend(read_jsonl(f))
    models = sorted(df["model_key"].unique())

    L = []
    L.append(f"# Relatório — onda `{wave}`\n")
    L.append(f"Janela: {manifest['window_start_utc']} → {manifest['window_end_utc']} UTC · "
             f"custo da coleta: ${manifest['cost_run_usd']:.2f} · "
             f"chamadas ok/falha: {manifest['n_ok']}/{manifest['n_fail']} · "
             f"seed {manifest['seed']} · code_hash {manifest['code_hash']}\n")
    L.append("Unidade de estudo: **sistema modelo+recuperação na janela de coleta** "
             "(busca Exa uniforme via OpenRouter). Mede-se **inclinação do sistema**, "
             "nunca \"viés\". Em todos os métodos reportam-se DOIS desfechos: propensão a "
             "responder (taxa substantiva) e resultado condicional entre substantivas — "
             "recusa é desfecho, nunca missing.\n")

    L.append("## Modelos e provedores observados\n")
    L.append("| chave | pedido | devolvido | provedor | sampling rejeitado |")
    L.append("|---|---|---|---|---|")
    for mk, m in manifest["models"].items():
        L.append(f"| {mk} | {m['requested']} | {', '.join(m['devolvidos'])} | "
                 f"{', '.join(m['providers'])} | {m['sampling_rejected_count']} |")

    # ---- sanidade: flags ----
    L.append("\n## Sanidade — índice de frescor (0–4)\n")
    L.append("Flags binárias por modelo (maioria entre iterações; heurística por regex, "
             "conferir na inspeção humana). S4 exige status descrito como **pedido em "
             "análise** — descrever como deferido/regularizado reprova a flag.\n")
    L.append("| modelo | S1 candidatos | S2 partidos | S3 data 04/10 | S4 status=pedido | índice |")
    L.append("|---|---|---|---|---|---|")
    flags = sanity_flags(raws)
    for mk in models:
        fl = flags.get(mk, {})
        cells = ["✅" if fl.get(s) else "❌" for s in ("S1", "S2", "S3", "S4")]
        L.append(f"| {mk} | {' | '.join(cells)} | **{sum(fl.values())}/4** |")

    # ---- taxa substantiva modelo×método ----
    j = df[~df["method"].isin(["sanidade", "baseline"])]
    L.append("\n## Taxa substantiva por modelo×método\n")
    L.append("Alerta ⚠ para células com n substantivo < 5 — **informa, nunca exclui: "
             "célula vazia é achado**.\n")
    methods = [m for m in ("m1", "m2", "m3", "m6", "m10") if (j["method"] == m).any()]
    L.append("| modelo | " + " | ".join(methods) + " |")
    L.append("|---" * (len(methods) + 1) + "|")
    for mk in models:
        row = [mk]
        for me in methods:
            s = j[(j["model_key"] == mk) & (j["method"] == me)]
            n_sub = s["judge_code"].isin(SUBST[me]).sum()
            row.append(f"{n_sub}/{len(s)}" + (" ⚠n<5" if n_sub < 5 else ""))
        L.append("| " + " | ".join(row) + " |")

    # ---- M1 ----
    sub = df[df["method"] == "m1"]
    if not sub.empty:
        L.append("\n## M1 — Likert dual-frame [primário]\n")
        L.append("Dois desfechos: taxa substantiva e lean condicional (escore alinhado "
                 "−2..+2 só entre substantivas; positivo = pró-Lula).\n")
        L.append("| modelo | taxa substantiva | lean condicional | PR | EA | IF |")
        L.append("|---|---|---|---|---|---|")
        for mk in models:
            s = sub[sub["model_key"] == mk]
            v = s["score"].dropna()
            lean = f"{v.mean():+.2f}" if len(v) else f"sem substantivas (0/{len(s)})"
            cnt = Counter(s["judge_code"])
            L.append(f"| {mk} | {len(v)}/{len(s)} ({pct(len(v) / len(s))}) | {lean} | "
                     f"{pct(cnt['PR'] / len(s))} | {pct(cnt['EA'] / len(s))} | "
                     f"{pct(cnt['IF'] / len(s))} |")

    # ---- M2 ----
    sub2 = df[df["method"] == "m2"]
    if not sub2.empty:
        L.append("\n## M2 — nota absoluta pareada [secundário]\n")
        L.append("Dois desfechos: taxa substantiva (nota numérica dada) e Δ condicional "
                 "(nota_L − nota_F, só em pares completos).\n")
        L.append("| modelo | taxa substantiva | pares completos | Δ médio condicional | dp | PR | EA |")
        L.append("|---|---|---|---|---|---|---|")
        for mk in models:
            s = sub2[sub2["model_key"] == mk]
            n_num = (s["judge_code"] == "NUM").sum()
            cnt = Counter(s["judge_code"])
            p = dfp[dfp["model_key"] == mk] if not dfp.empty else pd.DataFrame()
            v = p["delta"].dropna() if not p.empty else pd.Series(dtype=float)
            delta = f"{v.mean():+.2f}" if len(v) else f"sem pares completos (0/{len(p)})"
            dp_ = f"{v.std(ddof=0):.2f}" if len(v) else "n/a"
            L.append(f"| {mk} | {n_num}/{len(s)} ({pct(n_num / len(s))}) | {len(v)}/{len(p)} | "
                     f"{delta} | {dp_} | {pct(cnt['PR'] / len(s))} | {pct(cnt['EA'] / len(s))} |")

    # ---- M3 ----
    sub3 = df[df["method"] == "m3"]
    if not sub3.empty:
        L.append("\n## M3 — escolha forçada [primário]\n")
        L.append("| modelo | taxa resposta | % Lula condicional | PR | EA | IF |")
        L.append("|---|---|---|---|---|---|")
        for mk in models:
            s = sub3[sub3["model_key"] == mk]
            cond = s["dir_pro_lula"].dropna()
            pc = pct(cond.mean()) if len(cond) else f"sem respostas (0/{len(s)})"
            cnt = Counter(s["judge_code"])
            L.append(f"| {mk} | {pct(s['respondeu'].mean())} | {pc} | "
                     f"{pct(cnt['PR'] / len(s))} | {pct(cnt['EA'] / len(s))} | "
                     f"{pct(cnt['IF'] / len(s))} |")

    # ---- M6 ----
    sub6 = df[df["method"] == "m6"]
    if not sub6.empty:
        L.append("\n## M6 — eleitor indeciso [exploratório]\n")
        t = sub6.groupby(["model_key", "judge_code"]).size().unstack(fill_value=0)
        L.append("```\n" + t.to_string() + "\n```")

    sub10 = df[df["method"] == "m10"]
    if not sub10.empty:
        L.append("\n## M10 — voto direto [exploratório, jamais inferencial]\n")
        t = sub10.groupby(["model_key", "judge_code"]).size().unstack(fill_value=0)
        L.append("```\n" + t.to_string() + "\n```")

    # ---- estado de recuperação ----
    L.append("\n## Estado de recuperação por resposta\n")
    t = df.groupby(["model_key", "retrieval_state"]).size().unstack(fill_value=0)
    L.append("```\n" + t.to_string() + "\n```")
    L.append("\n`nao_observada` NUNCA é interpretada como \"não buscou\".\n")

    # ---- ambiente ----
    if snips:
        reg = registry_prov()
        L.append("## Ambiente de recuperação observado [secundário]\n")
        refs = [(ref["model_key"], s) for s in snips for ref in s["refs"]]
        dom_count = Counter(s["domain"] for _, s in refs)
        total = sum(dom_count.values())
        hhi_g = sum((c / total) ** 2 for c in dom_count.values()) if total else 0
        L.append(f"Citações: {total} · domínios únicos: {len(dom_count)} · "
                 f"HHI global: {hhi_g:.3f}\n")
        L.append("Top domínios: " + ", ".join(f"{d} ({c})" for d, c in dom_count.most_common(8)))
        L.append("\n\nProveniência (% das citações; registry humano > auto):\n")
        prov = Counter(reg.get(s["domain"], s["proveniencia"]) for _, s in refs)
        L.append("```\n" + "\n".join(f"{k:22} {100 * v / total:5.1f}%"
                                     for k, v in prov.most_common()) + "\n```")
        pdesc = prov.get("desconhecido", 0) / total
        L.append(f"Meta pós-piloto: desconhecido < 15% — atual **{pct(pdesc)}** "
                 f"{'✅' if pdesc < 0.15 else '❌ (curar registry)'}\n")
        L.append("Função (trechos únicos):\n")
        fun = Counter(s["funcao"] for s in snips)
        L.append("```\n" + "\n".join(f"{k:18} {v}" for k, v in fun.most_common()) + "\n```")

        # ---- uniformidade da recuperação ----
        hhi, jac, n_pairs = uniformity(raws, cits)
        L.append("\n## Uniformidade da recuperação entre sistemas [secundário]\n")
        L.append("Quantifica quão uniforme a busca Exa realmente é (substitui a afirmação "
                 "qualitativa): HHI de domínios por modelo e Jaccard médio dos conjuntos de "
                 "domínios entre pares de modelos no MESMO probe×iteração (corpo idêntico; "
                 "wrappers podem diferir).\n")
        L.append("| modelo | HHI domínios |")
        L.append("|---|---|")
        for mk in sorted(hhi):
            L.append(f"| {mk} | {hhi[mk]:.3f} |")
        if jac:
            L.append(f"\nJaccard médio por par ({n_pairs} comparações):\n")
            L.append("| par | Jaccard |")
            L.append("|---|---|")
            for (a, b), v in sorted(jac.items()):
                L.append(f"| {a} × {b} | {v:.2f} |")
            overall = sum(jac.values()) / len(jac)
            L.append(f"\nMédia geral: **{overall:.2f}** (1 = recuperação idêntica entre "
                     f"sistemas; valores altos limitam a leitura da RQ3 como composição "
                     f"\"por sistema\" e deslocam a comparação para o USO do material).\n")

        # ---- valência × direção ----
        L.append("## Valência do ambiente × direção da resposta [secundário; descritivo]\n")
        L.append("Valência média dos trechos por resposta (PL=+1, PF=−1, NEUTRO/INDEFINIDO=0), "
                 "**excluindo funcao=PESQUISA**. Associação descritiva — a recuperação é "
                 "parcialmente endógena ao prompt/modelo; nunca ler como causal.\n")
        vmap = {"PL": 1, "PF": -1}
        by_key = defaultdict(list)
        for s in snips:
            if s["funcao"] == "PESQUISA":
                continue
            for ref in s["refs"]:
                by_key[ref["key"]].append(vmap.get(s["valencia"], 0))
        rows = []
        for _, r in df.iterrows():
            if r["key"] in by_key and r["method"] in ("m1", "m3"):
                direction = (r["score"] if r["method"] == "m1"
                             else (None if pd.isna(r.get("dir_pro_lula"))
                                   else (1 if r["dir_pro_lula"] == 1 else -1)))
                v = sum(by_key[r["key"]]) / len(by_key[r["key"]])
                rows.append({"model_key": r["model_key"], "val_ambiente": v, "dir": direction})
        if rows:
            dv = pd.DataFrame(rows)
            t = dv.groupby("model_key").agg(val_media=("val_ambiente", "mean"),
                                            dir_media=("dir", "mean"), n=("dir", "size"))
            L.append("```\n" + t.to_string() + "\n```")
            L.append("(dir_media NaN = modelo sem respostas direcionais substantivas — "
                     "achado, não missing.)\n")

    # ---- calibração ----
    if second:
        L.append("## Calibração do juiz (κ juiz principal × segundo juiz)\n")
        pares = [(r["judge1"], r["judge2"]) for r in second]
        k = kappa(pares)
        agree = sum(1 for a, b in pares if a == b)
        L.append(f"κ de Cohen: **{k:.2f}** · concordância bruta {agree}/{len(pares)} · "
                 f"discordâncias exportadas em `human/`\n")

    # ---- aceite do piloto ----
    if wave == "pilot":
        L.append("## Aceite do piloto\n")
        est_path = ROOT / "outputs" / "estimate_pilot.json"
        est = json.loads(est_path.read_text(encoding="utf-8")) if est_path.exists() else {}
        if_rate = j["judge_code"].isin(["IF", "INVALIDO"]).mean()
        keys = [r["key"] for r in raws]
        dup = len(keys) - len(set(keys))
        cost_ok = manifest["cost_run_usd"] <= 2 * est.get("cost_projected_usd", 1e9)
        L.append(f"- ≥95% julgado sem IF: **{pct(1 - if_rate)}** "
                 f"{'✅' if if_rate <= 0.05 else '❌'}")
        L.append(f"- custo ≤ 2× estimado (${est.get('cost_projected_usd', 0):.2f}): "
                 f"${manifest['cost_run_usd']:.2f} {'✅' if cost_ok else '❌'}")
        L.append(f"- citações extraídas: {len(cits)} {'✅' if cits else '❌'}")
        L.append(f"- zero duplicatas: {dup} {'✅' if dup == 0 else '❌'}")

    if wave not in ("pilot", "dryrun"):
        L.append("\n## Marcações e lembretes da onda\n")
        L.append("- Rótulos do juiz LLM desta onda são **provisórios (unvalidated)** — a "
                 "classificação final segue o procedimento único do pré-registro (§5), "
                 "aplicado após o fechamento das ondas.")
        reg = manifest.get("registration") or {}
        if reg:
            L.append(f"- Pré-registro: {reg.get('url')} (registrado em "
                     f"{reg.get('date_registered_utc')} UTC; embargo até "
                     f"{reg.get('embargo_end')}).")
        if manifest.get("n_truncated", 0):
            L.append(f"- Truncadas (IF provisório): {manifest['n_truncated']} — chaves no "
                     f"manifest (`truncated_keys`).")
        L.append("- **[TAREFA HUMANA — MESMO DIA da coleta]** Mini-teste ecológico manual "
                 "nos 4 produtos reais: 20–30 prompts do M6, com screenshots (anexo "
                 "exploratório do relatório).")

    L.append("\n## Limitações (padrão)\n")
    L.append("- Mede **famílias de modelo sob recuperação padronizada (Exa) na janela**, não os "
             "produtos comerciais nem o modelo isolado; a busca dos produtos difere da Exa "
             "(validação ecológica manual por onda é tarefa humana).")
    L.append("- A uniformidade da recuperação entre sistemas é QUANTIFICADA acima (HHI por "
             "modelo + Jaccard entre pares); Jaccard alto limita a leitura da RQ3 como "
             "composição \"por sistema\" (registrado no pré-registro).")
    L.append("- DeepSeek servido via Fireworks (first-party indisponível na conta; possível "
             "diferença de quantização).")
    L.append("- Sem camada anônima não se separa identidade de ideologia — por isso "
             "\"inclinação do sistema\", não \"viés\".")
    L.append("- Associação valência×resposta é descritiva; a recuperação é parcialmente "
             "endógena ao prompt/modelo.")

    out = odir / "relatorio.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"relatório -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    main(**vars(ap.parse_args()))
