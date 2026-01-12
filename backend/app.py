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
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
FACTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'facts')
GROK_API_KEY = os.environ.get('GROK_API_KEY', '') or os.environ.get('XAI_API_KEY', '')
GROK_MODEL = os.environ.get('GROK_MODEL', 'grok-4-1-fast-non-reasoning')

# Ensure facts directory exists
os.makedirs(FACTS_DIR, exist_ok=True)

# Pydantic models for structured output
class Fact(BaseModel):
    """A single Pop Up Video fact with timing"""
    time: int = Field(ge=0, le=600, description="Time in seconds when the fact should appear (0-600)")
    text: str = Field(min_length=10, max_length=250, description="The fact text (10-250 characters)")

class FactsList(BaseModel):
    """Collection of Pop Up Video facts"""
    facts: List[Fact] = Field(min_length=1, max_length=50, description="List of 1-50 facts")


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


def fetch_youtube_transcript(video_id):
    """
    Fetch transcript/captions from YouTube using youtube-transcript-api.
    Returns list of dicts with 'start', 'duration', and 'text' keys.
    Returns None if no transcript is available.
    """
    try:
        print(f"📝 Fetching transcript for video: {video_id}")
        
        # Create API instance
        ytt_api = YouTubeTranscriptApi()
        
        # Get list of available transcripts
        transcript_list = ytt_api.list(video_id)
        
        # Try manual (human-made) English transcript first
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
            print(f"✅ Found manually created English transcript")
        except:
            # Fall back to auto-generated English
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
                print(f"✅ Found auto-generated English transcript")
            except:
                # Try any English transcript
                transcript = transcript_list.find_transcript(['en'])
                print(f"✅ Found English transcript")
        
        # Fetch the actual transcript data
        fetched_transcript = transcript.fetch()
        
        # Convert to raw data (list of dicts)
        raw_data = fetched_transcript.to_raw_data()
        
        # Format the transcript
        formatted_transcript = []
        for entry in raw_data:
            formatted_transcript.append({
                'start': int(entry['start']),  # Round to integer seconds
                'duration': entry['duration'],
                'text': entry['text']
            })
        
        print(f"✅ Transcript fetched: {len(formatted_transcript)} entries")
        return formatted_transcript
        
    except TranscriptsDisabled:
        print(f"⚠️  Transcripts are disabled for video: {video_id}")
        return None
    except NoTranscriptFound:
        print(f"⚠️  No English transcript found for video: {video_id}")
        return None
    except Exception as e:
        print(f"⚠️  Error fetching transcript: {e}")
        return None


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


def generate_general_facts_with_grok(title, video_id, duration=None, description=None, transcript=None):
    """
    Generate Pop Up Video style facts for any video type (non-music).
    """
    if not xai_client:
        return [
            {"time": 10, "text": f"Watching: {title}"},
            {"time": 30, "text": "Pop Up Video facts coming soon!"},
            {"time": 60, "text": "Set your GROK_API_KEY environment variable to generate real facts."}
        ]
    
    # Calculate fact timing based on video duration
    if duration and duration > 0:
        end_time = int(duration) - 10
        num_facts = max(10, min(25, int(duration / 15)))
        timing_instruction = f"Distribute timing evenly from 10 seconds to {end_time} seconds. Generate approximately {num_facts} facts."
    else:
        timing_instruction = "Distribute timing evenly from 10 seconds to 280 seconds. Generate 10-20 facts."
    
    description_context = f"\nVideo Description: {description[:500]}..." if description and len(description) > 20 else ""
    
    # Format transcript for prompt (if available)
    transcript_context = ""
    if transcript and len(transcript) > 0:
        # Summarize transcript to keep prompt size manageable
        transcript_lines = []
        for i, entry in enumerate(transcript):
            if i % 3 == 0 or i < 10 or i > len(transcript) - 10:  # Sample: first 10, last 10, and every 3rd
                transcript_lines.append(f"[{entry['start']}s] {entry['text']}")
            if len(transcript_lines) >= 50:  # Limit to 50 entries
                break
        transcript_context = f"\n\nTranscript/Captions (sampled):\n" + "\n".join(transcript_lines[:50])
    
    prompt = f"""Generate interesting Pop Up Video style facts for this YouTube video:

Title: "{title}"
YouTube Video ID: {video_id}
Video Duration: {int(duration) if duration else 'unknown'} seconds{description_context}{transcript_context}

Analyze the title, description, and transcript to identify:
- Main subjects (people, products, places, events)
- Key topics or themes discussed
- Any recognizable entities
- What's being talked about at different timestamps

Generate fun, surprising trivia facts about:
- People mentioned or featured (actors, creators, personalities)
- Products or brands mentioned
- Historical context or events referenced
- Behind-the-scenes information
- Cultural impact or significance
- Production details if applicable
- Any interesting connections or trivia
- Content discussed at specific timestamps

Facts should be:
- Short (1-2 sentences max, under 200 characters)
- Entertaining and surprising
- Factually accurate (DO NOT make up information)
- In the style of VH1's Pop Up Video
- Relevant to what's mentioned in the title/description

{timing_instruction}

Return ONLY valid JSON matching this structure:
{{
  "facts": [
    {{"time": 10, "text": "First fact..."}},
    {{"time": 25, "text": "Second fact..."}},
    ...
  ]
}}"""
    
    facts = _call_grok_with_retry(prompt)
    return {'facts': facts, 'prompt': prompt}


