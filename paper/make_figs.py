# -*- coding: utf-8 -*-
"""Figuras e números do preprint (onda 2026-09-w1). Paleta de referência validada
(dataviz skill): categóricas slots 1-4, divergente azul<->vermelho com meio neutro,
sequencial azul. Saída: paper/figs/*.pdf + paper/numbers.tex"""
import json
import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from analyze import sanity_flags, uniformity  # noqa: E402
from common import read_jsonl  # noqa: E402

WAVE = "2026-09-w1"
ODIR = ROOT / "outputs" / WAVE
JDIR = ROOT / "data" / "judged" / WAVE
RDIR = ROOT / "data" / "raw" / WAVE
FIGS = ROOT / "paper" / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20261004)

# ---- paleta (referência validada; modo light, superfície #fcfcfb) ----
SURF = "#fcfcfb"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASE = "#e1e0d9", "#c3c2b7"
MODEL_COLOR = {"chatgpt": "#2a78d6", "claude": "#eb6834",
               "deepseek": "#1baf7a", "gemini": "#eda100"}
MODEL_LABEL = {"chatgpt": "GPT-5.6-Luna", "claude": "Claude Sonnet 4.6",
               "deepseek": "DeepSeek V4 Flash", "gemini": "Gemini 3.7 Flash"}
MODELS = ["chatgpt", "claude", "deepseek", "gemini"]
CAT4 = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # substantive/PR/EA/IF
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#1c5cab", "#104281"]
DIV_NEG, DIV_MID, DIV_POS = "#2a78d6", "#f0efec", "#e34948"  # Flavio <- neutro -> Lula
DIMS = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]
DIM_LABEL = {"D1": "Economy", "D2": "Health", "D3": "Education", "D4": "Security",
             "D5": "Environment", "D6": "Agribusiness", "D7": "Social programs"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5,
    "axes.edgecolor": BASE, "axes.labelcolor": INK2, "axes.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 8,
    "ytick.labelsize": 8, "figure.facecolor": SURF, "axes.facecolor": SURF,
    "savefig.facecolor": SURF, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.grid": False, "legend.frameon": False, "pdf.fonttype": 42,
})

df = pd.read_csv(ODIR / "scores.csv")
dfp = pd.read_csv(ODIR / "m2_pairs.csv")
snips = read_jsonl(JDIR / "citations_judged.jsonl")
cits = read_jsonl(RDIR / "citations.jsonl")
manifest = json.loads((RDIR / "manifest.json").read_text(encoding="utf-8"))
raws = []
for f in sorted(RDIR.glob("*_*.jsonl")):
    if f.name != "citations.jsonl":
        raws.extend(read_jsonl(f))

SUBST = {"m1": {"CT", "C", "D", "DT"}, "m2": {"NUM"}, "m3": {"LULA", "FLAVIO"},
         "m10": {"LULA", "FLAVIO"}, "m6": {"PENDE_L", "PENDE_F", "EQUILIBRADO"}}
NUMS = {}


def boot_ci(vals, stat=np.mean, n=5000):
    vals = np.asarray(vals, dtype=float)
    if len(vals) == 0:
        return np.nan, np.nan
    idx = RNG.integers(0, len(vals), size=(n, len(vals)))
    bs = stat(vals[idx], axis=1)
    return np.percentile(bs, 2.5), np.percentile(bs, 97.5)


def wilson(k, n):
    if n == 0:
        return np.nan, np.nan
    z, p = 1.96, k / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return c - h, c + h


def spine_off(ax, keep=("left", "bottom")):
    for s in ax.spines:
        ax.spines[s].set_visible(s in keep)


# ================= Fig 1 — response composition =================
methods = ["m1", "m2", "m3", "m6", "m10"]
mlab = {"m1": "M1 Likert", "m2": "M2 0–10 rating", "m3": "M3 forced choice",
        "m6": "M6 undecided voter", "m10": "M10 direct vote"}
