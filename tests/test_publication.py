from __future__ import annotations

import json
from dataclasses import replace

import pytest

import src.publication as publication


def test_frozen_publication_model_has_closed_shape() -> None:
    model = publication.build_publication_model()
    assert model.specification.publication_schema_version == 1
    assert model.specification.publication_contract_version == 1
    assert model.specification.section_ids == publication.SECTION_IDS
    assert model.specification.table_ids == publication.TABLE_IDS
    assert model.specification.figure_roles == publication.FIGURE_ROLES
    assert model.specification.transform_ids == publication.TRANSFORM_IDS
    assert model.specification.display_format_ids == publication.DISPLAY_FORMAT_IDS
    assert [table.table_id for table in model.tables] == list(publication.TABLE_IDS)
    assert [len(table.rows) for table in model.tables] == [20, 180, 20, 11]


def test_identity_and_authority_registry_are_fixed() -> None:
    model = publication.build_publication_model()
    assert [claim.claim_id for claim in model.claims] == [
        "provenance.e0_identity", "provenance.e1_identity", "provenance.e2_identity",
        "primary.top_three", "primary.score_uncertainty", "primary.rank_uncertainty",
        "robustness.point_ranks", "s6.rank_comparison",
    ]
    assert [claim.source_authority for claim in model.claims] == ["E0", "E1", "E2", "E1", "E1", "E1", "E2", "E1"]
    assert publication.AGGREGATION_TRANSFORMS == ()
    assert publication.PRIMARY_RUN_ID == "9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689"
    assert publication.S6_RUN_ID == "8dba0d09c93abafe6c448a3ddb8ee22671792208e85b378f5c1b2328ee52624d"


def test_source_pointers_reject_open_traversal() -> None:
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E0", "source_identity", field="anything_else")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E2", "metric", metric="rank_distributions", record_key="model_id", record_value="gpt-4", field="rank_by_run")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E1", "run_result", publication.PRIMARY_RUN_ID, "bootstrap_summary", field="rank_summary.arbitrary")


def test_tables_store_typed_values_without_display_duplicates() -> None:
    model = publication.build_publication_model()
    primary = model.tables[0]
    row = primary.rows[0]
    assert isinstance(row.values["point_rank"], int)
    assert isinstance(row.values["point_score"], float)
    assert all(not isinstance(value, dict) or set(value) != {"raw", "display"} for table in model.tables for row in table.rows for value in row.values.values())
    assert all("display" not in row.values for table in model.tables for row in table.rows)


def test_report_is_anchored_and_has_no_historical_e3_wording() -> None:
    model = publication.build_publication_model()
    report = publication.render_report_markdown(model)
    assert report.endswith("\n")
    assert all(f"<!-- publication-section:{section} -->" in report for section in publication.SECTION_IDS)
    for claim_id in ("primary.top_three", "primary.score_uncertainty", "primary.rank_uncertainty", "robustness.point_ranks", "s6.rank_comparison"):
        assert f"<!-- publication-claim:{claim_id} -->" in report
    lowered = report.lower()
    assert "e3 publication" not in lowered
    assert "e3 evidence" not in lowered
    assert "estimated preference under the frozen historical arena population" in lowered


def test_serializers_are_deterministic_and_instance_id_is_out_of_scope() -> None:
    first = publication.build_publication_model()
    second = publication.build_publication_model()
    assert publication.serialize_publication_spec(first.specification) == publication.serialize_publication_spec(second.specification)
    assert publication.serialize_tables(first) == publication.serialize_tables(second)
    assert publication.serialize_traceability(first) == publication.serialize_traceability(second)
    assert first.specification.publication_spec_id == second.specification.publication_spec_id
    assert b"publication_instance_id" not in publication.serialize_publication_spec(first.specification)
    assert b"publication_instance_id" not in publication.serialize_tables(first)
    assert b"publication_instance_id" not in publication.serialize_traceability(first)
    parsed = json.loads(publication.serialize_tables(first))
    assert parsed["publication_spec_id"] == first.specification.publication_spec_id
    assert publication.serialize_tables(first).endswith(b"\n")


def test_figure_roles_use_existing_phase3_specs() -> None:
    model = publication.build_publication_model()
    assert isinstance(model.figures["primary_preference"], publication.PrimaryFigureSpec)
    assert isinstance(model.figures["rank_uncertainty"], publication.RankUncertaintyFigureSpec)
    assert isinstance(model.figures["robustness_ranks"], publication.RobustnessFigureSpec)
    assert isinstance(model.figures["s6_heterogeneity"], publication.HeterogeneityFigureSpec)
    assert {"output_path", "kind", "figure_role", "transform_id", "phase3_spec_type", "source_claim_ids"} <= set(model.traceability["figure_bindings"][0])


