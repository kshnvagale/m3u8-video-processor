import requests
import os
import subprocess
import m3u8
from urllib.parse import urljoin, urlparse
import logging
import time
import shutil
from queue import Queue
import traceback
from typing import List, Dict

def update_progress(queue: Queue, message: str):
    """Send progress update through the queue"""
    try:
        queue.put({
            'message': message
        })
    except Exception as e:
        logging.error(f"Error sending progress update: {str(e)}")

def download_full_video(video_url: str, filename: str, progress_queue: Queue) -> str:
    """Download and convert full video"""
    output_path = os.path.join('uploads', filename)
    
    try:
        # Loading playlist
        update_progress(progress_queue, 'Loading playlist...')
        
        try:
            playlist = m3u8.load(video_url)
        except Exception as e:
            raise Exception(f"Failed to load playlist: {str(e)}")
        
        # Extract base URL
        parsed_url = urlparse(video_url)
        base_path = os.path.dirname(parsed_url.path)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base_path}/"
        
        # Create temporary directory
        temp_dir = f"temp_{os.urandom(4).hex()}"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            segment_files = []
            total_segments = len(playlist.segments)
            
            update_progress(progress_queue, f'Downloading video segments (0/{total_segments})')
            
            # Download all segments
            for i, segment in enumerate(playlist.segments):
                segment_file = os.path.join(temp_dir, f"segment_{i:03d}.ts")
                segment_url = urljoin(base_url, segment.uri)
                
                try:
                    # Download segment
                    response = requests.get(segment_url, verify=False)
                    response.raise_for_status()
                    
                    with open(segment_file, 'wb') as f:
                        f.write(response.content)
                    segment_files.append(segment_file)
                    
                    # Update progress every 5 segments or on last segment
                    if (i + 1) % 5 == 0 or i == total_segments - 1:
                        update_progress(
                            progress_queue,
                            f'Downloading video segments ({i + 1}/{total_segments})'
                        )
                        
                except Exception as e:
                    raise Exception(f"Error downloading segment {i}: {str(e)}")
            
            # Create file list for FFmpeg
            update_progress(progress_queue, 'Converting to MP4...')
            file_list = os.path.join(temp_dir, 'file_list.txt')
            with open(file_list, 'w') as f:
                for segment in segment_files:
                    abs_path = os.path.abspath(segment)
                    f.write(f"file '{abs_path}'\n")
            
            # Convert to MP4
            try:
                ffmpeg_command = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', file_list,
                    '-c', 'copy',
                    '-y',
                    output_path
                ]
                
                result = subprocess.run(
                    ffmpeg_command,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
            except subprocess.CalledProcessError as e:
                raise Exception(f"FFmpeg error: {e.stderr}")
            
            update_progress(progress_queue, 'Finalizing...')
            progress_queue.put('DONE')
            
            return filename
            
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
    except Exception as e:
        error_msg = f"Error processing video: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        progress_queue.put('DONE')
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

def get_video_duration(file_path: str) -> str:
    """Get video duration using FFprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFprobe error: {e.stderr}")
    except Exception as e:
        raise Exception(f"Error getting video duration: {str(e)}")