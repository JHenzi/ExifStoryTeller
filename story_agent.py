#!/usr/bin/env python3
"""
Story Agent - Generates travel narratives from photo metadata with vision
Reads from the photo database created by app.py and generates stories using LMStudio,
with image vision capabilities. Writes individual markdown files per segment.
"""

import os
import sqlite3
import argparse
import json
import base64
import random
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import sys

# Try to import OpenAI (or compatible API)
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("WARNING: openai library not found. Install with: pip install openai")
    sys.exit(1)

# LMStudio endpoint
LMSTUDIO_BASE_URL = "http://192.168.1.220:1234/v1"

def parse_datetime(dt_string):
    """Parse datetime string from database"""
    if not dt_string:
        return None
    try:
        # Handle various datetime formats
        for fmt in ['%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None

def is_image_readable(filepath: str) -> bool:
    """Check if image is readable by vision model (JPG/PNG only)"""
    if not filepath:
        return False
    ext = os.path.splitext(filepath)[1].lower()
    return ext in ['.jpg', '.jpeg', '.png']

def encode_image_to_base64(filepath: str) -> Optional[str]:
    """Encode image file to base64 string"""
    try:
        with open(filepath, 'rb') as f:
            image_data = f.read()
            return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        print(f"ERROR: Could not encode image {filepath}: {e}", flush=True)
        return None

def get_image_mime_type(filepath: str) -> str:
    """Get MIME type for image"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.jpg', '.jpeg']:
        return 'image/jpeg'
    elif ext == '.png':
        return 'image/png'
    return 'image/jpeg'  # default

def get_photo_chunks_by_month(db_file: str) -> List[Dict]:
    """
    Group photos by location and month, selecting 1 random PNG/JPG per location/month.
    Returns list of chunk dictionaries with metadata and selected photo.
    """
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all photos with location and datetime
    # Filter out erroneous 1999 dates and ensure chronological order (oldest to newest)
    query = '''
    SELECT id, filename, filepath, datetime, location, camera_model, lens_model,
           iso, fnumber, exposure_time, focal_length, gps_lat, gps_lon
    FROM photos
    WHERE datetime IS NOT NULL 
      AND location IS NOT NULL
      AND status = 'processed'
      AND datetime NOT LIKE '1999%'
    ORDER BY datetime ASC
    '''
    
    cursor.execute(query)
    photos = cursor.fetchall()
    
    if not photos:
        print("No photos found with location and datetime data.")
        conn.close()
        return []
    
    print(f"Found {len(photos)} photos (excluding 1999 dates).", flush=True)
    
    # Group photos by location and month
    chunks = defaultdict(lambda: {
        'photos': [],
        'readable_photos': [],  # Only JPG/PNG
        'selected_photo': None,
        'location': None,
        'year_month': None,
        'date': None,
        'cameras': set(),
        'lens_models': set(),
        'total_photos': 0
    })
    
    for photo in photos:
        dt = parse_datetime(photo['datetime'])
        if not dt:
            continue
        
        # Double-check: filter out 1999 dates (erroneous camera dates)
        if dt.year == 1999:
            continue
        
        location = photo['location']
        year_month = f"{dt.year}-{dt.month:02d}"
        chunk_key = f"{location}|{year_month}"
        
        chunk = chunks[chunk_key]
        chunk['location'] = location
        chunk['year_month'] = year_month
        if chunk['date'] is None or dt < chunk['date']:
            chunk['date'] = dt
        
        photo_data = {
            'id': photo['id'],
            'filename': photo['filename'],
            'filepath': photo['filepath'],
            'datetime': photo['datetime'],
            'camera_model': photo['camera_model'],
            'lens_model': photo['lens_model'],
            'iso': photo['iso'],
            'fnumber': photo['fnumber'],
            'exposure_time': photo['exposure_time'],
            'focal_length': photo['focal_length'],
            'gps_lat': photo['gps_lat'],
            'gps_lon': photo['gps_lon']
        }
        
        chunk['photos'].append(photo_data)
        
        # Track readable images separately
        if is_image_readable(photo['filepath']):
            chunk['readable_photos'].append(photo_data)
        
        if photo['camera_model']:
            chunk['cameras'].add(photo['camera_model'])
        if photo['lens_model']:
            chunk['lens_models'].add(photo['lens_model'])
    
    # Select random readable photo for each chunk
    # Sort chunks chronologically from oldest to newest
    chunk_list = []
    sorted_chunks = sorted(chunks.items(), key=lambda x: x[1]['date'] if x[1]['date'] else datetime.max)
    
    for chunk_key, chunk_data in sorted_chunks:
        chunk_data['total_photos'] = len(chunk_data['photos'])
        
        # Select 1 random PNG/JPG image
        if chunk_data['readable_photos']:
            chunk_data['selected_photo'] = random.choice(chunk_data['readable_photos'])
        elif chunk_data['photos']:
            # Fallback: use any photo if no readable ones
            chunk_data['selected_photo'] = random.choice(chunk_data['photos'])
        
        chunk_data['cameras'] = sorted(list(chunk_data['cameras']))
        chunk_data['lens_models'] = sorted(list(chunk_data['lens_models']))
        chunk_list.append(chunk_data)
    
    # Print date range summary
    if chunk_list:
        first_date = chunk_list[0]['date']
        last_date = chunk_list[-1]['date']
        if first_date and last_date:
            print(f"Date range: {first_date.strftime('%Y-%m-%d')} to {last_date.strftime('%Y-%m-%d')} ({len(chunk_list)} location/month segments)", flush=True)
    
    conn.close()
    return chunk_list

def load_metadata(metadata_file: str) -> Dict:
    """Load metadata.md file from disk. Returns empty dict if file doesn't exist."""
    metadata = {}
    
    if not os.path.exists(metadata_file):
        print(f"WARNING: {metadata_file} not found. Story will be generated without personal context.", flush=True)
        return metadata
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse key: value pairs
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        metadata[key] = value
        return metadata
    except Exception as e:
        print(f"WARNING: Could not read {metadata_file}: {e}", flush=True)
        return metadata

def format_exif_data(photo: Dict) -> str:
    """Format EXIF data for a photo into a readable string"""
    exif_parts = []
    if photo.get('camera_model'):
        exif_parts.append(f"Camera: {photo['camera_model']}")
    if photo.get('lens_model'):
        exif_parts.append(f"Lens: {photo['lens_model']}")
    if photo.get('iso'):
        exif_parts.append(f"ISO: {photo['iso']}")
    if photo.get('fnumber'):
        exif_parts.append(f"f/{photo['fnumber']}")
    if photo.get('exposure_time'):
        exif_parts.append(f"Exposure: {photo['exposure_time']}s")
    if photo.get('focal_length'):
        exif_parts.append(f"Focal Length: {photo['focal_length']}mm")
    if photo.get('datetime'):
        exif_parts.append(f"Date/Time: {photo['datetime']}")
    if photo.get('gps_lat') and photo.get('gps_lon'):
        exif_parts.append(f"GPS: {photo['gps_lat']}, {photo['gps_lon']}")
    
    return " | ".join(exif_parts) if exif_parts else "No EXIF data"

def create_data_log(recent_chunks: List[Dict], current_chunk: Dict) -> str:
    """
    Create a structured data log in the format:
    Date - Location - Photo count
    Photo.jpg including EXIF data
    """
    log_parts = []
    
    # Add recent chunks summary (if any)
    for chunk in recent_chunks:
        date_str = chunk['date'].strftime("%m/%d/%Y") if chunk['date'] else "Unknown date"
        log_parts.append(f"{date_str} - {chunk['location']} - {chunk['total_photos']} photos")
    
    # Add current chunk
    date_str = current_chunk['date'].strftime("%m/%d/%Y") if current_chunk['date'] else "Unknown date"
    log_parts.append(f"{date_str} - {current_chunk['location']} - {current_chunk['total_photos']} photos")
    
    # Add photo and EXIF data for current chunk
    if current_chunk.get('selected_photo'):
        photo = current_chunk['selected_photo']
        log_parts.append("")
        log_parts.append(f"{photo['filename']}")
        exif_str = format_exif_data(photo)
        log_parts.append(f"EXIF: {exif_str}")
    
    return "\n".join(log_parts)

def get_story_history(stories_dir: str, last_n: int = 5) -> List[str]:
    """Get last N story segments for context"""
    if not os.path.exists(stories_dir):
        return []
    
    # Get all story files sorted by filename (which includes date)
    story_files = []
    for filename in os.listdir(stories_dir):
        if filename.endswith('.md') and filename != 'metadata.md':
            story_files.append(filename)
    
    story_files.sort()  # Sort by filename (date-sequential)
    
    # Get last N files
    recent_files = story_files[-last_n:] if len(story_files) > last_n else story_files
    
    history = []
    for filename in recent_files:
        filepath = os.path.join(stories_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    history.append(content)
        except Exception as e:
            print(f"WARNING: Could not read {filename}: {e}", flush=True)
    
    return history

def generate_story_segment(chunk: Dict, recent_chunks: List[Dict], metadata: Dict, 
                          client, model: str, sequence_num: int) -> str:
    """
    Generate a single story segment using LLM with image vision.
    Returns the story text.
    """
    # Create structured data log
    data_log = create_data_log(recent_chunks, chunk)
    
    # Prepare context
    context_parts = []
    
    # Add metadata context
    if metadata:
        context_parts.append(f"You are {metadata.get('Name', 'Traveler')}, from {metadata.get('Hometown', 'Unknown')}.")
        context_parts.append("")
    
    # Add the structured data log
    context_parts.append("Photo Activity Data:")
    context_parts.append("")
    context_parts.append(data_log)
    context_parts.append("")
    
    # Prepare image if available
    messages = [
        {
            "role": "system",
            "content": "You are a writer creating a personal life story narrative from actual photo data. You will be given structured data logs showing dates, locations, photo counts, and EXIF data. Write about the ACTUAL data provided - do not make up events, locations, or details that are not in the data. Reference the image when relevant. Keep it natural and flowing, but stay grounded in the facts provided."
        },
        {
            "role": "user",
            "content": []
        }
    ]
    
    # Add text context
    user_content = messages[1]["content"]
    user_content.append({
        "type": "text",
        "text": f"{chr(10).join(context_parts)}\n\nBased on the photo activity data above, write a personal narrative entry. Use ONLY the information provided in the data log. Describe what you see in the image and connect it to the location and date information. If there are multiple locations in the recent activity, note the progression from one place to another. Do not invent details not present in the data."
    })
    
    # Add image if available
    if chunk['selected_photo'] and chunk['selected_photo']['filepath']:
        image_path = chunk['selected_photo']['filepath']
        if os.path.exists(image_path) and is_image_readable(image_path):
            base64_image = encode_image_to_base64(image_path)
            if base64_image:
                mime_type = get_image_mime_type(image_path)
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}"
                    }
                })
                print(f"  Including image: {os.path.basename(image_path)}", flush=True)
    
    try:
        print(f"Generating story segment {sequence_num} for {chunk['location']}...", flush=True)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )
        
        story_text = response.choices[0].message.content
        return story_text
        
    except Exception as e:
        print(f"ERROR: Failed to generate story segment: {e}", flush=True)
        # Fallback narrative
        date_str = chunk['date'].strftime("%B %d, %Y") if chunk['date'] else "Unknown date"
        return f"On {date_str}, I visited {chunk['location']}. {chunk['total_photos']} photos were taken here this month."

