# Image History - AI-Powered Photo Story Generator 🚀

**Transform your photo collection into an AI-generated life story using LLM vision models, EXIF metadata, and geocoding. Build your own personal travel narrative with multimodal AI!**

![Story Viewer Screenshot](Screenshot.png)

> **Perfect for AI enthusiasts, developers, and anyone who wants to explore the intersection of computer vision, LLMs, and personal data storytelling.**

## 🌟 What Makes This Awesome?

This project combines **multimodal AI**, **computer vision**, and **geocoding** to automatically generate personalized travel narratives from your photo collection. It's a complete pipeline from raw images to beautiful web stories:

1. **Extract EXIF metadata** from thousands of photos (GPS, camera settings, timestamps)
2. **Geocode locations** using Geonames database for accurate place names
3. **Generate AI stories** using vision-capable LLMs (LMStudio, OpenAI, etc.) with image understanding
4. **Serve beautiful web interface** with Flask to browse your AI-generated life story

### Why AI Developers Love This

- 🤖 **Multimodal AI Integration**: Uses vision models to understand images + context
- 📊 **Data-Driven Storytelling**: Feeds structured data logs to LLMs (no hallucination!)
- 🗺️ **Geocoding & Location Intelligence**: Automatic location detection from GPS coordinates
- 🎨 **Beautiful Web UI**: Flask-based viewer with responsive design
- 🔄 **Fault-Tolerant Processing**: Resume capability, error handling, progress tracking
- 📸 **EXIF Data Extraction**: Comprehensive metadata capture (camera, lens, GPS, etc.)

## 🎯 Use Cases

- **Personal Photo Archives**: Turn years of photos into a chronological life story
- **Travel Journals**: Automatically document trips with AI-generated narratives
- **AI Research Projects**: Study how vision models interpret personal photo collections
- **Multimodal LLM Experiments**: Test different models (GPT-4V, Claude, local models)
- **Data Visualization**: Explore your photo metadata with CSV exports and web interface

## 🚀 Quick Start

### 1. Extract EXIF Data & Build Database

```bash
# Process your photo folder
python app.py process --folder /path/to/your/photos

# The database filename is auto-derived from folder name
# Example: /path/to/library7/ → library7.db
```

### 2. Generate AI Stories with Vision Models

```bash
# Generate stories using LMStudio (or any OpenAI-compatible API)
python story_agent.py --db library7.db \
  --base-url http://192.168.1.220:1234/v1 \
  --model your-model-name

# Uses vision models to analyze images + metadata
# Creates markdown files in stories/ directory
```

### 3. View Your Stories in Web Interface

```bash
# Start Flask web server
python story_viewer.py

# Open browser to http://127.0.0.1:5000
# Browse your AI-generated life story with image previews!
```

## 📖 Features

### EXIF Metadata Extraction (`app.py`)

- ✅ **Comprehensive EXIF parsing**: Camera model, lens, ISO, aperture, exposure, GPS coordinates
- ✅ **Geocoding integration**: Automatic location lookup from GPS using Geonames database
- ✅ **Fault tolerance**: Resume processing, skip already-processed files, error tracking
- ✅ **Smart change detection**: Automatically reprocesses modified files
- ✅ **Progress tracking**: Saves every 500 images, handles interruptions gracefully
- ✅ **Multiple formats**: JPG, PNG, TIFF, RAW, HEIC, and more
- ✅ **CSV export**: Flexible grouping by day, location, or both for data analysis

### AI Story Generation (`story_agent.py`)

- ✅ **Vision model integration**: Feeds images to LLMs with base64 encoding
- ✅ **Data-driven prompts**: Structured data logs prevent hallucination
- ✅ **Context-aware narratives**: Maintains story continuity across segments
- ✅ **Location-based chunking**: Groups photos by location and month
- ✅ **EXIF context**: Includes camera settings, GPS, timestamps in prompts
- ✅ **Metadata support**: Personal context (name, hometown) for personalized stories
- ✅ **Chronological ordering**: Filters erroneous dates, sorts oldest to newest
- ✅ **LMStudio compatible**: Works with local models or OpenAI API

### Web Story Viewer (`story_viewer.py`)

- ✅ **Beautiful Flask interface**: Responsive design, modern UI
- ✅ **Chronological index**: Browse all stories sorted by date
- ✅ **Image previews**: Automatic photo lookup and display
- ✅ **Individual story pages**: Full narrative with metadata
- ✅ **Markdown rendering**: Clean story presentation
- ✅ **Photo serving**: Direct image links from your photo archive

## 🛠️ Installation

### Requirements

```bash
# Core dependencies
pip install exifread flask

# Optional: For better markdown rendering
pip install markdown

# Optional: For AI story generation
pip install openai
```

### Geonames Database (Optional)

