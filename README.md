# PopUp Video - Universal YouTube Facts Generator

A TamperMonkey script that brings the classic VH1 "Pop Up Video" experience to any YouTube music video! Displays fun, surprising facts in yellow pop-up bubbles while you watch.

## Features

- 🎵 **Works on any YouTube video** - automatically extracts song/artist info
- 🤖 **AI-Generated Facts** - uses Grok-2 to create entertaining trivia
- 📦 **GitHub Caching** - facts are shared across all users once generated
- 🎨 **Classic Pop Up Video Style** - yellow bubbles, random positioning
- ⚡ **Fast Loading** - cached facts load instantly

## Architecture

```
YouTube Page → TamperMonkey Script
                ↓
          Check GitHub Cache
                ↓
         ┌──────┴──────┐
         ↓             ↓
    Found (fast!)   Not Found
         ↓             ↓
    Use Cache    Call Local API
                      ↓
                 Generate Facts
                      ↓
                Save to facts/
                      ↓
            (Manually push to GitHub)
```

## Setup

### 1. Install TamperMonkey

- Chrome/Edge: [TamperMonkey Extension](https://www.tampermonkey.net/)
- Firefox: [TamperMonkey Add-on](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/)

### 2. Install the Script

1. Open TamperMonkey Dashboard
2. Click "Create a new script"
3. Copy the contents of `PopUpVideo.js`
4. Update `GITHUB_FACTS_URL` with your GitHub username/repo
5. Save (Ctrl+S)

### 3. Set Up Backend (For Generating New Facts)

#### Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

#### Set Grok API Key

**Windows PowerShell:**
```powershell
$env:GROK_API_KEY = "your-grok-api-key-here"
```

**Mac/Linux:**
```bash
export GROK_API_KEY="your-grok-api-key-here"
```

**Get a Grok API Key:**
- Visit [x.ai](https://x.ai/) and sign up
- Navigate to API settings
- Generate an API key

#### Run the Backend

```bash
python app.py
```

The server will start on `http://localhost:5000`

### 4. GitHub Setup (For Sharing Facts)

1. Create a GitHub repo (or use this one)
2. Ensure the `facts/` directory is in the repo
3. Update the `GITHUB_FACTS_URL` in `PopUpVideo.js`:
   ```javascript
   const GITHUB_FACTS_URL = 'https://raw.githubusercontent.com/YOUR_USERNAME/PopUpVideo/main/facts/';
   ```

## Usage

### Watching Videos with Cached Facts

1. Navigate to any YouTube video
2. If facts exist in GitHub, they'll load automatically
3. Enjoy the pop-ups!

### Generating Facts for New Videos

1. Make sure the backend is running (`python backend/app.py`)
2. Navigate to a YouTube video without cached facts
3. The script will automatically:
   - Detect no cache exists
   - Call your local API
   - Generate facts using Grok
   - Save to `facts/{VIDEO_ID}.json`
4. Check the browser console for status messages

### Syncing Facts to GitHub

After generating new facts:

```bash
git add facts/*.json
git commit -m "Add facts for [Song Name]"
git push
```

Now everyone using your script can access these facts!

## File Structure

```
PopUpVideo/
├── PopUpVideo.js           # TamperMonkey script
├── backend/
│   ├── app.py             # Flask API server
│   └── requirements.txt   # Python dependencies
├── facts/
│   ├── hTWKbfoikeg.json  # Cached facts (Nirvana example)
│   └── ...               # More fact files
└── README.md
```

## JSON Format

Each fact file (`facts/{VIDEO_ID}.json`) follows this structure:

```json
{
  "videoId": "hTWKbfoikeg",
  "title": "Nirvana - Smells Like Teen Spirit",
  "artist": "Nirvana",
  "song": "Smells Like Teen Spirit",
  "generatedAt": "2026-01-09T00:00:00Z",
  "facts": [
    {
      "time": 10,
      "text": "Fun fact appears at 10 seconds!"
    },
    {
      "time": 25,
      "text": "Another fact at 25 seconds!"
    }
  ]
}
```

## API Endpoints

### `GET /health`
Check if the backend is running.

### `POST /generate-facts`
Generate facts for a video.

**Request:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up"
}
```

**Response:**
```json
{
  "source": "generated",
  "data": {
    "videoId": "dQw4w9WgXcQ",
    "facts": [...]
  }
}
```

### `GET /list-facts`
List all cached video IDs.

## Troubleshooting

### "Cannot connect to local API"
- Make sure the backend is running: `python backend/app.py`
- Check the console for the server URL (should be `http://localhost:5000`)

### "Error generating facts"
- Verify your `GROK_API_KEY` is set correctly
- Check the backend console for error messages
- Ensure you have internet connection for API calls

### Facts not appearing
- Open browser console (F12)
- Look for `[PopUpFacts]` log messages
- Verify the video has facts in the `facts/` directory
- Make sure TamperMonkey script is enabled

### GitHub cache not working
- Verify `GITHUB_FACTS_URL` is correct in the script
- Ensure the facts file exists in your GitHub repo
- Check that the file is in the `main` branch
- Try accessing the raw GitHub URL directly in your browser

## Customization

### Change popup styling
Edit the `showPopup()` function in `PopUpVideo.js`:
- Background color: `popup.style.background`
- Font size: `popup.style.fontSize`
- Duration: Change the `8000` timeout value

### Modify fact generation prompt
Edit the `generate_facts_with_grok()` function in `backend/app.py` to customize how Grok generates facts.

### Change timing
Modify the `time` values in generated facts to control when pop-ups appear.

## Contributing

Found a video with incorrect or boring facts? Contributions welcome!

1. Edit the JSON file in `facts/`
2. Submit a Pull Request
3. Share better facts with everyone!

## License

MIT License - Feel free to use and modify!

## Credits

Inspired by VH1's Pop Up Video (1996-2002) 📺✨