def test_claim_chains_never_contain_display_formats_and_primary_coverage_is_complete() -> None:
    model = publication.build_publication_model()
    display_ids = set(publication.DISPLAY_FORMAT_IDS)
    assert all(not display_ids.intersection(claim.transform_chain) for claim in model.claims)
    bindings = [binding for claim in model.claims if claim.claim_kind == "quantitative" for binding in claim.render_bindings if binding.get("kind") == "table_cell"]
    covered = {(b["table_id"], b["row_id"], b["column_id"]) for b in bindings}
    for table in model.tables:
        if table.table_id == "primary-results":
            assert {(table.table_id, row.row_id, column.column_id) for row in table.rows for column in table.columns if column.column_id != "model_id"} <= covered


def test_provenance_rows_and_e2_claim_are_semantically_aligned() -> None:
    model = publication.build_publication_model()
    provenance = next(table for table in model.tables if table.table_id == "provenance")
    assert [row.values["field"] for row in provenance.rows] == [
        "source_dataset", "source_revision", "source_snapshot_id", "source_file_sha256",
        "bundle_name", "e1_payload_inventory_sha256", "primary_run_id", "s6_run_id",
        "artifact_instance_id", "derivation_spec_id", "e2_payload_inventory_sha256",
    ]
    assert not any(row.values["field"] in {"historical_population", "current_leaderboard", "capability_claim", "causal_claim", "external_generalization"} for row in provenance.rows)
    e2 = next(claim for claim in model.claims if claim.claim_id == "provenance.e2_identity")
    assert [pointer.object for pointer in e2.source_pointers] == ["artifact_identity"] * 3
    assert set(e2.scientific_values) == {publication.E2_INSTANCE_ID, publication.E2_DERIVATION_SPEC_ID, publication.E2_PAYLOAD_INVENTORY_SHA256}


def test_nested_publication_values_are_deeply_immutable() -> None:
    model = publication.build_publication_model()
    with pytest.raises(TypeError):
        model.tables[0].rows[0].values["point_rank"] = 999  # type: ignore[index]
    with pytest.raises(TypeError):
        model.traceability["claims"] = ()  # type: ignore[index]
    before = publication.serialize_tables(model)
    assert before == publication.serialize_tables(model)


def test_report_bindings_include_actual_prose_and_table_hashes() -> None:
    model = publication.build_publication_model()
    claims = {entry["claim_id"]: entry for entry in model.traceability["claims"]}
    top = next(binding for binding in claims["primary.top_three"]["render_bindings"] if binding.get("kind") == "report_claim")
    assert top["expected_text"] in model.report_markdown
    uncertainty = next(binding for binding in claims["primary.score_uncertainty"]["render_bindings"] if binding.get("kind") == "report_claim")
    assert uncertainty["table_sha256"]
    assert uncertainty["table_id"] == "primary-results"


def test_e2_cross_specification_byte_binding_rejects_modified_file(tmp_path) -> None:
    source = publication.Path(publication.__file__).resolve().parents[1] / "artifacts" / "phase-5" / publication.E2_INSTANCE_ID / "cross_specification.json"
    modified = tmp_path / "cross_specification.json"
    modified.write_bytes(source.read_bytes().replace(b'"maximum_absolute_rank_shift":0', b'"maximum_absolute_rank_shift":1', 1))
    with pytest.raises(publication.PublicationError, match="bytes do not match"):
        publication._cross_specification(modified)


def test_s6_identity_changes_specification_identity() -> None:
    spec = publication.build_publication_spec()
    changed = publication.PublicationSpec(
        spec.publication_schema_version, spec.publication_contract_version,
        spec.source_e0_identity, {**spec.source_e1_identity, "s6_run_id": "f" * 64},
        spec.source_e2_identity, spec.section_ids, spec.table_ids, spec.figure_roles,
        spec.transform_ids, spec.display_format_ids,
    )
    assert changed.publication_spec_id != spec.publication_spec_id


def test_closed_pointer_rules_reject_valid_looking_openings() -> None:
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E1", "run_result", "f" * 64, "manifest", field="run_id")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E1", "run_result", publication.PRIMARY_RUN_ID, "manifest", record_key="model_id", record_value="gpt-4", field="run_id")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E1", "run_result", publication.PRIMARY_RUN_ID, "point_estimate", record_key="bad", record_value="gpt-4", field="derived_rank")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E1", "run_result", publication.PRIMARY_RUN_ID, "point_estimate", record_key="model_id", field="derived_rank")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E2", "metric", record_key="bad", record_value="gpt-4", field="rank_by_run", metric="cross_specification")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E2", "metric", record_key="model_id", record_value="gpt-4", field="record_set", metric="cross_specification")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E1", "bundle_identity", field="run_id")
    with pytest.raises(publication.PublicationError):
        publication.SourcePointer("E2", "artifact_identity", field="primary_rank")


