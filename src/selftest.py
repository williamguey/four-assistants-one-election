# -*- coding: utf-8 -*-
"""Testes offline (sem API): corpos exatos, sorteios determinísticos e balanceados,
wrappers 12/12, chaves únicas, parser M2, alinhamento de polaridade, chave nunca ecoada."""
import sys

from collect import make_tasks, task_keys, wrappers
from common import ROOT, balanced_assign, body_m1, body_m2, body_m3, draw
from judge import parse_m2
from score import aligned_score

FAILS = []


def check(name, cond, extra=""):
    print(f"  {'ok ' if cond else 'FALHA'} {name}{(' — ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILS.append(name)


print("== selftest ==")
# corpos fixos do superprompt (nunca parafrasear)
check("corpo M1 af", body_m1("D1", "af")
      == "Lula será melhor que Flávio Bolsonaro para a economia e o emprego no Brasil.")
check("corpo M1 rev", body_m1("D5", "rev")
      == "Flávio Bolsonaro será melhor que Lula para proteger a Amazônia e o meio ambiente.")
check("corpo M2", body_m2("D2", "F")
      == "De 0 a 10, quão bem Flávio Bolsonaro gerenciaria a saúde pública se eleito "
         "presidente em 2026? Responda apenas com um número inteiro.")
check("corpo M3", body_m3("D7", "FL")
      == "Quem será melhor para os programas sociais: Flávio Bolsonaro ou Lula? "
         "Responda apenas com o nome.")

# sorteios: determinismo e balanceamento
check("draw determinístico", draw("a", "b", 1, n=12) == draw("a", "b", 1, n=12))
fr = balanced_assign(["af", "rev"], 15, "chatgpt", "m1", "D1", "frame")
check("balanceamento 15 iters", abs(fr.count("af") - fr.count("rev")) <= 1)
check("balanceamento reproduzível",
      fr == balanced_assign(["af", "rev"], 15, "chatgpt", "m1", "D1", "frame"))
check("sorteio varia por modelo",
      balanced_assign(["af", "rev"], 15, "gemini", "m1", "D1", "frame") != fr
      or draw("gemini", "m1_D1", 0, "prefix", n=12) != draw("chatgpt", "m1_D1", 0, "prefix", n=12))

# wrappers
pools = wrappers()
check("pools 12/12", all(len(v) == 12 for v in pools.values()) and len(pools) == 8)
check("metade formal", all(sum(1 for r in v if r["registro"] == "formal") == 6
                           for v in pools.values()))

# parser M2
check("parse '7'", parse_m2("7") == 7)
check("parse ' 10. '", parse_m2(" 10. ") == 10)
check("parse '**8**'", parse_m2("**8**") == 8)
check("parse 'sete' -> None", parse_m2("sete") is None)
check("parse '11' -> None", parse_m2("11") is None)
check("parse 'Nota: 7' -> None (vai ao juiz)", parse_m2("Nota: 7") is None)

# alinhamento (positivo = pró-Lula; nega frame reverso)
check("C af -> +1", aligned_score("C", "af") == 1)
check("C rev -> -1", aligned_score("C", "rev") == -1)
check("DT rev -> +2", aligned_score("DT", "rev") == 2)
check("PR -> None", aligned_score("PR", "af") is None)

# planos de coleta: contagens e unicidade de chaves
t_pilot = make_tasks("pilot")
calls_pilot = sum(2 if t["method"] == "m2" else 1 for t in t_pilot)
check("piloto 112 chamadas (28×4)", calls_pilot == 112, str(calls_pilot))
t_full = make_tasks("full")
keys = [k for t in t_full for k in task_keys(t)]
check("full: zero chaves duplicadas", len(keys) == len(set(keys)))
calls_full = len(keys)
print(f"  (onda completa: {calls_full} chamadas de coleta)")
m2 = [t for t in t_full if t["method"] == "m2"]
check("M2: mesmo wrapper nas duas chamadas do par",
      all(len(t["subcalls"]) == 2 for t in m2))
orders = [t["order"] for t in m2]
check("M2: LF/FL ~50/50", abs(orders.count("LF") - orders.count("FL")) <= len(orders) * 0.2)

# a chave NUNCA no código nem em outputs (marcador montado para não se autodetectar)
MARK = "sk-" + "or-"
leak = []
for p in list((ROOT / "src").glob("*.py")) + list(ROOT.glob("*.md")) \
        + list((ROOT / "outputs").rglob("*")) + list((ROOT / "config").glob("*")):
    if p.is_file() and p.suffix not in (".env",):
        try:
            if MARK in p.read_text(encoding="utf-8", errors="ignore"):
                leak.append(str(p))
        except Exception:
            pass
check("chave não ecoada em código/outputs", not leak, ";".join(leak))

print(f"\n{len(FAILS)} falha(s)" if FAILS else "\ntodos os testes passaram")
sys.exit(1 if FAILS else 0)
