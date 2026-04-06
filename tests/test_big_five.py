"""Tests for Big Five personality scoring."""

from unittest.mock import MagicMock

from percent.persona.big_five import BigFiveResult, BigFiveScore, _parse_result, compute_big_five


class TestParseResult:
    def test_parse_valid_json(self):
        text = """{
            "openness": {"score": 75, "reasoning": "好奇心强"},
            "conscientiousness": {"score": 60, "reasoning": "有计划"},
            "extraversion": {"score": 80, "reasoning": "社交活跃"},
            "agreeableness": {"score": 40, "reasoning": "说话直接"},
            "neuroticism": {"score": 30, "reasoning": "情绪稳定"}
        }"""
        result = _parse_result(text)
        assert result.openness.score == 75
        assert result.extraversion.score == 80
        assert result.agreeableness.score == 40

    def test_parse_clamps_scores(self):
        text = """{
            "openness": {"score": 150, "reasoning": "..."},
            "conscientiousness": {"score": -10, "reasoning": "..."},
            "extraversion": {"score": 50, "reasoning": "..."},
            "agreeableness": {"score": 50, "reasoning": "..."},
            "neuroticism": {"score": 50, "reasoning": "..."}
        }"""
        result = _parse_result(text)
        assert result.openness.score == 100
        assert result.conscientiousness.score == 0

    def test_parse_with_surrounding_text(self):
        text = """Here are the results:\n{"openness": {"score": 60, "reasoning": "test"}, "conscientiousness": {"score": 60, "reasoning": "test"}, "extraversion": {"score": 60, "reasoning": "test"}, "agreeableness": {"score": 60, "reasoning": "test"}, "neuroticism": {"score": 60, "reasoning": "test"}}"""
        result = _parse_result(text)
        assert result.openness.score == 60


class TestBigFiveResult:
    def test_to_dict(self):
        result = BigFiveResult(
            openness=BigFiveScore(75, "curious"),
            conscientiousness=BigFiveScore(60, "organized"),
            extraversion=BigFiveScore(80, "social"),
            agreeableness=BigFiveScore(40, "direct"),
            neuroticism=BigFiveScore(30, "stable"),
        )
        d = result.to_dict()
        assert d["openness"]["score"] == 75
        assert d["neuroticism"]["score"] == 30
        assert len(d) == 5

    def test_format_report(self):
        result = BigFiveResult(
            openness=BigFiveScore(75, "好奇心强"),
            conscientiousness=BigFiveScore(60, "有计划"),
            extraversion=BigFiveScore(80, "社交活跃"),
            agreeableness=BigFiveScore(40, "说话直接"),
            neuroticism=BigFiveScore(30, "情绪稳定"),
        )
        report = result.format_report()
        assert "Big Five" in report
        assert "75" in report
        assert "好奇心强" in report


class TestComputeBigFive:
    def test_compute_calls_llm(self):
        mock_client = MagicMock()
        mock_client.complete.return_value = """{
            "openness": {"score": 70, "reasoning": "test"},
            "conscientiousness": {"score": 65, "reasoning": "test"},
            "extraversion": {"score": 55, "reasoning": "test"},
            "agreeableness": {"score": 45, "reasoning": "test"},
            "neuroticism": {"score": 35, "reasoning": "test"}
        }"""
        result = compute_big_five(mock_client, "# Test profile\nSome traits...")
        assert result.openness.score == 70
        mock_client.complete.assert_called_once()