Download `cities500.txt` from [Geonames](https://www.geonames.org/) for location lookup. The script will automatically import it into the database on first run.

## 📚 Detailed Usage

### EXIF Extraction & Database Building

```bash
# Basic usage
python app.py process --folder /path/to/photos

# Force reprocess all files
python app.py process --folder /path/to/photos --force-reprocess

# Skip location lookup (faster)
python app.py process --folder /path/to/photos --skip-location

# Custom database name
python app.py process --folder /path/to/photos --db my_photos.db
```

### CSV Export for Analysis

```bash
# Export all data
python app.py export

# Group by day and location
python app.py export --group-by-day --group-by-location

# Custom output file
python app.py export --output analysis.csv --group-by-day
```

### AI Story Generation

```bash
# Basic story generation
python story_agent.py --db library7.db

# Custom LMStudio endpoint
python story_agent.py --db library7.db \
  --base-url http://localhost:1234/v1 \
  --model llama-3

# Custom metadata file
python story_agent.py --db library7.db \
  --metadata-file my_metadata.md

# Custom stories directory
python story_agent.py --db library7.db \
  --stories-dir ./my_stories
```

### Web Viewer

```bash
# Start Flask server
python story_viewer.py

# Server runs on http://127.0.0.1:5000
# Navigate to index page to see all stories
```

**Configure photo path** in `story_viewer.py`:
```python
PHOTOS_BASE_PATH = '/path/to/your/photos'
```

## 🗄️ Database Schema

The SQLite database contains a `photos` table with:

- **Metadata**: `filename`, `filepath`, `datetime`, `camera_model`, `lens_model`
- **Camera settings**: `iso`, `fnumber`, `exposure_time`, `focal_length`
- **Location data**: `gps_lat`, `gps_lon`, `location` (geocoded name)
- **Processing status**: `status`, `file_hash`, `file_mtime`, `processed_at`, `error_message`

Plus a `locations` table for fast geocoding lookups (auto-imported from `cities500.txt`).

## 🤖 AI Integration Details

### How Story Generation Works

1. **Photo Chunking**: Groups photos by location and month
2. **Data Log Creation**: Formats structured logs with dates, locations, photo counts, EXIF data
3. **Image Selection**: Randomly selects one JPG/PNG per location/month for vision model
4. **LLM Prompting**: Sends data log + base64-encoded image to vision-capable model
5. **Story Output**: Generates markdown files named `YYYY-MM-DD-SEQUENCE#-LOCATION.md`

### Supported AI Models

- **LMStudio**: Local models with OpenAI-compatible API
- **OpenAI GPT-4V**: Vision-capable models
- **Claude 3**: Anthropic's vision models
- **Any OpenAI-compatible API**: Custom endpoints supported

### Data-Driven Approach

Instead of letting the LLM hallucinate, we feed it structured data:

```
11/12/2008 - Westwood, OH - 4 photos
12/05/2008 - Cincinnati, OH - 5 photos
1/10/2009 - Cheviot, OH - 29 photos

photo.jpg
EXIF: Camera: Canon EOS | Lens: 24-70mm | ISO: 400 | f/2.8 | ...
```

The LLM writes about **actual data**, not made-up events!

## 🎨 Web Interface Features

The Flask viewer (`story_viewer.py`) provides:

- **Index Page**: Chronological list of all stories with metadata
- **Story Pages**: Individual narratives with image previews
- **Image Serving**: Direct links to photos from your archive
- **Responsive Design**: Works on desktop and mobile
- **Error Handling**: Graceful handling of missing photos

![Story Viewer Screenshot](Screenshot.png)

*Browse your AI-generated life story with beautiful image previews*

## 🔧 Configuration

### Metadata File (`metadata.md`)

Create a `metadata.md` file for personalized context:

```markdown
Name: Joe
Hometown: Cincinnati, OH
```

The story agent reads this to provide personal context to the LLM.

### Photo Path Configuration

Update `PHOTOS_BASE_PATH` in `story_viewer.py` to point to your photo archive:

```python
PHOTOS_BASE_PATH = '/Volumes/E1999/photos_backup'
```

## 🐛 Troubleshooting

### Photos Not Found in Web Viewer

- Check `PHOTOS_BASE_PATH` in `story_viewer.py`
- Ensure photo filenames match exactly (case-sensitive on some systems)
- Photos are searched recursively in the base path

### Story Generation Fails

- Verify LMStudio/API endpoint is accessible
- Check model name is correct
- Ensure images are JPG/PNG (HEIC not supported by vision models)
- Review error messages in console output

### Location Lookup Issues

- Download `cities500.txt` from Geonames
- Location data auto-imports on first run (may take 1-2 minutes)
- Photos without GPS will have `NULL` location

## 📊 Performance

- **EXIF extraction**: ~100-500 images/second (depends on file size)
- **Location lookup**: Fast after initial database import (uses spatial indexes)
- **Story generation**: Depends on LLM speed (local models: 10-30s per segment)
- **Web viewer**: Instant page loads, fast image serving

## 🎓 For AI Researchers & Developers

This project demonstrates:

- **Multimodal AI workflows**: Combining vision models with structured data
- **Data-driven LLM prompting**: Reducing hallucination with structured inputs
- **Geocoding integration**: Real-world location intelligence
- **Fault-tolerant processing**: Production-ready error handling
- **Web interface design**: Flask-based story presentation

**Perfect for:**
- Studying how vision models interpret personal photo collections
- Experimenting with different LLM providers and models
- Building similar AI-powered storytelling applications
- Learning multimodal AI integration patterns

## 📝 License & Credits

- Uses [Geonames](https://www.geonames.org/) database for location data
- Compatible with [LMStudio](https://lmstudio.ai/) for local LLM inference
- Built with Python, Flask, SQLite, and modern AI APIs

## 🤝 Contributing

This is a personal project, but feel free to:
- Fork and adapt for your own photo collections
- Experiment with different LLM models and prompts
- Build additional features (timeline visualization, search, etc.)
- Share your AI-generated stories!

## 🔗 Related Projects

Looking for more AI-powered photo projects? Check out:
- [Awesome AI](https://github.com/sindresorhus/awesome#artificial-intelligence) - Curated AI resources
- Vision model benchmarks and comparisons
- Personal data storytelling tools

---

**Built for AI enthusiasts who want to do cool things with multimodal AI, vision models, and personal data storytelling.** 🚀

*Transform your photo collection into an AI-generated life story today!*
