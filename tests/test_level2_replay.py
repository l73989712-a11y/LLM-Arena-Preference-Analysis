from __future__ import annotations

from pathlib import Path

import pytest

import src.level2_replay as replay


@pytest.fixture
def protected_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    roots = tuple(tmp_path / "accepted" / name for name in ("e1", "e2", "publication"))
    for root in roots:
        root.mkdir(parents=True)
    monkeypatch.setattr(replay, "ACCEPTED_E1_ROOT", roots[0])
    monkeypatch.setattr(replay, "ACCEPTED_E2_ROOT", roots[1])
    monkeypatch.setattr(replay, "ACCEPTED_PUBLICATION_ROOT", roots[2])
    return roots


def test_output_root_must_be_new_and_ordinary(protected_roots: tuple[Path, Path, Path], tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(replay.Level2ReplayError, match="already exists"):
        replay.validate_scratch_root(existing)
    with pytest.raises(replay.Level2ReplayError, match="ordinary existing directory"):
        replay.validate_scratch_root(tmp_path / "missing-parent" / "output")


@pytest.mark.parametrize("root_index", [0, 1, 2])
def test_accepted_roots_are_rejected(
    protected_roots: tuple[Path, Path, Path], root_index: int
) -> None:
    with pytest.raises(replay.Level2ReplayError, match="accepted frozen authority"):
        replay.validate_scratch_root(protected_roots[root_index])


def test_children_and_ancestors_of_accepted_roots_are_rejected(
    protected_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    with pytest.raises(replay.Level2ReplayError, match="accepted frozen authority"):
        replay.validate_scratch_root(protected_roots[1] / "child")
    with pytest.raises(replay.Level2ReplayError, match="accepted frozen authority"):
        replay.validate_scratch_root(tmp_path / "accepted")


def test_reparse_ancestor_is_rejected_when_supported(
    protected_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(protected_roots[0].parent, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(replay.Level2ReplayError, match="ordinary existing directory"):
        replay.validate_scratch_root(alias / "output")


def test_mocked_reparse_ancestor_is_rejected(
    monkeypatch: pytest.MonkeyPatch, protected_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    monkeypatch.setattr(replay, "_is_reparse", lambda path: Path(path) == parent)
    with pytest.raises(replay.Level2ReplayError, match="ordinary existing directory"):
        replay.validate_scratch_root(parent / "output")


def test_e2_preverification_failure_prevents_output_creation(
    monkeypatch: pytest.MonkeyPatch, protected_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    output = tmp_path / "output"
    monkeypatch.setattr(replay, "verify_frozen_bundle", lambda: (_ for _ in ()).throw(RuntimeError("E1 failed")))
    called = False

    def produce(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("producer must not run")

    monkeypatch.setattr(replay, "produce_ranking_robustness_artifact_instance", produce)
    with pytest.raises(RuntimeError, match="E1 failed"):
        replay.replay_e2(output)
    assert not called
    assert not output.exists()


def test_e2_uses_fixed_historical_identity_and_cleans_ordinary_failure(
    monkeypatch: pytest.MonkeyPatch, protected_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    output = tmp_path / "output"
    observed: dict[str, str] = {}

    def produce(*, output_parent: Path, producer_git_sha: str):
        observed["producer_git_sha"] = producer_git_sha
        (output_parent / "partial").write_text("partial", encoding="utf-8")
        raise RuntimeError("producer failed")

    monkeypatch.setattr(replay, "produce_ranking_robustness_artifact_instance", produce)
    with pytest.raises(RuntimeError, match="producer failed"):
        replay.replay_e2(output)
    assert observed == {"producer_git_sha": replay.E2_PRODUCER_GIT_SHA}
    assert not output.exists()


def test_keyboard_interrupt_cleans_owned_root(
    monkeypatch: pytest.MonkeyPatch, protected_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    output = tmp_path / "output"

    def produce(*, output_parent: Path, producer_git_sha: str):
        (output_parent / "partial").write_text("partial", encoding="utf-8")
        raise KeyboardInterrupt

    monkeypatch.setattr(replay, "produce_ranking_robustness_artifact_instance", produce)
    with pytest.raises(KeyboardInterrupt):
        replay.replay_e2(output)
    assert not output.exists()


def test_postproduction_failure_cleans_owned_root(
    monkeypatch: pytest.MonkeyPatch, protected_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    output = tmp_path / "output"

    def produce(*, output_parent: Path, producer_git_sha: str):
        bundle = output_parent / "bundle"
        bundle.mkdir()
        return type("Result", (), {"instance_path": bundle})()

    monkeypatch.setattr(replay, "produce_ranking_robustness_artifact_instance", produce)
    monkeypatch.setattr(replay, "verify_ranking_robustness_artifact", lambda _path: (_ for _ in ()).throw(RuntimeError("post failed")))
    with pytest.raises(RuntimeError, match="post failed"):
        replay.replay_e2(output)
    assert not output.exists()


@pytest.mark.parametrize("returned_path_kind", ["outside", "accepted"])
def test_producer_returning_non_owned_bundle_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    protected_roots: tuple[Path, Path, Path],
    tmp_path: Path,
    returned_path_kind: str,
) -> None:
    output = tmp_path / "output"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel").write_text("untouched", encoding="utf-8")
    returned = outside if returned_path_kind == "outside" else protected_roots[1]
    if returned_path_kind == "accepted":
        (returned / "sentinel").write_text("authority", encoding="utf-8")
    verifier_called = False
    monkeypatch.setattr(replay, "verify_frozen_bundle", lambda: None)

    def produce(*, output_parent: Path, producer_git_sha: str):
        (output_parent / "partial").write_text("partial", encoding="utf-8")
        return type("Result", (), {"instance_path": returned})()

    def verify(_path: Path) -> None:
        nonlocal verifier_called
        verifier_called = True

    monkeypatch.setattr(replay, "produce_ranking_robustness_artifact_instance", produce)
    monkeypatch.setattr(replay, "verify_ranking_robustness_artifact", verify)
    with pytest.raises(replay.Level2ReplayError, match="owned scratch descendant"):
        replay.replay_e2(output)
    assert not verifier_called
    assert not output.exists()
    assert (outside / "sentinel").read_text(encoding="utf-8") == "untouched"
    if returned_path_kind == "accepted":
        assert (protected_roots[1] / "sentinel").read_text(encoding="utf-8") == "authority"


def test_publication_preverifies_accepted_e2_and_never_uses_scratch_e2(
    monkeypatch: pytest.MonkeyPatch, protected_roots: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    output = tmp_path / "output"
    verified: list[Path] = []
    monkeypatch.setattr(replay, "verify_frozen_bundle", lambda: None)
    monkeypatch.setattr(replay, "verify_ranking_robustness_artifact", lambda path: verified.append(Path(path)))
    monkeypatch.setattr(replay, "build_publication_model", lambda: object())

    def write(_model: object, output_parent: Path, producer_git_sha: str):
        assert producer_git_sha == replay.PUBLICATION_PRODUCER_GIT_SHA
        bundle = output_parent / "publication"
        bundle.mkdir()
        return type("Result", (), {"bundle_path": bundle})()

    monkeypatch.setattr(replay, "write_publication_bundle", write)
    monkeypatch.setattr(replay, "verify_publication_bundle", lambda _path: None)
    result = replay.replay_publication(output)
    assert verified == [protected_roots[1]]
    assert result.bundle_path == output / "publication"


def test_cli_requires_output_root_and_labels_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        replay.main(["e2"])
    output = tmp_path / "output"
    monkeypatch.setattr(replay, "replay_e2", lambda root: replay.ReplayResult("e2", Path(root), Path(root) / "bundle"))
    assert replay.main(["e2", "--output-root", str(output)]) == 0
    text = capsys.readouterr().out
    assert "NON-AUTHORITATIVE" in text
    assert "VERDICT: PASS" in text


def test_cli_does_not_accept_producer_or_authority_override(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        replay.main(["e2", "--output-root", str(tmp_path / "output"), "--producer-sha", "a" * 40])


def test_module_does_not_invoke_current_data_paths() -> None:
    source = Path(replay.__file__).read_text(encoding="utf-8")
    assert "load_dataset" not in source
    assert "download_chatbot_arena" not in source
