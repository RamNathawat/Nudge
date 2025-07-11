# backend/app/web_scraper.py

import requests
import logging
import re
from bs4 import BeautifulSoup
import chardet
from typing import List, Tuple, Optional
from .config import config
import os
from serpapi import GoogleSearch # Import the new library

# --- Setup ---
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def get_random_user_agent():
    """Returns a standard user agent for fetching page content."""
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def _decode_content(response: requests.Response) -> str:
    """Decodes response content, handling different encodings."""
    try:
        detected_encoding = chardet.detect(response.content)['encoding'] or 'utf-8'
        return response.content.decode(detected_encoding, errors='replace')
    except (UnicodeDecodeError, Exception):
        return response.content.decode('latin-1', errors='replace')

# --- NEW, ROBUST SCRAPING FUNCTION ---
def scrape_search_engine(search_query: str, engine_name: str = "google") -> List[str]:
    """
    Uses SerpApi to reliably fetch search results, avoiding blocks and HTML parsing.
    """
    if not SERPAPI_KEY:
        logging.error("SERPAPI_KEY not found in environment variables. Web scraping will fail.")
        return []

    params = {
        "q": search_query,
        "api_key": SERPAPI_KEY,
        "engine": "google",
        "num": "10" # Get top 10 results
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Extract links from the structured JSON response
        if "organic_results" in results:
            logging.info(f"Successfully fetched {len(results['organic_results'])} results from SerpApi for query: '{search_query}'")
            return [result["link"] for result in results["organic_results"] if "link" in result]

    except Exception as e:
        logging.error(f"Error scraping with SerpApi for query '{search_query}': {e}")

    return []

# --- Page Content Fetching (This function remains to fetch the content from the URLs found) ---
def fetch_page_content(url: str, snippet_length: Optional[int] = None) -> Tuple[List[str], List[str]]:
    """Fetches and cleans content from a URL."""
    if snippet_length is None:
        snippet_length = config.DEEP_RESEARCH_SNIPPET_LENGTH
    
    content_snippets = []
    references = []
    
    try:
        response = requests.get(url, headers={'User-Agent': get_random_user_agent()}, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
        
        page_text = _decode_content(response)
        soup = BeautifulSoup(page_text, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'[\ud800-\udbff\udc00-\udfff]', '', text)
        
        title = soup.title.string.strip() if soup.title else url
        formatted_snippet = f"### {title}\n\n{text[:snippet_length]}\n"
        
        content_snippets.append(formatted_snippet)
        references.append(url)
            
    except Exception as e:
        logging.error(f"Request error fetching {url}: {e}")
        
    return content_snippets, references