cats = [("substantive", CAT4[0]), ("PR", CAT4[1]), ("EA", CAT4[2]), ("IF", CAT4[3])]
fig, axes = plt.subplots(1, 5, figsize=(7.2, 2.5), sharey=True)
j = df[~df["method"].isin(["sanidade", "baseline"])]
for ax, me in zip(axes, methods):
    for yi, mk in enumerate(MODELS[::-1]):
        s = j[(j["model_key"] == mk) & (j["method"] == me)]
        n = len(s)
        shares = {"substantive": s["judge_code"].isin(SUBST[me]).sum() / n,
                  "PR": (s["judge_code"] == "PR").sum() / n,
                  "EA": (s["judge_code"] == "EA").sum() / n,
                  "IF": s["judge_code"].isin(["IF", "INVALIDO"]).sum() / n}
        left = 0.0
        for cname, ccol in cats:
            v = shares[cname]
            if v > 0:
                ax.barh(yi, v, left=left, height=0.58, color=ccol,
                        edgecolor=SURF, linewidth=1.2)
                if v >= 0.18:
                    ax.text(left + v / 2, yi, f"{100 * v:.0f}", ha="center",
                            va="center", color="#ffffff", fontsize=7.2)
            left += v
    ax.set_xlim(0, 1)
    ax.set_title(mlab[me], fontsize=8.5, color=INK, pad=4)
    ax.set_xticks([0, 0.5, 1])
    ax.set_xticklabels(["0", "50", "100%"])
    spine_off(ax, keep=("bottom",))
    ax.tick_params(length=0)
axes[0].set_yticks(range(4))
axes[0].set_yticklabels([MODEL_LABEL[m] for m in MODELS[::-1]], color=INK2)
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in cats]
fig.legend(handles, ["Substantive", "Policy refusal (PR)",
                     "Epistemic abstention (EA)", "Format failure (IF)"],
           loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.06), fontsize=8)
fig.tight_layout()
fig.savefig(FIGS / "fig1_composition.pdf", bbox_inches="tight")
plt.close(fig)

# ================= Fig 2 — conditional direction =================
fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6))
panels = []
m1 = df[df["method"] == "m1"]
for mk in MODELS:
    v = m1[m1["model_key"] == mk]["score"].dropna().values
    panels.append(("a", mk, v))
ax = axes[0]
for yi, mk in enumerate(MODELS[::-1]):
    v = m1[m1["model_key"] == mk]["score"].dropna().values
    dimmeans = [m1[(m1["model_key"] == mk) & (m1["dim_id"] == d)]["score"].dropna().mean()
                for d in DIMS]
    if len(v):
        lo, hi = boot_ci(v)
        ax.plot([lo, hi], [yi, yi], color=MODEL_COLOR[mk], lw=1.6, solid_capstyle="round")
        ax.plot(np.array(dimmeans), np.full(7, yi) + 0.22, "o", ms=2.6,
                color=MODEL_COLOR[mk], alpha=0.45, mew=0)
        ax.plot(v.mean(), yi, "o", ms=6.5, color=MODEL_COLOR[mk],
                mec=SURF, mew=1.2)
        ax.text(v.mean(), yi - 0.34, f"{v.mean():+.2f}", ha="center", fontsize=7.5,
                color=INK)
    else:
        ax.text(0, yi, "no substantive responses (0/105)", ha="center", va="center",
                fontsize=7, color=MUTED, style="italic")
ax.set_xlim(-2, 2)
ax.axvline(0, color=BASE, lw=0.8)
ax.set_title("M1 aligned Likert score", fontsize=8.5, color=INK)
ax.set_xlabel("← favors Bolsonaro   ·   favors Lula →", fontsize=7.5)
ax = axes[1]
for yi, mk in enumerate(MODELS[::-1]):
    p = dfp[dfp["model_key"] == mk]["delta"].dropna().values
    dimmeans = [dfp[(dfp["model_key"] == mk) & (dfp["dim_id"] == d)]["delta"].dropna().mean()
                for d in DIMS]
    if len(p):
        lo, hi = boot_ci(p)
        ax.plot([lo, hi], [yi, yi], color=MODEL_COLOR[mk], lw=1.6, solid_capstyle="round")
        ax.plot(np.array(dimmeans), np.full(7, yi) + 0.22, "o", ms=2.6,
                color=MODEL_COLOR[mk], alpha=0.45, mew=0)
        ax.plot(p.mean(), yi, "o", ms=6.5, color=MODEL_COLOR[mk], mec=SURF, mew=1.2)
        ax.text(p.mean(), yi - 0.34, f"{p.mean():+.2f}", ha="center", fontsize=7.5,
                color=INK)
    else:
        ax.text(0, yi, "no complete pairs (0/105)", ha="center", va="center",
                fontsize=7, color=MUTED, style="italic")
