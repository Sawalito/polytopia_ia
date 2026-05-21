"""
experiments/plots.py  —  Polytopia AI · Evaluation Plots  (v3 - correct API)
=============================================================================
Uses the real run_game() return keys:
  result['winner']       -> 0 | 1 | None
  result['final_turn']   -> int
  result['final_score']  -> {0: float, 1: float}

Bot files discovered individually (no strategy_bots.py):
  random_bot.py / aggressive_bot.py / defensive_bot.py /
  economic_bot.py / greedy_attack_bot.py / heuristic_bot.py

Usage:
  python -m experiments.plots
"""

from __future__ import annotations

import sys
import warnings
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns

warnings.filterwarnings("ignore")

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent
SRC     = ROOT / "src"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
sys.path.insert(0, str(SRC))

# ── style ──────────────────────────────────────────────────────────────────────
PALETTE  = ["#00c8ff", "#ff3e6c", "#ffe000", "#3ddc97", "#ff7c2a", "#b57bee"]
BG       = "#0f1117"
GRID_COL = "#2a2d3a"
TEXT_COL = "#e8eaf0"

sns.set_theme(style="dark", rc={
    "axes.facecolor":   BG,
    "figure.facecolor": BG,
    "axes.edgecolor":   GRID_COL,
    "axes.labelcolor":  TEXT_COL,
    "xtick.color":      TEXT_COL,
    "ytick.color":      TEXT_COL,
    "text.color":       TEXT_COL,
    "grid.color":       GRID_COL,
    "axes.grid":        True,
    "grid.linewidth":   0.5,
    "font.family":      "monospace",
})


# ── bot registry  (module_path, class_name, display_name) ─────────────────────
BOT_REGISTRY = [
    ("polytopia.agents.random_bot",       "RandomBot",       "Random"),
    ("polytopia.agents.heuristic_bot",    "HeuristicBot",    "HeuristicV3"),
    ("polytopia.agents.aggressive_bot",   "AggressiveBot",   "Aggressive"),
    ("polytopia.agents.defensive_bot",    "DefensiveBot",    "Defensive"),
    ("polytopia.agents.economic_bot",     "EconomicBot",     "Economic"),
    ("polytopia.agents.greedy_attack_bot","GreedyAttackBot", "GreedyAttack"),
]

def load_available_bots() -> dict[str, type]:
    """Returns {display_name: class} for every bot that imports successfully."""
    import importlib
    available = {}
    for mod_path, cls_name, display in BOT_REGISTRY:
        try:
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name)
            available[display] = cls
            print(f"  [bot] {display:15s} ✓")
        except Exception as e:
            print(f"  [bot] {display:15s} ✗  ({e})")
    return available


def make_bot(cls, player_id: int, seed: int):
    for kw in [{"player_id": player_id, "seed": seed},
               {"player_id": player_id}, {}]:
        try:
            return cls(**kw)
        except TypeError:
            continue
    raise RuntimeError(f"Cannot instantiate {cls}")


# ── core match runner ──────────────────────────────────────────────────────────
def run_match(cls0, cls1, seed: int) -> dict:
    """
    Run one game. Returns:
      winner   : 0 | 1 | None
      turns    : int
      score_p0 : float
      score_p1 : float
    """
    from polytopia.engine.state_init import create_initial_state
    from polytopia.game_loop import run_game

    state  = create_initial_state(seed=seed)
    bot0   = make_bot(cls0, player_id=0, seed=seed + 1000)
    bot1   = make_bot(cls1, player_id=1, seed=seed + 2000)
    result = run_game(bot0, bot1, state)

    scores = result.get("final_score", {})
    return {
        "winner":   result.get("winner"),
        "turns":    result.get("final_turn", result.get("turn", 30)),
        "score_p0": float(scores.get(0, 0)),
        "score_p1": float(scores.get(1, 0)),
    }


