import requests
import os
import subprocess
import logging
import time
import shutil
import re
from typing import List, Dict
from progress_tracker import progress_tracker
from queue import Queue  # Add this if it's missing
import traceback

def update_progress(queue: Queue, message: str):
    """Send progress update through the queue"""
    try:
        queue.put({
            'message': message
        })
    except Exception as e:
        logging.error(f"Error sending progress update: {str(e)}")

def format_time(seconds):
    """Format seconds into HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def format_speed(bytes_per_second):
    """Format speed in bytes/second to a human-readable format"""
    if bytes_per_second < 1024:
        return f"{bytes_per_second:.1f} B/s"
    elif bytes_per_second < 1024 * 1024:
        return f"{bytes_per_second/1024:.1f} KB/s"
    else:
        return f"{bytes_per_second/(1024*1024):.1f} MB/s"

def get_duration_from_ffmpeg(file_or_url):
    """Get duration using FFprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_or_url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except:
        return None

def download_full_video(video_url: str, filename: str, process_id: str) -> str:
    """Download video directly using FFmpeg with progress tracking"""
    output_path = os.path.join('uploads', filename)
    start_time = time.time()  # Initialize start_time at the beginning
    
    try:
        # Get video duration first
        total_duration = get_duration_from_ffmpeg(video_url)
        
        # FFmpeg command for direct download with progress
        ffmpeg_command = [
            'ffmpeg',
            '-i', video_url,
            '-c', 'copy',
            '-y',
            '-progress', '-',
            '-nostats',
            output_path
        ]
        
        process = subprocess.Popen(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Pattern to extract time from FFmpeg output
        time_pattern = re.compile(r'out_time_ms=(\d+)')
        
        while True:
            line = process.stdout.readline()
            
            if process.poll() is not None:
                break
                
            if line:
                # Extract time from FFmpeg output
                time_match = time_pattern.search(line)
                if time_match:
                    time_ms = int(time_match.group(1))
                    current_time = time_ms / 1000000  # Convert to seconds
                    
                    # Calculate progress percentage if duration is available
                    progress = 0
                    if total_duration:
                        progress = min(100, (current_time / total_duration) * 100)
                    
                    # Format current time
                    time_str = format_time(current_time)
                    
                    # Calculate speed and time remaining
                    elapsed_time = time.time() - start_time
                    if elapsed_time > 0 and total_duration:
                        speed = (current_time / elapsed_time) * 1024 * 1024  # Approximate bytes/second
                        remaining_time = (total_duration - current_time) * (elapsed_time / current_time) if current_time > 0 else 0
                        
                        progress_data = {
                            "status": "downloading",
                            "progress": progress,
                            "current_time": time_str,
                            "elapsed": format_time(int(elapsed_time)),
                            "remaining": format_time(int(remaining_time)),
                            "speed": format_speed(speed),
                            "message": f"Downloading: {time_str}"
                        }
                    else:
                        progress_data = {
                            "status": "downloading",
                            "progress": progress,
                            "current_time": time_str,
                            "message": f"Downloading: {time_str}"
                        }
                    
                    progress_tracker.update_progress(process_id, progress_data)
        
        # Check if process completed successfully
        if process.returncode != 0:
            error_output = process.stderr.read()
            raise Exception(f"FFmpeg error: {error_output}")
        
        # Update final progress
        progress_tracker.update_progress(process_id, {
            "status": "complete",
            "progress": 100,
            "message": "Download complete"
        })
        
        return filename
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error downloading video: {error_msg}")
        
        # Update error progress
        progress_tracker.update_progress(process_id, {
            "status": "error",
            "message": f"Error: {error_msg}"
        })
        
        # Clean up output file if it exists
        if os.path.exists(output_path):
            os.remove(output_path)
            
        raise Exception(error_msg)
    
def trim_video(input_file: str, screen_output: str, webcam_output: str, 
               start_time: str, end_time: str, crop_data: Dict, 
               progress_queue: Queue) -> List[str]:
    """
    Trim and crop video into screen share and webcam videos
    Returns list of output file paths
    """
    input_path = os.path.join('uploads', input_file)
    output_files = []
    
    try:
        # Validate input file
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_file}")

        update_progress(progress_queue, 'Processing screen share video...')
        
        # Process screen share area
        screen_crop = crop_data['screen']
        screen_command = [
            'ffmpeg',
            '-i', input_path,
            '-ss', start_time,
            '-to', end_time,
            '-filter:v', f'crop={int(screen_crop["width"])}:{int(screen_crop["height"])}:{int(screen_crop["x"])}:{int(screen_crop["y"])}',
            '-c:a', 'copy',
            '-y',
            screen_output
        ]
        
        try:
            subprocess.run(screen_command, capture_output=True, text=True, check=True)
            output_files.append(screen_output)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error (screen): {e.stderr}")
            
        update_progress(progress_queue, 'Processing webcam video...')
        
        # Process webcam area
        webcam_crop = crop_data['webcam']
        webcam_command = [
            'ffmpeg',
            '-i', input_path,
            '-ss', start_time,
            '-to', end_time,
            '-filter:v', f'crop={int(webcam_crop["width"])}:{int(webcam_crop["height"])}:{int(webcam_crop["x"])}:{int(webcam_crop["y"])}',
            '-c:a', 'copy',
            '-y',
            webcam_output
        ]
        
        try:
            subprocess.run(webcam_command, capture_output=True, text=True, check=True)
            output_files.append(webcam_output)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error (webcam): {e.stderr}")
        
        update_progress(progress_queue, 'Finalizing...')
        progress_queue.put('DONE')
        
        return output_files
        
    except Exception as e:
        error_msg = f"Error processing video: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        progress_queue.put('DONE')
        
        # Clean up any output files if there was an error
        for file in output_files:
            if os.path.exists(file):
                os.remove(file)
                
        raise Exception(error_msg)

