from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pandas as pd
import pytest

from src.battle_contract import SourceProvenance, canonicalize_battles
from src.formal_run import FormalRunConfig, _manifest, execute_formal_run, verify_research_artifacts
from src.population import BASE_RESEARCH, apply_population
from src.population_views import (
    POPULATION_VIEW_SCHEMA_VERSION,
    S4_REPEATED_QID,
    S5_PAIR_SUPPORT_GE10,
    S5_PAIR_SUPPORT_GE20,
    S5_PAIR_SUPPORT_GE50,
    S6_LANGUAGE_ENGLISH,
    apply_population_view,
    population_view_for_id,
)
from src.preference_bootstrap import BootstrapConfig
from src.preference_estimation import PreferenceEstimatorConfig


PROVENANCE = SourceProvenance(source_dataset="synthetic/population-views", source_revision="v1")


def _conversation(prompt: str = "prompt") -> list[dict[str, str]]:
    return [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "response"},
    ]


def _row(
    model_a: str = "a",
    model_b: str = "b",
    *,
    winner: str = "model_a",
    question_id: object = "q1",
    language: object = "English",
    judge: str = "j1",
) -> dict[str, object]:
    return {
        "model_a": model_a,
        "model_b": model_b,
        "winner": winner,
        "question_id": question_id,
        "conversation_a": _conversation(),
        "conversation_b": _conversation(),
        "tstamp": 0,
        "judge": judge,
        "language": language,
        "anony": True,
    }


def _population(rows: list[dict[str, object]]):
    canonical = canonicalize_battles(pd.DataFrame(rows), provenance=PROVENANCE)
    return apply_population(canonical, BASE_RESEARCH)


def _view(rows: list[dict[str, object]], spec):
    return apply_population_view(_population(rows), spec)


def test_s4_unique_and_repeated_groups_follow_all_row_exclusion() -> None:
    result = _view(
        [
            _row(question_id="unique"),
            _row(question_id="repeat"),
            _row(model_a="b", model_b="c", question_id="repeat"),
        ],
        S4_REPEATED_QID,
    )
    assert list(result.population.eligible["question_id_raw"]) == ["unique"]
    assert result.support_audit == {"repeated_group_count": 1, "rows_excluded": 2, "max_group_size": 2}


def test_s4_missing_blank_and_order_outcome_invariant() -> None:
    rows = [
        _row(question_id=None),
        _row(model_a="b", model_b="c", question_id="   "),
        _row(model_a="c", model_b="d", question_id="repeat", winner="tie"),
        _row(model_a="d", model_b="e", question_id="repeat", winner="tie (bothbad)"),
    ]
    first = _view(rows, S4_REPEATED_QID).population.eligible["source_row_index"].tolist()
    second = _view(list(reversed(rows)), S4_REPEATED_QID).population.eligible["question_id_raw"].tolist()
    assert first == [0, 1]
    assert second[0] == "   "
    assert pd.isna(second[1])


def test_s4_preserves_exact_nonblank_question_identity() -> None:
    result = _view(
        [
            _row(question_id="q1"),
            _row(model_a="b", model_b="c", question_id=" q1 "),
        ],
        S4_REPEATED_QID,
    )
    assert result.support_audit == {"repeated_group_count": 0, "rows_excluded": 0, "max_group_size": 1}
    assert len(result.population.eligible) == 2


def test_s4_identity_and_schema_are_manifest_safe() -> None:
    result = _view([_row(question_id="q")], S4_REPEATED_QID)
    assert result.spec.population_id == "base_research_no_repeated_qid"
    assert result.spec.population_view_schema_version == POPULATION_VIEW_SCHEMA_VERSION
    assert result.population.spec.population_spec_version == POPULATION_VIEW_SCHEMA_VERSION
    assert "question_id_raw" not in result.spec.to_dict()


def test_s5_support_is_inclusive_unordered_and_outcome_blind() -> None:
    rows = [
        _row("a", "b", winner="model_a", question_id="q1"),
        _row("b", "a", winner="tie", question_id="q2"),
        _row("a", "b", winner="tie (bothbad)", question_id="q3"),
    ]
    rows += [
        _row("a", "b", winner="model_b", question_id=f"q{i}")
        for i in range(4, 11)
    ]
    result = _view(rows, S5_PAIR_SUPPORT_GE10)
    assert len(result.population.eligible) == 10
    assert result.population.eligible["model_a_id"].tolist()[:3] == ["a", "b", "a"]


def test_s5_all_rows_of_nonqualifying_pairs_are_removed_and_thresholds_distinct() -> None:
    rows = [_row("a", "b", question_id=f"ab{i}") for i in range(10)]
    rows += [_row("a", "c", question_id=f"ac{i}") for i in range(9)]
    ge10 = _view(rows, S5_PAIR_SUPPORT_GE10).population
    ge20 = _view(rows, S5_PAIR_SUPPORT_GE20).population
    ge50 = _view(rows, S5_PAIR_SUPPORT_GE50).population
    assert len(ge10.eligible) == 10
    assert len(ge20.eligible) == 0
    assert len(ge50.eligible) == 0
    assert {S5_PAIR_SUPPORT_GE10.population_id, S5_PAIR_SUPPORT_GE20.population_id, S5_PAIR_SUPPORT_GE50.population_id}.__len__() == 3


