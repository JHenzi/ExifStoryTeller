# Story Agent - Travel Narrative Generator

An intelligent agent that generates travel stories from your photo metadata using Large Language Models (LLMs), creating a link between narrative text and specific photos for display applications.

## Overview

The Story Agent reads from the photo database created by `app.py`, groups photos by location and date, and uses an LLM to generate compelling travel narratives. Most importantly, it **links each story segment to the specific photos it describes**, enabling you to build applications that display photos alongside their story text.

## Features

- ✅ **Intelligent Chunking**: Groups photos by location and date automatically
- ✅ **LLM Story Generation**: Creates engaging travel narratives using GPT-4 or compatible models
- ✅ **Photo Linking**: Links story segments to specific photo filenames and IDs
- ✅ **Database Storage**: Stores stories with photo relationships for querying
- ✅ **JSON Export**: Exports stories in a format ready for display applications
- ✅ **Fallback Mode**: Works without LLM API (generates simple narrative)

## Requirements

```bash
pip install openai
```

Or for other LLM APIs, install the appropriate library and modify the `generate_story_with_llm` function.

## Usage

### Basic Usage

```bash
# Generate story (requires OPENAI_API_KEY environment variable)
python story_agent.py --db library7.db

# Or provide API key directly
python story_agent.py --db library7.db --api-key sk-your-key-here
```

### Advanced Options

```bash
# Use different model
python story_agent.py --db library7.db --model gpt-3.5-turbo

# Custom story title
python story_agent.py --db library7.db --title "My 2023 Travels"

# Export to specific file
python story_agent.py --db library7.db --export my_story.json

# Use compatible API (e.g., local LLM server)
python story_agent.py --db library7.db --base-url http://localhost:8000/v1 --model local-model
```

### Export Only (No LLM Generation)

```bash
# Export existing story without regenerating
python story_agent.py --db library7.db --no-llm --export story.json
```

## Database Schema

The script creates two new tables in your photo database:

### `story_segments` Table
- `id` - Primary key
- `story_title` - Title of the story
- `segment_index` - Order of segment in story
- `segment_text` - The story text for this segment
- `created_at` - When story was generated
- `photo_ids` - JSON array of photo IDs (for quick reference)
- `location` - Location mentioned in segment
- `date_range` - Date range for segment

### `story_photo_links` Table
- `id` - Primary key
- `story_segment_id` - Links to story_segments.id
- `photo_id` - Links to photos.id

This many-to-many relationship allows:
- One story segment to reference multiple photos
- One photo to appear in multiple story segments

## JSON Export Format

The exported JSON file has this structure:

```json
{
  "story_title": "Travel Story",
  "created_at": "2024-01-15T10:30:00",
  "total_segments": 5,
  "segments": [
    {
      "segment_id": 1,
      "segment_index": 0,
      "text": "The story text for this segment...",
      "location": "Cincinnati, OH, USA",
      "date_range": "September 12, 2008",
      "photos": [
        {
          "id": 123,
          "filename": "IMG_001.jpg",
          "filepath": "/path/to/IMG_001.jpg"
        },
        {
          "id": 124,
          "filename": "IMG_002.jpg",
          "filepath": "/path/to/IMG_002.jpg"
        }
      ]
    }
  ]
}
```

## Building a Display Application

The JSON export format is designed to make it easy to build display applications. Here's the workflow:

1. **Generate Story**: Run `story_agent.py` to create story from photos
2. **Load JSON**: Your app loads the exported JSON file
3. **Display Segments**: Show story segments in order
4. **Link Photos**: For each segment, display the associated photos
5. **Navigation**: Allow users to navigate between segments and photos

### Example Display Logic

```python
import json

# Load story
with open('library7_story.json') as f:
    story = json.load(f)

# Display each segment
for segment in story['segments']:
    print(f"\n{segment['text']}")
    print(f"\nLocation: {segment['location']}")
    print(f"Date: {segment['date_range']}")
    print(f"\nRelated Photos:")
    for photo in segment['photos']:
        print(f"  - {photo['filename']}")
        # Display photo: load_image(photo['filepath'])
```

## How It Works

1. **Photo Analysis**: Reads all photos with location and datetime from database
2. **Chunking**: Groups photos by location and date (same day, same city)
3. **Summary Creation**: Creates metadata summaries for each chunk (location, date, camera, photo count)
4. **LLM Processing**: Sends chunks to LLM with prompt to generate cohesive narrative
5. **Photo Mapping**: Maps story segments back to photos using location/filename matching
6. **Storage**: Stores story segments and photo links in database
7. **Export**: Exports to JSON for easy consumption by display apps

## Chunking Strategy

Photos are grouped by:
- **Location**: Same city/location (e.g., "Cincinnati, OH, USA")
- **Date**: Same calendar day

This creates natural story segments like:
- "September 12, 2008 in Cincinnati, OH, USA - 10 photos"
- "September 13, 2008 in Gatlinburg, TN, USA - 15 photos"

## LLM Prompt

The agent sends a prompt like this to the LLM:

```
You are a travel storyteller. Based on the following chronological photo metadata,
write a compelling travel narrative...

--- Segment 1 ---
Location: Cincinnati, OH, USA
Date: September 12, 2008
Number of photos: 10
Cameras/devices used: iPhone 3G
Photo files: IMG_001.jpg, IMG_002.jpg, ...

--- Segment 2 ---
...
```

## Customization

### Using Different LLM APIs

Modify the `generate_story_with_llm` function to use:
- Anthropic Claude
- Google Gemini
- Local LLM servers (Ollama, etc.)
- Any OpenAI-compatible API

### Adjusting Chunking

Modify `get_photo_chunks()` to change grouping:
- Group by week/month instead of day
- Group by location only (ignore date)
- Custom grouping logic

### Improving Photo Mapping

The current photo mapping uses simple text matching. You could enhance it by:
- Using LLM to explicitly identify which photos are mentioned
- Using image analysis to match story content to photos
- Manual curation interface

## Example Workflow

```bash
# 1. Process photos (using app.py)
python app.py process --folder /path/to/photos

# 2. Generate story
python story_agent.py --db library7.db --title "My 2023 Adventures"

# 3. Export for display
python story_agent.py --db library7.db --export story.json

# 4. Build your display app using story.json
```

## Notes

- The story is stored in the same database as your photos for easy querying
- Story segments are linked to photos via the `story_photo_links` table
- The JSON export includes all necessary data for building a display application
- Photos without location or datetime are excluded from story generation
- The agent can work without an LLM API (fallback mode) but generates simpler narratives

