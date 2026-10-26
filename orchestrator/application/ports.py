from __future__ import annotations

from pathlib import Path
from typing import Protocol

from orchestrator.domain.models import (
    CompileResult,
    MigrationResult,
    RuntimeResult,
    Screen,
    StaticAnalysisResult,
)


class LLMClient(Protocol):
    model: str

    def generate(
        self,
        prompt: str,
        system: str | None,
        *,
        run_index: int,
        iteration: int,
        screen_id: str,
        scenario: str,
        preset: str,
    ) -> tuple[str, dict]:
        ...


class Compiler(Protocol):
    def assemble(self, harness_dir: Path | None = None) -> CompileResult:
        ...


class StaticAnalyzer(Protocol):
    def analyze(self, harness_dir: Path | None = None, *, skip_lint: bool = False) -> StaticAnalysisResult:
        ...


class RuntimeChecker(Protocol):
    def check(
        self,
        code: str,
        *,
        built: bool,
        harness_dir: Path | None = None,
        device_serial: str | None = None,
    ) -> RuntimeResult:
        ...


class HarnessWriter(Protocol):
    def write(
        self,
        code: str,
        *,
        harness_dir: Path | None = None,
        screen_id: str | None = None,
    ) -> tuple[Path, int, str]:
        ...


class ScreenRepository(Protocol):
    def get(self, screen_id: str) -> Screen:
        ...

    def ids(self) -> list[str]:
        ...


class ResultStore(Protocol):
    def exists(self, model: str, sub: str, screen_id: str, run_index: int) -> bool:
        ...

    def save(self, result: MigrationResult) -> Path:
        ...


class CallLog(Protocol):
    def append(self, record: dict) -> None:
        ...