def resize_videos(screen_input: str, webcam_input: str, progress_queue: Queue = None) -> List[str]:
    """
    Resize cropped videos to specific resolutions while maintaining aspect ratio
    Screen: 1530x1080
    Webcam: 360x270
    Returns list of resized output file paths
    """
    output_files = []
    try:
        if progress_queue:
            update_progress(progress_queue, 'Resizing screen recording...')

        # Create output filenames
        screen_output = screen_input.replace('.mp4', '_resized.mp4')
        webcam_output = webcam_input.replace('.mp4', '_resized.mp4')

        # Resize screen recording with padding to maintain aspect ratio
        screen_command = [
            'ffmpeg',
            '-i', screen_input,
            '-vf', 'scale=1530:1080:force_original_aspect_ratio=decrease,pad=1530:1080:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264',  # Use H.264 codec
            '-preset', 'ultrafast',  # Fastest encoding
            '-crf', '23',  # Balanced quality and size
            '-c:a', 'copy',  # Copy audio stream
            '-y',
            screen_output
        ]

        try:
            subprocess.run(screen_command, capture_output=True, text=True, check=True)
            output_files.append(screen_output)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error (screen resize): {e.stderr}")

        if progress_queue:
            update_progress(progress_queue, 'Resizing webcam recording...')

        # Resize webcam recording with padding
        webcam_command = [
            'ffmpeg',
            '-i', webcam_input,
            '-vf', 'scale=360:270:force_original_aspect_ratio=decrease,pad=360:270:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264',  # Use H.264 codec
            '-preset', 'ultrafast',  # Fastest encoding
            '-crf', '23',  # Balanced quality and size
            '-c:a', 'copy',  # Copy audio stream
            '-y',
            webcam_output
        ]

        try:
            subprocess.run(webcam_command, capture_output=True, text=True, check=True)
            output_files.append(webcam_output)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error (webcam resize): {e.stderr}")

        if progress_queue:
            update_progress(progress_queue, 'Resizing completed...')
            progress_queue.put('DONE')

        return output_files

    except Exception as e:
        error_msg = f"Error resizing videos: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        if progress_queue:
            progress_queue.put('DONE')

        # Clean up any output files if there was an error
        for file in output_files:
            if os.path.exists(file):
                os.remove(file)

        raise Exception(error_msg)

def get_video_duration(file_path: str) -> str:
    """Get video duration using FFprobe"""
    duration = get_duration_from_ffmpeg(file_path)
    if duration is None:
        raise Exception("Could not determine video duration")
        
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def calculate_default_crop_areas(video_width: int, video_height: int) -> dict:
    """Calculate default crop areas for screen and webcam"""
    # Screen takes up most of the space (80% width, full height)
    screen_width = int(video_width * 0.8)
    screen_height = video_height
    screen_x = 0
    screen_y = 0
    
    # Webcam takes top-right corner (20% width, 25% height)
    webcam_width = int(video_width * 0.2)
    webcam_height = int(video_height * 0.25)
    webcam_x = screen_width
    webcam_y = 0
    
    return {
        'screen': {
            'x': screen_x,
            'y': screen_y,
            'width': screen_width,
            'height': screen_height
        },
        'webcam': {
            'x': webcam_x,
            'y': webcam_y,
            'width': webcam_width,
            'height': webcam_height
        }
    }