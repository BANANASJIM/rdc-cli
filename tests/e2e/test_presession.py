"""E2E tests for commands that do NOT require a daemon session.

These are pure black-box tests that invoke the CLI via subprocess.
No GPU marker needed since none of these replay a capture.
"""

from __future__ import annotations

from conftest import rdc_fail, rdc_ok


class TestVersion:
    """1.1: rdc --version."""

    def test_prints_version_string(self) -> None:
        """``rdc --version`` prints a version string and exits 0."""
        out = rdc_ok("--version")
        assert "rdc" in out.lower()
        # Version should contain at least major.minor.patch pattern
        parts = out.strip().split()
        version_part = parts[-1]
        assert "." in version_part


class TestHelp:
    """1.2: rdc --help."""

    def test_prints_all_commands(self) -> None:
        """``rdc --help`` lists available commands."""
        out = rdc_ok("--help")
        assert "Commands:" in out or "commands:" in out.lower()
        # Spot-check a few known commands
        for cmd in ("open", "close", "status", "doctor", "goto"):
            assert cmd in out


class TestDoctor:
    """1.3: rdc doctor."""

    def test_checks_environment(self) -> None:
        """``rdc doctor`` checks renderdoc, python, platform (all green)."""
        out = rdc_ok("doctor")
        assert "python" in out.lower()
        assert "platform" in out.lower()
        assert "renderdoc" in out.lower()


class TestStatusNoSession:
    """1.4: rdc status with no active session."""

    def test_error_no_active_session(self) -> None:
        """``rdc status`` without a session prints error and exits 1."""
        out = rdc_fail("status", session="e2e_nosession_status", exit_code=1)
        assert "no active session" in out.lower()


class TestCloseNoSession:
    """1.5: rdc close with no active session."""

    def test_error_no_active_session(self) -> None:
        """``rdc close`` without a session prints error and exits 1."""
        out = rdc_fail("close", session="e2e_nosession_close", exit_code=1)
        assert "no active session" in out.lower()


class TestCompletionBash:
    """1.6: rdc completion bash."""

    def test_valid_bash_completion_script(self) -> None:
        """``rdc completion bash`` outputs a valid bash completion script."""
        out = rdc_ok("completion", "bash")
        assert "_rdc_completion" in out
        assert "complete" in out


class TestCompletionZsh:
    """1.7: rdc completion zsh."""

    def test_valid_zsh_completion_script(self) -> None:
        """``rdc completion zsh`` outputs a valid zsh completion script."""
        out = rdc_ok("completion", "zsh")
        assert "compdef" in out or "compadd" in out


class TestOpenNonexistent:
    """1.8: rdc open nonexistent.rdc."""

    def test_error_file_not_found(self) -> None:
        """``rdc open nonexistent.rdc`` prints file-not-found error and exits 1."""
        out = rdc_fail(
            "open",
            "nonexistent.rdc",
            session="e2e_nosession_open",
            exit_code=1,
        )
        assert "file not found" in out.lower()
