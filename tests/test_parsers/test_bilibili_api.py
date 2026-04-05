from unittest.mock import MagicMock, patch

from engram.parsers.bilibili_api import fetch_bilibili_history


def test_fetch_parses_api_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "cursor": {"view_at": 0, "business": ""},
            "list": [
                {
                    "title": "3Blue1Brown - Linear Algebra",
                    "author_name": "3Blue1Brown",
                    "tag_name": "science",
                    "duration": 1080,
                    "view_at": 1700000000,
                },
            ],
        },
    }

    with patch("engram.parsers.bilibili_api.requests.get", return_value=mock_response):
        chunks = fetch_bilibili_history("fake_cookie", max_pages=1)

    assert len(chunks) == 1
    assert "3Blue1Brown" in chunks[0].content
    assert chunks[0].source == "bilibili"


def test_fetch_handles_expired_cookie():
    mock_response = MagicMock()
    mock_response.json.return_value = {"code": -101, "message": "账号未登录"}

    with patch("engram.parsers.bilibili_api.requests.get", return_value=mock_response):
        try:
            fetch_bilibili_history("expired_cookie")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Cookie expired" in str(e)
