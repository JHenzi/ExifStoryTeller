# TODO - Image History Project

## Completed ✅

- [x] Modify app.py to accept folder path at runtime via command-line arguments
- [x] Add `location` column to database schema
- [x] Implement location lookup from allCountries.txt based on GPS coordinates
- [x] Add CSV export functionality
- [x] Add grouping options for CSV export (by day, by location, by both)
- [x] Add progress indicators during image processing
- [x] Handle missing GPS data gracefully
- [x] Handle missing allCountries.txt file gracefully
- [x] Create README.md with documentation
- [x] Create TODO.md file
- [x] Add fault tolerance and resume capability (track processed files, skip already processed)
- [x] Add status tracking (processed, failed) for each file
- [x] Add file change detection (hash and modification time)
- [x] Add periodic database commits for fault tolerance
- [x] Add database migration support for schema changes
- [x] Add option to skip location lookup for faster processing
- [x] Add better error handling for corrupted images (record failures, continue processing)
- [x] Add force reprocess option

## Future Enhancements 🚀

### Performance Optimizations
- [ ] Optimize location lookup by creating a spatial index or using a more efficient search algorithm
- [ ] Cache location lookups to avoid re-scanning allCountries.txt for similar coordinates
- [x] Add option to skip location lookup for faster processing
- [ ] Implement parallel processing for multiple images

### Database Features
- [x] Add database migration support for schema changes
- [x] Add option to update existing records instead of only inserting
- [ ] Add database query interface (CLI commands to query the database)
- [ ] Add support for database backups

### Export Features
- [ ] Add JSON export format option
- [ ] Add Excel export format option
- [ ] Add filtering options for export (by date range, location, camera model, etc.)
- [ ] Add statistics summary export (total photos, photos per location, etc.)

### Location Features
- [ ] Add support for reverse geocoding APIs (Google Maps, OpenStreetMap) as alternative to allCountries.txt
- [ ] Add more detailed location information (country, state, city hierarchy)
- [ ] Add option to specify maximum distance for location lookup
- [ ] Add support for custom location databases

### EXIF Features
- [ ] Add support for more EXIF tags (white balance, flash, metering mode, etc.)
- [ ] Add support for video files (extract metadata from video files)
- [ ] Add thumbnail extraction and storage
- [ ] Add image dimension extraction (width, height)

### User Interface
- [ ] Add web interface for browsing photos and metadata
- [ ] Add map visualization of photo locations
- [ ] Add timeline view of photos
- [ ] Add search and filter interface

### Data Analysis
- [ ] Add statistics generation (most used camera, favorite locations, etc.)
- [ ] Add photo count by location visualization
- [ ] Add time-based analysis (photos per month/year)
- [ ] Add camera settings analysis (ISO distribution, aperture preferences, etc.)

### Error Handling & Validation
- [x] Add better error handling for corrupted images
- [ ] Add validation for GPS coordinate ranges
- [x] Add logging to file option
- [ ] Add dry-run mode to preview what would be processed

### Documentation
- [ ] Add example usage scripts
- [ ] Add troubleshooting guide
- [ ] Add API documentation for programmatic usage
- [ ] Add contribution guidelines

