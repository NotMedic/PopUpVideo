from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from datetime import datetime
import re
from xai_sdk import Client
from xai_sdk.chat import system, user
from pydantic import BaseModel, Field
from typing import List

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
FACTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'facts')
GROK_API_KEY = os.environ.get('GROK_API_KEY', '') or os.environ.get('XAI_API_KEY', '')
GROK_MODEL = os.environ.get('GROK_MODEL', 'grok-4-1-fast-reasoning')

# Ensure facts directory exists
os.makedirs(FACTS_DIR, exist_ok=True)

# Pydantic models for structured output
class Fact(BaseModel):
    """A single Pop Up Video fact with timing"""
    time: int = Field(ge=0, le=600, description="Time in seconds when the fact should appear (0-600)")
    text: str = Field(min_length=10, max_length=250, description="The fact text (10-250 characters)")

class FactsList(BaseModel):
    """Collection of Pop Up Video facts"""
    facts: List[Fact] = Field(min_length=15, max_length=25, description="List of 15-25 facts")


# Initialize xAI SDK client
xai_client = None
try:
    if GROK_API_KEY:
        xai_client = Client(api_key=GROK_API_KEY)
        print("✅ xAI SDK client initialized")
    else:
        print("⚠️ No GROK_API_KEY or XAI_API_KEY found - using fallback mode")
except Exception as e:
    print(f"⚠️ Failed to initialize xAI client: {e}")


def is_likely_music_video(title):
    """
    Check if the video title looks like a music video.
    Returns (is_music_video, reason)
    """
    # Music video indicators
    music_indicators = [
        r'\(Official\s*(Video|Music\s*Video|Audio|MV)\)',
        r'\[Official\s*(Video|Music\s*Video|Audio|MV)\]',
        r'\(Lyric\s*Video\)',
        r'\[Lyric\s*Video\]',
        r' - (Official|Lyric|Music)\s*(Video|Audio)',
        r'(Official|Lyric)\s*Video',
        r'\bMV\b',
        r'\bOfficial\s*Audio\b'
    ]
    
    # Non-music video indicators (skip these)
    non_music_indicators = [
        r'\b(Tutorial|How\s*to|Guide|Review|Unboxing|Vlog|Interview|Podcast|Gameplay|Walkthrough)\b',
        r'\b(Trailer|Teaser|Behind\s*the\s*Scenes|BTS|Making\s*of)\b',
        r'\b(Ep\s*\d+|Episode\s*\d+|Season\s*\d+|S\d+E\d+)\b',  # TV shows
        r'\b(Part\s*\d+|#\d+)\b',  # Multi-part videos
        r'\b(Live\s*Stream|Streaming)\b',
        r'\b(News|Documentary|Lecture|Sermon)\b'
    ]
    
    # Check for non-music indicators first (highest priority)
    for pattern in non_music_indicators:
        if re.search(pattern, title, re.IGNORECASE):
            return False, f"Contains non-music keyword: {pattern}"
    
    # Check for strong music indicators
    for pattern in music_indicators:
        if re.search(pattern, title, re.IGNORECASE):
            return True, "Contains music video keywords"
    
    # Check for artist - song format (common for music videos)
    if ' - ' in title:
        parts = title.split(' - ')
        # If we have 2 parts and they're reasonable lengths, likely music
        if len(parts) == 2 and 2 <= len(parts[0]) <= 50 and 2 <= len(parts[1]) <= 100:
            return True, "Has artist - song format"
    
    # Check for common music-related words
    music_words = r'\b(feat\.|ft\.|featuring|remix|cover|acoustic|live|performance)\b'
    if re.search(music_words, title, re.IGNORECASE):
        return True, "Contains music-related terms"
    
    # Default: assume it might be music (be permissive)
    return True, "No clear non-music indicators"


def parse_video_title(title):
    """
    Extract artist and song from YouTube video title.
    Handles common formats like:
    - "Artist - Song Title"
    - "Song Title - Artist"
    - "Artist - Song (Official Video)"
    """
    # Remove common YouTube suffixes
    clean_title = re.sub(r'\s*\((Official|Lyric|Music)?\s*(Video|Audio|MV|HD|4K)\)', '', title, flags=re.IGNORECASE)
    clean_title = re.sub(r'\s*\[(Official|Lyric|Music)?\s*(Video|Audio|MV|HD|4K)\]', '', clean_title, flags=re.IGNORECASE)
    clean_title = clean_title.strip()
    
    # Try to split on common delimiters
    if ' - ' in clean_title:
        parts = clean_title.split(' - ', 1)
        return {
            'artist': parts[0].strip(),
            'song': parts[1].strip(),
            'full_title': clean_title,
            'is_music': True
        }
    elif '|' in clean_title:
        parts = clean_title.split('|', 1)
        return {
            'artist': parts[0].strip(),
            'song': parts[1].strip(),
            'full_title': clean_title,
            'is_music': True
        }
    
    # Fallback - couldn't parse artist/song clearly
    return {
        'artist': 'Unknown',
        'song': clean_title,
        'full_title': clean_title,
        'is_music': False  # Unclear format
    }