def test_table_schema_and_claim_semantics_are_closed() -> None:
    with pytest.raises(publication.PublicationError):
        publication.TableModel("primary-results", "bad", (publication.ColumnSpec("anything", "Anything", "string", "label.v1"),), ())
    with pytest.raises(publication.PublicationError):
        publication.Claim("primary.top_three", "provenance", "E1", (publication.SourcePointer("E1", "run_result", publication.PRIMARY_RUN_ID, "point_estimate", field="derived_rank"),), ("identity.v1",), (), ())


def test_producer_consistency_validator_rejects_report_and_traceability_mismatches() -> None:
    model = publication.build_publication_model()
    with pytest.raises(publication.PublicationError):
        replace(model, report_markdown=model.report_markdown.replace("point rank 1", "point rank 2", 1))
    broken_trace = dict(model.traceability)
    broken_trace["claims"] = tuple(model.traceability["claims"])[1:]
    with pytest.raises(publication.PublicationError):
        replace(model, traceability=broken_trace)
    entry = dict(model.traceability["claims"][3])
    renderings = list(entry["render_bindings"])
    table_binding = next(item for item in renderings if item.get("kind") == "table_cell")
    renderings[renderings.index(table_binding)] = {**table_binding, "expected_value": 999}
    entry["render_bindings"] = renderings
    entries = list(model.traceability["claims"])
    entries[3] = entry
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "claims": entries})


def test_report_table_hash_and_figure_semantics_are_required() -> None:
    model = publication.build_publication_model()
    entries = list(model.traceability["claims"])
    entry = dict(entries[3])
    report = [dict(binding) for binding in entry["render_bindings"]]
    report_binding = next(binding for binding in report if binding.get("kind") == "report_claim")
    report_binding["table_sha256"] = "0" * 64
    entry["render_bindings"] = report
    entries[3] = entry
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "claims": entries})
    figures = list(model.traceability["figure_bindings"])
    figures[0] = {**figures[0], "phase3_spec_type": "WrongFigureSpec"}
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "figure_bindings": figures})


def test_half_even_display_is_distinct_and_raw_values_remain_raw() -> None:
    assert publication._display(1.2345645, "decimal6_half_even.v1") == "1.234564"
    assert publication._display(1.2345655, "decimal6_half_even.v1") == "1.234566"
    model = publication.build_publication_model()
    assert model.tables[0].rows[0].values["point_score"] != publication._display(model.tables[0].rows[0].values["point_score"], "decimal6_half_even.v1")


@pytest.mark.parametrize("field", ["source_pointers", "transform_chain", "scientific_values"])
def test_traceability_claim_semantics_cannot_drift(field: str) -> None:
    model = publication.build_publication_model()
    entries = [dict(entry) for entry in model.traceability["claims"]]
    entries[3][field] = ("tampered",)
    with pytest.raises(publication.PublicationError, match="semantic mismatch"):
        replace(model, traceability={**model.traceability, "claims": entries})


def test_traceability_top_level_and_claim_registry_are_closed() -> None:
    model = publication.build_publication_model()
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "publication_spec_id": "0" * 64})
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "publication_schema_version": 2})
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "extra": True})
    entries = list(model.traceability["claims"])
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "claims": entries + [entries[0]]})
    duplicate = entries.copy()
    duplicate[1] = {**duplicate[1], "claim_id": duplicate[0]["claim_id"]}
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "claims": duplicate})


def test_canonical_rows_and_membership_cannot_be_reordered() -> None:
    model = publication.build_publication_model()
    tables = list(model.tables)
    primary = tables[0]
    with pytest.raises(publication.PublicationError):
        replace(model, tables=(replace(primary, rows=tuple(reversed(primary.rows))), *tables[1:]))
    changed_row = replace(primary.rows[0], row_id="model:wrong")
    with pytest.raises(publication.PublicationError):
        replace(model, tables=(replace(primary, rows=(changed_row,) + primary.rows[1:]), *tables[1:]))
    bad_membership = replace(primary.rows[5], claim_ids=("primary.top_three", "primary.score_uncertainty", "primary.rank_uncertainty"))
    with pytest.raises(publication.PublicationError):
        replace(model, tables=(replace(primary, rows=primary.rows[:5] + (bad_membership,) + primary.rows[6:]), *tables[1:]))


def test_traceability_bindings_use_exact_closed_union_shapes() -> None:
    model = publication.build_publication_model()
    entries = [dict(entry) for entry in model.traceability["claims"]]
    top = dict(entries[3])
    report = [dict(binding) for binding in top["render_bindings"]]
    report_binding = next(binding for binding in report if binding["kind"] == "report_claim")
    report_binding["extra"] = True
    top["render_bindings"] = report
    entries[3] = top
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "claims": entries})
    figures = [dict(binding) for binding in model.traceability["figure_bindings"]]
    figures[0]["output_path"] = "figures/wrong.png"
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "figure_bindings": figures})


