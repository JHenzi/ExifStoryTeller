#!/usr/bin/env python3
"""
Flask app to view photo stories with image previews
Reads markdown story files and serves them with linked images
"""

import os
import re
from datetime import datetime
from flask import Flask, render_template_string, send_from_directory, abort
import glob

# Try to import markdown, fallback to simple conversion
try:
    from markdown import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False
    def markdown(text):
        # Simple markdown to HTML conversion
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        return '\n'.join(f'<p>{p.replace(chr(10), "<br>")}</p>' for p in paragraphs)

app = Flask(__name__)

# Configuration
STORIES_DIR = 'stories'
PHOTOS_BASE_PATH = '/Volumes/E1999/photos_backup'

def parse_story_file(filepath):
    """Parse a markdown story file and extract metadata"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract metadata
    metadata = {
        'filename': os.path.basename(filepath),
        'title': '',
        'date': '',
        'photo': '',
        'total_photos': '',
        'content': content
    }
    
    # Extract title (first # heading)
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if title_match:
        metadata['title'] = title_match.group(1)
    
    # Extract date
    date_match = re.search(r'\*\*Date:\*\*\s+(.+)$', content, re.MULTILINE)
    if date_match:
        metadata['date'] = date_match.group(1)
    
    # Extract photo filename
    photo_match = re.search(r'\*\*Photo:\*\*\s+(.+)$', content, re.MULTILINE)
    if photo_match:
        metadata['photo'] = photo_match.group(1).strip()
    
    # Extract total photos
    total_match = re.search(r'\*\*Total Photos:\*\*\s+(\d+)', content, re.MULTILINE)
    if total_match:
        metadata['total_photos'] = total_match.group(1)
    
    # Extract story content (after the --- separator)
    parts = content.split('---')
    if len(parts) > 1:
        metadata['story_content'] = parts[-1].strip()
    else:
        metadata['story_content'] = content
    
    # Parse date for sorting
    try:
        # Try to parse date from filename (YYYY-MM-DD format)
        date_str = os.path.basename(filepath)[:10]
        metadata['date_obj'] = datetime.strptime(date_str, '%Y-%m-%d')
    except:
        try:
            # Try to parse from date field
            if metadata['date']:
                # Handle formats like "September 21, 2008" or "December 31, 1969"
                metadata['date_obj'] = datetime.strptime(metadata['date'], '%B %d, %Y')
        except:
            metadata['date_obj'] = datetime.min
    
    return metadata

def find_photo_path(photo_filename):
    """Find the full path to a photo file in the photos_backup directory"""
    if not photo_filename:
        return None
    
    # Search for the file recursively in photos_backup
    search_patterns = [
        os.path.join(PHOTOS_BASE_PATH, '**', photo_filename),
        os.path.join(PHOTOS_BASE_PATH, '**', photo_filename.upper()),
        os.path.join(PHOTOS_BASE_PATH, '**', photo_filename.lower()),
    ]
    
    for pattern in search_patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    
    return None

def get_all_stories():
    """Get all story files sorted by date"""
    stories = []
    stories_path = os.path.join(os.path.dirname(__file__), STORIES_DIR)
    
    if not os.path.exists(stories_path):
        return stories
    
    for filename in os.listdir(stories_path):
        if filename.endswith('.md') and filename != 'metadata.md':
            filepath = os.path.join(stories_path, filename)
            try:
                story = parse_story_file(filepath)
                stories.append(story)
            except Exception as e:
                print(f"Error parsing {filename}: {e}")
    
    # Sort by date (oldest first)
    stories.sort(key=lambda x: x['date_obj'])
    return stories

# HTML Templates
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Stories - Index</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 30px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        .story-list {
            list-style: none;
        }
        .story-item {
            padding: 20px;
            margin-bottom: 15px;
            background: #fafafa;
            border-left: 4px solid #3498db;
            border-radius: 4px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .story-item:hover {
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .story-item a {
            text-decoration: none;
            color: inherit;
            display: block;
        }
        .story-title {
            font-size: 1.3em;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 8px;
        }
        .story-meta {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        .story-meta span {
            margin-right: 15px;
        }
        .count {
            color: #3498db;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Photo Stories</h1>
        <ul class="story-list">
            {% for story in stories %}
            <li class="story-item">
                <a href="/story/{{ story.filename }}">
                    <div class="story-title">{{ story.title }}</div>
                    <div class="story-meta">
                        <span>📅 {{ story.date }}</span>
                        <span>📷 <span class="count">{{ story.total_photos }}</span> photos</span>
                        {% if story.photo %}
                        <span>🖼️ {{ story.photo }}</span>
                        {% endif %}
                    </div>
                </a>
            </li>
            {% endfor %}
        </ul>
        <p style="margin-top: 30px; color: #7f8c8d; text-align: center;">
            Total stories: {{ stories|length }}
        </p>
    </div>
</body>
</html>
"""

