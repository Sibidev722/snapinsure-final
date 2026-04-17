"""
spaCy NLP Disruption Extraction Pipeline
----------------------------------------
Extracts structured event data from raw news text using NER and keyword heuristics.
"""

import spacy
from typing import Dict, Any

# Load the small English pipeline
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise RuntimeError("spaCy model not found. Please run: python -m spacy download en_core_web_sm")

# Keyword dictionaries for event typing and severity
HIGH_SEVERITY_KEYWORDS = {"strike", "shutdown", "riot", "violence", "explosion", "blockade"}
MEDIUM_SEVERITY_KEYWORDS = {"protest", "union", "block", "delay", "demonstration", "march"}

def extract_news_event(text: str) -> Dict[str, Any]:
    """
    Parses a single text blob (like a news article summary) to extract
    event_type, location, severity, and confidence score.
    """
    doc = nlp(text)
    
    locations = []
    # ── 1. NER for Location ──────────────────────────────────────────────────
    # Extract entities labeled as GPE (Geo-Political Entity), LOC (Location), or FAC (Facility)
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC", "FAC"):
            locations.append(ent.text)
            
    # Deduplicate while preserving order of discovery
    locations = list(dict.fromkeys(locations))
    primary_location = locations[0] if locations else "Unknown"
    
    # ── 2. Identify Event Type ───────────────────────────────────────────────
    text_lower = text.lower()
    event_type = "unknown"
    
    # Fallthrough heuristic for specific exact keywords
    if "strike" in text_lower:
        event_type = "strike"
    elif "protest" in text_lower or "demonstration" in text_lower or "march" in text_lower:
        event_type = "protest"
    elif "shutdown" in text_lower:
        event_type = "shutdown"
    elif "riot" in text_lower or "violence" in text_lower:
        event_type = "riot"
    elif "blockade" in text_lower or "block" in text_lower:
        event_type = "blockade"
    elif "union" in text_lower:
        event_type = "union action"
        
    # ── 3. Keyword-based Scoring for Severity & Confidence ───────────────────
    severity = "low"
    confidence = 0.3  # Base confidence level
    
    has_high = any(kw in text_lower for kw in HIGH_SEVERITY_KEYWORDS)
    has_med = any(kw in text_lower for kw in MEDIUM_SEVERITY_KEYWORDS)
    
    if has_high:
        severity = "high"
        confidence += 0.40
    elif has_med:
        severity = "medium"
        confidence += 0.25
        
    if primary_location != "Unknown":
        confidence += 0.15
        
    # Penalty if we couldn't actually identify what type of event it is
    if event_type == "unknown":
        confidence = 0.0
        
    # Cap confidence at 1.0 safely
    confidence = min(1.0, round(confidence, 2))
        
    return {
        "event_type": event_type,
        "location": primary_location,
        "severity": severity,
        "confidence": confidence
    }
