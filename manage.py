# -*- coding: utf-8 -*-
"""Runner do pipeline (make não existe nesta máquina).
Uso: python manage.py <etapa> [args]
Etapas: probes | wrappers | test | estimate <dryrun|pilot|full> | dry-run | pilot |
        collect --confirm-prereg | judge <wave> [--second] | score <wave> |
        analyze <wave> | export-human <wave>
Sequência: probes -> wrappers -> test -> estimate -> dry-run -> pilot ->
           [HUMANO: pré-registro + recarga] -> collect --confirm-prereg -> judge -> score ->
           analyze -> export-human"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT / "src")}


def run(script, *args):
    r = subprocess.run([sys.executable, str(ROOT / "src" / script), *args], env=ENV)
    sys.exit(r.returncode) if r.returncode else None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "probes":
        run("build_probes.py")
    elif cmd == "wrappers":
        run("build_wrappers.py")
    elif cmd == "test":
        run("selftest.py")
    elif cmd == "estimate":
        run("estimate.py", "--mode", rest[0] if rest else "full")
    elif cmd == "dry-run":
        run("estimate.py", "--mode", "dryrun")
        run("collect.py", "--mode", "dryrun")
    elif cmd == "pilot":
        run("estimate.py", "--mode", "pilot")
        run("collect.py", "--mode", "pilot")
    elif cmd == "collect":
        run("estimate.py", "--mode", "full")
        run("collect.py", "--mode", "full", *rest)
    elif cmd == "judge":
        run("judge.py", "--wave", rest[0], *rest[1:])
    elif cmd == "score":
        run("score.py", "--wave", rest[0])
    elif cmd == "analyze":
        run("analyze.py", "--wave", rest[0])
    elif cmd == "export-human":
        run("export_human.py", "--wave", rest[0])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
