#!/usr/bin/env python3
"""Build hindcast skill summary table + two-panel heatmap for one city.

Input discovery is automatic from the current repository layout:
notebooks/FIGURES/*-<CITY>/*_hindcast_skill_summary.csv

Rows in output:
- method
- within each method: CRPSS and RMSE improvement

Columns in output:
- horizons
- within each horizon: ranked vs random, ranked vs full
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "horizon",
    "method",
    "ranked_crpss_vs_random",
    "ranked_crpss_vs_full",
    "ranked_rmse_improvement_vs_random",
    "ranked_rmse_improvement_vs_full",
}

HORIZON_ORDER = ["year_1", "years_2_5", "years_6_10"]
HORIZON_LABELS = {
    "year_1": "Y1",
    "years_2_5": "Y2-5",
    "years_6_10": "Y6-10",
}
COMPARISON_ORDER = ["ranked vs random", "ranked vs full"]
SCORE_ORDER = ["CRPSS", "RMSE improvement"]
ABS_MAX = {"CRPSS": 0.25, "RMSE improvement": 0.5}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a city-level method/score vs horizon/comparison heatmap from hindcast summary CSV files."
    )
    parser.add_argument("city", help="City name, e.g. Barcelona, Paris, Prague, Bergen.")
    parser.add_argument(
        "--title",
        default=None,
        help="Heatmap title.",
    )
    return parser.parse_args()


def normalize_horizon_order(horizons: Iterable[str]) -> list[str]:
    unique = list(dict.fromkeys(horizons))
    preferred = [h for h in HORIZON_ORDER if h in unique]
    remaining = sorted(h for h in unique if h not in preferred)
    return preferred + remaining


def load_records(files: list[Path]) -> pd.DataFrame:
    records: list[dict[str, object]] = []

    for file_path in files:
        df = pd.read_csv(file_path)
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            missing_str = ", ".join(sorted(missing))
            raise ValueError(f"{file_path} is missing required columns: {missing_str}")

        for _, row in df.iterrows():
            method = str(row["method"])
            horizon = str(row["horizon"])
            records.extend(
                [
                    {
                        "method": method,
                        "score": "CRPSS",
                        "horizon": horizon,
                        "comparison": "ranked vs random",
                        "value": row["ranked_crpss_vs_random"],
                    },
                    {
                        "method": method,
                        "score": "CRPSS",
                        "horizon": horizon,
                        "comparison": "ranked vs full",
                        "value": row["ranked_crpss_vs_full"],
                    },
                    {
                        "method": method,
                        "score": "RMSE improvement",
                        "horizon": horizon,
                        "comparison": "ranked vs random",
                        "value": row["ranked_rmse_improvement_vs_random"],
                    },
                    {
                        "method": method,
                        "score": "RMSE improvement",
                        "horizon": horizon,
                        "comparison": "ranked vs full",
                        "value": row["ranked_rmse_improvement_vs_full"],
                    },
                ]
            )

    if not records:
        raise ValueError("No records found in input files.")

    return pd.DataFrame.from_records(records)


def build_table(records: pd.DataFrame) -> pd.DataFrame:
    method_order = sorted(records["method"].drop_duplicates().tolist())
    horizon_order = normalize_horizon_order(records["horizon"].tolist())

    records = records.copy()
    records["method"] = pd.Categorical(records["method"], categories=method_order, ordered=True)
    records["score"] = pd.Categorical(records["score"], categories=SCORE_ORDER, ordered=True)
    records["horizon"] = pd.Categorical(records["horizon"], categories=horizon_order, ordered=True)
    records["comparison"] = pd.Categorical(
        records["comparison"], categories=COMPARISON_ORDER, ordered=True
    )

    table = records.pivot_table(
        index=["method", "score"],
        columns=["comparison", "horizon"],
        values="value",
        aggfunc="mean",
    ).sort_index(axis=0)

    column_order = pd.MultiIndex.from_product(
        [COMPARISON_ORDER, horizon_order], names=["comparison", "horizon"]
    )
    table = table.reindex(columns=column_order)

    return table


def discover_city_files(city: str) -> tuple[list[Path], Path]:
    figure_root = Path("notebooks/FIGURES")
    city_dirs = sorted(path for path in figure_root.glob(f"*-{city}") if path.is_dir())
    if not city_dirs:
        raise FileNotFoundError(f"No city folder matched: {figure_root}/*-{city}")

    files: list[Path] = []
    for city_dir in city_dirs:
        files.extend(sorted(city_dir.glob("*_hindcast_skill_summary.csv")))

    if not files:
        raise FileNotFoundError(
            f"No hindcast summary files found in matched city folders for '{city}'."
        )

    output_dir = city_dirs[0] if len(city_dirs) == 1 else figure_root
    return files, output_dir


def derive_prefix_from_files(files: list[Path], methods: Iterable[str]) -> str:
    method_candidates = sorted({str(method) for method in methods}, key=len, reverse=True)
    first_name = files[0].name
    for method in method_candidates:
        suffix = f"_{method}_hindcast_skill_summary.csv"
        if first_name.endswith(suffix):
            return first_name[: -len(suffix)]
    raise ValueError(
        f"Could not derive a common prefix from '{first_name}'. Expected '*_<method>_hindcast_skill_summary.csv'."
    )

def plot_score_panel(
    ax: plt.Axes,
    score_table: pd.DataFrame,
    vmin: float,
    vmax: float,
) -> plt.AxesImage:
    values = score_table.to_numpy(dtype=float)
    n_rows, n_cols = values.shape

    im = ax.imshow(values, cmap="RdBu_r", vmin=vmin, vmax=vmax, aspect="auto")

    ax.set_yticks(np.arange(n_rows))
    ax.set_yticklabels(score_table.index.tolist())

    # Bottom x labels: horizon labels for each subcolumn.
    horizon_labels = [HORIZON_LABELS.get(h, h) for _, h in score_table.columns]
    ax.set_xticks(np.arange(n_cols))
    ax.set_xticklabels(horizon_labels, rotation=0)

    # Top labels: comparison groups centered over their horizon block.
    comparisons = list(dict.fromkeys(c for c, _ in score_table.columns))
    horizons = list(dict.fromkeys(h for _, h in score_table.columns))
    n_horizons = max(len(horizons), 1)
    for i, comparison in enumerate(comparisons):
        center = i * n_horizons + (n_horizons - 1) / 2
        ax.text(
            center,
            1.015,
            comparison,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    # Vertical separators between comparison groups.
    for i in range(1, len(comparisons)):
        ax.axvline(i * n_horizons - 0.5, color="black", linewidth=1.0)

    # Annotate values.
    for i in range(n_rows):
        for j in range(n_cols):
            val = values[i, j]
            text = "" if not np.isfinite(val) else f"{val:.3f}"
            ax.text(j, i, text, ha="center", va="center", color="black", fontsize=8)

    # Draw thin cell grid.
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1)
    ax.tick_params(which="minor", bottom=False, left=False)

    return im


def plot_heatmap(table: pd.DataFrame, title: str, output_png: Path, output_pdf: Path) -> None:
    methods = sorted({method for method, _ in table.index})
    n_rows = len(methods)
    n_cols = table.shape[1]
    fig_w = max(9, n_cols * 1.25)
    fig_h = max(5, n_rows * 0.7 + 2.5)

    fig_w = 8
    fig_h = 2.4

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(fig_w * 1.5, fig_h),
        sharey=True,
        constrained_layout=True,
    )
    fig.suptitle(title, y=1.1)

    for ax, score_name in zip(axes, SCORE_ORDER):
        score_table = table.xs(score_name, level="score")
        score_table = score_table.reindex(methods)
        abs_max = ABS_MAX.get(score_name, 1.0)
        im = plot_score_panel(ax, score_table, -abs_max, abs_max)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cbar.set_label(score_name)

    fig.savefig(output_png, dpi=300, bbox_inches="tight")
    fig.savefig(output_pdf, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()

    city = args.city.strip()
    files, output_dir = discover_city_files(city)

    records = load_records(files)
    table = build_table(records)
    prefix = derive_prefix_from_files(files, records["method"].drop_duplicates().tolist())

    output_dir.mkdir(parents=True, exist_ok=True)

    output_stem = f"{prefix}_hindcast_skill_heatmap"
    output_csv = output_dir / f"{output_stem}.csv"
    output_png = output_dir / f"{output_stem}.png"
    output_pdf = output_dir / f"{output_stem}.pdf"

    title = args.title or f"{prefix}: hindcast skill by method and horizon"

    table.to_csv(output_csv)
    plot_heatmap(table, title, output_png, output_pdf)

    print(f"Input files: {len(files)}")
    print(f"Table CSV: {output_csv}")
    print(f"Heatmap PNG: {output_png}")
    print(f"Heatmap PDF: {output_pdf}")


if __name__ == "__main__":
    main()
