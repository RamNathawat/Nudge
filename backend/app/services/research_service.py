# backend/app/services/research_service.py

import logging
import concurrent.futures
from typing import List

from app.web_scraper import scrape_search_engine, fetch_page_content
from app.config import config
from app.utils import generate_gemini_response

logger = logging.getLogger(__name__)

def _get_refined_queries(summaries: list, original_query: str) -> List[str]:
    """Uses an LLM to generate new, more specific search queries based on initial findings."""
    if not summaries:
        return []
    
    # Use the DEEP_RESEARCH_REFINEMENT_PROMPT from the config
    refinement_prompt = config.DEEP_RESEARCH_REFINEMENT_PROMPT.format(
        original_query=original_query,
        summaries="\n\n".join(summaries)
    )
    
    refined_queries_str = generate_gemini_response(refinement_prompt)
    # Clean up the list of queries
    return [q.strip("- ") for q in refined_queries_str.split('\n') if q.strip()]

def perform_deep_research(topic: str) -> str:
    """
    The centralized, mastery-level deep research function.
    Performs a multi-loop, query-refining search to gather comprehensive context.
    Returns a single, rich text corpus.
    """
    logger.info(f"🔬 [Research Service] Starting deep dive for topic: '{topic}'")
    
    all_text_content = ""
    all_summaries = []
    all_references = set()
    current_queries = [topic]

    # Perform 2 loops of research: one broad, one deep
    for i in range(2): 
        logger.info(f"--- Research Loop {i+1} for topic '{topic}' ---")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            # Scrape for all current queries
            search_futures = {executor.submit(scrape_search_engine, query, "google"): query for query in current_queries}
            
            for future in concurrent.futures.as_completed(search_futures):
                urls = future.result()
                all_references.update(urls)

    # Fetch content from all unique URLs found
    unique_urls = list(all_references)
    logger.info(f"📚 Found {len(unique_urls)} unique URLs. Fetching content...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        # Limit to 15 pages for a mastery-level deep dive
        fetch_futures = {executor.submit(fetch_page_content, url): url for url in unique_urls[:15]}
        for future in concurrent.futures.as_completed(fetch_futures):
            snippets, _ = future.result()
            if snippets:
                all_text_content += "\n\n".join(snippets)
                # Create a summary of the snippet for the next loop's query refinement
                if len(all_summaries) < 5: # Limit summaries to keep it efficient
                    summary_prompt = config.DEEP_RESEARCH_SUMMARY_PROMPT.format(query=topic) + "\n\n" + "\n".join(snippets)
                    summary = generate_gemini_response(summary_prompt)
                    all_summaries.append(summary)

        # After the first loop, refine the queries for the second loop
        if i == 0 and all_summaries:
            logger.info("Refining search queries for deep dive...")
            new_queries = _get_refined_queries(all_summaries, topic)
            if new_queries:
                # Add new queries, but don't replace the original topic
                current_queries.extend(new_queries)
                current_queries = list(set(current_queries)) # Remove duplicates
                logger.info(f"New queries for deep dive: {current_queries}")

    logger.info(f"🔬 [Research Service] Completed deep dive for '{topic}'. Returning {len(all_text_content.split())} words.")
    return all_text_content