# ── run all pairs (BOTH orderings) ────────────────────────────────────────────
def run_tournament(available: dict[str, type], n_seeds: int) -> dict:
    """
    Runs each pair both ways (A-as-P0 vs B, B-as-P0 vs A).
    Returns a big dict with all raw game data.
    """
    bot_list = list(available.keys())
    n        = len(bot_list)

    # raw_games[(i,j)] = list of match dicts where i is P0 and j is P1
    raw_games: dict[tuple, list[dict]] = defaultdict(list)

    for i, n0 in enumerate(bot_list):
        for j, n1 in enumerate(bot_list):
            if i == j:
                continue
            c0, c1 = available[n0], available[n1]
            print(f"  {n0:12s}(P0) vs {n1:12s}(P1) … ", end="", flush=True)
            w0 = w1 = 0
            for seed in range(n_seeds):
                try:
                    r = run_match(c0, c1, seed)
                    raw_games[(i, j)].append(r)
                    if r["winner"] == 0: w0 += 1
                    elif r["winner"] == 1: w1 += 1
                except Exception as e:
                    raw_games[(i, j)].append(
                        {"winner": None, "turns": 30, "score_p0": 0, "score_p1": 0})
            print(f"{w0}–{w1}")

    return {"bot_list": bot_list, "raw_games": raw_games, "n_seeds": n_seeds}


# ── build win-rate matrix (both orderings averaged) ────────────────────────────
def build_matrix(data: dict) -> np.ndarray:
    bot_list = data["bot_list"]
    raw      = data["raw_games"]
    n        = len(bot_list)
    matrix   = np.full((n, n), np.nan)
    np.fill_diagonal(matrix, 0.5)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # games where i=P0, j=P1
            games_ij = raw.get((i, j), [])
            # games where j=P0, i=P1
            games_ji = raw.get((j, i), [])

            i_wins = (
                sum(1 for g in games_ij if g["winner"] == 0) +  # i is P0
                sum(1 for g in games_ji if g["winner"] == 1)    # i is P1
            )
            total = len(games_ij) + len(games_ji)
            if total > 0:
                matrix[i, j] = i_wins / total

    return matrix


# ── PLOT 1 – Heatmap ──────────────────────────────────────────────────────────
def plot_heatmap(bot_list: list[str], matrix: np.ndarray, out: Path):
    n = len(bot_list)
    fig, ax = plt.subplots(figsize=(max(6, n), max(5, n - 1)))
    fig.patch.set_facecolor(BG)

    cmap = sns.diverging_palette(10, 145, s=80, l=50, as_cmap=True)
    sns.heatmap(
        matrix, mask=np.isnan(matrix),
        annot=True, fmt=".0%",
        cmap=cmap, center=0.5, vmin=0, vmax=1,
        linewidths=1, linecolor=GRID_COL, ax=ax,
        cbar_kws={"label": "Win rate (row vs col)"},
        annot_kws={"size": 12, "weight": "bold"},
    )
    ax.set_xticklabels(bot_list, rotation=35, ha="right", fontsize=10)
    ax.set_yticklabels(bot_list, rotation=0,  fontsize=10)
    ax.set_title(
        "🏆  Tournament Win-Rate Matrix\n"
        "(both orderings averaged — eliminates P0/P1 bias)",
        fontsize=12, pad=14, color=TEXT_COL, weight="bold",
    )
    ax.set_xlabel("Opponent (column)", fontsize=10)
    ax.set_ylabel("Player   (row)",    fontsize=10)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[✓] {out.name}")


# ── PLOT 2 – Win-Rate Bar ─────────────────────────────────────────────────────
def plot_winrates(bot_list: list[str], matrix: np.ndarray, out: Path):
    n  = len(bot_list)
    wr = []
    for i in range(n):
        row = [matrix[i, j] for j in range(n)
               if i != j and not np.isnan(matrix[i, j])]
        wr.append(np.mean(row) if row else 0.5)

    order  = np.argsort(wr)[::-1]
    labels = [bot_list[i] for i in order]
    values = [wr[i]       for i in order]
    colors = [PALETTE[k % len(PALETTE)] for k in range(n)]

    fig, ax = plt.subplots(figsize=(max(7, n * 1.3), 5))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)

    bars = ax.bar(labels, values, color=colors, width=0.55,
                  zorder=3, edgecolor=BG)
    ax.axhline(0.5, color=TEXT_COL, linestyle="--", lw=1, alpha=0.4)
    ax.set_ylim(0, 1.10)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_title("📊  Average Win Rate per Bot\n(across all opponents, both positions)",
                 fontsize=13, pad=12, color=TEXT_COL, weight="bold")
    ax.set_ylabel("Win Rate", fontsize=11)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.015,
                f"{val:.0%}", ha="center", va="bottom",
                fontsize=11, weight="bold", color=TEXT_COL)

    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[✓] {out.name}")


