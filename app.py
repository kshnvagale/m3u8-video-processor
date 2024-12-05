from flask import Flask, render_template, request, send_file, jsonify, current_app, Response
from video_processor import download_full_video, trim_video, get_video_duration
import os
import logging
import json
import re
import zipfile
import shutil
import threading
import time
from datetime import datetime
from progress_tracker import progress_tracker
from pathlib import Path




# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__,
    static_folder='static',
    template_folder='templates'
)

def get_downloads_path():
    """Get user's Downloads folder path"""
    try:
        # Get the downloads folder path based on OS
        if os.name == 'nt':  # Windows
            import winreg
            sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
            downloads_guid = '{374DE290-123F-4565-9164-39C4925E467B}'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                downloads_path = winreg.QueryValueEx(key, downloads_guid)[0]
        else:  # Linux/Mac
            downloads_path = str(Path.home() / "Downloads")
        
        # Create a subfolder for our app
        app_downloads = os.path.join(downloads_path, "video_processor")
        if not os.path.exists(app_downloads):
            os.makedirs(app_downloads)
            
        return app_downloads
    except Exception as e:
        logging.error(f"Error getting downloads path: {str(e)}")
        # Fallback to current directory if we can't get Downloads folder
        return os.path.join(os.getcwd(), "downloads")

# Configure folders using Downloads path
BASE_DOWNLOAD_PATH = get_downloads_path()
UPLOAD_FOLDER = os.path.join(BASE_DOWNLOAD_PATH, 'uploads')
TEMP_FOLDER = os.path.join(BASE_DOWNLOAD_PATH, 'temp')

# Create folders if they don't exist
for folder in [UPLOAD_FOLDER, TEMP_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TEMP_FOLDER'] = TEMP_FOLDER

def validate_filename(filename, is_segment=False):
    """Validate and sanitize filename"""
    if is_segment:
        try:
            num = int(filename)
            if num < 1:
                raise ValueError('Segment number must be positive')
            return str(num)
        except ValueError:
            raise ValueError('Invalid segment number')
    else:
        # Remove any directory components
        filename = os.path.basename(filename)
        
        # Replace invalid characters with underscore
        filename = re.sub(r'[^\w\-_.]', '_', filename)
        
        # Ensure it ends with .mp4
        if not filename.lower().endswith('.mp4'):
            filename += '.mp4'
        
        return filename

def validate_timestamp(timestamp):
    """Validate HH:MM:SS format"""
    pattern = re.compile(r'^([0-9]{2}):([0-9]{2}):([0-9]{2})$')
    if not pattern.match(timestamp):
        raise ValueError('Time must be in HH:MM:SS format')
    
    hours, minutes, seconds = map(int, timestamp.split(':'))
    if hours > 23 or minutes > 59 or seconds > 59:
        raise ValueError('Invalid time values')
    return True

@app.route('/')
def index():
    # Get list of available MP4 files, excluding processed files
    mp4_files = [f for f in os.listdir(UPLOAD_FOLDER) 
                 if f.endswith('.mp4') and not any(x in f for x in ['_screen', '_av'])]
    mp4_files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x)), reverse=True)
    return render_template('index.html', mp4_files=mp4_files)


@app.route('/check-progress/<process_id>')
def check_progress(process_id):
    """Check progress for a specific process"""
    progress_data = progress_tracker.get_progress(process_id)
    return jsonify(progress_data)

@app.route('/download/<filename>')
def download(filename):
    try:
        if not filename or '..' in filename:
            raise ValueError("Invalid filename")
            
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {filename}")
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logging.error(f"Download error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 404

@app.route('/download-processed/<filename>')
def download_processed(filename):
    try:
        if not filename or '..' in filename:
            raise ValueError("Invalid filename")
            
        zip_path = os.path.join(app.config['TEMP_FOLDER'], filename)
        
        if not os.path.exists(zip_path):
            logging.error(f"Zip file not found: {zip_path}")
            return jsonify({
                'success': False,
                'message': 'Download file not found'
            }), 404
            
        try:
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/zip'
            )
        finally:
            # Clean up zip file after sending
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception as e:
                    logging.error(f"Error removing zip file: {str(e)}")
                    
    except Exception as e:
        logging.error(f"Error in download_processed: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Download error: {str(e)}"
        }), 500

@app.route('/get-duration/<filename>')
def get_duration_route(filename):
    try:
        # Validate and sanitize the filename
        if not filename or '..' in filename:
            raise ValueError("Invalid filename")
            
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Check if file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {filename}")
            
        # Get duration using FFprobe
        duration = get_video_duration(video_path)
        
        return jsonify({
            'success': True,
            'duration': duration
        })
        
    except FileNotFoundError as e:
        logging.error(f"File not found error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 404
        
    except Exception as e:
        logging.error(f"Error getting video duration: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error getting video duration: {str(e)}"
        }), 500

