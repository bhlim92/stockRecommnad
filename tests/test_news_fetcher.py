import pytest
from unittest.mock import MagicMock, patch
from app.news_fetcher import NewsFetcher

# Sample Google News RSS XML
MOCK_NEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Google News</title>
    <item>
      <title>Fed Keeps Rates Steady as Inflation Moderates - Wall Street Journal</title>
      <link>https://example.com/fed-rates</link>
      <pubDate>Sun, 31 May 2026 12:00:00 GMT</pubDate>
      <description>&lt;a href="https://example.com/fed-rates"&gt;Fed Keeps Rates Steady&lt;/a&gt;</description>
      <source url="https://wsj.com">Wall Street Journal</source>
    </item>
    <item>
      <title>Markets Rally to New Highs</title>
      <link>https://example.com/market-rally</link>
      <pubDate>Sun, 31 May 2026 13:00:00 GMT</pubDate>
      <description>Stocks jumped on strong earnings reports from tech giants.</description>
    </item>
  </channel>
</rss>
"""

@patch("app.news_fetcher.requests.get")
def test_fetch_query_news_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = MOCK_NEWS_RSS.encode("utf-8")
    mock_get.return_value = mock_resp
    
    fetcher = NewsFetcher()
    news = fetcher.fetch_query_news("inflation", limit=5)
    
    assert len(news) == 2
    
    # Check WSJ article title parse split "Headline - Source Name"
    assert news[0]["title"] == "Fed Keeps Rates Steady as Inflation Moderates"
    assert news[0]["source"] == "Wall Street Journal"
    assert news[0]["link"] == "https://example.com/fed-rates"
    assert news[0]["pub_date"] == "Sun, 31 May 2026 12:00:00 GMT"
    assert "Fed Keeps Rates Steady" in news[0]["summary"]
    
    # Check item without " - Source Name" split or source node details
    assert news[1]["title"] == "Markets Rally to New Highs"
    assert news[1]["source"] == "Unknown"
    assert news[1]["summary"] == "Stocks jumped on strong earnings reports from tech giants."

@patch("app.news_fetcher.requests.get")
def test_fetch_query_news_failure(mock_get):
    # Test HTTP Error propagation
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
    mock_get.return_value = mock_resp
    
    fetcher = NewsFetcher()
    with pytest.raises(ConnectionError):
        fetcher.fetch_query_news("KOSPI")
