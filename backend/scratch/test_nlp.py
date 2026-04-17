import asyncio
import os
import sys

# Add the backend directory to sys.path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
env_path = os.path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path)

print(f"DEBUG: NEWS_API_KEY loaded: {bool(os.getenv('NEWS_API_KEY'))}")
print(f"DEBUG: GNEWS_API_KEY loaded: {bool(os.getenv('GNEWS_API_KEY'))}")

async def test_nlp_pipeline():
    print("\n--- Testing NLP & News Pipeline ---")
    try:
        from services.news_fetcher_service import news_fetcher_service
        from services.spacy_nlp_pipeline import extract_news_event
        from services.event_mapper_service import event_mapper
        
        # 1. Test News Fetching
        city = "Chennai"
        print(f"\n[1] Fetching live news for {city}...")
        fetch_result = await news_fetcher_service.fetch_and_store_news(city)
        print(f"Fetch success: {fetch_result.get('success')}")
        print(f"Articles inserted/found: {fetch_result.get('inserted', 0)}")
        
        articles = fetch_result.get('articles', [])
        
        if not articles:
            # If no live articles found today, let's mock one to test the spaCy/Mapper logic
            print("\n[!] No live articles found for today. Injecting mock article for pipeline testing...")
            articles = [{
                "title": "Large scale protest in Anna Nagar over fuel prices",
                "description": "Traffic blocked as union members shutdown main roads in central Chennai."
            }]

        # 2. Test NLP Extraction
        print("\n[2] Running spaCy NLP Extraction on first article...")
        article = articles[0]
        text_blob = f"{article.get('title')} {article.get('description')}"
        print(f"Text: {text_blob}")
        
        nlp_result = extract_news_event(text_blob)
        print(f"NLP Output: {nlp_result}")
        
        # 3. Test Event Mapping
        print("\n[3] Mapping event to city zones...")
        mapped_result = await event_mapper.map_and_store_event(nlp_result)
        print(f"Mapped Result: {mapped_result}")
        
        print("\n--- NLP Pipeline Test Completed Successfully ---")
        
    except Exception as e:
        print(f"\n[ERROR] NLP test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_nlp_pipeline())