def generate_facts_with_grok(artist, song, title, video_id, duration=None, description=None, transcript=None):
    """
    Call Grok API using xAI SDK with Pydantic validation for music videos.
    """
    if not xai_client:
        # Fallback for testing without API key
        return [
            {"time": 10, "text": f"This is {artist} - {song}!"},
            {"time": 30, "text": "Pop Up Video facts coming soon!"},
            {"time": 60, "text": "Set your GROK_API_KEY environment variable to generate real facts."}
        ]
    
    # Calculate fact timing based on video duration
    if duration and duration > 0:
        end_time = int(duration) - 10  # Stop 10 seconds before end
        num_facts = max(15, min(25, int(duration / 15)))  # 1 fact every ~15 seconds
        timing_instruction = f"Distribute timing evenly from 10 seconds to {end_time} seconds (approximately one fact every 10-15 seconds). Generate approximately {num_facts} facts."
    else:
        timing_instruction = "Distribute timing evenly from 10 seconds to 280 seconds. Generate 15-20 facts."
    
    description_context = f"\nVideo Description: {description[:500]}..." if description and len(description) > 20 else ""
    
    # Format transcript/lyrics for prompt (if available)
    transcript_context = ""
    if transcript and len(transcript) > 0:
        # For music videos, include full lyrics with timestamps
        lyrics_lines = []
        for entry in transcript:
            lyrics_lines.append(f"[{entry['start']}s] {entry['text']}")
        transcript_context = f"\n\nLyrics with Timestamps:\n" + "\n".join(lyrics_lines)
    
    prompt = f"""Generate interesting Pop Up Video style facts for this music video:

"{title}" by {artist}
YouTube Video ID: {video_id}
Video Duration: {int(duration) if duration else 'unknown'} seconds{description_context}{transcript_context}

Generate fun, surprising trivia facts about:
- The song's creation and recording
- The artist/band members
- The music video production
- The song's chart performance and cultural impact
- The era when this was released
- Any interesting backstory or context
- Specific lyrics and their meanings (if transcript provided)

IMPORTANT: If lyrics/transcript is provided above:
- Match facts to relevant timestamps where specific lyrics are sung. THis does not have to be on a 15 second boundary or anything.
- Reference actual lyrics when discussing song meaning or wordplay
- Use real references from sites like genius.com, songfacts.com, or similar to provide accurate lyric interpretations
- Time facts to appear during meaningful or interesting lyrical moments
- Feel free to include facts about other people mentioned in the lyrics at the appropriate time stamps where they're mentioned in the transcript. 
- Call out double entendres, puns, or clever wordplay in the lyrics, but not for every fact.

Facts should be:
- Short (1-2 sentences max, under 200 characters)
- Entertaining and surprising
- Factually accurate (DO NOT make up information). cite your sources.
- In the style of VH1's Pop Up Video

{timing_instruction}

Return ONLY valid JSON matching this structure:
{{
  "facts": [
    {{"time": 10, "text": "First fact..."}},
    {{"time": 25, "text": "Second fact..."}},
    ...
  ]
}}"""
    
    facts = _call_grok_with_retry(prompt)
    return {'facts': facts, 'prompt': prompt}


