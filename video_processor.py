import requests
import os
import subprocess
import logging
import time
import shutil
import re
from typing import List, Dict
from progress_tracker import progress_tracker
from flask import current_app
from pathlib import Path

def get_downloads_path():
    """Get user's Downloads folder path"""
    try:
        if os.name == 'nt':  # Windows
            import winreg
            sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
            downloads_guid = '{374DE290-123F-4565-9164-39C4925E467B}'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                downloads_path = winreg.QueryValueEx(key, downloads_guid)[0]
        else:  # Linux/Mac
            downloads_path = str(Path.home() / "Downloads")
        app_downloads = os.path.join(downloads_path, "video_processor")
        return app_downloads
    except Exception as e:
        return os.path.join(os.getcwd(), "downloads")

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
    output_path = os.path.join(get_downloads_path(), 'uploads', filename)

    start_time = time.time()
    
    try:
        # Get video duration first
        total_duration = get_duration_from_ffmpeg(video_url)
        
        # FFmpeg command for direct download with progress
        ffmpeg_command = [
            'ffmpeg',
            '-i', video_url,
            '-c', 'copy',           # Copy streams without re-encoding
            '-y',                   # Overwrite output file if it exists
            '-progress', 'pipe:1',  # Output progress to stdout
            '-nostats',             # Disable standard stats output
            '-loglevel', 'error',   # Only show errors in log
            output_path
        ]
        
        process = subprocess.Popen(
            ffmpeg_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )
        
        # Pattern to extract time from FFmpeg output
        time_pattern = re.compile(r'out_time_ms=(\d+)')
        
        while True:
            line = process.stdout.readline()
            
            if not line and process.poll() is not None:
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
        
        # Verify the output file exists and has content
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise Exception("Download failed: Output file is missing or empty")
        
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
               process_id: str) -> List[str]:
    """
    Trim and crop video into screen share and webcam videos
    Returns list of output file paths
    """
    input_path = os.path.join(get_downloads_path(), 'uploads', input_file)
    output_files = []
    
    try:
        # Validate input file
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # Update progress
        progress_tracker.update_progress(process_id, {
            "status": "processing",
            "message": "Processing screen share video...",
            "progress": 0
        })
        
        # Process screen share area
        screen_crop = crop_data['screen']
        screen_command = [
            'ffmpeg',
            '-i', input_path,
            '-ss', start_time,
            '-to', end_time,
            '-filter:v', f'crop={int(screen_crop["width"])}:{int(screen_crop["height"])}:{int(screen_crop["x"])}:{int(screen_crop["y"])}',
            '-an',
            '-y',
            screen_output
        ]
        
        try:
            subprocess.run(screen_command, capture_output=True, text=True, check=True)
            output_files.append(screen_output)
            progress_tracker.update_progress(process_id, {
                "status": "processing",
                "message": "Processing webcam video...",
                "progress": 50
            })
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error (screen): {e.stderr}")
        
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
            progress_tracker.update_progress(process_id, {
                "status": "complete",
                "message": "Processing complete",
                "progress": 100
            })
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error (webcam): {e.stderr}")
        
        return output_files
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error processing video: {error_msg}")
        
        # Update error progress
        progress_tracker.update_progress(process_id, {
            "status": "error",
            "message": f"Error: {error_msg}"
        })
        
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
    screen_width = int(video_width * 1.0)
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