# backend/app/web_scraper.py

import requests
import logging
import re
from urllib.parse import urlparse, urljoin, quote_plus, unquote
from bs4 import BeautifulSoup, SoupStrainer
import brotli
import chardet
import random
from typing import List, Tuple, Dict, Any, Optional
from .config import config

# --- Helper Functions ---

def get_random_user_agent():
    return random.choice(config.USER_AGENTS)

def fix_url(url):
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = "https://" + url
        if not urlparse(url).netloc:
            return None
        return url.split("?")[0]
    except Exception:
        return None

def _decode_content(response: requests.Response) -> str:
    # Decodes response content, handling different encodings.
    try:
        detected_encoding = chardet.detect(response.content)['encoding'] or 'utf-8'
        return response.content.decode(detected_encoding, errors='replace')
    except (UnicodeDecodeError, Exception):
        return response.content.decode('latin-1', errors='replace')

# --- Scraping Functions ---

def scrape_google(search_query: str) -> List[str]:
    # Scrapes Google search results.
    search_results = []
    google_url = f"https://www.google.com/search?q={quote_plus(search_query)}&num=20"
    try:
        headers = {'User-Agent': get_random_user_agent()}
        response = requests.get(google_url, headers=headers, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
        only_results = SoupStrainer('div', class_='tF2Cxc')
        soup = BeautifulSoup(response.text, 'html.parser', parse_only=only_results)
        for result in soup.find_all('div', class_='tF2Cxc'):
            if link := result.find('a', href=True):
                if fixed_url := fix_url(link['href']):
                    search_results.append(fixed_url)
    except Exception as e:
        logging.error(f"Error scraping Google: {e}")
    return list(set(search_results))

def scrape_duckduckgo(search_query: str) -> List[str]:
    # Scrapes DuckDuckGo search results.
    search_results = []
    duck_url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}"
    try:
        response = requests.get(duck_url, headers={'User-Agent': get_random_user_agent()}, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
        only_results = SoupStrainer('a', class_='result__a')
        soup = BeautifulSoup(response.text, 'html.parser', parse_only=only_results)
        for a_tag in soup.find_all('a', class_='result__a', href=True):
            if fixed_url := fix_url(urljoin("https://html.duckduckgo.com/", a_tag['href'])):
                search_results.append(fixed_url)
    except Exception as e:
        logging.error(f"Error scraping DuckDuckGo: {e}")
    return list(set(search_results))


def scrape_bing(search_query: str) -> List[str]:
    # Scrapes Bing search results.
    search_results = []
    bing_url = f"https://www.bing.com/search?q={quote_plus(search_query)}"
    try:
        response = requests.get(bing_url, headers={'User-Agent': get_random_user_agent()}, timeout=config.REQUEST_TIMEOUT)
        response.raise_for_status()
        only_results = SoupStrainer('li', class_='b_algo')
        soup = BeautifulSoup(response.text, 'html.parser', parse_only=only_results)
        for li in soup.find_all('li', class_='b_algo'):
            if a_tag := li.find('a', href=True):
                if fixed_url := fix_url(a_tag['href']):
                    search_results.append(fixed_url)
    except Exception as e:
        logging.error(f"Error scraping Bing: {e}")
    return list(set(search_results))


def scrape_search_engine(search_query: str, engine_name: str) -> List[str]:
    # Scrapes search results from a specified search engine.
    scrapers = {
        "google": scrape_google,
        "duckduckgo": scrape_duckduckgo,
        "bing": scrape_bing,
    }
    if scraper := scrapers.get(engine_name):
        return scraper(search_query)
    logging.warning(f"Unknown search engine: {engine_name}")
    return []

def fetch_page_content(url: str, snippet_length: Optional[int] = None) -> Tuple[List[str], List[str]]:
    # Fetches and cleans content from a URL.
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
        
        title = soup.title.string if soup.title else url
        formatted_snippet = f"### {title}\n\n{text[:snippet_length]}\n"
        
        content_snippets.append(formatted_snippet)
        references.append(url)
            
    except Exception as e:
        logging.error(f"Request error fetching {url}: {e}")
        
    return content_snippets, references