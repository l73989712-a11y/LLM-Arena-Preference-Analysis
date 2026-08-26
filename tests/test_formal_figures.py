from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
import inspect
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

import src.formal_figures as figures
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
            RobustnessRecord(analysis, model_id, ranks[model_id], ranks[model_id] - index)
            for index, model_id in enumerate(MODEL_IDS, start=1)
        )
        comparability = "latent_scores_not_comparable_with_primary" if analysis in {"S1", "S2"} else "same_estimator_parameterization_only"
        robustness.append(RobustnessResult(analysis, f"run-{analysis}", "davidson", "ordinary_tie_only", "base_research", records, comparability))
    heterogeneity = HeterogeneityResult(
        "S6-English", "partially robust / heterogeneous", "NOT SUPPORTED",
        tuple(HeterogeneityRecord(record.model_id, index, record.point_rank, record.rank_delta_vs_primary) for index, record in enumerate(robustness[-1].records, start=1)),
        True, True,
    )
    return FormalPresentationModel(
        "lmsys/chatbot_arena_conversations", "a" * 64, "snapshot-1", "revision-1", primary,
        tuple(robustness), heterogeneity,
        ReviewFacts(True, True, "partially robust / heterogeneous", ("causal claims",)),
    )


def test_tables_are_rank_ordered_and_trace_e2_values() -> None:
    model = _model()
    package = figures.build_formal_publication_package(model)
    assert len(package.primary_table) == 20
    assert tuple(row.point_rank for row in package.primary_table) == tuple(range(1, 21))
    assert tuple(row.model_id for row in package.primary_table) == MODEL_IDS
    assert package.primary_table[0].point_score == model.primary[0].point_score
    assert package.primary_table[0].score_ci_low == model.primary[0].score_ci_low
    assert package.primary_table[0].rank_ci_high == model.primary[0].rank_ci_high
    assert package.primary_table[0].probability_rank_1 == model.primary[0].probability_rank_1
    assert tuple(row.field for row in package.provenance_table)[:5] == (
        "evidence_class", "source_dataset", "source_revision", "source_snapshot_id", "source_file_sha256",
    )


def test_robustness_table_is_closed_world_rank_only() -> None:
    package = figures.build_formal_publication_package(_model())
    assert package.robustness_figure.analysis_labels == ANALYSES
    assert len(package.robustness_table) == 9 * 20
    assert tuple(field.name for field in fields(figures.RobustnessTableRow)) == (
        "analysis_label", "primary_rank", "model_id", "point_rank", "rank_delta_vs_primary",
    )
    s6_model_05 = next(row for row in package.robustness_table if row.analysis_label == "S6-English" and row.model_id == "model-05")
    assert s6_model_05.point_rank == 6
    assert s6_model_05.rank_delta_vs_primary == 1


def test_s6_table_and_caption_preserve_non_causal_boundary() -> None:
    package = figures.build_formal_publication_package(_model())
    assert len(package.heterogeneity_table) == 20
    moved = next(row for row in package.heterogeneity_table if row.model_id == "model-05")
    assert (moved.primary_rank, moved.english_rank, moved.rank_delta) == (5, 6, 1)
    assert package.heterogeneity_figure.classification == "partially robust / heterogeneous"
    assert package.heterogeneity_figure.causal_interpretation == "NOT SUPPORTED"
    assert "causal interpretation: NOT SUPPORTED" in package.heterogeneity_figure.caption


def test_titles_and_captions_preserve_claim_boundaries() -> None:
    package = figures.build_formal_publication_package(_model())
    for spec in (
        package.primary_figure, package.rank_uncertainty_figure,
        package.robustness_figure, package.heterogeneity_figure,
    ):
        text = f"{spec.title} {spec.caption}".lower()
        assert "leaderboard" in text
        assert "capability ranking" in text
        assert "historical" in text
        assert spec.claims.historical_population is True
        assert spec.claims.current_leaderboard is False
        assert spec.claims.capability_claim is False
        assert spec.claims.causal_claim is False
        assert spec.claims.external_generalization is False
    assert "rank-1 probabilities" not in package.rank_uncertainty_figure.caption
    assert "machine-readable primary table" in package.rank_uncertainty_figure.caption


def test_package_is_deterministic_and_immutable() -> None:
    model = _model()
    first = figures.build_formal_publication_package(model)
    second = figures.build_formal_publication_package(model)
    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.primary_table = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        first.primary_table[0] = first.primary_table[0]  # type: ignore[index]


