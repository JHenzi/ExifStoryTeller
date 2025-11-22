import os
import sqlite3
import exifread
import sys
import csv
import math
import argparse
import hashlib
import time
import signal
from datetime import datetime
from tqdm import tqdm

# Configuration
LOCATIONS_FILE = 'cities500.txt'  # Geonames cities with population > 500
DB_FILE = 'photo_metadata.db'

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle interrupt signals gracefully"""
    global shutdown_requested
    shutdown_requested = True
    print("\n\nShutdown requested. Finishing current operation and exiting gracefully...", flush=True)

# Helper: Convert GPS to decimal
def dms_to_decimal(dms, ref):
    # dms is a tuple of Rational numbers
    degrees = float(dms[0].num) / float(dms[0].den)
    minutes = float(dms[1].num) / float(dms[1].den)
    seconds = float(dms[2].num) / float(dms[2].den)
    dec = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ['S', 'W']:
        dec = -dec
    return dec

# Helper: Calculate distance between two GPS coordinates (Haversine formula)
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in kilometers between two GPS coordinates"""
    R = 6371  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

# Helper: Calculate file hash for change detection
def calculate_file_hash(filepath):
    """Calculate MD5 hash of file for change detection"""
    try:
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None

# Helper: Get file modification time
def get_file_mtime(filepath):
    """Get file modification time as timestamp"""
    try:
        return os.path.getmtime(filepath)
    except Exception:
        return None

# Helper: Derive database filename from image directory
def get_db_filename_from_folder(image_dir, default_db=None):
    """
    Derive database filename from image directory path.
    Uses the last directory name in the path as the database name.
    
    Args:
        image_dir: Path to image directory
        default_db: Default database file if path extraction fails
    
    Returns:
        Database filename (e.g., 'library7.db' for '/path/to/image/library7/')
    """
    try:
        # Normalize the path and remove trailing slashes
        normalized_path = os.path.normpath(image_dir)
        # Get the last directory name
        folder_name = os.path.basename(normalized_path)
        if folder_name:
            return f"{folder_name}.db"
    except Exception:
        pass
    
    # Fallback to default if extraction fails
    return default_db or DB_FILE

