from flask import Flask, render_template, request, send_file, jsonify, Response
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

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__,
    static_folder='static',
    template_folder='templates'
)

# Configure folders
UPLOAD_FOLDER = 'uploads'
TEMP_FOLDER = 'temp'
for folder in [UPLOAD_FOLDER, TEMP_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TEMP_FOLDER'] = TEMP_FOLDER

def validate_filename(filename):
    """Validate and sanitize filename"""
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
    # Get list of available MP4 files
    mp4_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('.mp4')]
    mp4_files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x)), reverse=True)
    return render_template('index.html', mp4_files=mp4_files)

@app.route('/download-video', methods=['POST'])
def download_video():
    try:
        video_url = request.form['video_url']
        filename = request.form['filename']
        
        # Validate and sanitize filename
        filename = validate_filename(filename)
        
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
            
    except Exception as e:
        logging.error(f"Error initiating download: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

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
        input_file = data['input_file']
        start_time = data['start_time']
        end_time = data['end_time']
        filename = data['filename']
        crop_data = data['crop_data']
        
        # Validate filename
        filename = validate_filename(filename)
        base_filename = os.path.splitext(filename)[0]
        
        # Validate timestamps
        try:
            validate_timestamp(start_time)
            validate_timestamp(end_time)
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 400
        
        # Create a process ID
        process_id = os.urandom(16).hex()
        
        try:
            # Create temporary directory for processing
            temp_dir = os.path.join(app.config['TEMP_FOLDER'], process_id)
            os.makedirs(temp_dir, exist_ok=True)
            
            # Setup output filenames
            screen_file = f"screen_{base_filename}.mp4"
            webcam_file = f"webcam_{base_filename}.mp4"
            
            # Start processing in a separate thread
            def process_task():
                try:
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
                    
                    progress_tracker.update_progress(process_id, {
                        "status": "creating_zip",
                        "message": "Creating download package...",
                        "progress": 90
                    })
                    
                    # Create zip file
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    zip_filename = f"{base_filename}_{timestamp}.zip"
                    zip_path = os.path.join(app.config['TEMP_FOLDER'], zip_filename)
                    
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for file in output_files:
                            if os.path.exists(file):
                                zipf.write(file, os.path.basename(file))
                            else:
                                logging.error(f"Output file not found: {file}")
                    
                    if not os.path.exists(zip_path):
                        raise Exception("Failed to create zip file")
                    
                    # Update progress with download URL
                    progress_tracker.update_progress(process_id, {
                        "status": "complete",
                        "message": "Processing complete!",
                        "progress": 100,
                        "download_url": f'/download-processed/{zip_filename}'
                    })
                    
                except Exception as e:
                    logging.error(f"Processing error: {str(e)}")
                    progress_tracker.update_progress(process_id, {
                        "status": "error",
                        "message": f"Error: {str(e)}"
                    })
                finally:
                    # Clean up temporary directory
                    if os.path.exists(temp_dir):
                        try:
                            shutil.rmtree(temp_dir)
                        except Exception as e:
                            logging.error(f"Error cleaning up temp dir: {str(e)}")
            
            # Start processing thread
            thread = threading.Thread(target=process_task)
            thread.start()
            
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)