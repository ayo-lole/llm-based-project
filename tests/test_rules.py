from orchestrator.domain.rules import check_arch_rules
from orchestrator.domain.scoring import arch_score, mvvm_compliant

COMPLIANT = """
package demo
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.material3.Button
import androidx.compose.material3.Text

interface LoginRepository
data class LoginUiState(val name: String = "")
class LoginViewModel(private val repository: LoginRepository) : ViewModel() {
    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()
    fun onSubmit() {}
}
@Composable
fun LoginScreen(vm: LoginViewModel) {
    val state = vm.uiState.collectAsStateWithLifecycle()
    LoginContent(state = state.value, onSubmit = vm::onSubmit)
}
@Composable
fun LoginContent(state: LoginUiState, onSubmit: () -> Unit) {
    Button(onClick = onSubmit) { Text(state.name) }
}
@Preview
@Composable
fun LoginPreview() {
    Text("preview")
}
@Composable
fun MigrationRoot() { }
"""

R1 = """
package demo
import androidx.compose.runtime.Composable
import androidx.compose.material3.Text
@Composable fun Screen() { Text("x") }
"""

R2 = """
package demo
import androidx.lifecycle.ViewModel
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
data class Ui(val x: String = "")
class Vm : ViewModel() {
    private val _uiState = MutableStateFlow(Ui())
    val uiState: StateFlow<Ui> = _uiState.asStateFlow()
}
@Composable fun Screen(vm: Vm) { val s = vm.uiState.collectAsState() }
"""

R3 = """
package demo
import androidx.lifecycle.ViewModel
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
data class Ui(val x: String = "")
class Vm : ViewModel() {
    private val _uiState = MutableStateFlow(Ui())
    val uiState: StateFlow<Ui> = _uiState.asStateFlow()
}
@Composable fun Screen(vm: Vm) {
    LaunchedEffect(Unit) { repository.load() }
}
"""

R4 = """
package demo
import androidx.lifecycle.ViewModel
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.material3.Button
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
data class Ui(val x: String = "")
class Vm : ViewModel() {
    private val _uiState = MutableStateFlow(Ui())
    val uiState: StateFlow<Ui> = _uiState.asStateFlow()
}
@Composable fun Leaf() {
    val user = remember { mutableStateOf("") }
    Button(onClick = { }) { }
}
"""

R5 = """
package demo
import androidx.lifecycle.ViewModel
import androidx.compose.runtime.Composable
import androidx.compose.material3.Button
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
data class Ui(val x: String = "")
class Vm : ViewModel() {
    private val _uiState = MutableStateFlow(Ui())
    val uiState: StateFlow<Ui> = _uiState.asStateFlow()
}
@Composable fun Screen(vm: Vm) {
    Button(onClick = { vm.x = 1 }) { }
}
"""

R6 = """
package demo
import androidx.lifecycle.ViewModel
import androidx.compose.runtime.Composable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
data class Ui(val x: String = "")
class UserRepository
class Vm : ViewModel() {
    private val repo = UserRepository()
    private val _uiState = MutableStateFlow(Ui())
    val uiState: StateFlow<Ui> = _uiState.asStateFlow()
}
@Composable fun Screen(vm: Vm) { }
"""

UI_STATE_OK = """
package demo
import androidx.lifecycle.ViewModel
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.material3.Button
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
interface Repo
data class Ui(val x: String = "")
class Vm(private val repository: Repo) : ViewModel() {
    private val _uiState = MutableStateFlow(Ui())
    val uiState: StateFlow<Ui> = _uiState.asStateFlow()
    fun onClick() {}
}
@Composable fun Screen(vm: Vm) {
    val state = vm.uiState.collectAsStateWithLifecycle()
    Content(state.value, onClick = vm::onClick)
}
@Composable fun Content(state: Ui, onClick: () -> Unit) {
    val expanded = remember { mutableStateOf(false) }
    Button(onClick = onClick) { }
}
@Composable fun MigrationRoot() {}
"""


def test_compliant_zero():
    v = check_arch_rules(COMPLIANT)
    assert v == []
    assert arch_score(v) == 100
    assert mvvm_compliant(v)


def test_r1():
    assert any(x.startswith("[R1]") for x in check_arch_rules(R1))


def test_r2():
    assert any(x.startswith("[R2]") for x in check_arch_rules(R2))


def test_r3():
    assert any(x.startswith("[R3]") for x in check_arch_rules(R3))


def test_r4():
    assert any(x.startswith("[R4]") for x in check_arch_rules(R4))


def test_r5():
    assert any(x.startswith("[R5]") for x in check_arch_rules(R5))


def test_r6():
    assert any(x.startswith("[R6]") for x in check_arch_rules(R6))


def test_preview_ignored():
    code = COMPLIANT + """
@Preview
@Composable fun BadPreview() {
    val user = remember { mutableStateOf("x") }
}
"""
    assert check_arch_rules(code) == []


def test_ui_element_state_allowed():
    assert check_arch_rules(UI_STATE_OK) == []
