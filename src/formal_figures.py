"""Claim-bounded figures and tables rendered only from the E2 presentation model."""

from __future__ import annotations

from dataclasses import dataclass

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

from src.formal_presentation import ClaimMetadata, FormalPresentationModel


class FigureSpecificationError(ValueError):
    """Raised when an E2 presentation model cannot be rendered safely."""


_ANALYSES = ("Primary", "S1", "S2", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50", "S6-English")
_BOUNDARY_CAPTION = (
    "Historical Arena preference evidence with frozen uncertainty summaries; "
    "not a current leaderboard, capability ranking, causal claim, or external generalization."
)
_S6_CLASSIFICATION = "partially robust / heterogeneous"
_S6_CAUSAL_INTERPRETATION = "NOT SUPPORTED"


@dataclass(frozen=True)
class PrimaryTableRow:
    point_rank: int
    model_id: str
    point_score: float
    score_ci_low: float
    score_ci_high: float
    rank_median: float
    rank_ci_low: float
    rank_ci_high: float
    probability_rank_1: float


@dataclass(frozen=True)
class RobustnessTableRow:
    analysis_label: str
    primary_rank: int
    model_id: str
    point_rank: int
    rank_delta_vs_primary: int


@dataclass(frozen=True)
class HeterogeneityTableRow:
    primary_rank: int
    model_id: str
    english_rank: int
    rank_delta: int


@dataclass(frozen=True)
class ProvenanceTableRow:
    field: str
    value: str


@dataclass(frozen=True)
class PrimaryFigureSpec:
    filename: str
    title: str
    caption: str
    claims: ClaimMetadata
    rows: tuple[PrimaryTableRow, ...]


@dataclass(frozen=True)
class RankUncertaintyFigureSpec:
    filename: str
    title: str
    caption: str
    claims: ClaimMetadata
    rows: tuple[PrimaryTableRow, ...]


@dataclass(frozen=True)
class RobustnessFigureSpec:
    filename: str
    title: str
    caption: str
    claims: ClaimMetadata
    analysis_labels: tuple[str, ...]
    rows: tuple[RobustnessTableRow, ...]


@dataclass(frozen=True)
class HeterogeneityFigureSpec:
    filename: str
    title: str
    caption: str
    claims: ClaimMetadata
    classification: str
    causal_interpretation: str
    rows: tuple[HeterogeneityTableRow, ...]


@dataclass(frozen=True)
class FormalPublicationPackage:
    """Deterministic E3 specifications and table records; no files are written."""

    primary_figure: PrimaryFigureSpec
    rank_uncertainty_figure: RankUncertaintyFigureSpec
    robustness_figure: RobustnessFigureSpec
    heterogeneity_figure: HeterogeneityFigureSpec
    primary_table: tuple[PrimaryTableRow, ...]
    robustness_table: tuple[RobustnessTableRow, ...]
    heterogeneity_table: tuple[HeterogeneityTableRow, ...]
    provenance_table: tuple[ProvenanceTableRow, ...]


def _validate_claims(claims: ClaimMetadata) -> None:
    if (
        claims.evidence_class != "E2_presentation_derivative"
        or claims.historical_population is not True
        or claims.current_leaderboard is not False
        or claims.capability_claim is not False
        or claims.causal_claim is not False
        or claims.external_generalization is not False
    ):
        raise FigureSpecificationError("claim metadata does not permit formal public-facing rendering")


def _primary_metadata() -> tuple[str, str, str]:
    return (
        "formal_primary_preference.png",
        "Estimated Historical Arena Preference",
        "Frozen 95% score intervals for the historical Arena preference population. " + _BOUNDARY_CAPTION,
    )


def _rank_uncertainty_metadata() -> tuple[str, str, str]:
    return (
        "formal_rank_uncertainty.png",
        "Historical Arena Rank Uncertainty",
        "Frozen 95% rank intervals; point rank does not imply certainty. "
        "Rank-1 probability is retained in the machine-readable primary table. " + _BOUNDARY_CAPTION,
    )


def _robustness_metadata() -> tuple[str, str, str]:
    return (
        "formal_robustness_ranks.png",
        "Rank Displacement Across Frozen Analyses",
        "Rank displacement versus Primary across the nine frozen analyses; "
        "no cross-estimator score comparison. " + _BOUNDARY_CAPTION,
    )


def _validate_s6_semantics(classification: object, causal_interpretation: object) -> None:
    if (
        not isinstance(classification, str)
        or not classification.strip()
        or classification.casefold() != _S6_CLASSIFICATION
        or not isinstance(causal_interpretation, str)
        or causal_interpretation != _S6_CAUSAL_INTERPRETATION
    ):
        raise FigureSpecificationError("S6 heterogeneity classification or causal boundary is invalid")


def _heterogeneity_metadata(classification: object, causal_interpretation: object) -> tuple[str, str, str]:
    _validate_s6_semantics(classification, causal_interpretation)
    return (
        "formal_s6_heterogeneity.png",
        "English-Subgroup Rank Heterogeneity",
        "Primary and English-subgroup rank displacement. "
        f"{classification.upper()}; causal interpretation: {causal_interpretation}. " + _BOUNDARY_CAPTION,
    )


def _validate_canonical_text(
    filename: str,
    title: str,
    caption: str,
    expected: tuple[str, str, str],
) -> None:
    if (filename, title, caption) != expected:
        raise FigureSpecificationError("public figure specification text or filename is not canonical")


def _validate_primary_table_rows(rows: tuple[PrimaryTableRow, ...]) -> None:
    if len(rows) != 20 or tuple(row.point_rank for row in rows) != tuple(range(1, 21)):
        raise FigureSpecificationError("primary figure rows must be exactly rank ordered 1..20")
    if len({row.model_id for row in rows}) != len(rows):
        raise FigureSpecificationError("primary figure model IDs are not unique")


def _validate_robustness_table_rows(
    rows: tuple[RobustnessTableRow, ...],
    analysis_labels: tuple[str, ...],
) -> None:
    if analysis_labels != _ANALYSES or len(rows) != len(_ANALYSES) * 20:
        raise FigureSpecificationError("robustness figure rows do not match the frozen analysis contract")
    primary_ids: tuple[str, ...] | None = None
    for analysis_index, analysis_label in enumerate(_ANALYSES):
        analysis_rows = rows[analysis_index * 20:(analysis_index + 1) * 20]
        if (
            tuple(row.analysis_label for row in analysis_rows) != (analysis_label,) * 20
            or tuple(row.primary_rank for row in analysis_rows) != tuple(range(1, 21))
        ):
            raise FigureSpecificationError("robustness figure rows are not ordered by frozen analysis and Primary rank")
        model_ids = tuple(row.model_id for row in analysis_rows)
        if primary_ids is None:
            primary_ids = model_ids
        elif model_ids != primary_ids:
            raise FigureSpecificationError("robustness figure rows are not aligned to Primary rank order")


def _validate_heterogeneity_table_rows(rows: tuple[HeterogeneityTableRow, ...]) -> None:
    if len(rows) != 20 or tuple(row.primary_rank for row in rows) != tuple(range(1, 21)):
        raise FigureSpecificationError("S6 heterogeneity figure rows must be exactly Primary rank ordered 1..20")
    if len({row.model_id for row in rows}) != len(rows):
        raise FigureSpecificationError("S6 heterogeneity figure model IDs are not unique")


def _primary_rows(model: FormalPresentationModel) -> tuple[PrimaryTableRow, ...]:
    if len(model.primary) != 20 or tuple(record.point_rank for record in model.primary) != tuple(range(1, 21)):
        raise FigureSpecificationError("primary presentation records must be exactly rank ordered 1..20")
    rows = tuple(
        PrimaryTableRow(
            record.point_rank,
            record.model_id,
            record.point_score,
            record.score_ci_low,
            record.score_ci_high,
            record.rank_median,
            record.rank_ci_low,
            record.rank_ci_high,
            record.probability_rank_1,
        )
        for record in model.primary
    )
    _validate_primary_table_rows(rows)
    return rows


def _robustness_rows(model: FormalPresentationModel, primary_rows: tuple[PrimaryTableRow, ...]) -> tuple[RobustnessTableRow, ...]:
    if tuple(result.analysis_label for result in model.robustness) != _ANALYSES:
        raise FigureSpecificationError("robustness analyses do not match the frozen presentation contract")
    primary_ids = tuple(row.model_id for row in primary_rows)
    rows: list[RobustnessTableRow] = []
    for result in model.robustness:
        if result.analysis_label in {"S1", "S2"} and result.score_comparability != "latent_scores_not_comparable_with_primary":
            raise FigureSpecificationError(f"{result.analysis_label} score comparability boundary is missing")
        if tuple(record.model_id for record in result.records) != primary_ids:
            raise FigureSpecificationError(f"{result.analysis_label} records are not aligned to Primary rank order")
        rows.extend(
            RobustnessTableRow(result.analysis_label, index, record.model_id, record.point_rank, record.rank_delta_vs_primary)
            for index, record in enumerate(result.records, start=1)
        )
    return tuple(rows)


def _heterogeneity_rows(model: FormalPresentationModel, primary_rows: tuple[PrimaryTableRow, ...]) -> tuple[HeterogeneityTableRow, ...]:
    heterogeneity = model.heterogeneity
    if heterogeneity.analysis_label != "S6-English":
        raise FigureSpecificationError("S6 heterogeneity causal boundary is missing")
    _validate_s6_semantics(heterogeneity.classification, heterogeneity.causal_interpretation)
    if (
        not isinstance(model.review_facts.heterogeneity_classification, str)
        or heterogeneity.classification.casefold() != model.review_facts.heterogeneity_classification.casefold()
        or heterogeneity.top4_set_preserved is not model.review_facts.top4_set_preserved
        or heterogeneity.top4_order_preserved is not model.review_facts.top4_order_preserved
    ):
        raise FigureSpecificationError("S6 heterogeneity facts are inconsistent with the frozen review")
    primary_ids = tuple(row.model_id for row in primary_rows)
    if tuple(record.model_id for record in heterogeneity.records) != primary_ids:
        raise FigureSpecificationError("S6 heterogeneity records are not aligned to Primary rank order")
    rows = tuple(
        HeterogeneityTableRow(record.primary_rank, record.model_id, record.english_rank, record.rank_delta)
        for record in heterogeneity.records
    )
    _validate_heterogeneity_table_rows(rows)
    return rows


def _provenance_rows(model: FormalPresentationModel) -> tuple[ProvenanceTableRow, ...]:
    claims = model.claims
    return (
        ProvenanceTableRow("evidence_class", claims.evidence_class),
        ProvenanceTableRow("source_dataset", model.source_dataset),
        ProvenanceTableRow("source_revision", model.source_revision),
        ProvenanceTableRow("source_snapshot_id", model.source_snapshot_id),
        ProvenanceTableRow("source_file_sha256", model.source_file_sha256),
        ProvenanceTableRow("historical_population", str(claims.historical_population).lower()),
        ProvenanceTableRow("current_leaderboard", str(claims.current_leaderboard).lower()),
        ProvenanceTableRow("capability_claim", str(claims.capability_claim).lower()),
        ProvenanceTableRow("causal_claim", str(claims.causal_claim).lower()),
        ProvenanceTableRow("external_generalization", str(claims.external_generalization).lower()),
    )


def build_formal_publication_package(model: FormalPresentationModel) -> FormalPublicationPackage:
    """Create deterministic figure specifications and tables from E2 only."""
    if not isinstance(model, FormalPresentationModel):
        raise TypeError("build_formal_publication_package expects FormalPresentationModel")
    _validate_claims(model.claims)
    primary_rows = _primary_rows(model)
    robustness_rows = _robustness_rows(model, primary_rows)
    heterogeneity_rows = _heterogeneity_rows(model, primary_rows)
    primary_metadata = _primary_metadata()
    rank_metadata = _rank_uncertainty_metadata()
    robustness_metadata = _robustness_metadata()
    heterogeneity_metadata = _heterogeneity_metadata(
        model.heterogeneity.classification,
        model.heterogeneity.causal_interpretation,
    )
    return FormalPublicationPackage(
        PrimaryFigureSpec(*primary_metadata, model.claims, primary_rows),
        RankUncertaintyFigureSpec(*rank_metadata, model.claims, primary_rows),
        RobustnessFigureSpec(*robustness_metadata, model.claims, _ANALYSES, robustness_rows),
        HeterogeneityFigureSpec(
            *heterogeneity_metadata,
            model.claims,
            model.heterogeneity.classification,
            model.heterogeneity.causal_interpretation,
            heterogeneity_rows,
        ),
        primary_rows,
        robustness_rows,
        heterogeneity_rows,
        _provenance_rows(model),
    )


def _validate_primary_spec(spec: PrimaryFigureSpec) -> None:
    _validate_claims(spec.claims)
    _validate_canonical_text(spec.filename, spec.title, spec.caption, _primary_metadata())
    _validate_primary_table_rows(spec.rows)


def _validate_rank_uncertainty_spec(spec: RankUncertaintyFigureSpec) -> None:
    _validate_claims(spec.claims)
    _validate_canonical_text(spec.filename, spec.title, spec.caption, _rank_uncertainty_metadata())
    _validate_primary_table_rows(spec.rows)


def _validate_robustness_spec(spec: RobustnessFigureSpec) -> None:
    _validate_claims(spec.claims)
    _validate_canonical_text(spec.filename, spec.title, spec.caption, _robustness_metadata())
    _validate_robustness_table_rows(spec.rows, spec.analysis_labels)


def _validate_heterogeneity_spec(spec: HeterogeneityFigureSpec) -> None:
    _validate_claims(spec.claims)
    _validate_canonical_text(
        spec.filename,
        spec.title,
        spec.caption,
        _heterogeneity_metadata(spec.classification, spec.causal_interpretation),
    )
    _validate_heterogeneity_table_rows(spec.rows)


def _figure_with_caption(title: str, caption: str, height: float) -> tuple[Figure, plt.Axes]:
    figure, axis = plt.subplots(figsize=(11, height), layout="constrained")
    figure.suptitle(title, fontsize=14, fontweight="bold")
    figure.text(0.5, 0.01, caption, ha="center", va="bottom", fontsize=8, wrap=True)
    return figure, axis


def render_primary_figure(spec: PrimaryFigureSpec) -> Figure:
    _validate_primary_spec(spec)
    positions = np.arange(len(spec.rows))
    scores = np.array([row.point_score for row in spec.rows])
    lows = np.array([row.score_ci_low for row in spec.rows])
    highs = np.array([row.score_ci_high for row in spec.rows])
    figure, axis = _figure_with_caption(spec.title, spec.caption, 8.0)
    axis.hlines(positions, lows, highs, color="#7895B2", linewidth=2, label="Frozen 95% score interval")
    axis.scatter(scores, positions, color="#176B87", label="Point estimate", zorder=2)
    axis.set_yticks(positions, [f"{row.point_rank}. {row.model_id}" for row in spec.rows])
    axis.invert_yaxis()
    axis.axvline(0, color="#A0A0A0", linewidth=0.8, zorder=0)
    axis.set_xlabel("Estimated preference score (frozen 95% interval)")
    axis.set_ylabel("Model, ordered by point rank")
    axis.grid(axis="x", alpha=0.25)
    axis.legend(loc="lower right")
    return figure


def render_rank_uncertainty_figure(spec: RankUncertaintyFigureSpec) -> Figure:
    _validate_rank_uncertainty_spec(spec)
    positions = np.arange(len(spec.rows))
    medians = np.array([row.rank_median for row in spec.rows])
    lows = np.array([row.rank_ci_low for row in spec.rows])
    highs = np.array([row.rank_ci_high for row in spec.rows])
    figure, axis = _figure_with_caption(spec.title, spec.caption, 8.0)
    axis.errorbar(medians, positions, xerr=np.vstack((medians - lows, highs - medians)), fmt="o", color="#B84A62", ecolor="#D7A6AE", capsize=3)
    axis.set_yticks(positions, [f"{row.point_rank}. {row.model_id}" for row in spec.rows])
    axis.set_xticks(range(1, len(spec.rows) + 1))
    axis.invert_xaxis()
    axis.invert_yaxis()
    axis.set_xlabel("Rank (1 = higher estimated historical preference)")
    axis.set_ylabel("Model, ordered by Primary point rank")
    axis.grid(axis="x", alpha=0.25)
    return figure


def render_robustness_figure(spec: RobustnessFigureSpec) -> Figure:
    _validate_robustness_spec(spec)
    model_ids = tuple(dict.fromkeys(row.model_id for row in spec.rows))
    deltas = np.array([[next(row.rank_delta_vs_primary for row in spec.rows if row.model_id == model_id and row.analysis_label == analysis) for analysis in spec.analysis_labels] for model_id in model_ids])
    figure, axis = _figure_with_caption(spec.title, spec.caption, 8.0)
    limit = max(1, int(np.abs(deltas).max()))
    image = axis.imshow(deltas, cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
    axis.set_xticks(range(len(spec.analysis_labels)), spec.analysis_labels, rotation=35, ha="right")
    axis.set_yticks(range(len(model_ids)), [f"{index}. {model_id}" for index, model_id in enumerate(model_ids, start=1)])
    axis.set_xlabel("Frozen analysis")
    axis.set_ylabel("Model, ordered by Primary point rank")
    colorbar = figure.colorbar(image, ax=axis, shrink=0.75)
    colorbar.set_label("Point-rank displacement versus Primary")
    return figure


def render_heterogeneity_figure(spec: HeterogeneityFigureSpec) -> Figure:
    _validate_heterogeneity_spec(spec)
    positions = np.arange(len(spec.rows))
    figure, axis = _figure_with_caption(spec.title, spec.caption, 8.0)
    for position, row in zip(positions, spec.rows):
        axis.plot((row.primary_rank, row.english_rank), (position, position), color="#8795A1", linewidth=1)
    axis.scatter([row.primary_rank for row in spec.rows], positions, color="#176B87", label="Primary", zorder=2)
    axis.scatter([row.english_rank for row in spec.rows], positions, color="#B84A62", marker="s", label="English subgroup", zorder=2)
    axis.set_yticks(positions, [f"{row.primary_rank}. {row.model_id}" for row in spec.rows])
    axis.set_xticks(range(1, len(spec.rows) + 1))
    axis.invert_xaxis()
    axis.invert_yaxis()
    axis.set_xlabel("Rank (1 = higher estimated historical preference)")
    axis.set_ylabel("Model, ordered by Primary point rank")
    axis.legend(loc="lower right")
    return figure


def render_all_formal_figures(package: FormalPublicationPackage) -> tuple[Figure, Figure, Figure, Figure]:
    """Render all publication figures in memory; callers own the returned figures."""
    return (
        render_primary_figure(package.primary_figure),
        render_rank_uncertainty_figure(package.rank_uncertainty_figure),
        render_robustness_figure(package.robustness_figure),
        render_heterogeneity_figure(package.heterogeneity_figure),
    )


__all__ = [
    "FigureSpecificationError", "FormalPublicationPackage", "HeterogeneityFigureSpec",
    "HeterogeneityTableRow", "PrimaryFigureSpec", "PrimaryTableRow", "ProvenanceTableRow",
    "RankUncertaintyFigureSpec", "RobustnessFigureSpec", "RobustnessTableRow",
    "build_formal_publication_package", "render_all_formal_figures", "render_heterogeneity_figure",
    "render_primary_figure", "render_rank_uncertainty_figure", "render_robustness_figure",
]
