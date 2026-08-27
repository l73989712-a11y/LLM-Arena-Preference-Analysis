from __future__ import annotations

from pathlib import Path
import re

from packaging.requirements import InvalidRequirement, Requirement


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DIRECT_REQUIREMENTS = REPOSITORY_ROOT / "requirements.txt"
DEV_REQUIREMENTS = REPOSITORY_ROOT / "requirements-dev.txt"
CONSTRAINTS = REPOSITORY_ROOT / "requirements-constraints.txt"
OPTIONAL_REQUIREMENTS = REPOSITORY_ROOT / "requirements_optional.txt"


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_requirements(path: Path, *, allow_runtime_include: bool = False) -> list[Requirement]:
    requirements: list[Requirement] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line == "-r requirements.txt":
            assert allow_runtime_include, f"unexpected runtime include in {path.name}"
            continue
        assert not line.startswith("-"), f"unknown requirements directive in {path.name}: {raw!r}"
        try:
            requirement = Requirement(line)
        except InvalidRequirement as exc:
            raise AssertionError(f"unparseable requirement line in {path.name}: {raw!r}") from exc
        requirements.append(requirement)
    return requirements


def _requirement_names(path: Path, *, allow_runtime_include: bool = False) -> list[str]:
    return [_normalized(requirement.name) for requirement in _parse_requirements(path, allow_runtime_include=allow_runtime_include)]


def _constraints() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s#]+)", line)
        assert match, f"constraint is not an exact pin: {raw!r}"
        name = _normalized(match.group(1))
        assert name not in result, f"duplicate normalized constraint: {name}"
        result[name] = match.group(2)
    return result


def test_dev_requirements_inherit_runtime_once() -> None:
    lines = [line.split("#", 1)[0].strip() for line in DEV_REQUIREMENTS.read_text(encoding="utf-8").splitlines()]
    assert lines.count("-r requirements.txt") == 1
    assert _requirement_names(DEV_REQUIREMENTS, allow_runtime_include=True) == ["pytest"]


def test_canonical_direct_requirements_are_exactly_constrained() -> None:
    direct_names = _requirement_names(DIRECT_REQUIREMENTS)
    direct = set(direct_names)
    dev_direct = set(_requirement_names(DEV_REQUIREMENTS, allow_runtime_include=True))
    constraints = _constraints()

    assert len(direct) == len(direct_names)
    assert direct <= constraints.keys()
    assert dev_direct == {"pytest"}
    assert dev_direct <= constraints.keys()


def test_optional_requirements_are_not_promoted() -> None:
    optional = set(_requirement_names(OPTIONAL_REQUIREMENTS))
    assert not optional & set(_requirement_names(DIRECT_REQUIREMENTS))


def test_canonical_requirements_have_no_unsafe_sources() -> None:
    for path, allow_include in ((DIRECT_REQUIREMENTS, False), (DEV_REQUIREMENTS, True)):
        for requirement in _parse_requirements(path, allow_runtime_include=allow_include):
            assert requirement.url is None, f"direct requirement must not use a URL: {requirement}"


def test_constraints_header_records_phase4_policy() -> None:
    header = CONSTRAINTS.read_text(encoding="utf-8").split("altair==", 1)[0]
    assert ">=3.12,<3.13" in header
    assert "CPython 3.12.5" in header
    assert "Windows AMD64" in header
    assert "P4-T4" in header
    assert "E1-generation contract" in header
