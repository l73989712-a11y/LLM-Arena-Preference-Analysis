from __future__ import annotations

from dataclasses import dataclass
import inspect

import pytest
import matplotlib.pyplot as plt

import formal_app
from src.formal_explorer import FormalExplorerModel


@dataclass
class _Call:
    name: str
    value: object = None


class _FakeStreamlit:
    def __init__(self, checkbox_value: bool = False) -> None:
        self.calls: list[_Call] = []
        self.checkbox_value = checkbox_value

    def set_page_config(self, **kwargs): self.calls.append(_Call("set_page_config", kwargs))
    def title(self, value): self.calls.append(_Call("title", value))
    def caption(self, value): self.calls.append(_Call("caption", value))
    def warning(self, value): self.calls.append(_Call("warning", value))
    def error(self, value): self.calls.append(_Call("error", value))
    def write(self, value): self.calls.append(_Call("write", value))
    def metric(self, *args, **kwargs): self.calls.append(_Call("metric", (args, kwargs)))
    def subheader(self, value): self.calls.append(_Call("subheader", value))
    def dataframe(self, value, **kwargs): self.calls.append(_Call("dataframe", value))
    def info(self, value): self.calls.append(_Call("info", value))
    def markdown(self, value): self.calls.append(_Call("markdown", value))
    def tabs(self, labels):
        self.calls.append(_Call("tabs", labels))
        return [_FakeContext(self) for _ in labels]
    def slider(self, *args, **kwargs): self.calls.append(_Call("slider", args)); return kwargs.get("value", 20)
    def selectbox(self, *args, **kwargs): self.calls.append(_Call("selectbox", args)); return args[1][0]
    def checkbox(self, *args, **kwargs): self.calls.append(_Call("checkbox", args)); return self.checkbox_value
    def pyplot(self, figure, **kwargs): self.calls.append(_Call("pyplot", figure))
    def stop(self): self.calls.append(_Call("stop")); raise StopIteration()


class _FakeContext:
    def __init__(self, owner): self.owner = owner
    def __enter__(self): return self
    def __exit__(self, *args): return False


def _explorer() -> FormalExplorerModel:
    from tests.test_formal_explorer import _inputs
    model, package, report, markdown = _inputs()
    return formal_app.build_formal_explorer(model, package, report, markdown)


def test_source_has_independent_entrypoint_and_forbidden_controls_absent() -> None:
    source = inspect.getsource(formal_app)
    assert "app.py" not in source
    for forbidden in ("file_uploader", "run_id text input", "confidence-level", "tie-policy", "LLM analysis"):
        assert forbidden not in source.lower()
    assert "sample_data" not in source
    assert "run_pipeline" not in source


def test_render_ui_exposes_six_canonical_tabs_and_boundary_text(monkeypatch) -> None:
    fake = _FakeStreamlit()
    monkeypatch.setattr(formal_app, "st", fake)
    formal_app.render_explorer_ui(_explorer())
    tabs = next(call.value for call in fake.calls if call.name == "tabs")
    assert tabs == ("Overview", "Primary & Uncertainty", "Robustness", "English-Subgroup Heterogeneity", "Methods & Provenance", "Report")
    text = " ".join(str(call.value) for call in fake.calls)
    assert "Historical frozen dataset" in text
    assert "not a current leaderboard" in text
    assert "latent scores are not comparable" in text
    assert "NOT SUPPORTED" in text
    assert "primary_formal_run_id" in text


def test_report_markdown_is_displayed_unchanged(monkeypatch) -> None:
    fake = _FakeStreamlit()
    monkeypatch.setattr(formal_app, "st", fake)
    model, package, report, markdown = __import__("tests.test_formal_explorer", fromlist=["_inputs"])._inputs()
    explorer = formal_app.build_formal_explorer(model, package, report, markdown)
    formal_app.render_explorer_ui(explorer)
    assert any(call.name == "markdown" and call.value == markdown for call in fake.calls)