ax.set_xlim(-5, 5)
ax.axvline(0, color=BASE, lw=0.8)
ax.set_title("M2 within-pair Δ (Lula − Bolsonaro)", fontsize=8.5, color=INK)
ax.set_xlabel("rating difference (0–10 scale)", fontsize=7.5)
ax = axes[2]
m3 = df[df["method"] == "m3"]
for yi, mk in enumerate(MODELS[::-1]):
    s = m3[m3["model_key"] == mk]
    cond = s["dir_pro_lula"].dropna()
    if len(cond):
        k, n = int(cond.sum()), len(cond)
        lo, hi = wilson(k, n)
        ax.plot([100 * lo, 100 * hi], [yi, yi], color=MODEL_COLOR[mk], lw=1.6,
                solid_capstyle="round")
        ax.plot(100 * k / n, yi, "o", ms=6.5, color=MODEL_COLOR[mk], mec=SURF, mew=1.2)
        ax.text(100 * k / n, yi - 0.34, f"{100 * k / n:.0f}%", ha="center",
                fontsize=7.5, color=INK)
    else:
        ax.text(50, yi, "no substantive responses (0/105)", ha="center", va="center",
                fontsize=7, color=MUTED, style="italic")
ax.set_xlim(0, 100)
ax.axvline(50, color=BASE, lw=0.8)
ax.set_title("M3 conditional preference", fontsize=8.5, color=INK)
ax.set_xlabel("% choosing Lula (among responses)", fontsize=7.5)
for ax in axes:
    ax.set_yticks(range(4))
    ax.set_ylim(-0.7, 3.7)
    spine_off(ax, keep=("bottom",))
    ax.tick_params(length=0)
axes[0].set_yticklabels([MODEL_LABEL[m] for m in MODELS[::-1]], color=INK2)
axes[1].set_yticklabels([])
axes[2].set_yticklabels([])
fig.tight_layout()
fig.savefig(FIGS / "fig2_direction.pdf", bbox_inches="tight")
plt.close(fig)

# ================= Fig 3 — lean by dimension (heatmaps) =================
fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.3))
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
cmap = LinearSegmentedColormap.from_list("div", [DIV_NEG, DIV_MID, DIV_POS])
for ax, (title, table, vmax) in zip(axes, [
        ("M1 aligned score by dimension", "m1", 2.0),
        ("M2 within-pair Δ by dimension", "m2", 4.0)]):
    M = np.full((4, 7), np.nan)
    for i, mk in enumerate(MODELS):
        for k, d in enumerate(DIMS):
            if table == "m1":
                v = m1[(m1["model_key"] == mk) & (m1["dim_id"] == d)]["score"].dropna()
            else:
                v = dfp[(dfp["model_key"] == mk) & (dfp["dim_id"] == d)]["delta"].dropna()
            M[i, k] = v.mean() if len(v) else np.nan
    norm = TwoSlopeNorm(vcenter=0, vmin=-vmax, vmax=vmax)
    ax.imshow(np.where(np.isnan(M), 0, M), cmap=cmap, norm=norm, aspect="auto")
    for i in range(4):
        for k in range(7):
            if np.isnan(M[i, k]):
                ax.text(k, i, "abst.", ha="center", va="center", fontsize=6.5,
                        color=MUTED, style="italic")
            else:
                dark = abs(M[i, k]) > 0.55 * vmax
                ax.text(k, i, f"{M[i, k]:+.1f}", ha="center", va="center",
                        fontsize=6.8, color="#ffffff" if dark else INK)
    ax.set_xticks(range(7))
    ax.set_xticklabels([DIM_LABEL[d] for d in DIMS], rotation=35, ha="right",
                       fontsize=6.8)
    ax.set_yticks(range(4))
    if ax is axes[0]:
        ax.set_yticklabels([MODEL_LABEL[m] for m in MODELS], fontsize=7.5, color=INK2)
    else:
        ax.set_yticklabels([])
    ax.set_title(title, fontsize=8.5, color=INK, pad=4)
    spine_off(ax, keep=())
    ax.tick_params(length=0)
    for i in range(4):
        for k in range(7):
            ax.add_patch(plt.Rectangle((k - 0.5, i - 0.5), 1, 1, fill=False,
                                       edgecolor=SURF, lw=1.5))
sm = plt.cm.ScalarMappable(cmap=cmap, norm=TwoSlopeNorm(vcenter=0, vmin=-1, vmax=1))
cb = fig.colorbar(sm, ax=axes, fraction=0.025, pad=0.02, ticks=[-1, 0, 1])
cb.ax.set_yticklabels(["Bolsonaro", "0", "Lula"], fontsize=6.8)
cb.outline.set_visible(False)
fig.savefig(FIGS / "fig3_dimensions.pdf", bbox_inches="tight")
plt.close(fig)

# ================= Fig 4 — retrieval environment =================
hhi, jac, n_pairs = uniformity(raws, cits)
refs = [(ref["model_key"], s) for s in snips for ref in s["refs"]]
from collections import Counter
dom_count = Counter(s["domain"] for _, s in refs)
total = sum(dom_count.values())
fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.5), gridspec_kw={"width_ratios": [1.5, 1]})
ax = axes[0]
top = dom_count.most_common(10)[::-1]
ax.barh(range(10), [c for _, c in top], height=0.6, color=SEQ[3],
        edgecolor=SURF, linewidth=1)