def generate_facts_with_grok(artist, song, title, video_id):
    """
    Call Grok API using xAI SDK with Pydantic validation.
    """
    if not xai_client:
        # Fallback for testing without API key
        return [
            {"time": 10, "text": f"This is {artist} - {song}!"},
            {"time": 30, "text": "Pop Up Video facts coming soon!"},
            {"time": 60, "text": "Set your GROK_API_KEY environment variable to generate real facts."}
        ]
    
    prompt = f"""Generate 15-20 interesting, surprising Pop Up Video style facts for: "{title}" by {artist}.

YouTube Video ID: {video_id}
(You may have this video indexed - use any knowledge about this specific video to enhance accuracy)

Facts should be:
- Short (1-2 sentences max)
- Entertaining and surprising
- In the style of VH1's Pop Up Video (quirky, fun, unexpected trivia)
- Factually accurate about the song, music video, artist, or the era
- Relevant to the scene at the time they're popped up in the music video

Distribute timing evenly from 10 seconds to 280 seconds throughout a typical 3-5 minute music video.

Return ONLY valid JSON matching this structure:
{{
  "facts": [
    {{"time": 10, "text": "First fact..."}},
    {{"time": 25, "text": "Second fact..."}},
    ...
  ]
}}"""

    try:
        print(f"🌐 Generating facts using xAI SDK...")
        
        # Use xAI SDK to generate facts
        chat = xai_client.chat.create(model=GROK_MODEL)
        chat.append(system("You are a Pop Up Video fact generator. Always respond with valid JSON matching the exact structure requested."))
        chat.append(user(prompt))
        
        # Get the response
        response = chat.sample()
        content = response.content
        
        print(f"✅ Received response from Grok ({len(content)} chars)")
        
        # Clean up markdown code blocks if present
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        # Parse and validate with Pydantic
        facts_list = FactsList.model_validate_json(content)
        
        print(f"✅ Generated {len(facts_list.facts)} facts successfully")
        
        # Convert Pydantic objects to dicts
        facts = [{"time": fact.time, "text": fact.text} for fact in facts_list.facts]
        return facts
        
    except Exception as e:
        print(f"❌ Error calling Grok API: {e}")
        # Fallback facts
        return [
            {"time": 10, "text": f"Error generating facts: {str(e)}"},
            {"time": 30, "text": f"Playing: {artist} - {song}"}
        ]


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'PopUpVideo Facts Generator'})


@app.route('/generate-facts', methods=['POST'])
def generate_facts():
    """
    Generate facts for a video.
    Expects JSON: {"video_id": "...", "title": "..."}
    """
    try:
        data = request.get_json()
        video_id = data.get('video_id', '')
        title = data.get('title', '')
        
        if not video_id or not title:
            return jsonify({'error': 'Missing video_id or title'}), 400
        
        # Check if facts already exist
        facts_file = os.path.join(FACTS_DIR, f'{video_id}.json')
        if os.path.exists(facts_file):
            with open(facts_file, 'r', encoding='utf-8') as f:
                existing_facts = json.load(f)
            return jsonify({
                'source': 'cache',
                'data': existing_facts
            })
        
        # Check if this looks like a music video
        is_music, reason = is_likely_music_video(title)
        print(f"🎵 Music video check: {is_music} - {reason}")
        
        if not is_music:
            print(f"⏭️  Skipping non-music video: {title}")
            return jsonify({
                'source': 'skipped',
                'reason': 'Not detected as a music video',
                'detail': reason,
                'data': None
            }), 200  # Return 200 so TamperMonkey doesn't show error
        
        # Parse video title
        parsed = parse_video_title(title)
        
        # Double-check parsing quality
        if not parsed['is_music'] and parsed['artist'] == 'Unknown':
            print(f"⚠️  Unclear music video format: {title}")
            return jsonify({
                'source': 'skipped',
                'reason': 'Unable to parse artist/song from title',
                'detail': 'Title format unclear',
                'data': None
            }), 200
        
        # Generate facts using Grok
        print(f"Generating facts for: {parsed['artist']} - {parsed['song']} (ID: {video_id})")
        facts = generate_facts_with_grok(parsed['artist'], parsed['song'], parsed['full_title'], video_id)
        
        # Create facts object
        facts_data = {
            'videoId': video_id,
            'title': parsed['full_title'],
            'artist': parsed['artist'],
            'song': parsed['song'],
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'facts': facts
        }
        
        # Save to file
        with open(facts_file, 'w', encoding='utf-8') as f:
            json.dump(facts_data, f, indent=2, ensure_ascii=False)
        
        print(f"Facts saved to: {facts_file}")
        
        return jsonify({
            'source': 'generated',
            'data': facts_data
        })
        
    except Exception as e:
        print(f"Error in generate_facts: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/list-facts', methods=['GET'])
def list_facts():
    """List all cached fact files."""
    try:
        files = [f.replace('.json', '') for f in os.listdir(FACTS_DIR) if f.endswith('.json')]
        return jsonify({'count': len(files), 'video_ids': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("Pop Up Video Facts Generator - Backend Server")
    print("=" * 60)
    print(f"Facts directory: {FACTS_DIR}")
    print(f"xAI SDK client: {'✅ Initialized' if xai_client else '❌ Not available (using fallback)'}")
    print(f"Model: {GROK_MODEL}")
    print("=" * 60)
    print("\nStarting server on http://localhost:5000")
    print("Endpoints:")
    print("  GET  /health")
    print("  POST /generate-facts")
    print("  GET  /list-facts")
    print("=" * 60)
    app.run(debug=True, port=5000)