def test_invalid_claim_metadata_fails_closed() -> None:
    model = _model()
    invalid_claims = ClaimMetadata(current_leaderboard=True)
    with pytest.raises(figures.FigureSpecificationError, match="claim metadata"):
        figures.build_formal_publication_package(replace(model, claims=invalid_claims))
    package = figures.build_formal_publication_package(model)
    with pytest.raises(figures.FigureSpecificationError, match="claim metadata"):
        figures.render_primary_figure(replace(package.primary_figure, claims=invalid_claims))
    with pytest.raises(figures.FigureSpecificationError, match="claim metadata"):
        figures.build_formal_publication_package(replace(model, claims=ClaimMetadata(evidence_class="not_e2")))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("title", "Current Capability Leaderboard"),
        ("caption", "This is a current capability ranking."),
        ("filename", "current_capability_leaderboard.png"),
    ),
)
def test_primary_renderer_rejects_tampered_public_claim_text(field: str, value: str) -> None:
    package = figures.build_formal_publication_package(_model())
    tampered = replace(package.primary_figure, **{field: value})
    with pytest.raises(figures.FigureSpecificationError, match="canonical"):
        figures.render_primary_figure(tampered)


def test_heterogeneity_renderer_rejects_causal_caption_tampering() -> None:
    package = figures.build_formal_publication_package(_model())
    tampered = replace(
        package.heterogeneity_figure,
        caption="English causes model performance changes.",
    )
    with pytest.raises(figures.FigureSpecificationError, match="canonical"):
        figures.render_heterogeneity_figure(tampered)


def test_malformed_s6_spec_classification_fails_with_domain_error() -> None:
    package = figures.build_formal_publication_package(_model())
    malformed = replace(package.heterogeneity_figure, classification=None)  # type: ignore[arg-type]
    with pytest.raises(figures.FigureSpecificationError, match="classification"):
        figures.render_heterogeneity_figure(malformed)


def test_s1_s2_boundary_and_alignment_fail_closed() -> None:
    model = _model()
    s1 = model.robustness[1]
    invalid_s1 = replace(s1, score_comparability="same_estimator_parameterization_only")
    with pytest.raises(figures.FigureSpecificationError, match="S1 score comparability"):
        figures.build_formal_publication_package(replace(model, robustness=(model.robustness[0], invalid_s1) + model.robustness[2:]))
    bad_s6 = replace(model.robustness[-1], records=tuple(reversed(model.robustness[-1].records)))
    with pytest.raises(figures.FigureSpecificationError, match="aligned"):
        figures.build_formal_publication_package(replace(model, robustness=model.robustness[:-1] + (bad_s6,)))


def test_s6_review_facts_must_match_heterogeneity_e2_facts() -> None:
    model = _model()
    mismatched_review = replace(model.review_facts, heterogeneity_classification="robust")
    with pytest.raises(figures.FigureSpecificationError, match="S6 heterogeneity facts"):
        figures.build_formal_publication_package(replace(model, review_facts=mismatched_review))
    package = figures.build_formal_publication_package(model)
    assert model.heterogeneity.classification.upper() in package.heterogeneity_figure.caption


def test_primary_renderer_accepts_point_outside_frozen_interval() -> None:
    model = _model()
    outside = replace(model.primary[0], point_score=model.primary[0].score_ci_high + 5.0)
    outside_model = replace(model, primary=(outside,) + model.primary[1:])
    package = figures.build_formal_publication_package(outside_model)
    assert package.primary_table[0].point_score > package.primary_table[0].score_ci_high
    figure = figures.render_primary_figure(package.primary_figure)
    try:
        stream = io.BytesIO()
        figure.savefig(stream, format="png", dpi=80)
        assert stream.getvalue().startswith(b"\x89PNG")
    finally:
        plt.close(figure)


def test_renderers_return_nonempty_in_memory_pngs_without_file_output(tmp_path) -> None:
    package = figures.build_formal_publication_package(_model())
    rendered = figures.render_all_formal_figures(package)
    assert len(rendered) == 4
    try:
        for figure in rendered:
            stream = io.BytesIO()
            figure.savefig(stream, format="png", dpi=80)
            assert stream.getvalue().startswith(b"\x89PNG")
            assert len(stream.getvalue()) > 1_000
        assert list(tmp_path.iterdir()) == []
    finally:
        for figure in rendered:
            plt.close(figure)


def test_formal_rendering_does_not_depend_on_the_e1_loader() -> None:
    source = inspect.getsource(figures)
    assert "formal_results" not in source
    assert "load_frozen_formal_research" not in source
    assert "load_frozen_formal_run" not in source
