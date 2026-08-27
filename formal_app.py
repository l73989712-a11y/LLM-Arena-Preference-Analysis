"""Streamlit adapter for the verified, frozen formal research explorer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.formal_explorer import (
    ExplorerSpecificationError,
    FormalExplorerModel,
    build_formal_explorer,
    select_primary_rows,
    select_robustness_rows,
)
from src.formal_figures import (
    FigureSpecificationError,
    build_formal_publication_package,
    render_heterogeneity_figure,
    render_primary_figure,
    render_rank_uncertainty_figure,
    render_robustness_figure,
)
from src.formal_presentation import PresentationModelError, build_formal_presentation
from src.formal_report import ReportSpecificationError, build_formal_report, render_formal_report_markdown
from src.formal_results import FrozenResultsError, load_frozen_formal_research


@dataclass(frozen=True)
class RuntimeExplorer:
    explorer: FormalExplorerModel
    primary_figure: Any
    rank_figure: Any
    robustness_figure: Any
    heterogeneity_figure: Any


def build_runtime_explorer(artifact_root: str | Path = "outputs/research") -> RuntimeExplorer:
    """Run the one-way frozen pipeline used by the formal application entrypoint."""
    try:
        bundle = load_frozen_formal_research(artifact_root)
        presentation = build_formal_presentation(bundle)
        package = build_formal_publication_package(presentation)
        report = build_formal_report(presentation, package)
        report_markdown = render_formal_report_markdown(report, presentation, package)
        explorer = build_formal_explorer(presentation, package, report, report_markdown)
        return RuntimeExplorer(
            explorer,
            render_primary_figure(package.primary_figure),
            render_rank_uncertainty_figure(package.rank_uncertainty_figure),
            render_robustness_figure(package.robustness_figure),
            render_heterogeneity_figure(package.heterogeneity_figure),
        )
    except (FrozenResultsError, PresentationModelError, FigureSpecificationError, ReportSpecificationError, ExplorerSpecificationError) as exc:
        raise RuntimeError(f"Frozen formal research inputs could not be verified: {exc}") from exc


def _show_figure(figure: Any) -> None:
    st.pyplot(figure, clear_figure=False)
    plt.close(figure)


def _table_frame(rows: tuple[Any, ...]) -> pd.DataFrame:
    return pd.DataFrame([row.__dict__ for row in rows])


def _render_overview(explorer: FormalExplorerModel) -> None:
    overview = explorer.overview
    st.warning("Historical frozen evidence - not a current leaderboard.")
    st.write(overview.research_question)
    st.metric("Models", overview.model_count)
    st.metric("Frozen analyses", overview.frozen_analysis_count)
    st.subheader("Primary top three")
    st.dataframe(pd.DataFrame(overview.primary_top_three, columns=("Model", "Point rank")), hide_index=True, use_container_width=True)
    st.subheader("Claim boundaries")
    for boundary in overview.claim_boundary:
        st.write(f"- {boundary}")


def _render_primary(explorer: FormalExplorerModel, primary_figure: Any = None, rank_figure: Any = None) -> None:
    top_n = st.slider("Display top N", min_value=1, max_value=20, value=20)
    model_ids = [row.model_id for row in explorer.primary.rows]
    selected_model = st.selectbox("Model", ("All models", *model_ids))
    model_id = None if selected_model == "All models" else selected_model
    rows = select_primary_rows(explorer, top_n=top_n, model_id=model_id)
    st.dataframe(_table_frame(rows), hide_index=True, use_container_width=True)
    st.caption(explorer.primary.score_figure.caption)
    st.write(f"Figure: {explorer.primary.score_figure.title} (`{explorer.primary.score_figure.filename}`)")
    if primary_figure is not None and st.checkbox("Show preference figure", value=True):
        _show_figure(primary_figure)
    st.caption(explorer.primary.rank_figure.caption)
    st.write(f"Figure: {explorer.primary.rank_figure.title} (`{explorer.primary.rank_figure.filename}`)")
    if rank_figure is not None and st.checkbox("Show rank uncertainty figure", value=True):
        _show_figure(rank_figure)


def _render_robustness(explorer: FormalExplorerModel, figure: Any = None) -> None:
    analysis = st.selectbox("Frozen analysis", explorer.robustness.analyses)
    model_ids = [row.model_id for row in explorer.primary.rows]
    selected_model = st.selectbox("Model", ("All models", *model_ids), key="robustness-model")
    model_id = None if selected_model == "All models" else selected_model
    st.info(explorer.robustness.s1_s2_boundary)
    st.dataframe(_table_frame(select_robustness_rows(explorer, analysis_label=analysis, model_id=model_id)), hide_index=True, use_container_width=True)
    st.caption(explorer.robustness.figure.caption)
    st.write(f"Figure: {explorer.robustness.figure.title} (`{explorer.robustness.figure.filename}`)")
    if figure is not None and st.checkbox("Show robustness figure", value=True):
        _show_figure(figure)


def _render_heterogeneity(explorer: FormalExplorerModel, figure: Any = None) -> None:
    st.subheader("English-Subgroup Heterogeneity")
    st.write(f"Classification: {explorer.heterogeneity.classification.upper()}")
    st.write(f"Causal interpretation: {explorer.heterogeneity.causal_interpretation}")
    st.write(f"Top-four set preserved: {explorer.heterogeneity.top4_set_preserved}")
    st.write(f"Top-four order preserved: {explorer.heterogeneity.top4_order_preserved}")
    st.dataframe(_table_frame(explorer.heterogeneity.rows), hide_index=True, use_container_width=True)
    st.caption(explorer.heterogeneity.figure.caption)
    st.write(f"Figure: {explorer.heterogeneity.figure.title} (`{explorer.heterogeneity.figure.filename}`)")
    if figure is not None and st.checkbox("Show heterogeneity figure", value=True):
        _show_figure(figure)


def _render_provenance(explorer: FormalExplorerModel) -> None:
    st.warning(explorer.provenance.historical_source_warning)
    st.write(f"Formal evidence status: {explorer.provenance.formal_evidence_status}")
    st.dataframe(_table_frame(explorer.provenance.rows), hide_index=True, use_container_width=True)


def _render_report(explorer: FormalExplorerModel) -> None:
    st.markdown(explorer.report_markdown)


def _close_runtime_figures(runtime: RuntimeExplorer) -> None:
    for figure in (
        runtime.primary_figure,
        runtime.rank_figure,
        runtime.robustness_figure,
        runtime.heterogeneity_figure,
    ):
        plt.close(figure)


def _render_tabs(explorer: FormalExplorerModel, figures: RuntimeExplorer | None) -> None:
    st.set_page_config(page_title="Formal Historical Arena Research", layout="wide")
    st.title("Formal Historical Arena Research")
    st.caption(explorer.overview.historical_population_warning)
    tabs = st.tabs(("Overview", "Primary & Uncertainty", "Robustness", "English-Subgroup Heterogeneity", "Methods & Provenance", "Report"))
    with tabs[0]:
        _render_overview(explorer)
    with tabs[1]:
        _render_primary(explorer, figures.primary_figure if figures is not None else None, figures.rank_figure if figures is not None else None)
    with tabs[2]:
        _render_robustness(explorer, figures.robustness_figure if figures is not None else None)
    with tabs[3]:
        _render_heterogeneity(explorer, figures.heterogeneity_figure if figures is not None else None)
    with tabs[4]:
        _render_provenance(explorer)
    with tabs[5]:
        _render_report(explorer)


def render_explorer_ui(runtime: RuntimeExplorer | FormalExplorerModel) -> None:
    """Render only the verified explorer state and release runtime figures after each cycle."""
    if isinstance(runtime, RuntimeExplorer):
        try:
            _render_tabs(runtime.explorer, runtime)
        finally:
            _close_runtime_figures(runtime)
        return
    if isinstance(runtime, FormalExplorerModel):
        _render_tabs(runtime, None)
        return
    raise TypeError("render_explorer_ui expects RuntimeExplorer or FormalExplorerModel")


def main() -> None:
    try:
        runtime = build_runtime_explorer()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()
    render_explorer_ui(runtime)


if __name__ == "__main__":
    main()