STORY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ story.title }} - Photo Story</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.8;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #ecf0f1;
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 15px;
        }
        .meta {
            color: #7f8c8d;
            font-size: 0.95em;
            margin-bottom: 10px;
        }
        .meta span {
            margin-right: 20px;
        }
        .photo-preview {
            margin: 30px 0;
            text-align: center;
        }
        .photo-preview img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        .photo-preview .photo-info {
            margin-top: 10px;
            color: #7f8c8d;
            font-size: 0.9em;
        }
        .story-content {
            margin-top: 30px;
            font-size: 1.1em;
            line-height: 1.8;
        }
        .story-content p {
            margin-bottom: 15px;
        }
        .back-link {
            display: inline-block;
            margin-bottom: 20px;
            color: #3498db;
            text-decoration: none;
            font-weight: 500;
        }
        .back-link:hover {
            text-decoration: underline;
        }
        .error-message {
            background: #fee;
            color: #c33;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Back to Index</a>
        
        <div class="header">
            <h1>{{ story.title }}</h1>
            <div class="meta">
                <span>📅 {{ story.date }}</span>
                <span>📷 {{ story.total_photos }} photos</span>
                {% if story.photo %}
                <span>🖼️ {{ story.photo }}</span>
                {% endif %}
            </div>
        </div>
        
        {% if photo_path %}
        <div class="photo-preview">
            <img src="/photo/{{ story.photo }}" alt="{{ story.photo }}" />
            <div class="photo-info">{{ story.photo }}</div>
        </div>
        {% elif story.photo %}
        <div class="error-message">
            ⚠️ Photo not found: {{ story.photo }}<br>
            Searched in: {{ photos_base_path }}
        </div>
        {% endif %}
        
        <div class="story-content">
            {{ story_html|safe }}
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Index page showing all stories"""
    stories = get_all_stories()
    return render_template_string(INDEX_TEMPLATE, stories=stories)

@app.route('/story/<filename>')
def story(filename):
    """Individual story page"""
    stories_path = os.path.join(os.path.dirname(__file__), STORIES_DIR)
    filepath = os.path.join(stories_path, filename)
    
    if not os.path.exists(filepath):
        abort(404)
    
    story = parse_story_file(filepath)
    
    # Convert markdown to HTML
    if HAS_MARKDOWN:
        story_html = markdown(story['story_content'])
    else:
        # Simple conversion: preserve paragraphs and line breaks
        content = story['story_content']
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        story_html = '\n'.join(f'<p>{p.replace(chr(10), "<br>")}</p>' for p in paragraphs)
    
    # Try to find photo path
    photo_path = None
    if story['photo']:
        photo_path = find_photo_path(story['photo'])
    
    return render_template_string(
        STORY_TEMPLATE,
        story=story,
        story_html=story_html,
        photo_path=photo_path,
        photos_base_path=PHOTOS_BASE_PATH
    )

@app.route('/photo/<photo_filename>')
def serve_photo(photo_filename):
    """Serve photo files"""
    photo_path = find_photo_path(photo_filename)
    
    if not photo_path or not os.path.exists(photo_path):
        abort(404)
    
    directory = os.path.dirname(photo_path)
    filename = os.path.basename(photo_path)
    
    return send_from_directory(directory, filename)

if __name__ == '__main__':
    # Check if photos directory exists
    if not os.path.exists(PHOTOS_BASE_PATH):
        print(f"WARNING: Photos directory not found: {PHOTOS_BASE_PATH}")
        print("Image previews will not work until the directory is available.")
    
    print("Starting Flask app...")
    print(f"Stories directory: {os.path.join(os.path.dirname(__file__), STORIES_DIR)}")
    print(f"Photos base path: {PHOTOS_BASE_PATH}")
    print("\nOpen your browser to: http://127.0.0.1:5000")
    
    app.run(debug=True, host='127.0.0.1', port=5000)

