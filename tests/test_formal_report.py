from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import inspect

import pytest

import src.formal_report as report_module
from src.formal_figures import FormalPublicationPackage, build_formal_publication_package
from src.formal_presentation import (
    ClaimMetadata,
    FormalModelResult,
    FormalPresentationModel,
    HeterogeneityRecord,
    HeterogeneityResult,
    ReviewFacts,
    RobustnessRecord,
    RobustnessResult,
)


MODEL_IDS = tuple(f"model-{rank:02d}" for rank in range(1, 21))
ANALYSES = ("Primary", "S1", "S2", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50", "S6-English")


def _model() -> FormalPresentationModel:
    primary = tuple(
        FormalModelResult(
            "Primary", model_id, rank, float(21 - rank), float(20.5 - rank), float(21.5 - rank),
            float(rank), float(max(1, rank - 1)), float(min(20, rank + 1)), 1.0 if rank == 1 else 0.0,
        )
        for rank, model_id in enumerate(MODEL_IDS, start=1)
    )
    robustness: list[RobustnessResult] = []
    for analysis in ANALYSES:
        ranks = {model_id: rank for rank, model_id in enumerate(MODEL_IDS, start=1)}
        if analysis == "S6-English":
            ranks[MODEL_IDS[4]], ranks[MODEL_IDS[5]] = 6, 5
        records = tuple(
            RobustnessRecord(analysis, model_id, ranks[model_id], ranks[model_id] - rank)
            for rank, model_id in enumerate(MODEL_IDS, start=1)
        )
        comparability = "latent_scores_not_comparable_with_primary" if analysis in {"S1", "S2"} else "same_estimator_parameterization_only"
        robustness.append(RobustnessResult(analysis, f"run-{analysis}", "davidson", "ordinary_tie_only", "base_research", records, comparability))
    heterogeneity = HeterogeneityResult(
        "S6-English", "partially robust / heterogeneous", "NOT SUPPORTED",
        tuple(HeterogeneityRecord(record.model_id, rank, record.point_rank, record.rank_delta_vs_primary) for rank, record in enumerate(robustness[-1].records, start=1)),
        True, True,
    )
    return FormalPresentationModel(
        "lmsys/chatbot_arena_conversations", "a" * 64, "snapshot-1", "revision-1", primary,
        tuple(robustness), heterogeneity,
        ReviewFacts(True, True, "partially robust / heterogeneous", ("causal claims",)),
    )


def _inputs() -> tuple[FormalPresentationModel, FormalPublicationPackage]:
    model = _model()
    return model, build_formal_publication_package(model)


def _report() -> report_module.FormalReport:
    model, package = _inputs()
    return report_module.build_formal_report(model, package)


def _section(report: report_module.FormalReport, section_id: str) -> report_module.ReportSection:
    return next(section for section in report.sections if section.section_id == section_id)


def _table(section: report_module.ReportSection, table_id: str) -> report_module.ReportTable:
    return next(table for table in section.tables if table.table_id == table_id)


def test_report_sections_and_tables_are_fixed_and_trace_e2_e3() -> None:
    model = _model()
    package = build_formal_publication_package(model)
    report = report_module.build_formal_report(model, package)
    assert tuple(section.section_id for section in report.sections) == (
        "overview", "research-question", "data-population", "method", "primary-result", "uncertainty",
        "robustness", "heterogeneity", "limitations", "methods-provenance",
    )
    primary = _table(_section(report, "primary-result"), "primary-results")
    assert len(primary.rows) == 20
    assert tuple(row[0] for row in primary.rows) == tuple(range(1, 21))
    assert primary.rows[0] == (
        package.primary_table[0].point_rank,
        package.primary_table[0].model_id,
        package.primary_table[0].point_score,
        package.primary_table[0].score_ci_low,
        package.primary_table[0].score_ci_high,
        package.primary_table[0].rank_median,
        package.primary_table[0].rank_ci_low,
        package.primary_table[0].rank_ci_high,
        package.primary_table[0].probability_rank_1,
    )
    assert len(_table(_section(report, "robustness"), "robustness-ranks").rows) == 9 * 20
    assert len(_table(_section(report, "heterogeneity"), "english-subgroup-ranks").rows) == 20


def test_report_wording_preserves_uncertainty_robustness_and_s6_boundaries() -> None:
    model, package = _inputs()
    markdown = report_module.render_formal_report_markdown(_report(), model, package)
    assert "Point rank does not imply certainty." in markdown
    assert "frozen point-rank ordering is preserved" in markdown
    assert "latent score values are not compared" in markdown
    assert "Frozen rank intervals are reported without deriving a new local-ordering classification" in markdown
    assert "PARTIALLY ROBUST / HETEROGENEOUS" in markdown
    assert "Causal interpretation: NOT SUPPORTED." in markdown
    assert "top-four set and top-four order" in markdown
    assert "largest displayed absolute rank displacement" in markdown


def test_report_markdown_is_deterministic_and_claim_bounded() -> None:
    model, package = _inputs()
    first = report_module.render_formal_report_markdown(_report(), model, package)
    second = report_module.render_formal_report_markdown(_report(), model, package)
    assert first == second
    forbidden = (
        "current leaderboard",
        "objective capability",
        "causes better performance",
        "universally preferred",
        "best model",
    )
    lower = first.lower()
    assert all(phrase not in lower for phrase in forbidden)
    assert "not a description of systems available" in lower
    assert "does not establish causal mechanisms" in lower


def test_provenance_and_claim_metadata_are_carried_into_report() -> None:
    report = _report()
    provenance = _table(_section(report, "methods-provenance"), "provenance")
    values = dict(provenance.rows)
    assert values == {
        "evidence_class": "E2_presentation_derivative",
        "source_dataset": "lmsys/chatbot_arena_conversations",
        "source_revision": "revision-1",
        "source_snapshot_id": "snapshot-1",
        "source_file_sha256": "a" * 64,
        "primary_formal_run_id": "run-Primary",
        "historical_population": "true",
        "current_leaderboard": "false",
        "capability_claim": "false",
        "causal_claim": "false",
        "external_generalization": "false",
    }
    assert report.claims == _model().claims


def test_report_is_immutable_and_rejects_inconsistent_e3_values() -> None:
    model = _model()
    package = build_formal_publication_package(model)
    report = report_module.build_formal_report(model, package)
    with pytest.raises(FrozenInstanceError):
        report.title = "Changed"  # type: ignore[misc]
    tampered_primary = replace(package.primary_table[0], point_score=999.0)
    with pytest.raises(report_module.ReportSpecificationError, match="Primary values"):
        report_module.build_formal_report(model, replace(package, primary_table=(tampered_primary,) + package.primary_table[1:]))
    invalid_claims = ClaimMetadata(current_leaderboard=True)
    with pytest.raises(report_module.ReportSpecificationError, match="claim metadata"):
        report_module.build_formal_report(replace(model, claims=invalid_claims), package)


def test_markdown_renderer_rejects_tampered_claim_text() -> None:
    model, package = _inputs()
    report = report_module.build_formal_report(model, package)
    primary_section = report.sections[4]
    tampered_section = replace(
        primary_section,
        paragraphs=("This is a current leaderboard.",),
    )
    tampered_report = replace(report, sections=report.sections[:4] + (tampered_section,) + report.sections[5:])
    with pytest.raises(report_module.ReportSpecificationError, match="canonical"):
        report_module.render_formal_report_markdown(tampered_report, model, package)


@pytest.mark.parametrize("table_index", (4, 6, 7, 9))
def test_markdown_renderer_rejects_tampered_table_values(table_index: int) -> None:
    model, package = _inputs()
    report = report_module.build_formal_report(model, package)
    section = report.sections[table_index]
    table = section.tables[0]
    row = list(table.rows[0])
    row[1] = "tampered provenance" if table_index == 9 else 999.0
    tampered_table = replace(table, rows=(tuple(row),) + table.rows[1:])
    tampered_section = replace(section, tables=(tampered_table,))
    tampered_report = replace(report, sections=report.sections[:table_index] + (tampered_section,) + report.sections[table_index + 1:])
    with pytest.raises(report_module.ReportSpecificationError, match="canonical E2/E3"):
        report_module.render_formal_report_markdown(tampered_report, model, package)


def test_report_does_not_depend_on_loader_or_filesystem_artifacts() -> None:
    source = inspect.getsource(report_module)
    assert "formal_results" not in source
    assert "load_frozen_formal_research" not in source
    assert "Path(" not in source
    assert ".read_" not in source
