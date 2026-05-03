"""Generate all plots and the report_sections.md.

Reads CSVs produced by optimize.py and experiments.py; writes 7 figures + report.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import generate as gen_mod
from .ga import GAConfig, run_ga

HERE = Path(__file__).parent
DATA = HERE / "data"
FIGURES = HERE / "figures"


def _require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing — run optimize.py and experiments.py first"
        )
    return path


def plot_convergence() -> None:
    _require(DATA / "convergence.csv")
    summary = json.loads(_require(DATA / "results_summary.json").read_text())
    df = pd.read_csv(DATA / "convergence.csv")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(df["generation"], df["best_fitness"], label="GA best", color="steelblue")
    ax.plot(
        df["generation"],
        df["avg_fitness"],
        label="GA average",
        color="orange",
        alpha=0.7,
    )
    greedy_value = summary["greedy"]["total_value"]
    ax.axhline(
        greedy_value,
        color="gray",
        linestyle="--",
        label=f"Greedy baseline (${greedy_value:.2f})",
    )
    if summary.get("dp"):
        dp_value = summary["dp"]["total_value"]
        ax.axhline(
            dp_value,
            color="green",
            linestyle=":",
            label=f"DP optimum (${dp_value:.2f})",
        )
    ax.set_xlabel("generation")
    ax.set_ylabel("fitness (total estimated value, $)")
    ax.set_title("GA convergence vs. baselines")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "convergence.png", dpi=300)
    plt.close(fig)


def plot_ga_vs_baselines() -> None:
    summary = json.loads(_require(DATA / "results_summary.json").read_text())
    labels = ["Random (avg)", "Random (best)", "Greedy", "GA"]
    values = [
        summary["random"]["mean_value"],
        summary["random"]["best_value"],
        summary["greedy"]["total_value"],
        summary["ga"]["total_value"],
    ]
    colors = ["lightgray", "gray", "steelblue", "forestgreen"]
    if summary.get("dp"):
        labels.append("DP (exact)")
        values.append(summary["dp"]["total_value"])
        colors.append("goldenrod")

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, values, color=colors)
    for bar, v in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"${v:.0f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.set_ylabel("total estimated value ($)")
    ax.set_title("GA vs. baselines on 200-lead pool")
    fig.tight_layout()
    fig.savefig(FIGURES / "ga_vs_baselines.png", dpi=300)
    plt.close(fig)


def plot_mutation_sensitivity() -> None:
    df = pd.read_csv(_require(DATA / "mutation_sensitivity.csv"))
    agg = df.groupby("mutation_rate")["best_fitness"].agg(["mean", "std"]).reset_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(
        agg["mutation_rate"],
        agg["mean"],
        yerr=agg["std"],
        marker="o",
        capsize=4,
        color="steelblue",
    )
    ax.set_xscale("log")
    ax.set_xlabel("mutation rate (log scale)")
    ax.set_ylabel("best fitness ($) — mean ± std over 5 seeds")
    ax.set_title("Mutation rate sensitivity")
    fig.tight_layout()
    fig.savefig(FIGURES / "mutation_sensitivity.png", dpi=300)
    plt.close(fig)


def plot_population_sensitivity() -> None:
    df = pd.read_csv(_require(DATA / "population_sensitivity.csv"))
    agg = (
        df.groupby("pop_size")
        .agg(
            best_fitness_mean=("best_fitness", "mean"),
            best_fitness_std=("best_fitness", "std"),
            wall_time_mean=("wall_time_s", "mean"),
        )
        .reset_index()
    )

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.errorbar(
        agg["pop_size"],
        agg["best_fitness_mean"],
        yerr=agg["best_fitness_std"],
        marker="o",
        capsize=4,
        color="steelblue",
        label="best fitness",
    )
    ax1.set_xlabel("population size")
    ax1.set_ylabel("best fitness ($)", color="steelblue")
    ax1.tick_params(axis="y", labelcolor="steelblue")

    ax2 = ax1.twinx()
    ax2.plot(
        agg["pop_size"],
        agg["wall_time_mean"],
        marker="s",
        color="tomato",
        label="wall time",
    )
    ax2.set_ylabel("wall time (s)", color="tomato")
    ax2.tick_params(axis="y", labelcolor="tomato")

    ax1.set_title("Population size: fitness vs. runtime")
    fig.tight_layout()
    fig.savefig(FIGURES / "population_sensitivity.png", dpi=300)
    plt.close(fig)


def plot_methods_by_scale() -> None:
    """Each method's fitness as a percentage of the DP optimum, across pool sizes.

    Raw-fitness curves overlap visually because all three methods land within 0.15%
    of each other at this scale. Plotting percent-of-optimum makes the (small but
    real) gaps legible.
    """
    df = pd.read_csv(_require(DATA / "scaling.csv"))
    pivot_fit = df.pivot(index="pool_size", columns="method", values="fitness")
    if "dp" not in pivot_fit.columns:
        return
    dp_values = pivot_fit["dp"]

    fig, ax = plt.subplots(figsize=(9, 5))
    method_styles = {
        "dp": ("DP (exact)", "goldenrod", "o", 10),
        "greedy": ("Greedy", "steelblue", "s", 9),
        "ga": ("GA", "forestgreen", "^", 9),
    }
    for method, (label, color, marker, size) in method_styles.items():
        if method in pivot_fit.columns:
            pct = pivot_fit[method] / dp_values * 100.0
            ax.plot(
                pct.index,
                pct.values,
                marker=marker,
                markersize=size,
                color=color,
                label=label,
                linewidth=2,
            )
            for x, y in zip(pct.index, pct.values):
                ax.annotate(
                    f"{y:.3f}%",
                    xy=(x, y),
                    xytext=(0, 8 if method == "greedy" else -14),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                    color=color,
                )

    ax.set_xlabel("pool size (leads)")
    ax.set_ylabel("% of DP optimum")
    ax.set_title("Solution quality vs. pool size (% of exact optimum)")
    ax.set_ylim(98.4, 100.15)
    ax.axhline(100, color="goldenrod", linestyle=":", alpha=0.4)
    ax.legend(loc="lower right")
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIGURES / "methods_by_scale.png", dpi=300)
    plt.close(fig)


def plot_scaling() -> None:
    df = pd.read_csv(_require(DATA / "scaling.csv"))
    pivot_fit = df.pivot(index="pool_size", columns="method", values="fitness")
    pivot_time = df.pivot(index="pool_size", columns="method", values="wall_time_s")

    gap_pct = None
    if "ga" in pivot_fit.columns and "greedy" in pivot_fit.columns:
        gap_pct = (pivot_fit["ga"] - pivot_fit["greedy"]) / pivot_fit["greedy"] * 100.0

    fig, ax1 = plt.subplots(figsize=(9, 5))
    if gap_pct is not None:
        ax1.plot(gap_pct.index, gap_pct.values, marker="o", color="steelblue", label="GA − Greedy (%)")
    ax1.axhline(0, color="gray", linewidth=0.5)
    ax1.set_xlabel("pool size (leads)")
    ax1.set_ylabel("GA improvement over greedy (%)", color="steelblue")
    ax1.tick_params(axis="y", labelcolor="steelblue")

    ax2 = ax1.twinx()
    for method in [c for c in pivot_time.columns if c in ("ga", "dp", "greedy")]:
        ax2.plot(
            pivot_time.index,
            pivot_time[method].values,
            marker="s",
            label=f"{method} time",
            linestyle="--",
        )
    ax2.set_ylabel("wall time (s)")
    ax2.set_yscale("log")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.set_title("Scaling: fitness gap and runtime vs. pool size")
    fig.tight_layout()
    fig.savefig(FIGURES / "scaling.png", dpi=300)
    plt.close(fig)


def plot_budget_sensitivity() -> None:
    df = pd.read_csv(_require(DATA / "budget_sensitivity.csv"))
    agg = (
        df.groupby("budget_pct")
        .agg(
            leads_mean=("leads_selected", "mean"),
            value_mean=("total_value", "mean"),
        )
        .reset_index()
    )

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(
        agg["budget_pct"] * 100,
        agg["leads_mean"],
        marker="o",
        color="steelblue",
        label="leads selected",
    )
    ax1.set_xlabel("budget (% of total pool cost)")
    ax1.set_ylabel("leads selected", color="steelblue")
    ax1.tick_params(axis="y", labelcolor="steelblue")

    ax2 = ax1.twinx()
    ax2.plot(
        agg["budget_pct"] * 100,
        agg["value_mean"],
        marker="s",
        color="forestgreen",
        label="total value captured",
    )
    ax2.set_ylabel("total value ($)", color="forestgreen")
    ax2.tick_params(axis="y", labelcolor="forestgreen")
    ax1.set_title("Budget tightness: selection count and value captured")
    fig.tight_layout()
    fig.savefig(FIGURES / "budget_sensitivity.png", dpi=300)
    plt.close(fig)


def plot_chromosome_heatmap() -> None:
    """Run a short GA, keep the final population's top-10 chromosomes as a heatmap."""
    df = gen_mod.load_pool()
    budget = gen_mod.load_budget()
    leads = df.to_dict(orient="records")

    # Re-run GA but capture final population by re-seeding and running a custom loop.
    # Simpler: run multiple GA seeds and take their best chromosomes as the "top 10".
    chromos = []
    for seed in range(10):
        res = run_ga(leads, budget, GAConfig(generations=80), seed=seed)
        chromos.append(res.best_chromosome)

    # Show only leads selected by at least one top solution (otherwise all-zero columns dominate).
    matrix = np.array(chromos)
    col_sum = matrix.sum(axis=0)
    active = np.where(col_sum > 0)[0]
    if len(active) == 0:
        active = np.arange(matrix.shape[1])
    matrix = matrix[:, active]

    fig, ax = plt.subplots(figsize=(max(10, len(active) * 0.08), 5))
    ax.imshow(matrix, aspect="auto", cmap="Blues", interpolation="nearest")
    ax.set_xlabel(f"lead index (showing {len(active)} leads selected by ≥1 run)")
    ax.set_ylabel("GA run (different seed)")
    ax.set_title("Top-10 GA solutions — chromosome heatmap")
    ax.set_yticks(range(10))
    ax.set_yticklabels([f"seed {s}" for s in range(10)])
    ax.set_xticks([])
    fig.tight_layout()
    fig.savefig(FIGURES / "chromosome_heatmap.png", dpi=300)
    plt.close(fig)


