import json
from openai import OpenAI
from typing import List, Dict, Optional
from api_service.config.logger_manager import LoggerManager
from api_service.config.config import load_env_vars

logger = LoggerManager.get_logger("LLMService")

def get_llm_client() -> Optional[OpenAI]:
    """Initialize and return the OpenAI client if configured."""
    config = load_env_vars()
    api_key = config.get('OPENAI_API_KEY')
    base_url = config.get('OPENAI_BASE_URL') # Optional for proxy/alternative setups
    
    if not api_key:
        logger.warning("OPENAI_API_KEY is not configured. LLM recommendations will be disabled.")
        return None
        
    try:
        # Pass base_url only if it exists
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
            
        client = OpenAI(**client_kwargs)
        return client
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        return None

def get_recommendations_from_history(history_items: List[Dict], max_results: int = 5, item_type: str = "movie") -> List[Dict]:
    """
    Generate recommendations based on a user's watch history using an LLM.
    
    Args:
        history_items: List of dictionaries containing watched items (must have 'title' and ideally 'year')
        max_results: Number of recommendations to generate
        item_type: 'movie' or 'tv'
        
    Returns:
        List of dictionaries with 'title' and 'year' of recommended items.
    """
    client = get_llm_client()
    if not client:
        logger.info("Falling back to standard algorithms (LLM not configured).")
        return []
        
    if not history_items:
        logger.info("No history provided for LLM recommendations.")
        return []
        
    config = load_env_vars()
    model = config.get('LLM_MODEL', 'gpt-4o-mini') # Default to a fast/cheap model
    
    # Format the history into a string
    history_strings = []
    for item in history_items:
        title = item.get("title", item.get("name", "Unknown Title"))
        year = item.get("year", "Unknown Year")
        history_strings.append(f"- {title} ({year})")
        
    history_text = "\n".join(history_strings)
    list_type = "movies" if item_type == "movie" else "TV shows"
    
    prompt = f"""You are an expert film and television recommendation system.
The user has recently watched and enjoyed the following {list_type}:

{history_text}

Analyze the themes, genres, pacing, and tone of these {list_type} to build a taste profile.
Based on this profile, recommend exactly {max_results} similar {list_type} that the user is highly likely to enjoy.

Follow these strict rules:
1. Do NOT recommend any of the {list_type} that the user has already watched (listed above).
2. ONLY respond with a valid JSON array of objects.
3. Each object MUST have a "title" string field, a "year" integer field, and a "rationale" string field explaining why it was chosen based on the user's history.
4. Do NOT wrap the JSON in markdown code blocks. Do not add any conversational text.

Example format:
[
  {{"title": "Example Movie", "year": 2023, "rationale": "Because you enjoyed X and Y, this movie shares similar themes..."}},
  {{"title": "Another Great Catch", "year": 1999, "rationale": "A classic in the same genre as Z..."}}
]
"""

    try:
        logger.info(f"Sending LLM request to OpenAI ({model}) for {len(history_items)} {list_type} history items.")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a specialized system that only outputs raw JSON arrays of media recommendations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            # If using API that supports strict JSON mode
            response_format={ "type": "json_object" } if model in ['gpt-4-1106-preview', 'gpt-3.5-turbo-1106', 'gpt-4o', 'gpt-4o-mini'] else None
        )
        
        content = response.choices[0].message.content.strip()
        
        # If the LLM still wrapped it in markdown despite instructions, clean it up
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        content = content.strip()
        
        # Parse the JSON
        # Some models return `{"recommendations": [{...}]}` when forced into json_object mode
        parsed_json = json.loads(content)
        
        recommendations = []
        if isinstance(parsed_json, list):
            recommendations = parsed_json
        elif isinstance(parsed_json, dict):
            # Try to grab the first list value found in the dict
            for key, val in parsed_json.items():
                if isinstance(val, list):
                    recommendations = val
                    break
                    
        # Create a set of lowercased history titles for easy comparison
        watched_titles = {
            (item.get("title") or item.get("name") or "").lower() 
            for item in history_items
        }

        # Filter and validate
        valid_recommendations = []
        for rec in recommendations:
            if isinstance(rec, dict) and "title" in rec and "year" in rec:
                rec_title = rec["title"].lower()
                
                # Check for exact or highly similar substring matches to strictly enforce the "no watched items" rule
                is_duplicate = any(
                    watched in rec_title or rec_title in watched 
                    for watched in watched_titles if watched
                )

                if is_duplicate:
                    logger.info(f"Filtered out duplicate recommendation already in watch history: {rec['title']}")
                    continue

                valid_recommendations.append(rec)
                rationale = rec.get("rationale", "No rationale provided by LLM.")
                logger.info(f"[{rec['title']} ({rec['year']})] LLM Rationale: {rationale}")
                
        logger.info(f"Successfully generated {len(valid_recommendations)} LLM recommendations.")
        # Limit to max_results safely
        final_recs = []
        for i, rec in enumerate(valid_recommendations):
            if i >= max_results:
                break
            final_recs.append(rec)
            
        return final_recs
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON. Raw response: {content}")
        return []
    except Exception as e:
        logger.error(f"Error communicating with LLM API: {str(e)}")
        return []