# Function: Import cities500.txt into database
def import_locations_to_db(cursor, conn, locations_file=LOCATIONS_FILE):
    """
    Import cities500.txt into the database for fast lookups.
    Creates a locations table with indexed latitude/longitude.
    cities500.txt contains cities with population > 500 (smaller, faster than allCountries.txt).
    """
    global shutdown_requested
    
    # Check if locations table already exists and has data
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='locations'")
    if cursor.fetchone():
        # Check if table needs migration (add admin1_code and admin2_code columns)
        cursor.execute("PRAGMA table_info(locations)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'admin1_code' not in columns:
            print("Migrating locations table to add admin codes...", flush=True)
            cursor.execute("ALTER TABLE locations ADD COLUMN admin1_code TEXT")
            cursor.execute("ALTER TABLE locations ADD COLUMN admin2_code TEXT")
            conn.commit()
            print("Migration complete. You may want to re-import locations for full data.", flush=True)
        
        cursor.execute("SELECT COUNT(*) FROM locations")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"Location database already loaded ({count:,} locations)", flush=True)
            return True
    
    if not os.path.exists(locations_file):
        print(f"WARNING: {locations_file} not found. Location lookup will be skipped.", flush=True)
        return False
    
    print(f"\nImporting location data from {locations_file}...", flush=True)
    print("This may take a minute...", flush=True)
    
    # Create locations table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS locations (
        geonameid INTEGER PRIMARY KEY,
        name TEXT,
        asciiname TEXT,
        latitude REAL,
        longitude REAL,
        feature_class TEXT,
        feature_code TEXT,
        country_code TEXT,
        admin1_code TEXT,
        admin2_code TEXT
    )
    ''')
    
    # Create indexes for fast spatial queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lat_lon ON locations(latitude, longitude)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lat ON locations(latitude)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lon ON locations(longitude)')
    
    conn.commit()
    
    # Import data
    imported_count = 0
    error_count = 0
    
    try:
        with open(locations_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if shutdown_requested:
                    print("\nLocation import interrupted by user", flush=True)
                    conn.commit()
                    return False
                
                if line_num % 100000 == 0:
                    print(f"  Imported {imported_count:,} locations... ({line_num:,} lines processed)", flush=True)
                    conn.commit()  # Periodic commit
                
                fields = line.strip().split('\t')
                if len(fields) < 9:
                    error_count += 1
                    continue
                
                try:
                    geonameid = int(fields[0]) if fields[0] else None
                    name = fields[1] if len(fields) > 1 else None
                    asciiname = fields[2] if len(fields) > 2 else None
                    latitude = float(fields[4]) if len(fields) > 4 and fields[4] else None
                    longitude = float(fields[5]) if len(fields) > 5 and fields[5] else None
                    feature_class = fields[6] if len(fields) > 6 else None
                    feature_code = fields[7] if len(fields) > 7 else None
                    country_code = fields[8] if len(fields) > 8 else None
                    admin1_code = fields[10] if len(fields) > 10 and fields[10] else None  # Field 11 (0-indexed: 10)
                    admin2_code = fields[11] if len(fields) > 11 and fields[11] else None  # Field 12 (0-indexed: 11)
                    
                    if geonameid and latitude is not None and longitude is not None:
                        cursor.execute('''
                        INSERT OR IGNORE INTO locations 
                        (geonameid, name, asciiname, latitude, longitude, feature_class, feature_code, country_code, admin1_code, admin2_code)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (geonameid, name, asciiname, latitude, longitude, feature_class, feature_code, country_code, admin1_code, admin2_code))
                        imported_count += 1
                except (ValueError, IndexError) as e:
                    error_count += 1
                    continue
        
        conn.commit()
        print(f"\nLocation import complete: {imported_count:,} locations imported", flush=True)
        if error_count > 0:
            print(f"  ({error_count:,} lines skipped due to errors)", flush=True)
        return True
        
    except Exception as e:
        print(f"ERROR: Error importing locations: {e}", flush=True)
        conn.rollback()
        return False

# Helper: Format location string
def format_location_string(name, admin1_code, country_code):
    """
    Format location as "City, State, Country" or "City, Country" if no state.
    Examples: "Cincinnati, OH, USA" or "London, GBR"
    """
    if not name:
        return None
    
    parts = [name]
    
    # Add state/province if available
    if admin1_code:
        parts.append(admin1_code)
    
    # Add country code if available
    if country_code:
        parts.append(country_code)
    
    return ", ".join(parts)

# Helper: Find nearest location using database query
def find_nearest_location(lat, lon, cursor, max_distance_km=50):
    """
    Find the nearest location from database based on GPS coordinates.
    Uses SQL query with bounding box for fast lookup.
    Returns formatted location string like "Cincinnati, OH, USA" or None if no location found within max_distance_km.
    """
    global shutdown_requested
    
    if shutdown_requested:
        return None
    
    try:
        # Calculate bounding box (rough approximation: 1 degree ≈ 111 km)
        # Add some buffer for the max_distance
        lat_buffer = max_distance_km / 111.0
        lon_buffer = max_distance_km / (111.0 * abs(math.cos(math.radians(lat))))
        
        # Query locations within bounding box - get all needed fields for formatting
        query = '''
        SELECT name, latitude, longitude, admin1_code, country_code
        FROM locations
        WHERE latitude BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
        '''
        
        cursor.execute(query, (
            lat - lat_buffer,
            lat + lat_buffer,
            lon - lon_buffer,
            lon + lon_buffer
        ))
        
        candidates = cursor.fetchall()
        
        if not candidates:
            return None
        
        # Find the closest candidate using Haversine formula
        nearest_location_data = None
        min_distance = float('inf')
        
        for name, loc_lat, loc_lon, admin1_code, country_code in candidates:
            if shutdown_requested:
                return None
            
            distance = haversine_distance(lat, lon, loc_lat, loc_lon)
            
            if distance < min_distance:
                min_distance = distance
                nearest_location_data = (name, admin1_code, country_code)
                
                # If we found a very close match, we can break early
                if distance < 0.5:  # Within 500m
                    break
        
        if min_distance <= max_distance_km and nearest_location_data:
            name, admin1_code, country_code = nearest_location_data
            return format_location_string(name, admin1_code, country_code)
        else:
            return None
            
    except Exception as e:
        print(f"ERROR: Error querying location database: {e}", flush=True)
        return None

