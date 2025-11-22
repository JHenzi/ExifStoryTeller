#!/usr/bin/env python3
"""
Map-Based Storyteller - Interactive map showing photo journey through locations
Groups photos by day and location, allows navigation through chronological path
"""

import os
import sqlite3
import sys
from datetime import datetime
from flask import Flask, render_template_string, send_from_directory, jsonify, abort, request
import glob
import json

app = Flask(__name__)

# Configuration
PHOTOS_BASE_PATH = '/Volumes/E1999/photos_backup'

def parse_datetime(dt_string):
    """Parse datetime string from database"""
    if not dt_string:
        return None
    try:
        for fmt in ['%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None

def find_photo_path(photo_filename):
    """Find the full path to a photo file in the photos_backup directory"""
    if not photo_filename:
        return None
    
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

def get_locations_by_day(db_file):
    """
    Get all unique location/day combinations, sorted chronologically.
    Returns list of dicts with: date, location, lat, lon, photo_count, first_photo_datetime
    """
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query: Group by date (day) and location, get first photo datetime and count
    # Handle datetime format: could be "2008:09:12 14:30:00" or "2008-09-12 14:30:00"
    # Extract date part by taking first 10 characters after replacing colons with dashes
    query = '''
    SELECT 
        SUBSTR(REPLACE(datetime, ':', '-'), 1, 10) as date,
        location,
        gps_lat,
        gps_lon,
        COUNT(*) as photo_count,
        MIN(datetime) as first_photo_datetime
    FROM photos
    WHERE datetime IS NOT NULL 
      AND location IS NOT NULL
      AND gps_lat IS NOT NULL
      AND gps_lon IS NOT NULL
      AND status = 'processed'
      AND datetime NOT LIKE '1999%'
    GROUP BY SUBSTR(REPLACE(datetime, ':', '-'), 1, 10), location
    HAVING COUNT(*) > 0
    ORDER BY first_photo_datetime ASC
    '''
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    locations = []
    for row in rows:
        dt = parse_datetime(row['first_photo_datetime'])
        if not dt or dt.year == 1999:
            continue
        
        # Normalize date format to YYYY-MM-DD
        date_str = row['date']
        if ':' in date_str:
            date_str = date_str.replace(':', '-')
        if len(date_str) > 10:
            date_str = date_str[:10]
        
        locations.append({
            'date': date_str,
            'location': row['location'],
            'lat': row['gps_lat'],
            'lon': row['gps_lon'],
            'photo_count': row['photo_count'],
            'first_photo_datetime': row['first_photo_datetime'],
            'date_obj': dt
        })
    
    conn.close()
    return locations

def get_photos_for_location_day(db_file, location, date):
    """
    Get all photos for a specific location and date.
    Returns list of photo dicts with metadata.
    """
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Handle datetime format: could be "2008:09:12 14:30:00" or "2008-09-12 14:30:00"
    # Match by extracting date part and comparing
    query = '''
    SELECT 
        id, filename, filepath, datetime, location,
        camera_model, lens_model, iso, fnumber, 
        exposure_time, focal_length, gps_lat, gps_lon
    FROM photos
    WHERE SUBSTR(REPLACE(datetime, ':', '-'), 1, 10) = ?
      AND location = ?
      AND status = 'processed'
      AND datetime NOT LIKE '1999%'
    ORDER BY datetime ASC
    '''
    
    cursor.execute(query, (date, location))
    rows = cursor.fetchall()
    
    photos = []
    for row in rows:
        photo = {
            'id': row['id'],
            'filename': row['filename'],
            'filepath': row['filepath'],
            'datetime': row['datetime'],
            'location': row['location'],
            'camera_model': row['camera_model'],
            'lens_model': row['lens_model'],
            'iso': row['iso'],
            'fnumber': row['fnumber'],
            'exposure_time': row['exposure_time'],
            'focal_length': row['focal_length'],
            'gps_lat': row['gps_lat'],
            'gps_lon': row['gps_lon']
        }
        photos.append(photo)
    
    conn.close()
    return photos

# HTML Template
MAP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Map Storyteller - Photo Journey</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            overflow: hidden;
        }
        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        .main-content {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        #map {
            flex: 1;
            height: 100%;
            position: relative;
        }
        .sidebar {
            width: 400px;
            background: white;
            border-left: 1px solid #ddd;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .sidebar-header {
            padding: 20px;
            background: #2c3e50;
            color: white;
            border-bottom: 2px solid #3498db;
        }
        .sidebar-header h1 {
            font-size: 1.3em;
            margin-bottom: 10px;
        }
        .location-info {
            font-size: 0.9em;
            opacity: 0.9;
        }
        .navigation {
            padding: 15px 20px;
            background: #ecf0f1;
            border-bottom: 1px solid #ddd;
            display: flex;
            gap: 10px;
        }
        .nav-button {
            flex: 1;
            padding: 12px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            transition: background 0.2s;
        }
        .nav-button:hover:not(:disabled) {
            background: #2980b9;
        }
        .nav-button:disabled {
            background: #bdc3c7;
            cursor: not-allowed;
        }
        .photo-gallery {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }
        .photo-item {
            margin-bottom: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .photo-item img {
            width: 100%;
            height: auto;
            display: block;
        }
        .photo-details {
            padding: 15px;
        }
        .photo-details h3 {
            font-size: 0.9em;
            color: #2c3e50;
            margin-bottom: 8px;
        }
        .photo-meta {
            font-size: 0.85em;
            color: #7f8c8d;
            line-height: 1.6;
        }
        .photo-meta strong {
            color: #34495e;
        }
        .location-counter {
            text-align: center;
            padding: 10px;
            background: #ecf0f1;
            font-size: 0.9em;
            color: #7f8c8d;
        }
        .timeline-overlay {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            pointer-events: none;
        }
        .timeline-container {
            background: rgba(44, 62, 80, 0.95);
            padding: 15px 30px;
            border-top: 2px solid #3498db;
            pointer-events: auto;
            backdrop-filter: blur(5px);
        }
        .timeline-track {
            position: relative;
            width: 100%;
            height: 30px;
            background: #34495e;
            border-radius: 15px;
            cursor: pointer;
            margin-top: 8px;
        }
        .timeline-handle {
            position: absolute;
            top: 0;
            width: 20px;
            height: 30px;
            background: #e74c3c;
            border-radius: 15px;
            cursor: grab;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
            transform: translateX(-10px);
            transition: background 0.2s;
        }
        .timeline-handle:hover {
            background: #c0392b;
        }
        .timeline-handle:active {
            cursor: grabbing;
        }
        .timeline-labels {
            display: flex;
            justify-content: space-between;
            color: #ecf0f1;
            font-size: 0.85em;
            margin-bottom: 5px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="main-content">
            <div id="map">
                <div class="timeline-overlay">
                    <div class="timeline-container">
                        <div class="timeline-labels">
                            <span id="timeline-start">Start</span>
                            <span id="timeline-end">End</span>
                        </div>
                        <div class="timeline-track" id="timeline-track">
                            <div class="timeline-handle" id="timeline-handle"></div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="sidebar">
                <div class="sidebar-header">
                    <h1>Photo Journey</h1>
                    <div class="location-info" id="location-info">Loading...</div>
                </div>
                <div class="navigation">
                    <button class="nav-button" id="prev-btn" onclick="navigateLocation(-1)">← Previous</button>
                    <button class="nav-button" id="next-btn" onclick="navigateLocation(1)">Next →</button>
                </div>
                <div class="location-counter">
                    <span id="location-counter">Location 0 of 0</span>
                </div>
                <div class="photo-gallery" id="photo-gallery">
                    <div class="loading">Loading photos...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let locations = [];
        let currentIndex = 0;
        let map;
        let currentMarker;
        let pathPolyline;

        // Initialize map
        function initMap() {
            map = L.map('map').setView([39.1031, -84.5120], 3); // Default center (Cincinnati)
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(map);
        }

        // Load locations from API
        async function loadLocations() {
            try {
                const response = await fetch('/api/locations');
                locations = await response.json();
                
                if (locations.length === 0) {
                    document.getElementById('location-info').textContent = 'No locations found';
                    return;
                }
                
                // Draw path through all locations
                drawPath();
                
                // Load first location
                currentIndex = 0;
                loadLocation(currentIndex);
            } catch (error) {
                console.error('Error loading locations:', error);
                document.getElementById('location-info').textContent = 'Error loading locations';
            }
        }

        // Draw path connecting all locations
        function drawPath() {
            if (pathPolyline) {
                map.removeLayer(pathPolyline);
            }
            
            const pathCoords = locations.map(loc => [loc.lat, loc.lon]);
            pathPolyline = L.polyline(pathCoords, {
                color: '#3498db',
                weight: 3,
                opacity: 0.6
            }).addTo(map);
            
            // Fit map to show all locations
            if (locations.length > 0) {
                const bounds = L.latLngBounds(pathCoords);
                map.fitBounds(bounds, { padding: [50, 50] });
            }
        }

        // Parse datetime string to Date object
        function parseDateTime(dtString) {
            if (!dtString) return null;
            
            // Handle EXIF format: "2008:09:12 14:30:00"
            // Replace first two colons (date part) with dashes, keep space and time
            let normalized = dtString;
            if (dtString.includes(':')) {
                // Replace colons in date part (first 10 chars) with dashes
                const parts = dtString.split(' ');
                if (parts.length >= 2) {
                    const datePart = parts[0].replace(/:/g, '-');
                    const timePart = parts[1];
                    normalized = `${datePart}T${timePart}`;
                } else {
                    // Just date part
                    normalized = dtString.replace(/:/g, '-');
                }
            } else if (dtString.includes(' ') && !dtString.includes('T')) {
                // Format: "2008-09-12 14:30:00" - replace space with T
                normalized = dtString.replace(' ', 'T');
            }
            
            // Try to parse
            let date = new Date(normalized);
            if (isNaN(date.getTime())) {
                // Fallback: try manual parsing for "YYYY:MM:DD HH:MM:SS"
                const regexPattern = '(\\d{4})[:/-](\\d{2})[:/-](\\d{2})\\s+(\\d{2}):(\\d{2}):(\\d{2})';
                const match = dtString.match(new RegExp(regexPattern));
                if (match) {
                    const [, year, month, day, hour, minute, second] = match;
                    date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day), 
                                   parseInt(hour), parseInt(minute), parseInt(second));
                } else {
                    // Last fallback: try as-is
                    date = new Date(dtString);
                }
            }
            
            return isNaN(date.getTime()) ? null : date;
        }

        // Load location and photos
        async function loadLocation(index) {
            if (index < 0 || index >= locations.length) {
                return;
            }
            
            currentIndex = index;
            const location = locations[index];
            
            // Update location info with proper date parsing
            const dateObj = parseDateTime(location.first_photo_datetime);
            let dateStr = 'Unknown date';
            if (dateObj) {
                dateStr = dateObj.toLocaleDateString('en-US', { 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                });
            }
            
            document.getElementById('location-info').innerHTML = `
                <strong>${location.location}</strong><br>
                ${dateStr}<br>
                ${location.photo_count} photos
            `;
            
            // Update timeline position
            updateTimelinePosition(index);
            
            // Update counter
            document.getElementById('location-counter').textContent = 
                `Location ${index + 1} of ${locations.length}`;
            
            // Update navigation buttons
            document.getElementById('prev-btn').disabled = (index === 0);
            document.getElementById('next-btn').disabled = (index === locations.length - 1);
            
            // Fly to location on map
            map.flyTo([location.lat, location.lon], 10, {
                duration: 1.5
            });
            
            // Update marker
            if (currentMarker) {
                map.removeLayer(currentMarker);
            }
            currentMarker = L.marker([location.lat, location.lon], {
                icon: L.divIcon({
                    className: 'custom-marker',
                    html: `<div style="background: #e74c3c; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">${index + 1}</div>`,
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                })
            }).addTo(map);
            
            // Load photos
            await loadPhotos(location.location, location.date);
        }

        // Load photos for current location/day
        async function loadPhotos(location, date) {
            document.getElementById('photo-gallery').innerHTML = '<div class="loading">Loading photos...</div>';
            
            try {
                const response = await fetch(`/api/photos?location=${encodeURIComponent(location)}&date=${encodeURIComponent(date)}`);
                const photos = await response.json();
                
                if (photos.length === 0) {
                    document.getElementById('photo-gallery').innerHTML = '<div class="loading">No photos found for this location</div>';
                    return;
                }
                
                let galleryHTML = '';
                photos.forEach(photo => {
                    const photoDate = parseDateTime(photo.datetime);
                    let dateStr = 'Unknown date';
                    if (photoDate) {
                        dateStr = photoDate.toLocaleString('en-US', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                    }
                    
                    let metaHTML = `<strong>Date:</strong> ${dateStr}<br>`;
                    if (photo.camera_model) {
                        metaHTML += `<strong>Camera:</strong> ${photo.camera_model}<br>`;
                    }
                    if (photo.lens_model) {
                        metaHTML += `<strong>Lens:</strong> ${photo.lens_model}<br>`;
                    }
                    if (photo.iso) {
                        metaHTML += `<strong>ISO:</strong> ${photo.iso}`;
                    }
                    if (photo.fnumber) {
                        metaHTML += ` | <strong>f/</strong>${photo.fnumber}`;
                    }
                    if (photo.exposure_time) {
                        metaHTML += ` | <strong>Exposure:</strong> ${photo.exposure_time}s`;
                    }
                    if (photo.focal_length) {
                        metaHTML += ` | <strong>Focal:</strong> ${photo.focal_length}mm`;
                    }
                    
                    galleryHTML += `
                        <div class="photo-item">
                            <img src="/photo/${encodeURIComponent(photo.filename)}" 
                                 alt="${photo.filename}" 
                                 onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'400\\' height=\\'300\\'%3E%3Crect fill=\\'%23ddd\\' width=\\'400\\' height=\\'300\\'/%3E%3Ctext x=\\'50%25\\' y=\\'50%25\\' text-anchor=\\'middle\\' dy=\\'.3em\\' fill=\\'%23999\\'%3EPhoto not found%3C/text%3E%3C/svg%3E';">
                            <div class="photo-details">
                                <h3>${photo.filename}</h3>
                                <div class="photo-meta">${metaHTML}</div>
                            </div>
                        </div>
                    `;
                });
                
                document.getElementById('photo-gallery').innerHTML = galleryHTML;
            } catch (error) {
                console.error('Error loading photos:', error);
                document.getElementById('photo-gallery').innerHTML = 
                    '<div class="loading">Error loading photos</div>';
            }
        }

        // Navigate to next/previous location
        function navigateLocation(direction) {
            const newIndex = currentIndex + direction;
            if (newIndex >= 0 && newIndex < locations.length) {
                loadLocation(newIndex);
            }
        }

        // Update timeline position
        function updateTimelinePosition(index) {
            if (locations.length === 0) return;
            
            const percentage = (index / (locations.length - 1)) * 100;
            const handle = document.getElementById('timeline-handle');
            const track = document.getElementById('timeline-track');
            
            if (handle && track) {
                const maxPosition = track.offsetWidth - handle.offsetWidth;
                handle.style.left = `${(percentage / 100) * maxPosition}px`;
            }
            
            // Update timeline labels
            if (locations.length > 0) {
                const firstDate = parseDateTime(locations[0].first_photo_datetime);
                const lastDate = parseDateTime(locations[locations.length - 1].first_photo_datetime);
                
                if (firstDate) {
                    document.getElementById('timeline-start').textContent = 
                        firstDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                }
                if (lastDate) {
                    document.getElementById('timeline-end').textContent = 
                        lastDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                }
            }
        }

        // Initialize timeline drag functionality
        function initTimeline() {
            const handle = document.getElementById('timeline-handle');
            const track = document.getElementById('timeline-track');
            let isDragging = false;
            
            // Mouse events
            handle.addEventListener('mousedown', (e) => {
                isDragging = true;
                e.preventDefault();
            });
            
            document.addEventListener('mousemove', (e) => {
                if (!isDragging) return;
                
                const rect = track.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
                
                const maxPosition = rect.width - handle.offsetWidth;
                handle.style.left = `${(percentage / 100) * maxPosition}px`;
                
                // Calculate which location index this corresponds to
                const index = Math.round((percentage / 100) * (locations.length - 1));
                if (index !== currentIndex && index >= 0 && index < locations.length) {
                    loadLocation(index);
                }
            });
            
            document.addEventListener('mouseup', () => {
                isDragging = false;
            });
            
            // Click on track to jump
            track.addEventListener('click', (e) => {
                const rect = track.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
                const index = Math.round((percentage / 100) * (locations.length - 1));
                if (index >= 0 && index < locations.length) {
                    loadLocation(index);
                }
            });
            
            // Touch events for mobile
            handle.addEventListener('touchstart', (e) => {
                isDragging = true;
                e.preventDefault();
            });
            
            document.addEventListener('touchmove', (e) => {
                if (!isDragging) return;
                
                const touch = e.touches[0];
                const rect = track.getBoundingClientRect();
                const x = touch.clientX - rect.left;
                const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
                
                const maxPosition = rect.width - handle.offsetWidth;
                handle.style.left = `${(percentage / 100) * maxPosition}px`;
                
                const index = Math.round((percentage / 100) * (locations.length - 1));
                if (index !== currentIndex && index >= 0 && index < locations.length) {
                    loadLocation(index);
                }
            });
            
            document.addEventListener('touchend', () => {
                isDragging = false;
            });
        }

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') {
                navigateLocation(-1);
            } else if (e.key === 'ArrowRight') {
                navigateLocation(1);
            }
        });

        // Initialize
        initMap();
        initTimeline();
        loadLocations();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main map storyteller page"""
    return render_template_string(MAP_TEMPLATE)

@app.route('/api/locations')
def api_locations():
    """API endpoint: Get all locations by day, sorted chronologically"""
    db_file = app.config.get('DB_FILE')
    if not db_file:
        return jsonify({'error': 'Database not configured'}), 500
    
    if not os.path.exists(db_file):
        return jsonify({'error': 'Database file not found'}), 404
    
    locations = get_locations_by_day(db_file)
    return jsonify(locations)

@app.route('/api/photos')
def api_photos():
    """API endpoint: Get photos for a specific location and date"""
    location = request.args.get('location')
    date = request.args.get('date')
    
    if not location or not date:
        return jsonify({'error': 'Location and date required'}), 400
    
    db_file = app.config.get('DB_FILE')
    if not db_file:
        return jsonify({'error': 'Database not configured'}), 500
    
    if not os.path.exists(db_file):
        return jsonify({'error': 'Database file not found'}), 404
    
    photos = get_photos_for_location_day(db_file, location, date)
    
    # Debug: log the query parameters and results
    print(f"DEBUG: Querying photos for location='{location}', date='{date}', found {len(photos)} photos", flush=True)
    
    return jsonify(photos)

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
    import argparse
    from flask import request
    
    parser = argparse.ArgumentParser(description='Map-based photo storyteller')
    parser.add_argument('--db', '-d', type=str, required=True,
                       help='SQLite database file (e.g., library7.db)')
    parser.add_argument('--photos-path', type=str, default=PHOTOS_BASE_PATH,
                       help=f'Base path to photos (default: {PHOTOS_BASE_PATH})')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                       help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5001,
                       help='Port to bind to (default: 5001)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"ERROR: Database '{args.db}' does not exist.", flush=True)
        sys.exit(1)
    
    # Configure app
    app.config['DB_FILE'] = args.db
    PHOTOS_BASE_PATH = args.photos_path
    
    # Check if photos directory exists
    if not os.path.exists(PHOTOS_BASE_PATH):
        print(f"WARNING: Photos directory not found: {PHOTOS_BASE_PATH}")
        print("Image previews will not work until the directory is available.")
    
    print("="*60, flush=True)
    print("Map Storyteller - Photo Journey", flush=True)
    print("="*60, flush=True)
    print(f"Database: {args.db}", flush=True)
    print(f"Photos path: {PHOTOS_BASE_PATH}", flush=True)
    print(f"\nOpen your browser to: http://{args.host}:{args.port}", flush=True)
    print("="*60, flush=True)
    
    app.run(debug=True, host=args.host, port=args.port)

