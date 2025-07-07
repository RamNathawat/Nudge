# backend/app/config.py

import os

class Config:
    # --- General ---
    API_KEY = os.getenv("GEMINI_API_KEY")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    MAX_WORKERS = 10
    REQUEST_TIMEOUT = 60

    # --- Caching ---
    CACHE_ENABLED = True
    CACHE = {}
    CACHE_TIMEOUT = 300 # 5 minutes

    # --- Scraping ---
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    ]
    SEARCH_ENGINES = ["google", "duckduckgo", "bing"]
    JOB_SEARCH_ENGINES = ["linkedin", "indeed"]

    # --- Research Prompts & Models ---
    DEEP_RESEARCH_SNIPPET_LENGTH = 10000
    MAX_TOKENS_PER_CHUNK = 25000
    JOB_RELEVANCE_MODEL = os.getenv("JOB_RELEVANCE_MODEL", "gemini-1.5-flash")
    DEFAULT_DEEP_RESEARCH_MODEL = "gemini-1.5-flash"

    DEEP_RESEARCH_SUMMARY_PROMPT = (
        "Analyze snippets for: '{query}'. Extract key facts, figures, and insights. "
        "Be concise, ignore irrelevant content, and prioritize authoritative sources. "
        "Focus on the main topic and avoid discussing the research process itself.\n\nContent Snippets:"
    )
    DEEP_RESEARCH_REPORT_PROMPT = (
        "DEEP RESEARCH REPORT: Synthesize a comprehensive report from web research on: '{search_query}'.\n\n"
        "{report_structure}\n\n"
        "Research Summaries (all iterations):\n{summaries}\n\n"
        "Generate the report in Markdown."
    )
    DEEP_RESEARCH_REFINEMENT_PROMPT = (
        "Analyze the following research summaries to identify key themes and entities. "
        "Suggest 3-5 new, more specific search queries that are *directly related* to the original topic: '{original_query}'. "
        "Identify any gaps in the current research and suggest queries to address those gaps."
    )

config = Config()