# Function: Migrate database schema if needed
def migrate_database(cursor):
    """Add new columns to existing database if they don't exist"""
    try:
        # Check if status column exists
        cursor.execute("PRAGMA table_info(photos)")
        columns = [row[1] for row in cursor.fetchall()]
        
        migrations = []
        if 'status' not in columns:
            migrations.append("ALTER TABLE photos ADD COLUMN status TEXT DEFAULT 'processed'")
        if 'file_hash' not in columns:
            migrations.append("ALTER TABLE photos ADD COLUMN file_hash TEXT")
        if 'file_mtime' not in columns:
            migrations.append("ALTER TABLE photos ADD COLUMN file_mtime REAL")
        if 'processed_at' not in columns:
            migrations.append("ALTER TABLE photos ADD COLUMN processed_at TEXT")
        if 'error_message' not in columns:
            migrations.append("ALTER TABLE photos ADD COLUMN error_message TEXT")
        
        for migration in migrations:
            cursor.execute(migration)
        
        return len(migrations) > 0
    except Exception as e:
        print(f"WARNING: Database migration issue: {e}", flush=True)
        return False

# Function: Process images and extract EXIF data
def process_images(image_dir, db_file=DB_FILE, force_reprocess=False, skip_location_lookup=False):
    """Extract EXIF data from images and store in SQLite database"""
    
    print(f"\nStarting image processing...", flush=True)
    print(f"  Directory: {image_dir}", flush=True)
    print(f"  Database: {db_file}", flush=True)
    print(f"  Force reprocess: {force_reprocess}", flush=True)
    print(f"  Skip location lookup: {skip_location_lookup}\n", flush=True)
    
    if not os.path.exists(image_dir):
        print(f"ERROR: Directory '{image_dir}' does not exist.", flush=True)
        return False
    
    # Connect to SQLite
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Create table with all columns
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        filepath TEXT UNIQUE,
        datetime TEXT,
        camera_model TEXT,
        lens_model TEXT,
        iso TEXT,
        fnumber TEXT,
        exposure_time TEXT,
        focal_length TEXT,
        orientation TEXT,
        gps_lat REAL,
        gps_lon REAL,
        location TEXT,
        status TEXT DEFAULT 'processed',
        file_hash TEXT,
        file_mtime REAL,
        processed_at TEXT,
        error_message TEXT
    )
    ''')
    
    # Migrate existing database
    migrated = migrate_database(cursor)
    conn.commit()
    
    # Import location data if needed and location lookup is enabled
    if not skip_location_lookup and os.path.exists(LOCATIONS_FILE):
        import_locations_to_db(cursor, conn)
    
    # Get set of already processed files (for resume capability)
    if not force_reprocess:
        cursor.execute("SELECT filepath, file_mtime, file_hash FROM photos WHERE status = 'processed'")
        processed_files = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        print(f"Found {len(processed_files)} already processed files (will skip unchanged)", flush=True)
    else:
        processed_files = {}
        print("Force reprocess mode: will reprocess all files", flush=True)
    
    # Check if cities500.txt exists
    if not os.path.exists(LOCATIONS_FILE):
        print(f"WARNING: {LOCATIONS_FILE} not found. Location lookup will be skipped.", flush=True)
    else:
        print(f"Location lookup enabled using {LOCATIONS_FILE}", flush=True)
    
    # Statistics
    image_count = 0
    skipped_count = 0
    error_count = 0
    gps_count = 0
    new_count = 0
    updated_count = 0
    
    # Collect all image files first
    print(f"\nScanning images in: {image_dir}...", flush=True)
    all_image_files = []
    for root, dirs, files in os.walk(image_dir):
        if shutdown_requested:
            break
        for file in files:
            if not file.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.tif', '.raw', '.cr2', '.nef')):
                continue
            filepath = os.path.join(root, file)
            all_image_files.append(filepath)
    
    total_files = len(all_image_files)
    print(f"Found {total_files} image files to process\n", flush=True)
    
    # Process each file with progress bar
    pbar = tqdm(total=total_files, desc="Processing images", unit="image", ncols=100)
    
    for idx, filepath in enumerate(all_image_files, 1):
        # Check for shutdown request
        if shutdown_requested:
            print(f"\nShutdown requested. Processed {image_count} files before stopping.", flush=True)
            pbar.close()
            conn.commit()
            conn.close()
            return False
        
        try:
            # Check if file still exists
            if not os.path.exists(filepath):
                error_count += 1
                pbar.update(1)
                continue
            
            # Check if already processed (unless force_reprocess)
            if not force_reprocess and filepath in processed_files:
                stored_mtime, stored_hash = processed_files[filepath]
                current_mtime = get_file_mtime(filepath)
                
                # Check if file has changed
                if current_mtime and stored_mtime and current_mtime == stored_mtime:
                    skipped_count += 1
                    pbar.update(1)
                    pbar.set_postfix({'processed': image_count, 'skipped': skipped_count, 'errors': error_count})
                    continue
                else:
                    # File changed, will reprocess
                    updated_count += 1
            
            file_hash = calculate_file_hash(filepath)
            file_mtime = get_file_mtime(filepath)
            
            try:
                with open(filepath, 'rb') as f:
                    tags = exifread.process_file(f, details=False)
                    
                    # Date / Time
                    datetime_val = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
                    datetime_val = str(datetime_val) if datetime_val else None
                    
                    # Camera / Phone
                    camera_model = tags.get('Image Model')
                    camera_model = str(camera_model) if camera_model else None
                    
                    # Lens info
                    lens_model = tags.get('EXIF LensModel')
                    lens_model = str(lens_model) if lens_model else None
                    
                    # ISO, FNumber, Exposure
                    iso = str(tags.get('EXIF ISOSpeedRatings')) if 'EXIF ISOSpeedRatings' in tags else None
                    fnumber = str(tags.get('EXIF FNumber')) if 'EXIF FNumber' in tags else None
                    exposure_time = str(tags.get('EXIF ExposureTime')) if 'EXIF ExposureTime' in tags else None
                    focal_length = str(tags.get('EXIF FocalLength')) if 'EXIF FocalLength' in tags else None
                    orientation = str(tags.get('Image Orientation')) if 'Image Orientation' in tags else None
                    
                    # GPS
                    gps_lat = gps_lon = None
                    location = None
                    
                    if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
                        try:
                            gps_lat = dms_to_decimal(tags['GPS GPSLatitude'].values, str(tags.get('GPS GPSLatitudeRef')))
                            gps_lon = dms_to_decimal(tags['GPS GPSLongitude'].values, str(tags.get('GPS GPSLongitudeRef')))
                            gps_count += 1
                            
                            # Look up location (unless skipped)
                            if not skip_location_lookup:
                                location = find_nearest_location(gps_lat, gps_lon, cursor)
                        except Exception as gps_error:
                            pass  # GPS extraction failed, continue without location
                    
                    # Insert or update in DB
                    processed_at = datetime.now().isoformat()
                    
                    cursor.execute('''
                    INSERT OR REPLACE INTO photos (
                        filename, filepath, datetime, camera_model, lens_model,
                        iso, fnumber, exposure_time, focal_length,
                        orientation, gps_lat, gps_lon, location,
                        status, file_hash, file_mtime, processed_at, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        os.path.basename(filepath), filepath, datetime_val, camera_model, lens_model,
                        iso, fnumber, exposure_time, focal_length,
                        orientation, gps_lat, gps_lon, location,
                        'processed', file_hash, file_mtime, processed_at, None
                    ))
                    
                    image_count += 1
                    if filepath not in processed_files:
                        new_count += 1
                    
                    # Commit periodically (every 500 files) for fault tolerance
                    if image_count % 500 == 0:
                        conn.commit()
                    
                    # Update progress bar
                    pbar.update(1)
                    pbar.set_postfix({'processed': image_count, 'skipped': skipped_count, 'errors': error_count})
                        
            except exifread.ExifReadError as e:
                # Corrupted EXIF data - still record the file
                error_msg = f"EXIF read error: {str(e)}"
                
                file_hash = calculate_file_hash(filepath)
                file_mtime = get_file_mtime(filepath)
                processed_at = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT OR REPLACE INTO photos (
                    filename, filepath, datetime, camera_model, lens_model,
                    iso, fnumber, exposure_time, focal_length,
                    orientation, gps_lat, gps_lon, location,
                    status, file_hash, file_mtime, processed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    os.path.basename(filepath), filepath, None, None, None,
                    None, None, None, None,
                    None, None, None, None,
                    'failed', file_hash, file_mtime, processed_at, error_msg
                ))
                error_count += 1
                if image_count % 500 == 0:
                    conn.commit()
                
                pbar.update(1)
                pbar.set_postfix({'processed': image_count, 'skipped': skipped_count, 'errors': error_count})
                    
        except Exception as e:
            # Critical error processing file
            error_msg = f"Processing error: {str(e)}"
            
            try:
                file_hash = calculate_file_hash(filepath)
                file_mtime = get_file_mtime(filepath)
                processed_at = datetime.now().isoformat()
                
                cursor.execute('''
                INSERT OR REPLACE INTO photos (
                    filename, filepath, datetime, camera_model, lens_model,
                    iso, fnumber, exposure_time, focal_length,
                    orientation, gps_lat, gps_lon, location,
                    status, file_hash, file_mtime, processed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    os.path.basename(filepath), filepath, None, None, None,
                    None, None, None, None,
                    None, None, None, None,
                    'failed', file_hash, file_mtime, processed_at, error_msg
                ))
                error_count += 1
                if error_count % 500 == 0:
                    conn.commit()
            except Exception as db_error:
                pass  # Could not record error, continue
            
            pbar.update(1)
            pbar.set_postfix({'processed': image_count, 'skipped': skipped_count, 'errors': error_count})
    
    # Close progress bar
    pbar.close()
    
    # Final commit
    conn.commit()
    conn.close()
    
    # Print summary
    print("\n" + "="*60, flush=True)
    print("Processing Summary:", flush=True)
    print(f"  Total files found: {total_files}", flush=True)
    print(f"  Newly processed: {new_count}", flush=True)
    print(f"  Updated (changed): {updated_count}", flush=True)
    print(f"  Skipped (unchanged): {skipped_count}", flush=True)
    print(f"  Failed: {error_count}", flush=True)
    print(f"  With GPS data: {gps_count}", flush=True)
    print(f"  Total in database: {image_count + error_count}", flush=True)
    print("="*60, flush=True)
    print(f"Done! Metadata saved to {db_file}\n", flush=True)
    return True

# Function: Export to CSV
def export_to_csv(db_file=DB_FILE, output_file=None, group_by_day=False, group_by_location=False):
    """Export photo metadata from SQLite database to CSV file"""
    
    if not os.path.exists(db_file):
        print(f"ERROR: Database '{db_file}' does not exist.", flush=True)
        return False
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Determine output filename
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if group_by_day and group_by_location:
            output_file = f'photo_export_by_day_location_{timestamp}.csv'
        elif group_by_day:
            output_file = f'photo_export_by_day_{timestamp}.csv'
        elif group_by_location:
            output_file = f'photo_export_by_location_{timestamp}.csv'
        else:
            output_file = f'photo_export_{timestamp}.csv'
    
    # Build query based on grouping
    if group_by_day and group_by_location:
        # Group by day and location
        query = '''
        SELECT 
            DATE(datetime) as day,
            location,
            COUNT(*) as photo_count,
            GROUP_CONCAT(filename, '; ') as filenames
        FROM photos
        WHERE datetime IS NOT NULL
        GROUP BY DATE(datetime), location
        ORDER BY day DESC, location
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Day', 'Location', 'Photo Count', 'Filenames'])
            writer.writerows(rows)
    
    elif group_by_day:
        # Group by day
        query = '''
        SELECT 
            DATE(datetime) as day,
            COUNT(*) as photo_count,
            GROUP_CONCAT(filename, '; ') as filenames
        FROM photos
        WHERE datetime IS NOT NULL
        GROUP BY DATE(datetime)
        ORDER BY day DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Day', 'Photo Count', 'Filenames'])
            writer.writerows(rows)
    
    elif group_by_location:
        # Group by location
        query = '''
        SELECT 
            location,
            COUNT(*) as photo_count,
            GROUP_CONCAT(filename, '; ') as filenames
        FROM photos
        WHERE location IS NOT NULL
        GROUP BY location
        ORDER BY photo_count DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Location', 'Photo Count', 'Filenames'])
            writer.writerows(rows)
    
    else:
        # Export all data
        # Check if status column exists
        cursor.execute("PRAGMA table_info(photos)")
        columns = [row[1] for row in cursor.fetchall()]
        has_status = 'status' in columns
        
        if has_status:
            query = '''
            SELECT 
                id, filename, filepath, datetime, camera_model, lens_model,
                iso, fnumber, exposure_time, focal_length, orientation,
                gps_lat, gps_lon, location, status, processed_at, error_message
            FROM photos
            ORDER BY datetime DESC
            '''
            cursor.execute(query)
            rows = cursor.fetchall()
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'ID', 'Filename', 'Filepath', 'DateTime', 'Camera Model', 'Lens Model',
                    'ISO', 'F-Number', 'Exposure Time', 'Focal Length', 'Orientation',
                    'GPS Latitude', 'GPS Longitude', 'Location', 'Status', 'Processed At', 'Error Message'
                ])
                writer.writerows(rows)
        else:
            query = '''
            SELECT 
                id, filename, filepath, datetime, camera_model, lens_model,
                iso, fnumber, exposure_time, focal_length, orientation,
                gps_lat, gps_lon, location
            FROM photos
            ORDER BY datetime DESC
            '''
            cursor.execute(query)
            rows = cursor.fetchall()
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'ID', 'Filename', 'Filepath', 'DateTime', 'Camera Model', 'Lens Model',
                    'ISO', 'F-Number', 'Exposure Time', 'Focal Length', 'Orientation',
                    'GPS Latitude', 'GPS Longitude', 'Location'
                ])
                writer.writerows(rows)
    
    conn.close()
    print(f"Export complete! Data saved to {output_file}", flush=True)
    return True