def test_s5_row_order_and_winner_changes_do_not_change_support() -> None:
    rows = [_row("a", "b", winner="model_a", question_id=f"q{i}") for i in range(10)]
    changed = [dict(row, winner="model_b" if i % 2 else "tie (bothbad)") for i, row in enumerate(reversed(rows))]
    first = _view(rows, S5_PAIR_SUPPORT_GE10).population.eligible["source_row_index"].tolist()
    second = _view(changed, S5_PAIR_SUPPORT_GE10).population.eligible["source_row_index"].tolist()
    assert first == list(range(10))
    assert set(second) == set(range(10))


def test_s6_is_exact_canonical_language_match_after_base_population() -> None:
    result = _view(
        [
            _row(language="English"),
            _row(model_a="b", model_b="c", language="english"),
            _row(model_a="c", model_b="d", language="English (US)"),
            _row(model_a="d", model_b="e", language="German"),
            _row(model_a="e", model_b="f", language=None),
        ],
        S6_LANGUAGE_ENGLISH,
    )
    assert len(result.population.eligible) == 1
    assert result.population.eligible.iloc[0]["language_canonical"] == "English"


def test_s6_invalid_base_row_cannot_become_eligible_and_order_is_stable() -> None:
    rows = [_row(language="English"), _row(model_a="a", model_b="a", language="English")]
    result = _view(rows, S6_LANGUAGE_ENGLISH)
    assert len(result.population.eligible) == 1
    reversed_result = _view(list(reversed(rows)), S6_LANGUAGE_ENGLISH)
    assert len(reversed_result.population.eligible) == 1


def test_view_registry_rejects_unknown_ids_and_serialization_has_no_row_data() -> None:
    with pytest.raises(KeyError, match="unknown population view"):
        population_view_for_id("base_research_unknown")
    payload = S5_PAIR_SUPPORT_GE10.to_dict()
    assert "pair_support_counts" not in str(payload)
    assert "question_id" not in str(payload)


def _config(population_id: str, view=None) -> FormalRunConfig:
    estimator = PreferenceEstimatorConfig("davidson")
    bootstrap = BootstrapConfig("judge_cluster", 4, seed=17, estimator_config=estimator)
    return FormalRunConfig(
        source_provenance=PROVENANCE,
        population_id=population_id,
        estimator_config=estimator,
        bootstrap_config=bootstrap,
        artifact_root="outputs/research",
        execution_mode="development",
        git_commit="a" * 40,
        population_view=view,
    )


def test_view_manifest_identity_changes_run_id_but_same_view_is_deterministic() -> None:
    base = _manifest(_config(BASE_RESEARCH.population_id), environment={"python_version": "3", "package_versions": {}})
    s4_a = _manifest(_config(S4_REPEATED_QID.population_id, S4_REPEATED_QID), environment={"python_version": "3", "package_versions": {}})
    s4_b = _manifest(_config(S4_REPEATED_QID.population_id, S4_REPEATED_QID), environment={"python_version": "3", "package_versions": {}})
    s5 = _manifest(_config(S5_PAIR_SUPPORT_GE10.population_id, S5_PAIR_SUPPORT_GE10), environment={"python_version": "3", "package_versions": {}})
    assert base.population_id == BASE_RESEARCH.population_id
    assert base.population_spec_version == 2
    assert "population_view" not in base.analysis_config
    assert s4_a.population_id == S4_REPEATED_QID.population_id
    assert s4_a.population_spec_version == 1
    assert s4_a.run_id == s4_b.run_id
    assert s4_a.run_id != base.run_id
    assert s4_a.run_id != s5.run_id
    assert s4_a.analysis_config["population_view"]["base_population"]["population_spec_version"] == 2


def test_view_must_be_registered_and_derive_from_base_v2() -> None:
    with pytest.raises(ValueError, match="base_research"):
        apply_population_view(_population([_row()]), replace(S4_REPEATED_QID, base_population_id="other"))
    with pytest.raises(ValueError, match="registered definition"):
        apply_population_view(_population([_row()]), replace(S4_REPEATED_QID, parameters={"bad": True}))


def test_formal_runner_consumes_effective_view_population_result(tmp_path) -> None:
    source = tmp_path / "synthetic.parquet"
    source.write_bytes(b"synthetic")
    provenance = replace(
        PROVENANCE,
        source_file=source.name,
        source_file_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    estimator = PreferenceEstimatorConfig("davidson")
    config = FormalRunConfig(
        source_provenance=provenance,
        population_id=S6_LANGUAGE_ENGLISH.population_id,
        population_view=S6_LANGUAGE_ENGLISH,
        estimator_config=estimator,
        bootstrap_config=BootstrapConfig("judge_cluster", 4, seed=17, estimator_config=estimator),
        artifact_root=tmp_path / "outputs" / "research",
        execution_mode="development",
        git_commit="a" * 40,
    )
    raw_rows = [
        _row("a", "b", question_id=f"q{i}", language="English", judge=f"j{i % 2}", winner="tie" if i == 1 else "model_a")
        for i in range(4)
    ]
    run_dir = execute_formal_run(
        source,
        config,
        repo_root=tmp_path,
        git_state={"branch": "main", "head": "a" * 40, "origin_main": "a" * 40, "status": ""},
        loader=lambda _path: pd.DataFrame(raw_rows),
    )
    assert verify_research_artifacts(run_dir).ok is True
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    point = json.loads((run_dir / "point_estimate.json").read_text(encoding="utf-8"))
    assert manifest["population_id"] == S6_LANGUAGE_ENGLISH.population_id
    assert manifest["population_spec_version"] == 1
    assert point["population_id"] == manifest["population_id"]
    assert point["population_spec_version"] == manifest["population_spec_version"]
