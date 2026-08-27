"""Read-only explorer view model built from the Phase 3 in-memory outputs."""

from __future__ import annotations

from dataclasses import dataclass

from src.formal_figures import (
    FormalPublicationPackage,
    HeterogeneityTableRow,
    PrimaryTableRow,
    ProvenanceTableRow,
    RobustnessTableRow,
    build_formal_publication_package,
)
from src.formal_presentation import FormalPresentationModel
from src.formal_report import FormalReport, render_formal_report_markdown


class ExplorerSpecificationError(ValueError):
    """Raised when E2/E3/report inputs cannot form a safe explorer model."""


@dataclass(frozen=True)
class ExplorerOverview:
    historical_population_warning: str
    research_question: str
    model_count: int
    frozen_analysis_count: int
    primary_top_three: tuple[tuple[str, int], ...]
    claim_boundary: tuple[str, ...]


@dataclass(frozen=True)
class ExplorerFigureReference:
    filename: str
    title: str
    caption: str


@dataclass(frozen=True)
class ExplorerPrimaryView:
    rows: tuple[PrimaryTableRow, ...]
    score_figure: ExplorerFigureReference
    rank_figure: ExplorerFigureReference


@dataclass(frozen=True)
class ExplorerRobustnessView:
    analyses: tuple[str, ...]
    rows: tuple[RobustnessTableRow, ...]
    s1_s2_boundary: str
    figure: ExplorerFigureReference


@dataclass(frozen=True)
class ExplorerHeterogeneityView:
    rows: tuple[HeterogeneityTableRow, ...]
    classification: str
    causal_interpretation: str
    top4_set_preserved: bool
    top4_order_preserved: bool
    figure: ExplorerFigureReference


@dataclass(frozen=True)
class ExplorerProvenanceView:
    rows: tuple[ProvenanceTableRow, ...]
    formal_evidence_status: str
    historical_source_warning: str


@dataclass(frozen=True)
class FormalExplorerModel:
    """Immutable read-only explorer state; it owns no loader or filesystem path."""

    overview: ExplorerOverview
    primary: ExplorerPrimaryView
    robustness: ExplorerRobustnessView
    heterogeneity: ExplorerHeterogeneityView
    provenance: ExplorerProvenanceView
    report_markdown: str


