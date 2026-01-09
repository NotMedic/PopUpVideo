from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from datetime import datetime
import re
import requests

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
FACTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'facts')
GROK_API_KEY = os.environ.get('GROK_API_KEY', '')  # Set via environment variable
GROK_API_URL = 'https://api.x.ai/v1/chat/completions'

# Ensure facts directory exists
os.makedirs(FACTS_DIR, exist_ok=True)


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
            'full_title': clean_title
        }
    elif '|' in clean_title:
        parts = clean_title.split('|', 1)
        return {
            'artist': parts[0].strip(),
            'song': parts[1].strip(),
            'full_title': clean_title
        }
    
    # Fallback - couldn't parse, return as-is
    return {
        'artist': 'Unknown',
        'song': clean_title,
        'full_title': clean_title
    }


def generate_facts_with_grok(artist, song, title):
    """
    Call Grok API to generate Pop Up Video style facts.
    """
    if not GROK_API_KEY:
        # Fallback for testing without API key
        return [
            {"time": 10, "text": f"This is {artist} - {song}!"},
            {"time": 30, "text": "Pop Up Video facts coming soon!"},
            {"time": 60, "text": "Set your GROK_API_KEY environment variable to generate real facts."}
        ]
    
    prompt = f"""You are generating fun facts for a "Pop Up Video" style experience for the music video: "{title}" by {artist}.

Generate exactly 15-20 interesting, surprising, or entertaining facts about this song, music video, artist, or the era it was made in. Facts should be:
- Short (1-2 sentences max)
- Entertaining and surprising
- In the style of VH1's Pop Up Video (quirky, fun, unexpected trivia)
- Factually accurate
- Timed throughout the video (assume a 3-5 minute video)

Format your response as a JSON array ONLY (no other text) with this structure:
[
  {{"time": 10, "text": "First fact here"}},
  {{"time": 25, "text": "Second fact here"}},
  ...
]

Distribute the timing evenly from 10 seconds to 280 seconds. Make the facts engaging!"""

    try:
        response = requests.post(
            GROK_API_URL,
            headers={
                'Authorization': f'Bearer {GROK_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'grok-2-1212',
                'messages': [
                    {'role': 'system', 'content': 'You are a Pop Up Video fact generator. Always respond with valid JSON only.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.8,
                'max_tokens': 2000
            },
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Extract the generated facts
        content = result['choices'][0]['message']['content']
        
        # Try to parse JSON from the response
        # Sometimes LLMs wrap JSON in markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        facts = json.loads(content)
        
        # Validate structure
        if not isinstance(facts, list):
            raise ValueError("Facts must be a list")
        
        for fact in facts:
            if not isinstance(fact, dict) or 'time' not in fact or 'text' not in fact:
                raise ValueError("Invalid fact structure")
        
        return facts
        
    except Exception as e:
        print(f"Error calling Grok API: {e}")
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
        
        # Parse video title
        parsed = parse_video_title(title)
        
        # Generate facts using Grok
        print(f"Generating facts for: {parsed['artist']} - {parsed['song']}")
        facts = generate_facts_with_grok(parsed['artist'], parsed['song'], parsed['full_title'])
        
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
    print(f"Grok API Key set: {'Yes' if GROK_API_KEY else 'No (using fallback)'}")
    print("=" * 60)
    print("\nStarting server on http://localhost:5000")
    print("Endpoints:")
    print("  GET  /health")
    print("  POST /generate-facts")
    print("  GET  /list-facts")
    print("=" * 60)
    app.run(debug=True, port=5000)