def test_runtime_orchestration_order_and_failure_are_visible(monkeypatch) -> None:
    order: list[str] = []
    sentinel = object()
    class _Package:
        primary_figure = sentinel
        rank_uncertainty_figure = sentinel
        robustness_figure = sentinel
        heterogeneity_figure = sentinel
    monkeypatch.setattr(formal_app, "load_frozen_formal_research", lambda root: order.append("load") or sentinel)
    monkeypatch.setattr(formal_app, "build_formal_presentation", lambda bundle: order.append("presentation") or sentinel)
    monkeypatch.setattr(formal_app, "build_formal_publication_package", lambda model: order.append("figures") or _Package())
    monkeypatch.setattr(formal_app, "build_formal_report", lambda model, package: order.append("report") or sentinel)
    monkeypatch.setattr(formal_app, "render_formal_report_markdown", lambda report, model, package: order.append("markdown") or "markdown")
    monkeypatch.setattr(formal_app, "build_formal_explorer", lambda model, package, report, markdown: order.append("explorer") or FormalExplorerModel)
    monkeypatch.setattr(formal_app, "render_primary_figure", lambda spec: order.append("primary-figure") or object())
    monkeypatch.setattr(formal_app, "render_rank_uncertainty_figure", lambda spec: order.append("rank-figure") or object())
    monkeypatch.setattr(formal_app, "render_robustness_figure", lambda spec: order.append("robustness-figure") or object())
    monkeypatch.setattr(formal_app, "render_heterogeneity_figure", lambda spec: order.append("heterogeneity-figure") or object())
    runtime = formal_app.build_runtime_explorer("frozen-root")
    assert runtime.explorer is FormalExplorerModel
    assert order == ["load", "presentation", "figures", "report", "markdown", "explorer", "primary-figure", "rank-figure", "robustness-figure", "heterogeneity-figure"]

    monkeypatch.setattr(formal_app, "load_frozen_formal_research", lambda root: (_ for _ in ()).throw(formal_app.FrozenResultsError("missing")))
    with pytest.raises(RuntimeError, match="could not be verified"):
        formal_app.build_runtime_explorer("missing-root")


def test_main_stops_visibly_without_demo_fallback(monkeypatch) -> None:
    fake = _FakeStreamlit()
    monkeypatch.setattr(formal_app, "st", fake)
    monkeypatch.setattr(formal_app, "build_runtime_explorer", lambda: (_ for _ in ()).throw(RuntimeError("verification failed")))
    with pytest.raises(StopIteration):
        formal_app.main()
    assert any(call.name == "error" and call.value == "verification failed" for call in fake.calls)
    assert any(call.name == "stop" for call in fake.calls)


def test_hidden_runtime_figures_are_closed_after_render(monkeypatch) -> None:
    fake = _FakeStreamlit(checkbox_value=False)
    monkeypatch.setattr(formal_app, "st", fake)
    runtime = formal_app.RuntimeExplorer(_explorer(), *(plt.figure() for _ in range(4)))
    numbers = tuple(figure.number for figure in (runtime.primary_figure, runtime.rank_figure, runtime.robustness_figure, runtime.heterogeneity_figure))
    formal_app.render_explorer_ui(runtime)
    assert all(not plt.fignum_exists(number) for number in numbers)


def test_shown_runtime_figures_are_closed_after_render(monkeypatch) -> None:
    fake = _FakeStreamlit(checkbox_value=True)
    monkeypatch.setattr(formal_app, "st", fake)
    runtime = formal_app.RuntimeExplorer(_explorer(), *(plt.figure() for _ in range(4)))
    numbers = tuple(figure.number for figure in (runtime.primary_figure, runtime.rank_figure, runtime.robustness_figure, runtime.heterogeneity_figure))
    formal_app.render_explorer_ui(runtime)
    assert sum(call.name == "pyplot" for call in fake.calls) == 4
    assert all(not plt.fignum_exists(number) for number in numbers)


def test_runtime_figures_are_closed_when_ui_raises(monkeypatch) -> None:
    fake = _FakeStreamlit()
    monkeypatch.setattr(formal_app, "st", fake)
    runtime = formal_app.RuntimeExplorer(_explorer(), *(plt.figure() for _ in range(4)))
    numbers = tuple(figure.number for figure in (runtime.primary_figure, runtime.rank_figure, runtime.robustness_figure, runtime.heterogeneity_figure))
    monkeypatch.setattr(formal_app, "_render_overview", lambda explorer: (_ for _ in ()).throw(RuntimeError("ui failure")))
    with pytest.raises(RuntimeError, match="ui failure"):
        formal_app.render_explorer_ui(runtime)
    assert all(not plt.fignum_exists(number) for number in numbers)
