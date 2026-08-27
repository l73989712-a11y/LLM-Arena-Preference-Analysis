"""Claim-bounded, deterministic Markdown reporting from E2 and E3 inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from src.formal_figures import (
    FormalPublicationPackage,
    HeterogeneityTableRow,
    PrimaryTableRow,
    ProvenanceTableRow,
    RobustnessTableRow,
)
from src.formal_presentation import ClaimMetadata, FormalPresentationModel


class ReportSpecificationError(ValueError):
    """Raised when E2/E3 inputs cannot support the frozen report contract."""


ReportCell: TypeAlias = str | int | float | bool

_SECTION_LAYOUT = (
    ("overview", "1. Overview"),
    ("research-question", "2. Research Question"),
    ("data-population", "3. Data & Frozen Population"),
    ("method", "4. Method"),
    ("primary-result", "5. Primary Result"),
    ("uncertainty", "6. Uncertainty"),
    ("robustness", "7. Robustness"),
    ("heterogeneity", "8. Heterogeneity"),
    ("limitations", "9. Limitations"),
    ("methods-provenance", "10. Methods & Provenance"),
)
_ROBUSTNESS_LABELS = ("Primary", "S1", "S2", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50")
_FIGURE_REFERENCES = (
    ("formal_primary_preference.png", "Estimated Historical Arena Preference"),
    ("formal_rank_uncertainty.png", "Historical Arena Rank Uncertainty"),
    ("formal_robustness_ranks.png", "Rank Displacement Across Frozen Analyses"),
    ("formal_s6_heterogeneity.png", "English-Subgroup Rank Heterogeneity"),
)
_PRIMARY_TABLE_TITLE = "Primary estimated historical Arena preference and frozen uncertainty"
_PRIMARY_COLUMNS = (
    "Point rank", "Model", "Point score", "Score CI low", "Score CI high", "Rank median",
    "Rank CI low", "Rank CI high", "P(rank=1)",
)
_ROBUSTNESS_TABLE_TITLE = "Frozen rank comparison across accepted analyses"
_ROBUSTNESS_COLUMNS = ("Analysis", "Primary rank", "Model", "Point rank", "Rank delta vs Primary")
_HETEROGENEITY_TABLE_TITLE = "Primary and English-subgroup rank movement"
_HETEROGENEITY_COLUMNS = ("Primary rank", "Model", "English rank", "Rank delta")
_PROVENANCE_TABLE_TITLE = "Frozen source and formal analysis provenance"
_PROVENANCE_COLUMNS = ("Field", "Value")
_PROVENANCE_FIELDS = (
    "evidence_class", "source_dataset", "source_revision", "source_snapshot_id", "source_file_sha256",
    "primary_formal_run_id", "historical_population", "current_leaderboard", "capability_claim",
    "causal_claim", "external_generalization",
)
_FORBIDDEN_PHRASES = (
    "current leaderboard",
    "objective capability",
    "causes better performance",
    "universally preferred",
    "best model",
)


@dataclass(frozen=True)
class ReportTable:
    table_id: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[ReportCell, ...], ...]


@dataclass(frozen=True)
class ReportFigureReference:
    filename: str
    title: str


@dataclass(frozen=True)
class ReportSection:
    section_id: str
    heading: str
    paragraphs: tuple[str, ...]
    tables: tuple[ReportTable, ...] = ()
    figures: tuple[ReportFigureReference, ...] = ()


@dataclass(frozen=True)
class FormalReport:
    """Immutable report specification rendered without filesystem access."""

    title: str
    claims: ClaimMetadata
    sections: tuple[ReportSection, ...]


def _validate_claims(claims: ClaimMetadata) -> None:
    if (
        claims.evidence_class != "E2_presentation_derivative"
        or claims.historical_population is not True
        or claims.current_leaderboard is not False
        or claims.capability_claim is not False
        or claims.causal_claim is not False
        or claims.external_generalization is not False
    ):
        raise ReportSpecificationError("claim metadata does not permit formal research reporting")


def _primary_rows(model: FormalPresentationModel) -> tuple[PrimaryTableRow, ...]:
    return tuple(
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


def _robustness_rows(model: FormalPresentationModel) -> tuple[RobustnessTableRow, ...]:
    rows: list[RobustnessTableRow] = []
    for result in model.robustness:
        rows.extend(
            RobustnessTableRow(
                result.analysis_label,
                primary_rank,
                record.model_id,
                record.point_rank,
                record.rank_delta_vs_primary,
            )
            for primary_rank, record in enumerate(result.records, start=1)
        )
    return tuple(rows)


def _heterogeneity_rows(model: FormalPresentationModel) -> tuple[HeterogeneityTableRow, ...]:
    return tuple(
        HeterogeneityTableRow(
            record.primary_rank,
            record.model_id,
            record.english_rank,
            record.rank_delta,
        )
        for record in model.heterogeneity.records
    )


def _provenance_rows(model: FormalPresentationModel) -> tuple[ProvenanceTableRow, ...]:
    primary_run = next((result for result in model.robustness if result.analysis_label == "Primary"), None)
    if primary_run is None:
        raise ReportSpecificationError("presentation model is missing the Primary formal analysis identity")
    claims = model.claims
    return (
        ProvenanceTableRow("evidence_class", claims.evidence_class),
        ProvenanceTableRow("source_dataset", model.source_dataset),
        ProvenanceTableRow("source_revision", model.source_revision),
        ProvenanceTableRow("source_snapshot_id", model.source_snapshot_id),
        ProvenanceTableRow("source_file_sha256", model.source_file_sha256),
        ProvenanceTableRow("primary_formal_run_id", primary_run.run_id),
        ProvenanceTableRow("historical_population", str(claims.historical_population).lower()),
        ProvenanceTableRow("current_leaderboard", str(claims.current_leaderboard).lower()),
        ProvenanceTableRow("capability_claim", str(claims.capability_claim).lower()),
        ProvenanceTableRow("causal_claim", str(claims.causal_claim).lower()),
        ProvenanceTableRow("external_generalization", str(claims.external_generalization).lower()),
    )


def _validate_package(model: FormalPresentationModel, package: FormalPublicationPackage) -> None:
    expected_primary = _primary_rows(model)
    expected_robustness = _robustness_rows(model)
    expected_heterogeneity = _heterogeneity_rows(model)
    expected_provenance = _provenance_rows(model)
    if (
        package.primary_table != expected_primary
        or package.primary_figure.rows != expected_primary
        or package.rank_uncertainty_figure.rows != expected_primary
    ):
        raise ReportSpecificationError("publication package Primary values do not trace to E2")
    if package.robustness_table != expected_robustness or package.robustness_figure.rows != expected_robustness:
        raise ReportSpecificationError("publication package robustness values do not trace to E2")
    if package.heterogeneity_table != expected_heterogeneity or package.heterogeneity_figure.rows != expected_heterogeneity:
        raise ReportSpecificationError("publication package heterogeneity values do not trace to E2")
    if package.provenance_table != tuple(row for row in expected_provenance if row.field != "primary_formal_run_id"):
        raise ReportSpecificationError("publication package provenance does not trace to E2")
    figures = (
        package.primary_figure,
        package.rank_uncertainty_figure,
        package.robustness_figure,
        package.heterogeneity_figure,
    )
    if tuple((figure.filename, figure.title) for figure in figures) != _FIGURE_REFERENCES:
        raise ReportSpecificationError("publication package figure references are not canonical")
    if any(figure.claims != model.claims for figure in figures):
        raise ReportSpecificationError("publication package claim metadata differs from E2")
    if (
        package.heterogeneity_figure.classification != model.heterogeneity.classification
        or package.heterogeneity_figure.causal_interpretation != model.heterogeneity.causal_interpretation
    ):
        raise ReportSpecificationError("publication package S6 boundary differs from E2")


def _primary_table(rows: tuple[PrimaryTableRow, ...]) -> ReportTable:
    return ReportTable(
        "primary-results",
        _PRIMARY_TABLE_TITLE,
        _PRIMARY_COLUMNS,
        tuple(
            (
                row.point_rank,
                row.model_id,
                row.point_score,
                row.score_ci_low,
                row.score_ci_high,
                row.rank_median,
                row.rank_ci_low,
                row.rank_ci_high,
                row.probability_rank_1,
            )
            for row in rows
        ),
    )


def _robustness_table(rows: tuple[RobustnessTableRow, ...]) -> ReportTable:
    return ReportTable(
        "robustness-ranks",
        _ROBUSTNESS_TABLE_TITLE,
        _ROBUSTNESS_COLUMNS,
        tuple(
            (row.analysis_label, row.primary_rank, row.model_id, row.point_rank, row.rank_delta_vs_primary)
            for row in rows
        ),
    )


def _heterogeneity_table(rows: tuple[HeterogeneityTableRow, ...]) -> ReportTable:
    return ReportTable(
        "english-subgroup-ranks",
        _HETEROGENEITY_TABLE_TITLE,
        _HETEROGENEITY_COLUMNS,
        tuple((row.primary_rank, row.model_id, row.english_rank, row.rank_delta) for row in rows),
    )


def _provenance_table(rows: tuple[ProvenanceTableRow, ...]) -> ReportTable:
    return ReportTable(
        "provenance",
        _PROVENANCE_TABLE_TITLE,
        _PROVENANCE_COLUMNS,
        tuple((row.field, row.value) for row in rows),
    )


def _figure_references() -> tuple[ReportFigureReference, ...]:
    return tuple(ReportFigureReference(filename, title) for filename, title in _FIGURE_REFERENCES)


def _validate_presentation_semantics(model: FormalPresentationModel) -> None:
    if len(model.primary) != 20 or tuple(record.point_rank for record in model.primary) != tuple(range(1, 21)):
        raise ReportSpecificationError("Primary presentation records must be exactly rank ordered 1..20")
    if tuple(result.analysis_label for result in model.robustness) != _ROBUSTNESS_LABELS + ("S6-English",):
        raise ReportSpecificationError("robustness analyses do not match the frozen report contract")
    if any(
        record.rank_delta_vs_primary != 0
        for result in model.robustness
        if result.analysis_label in _ROBUSTNESS_LABELS
        for record in result.records
    ):
        raise ReportSpecificationError("frozen Primary through S5 rank ordering is not preserved")
    heterogeneity = model.heterogeneity
    if (
        heterogeneity.analysis_label != "S6-English"
        or not isinstance(heterogeneity.classification, str)
        or heterogeneity.classification.casefold() != "partially robust / heterogeneous"
        or heterogeneity.causal_interpretation != "NOT SUPPORTED"
        or heterogeneity.top4_set_preserved is not True
        or heterogeneity.top4_order_preserved is not True
    ):
        raise ReportSpecificationError("S6 heterogeneity semantics do not match the frozen report contract")
    if tuple(record.primary_rank for record in heterogeneity.records) != tuple(range(1, 21)):
        raise ReportSpecificationError("S6 heterogeneity records must be ordered by Primary rank")


def _validate_report_tables(
    primary: ReportTable,
    robustness: ReportTable,
    heterogeneity: ReportTable,
    provenance: ReportTable,
) -> None:
    if (
        (primary.table_id, primary.title, primary.columns) != ("primary-results", _PRIMARY_TABLE_TITLE, _PRIMARY_COLUMNS)
        or len(primary.rows) != 20
        or tuple(row[0] for row in primary.rows) != tuple(range(1, 21))
        or any(len(row) != len(_PRIMARY_COLUMNS) or not isinstance(row[1], str) for row in primary.rows)
    ):
        raise ReportSpecificationError("Primary report table is not canonical")
    if (
        (robustness.table_id, robustness.title, robustness.columns)
        != ("robustness-ranks", _ROBUSTNESS_TABLE_TITLE, _ROBUSTNESS_COLUMNS)
        or len(robustness.rows) != 9 * 20
        or any(len(row) != len(_ROBUSTNESS_COLUMNS) for row in robustness.rows)
    ):
        raise ReportSpecificationError("robustness report table is not canonical")
    for index, analysis_label in enumerate(_ROBUSTNESS_LABELS + ("S6-English",)):
        rows = robustness.rows[index * 20:(index + 1) * 20]
        if (
            tuple(row[0] for row in rows) != (analysis_label,) * 20
            or tuple(row[1] for row in rows) != tuple(range(1, 21))
        ):
            raise ReportSpecificationError("robustness report table is not ordered by frozen analysis and Primary rank")
    if (
        (heterogeneity.table_id, heterogeneity.title, heterogeneity.columns)
        != ("english-subgroup-ranks", _HETEROGENEITY_TABLE_TITLE, _HETEROGENEITY_COLUMNS)
        or len(heterogeneity.rows) != 20
        or tuple(row[0] for row in heterogeneity.rows) != tuple(range(1, 21))
        or any(
            len(row) != len(_HETEROGENEITY_COLUMNS)
            or not isinstance(row[1], str)
            or isinstance(row[3], bool)
            or not isinstance(row[3], int)
            for row in heterogeneity.rows
        )
    ):
        raise ReportSpecificationError("S6 heterogeneity report table is not canonical")
    if (
        (provenance.table_id, provenance.title, provenance.columns)
        != ("provenance", _PROVENANCE_TABLE_TITLE, _PROVENANCE_COLUMNS)
        or tuple(row[0] for row in provenance.rows) != _PROVENANCE_FIELDS
        or any(len(row) != 2 or not isinstance(row[1], str) for row in provenance.rows)
    ):
        raise ReportSpecificationError("provenance report table is not canonical")


def _canonical_sections(
    primary: ReportTable,
    robustness: ReportTable,
    heterogeneity: ReportTable,
    provenance: ReportTable,
) -> tuple[ReportSection, ...]:
    _validate_report_tables(primary, robustness, heterogeneity, provenance)
    provenance_values = dict(provenance.rows)
    primary_top_three = ", ".join(
        f"{row[1]} (point rank {row[0]})" for row in primary.rows[:3]
    )
    max_displacement = max(abs(row[3]) for row in heterogeneity.rows)
    return (
        ReportSection(
            *_SECTION_LAYOUT[0],
            (
                "This report is a reproducible, claim-bounded presentation of frozen formal evidence "
                "from a historical Arena population. It describes estimated preference in that population "
                "while preserving uncertainty, provenance, and interpretation boundaries.",
            ),
        ),
        ReportSection(
            *_SECTION_LAYOUT[1],
            (
                "Within the frozen historical Arena population, how are model preferences estimated, "
                "with what frozen uncertainty, and how do point-rank records compare across the accepted analyses?",
            ),
        ),
        ReportSection(
            *_SECTION_LAYOUT[2],
            (
                f"The frozen source is {provenance_values['source_dataset']} at revision {provenance_values['source_revision']}. "
                "The research object is the specified historical population, not a description of systems "
                "available at the time this report is read.",
            ),
        ),
        ReportSection(
            *_SECTION_LAYOUT[3],
            (
                "The report consumes the immutable E2 presentation model and E3 publication package. "
                "It does not fit an estimator, resample observations, or calculate new confidence intervals.",
            ),
        ),
        ReportSection(
            *_SECTION_LAYOUT[4],
            (
                f"The first three Primary point ranks are {primary_top_three}. "
                "These are estimated historical Arena preference ranks, not a prescription for present-day use.",
            ),
            (primary,),
            (_figure_references()[0],),
        ),
        ReportSection(
            *_SECTION_LAYOUT[5],
            (
                "Point rank does not imply certainty. Frozen 95% score intervals, frozen 95% rank intervals, "
                "and frozen rank-1 probabilities are retained in the Primary table rather than recalculated here.",
            ),
            figures=(_figure_references()[1],),
        ),
        ReportSection(
            *_SECTION_LAYOUT[6],
            (
                "Across Primary and S1 through S5-ge50, the frozen point-rank ordering is preserved. "
                "S1 and S2 contribute rank evidence only; latent score values are not compared across estimator parameterizations. "
                "Frozen rank intervals are reported without deriving a new local-ordering classification in this report.",
            ),
            (robustness,),
            (_figure_references()[2],),
        ),
        ReportSection(
            *_SECTION_LAYOUT[7],
            (
                "The English subgroup is classified as PARTIALLY ROBUST / HETEROGENEOUS. "
                "The frozen review preserves the top-four set and top-four order. "
                f"The largest displayed absolute rank displacement is {max_displacement}. "
                "Causal interpretation: NOT SUPPORTED.",
            ),
            (heterogeneity,),
            (_figure_references()[3],),
        ),
        ReportSection(
            *_SECTION_LAYOUT[8],
            (
                "The evidence concerns one frozen historical population and frozen formal analyses. "
                "It does not establish causal mechanisms, generalize beyond that population, or evaluate present-day systems.",
            ),
        ),
        ReportSection(
            *_SECTION_LAYOUT[9],
            (
                "The provenance table records the frozen dataset identity, source snapshot, source file digest, "
                "Primary formal analysis identity, and claim metadata carried into this report.",
            ),
            (provenance,),
        ),
    )


def build_formal_report(model: FormalPresentationModel, package: FormalPublicationPackage) -> FormalReport:
    """Build an immutable, claim-bounded report specification from E2 and E3 only."""
    if not isinstance(model, FormalPresentationModel):
        raise TypeError("build_formal_report expects FormalPresentationModel")
    if not isinstance(package, FormalPublicationPackage):
        raise TypeError("build_formal_report expects FormalPublicationPackage")
    _validate_claims(model.claims)
    _validate_presentation_semantics(model)
    _validate_package(model, package)
    sections = _canonical_sections(
        _primary_table(package.primary_table),
        _robustness_table(package.robustness_table),
        _heterogeneity_table(package.heterogeneity_table),
        _provenance_table(_provenance_rows(model)),
    )
    return FormalReport("Frozen Historical Arena Preference Report", model.claims, sections)


def _format_cell(value: ReportCell) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _markdown_table(table: ReportTable) -> tuple[str, ...]:
    header = "| " + " | ".join(table.columns) + " |"
    divider = "| " + " | ".join("---" for _ in table.columns) + " |"
    rows = tuple(
        "| " + " | ".join(_format_cell(value).replace("|", "\\|") for value in row) + " |"
        for row in table.rows
    )
    return (f"### {table.title}", "", header, divider, *rows)


def _validate_renderable_report(
    report: FormalReport,
    model: FormalPresentationModel,
    package: FormalPublicationPackage,
) -> None:
    expected = build_formal_report(model, package)
    if report != expected:
        raise ReportSpecificationError("report does not match the canonical E2/E3-derived specification")
    _validate_claims(report.claims)
    if report.title != "Frozen Historical Arena Preference Report":
        raise ReportSpecificationError("report title is not canonical")
    if tuple((section.section_id, section.heading) for section in report.sections) != _SECTION_LAYOUT:
        raise ReportSpecificationError("report sections do not match the frozen report contract")
    table_counts = (0, 0, 0, 0, 1, 0, 1, 1, 0, 1)
    figure_counts = (0, 0, 0, 0, 1, 1, 1, 1, 0, 0)
    if (
        tuple(len(section.tables) for section in report.sections) != table_counts
        or tuple(len(section.figures) for section in report.sections) != figure_counts
    ):
        raise ReportSpecificationError("report table or figure layout is not canonical")
    primary = report.sections[4].tables[0]
    robustness = report.sections[6].tables[0]
    heterogeneity = report.sections[7].tables[0]
    provenance = report.sections[9].tables[0]
    text = " ".join(
        [report.title]
        + [section.heading for section in report.sections]
        + [paragraph for section in report.sections for paragraph in section.paragraphs]
        + [figure.title for section in report.sections for figure in section.figures]
        + [str(value) for section in report.sections for table in section.tables for row in table.rows for value in row]
    ).lower()
    if any(phrase in text for phrase in _FORBIDDEN_PHRASES):
        raise ReportSpecificationError("report text contains a forbidden claim")


def render_formal_report_markdown(
    report: FormalReport,
    model: FormalPresentationModel,
    package: FormalPublicationPackage,
) -> str:
    """Render a report specification deterministically to an in-memory Markdown string."""
    if not isinstance(report, FormalReport):
        raise TypeError("render_formal_report_markdown expects FormalReport")
    if not isinstance(model, FormalPresentationModel):
        raise TypeError("render_formal_report_markdown expects FormalPresentationModel")
    if not isinstance(package, FormalPublicationPackage):
        raise TypeError("render_formal_report_markdown expects FormalPublicationPackage")
    _validate_renderable_report(report, model, package)
    lines = [f"# {report.title}"]
    for section in report.sections:
        lines.extend(("", f"## {section.heading}", ""))
        for paragraph in section.paragraphs:
            lines.extend((paragraph, ""))
        for figure in section.figures:
            lines.extend((f"Figure reference: `{figure.filename}` - {figure.title}", ""))
        for table in section.tables:
            lines.extend(_markdown_table(table))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "FormalReport", "ReportFigureReference", "ReportSection", "ReportSpecificationError", "ReportTable",
    "build_formal_report", "render_formal_report_markdown",
]