_EXPECTED_ANALYSES = ("Primary", "S1", "S2", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50", "S6-English")
_PRIMARY_S5_ANALYSES = _EXPECTED_ANALYSES[:8]
_CLAIM_BOUNDARY = (
    "historical population only",
    "not a current leaderboard",
    "not a capability ranking",
    "not a causal claim",
    "not an external generalization",
)
_HISTORICAL_WARNING = "Historical frozen dataset; not refreshed against current Arena."
_RESEARCH_QUESTION = (
    "How are model preferences estimated within the frozen historical Arena population, "
    "with what uncertainty and rank robustness?"
)


def _validate_inputs(
    model: FormalPresentationModel,
    package: FormalPublicationPackage,
    report: FormalReport,
    report_markdown: str,
) -> None:
    if not isinstance(model, FormalPresentationModel):
        raise TypeError("build_formal_explorer expects FormalPresentationModel")
    if not isinstance(package, FormalPublicationPackage):
        raise TypeError("build_formal_explorer expects FormalPublicationPackage")
    if not isinstance(report, FormalReport):
        raise TypeError("build_formal_explorer expects FormalReport")
    if not isinstance(report_markdown, str):
        raise TypeError("build_formal_explorer expects Markdown text")
    if (
        not isinstance(model.heterogeneity.classification, str)
        or model.heterogeneity.classification.casefold() != "partially robust / heterogeneous"
    ):
        raise ExplorerSpecificationError("S6 classification is not canonical")
    if model.heterogeneity.causal_interpretation != "NOT SUPPORTED":
        raise ExplorerSpecificationError("S6 causal boundary is not canonical")
    try:
        canonical_package = build_formal_publication_package(model)
    except (TypeError, ValueError) as exc:
        raise ExplorerSpecificationError(f"presentation model is not canonical: {exc}") from exc
    if package != canonical_package:
        raise ExplorerSpecificationError("publication package is not the canonical E2-derived package")
    if report.claims != model.claims:
        raise ExplorerSpecificationError("report claims differ from the presentation model")
    try:
        canonical_markdown = render_formal_report_markdown(report, model, package)
    except (TypeError, ValueError) as exc:
        raise ExplorerSpecificationError(f"report is not a verified canonical report: {exc}") from exc
    if report_markdown != canonical_markdown:
        raise ExplorerSpecificationError("report Markdown is not the canonical E2/E3-derived output")
    if len(model.primary) != 20 or tuple(record.point_rank for record in model.primary) != tuple(range(1, 21)):
        raise ExplorerSpecificationError("Primary view must contain ranks 1..20")
    if tuple(result.analysis_label for result in model.robustness) != _EXPECTED_ANALYSES:
        raise ExplorerSpecificationError("explorer analyses do not match the closed-world frozen set")
    if len(package.primary_table) != 20 or len(package.robustness_table) != 180 or len(package.heterogeneity_table) != 20:
        raise ExplorerSpecificationError("publication package row counts are not canonical")


def build_formal_explorer(
    model: FormalPresentationModel,
    package: FormalPublicationPackage,
    report: FormalReport,
    report_markdown: str,
) -> FormalExplorerModel:
    """Build a deterministic explorer state from already-built Phase 3 objects."""
    _validate_inputs(model, package, report, report_markdown)
    primary_rows = package.primary_table
    robustness_rows = package.robustness_table
    heterogeneity_rows = package.heterogeneity_table
    primary_top_three = tuple((row.model_id, row.point_rank) for row in primary_rows[:3])
    primary_run_ids = tuple(result.run_id for result in model.robustness if result.analysis_label == "Primary")
    if len(primary_run_ids) != 1:
        raise ExplorerSpecificationError("presentation model must contain exactly one Primary run identity")
    score_spec = package.primary_figure
    rank_spec = package.rank_uncertainty_figure
    robustness_spec = package.robustness_figure
    heterogeneity_spec = package.heterogeneity_figure
    return FormalExplorerModel(
        overview=ExplorerOverview(
            historical_population_warning=_HISTORICAL_WARNING,
            research_question=_RESEARCH_QUESTION,
            model_count=20,
            frozen_analysis_count=9,
            primary_top_three=primary_top_three,
            claim_boundary=_CLAIM_BOUNDARY,
        ),
        primary=ExplorerPrimaryView(
            rows=primary_rows,
            score_figure=ExplorerFigureReference(score_spec.filename, score_spec.title, score_spec.caption),
            rank_figure=ExplorerFigureReference(rank_spec.filename, rank_spec.title, rank_spec.caption),
        ),
        robustness=ExplorerRobustnessView(
            analyses=_EXPECTED_ANALYSES,
            rows=robustness_rows,
            s1_s2_boundary="S1 and S2 are rank evidence only; latent scores are not comparable with Primary.",
            figure=ExplorerFigureReference(robustness_spec.filename, robustness_spec.title, robustness_spec.caption),
        ),
        heterogeneity=ExplorerHeterogeneityView(
            rows=heterogeneity_rows,
            classification=model.heterogeneity.classification,
            causal_interpretation=model.heterogeneity.causal_interpretation,
            top4_set_preserved=model.heterogeneity.top4_set_preserved,
            top4_order_preserved=model.heterogeneity.top4_order_preserved,
            figure=ExplorerFigureReference(heterogeneity_spec.filename, heterogeneity_spec.title, heterogeneity_spec.caption),
        ),
        provenance=ExplorerProvenanceView(
            rows=package.provenance_table + (
                ProvenanceTableRow("primary_formal_run_id", primary_run_ids[0]),
                ProvenanceTableRow("formal_evidence_status", "verified frozen Phase 2 evidence"),
            ),
            formal_evidence_status="verified frozen Phase 2 evidence",
            historical_source_warning=_HISTORICAL_WARNING,
        ),
        report_markdown=report_markdown,
    )


def select_primary_rows(
    explorer: FormalExplorerModel,
    *,
    top_n: int | None = None,
    model_id: str | None = None,
) -> tuple[PrimaryTableRow, ...]:
    """Return a display-only Primary subset without changing canonical order or values."""
    if not isinstance(explorer, FormalExplorerModel):
        raise TypeError("select_primary_rows expects FormalExplorerModel")
    if top_n is not None and (isinstance(top_n, bool) or not isinstance(top_n, int) or not 1 <= top_n <= 20):
        raise ExplorerSpecificationError("top_n must be an integer between 1 and 20")
    if model_id is not None and not isinstance(model_id, str):
        raise ExplorerSpecificationError("model_id must be a string")
    if model_id is not None and model_id not in {row.model_id for row in explorer.primary.rows}:
        raise ExplorerSpecificationError("model_id is not in the frozen explorer model set")
    rows = explorer.primary.rows
    if top_n is not None:
        rows = rows[:top_n]
    if model_id is not None:
        rows = tuple(row for row in rows if row.model_id == model_id)
    return rows


def select_robustness_rows(
    explorer: FormalExplorerModel,
    *,
    analysis_label: str | None = None,
    model_id: str | None = None,
) -> tuple[RobustnessTableRow, ...]:
    """Select accepted frozen analysis/model rows; no estimator or metric selection exists."""
    if not isinstance(explorer, FormalExplorerModel):
        raise TypeError("select_robustness_rows expects FormalExplorerModel")
    if analysis_label is not None and analysis_label not in explorer.robustness.analyses:
        raise ExplorerSpecificationError("analysis_label is not in the frozen explorer set")
    if model_id is not None and not isinstance(model_id, str):
        raise ExplorerSpecificationError("model_id must be a string")
    if model_id is not None and model_id not in {row.model_id for row in explorer.primary.rows}:
        raise ExplorerSpecificationError("model_id is not in the frozen explorer model set")
    return tuple(
        row for row in explorer.robustness.rows
        if (analysis_label is None or row.analysis_label == analysis_label)
        and (model_id is None or row.model_id == model_id)
    )


__all__ = [
    "ExplorerFigureReference", "ExplorerHeterogeneityView", "ExplorerOverview", "ExplorerPrimaryView", "ExplorerProvenanceView",
    "ExplorerRobustnessView", "ExplorerSpecificationError", "FormalExplorerModel",
    "build_formal_explorer", "select_primary_rows", "select_robustness_rows",
]