for yi, (d, c) in enumerate(top):
    ax.text(c + total * 0.002, yi, f"{100 * c / total:.1f}%", va="center", fontsize=7,
            color=INK2)
ax.set_yticks(range(10))
ax.set_yticklabels([d for d, _ in top], fontsize=7)
ax.set_title(f"Top domains ({total:,} citations, {len(dom_count)} domains)",
             fontsize=8.5, color=INK)
ax.set_xlabel("citations", fontsize=7.5)
spine_off(ax, keep=("bottom",))
ax.tick_params(length=0)
ax = axes[1]
J = np.full((4, 4), np.nan)
for (a, b), v in jac.items():
    ia, ib = MODELS.index(a), MODELS.index(b)
    J[ia, ib] = J[ib, ia] = v
cmapseq = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#104281"])
ax.imshow(np.where(np.isnan(J), 0, J), cmap=cmapseq, vmin=0.4, vmax=0.8, aspect="auto")
for i in range(4):
    for k in range(4):
        if i == k:
            ax.text(k, i, "·", ha="center", va="center", color=MUTED, fontsize=8)
        else:
            ax.text(k, i, f"{J[i, k]:.2f}", ha="center", va="center",
                    color="#ffffff" if J[i, k] > 0.62 else INK, fontsize=7.5)
        ax.add_patch(plt.Rectangle((k - 0.5, i - 0.5), 1, 1, fill=False,
                                   edgecolor=SURF, lw=1.5))
short = {"chatgpt": "GPT", "claude": "Claude", "deepseek": "DeepSeek", "gemini": "Gemini"}
ax.set_xticks(range(4))
ax.set_xticklabels([short[m] for m in MODELS], fontsize=7.5)
ax.set_yticks(range(4))
ax.set_yticklabels([short[m] for m in MODELS], fontsize=7.5)
ax.set_title("Between-system domain overlap\n(mean Jaccard, same probe×iteration)",
             fontsize=8.5, color=INK)
spine_off(ax, keep=())
ax.tick_params(length=0)
fig.tight_layout()
fig.savefig(FIGS / "fig4_environment.pdf", bbox_inches="tight")
plt.close(fig)

# ================= números para o TeX =================
def texnum(name, val):
    NUMS[name] = val


m1_stats, m2_stats, m3_stats = {}, {}, {}
for mk in MODELS:
    v = m1[m1["model_key"] == mk]["score"].dropna().values
    lo, hi = boot_ci(v) if len(v) else (np.nan, np.nan)
    m1_stats[mk] = (len(v), v.mean() if len(v) else np.nan, lo, hi)
    p = dfp[dfp["model_key"] == mk]["delta"].dropna().values
    lo, hi = boot_ci(p) if len(p) else (np.nan, np.nan)
    m2_stats[mk] = (len(p), p.mean() if len(p) else np.nan, lo, hi)
    cond = m3[m3["model_key"] == mk]["dir_pro_lula"].dropna()
    if len(cond):
        k, n = int(cond.sum()), len(cond)
        lo, hi = wilson(k, n)
        m3_stats[mk] = (n, 100 * k / n, 100 * lo, 100 * hi)
    else:
        m3_stats[mk] = (0, np.nan, np.nan, np.nan)

flags = sanity_flags(raws)
vmap = {"PL": 1, "PF": -1}
from collections import defaultdict
by_key = defaultdict(list)
for s in snips:
    if s["funcao"] == "PESQUISA":
        continue
    for ref in s["refs"]:
        by_key[ref["key"]].append(vmap.get(s["valencia"], 0))
val_rows = {}
for mk in MODELS:
    vs = [np.mean(by_key[k]) for k in df[df["model_key"] == mk]["key"] if k in by_key]
    val_rows[mk] = (np.mean(vs), len(vs))

second = read_jsonl(JDIR / "second_judge.jsonl")
pares = [(r["judge1"], r["judge2"]) for r in second]
agree = sum(1 for a, b in pares if a == b)

out = {"m1": m1_stats, "m2": m2_stats, "m3": m3_stats,
       "hhi": hhi, "jac_mean": float(np.mean(list(jac.values()))),
       "n_jac_groups": n_pairs, "total_cits": total, "n_domains": len(dom_count),
       "flags": {mk: sum(flags.get(mk, {}).values()) for mk in MODELS},
       "valence": val_rows, "kappa_agree": (agree, len(pares))}
(ROOT / "paper" / "computed.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
print("figs em", FIGS)
print(json.dumps(out, indent=1, default=lambda x: round(float(x), 3)))