def write_report_sections() -> None:
    summary = json.loads(_require(DATA / "results_summary.json").read_text())
    budget_info = json.loads(_require(DATA / "budget.json").read_text())

    ga_value = summary["ga"]["total_value"]
    greedy_value = summary["greedy"]["total_value"]
    dp_value = summary["dp"]["total_value"] if summary.get("dp") else None
    optimality = f"{summary['ga_over_dp_pct']:.2f}%" if summary.get("ga_over_dp_pct") else "n/a (DP skipped)"

    sections = [
        "# Enrichment Budget Optimizer — Report Sections",
        "",
        "Generated by `evaluate.py`. Paste into the IFSA CS38-09 report as needed.",
        "",
        "## 1.5.1 PEAS Analysis",
        "",
        "| Dimension | Description |",
        "|---|---|",
        "| **Performance** | Maximize total expected value of enriched leads within the daily budget. Measured by total value captured, budget utilization (% of budget spent), and value density (total value / total cost). |",
        "| **Environment** | Pool of N prospected leads. Each has observable Google Places features (rating, review count, website presence, business type) plus derived attributes (estimated enrichment cost, estimated reply value). **Fully observable, deterministic, episodic, static, discrete, single-agent.** |",
        "| **Actuators** | Select a subset of leads to enrich (binary include/exclude decision per lead). |",
        "| **Sensors** | Google Places API (rating, reviews, website, phone, business types) and the Hermes cost model. |",
        "",
        "### Agent type progression (Class 3)",
        "",
        "The existing Hermes enricher is a **simple reflex agent** — it pulls the next N leads in queue order. Replacing it with the GA optimizer promotes it to a **utility-based agent** that assigns expected value to each lead and maximizes total utility under a budget constraint.",
        "",
        "## 1.5.2 Problem Formulation",
        "",
        "Given N items, each with value v_i and cost c_i, and a capacity B, find a binary vector x = (x_1, ..., x_N) that",
        "",
        "```",
        "maximize    Σ(v_i · x_i)",
        "subject to  Σ(c_i · x_i) ≤ B",
        "            x_i ∈ {0, 1}",
        "```",
        "",
        "This is the 0/1 knapsack problem — NP-hard in general, but solvable exactly in O(N·B) via DP when costs are integer (we scale cents × 10^5 to achieve this).",
        "",
        "## 1.5.3 GA Design Justification",
        "",
        "- **Binary chromosome** — natural mapping: each gene is a yes/no decision for one lead. No decoding step needed.",
        "- **Tournament selection (k=3)** — balances selection pressure against diversity. k=2 too weak (drift), k=5 too greedy (premature convergence).",
        "- **Uniform crossover** — the value of a gene does not depend on its position, so single-point / two-point crossover have no geometric justification here. Uniform crossover mixes genes independently, which matches the problem structure.",
        "- **Bit-flip mutation (rate 0.02)** — standard for binary chromosomes. On 200 leads ≈ 4 flips per chromosome, enough to explore without destroying good solutions.",
        "- **Elitism (top 2)** — guarantees the best-so-far is never lost, so the best-fitness history is monotonically non-decreasing.",
        "- **Budget repair heuristic** — after crossover/mutation, if a chromosome exceeds the budget, drop selected leads starting with the lowest value/cost ratio until feasible. Improves sample efficiency versus relying on the fitness penalty alone.",
        "",
        "## 1.5.4 Results Snapshot",
        "",
        f"- Pool: **{summary['pool_size']} leads** | Daily budget: **${budget_info['daily_budget']:.4f}** ({int(budget_info['budget_fraction']*100)}% of total pool cost)",
        f"- Random (mean over 1000 trials): **${summary['random']['mean_value']:.2f}**",
        f"- Random (best): **${summary['random']['best_value']:.2f}**",
        f"- Greedy (value/cost): **${greedy_value:.2f}**",
        f"- **GA: ${ga_value:.2f}**",
        f"- DP (exact optimum): **{'$' + format(dp_value, '.2f') if dp_value else 'skipped — table too large'}**",
        f"- GA optimality vs. DP: **{optimality}**",
        "",
        "## 1.5.5 Synthetic Data Justification",
        "",
        "The lead pool is synthetic but calibrated against real Hermes data. Enrichment cost ($0.002 base, multiplier for website presence) matches the Gemini Flash pricing in the production cost model. Deal sizes ($3k / $5k based on employee count) are the actual Hermes pricing tiers. Feature distributions (rating ~ N(4.2, 0.5), reviews lognormal, ~75% with websites) match the empirical distribution of Florida Google Places responses that Hermes has already collected.",
        "",
        "Using synthetic data lets us (a) run the full parameter-sensitivity matrix without burning real API budget, and (b) compare GA against the DP optimum on a controlled instance — which tells us exactly how close the GA is to optimal.",
        "",
        "## 1.5.6 Limitations",
        "",
        "- GA does not guarantee optimality. For N=200 with our scaled-integer costs, DP yields the ground-truth optimum; the GA typically closes to within 1–2%.",
        "- `estimated_value` is a heuristic (deal_size × reply_probability); in production this should be replaced by a trained model's output.",
        "- Cost model assumes independent per-lead enrichment costs. Batch pricing would change the formulation.",
        "",
    ]
    (DATA / "report_sections.md").write_text("\n".join(sections))


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)

    plot_convergence()
    plot_ga_vs_baselines()
    plot_mutation_sensitivity()
    plot_population_sensitivity()
    plot_scaling()
    plot_methods_by_scale()
    plot_budget_sensitivity()
    plot_chromosome_heatmap()
    write_report_sections()

    print(f"wrote 7 figures to {FIGURES}")
    print(f"wrote report sections to {DATA / 'report_sections.md'}")


if __name__ == "__main__":
    main()