def write_story_file(stories_dir: str, chunk: Dict, story_text: str, sequence_num: int):
    """Write story segment to markdown file: YYYY-MM-DD-SEQUENCE#-LOCATION.md"""
    if not chunk['date']:
        print("WARNING: No date for chunk, skipping file write", flush=True)
        return None
    
    date_str = chunk['date'].strftime("%Y-%m-%d")
    # Clean location for filename (remove special chars)
    location_clean = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in chunk['location'])
    location_clean = location_clean.replace(' ', '_').replace(',', '')[:50]  # Limit length
    
    filename = f"{date_str}-{sequence_num:03d}-{location_clean}.md"
    filepath = os.path.join(stories_dir, filename)
    
    # Write story content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {chunk['location']}\n\n")
        f.write(f"**Date:** {chunk['date'].strftime('%B %d, %Y')}\n\n")
        if chunk['selected_photo']:
            f.write(f"**Photo:** {chunk['selected_photo']['filename']}\n\n")
        f.write(f"**Total Photos:** {chunk['total_photos']}\n\n")
        f.write("---\n\n")
        f.write(story_text)
        f.write("\n")
    
    print(f"  Written: {filename}", flush=True)
    return filepath

def main():
    parser = argparse.ArgumentParser(
        description='Generate travel stories from photo metadata using LMStudio with vision',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate story with LMStudio
  python story_agent.py --db library7.db --name "John" --hometown "Cincinnati, OH"

  # Use custom model
  python story_agent.py --db library7.db --model llama-3

  # Custom stories directory
  python story_agent.py --db library7.db --stories-dir ./my_stories
        """
    )
    
    parser.add_argument('--db', '-d', type=str, required=True,
                       help='SQLite database file (e.g., library7.db)')
    parser.add_argument('--base-url', type=str, default=LMSTUDIO_BASE_URL,
                       help=f'LMStudio API base URL (default: {LMSTUDIO_BASE_URL})')
    parser.add_argument('--model', type=str, default='local-model',
                       help='LLM model to use (default: local-model)')
    parser.add_argument('--stories-dir', type=str, default='stories',
                       help='Directory to write story files (default: stories)')
    parser.add_argument('--metadata-file', type=str, default='metadata.md',
                       help='Path to metadata.md file (default: metadata.md in current directory)')
    parser.add_argument('--history-size', type=int, default=5,
                       help='Number of previous segments to include as context (default: 5)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"ERROR: Database '{args.db}' does not exist.", flush=True)
        sys.exit(1)
    
    if not HAS_OPENAI:
        print("ERROR: openai library required. Install with: pip install openai", flush=True)
        sys.exit(1)
    
    print("="*60, flush=True)
    print("Story Agent - Travel Narrative Generator with Vision", flush=True)
    print("="*60, flush=True)
    print(f"Database: {args.db}", flush=True)
    print(f"LMStudio: {args.base_url}", flush=True)
    print(f"Model: {args.model}\n", flush=True)
    
    # Load metadata from disk
    print("Loading metadata...", flush=True)
    metadata = load_metadata(args.metadata_file)
    if metadata:
        print(f"  Loaded metadata from {args.metadata_file}", flush=True)
        for key, value in metadata.items():
            print(f"  {key}: {value}", flush=True)
    else:
        print(f"  No metadata found. Stories will be generated without personal context.", flush=True)
    print("", flush=True)
    
    # Create stories directory
    os.makedirs(args.stories_dir, exist_ok=True)
    
    # Get photo chunks (grouped by location/month)
    print("Analyzing photos and creating chunks...", flush=True)
    chunks = get_photo_chunks_by_month(args.db)
    
    if not chunks:
        print("No photo chunks found. Make sure photos have location and datetime data.")
        sys.exit(1)
    
    print(f"Found {len(chunks)} location/month chunks", flush=True)
    total_photos = sum(c['total_photos'] for c in chunks)
    photos_with_images = sum(1 for c in chunks if c['selected_photo'] and is_image_readable(c['selected_photo']['filepath']))
    print(f"Total photos: {total_photos}", flush=True)
    print(f"Chunks with readable images: {photos_with_images}\n", flush=True)
    
    # Setup LMStudio client
    client = openai.OpenAI(base_url=args.base_url, api_key="not-needed")
    
    # Generate story segments sequentially
    print("Generating story segments...\n", flush=True)
    sequence_num = 1
    
    for i, chunk in enumerate(chunks):
        # Get recent chunks for data log context (last N chunks before current)
        recent_chunks = chunks[max(0, i - args.history_size):i] if i > 0 else []
        
        # Generate story segment
        story_text = generate_story_segment(
            chunk, recent_chunks, metadata, client, args.model, sequence_num
        )
        
        # Write to file
        write_story_file(args.stories_dir, chunk, story_text, sequence_num)
        
        sequence_num += 1
        print("", flush=True)  # Blank line between segments
    
    print("="*60, flush=True)
    print(f"Story generation complete!", flush=True)
    print(f"Generated {sequence_num - 1} story segments", flush=True)
    print(f"Stories written to: {args.stories_dir}", flush=True)
    print("="*60, flush=True)

if __name__ == '__main__':
    main()