@app.route('/process-video', methods=['POST'])
def process_video():
    try:
        data = request.get_json()
        
        # For video download (Part 1)
        if 'video_url' in data:
            video_url = data.get('video_url')
            filename = data.get('filename')
            
            if not video_url or not filename:
                raise ValueError('Video URL and filename are required')
            
            # Add .mp4 extension if not present
            if not filename.lower().endswith('.mp4'):
                filename += '.mp4'
                
            # Create a process ID
            process_id = os.urandom(16).hex()
            
            # Start download in a separate thread
            def download_task():
                try:
                    download_full_video(video_url, filename, process_id)
                except Exception as e:
                    logging.error(f"Download error: {str(e)}")
                    progress_tracker.update_progress(process_id, {
                        "status": "error",
                        "message": f"Error: {str(e)}"
                    })
            
            thread = threading.Thread(target=download_task)
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Download started',
                'filename': filename,
                'process_id': process_id
            })
        
        # For video processing (Part 2)
        else:
            input_file = data['input_file']
            start_time = data['start_time']
            end_time = data['end_time']
            segment_number = data['filename']
            crop_data = data['crop_data']
            
            # Create a process ID
            process_id = os.urandom(16).hex()
            
            try:
                # Create temporary directory for processing
                temp_dir = os.path.join(app.config['TEMP_FOLDER'], process_id)
                os.makedirs(temp_dir, exist_ok=True)
                
                # Get original input filename without .mp4 extension
                source_video = os.path.splitext(input_file)[0]
                
                # Create filenames with new format
                screen_file = f"asl_{source_video}_segment-{segment_number}_screen.mp4"
                webcam_file = f"asl_{source_video}_segment-{segment_number}_av.mp4"
                
                # Process the videos
                progress_tracker.update_progress(process_id, {
                    "status": "processing",
                    "message": "Starting video processing...",
                    "progress": 0
                })
                
                output_files = trim_video(
                    input_file=input_file,
                    screen_output=os.path.join(temp_dir, screen_file),
                    webcam_output=os.path.join(temp_dir, webcam_file),
                    start_time=start_time,
                    end_time=end_time,
                    crop_data=crop_data,
                    process_id=process_id
                )
                
                if not output_files:
                    raise Exception("No output files were created")
                
                # Create zip file
                zip_filename = f"asl_{source_video}_segment-{segment_number}_zip.zip"
                zip_path = os.path.join(app.config['TEMP_FOLDER'], zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file in output_files:
                        if os.path.exists(file):
                            zipf.write(file, os.path.basename(file))
                        else:
                            logging.error(f"Output file not found: {file}")
                
                if not os.path.exists(zip_path):
                    raise Exception("Failed to create zip file")
                
                return jsonify({
                    'success': True,
                    'message': 'Processing started',
                    'process_id': process_id
                })
                
            except Exception as e:
                if 'temp_dir' in locals() and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                raise e
                    
    except Exception as e:
        logging.error(f"Process video error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    
@app.route('/cleanup', methods=['POST'])
def cleanup():
    try:
        # Get list of files before cleanup, excluding processed files from uploads count
        files_removed = {
            'uploads': [f for f in os.listdir(app.config['UPLOAD_FOLDER']) 
                       if f.endswith('.mp4') and not any(x in f for x in ['_screen', '_av'])],
            'temp': [f for f in os.listdir(app.config['TEMP_FOLDER']) 
                    if f.endswith('.mp4') or f.endswith('.zip')]
        }
        
        # Clean uploads folder
        for file in files_removed['uploads']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
            os.remove(file_path)
            
        # Clean temp folder
        for file in files_removed['temp']:
            file_path = os.path.join(app.config['TEMP_FOLDER'], file)
            os.remove(file_path)
            
        return jsonify({
            'success': True,
            'message': f"Successfully removed {len(files_removed['uploads'])} videos and {len(files_removed['temp'])} temporary files",
            'files_removed': files_removed
        })
        
    except Exception as e:
        logging.error(f"Cleanup error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error during cleanup: {str(e)}"
        }), 500
    
def cleanup_old_files(max_age_days=7):
    """Clean up files older than max_age_days"""
    try:
        current_time = time.time()
        for folder in [app.config['UPLOAD_FOLDER'], app.config['TEMP_FOLDER']]:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                file_age_days = (current_time - os.path.getmtime(filepath)) / (24 * 3600)
                
                if file_age_days > max_age_days:
                    try:
                        if os.path.isfile(filepath):
                            os.remove(filepath)
                        elif os.path.isdir(filepath):
                            shutil.rmtree(filepath)
                    except Exception as e:
                        logging.error(f"Error removing old file {filepath}: {str(e)}")
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}")

# Add this route to manually trigger cleanup
@app.route('/cleanup-old-files', methods=['POST'])
def trigger_cleanup():
    try:
        cleanup_old_files()
        return jsonify({
            'success': True,
            'message': 'Old files cleaned up successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error during cleanup: {str(e)}'
        }), 500

# Initialize cleanup on first request
def cleanup_init():
    with app.app_context():
        cleanup_old_files()

# Call cleanup_init when app starts
cleanup_init()

if __name__ == '__main__':
    app.run(debug=True, port=5000)