# ── PLOT 3 – Benchmark: HeuristicV3 vs Random ────────────────────────────────
def plot_benchmark(data: dict, out: Path):
    bot_list = data["bot_list"]
    raw      = data["raw_games"]

    # find indices
    try:
        ih = bot_list.index("HeuristicV3")
        ir = bot_list.index("Random")
    except ValueError:
        # fallback: first two bots
        ih, ir = 1, 0

    # collect all games between the two (both orderings)
    # normalise so "HeuristicV3 wins" = 1
    records = []
    for g in raw.get((ih, ir), []):   # heuristic P0
        records.append({"h_wins": g["winner"] == 0, "turns": g["turns"]})
    for g in raw.get((ir, ih), []):   # heuristic P1
        records.append({"h_wins": g["winner"] == 1, "turns": g["turns"]})

    cum_h, cum_r = [], []
    wh = wr = 0
    for r in records:
        if r["h_wins"]: wh += 1
        else:           wr += 1
        cum_h.append(wh); cum_r.append(wr)

    seeds  = list(range(1, len(records) + 1))
    total  = len(records)
    wr_pct = wh / total if total else 0

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)

    ax.plot(seeds, cum_h, color=PALETTE[0], lw=2.5,
            label=f"HeuristicV3  ({wh}/{total} wins)", marker="o", markersize=4)
    ax.plot(seeds, cum_r, color=PALETTE[1], lw=2.5,
            label=f"Random       ({wr}/{total} wins)", marker="s", markersize=4)

    ax.set_title(
        f"📈  Benchmark: HeuristicV3 vs Random\n"
        f"Cumulative wins — {total} games (both orderings)  |  "
        f"Heuristic win rate: {wr_pct:.0%}",
        fontsize=12, pad=12, color=TEXT_COL, weight="bold",
    )
    ax.set_xlabel("Game index", fontsize=11)
    ax.set_ylabel("Cumulative wins", fontsize=11)
    ax.legend(fontsize=10, framealpha=0.25)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[✓] {out.name}")


# ── PLOT 4 – Score Distribution ───────────────────────────────────────────────
def plot_scores(data: dict, out: Path):
    """Collect each bot's scores across ALL games it played (as P0 or P1)."""
    bot_list = data["bot_list"]
    raw      = data["raw_games"]
    n        = len(bot_list)

    scores_by_bot: dict[str, list[float]] = defaultdict(list)

    for (i, j), games in raw.items():
        ni, nj = bot_list[i], bot_list[j]
        for g in games:
            if g["score_p0"] > 0 or g["score_p1"] > 0:   # skip failed games
                scores_by_bot[ni].append(g["score_p0"])
                scores_by_bot[nj].append(g["score_p1"])

    labels = [b for b in bot_list if scores_by_bot[b]]
    values = [scores_by_bot[b] for b in labels]

    if not labels:
        print("[warn] No score data – skipping plot 4")
        return

    fig, ax = plt.subplots(figsize=(max(7, n * 1.5), 5))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)

    bp = ax.boxplot(
        values, patch_artist=True, widths=0.45,
        medianprops={"color": "#ffffff", "linewidth": 2.5},
        whiskerprops={"color": TEXT_COL, "linewidth": 1.2},
        capprops={"color": TEXT_COL, "linewidth": 1.5},
        flierprops={"marker": "o", "markerfacecolor": TEXT_COL,
                    "markersize": 4, "alpha": 0.35},
    )
    for patch, color in zip(bp["boxes"], PALETTE):
        patch.set_facecolor(color); patch.set_alpha(0.80)

    rng = np.random.default_rng(0)
    for k, (vals, color) in enumerate(zip(values, PALETTE), start=1):
        jitter = rng.uniform(-0.18, 0.18, len(vals))
        ax.scatter([k + j for j in jitter], vals,
                   color=color, alpha=0.40, s=16, zorder=4)

    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_title("🎯  Final Score Distribution per Bot\n"
                 "(formula: 10·city_levels + units_alive + stars)",
                 fontsize=12, pad=12, color=TEXT_COL, weight="bold")
    ax.set_ylabel("Final score", fontsize=10)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[✓] {out.name}")


