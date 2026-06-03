import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timezone, timedelta
from app.youtube_summarizer import YouTubeSummarizer

# Mock XML for YouTube Channel RSS Feed
MOCK_YT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <title>Mock Channel</title>
  <entry>
    <id>yt:video:VIDEO_NEW</id>
    <yt:videoId>VIDEO_NEW</yt:videoId>
    <title>Bull Market Outlook 2026</title>
    <published>{published_new}</published>
    <link rel="alternate" href="https://www.youtube.com/watch?v=VIDEO_NEW"/>
    <media:description xmlns:media="http://search.yahoo.com/mrss/">Recent macro views.</media:description>
  </entry>
  <entry>
    <id>yt:video:VIDEO_OLD</id>
    <yt:videoId>VIDEO_OLD</yt:videoId>
    <title>Historical Crash Recapped</title>
    <published>{published_old}</published>
    <link rel="alternate" href="https://www.youtube.com/watch?v=VIDEO_OLD"/>
    <media:description xmlns:media="http://search.yahoo.com/mrss/">Older views.</media:description>
  </entry>
</feed>
"""

@pytest.fixture
def mock_channel_map():
    return {"@sosumonkey": "UC8f3JcEcbM_1f8m8WqU2y8A"}

def test_resolve_handle_to_id_cached(mock_channel_map):
    summarizer = YouTubeSummarizer("mock-key", mock_channel_map)
    res_id = summarizer.resolve_handle_to_id("@sosumonkey")
    assert res_id == "UC8f3JcEcbM_1f8m8WqU2y8A"

@patch("app.youtube_summarizer.requests.get")
def test_resolve_handle_to_id_scrape(mock_get, mock_channel_map):
    # Mocking standard page response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><meta itemprop="channelId" content="UC_SCRAPED_ID_1234567890"></html>'
    mock_get.return_value = mock_resp
    
    summarizer = YouTubeSummarizer("mock-key", mock_channel_map)
    # Target not in cache
    res_id = summarizer.resolve_handle_to_id("@newchannel")
    
    assert res_id == "UC_SCRAPED_ID_1234567890"
    mock_get.assert_called_once_with("https://www.youtube.com/@newchannel", headers=ANY, timeout=15)

@patch("app.youtube_summarizer.requests.get")
def test_fetch_channel_videos_last_48h(mock_get, mock_channel_map):
    now_utc = datetime.now(timezone.utc)
    new_pub_time = (now_utc - timedelta(hours=10)).isoformat()
    old_pub_time = (now_utc - timedelta(hours=60)).isoformat()
    
    rss_content = MOCK_YT_RSS.format(published_new=new_pub_time, published_old=old_pub_time)
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = rss_content.encode("utf-8")
    mock_get.return_value = mock_resp
    
    summarizer = YouTubeSummarizer("mock-key", mock_channel_map)
    videos = summarizer.fetch_channel_videos_last_48h("UC12345")
    
    assert len(videos) == 1
    assert videos[0]["video_id"] == "VIDEO_NEW"
    assert videos[0]["title"] == "Bull Market Outlook 2026"

@patch("app.youtube_summarizer.YouTubeTranscriptApi.fetch")
def test_get_transcript_success(mock_fetch, mock_channel_map):
    mock_snippet_1 = MagicMock()
    mock_snippet_1.text = "Hello"
    mock_snippet_2 = MagicMock()
    mock_snippet_2.text = "world"
    
    mock_transcript = MagicMock()
    mock_transcript.snippets = [mock_snippet_1, mock_snippet_2]
    mock_fetch.return_value = mock_transcript
    
    summarizer = YouTubeSummarizer("mock-key", mock_channel_map)
    transcript = summarizer.get_transcript("VIDEO_NEW")
    
    assert transcript == "Hello world"
    mock_fetch.assert_called_once_with("VIDEO_NEW", languages=["ko", "en"])

@patch("app.youtube_summarizer.YouTubeTranscriptApi.fetch")
def test_get_transcript_failure(mock_fetch, mock_channel_map):
    mock_fetch.side_effect = Exception("No transcripts")
    
    summarizer = YouTubeSummarizer("mock-key", mock_channel_map)
    with pytest.raises(Exception) as exc_info:
        summarizer.get_transcript("VIDEO_NEW")
    assert "Transcript unavailable" in str(exc_info.value)

@patch("app.youtube_summarizer.genai.GenerativeModel")
def test_summarize_video_transcript(mock_genai_model, mock_channel_map):
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "### 1. Market Sentiment\nNeutral"
    mock_model_instance.generate_content.return_value = mock_response
    mock_genai_model.return_value = mock_model_instance
    
    summarizer = YouTubeSummarizer("mock-key", mock_channel_map)
    summary = summarizer.summarize_video_transcript("Bull Market Outlook 2026", "inflation rate is low.")
    
    assert "Market Sentiment" in summary
    assert "Neutral" in summary
    mock_model_instance.generate_content.assert_called_once()