# Main function
def main():
    parser = argparse.ArgumentParser(description='Extract EXIF data from images and manage photo metadata database')
    parser.add_argument('command', choices=['process', 'export'], 
                       help='Command to execute: "process" to extract EXIF data, "export" to export to CSV')
    parser.add_argument('--folder', '-f', type=str, 
                       help='Path to folder containing images (required for "process" command)')
    parser.add_argument('--db', '-d', type=str, default=None,
                       help='SQLite database file (default: auto-derived from folder name, e.g., library7.db for /path/to/library7/)')
    parser.add_argument('--output', '-o', type=str,
                       help='Output CSV file (optional, auto-generated if not provided)')
    parser.add_argument('--group-by-day', action='store_true',
                       help='Group export by day')
    parser.add_argument('--group-by-location', action='store_true',
                       help='Group export by location')
    parser.add_argument('--force-reprocess', action='store_true',
                       help='Force reprocessing of all files, even if already processed')
    parser.add_argument('--skip-location', action='store_true',
                       help='Skip location lookup for faster processing')
    
    args = parser.parse_args()
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    
    print("="*60, flush=True)
    print("Image History - EXIF Metadata Extractor", flush=True)
    print("="*60, flush=True)
    print("Press Ctrl+C to stop gracefully\n", flush=True)
    
    if args.command == 'process':
        if not args.folder:
            print("ERROR: --folder is required for 'process' command", flush=True)
            parser.print_help()
            sys.exit(1)
        
        # Derive database filename from folder if not explicitly provided
        if args.db is None:
            args.db = get_db_filename_from_folder(args.folder)
            print(f"Auto-derived database filename: {args.db}", flush=True)
        
        process_images(args.folder, args.db, args.force_reprocess, args.skip_location)
    
    elif args.command == 'export':
        # For export, use default if not provided
        if args.db is None:
            args.db = DB_FILE
        export_to_csv(args.db, args.output, args.group_by_day, args.group_by_location)

if __name__ == '__main__':
    main()