@pytest.mark.parametrize("table_index", [1, 2, 3])
def test_non_primary_canonical_rows_cannot_be_reordered(table_index: int) -> None:
    model = publication.build_publication_model()
    tables = list(model.tables)
    target = tables[table_index]
    tables[table_index] = replace(target, rows=tuple(reversed(target.rows)))
    with pytest.raises(publication.PublicationError):
        replace(model, tables=tuple(tables))


@pytest.mark.parametrize("table_index", [1, 2, 3])
def test_non_primary_canonical_row_ids_cannot_change(table_index: int) -> None:
    model = publication.build_publication_model()
    tables = list(model.tables)
    target = tables[table_index]
    changed = replace(target.rows[0], row_id="tampered-row")
    tables[table_index] = replace(target, rows=(changed,) + target.rows[1:])
    with pytest.raises(publication.PublicationError):
        replace(model, tables=tuple(tables))


def test_extra_claim_bindings_are_rejected_even_when_individually_valid() -> None:
    model = publication.build_publication_model()
    entries = [dict(entry) for entry in model.traceability["claims"]]
    entry = dict(entries[3])
    bindings = list(entry["render_bindings"])
    table_binding = next(binding for binding in bindings if binding["kind"] == "table_cell")
    bindings.append(dict(table_binding))
    entry["render_bindings"] = bindings
    entries[3] = entry
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "claims": entries})

    entry = dict(entries[3])
    bindings = list(model.traceability["claims"][3]["render_bindings"])
    report_binding = next(binding for binding in bindings if binding["kind"] == "report_claim")
    bindings.append(dict(report_binding))
    entry["render_bindings"] = bindings
    entries[3] = entry
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "claims": entries})

    entry = dict(model.traceability["claims"][3])
    bindings = list(entry["render_bindings"])
    bindings.append(dict(model.traceability["figure_bindings"][0]))
    entry["render_bindings"] = bindings
    entries = list(model.traceability["claims"])
    entries[3] = entry
    with pytest.raises(publication.PublicationError):
        replace(model, traceability={**model.traceability, "claims": entries})


def test_report_claim_must_occur_in_declared_section_with_its_payload() -> None:
    model = publication.build_publication_model()
    primary = next(table for table in model.tables if table.table_id == "primary-results")
    canonical = publication._markdown_table(primary)
    uncertainty = publication._report_section(model.report_markdown, "uncertainty")
    removed_section = uncertainty.replace(canonical, "", 1)
    removed = model.report_markdown.replace(uncertainty, removed_section, 1)
    with pytest.raises(publication.PublicationError):
        replace(model, report_markdown=removed)
    altered = canonical.replace("| 1 | gpt-4 |", "| 2 | gpt-4 |", 1)
    assert altered != canonical
    with pytest.raises(publication.PublicationError):
        replace(model, report_markdown=model.report_markdown.replace(uncertainty, uncertainty.replace(canonical, altered, 1), 1))

    top_anchor = "<!-- publication-claim:primary.top_three -->"
    moved = model.report_markdown.replace(top_anchor, "", 1)
    overview_marker = "<!-- publication-section:overview -->"
    moved = moved.replace(overview_marker, overview_marker + "\n" + top_anchor, 1)
    with pytest.raises(publication.PublicationError):
        replace(model, report_markdown=moved)


def test_canonical_model_rejects_fake_specification() -> None:
    model = publication.build_publication_model()
    spec = model.specification
    altered = publication.PublicationSpec(
        spec.publication_schema_version,
        spec.publication_contract_version,
        spec.source_e0_identity,
        spec.source_e1_identity,
        {**spec.source_e2_identity, "artifact_instance_id": "f" * 64},
        spec.section_ids,
        spec.table_ids,
        spec.figure_roles,
        spec.transform_ids,
        spec.display_format_ids,
    )
    with pytest.raises(publication.PublicationError):
        replace(model, specification=altered)


def test_actual_figure_specs_must_equal_accepted_phase3_package() -> None:
    model = publication.build_publication_model()
    altered = replace(model.figures["primary_preference"], title="tampered")
    figures = dict(model.figures)
    figures["primary_preference"] = altered
    with pytest.raises(publication.PublicationError):
        replace(model, figures=figures)


def test_figure_traceability_source_claims_and_paths_are_closed() -> None:
    model = publication.build_publication_model()
    for field, value in (("source_claim_ids", ["primary.rank_uncertainty"]), ("output_path", "figures/other.png")):
        figures = [dict(binding) for binding in model.traceability["figure_bindings"]]
        figures[0][field] = value
        with pytest.raises(publication.PublicationError):
            replace(model, traceability={**model.traceability, "figure_bindings": figures})
