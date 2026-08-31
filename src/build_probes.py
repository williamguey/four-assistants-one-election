# -*- coding: utf-8 -*-
"""Materializa dimensões e bateria de sanidade em CSV (fonte da verdade fica em common.py;
os corpos dos probes são templates fixos — nunca parafrasear)."""
import csv

from common import DIMS, ROOT, SANIDADE, body_m1, body_m2, body_m3, body_m6, BODY_M10


def main():
    pdir = ROOT / "data" / "probes"
    pdir.mkdir(parents=True, exist_ok=True)
    with open(pdir / "dims.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dim_id", "nome", "frase"])
        w.writerows(DIMS)
    with open(pdir / "sanidade.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["san_id", "pergunta"])
        w.writerows(SANIDADE)
    # amostra dos corpos gerados, para conferência humana (não é insumo da coleta)
    with open(pdir / "corpos_amostra.txt", "w", encoding="utf-8") as f:
        f.write("M1 af D1:  " + body_m1("D1", "af") + "\n")
        f.write("M1 rev D1: " + body_m1("D1", "rev") + "\n")
        f.write("M2 L D5:   " + body_m2("D5", "L") + "\n")
        f.write("M2 F D5:   " + body_m2("D5", "F") + "\n")
        f.write("M3 LF D7:  " + body_m3("D7", "LF") + "\n")
        f.write("M3 FL D7:  " + body_m3("D7", "FL") + "\n")
        f.write("M6 D4:     " + body_m6("D4") + "\n")
        f.write("M10:       " + BODY_M10 + "\n")
    print(f"dims: {len(DIMS)} | sanidade: {len(SANIDADE)} -> {pdir}")


if __name__ == "__main__":
    main()
