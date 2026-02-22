"""Tests for Fix 3: _friendly_pass_name (Clear) format parsing."""

from __future__ import annotations

from rdc.services.query_service import _friendly_pass_name


class TestFriendlyPassNameClearFormat:
    def test_clear_format(self) -> None:
        result = _friendly_pass_name("vkCmdBeginRenderPass(Clear)", 0)
        assert result == "Colour Pass #1 (Clear)"

    def test_load_format(self) -> None:
        result = _friendly_pass_name("vkCmdBeginRenderPass(Load)", 0)
        assert result == "Colour Pass #1 (Load)"

    def test_cd_format_unchanged(self) -> None:
        result = _friendly_pass_name("vkCmdBeginRenderPass(C=Clear, D=Clear)", 0)
        assert result == "Colour Pass #1 (1 Target + Depth)"

    def test_multi_target_unchanged(self) -> None:
        result = _friendly_pass_name("vkCmdBeginRenderPass(C=Clear, C=Load, D=Clear)", 2)
        assert result == "Colour Pass #3 (2 Targets + Depth)"

    def test_empty_parens_no_suffix(self) -> None:
        result = _friendly_pass_name("UnknownPassType()", 0)
        assert result == "Colour Pass #1"

    def test_no_parens_no_suffix(self) -> None:
        result = _friendly_pass_name("SomePass", 0)
        assert result == "Colour Pass #1"
