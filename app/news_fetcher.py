import urllib.parse
import requests
from bs4 import BeautifulSoup
from typing import List, TypedDict, Optional
from app.utils.helpers import retry_api_call
from app.utils.logger import setup_logger

logger = setup_logger("news_fetcher", "logs/app.log")

class NewsItem(TypedDict):
    """Single financial or macro news item"""
    title: str
    link: str
    pub_date: str
    source: str
    summary: str

class NewsFetcher:
    """
    Scrapes and filters financial news headlines and metadata using Google News RSS channels
    to bypass page-scraping blocks.
    """
    
    def __init__(self, user_agent: Optional[str] = None) -> None:
        self.headers = {"User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    @retry_api_call(max_retries=3, initial_delay=2.0, backoff_factor=2.0)
    def fetch_query_news(self, query: str, limit: int = 10) -> List[NewsItem]:
        """
        Queries RSS news feeds for topics matching keywords.
        
        Args:
            query: Term to search for (e.g. "S&P 500", "US Fed inflation").
            limit: Maximum news items to return.
            
        Returns:
            List of NewsItem typed dictionaries containing titles, links, and summaries.
        """
        logger.info(f"Querying Google News RSS for keyword: '{query}' (limit: {limit})")
        encoded_query = urllib.parse.quote(query)
        # Use Standard Google News RSS Search URL format
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # Use BeautifulSoup to parse the RSS XML structure
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
            
            news_list: List[NewsItem] = []
            for item in items[:limit]:
                title = item.find("title").text if item.find("title") else ""
                link = item.find("link").text if item.find("link") else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") else ""
                
                # Parse source element
                source_elem = item.find("source")
                source = source_elem.text if source_elem else "Unknown"
                
                # Parse description/summary element and strip HTML
                desc_elem = item.find("description")
                summary = ""
                if desc_elem:
                    desc_soup = BeautifulSoup(desc_elem.text, "html.parser")
                    summary = desc_soup.get_text().strip()
                
                # Refine title and source if format is "Headline - Source Name"
                actual_title = title
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    actual_title = parts[0].strip()
                    if source == "Unknown":
                        source = parts[1].strip()
                
                news_list.append({
                    "title": actual_title,
                    "link": link,
                    "pub_date": pub_date,
                    "source": source,
                    "summary": summary
                })
                
            logger.info(f"Successfully fetched {len(news_list)} news items for query: '{query}'")
            return news_list
        except Exception as e:
            logger.error(f"Error occurred in fetch_query_news for query '{query}': {str(e)}")
            raise ConnectionError(f"Failed to fetch news RSS for query: {query}. Error: {str(e)}")
