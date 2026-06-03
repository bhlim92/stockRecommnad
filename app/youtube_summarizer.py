import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai

from app.utils.helpers import retry_api_call
from app.utils.logger import setup_logger

logger = setup_logger("youtube_summarizer", "logs/app.log")

class YouTubeSummarizer:
    """
    Extracts transcripts from recent YouTube videos and generates key summarized notes using the Gemini API.
    """

    def __init__(self, api_key: str, channel_id_map: dict[str, str], model_name: str = "gemini-2.5-flash") -> None:
        """
        Args:
            api_key: Gemini API developer key.
            channel_id_map: In-memory cache map matching handles to Channel IDs.
            model_name: Name of the Gemini model to use.
        """
        self.api_key = api_key
        self.channel_id_map = channel_id_map
        self.model_name = model_name
        # Configure Gemini API
        if self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            logger.warning("Gemini API key is missing. Video summarization will be bypassed or mock-filled.")

    @retry_api_call(max_retries=3, initial_delay=2.0, backoff_factor=2.0)
    def resolve_handle_to_id(self, handle: str) -> str:
        """
        Resolves channel handle (@example) to full YouTube channel ID. Searches cache map first,
        falling back to parsing channel page source code if missing.
        
        Args:
            handle: Target YouTube channel handle.
            
        Returns:
            Resolved YouTube channel ID.
            
        Raises:
            ValueError: If handle cannot be resolved.
        """
        logger.info(f"Resolving handle to ID: {handle}")
        
        # Check cache map first
        if handle in self.channel_id_map:
            resolved_id = self.channel_id_map[handle]
            logger.debug(f"Handle {handle} resolved from cache: {resolved_id}")
            return resolved_id

        # Fallback to scraping the channel page source
        url = f"https://www.youtube.com/{handle}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # 1. Look for canonical link containing channel ID
            match = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})"', response.text)
            if match:
                resolved_id = match.group(1)
                logger.info(f"Resolved handle {handle} via canonical link: {resolved_id}")
                return resolved_id
                
            # 2. Look for any youtube.com/channel/UC... pattern
            match = re.search(r'youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})', response.text)
            if match:
                resolved_id = match.group(1)
                logger.info(f"Resolved handle {handle} via general channel URL: {resolved_id}")
                return resolved_id

            # 3. Look for externalChannelId JSON pattern
            match = re.search(r'\"externalChannelId\":\"(UC[a-zA-Z0-9_-]{22})\"', response.text)
            if match:
                resolved_id = match.group(1)
                logger.info(f"Resolved handle {handle} via externalChannelId: {resolved_id}")
                return resolved_id
            
            # 4. Look for itemprop="channelId" meta tag
            match = re.search(r'<meta itemprop="channelId" content="(UC[a-zA-Z0-9_-]{22})"', response.text)
            if match:
                resolved_id = match.group(1)
                logger.info(f"Resolved handle {handle} via meta tag: {resolved_id}")
                return resolved_id
                
            # 5. Look for JSON pattern "channelId":"UC..."
            match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', response.text)
            if match:
                resolved_id = match.group(1)
                logger.info(f"Resolved handle {handle} via JSON pattern: {resolved_id}")
                return resolved_id
                
            raise ValueError(f"No channel ID found in response for handle {handle}")
        except Exception as e:
            logger.error(f"Failed to scrape channel ID for handle {handle}: {str(e)}")
            raise ValueError(f"Could not resolve handle {handle} to channel ID: {str(e)}")

    @retry_api_call(max_retries=3, initial_delay=2.0, backoff_factor=2.0)
    def fetch_channel_videos_last_48h(self, channel_id: str) -> List[Dict[str, str]]:
        """
        Queries YouTube RSS feeds to retrieve links/details of videos uploaded in the past 48 hours.
        
        Args:
            channel_id: Channel ID to look up.
            
        Returns:
            List of dictionaries containing: 'video_id', 'title', 'published_at', 'link', 'description'.
        """
        logger.info(f"Fetching RSS video feed for channel ID: {channel_id}")
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "xml")
            entries = soup.find_all("entry")
            
            videos = []
            now = datetime.now(timezone.utc)
            
            for entry in entries:
                published_str = entry.find("published").text if entry.find("published") else ""
                if not published_str:
                    continue
                    
                try:
                    # Replace Z with UTC offset for compatibility with fromisoformat
                    pub_clean = published_str.replace("Z", "+00:00")
                    pub_dt = datetime.fromisoformat(pub_clean)
                except Exception:
                    continue
                
                # Check if video was published in the last 48 hours
                if now - pub_dt <= timedelta(hours=48):
                    video_id = entry.find("yt:videoId")
                    if not video_id:
                        video_id = entry.find("videoId")
                    video_id_str = video_id.text if video_id else ""
                    
                    if not video_id_str and entry.find("id"):
                        id_text = entry.find("id").text
                        if "video:" in id_text:
                            video_id_str = id_text.split("video:")[-1]
                            
                    title = entry.find("title").text if entry.find("title") else ""
                    link_elem = entry.find("link")
                    link = link_elem.get("href") if link_elem else f"https://www.youtube.com/watch?v={video_id_str}"
                    
                    # Extract RSS description if available
                    desc_elem = entry.find("media:description") or entry.find("description")
                    description = desc_elem.text if desc_elem else ""
                    
                    videos.append({
                        "video_id": video_id_str,
                        "title": title,
                        "published_at": published_str,
                        "link": link,
                        "description": description
                    })
                    
            logger.info(f"Found {len(videos)} videos in the last 48 hours for channel {channel_id}")
            return videos
        except Exception as e:
            logger.error(f"Error fetching RSS videos for channel {channel_id}: {str(e)}")
            raise ConnectionError(f"Failed to fetch YouTube RSS feed for channel {channel_id}: {str(e)}")

    def get_transcript(self, video_id: str, languages: List[str] = ["ko", "en"]) -> str:
        """
        Retrieves transcript text using the youtube-transcript-api client library.
        
        Args:
            video_id: YouTube video ID.
            languages: Language fallback list (attempts Korean, then English).
            
        Returns:
            Raw combined text transcript of the video.
            
        Raises:
            Exception: If transcripts are disabled or unavailable.
        """
        logger.info(f"Retrieving transcript for video ID: {video_id} (languages: {languages})")
        try:
            api = YouTubeTranscriptApi()
            transcript_obj = api.fetch(video_id, languages=languages)
            if hasattr(transcript_obj, "snippets"):
                transcript_text = " ".join([snippet.text for snippet in transcript_obj.snippets])
            elif isinstance(transcript_obj, list):
                transcript_text = " ".join([item["text"] for item in transcript_obj])
            else:
                transcript_text = str(transcript_obj)
            logger.info(f"Successfully retrieved transcript ({len(transcript_text)} characters) for video {video_id}")
            return transcript_text
        except Exception as e:
            logger.warning(f"Failed to get transcript for video {video_id}: {str(e)}")
            raise Exception(f"Transcript unavailable for video {video_id}")

    def summarize_video_transcript(self, title: str, transcript: str) -> str:
        """
        Sends the transcript text to Gemini to generate summaries detailing macro indicators and stock recommendations.
        
        Args:
            title: Title of the video.
            transcript: Transcribed text or metadata description.
            
        Returns:
            Markdown bullet points summarizing the video.
        """
        if not self.api_key:
            return "No Gemini API key available. Summarization bypassed."

        logger.info(f"Requesting Gemini summary for video: '{title}'")
        
        # Enforce the strict requirements format
        prompt = f"""
You are an expert financial analyst. Analyze and summarize the following YouTube video transcript (or description) for market insights.
All responses must be written in Korean (모든 요약 내용은 한국어로 작성해 주세요).

Video Title: {title}

Transcript / Content:
{transcript}

Provide the summary strictly in the following Markdown format:

### 1. 시장 센티먼트 및 거시 지표
[전반적인 시장 분위기(매수 우위, 중립, 매도 우위 등)와 언급된 주요 거시 경제 지표(금리, 인플레이션, 연준 정책, 환율 등)를 한국어로 요약해 주세요.]

### 2. 추천 종목 및 섹터 (Buy/Long)
[매수 또는 보유를 추천하는 특정 섹터 및 종목(예: AAPL, 삼성전자)과 구체적인 추천 사유를 적어주세요. 없으면 "없음"이라고 적어주세요.]

### 3. 매도 및 주의 종목/섹터 (Sell/Avoid)
[매도, 숏 포지션, 또는 비중 축소 및 주의를 권고하는 특정 섹터 및 종목과 구체적인 사유를 적어주세요. 없으면 "없음"이라고 적어주세요.]

### 4. 핵심 요약 (Key Takeaways)
* [핵심 주장/결론에 대한 첫 번째 요약 포인트]
* [핵심 주장/결론에 대한 두 번째 요약 포인트]
* [핵심 주장/결론에 대한 세 번째 요약 포인트]
"""
        # Sequential processing delay to respect API limits (13.0 seconds for free tier 5 RPM)
        logger.info("Sleeping 13 seconds to respect Gemini API rate limits...")
        time.sleep(13.0)
        
        try:
            # Initialize model (gemini-2.5-flash is standard, fallback to gemini-1.5-flash)
            try:
                model = genai.GenerativeModel(self.model_name)
            except Exception:
                model = genai.GenerativeModel("gemini-2.5-flash")
                
            response = model.generate_content(prompt)
            summary_text = response.text.strip()
            logger.info(f"Successfully generated summary for video: '{title}'")
            return summary_text
        except Exception as e:
            logger.error(f"Gemini API call failed for video '{title}': {str(e)}")
            return f"Error generating summary: {str(e)}"

    def summarize_videos_batched(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Summarizes multiple video transcripts/contents in a single batched Gemini API call
        to conserve API requests and stay within free tier quotas.
        """
        if not self.api_key:
            for v in videos:
                v["llm_summary"] = "No Gemini API key available. Summarization bypassed."
            return videos

        if not videos:
            return []

        logger.info(f"Requesting single batched Gemini summary for {len(videos)} videos...")
        
        prompt = "You are an expert financial analyst. Analyze and summarize the following YouTube video transcripts (or descriptions) for market insights.\n\n"
        prompt += f"We have {len(videos)} videos to summarize. For each video, write a separate structured summary strictly matching the format below.\n\n"
        
        for i, v in enumerate(videos, 1):
            prompt += f"--- VIDEO {i} ---\n"
            prompt += f"Video ID: {v['video_id']}\n"
            prompt += f"Title: {v['title']}\n"
            prompt += f"Channel: {v['channel_handle']}\n"
            prompt += f"Content:\n{v.get('content', '')[:6000]}\n"  # limit length to avoid token limit
            prompt += "----------------\n\n"
            
        prompt += """
Provide the summaries strictly in Korean (모든 내용을 한국어로 작성해 주세요). Do NOT merge them. Wrap each video's summary with the exact start and end markers as shown below:

=== VIDEO_SUMMARY_START [video_id_here] ===
### 1. 시장 센티먼트 및 거시 지표
[전반적인 시장 분위기(매수 우위, 중립, 매도 우위 등)와 언급된 주요 거시 경제 지표(금리, 인플레이션, 연준 정책, 환율 등)를 한국어로 요약해 주세요.]

### 2. 추천 종목 및 섹터 (Buy/Long)
[매수 또는 보유를 추천하는 특정 섹터 및 종목과 구체적인 추천 사유를 적어주세요. 없으면 "없음"이라고 적어주세요.]

### 3. 매도 및 주의 종목/섹터 (Sell/Avoid)
[매도, 숏 포지션, 또는 비중 축소 및 주의를 권고하는 특정 섹터 및 종목과 구체적인 사유를 적어주세요. 없으면 "없음"이라고 적어주세요.]

### 4. 핵심 요약 (Key Takeaways)
* [첫 번째 요약 포인트]
* [두 번째 요약 포인트]
* [세 번째 요약 포인트]
=== VIDEO_SUMMARY_END [video_id_here] ===

Double check that the video_id in the markers matches the respective Video ID exactly.
"""
        # Delay before API call to stay under rate limits
        logger.info("Sleeping 13 seconds before calling Gemini batched API...")
        time.sleep(13.0)
        
        try:
            try:
                model = genai.GenerativeModel(self.model_name)
            except Exception:
                model = genai.GenerativeModel("gemini-2.5-flash")
                
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            logger.info("Successfully received batched video summaries from Gemini.")
            
            # Parse individual summaries
            summaries_dict = {}
            pattern = re.compile(
                r'===+ VIDEO_SUMMARY_START \[([^\]]+)\] ===+(.*?)===+ VIDEO_SUMMARY_END \[\1\] ===+',
                re.DOTALL
            )
            matches = pattern.findall(response_text)
            for vid_id, content in matches:
                summaries_dict[vid_id.strip()] = content.strip()
                
            # Assign summaries back
            for v in videos:
                vid_id = v["video_id"]
                if vid_id in summaries_dict:
                    v["llm_summary"] = summaries_dict[vid_id]
                else:
                    # Fallback parser if bracket matching failed or didn't output exactly
                    found = False
                    for parsed_id, content in summaries_dict.items():
                        if parsed_id in vid_id or vid_id in parsed_id:
                            v["llm_summary"] = content
                            found = True
                            break
                    if not found:
                        logger.warning(f"Could not find parsed summary for video {vid_id} in batched response.")
                        v["llm_summary"] = "Summary generation failed to parse in batched response."
                        
            return videos
        except Exception as e:
            logger.error(f"Batched Gemini video summarization failed: {str(e)}")
            for v in videos:
                v["llm_summary"] = f"Error generating summary: {str(e)}"
            return videos
