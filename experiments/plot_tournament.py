"""Genera un heatmap PNG del torneo a partir del JSON producido por
experiments/tournament.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def plot_tournament_heatmap(
    json_path: str, output_path: str | None = None
) -> None:
    with open(json_path) as f:
        data = json.load(f)

    bots = data["bots"]
    matrix = data["matrix"]
    n = len(bots)

    grid = np.zeros((n, n))
    for i, a in enumerate(bots):
        for j, b in enumerate(bots):
            v = matrix[a][b]
            grid[i, j] = v if v is not None else 0.5

    fig, ax = plt.subplots(
        figsize=(max(8, n * 1.2), max(6, n * 1.0))
    )

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "tournament", ["#c0392b", "#ecf0f1", "#27ae60"]
    )

    im = ax.imshow(grid, cmap=cmap, vmin=0.0, vmax=1.0, aspect="equal")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(bots, rotation=45, ha="right")
    ax.set_yticklabels(bots)
    ax.set_xlabel("vs")
    ax.set_ylabel("Bot (fila)")
    ax.set_title(f"Torneo round-robin (n={data['n_seeds']} por matchup)")

    for i in range(n):
        for j in range(n):
            if i == j:
                txt = "-"
            else:
                txt = f"{grid[i, j] * 100:.0f}%"
            text_color = "white" if abs(grid[i, j] - 0.5) > 0.25 else "black"
            ax.text(
                j, i, txt, ha="center", va="center",
                color=text_color, fontsize=10,
            )

    plt.colorbar(im, ax=ax, label="Win rate")
    plt.tight_layout()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Heatmap guardado en {output_path}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", type=str, default="reports/tournament.json"
    )
    parser.add_argument(
        "--output", type=str, default="reports/tournament_heatmap.png"
    )
    args = parser.parse_args()
    plot_tournament_heatmap(args.input, args.output)


if __name__ == "__main__":
    main()
