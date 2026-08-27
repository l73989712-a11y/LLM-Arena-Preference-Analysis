from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import inspect

import pytest

import src.formal_explorer as explorer_module
from src.formal_figures import FormalPublicationPackage, build_formal_publication_package
from src.formal_presentation import (
    FormalModelResult,
    FormalPresentationModel,
    HeterogeneityRecord,
    HeterogeneityResult,
    ReviewFacts,
    RobustnessRecord,
    RobustnessResult,
)
from src.formal_report import FormalReport, build_formal_report, render_formal_report_markdown


MODEL_IDS = tuple(f"model-{rank:02d}" for rank in range(1, 21))
ANALYSES = ("Primary", "S1", "S2", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50", "S6-English")


def _inputs() -> tuple[FormalPresentationModel, FormalPublicationPackage, FormalReport, str]:
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
    model = FormalPresentationModel(
        "lmsys/chatbot_arena_conversations", "a" * 64, "snapshot-1", "revision-1", primary,
        tuple(robustness), heterogeneity,
        ReviewFacts(True, True, "partially robust / heterogeneous", ("causal claims",)),
    )
    package = build_formal_publication_package(model)
    report = build_formal_report(model, package)
    markdown = render_formal_report_markdown(report, model, package)
    return model, package, report, markdown


def _explorer() -> explorer_module.FormalExplorerModel:
    return explorer_module.build_formal_explorer(*_inputs())


def test_explorer_overview_and_views_are_deterministic() -> None:
    first = _explorer()
    second = _explorer()
    assert first == second
    assert first.overview.model_count == 20
    assert first.overview.frozen_analysis_count == 9
    assert first.overview.primary_top_three == (("model-01", 1), ("model-02", 2), ("model-03", 3))
    assert first.overview.claim_boundary == (
        "historical population only", "not a current leaderboard", "not a capability ranking",
        "not a causal claim", "not an external generalization",
    )
    assert len(first.primary.rows) == 20
    assert len(first.robustness.rows) == 180
    assert len(first.heterogeneity.rows) == 20
    assert len(first.provenance.rows) == 12
    assert {row.field: row.value for row in first.provenance.rows}["primary_formal_run_id"] == "run-Primary"
    assert first.primary.score_figure.title == "Estimated Historical Arena Preference"
    assert "not a current leaderboard" in first.primary.score_figure.caption
    assert first.primary.rank_figure.title == "Historical Arena Rank Uncertainty"
    assert first.robustness.figure.title == "Rank Displacement Across Frozen Analyses"
    assert first.heterogeneity.figure.title == "English-Subgroup Rank Heterogeneity"
    assert "causal interpretation: NOT SUPPORTED" in first.heterogeneity.figure.caption


def test_primary_selection_is_display_only() -> None:
    explorer = _explorer()
    top = explorer_module.select_primary_rows(explorer, top_n=5)
    assert tuple(row.point_rank for row in top) == (1, 2, 3, 4, 5)
    selected = explorer_module.select_primary_rows(explorer, model_id="model-04")
    assert selected == (explorer.primary.rows[3],)
    assert explorer_module.select_primary_rows(explorer, top_n=5, model_id="model-04") == (explorer.primary.rows[3],)
    with pytest.raises(explorer_module.ExplorerSpecificationError):
        explorer_module.select_primary_rows(explorer, top_n=0)
    with pytest.raises(explorer_module.ExplorerSpecificationError):
        explorer_module.select_primary_rows(explorer, top_n=21)
    with pytest.raises(explorer_module.ExplorerSpecificationError, match="model_id"):
        explorer_module.select_primary_rows(explorer, model_id="unknown-model")


def test_robustness_selection_is_closed_world_and_rank_only() -> None:
    explorer = _explorer()
    s1 = explorer_module.select_robustness_rows(explorer, analysis_label="S1")
    assert len(s1) == 20
    assert all(row.analysis_label == "S1" for row in s1)
    assert explorer_module.select_robustness_rows(explorer, analysis_label="S6-English", model_id="model-05")[0].rank_delta_vs_primary == 1
    with pytest.raises(explorer_module.ExplorerSpecificationError):
        explorer_module.select_robustness_rows(explorer, analysis_label="new-run")
    with pytest.raises(explorer_module.ExplorerSpecificationError, match="model_id"):
        explorer_module.select_robustness_rows(explorer, model_id="unknown-model")
    assert "latent scores are not comparable" in explorer.robustness.s1_s2_boundary


def test_s6_and_provenance_boundaries_are_exposed() -> None:
    explorer = _explorer()
    assert explorer.heterogeneity.classification == "partially robust / heterogeneous"
    assert explorer.heterogeneity.causal_interpretation == "NOT SUPPORTED"
    assert explorer.heterogeneity.top4_set_preserved is True
    assert explorer.heterogeneity.top4_order_preserved is True
    assert explorer.provenance.formal_evidence_status == "verified frozen Phase 2 evidence"
    assert explorer.provenance.historical_source_warning.startswith("Historical frozen dataset")
    assert explorer.report_markdown == _inputs()[-1]


def test_package_figure_metadata_tampering_is_rejected() -> None:
    model, package, report, markdown = _inputs()
    tampered_figure = replace(package.primary_figure, caption="Current capability leaderboard.")
    with pytest.raises(explorer_module.ExplorerSpecificationError, match="package"):
        explorer_module.build_formal_explorer(model, replace(package, primary_figure=tampered_figure), report, markdown)


def test_explorer_is_immutable_and_rejects_unanchored_report() -> None:
    model, package, report, markdown = _inputs()
    explorer = explorer_module.build_formal_explorer(model, package, report, markdown)
    with pytest.raises(FrozenInstanceError):
        explorer.report_markdown = "tampered"  # type: ignore[misc]
    with pytest.raises(explorer_module.ExplorerSpecificationError, match="canonical"):
        explorer_module.build_formal_explorer(model, package, report, markdown + "\n")
    with pytest.raises(explorer_module.ExplorerSpecificationError, match="canonical"):
        explorer_module.build_formal_explorer(replace(model, claims=replace(model.claims, current_leaderboard=True)), package, report, markdown)


def test_explorer_rejects_malformed_s6_classification() -> None:
    model, package, report, markdown = _inputs()
    malformed = replace(model.heterogeneity, classification=None)  # type: ignore[arg-type]
    with pytest.raises(explorer_module.ExplorerSpecificationError, match="classification"):
        explorer_module.build_formal_explorer(replace(model, heterogeneity=malformed), package, report, markdown)


def test_explorer_does_not_depend_on_filesystem_loader_or_demo_modules() -> None:
    source = inspect.getsource(explorer_module)
    assert "formal_results" not in source
    assert "load_frozen_formal_research" not in source
    assert "Path(" not in source
    for forbidden in ("sample_data", "preprocess", "ml_model", "run_pipeline", "visualization"):
        assert forbidden not in source