# ── PLOT 5 – Combat & Game-Length Stats ───────────────────────────────────────
def plot_combat(data: dict, out: Path):
    bot_list = data["bot_list"]
    raw      = data["raw_games"]

    # unique pairs only (i < j), merge both orderings
    pair_labels, avg_turns, avg_sw, avg_sl = [], [], [], []

    seen = set()
    for i in range(len(bot_list)):
        for j in range(len(bot_list)):
            if i >= j: continue
            pair = (i, j)
            if pair in seen: continue
            seen.add(pair)

            games = raw.get((i, j), []) + raw.get((j, i), [])
            if not games: continue

            ni, nj = bot_list[i], bot_list[j]
            pair_labels.append(f"{ni}\nvs\n{nj}")
            avg_turns.append(np.mean([g["turns"] for g in games]))

            ws, ls = [], []
            for g in games:
                s0, s1, w = g["score_p0"], g["score_p1"], g["winner"]
                if w == 0:   ws.append(s0); ls.append(s1)
                elif w == 1: ws.append(s1); ls.append(s0)
            avg_sw.append(np.mean(ws) if ws else 0)
            avg_sl.append(np.mean(ls) if ls else 0)

    if not pair_labels:
        print("[warn] No combat data – skipping plot 5")
        return

    x = np.arange(len(pair_labels))
    bw = 0.30

    fig, (ax1, ax2) = plt.subplots(1, 2,
                                    figsize=(max(10, len(pair_labels) * 2), 5))
    fig.patch.set_facecolor(BG)
    ax1.set_facecolor(BG); ax2.set_facecolor(BG)

    # — avg game length ————————————————————————————————
    ax1.bar(x, avg_turns, color=PALETTE[0], width=0.5, zorder=3, edgecolor=BG)
    ax1.axhline(30, color=PALETTE[1], linestyle="--", lw=1, alpha=0.6,
                label="max turns (30)")
    ax1.set_xticks(x); ax1.set_xticklabels(pair_labels, fontsize=7)
    ax1.set_ylim(0, 33)
    ax1.set_title("⏱  Avg Game Length (turns)",
                  fontsize=11, pad=10, color=TEXT_COL, weight="bold")
    ax1.set_ylabel("Turns", fontsize=10)
    ax1.legend(fontsize=8, framealpha=0.2)
    for xi, val in zip(x, avg_turns):
        ax1.text(xi, val + 0.3, f"{val:.1f}", ha="center",
                 fontsize=8, color=TEXT_COL, weight="bold")

    # — winner vs loser score ——————————————————————————
    ax2.bar(x - bw/2, avg_sw, width=bw, color=PALETTE[2],
            label="Winner", zorder=3, edgecolor=BG)
    ax2.bar(x + bw/2, avg_sl, width=bw, color=PALETTE[1],
            label="Loser",  zorder=3, edgecolor=BG, alpha=0.75)
    ax2.set_xticks(x); ax2.set_xticklabels(pair_labels, fontsize=7)
    ax2.set_title("🏅  Avg Final Score: Winner vs Loser",
                  fontsize=11, pad=10, color=TEXT_COL, weight="bold")
    ax2.set_ylabel("Score", fontsize=10)
    ax2.legend(fontsize=9, framealpha=0.25)

    fig.suptitle("⚔️  Combat & Game Stats",
                 fontsize=13, color=TEXT_COL, weight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[✓] {out.name}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    N_SEEDS = 10   # per ordering → each pair plays 2×10 = 20 games total

    print("=" * 62)
    print("  Polytopia AI — Evaluation Plots  (v3 — correct API)")
    print("=" * 62)

    available = load_available_bots()

    if len(available) < 2:
        print("[error] Need at least 2 bots. Aborting.")
        sys.exit(1)

    n     = len(available)
    pairs = n * (n - 1)
    print(f"\n  {n} bots  |  {pairs} orderings  |  "
          f"{N_SEEDS} seeds each  =  {pairs * N_SEEDS} games\n")

    # ── run tournament ─────────────────────────────────────────────────────────
    data   = run_tournament(available, N_SEEDS)
    matrix = build_matrix(data)

    # ── plots ──────────────────────────────────────────────────────────────────
    print("\n  Generating plots …\n")
    plot_heatmap (data["bot_list"], matrix, REPORTS / "plot_1_heatmap.png")
    plot_winrates(data["bot_list"], matrix, REPORTS / "plot_2_winrates.png")
    plot_benchmark(data,                    REPORTS / "plot_3_benchmark.png")
    plot_scores  (data,                     REPORTS / "plot_4_scores.png")
    plot_combat  (data,                     REPORTS / "plot_5_combat.png")

    print("\n" + "=" * 62)
    print(f"  All plots saved to:  {REPORTS}/")
    print("=" * 62)


if __name__ == "__main__":
    main()