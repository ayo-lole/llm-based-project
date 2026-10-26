from pathlib import Path

from orchestrator.application.feedback import collect_problems, format_feedback, prioritize
from orchestrator.application.migrate import migrate_screen
from orchestrator.domain.models import CompileResult, MigrationResult, RuntimeResult, Screen, StaticAnalysisResult


class _LLM:
    model = "openai/gpt-4o"

    def __init__(self, outputs: list[str]):
        self.outputs = list(outputs)
        self.calls = []

    def generate(self, prompt, system, **kwargs):
        self.calls.append((prompt, system, kwargs))
        return self.outputs.pop(0), {}


class _Screens:
    def get(self, screen_id: str) -> Screen:
        return Screen(id=screen_id, xml="<LinearLayout/>")

    def ids(self):
        return ["s"]


class _Writer:
    def write(self, code, **kwargs):
        return Path("Generated.kt"), 0, "existing"


class _Compiler:
    def __init__(self, results: list[CompileResult]):
        self.results = list(results)

    def assemble(self, harness_dir=None):
        return self.results.pop(0)


class _Analyzer:
    def analyze(self, harness_dir=None, *, skip_lint=False):
        return StaticAnalysisResult(True, True, True)


class _Runtime:
    def check(self, code, *, built, harness_dir=None, device_serial=None):
        return RuntimeResult(built, "emulator" if built else "skipped")


class _Store:
    def __init__(self):
        self.saved = []

    def exists(self, *a):
        return False

    def save(self, result: MigrationResult) -> Path:
        self.saved.append(result)
        return Path("x.json")


TEMPLATES = {
    "s1": "go {XML} {CONTEXT}",
    "s2": "s2 {XML} {CONTEXT}",
    "s3": "s3 {XML} {CONTEXT}",
    "s4": "s4 {XML} {CONTEXT}",
    "refine": "fix {PREV_CODE} {FEEDBACK}",
}

OK_CODE = """
package demo
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import androidx.compose.runtime.Composable
import androidx.compose.material3.Button
import androidx.compose.material3.Text
interface Repo
data class Ui(val n: String = "")
class Vm(private val repository: Repo) : ViewModel() {
    private val _uiState = MutableStateFlow(Ui())
    val uiState: StateFlow<Ui> = _uiState.asStateFlow()
    fun onClick() {}
}
@Composable fun Screen(vm: Vm) {
    val s = vm.uiState.collectAsStateWithLifecycle()
    Content(s.value, onClick = vm::onClick)
}
@Composable fun Content(state: Ui, onClick: () -> Unit) {
    Button(onClick = onClick) { Text(state.n) }
}
@Composable fun MigrationRoot() {}
"""

FAIL_CODE = "package demo\nimport androidx.compose.runtime.Composable\n@Composable fun Screen() {}\n"


def _run(outputs, compiles, scenario="s4", **flags):
    store = _Store()
    client = _LLM(outputs)
    migrate_screen(
        "s",
        client,
        TEMPLATES,
        _Screens(),
        _Writer(),
        _Compiler(compiles),
        _Analyzer(),
        _Runtime(),
        store,
        scenario=scenario,
        **flags,
    )
    return store.saved[0], client


def test_converge_full_needs_arch_and_build():
    ok = CompileResult(True, True, True)
    result, _ = _run([OK_CODE], [ok], scenario="s4")
    assert result.converged
    assert result.iterations == 1


def test_no_static_converges_on_build_only():
    built = CompileResult(True, True, True)
    result, _ = _run([FAIL_CODE], [built], scenario="s4", no_static_analysis=True, ablation_label="no_static_analysis")
    assert result.converged


def test_no_arch_converges_on_build_only():
    built = CompileResult(True, True, True)
    result, _ = _run([FAIL_CODE], [built], scenario="s4", no_constraints=True, ablation_label="no_arch_constraint")
    assert result.converged


def test_k4_three_refinements():
    fail = CompileResult(False, False, False, errors=["e: boom"])
    result, client = _run([FAIL_CODE, FAIL_CODE, FAIL_CODE, FAIL_CODE], [fail, fail, fail, fail], scenario="s4")
    assert result.iterations == 4
    assert len(client.calls) == 4  # initial + 3 refinements


def test_feedback_order():
    compile_res = CompileResult(False, False, False, errors=["e: one", "e: two"])
    sa = StaticAnalysisResult(False, True, True, detekt_issues=["style"])
    problems = collect_problems(compile_res, sa, ["[R3] io", "[R1] vm"])
    ranked = prioritize(problems)
    assert ranked[0].startswith("e:")
    assert ranked.index("[R3] io") < ranked.index("[R1] vm") or "[R3]" in ranked[2]
    text = format_feedback(problems)
    assert text.count("\n") <= 20


def test_persistence_fields():
    ok = CompileResult(True, True, True)
    result, _ = _run([OK_CODE], [ok], scenario="s3")
    d = result.to_dict()
    assert "codes_per_iteration" in d
    assert "generation_settings" in d
    assert result.history[0].compile_s >= 0