def _call_grok_with_retry(prompt):

    """
    Helper function to call Grok with retry logic using Structured Outputs.
    """
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"🌐 Generating facts using xAI SDK with Structured Outputs (attempt {attempt + 1}/{max_retries})...")
            
            # Use xAI SDK with Structured Outputs - guarantees valid JSON
            chat = xai_client.chat.create(model=GROK_MODEL)
            chat.append(system("You are a Pop Up Video fact generator. Generate interesting, accurate trivia facts."))
            chat.append(user(prompt))
            
            # Use chat.parse() with Pydantic model - returns validated object directly
            response, facts_list = chat.parse(FactsList)
            
            print(f"✅ Generated {len(facts_list.facts)} facts successfully")
            
            # Convert Pydantic objects to dicts
            facts = [{"time": fact.time, "text": fact.text} for fact in facts_list.facts]
            return facts
            
        except Exception as attempt_error:
            print(f"⚠️  Attempt {attempt + 1} failed: {attempt_error}")
            
            # If this was the last attempt, raise the error
            if attempt == max_retries - 1:
                raise
            
            # Otherwise wait a bit and retry
            print(f"🔄 Retrying in 2 seconds...")
            import time
            time.sleep(2)
    
    # Fallback if all retries failed
    return [
        {"time": 10, "text": "Error generating facts"},
        {"time": 30, "text": "Unable to connect to fact generator"}
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
        duration = data.get('duration', None)  # Optional duration in seconds
        description = data.get('description', None)  # Optional video description
        
        if not video_id or not title:
            return jsonify({'error': 'Missing video_id or title'}), 400
        
        print(f"📹 Processing video: {video_id} - {title}")
        
        # Check if facts already exist (do this BEFORE fetching transcript)
        facts_file = os.path.join(FACTS_DIR, f'{video_id}.json')
        if os.path.exists(facts_file):
            print(f"✅ Using cached facts from: {facts_file}")
            with open(facts_file, 'r', encoding='utf-8') as f:
                existing_facts = json.load(f)
            return jsonify({
                'source': 'cache',
                'data': existing_facts
            })
        
        # Only fetch transcript if we need to generate new facts
        transcript = fetch_youtube_transcript(video_id)
        
        # Log transcript availability
        if transcript and len(transcript) > 0:
            print(f"📝 Transcript available: {len(transcript)} entries")
        else:
            print("📝 No transcript available")
        
        # Check if this looks like a music video
        is_music, reason = is_likely_music_video(title)
        print(f"🎵 Content type check: {is_music} - {reason}")
        
        duration_info = f" ({int(duration)}s)" if duration else ""
        
        # Generate facts based on content type
        if is_music:
            # Parse video title for music content
            parsed = parse_video_title(title)
            
            # Double-check parsing quality
            if not parsed['is_music'] and parsed['artist'] == 'Unknown':
                print(f"⚠️  Unclear music video format, treating as general content: {title}")
                # Fallback to general facts
                print(f"Generating general facts for: {title} (ID: {video_id}){duration_info}")
                result = generate_general_facts_with_grok(title, video_id, duration, description, transcript)
                facts = result['facts']
                prompt_used = result['prompt']
                content_type = 'general'
                artist = 'Unknown'
                song = title
            else:
                print(f"Generating music facts for: {parsed['artist']} - {parsed['song']} (ID: {video_id}){duration_info}")
                result = generate_facts_with_grok(parsed['artist'], parsed['song'], parsed['full_title'], video_id, duration, description, transcript)
                facts = result['facts']
                prompt_used = result['prompt']
                content_type = 'music'
                artist = parsed['artist']
                song = parsed['song']
        else:
            # Generate general facts for non-music content
            print(f"🎬 Generating general facts for: {title} (ID: {video_id}){duration_info}")
            result = generate_general_facts_with_grok(title, video_id, duration, description, transcript)
            facts = result['facts']
            prompt_used = result['prompt']
            content_type = 'general'
            artist = 'N/A'
            song = title
        
        # Create facts object
        facts_data = {
            'videoId': video_id,
            'title': title,
            'contentType': content_type,
            'artist': artist,
            'song': song,
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'prompt': prompt_used,
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
