from flask import Flask, render_template, request, send_file, jsonify, Response
from video_processor import download_full_video, trim_video, get_video_duration
import os
from queue import Queue
import json
import re

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Store progress information
progress_queues = {}

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
        
        # Create a queue for this process
        process_id = os.urandom(16).hex()
        progress_queues[process_id] = Queue()
        
        try:
            # Download and convert the full video
            output_file = download_full_video(
                video_url=video_url,
                filename=filename,
                progress_queue=progress_queues[process_id]
            )
            
            # Get video duration
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], output_file)
            duration = get_video_duration(video_path)
            
            return jsonify({
                'success': True,
                'message': 'Video downloaded and converted successfully',
                'filename': output_file,
                'duration': duration,
                'process_id': process_id
            })
            
        except Exception as e:
            progress_queues.pop(process_id, None)
            raise e
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/trim-video', methods=['POST'])
def trim():
    try:
        input_file = request.form['input_file']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        filename = request.form['filename']
        
        # Validate filename
        filename = validate_filename(filename)
        
        # Validate timestamps
        try:
            validate_timestamp(start_time)
            validate_timestamp(end_time)
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 400
        
        # Create a queue for this process
        process_id = os.urandom(16).hex()
        progress_queues[process_id] = Queue()
        
        try:
            # Trim the video
            output_file = trim_video(
                input_file=input_file,
                filename=filename,
                start_time=start_time,
                end_time=end_time,
                progress_queue=progress_queues[process_id]
            )
            
            return jsonify({
                'success': True,
                'message': 'Video trimmed successfully',
                'download_url': f'/download/{output_file}',
                'process_id': process_id
            })
            
        except Exception as e:
            progress_queues.pop(process_id, None)
            raise e
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/progress/<process_id>')
def progress(process_id):
    def generate():
        queue = progress_queues.get(process_id)
        if queue:
            while True:
                try:
                    progress = queue.get()
                    if progress == 'DONE':
                        break
                    yield f"data: {json.dumps(progress)}\n\n"
                except Exception as e:
                    print(f"Error in progress generation: {e}")
                    break
            # Clean up the queue
            progress_queues.pop(process_id, None)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/<filename>')
def download(filename):
    try:
        return send_file(
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return str(e), 404

@app.route('/get-duration/<filename>')
def get_duration(filename):
    try:
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        duration = get_video_duration(video_path)
        return jsonify({
            'success': True,
            'duration': duration
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)