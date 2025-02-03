import requests
import os
import subprocess
import logging
import time
import shutil
import re
import json
import m3u8
import psutil
from typing import List, Dict, Tuple
from progress_tracker import progress_tracker
from flask import current_app
from pathlib import Path
import threading
import concurrent.futures
from urllib.parse import urljoin

# Configure custom logger
class EmojiFormatter(logging.Formatter):
    """Custom formatter that adds emojis to log messages"""
    FORMATS = {
        logging.ERROR: "❌ %(message)s",
        logging.WARNING: "⚠️ %(message)s",
        logging.INFO: "ℹ️ %(message)s",
        logging.DEBUG: "🔍 %(message)s"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logger():
    """Setup custom logger with emoji formatting"""
    logger = logging.getLogger('VideoProcessor')
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Prevent propagation to root logger (prevents duplicate logs)
    logger.propagate = False
    
    # Console handler with emoji formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(EmojiFormatter())
    logger.addHandler(console_handler)
    
    # Suppress Werkzeug logging except for errors
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)
    
    return logger

logger = setup_logger()

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

def get_m3u8_info(url: str) -> Tuple[int, List[Tuple[str, float]], float]:
    """Get total segments, their URLs, and actual durations from M3U8 playlist"""
    try:
        playlist = m3u8.load(url)
        total_duration = 0
        segments = []

        if playlist.is_endlist:
            for seg in playlist.segments:
                segments.append((seg.uri, seg.duration))
                total_duration += seg.duration

        return len(segments), segments, total_duration
    except Exception as e:
        logger.error(f"Error parsing M3U8: {e}")
        return 0, [], 0

def download_segment(segment_info: Tuple[str, str, str]) -> bool:
    """Download a single M3U8 segment without modifying its filename."""
    url, original_filename, output_dir = segment_info
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        
        output_path = os.path.join(output_dir, original_filename)

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return True
    except Exception as e:
        logger.debug(f"⚠️ Failed to download segment {original_filename}: {e}")
        return False

def convert_m3u8_to_mp4(m3u8_path: str, output_path: str):
    """Convert M3U8 playlist to MP4 using FFmpeg"""
    try:
        cmd = [
            'ffmpeg',
            '-protocol_whitelist', 'file,http,https,tcp,tls',
            '-i', m3u8_path,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-movflags', '+faststart',
            '-y', output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"✅ MP4 conversion successful: {output_path}")
    except Exception as e:
        logger.error(f"❌ MP4 conversion failed: {e}")
        raise

def get_optimal_workers():
    """Calculate optimal number of worker threads based on system resources"""
    try:
        # Get CPU count and memory info
        cpu_count = psutil.cpu_count()
        memory = psutil.virtual_memory()
        
        # Base number of workers on CPU cores
        optimal_workers = cpu_count * 4
        
        # Adjust based on available memory (reduce if less than 4GB free)
        if memory.available < 4 * 1024 * 1024 * 1024:  # 4GB in bytes
            optimal_workers = max(8, optimal_workers // 2)
        
        # Cap at reasonable maximum
        return min(32, optimal_workers)
    except:
        # Default to 16 workers if can't determine system resources
        return 16

def get_system_load():
    """Get current system load metrics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        return cpu_percent, memory.percent
    except:
        return 0, 0

def adjust_workers(current_workers: int, cpu_percent: float, memory_percent: float) -> int:
    """Dynamically adjust number of workers based on system load"""
    # Reduce workers if system is under heavy load
    if cpu_percent > 80 or memory_percent > 80:
        return max(4, current_workers - 4)
    # Increase workers if system load is low
    elif cpu_percent < 50 and memory_percent < 60:
        return min(32, current_workers + 2)
    return current_workers

def generate_download_report(total_segments: int, elapsed_time: float, final_speed: float, output_path: str) -> str:
    """Generate a formatted download report with emojis"""
    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    file_size_mb = file_size / (1024 * 1024)
    avg_speed_mb = final_speed / (1024 * 1024)
    
    report = [
        "\n" + "="*50,
        "📥 Download Complete! 🎉",
        "="*50,
        f"\n📊 Download Statistics:",
        f"   ├─ 🎬 Total Segments: {total_segments}",
        f"   ├─ ⏱️ Time Taken: {format_time(int(elapsed_time))}",
        f"   ├─ 📦 File Size: {file_size_mb:.2f} MB",
        f"   ├─ ⚡ Average Speed: {format_speed(final_speed)}",
        f"   └─ 🎯 Efficiency: {avg_speed_mb:.1f} MB/s ({total_segments/elapsed_time:.1f} segments/s)",
        "="*50 + "\n"
    ]
    return "\n".join(report)

def download_full_video(video_url: str, filename: str, process_id: str) -> str:
    """Download video directly using parallel segment downloading"""
    output_path = os.path.join(get_downloads_path(), 'uploads', filename)
    start_time = time.time()
    
    # Create temporary directory for segments
    temp_dir = os.path.join(get_downloads_path(), 'temp', process_id)
    os.makedirs(temp_dir, exist_ok=True)

    # Define the local path for storing the M3U8 file
    m3u8_filename = "playlist.m3u8"  # Set a standard filename
    local_m3u8_path = os.path.join(temp_dir, m3u8_filename)

    try:
        # Download the M3U8 file from the given URL
        logger.info("\n🔍 Downloading M3U8 playlist...")
        response = requests.get(video_url, stream=True, timeout=10)
        response.raise_for_status()  # Ensure the request was successful

        # Save the downloaded M3U8 file locally
        with open(local_m3u8_path, 'wb') as f:
            f.write(response.content)

        # Parse the M3U8 file to extract segment details
        total_segments, segment_data, total_duration = get_m3u8_info(local_m3u8_path)
        if total_segments == 0 or not segment_data:
            raise Exception("No segments found in playlist")
        
        logger.info(f"\n📋 Playlist Analysis:")
        logger.info(f"   ├─ Total Segments: {total_segments}")
        logger.info(f"   └─ Duration: {format_time(int(total_duration))}\n")
        
        # Prepare segment download tasks
        base_url = video_url.rsplit('/', 1)[0] + '/'
        download_tasks = [
            (urljoin(base_url, seg_url), seg_url, temp_dir)  # Keep original TS filename
            for seg_url, _ in segment_data
        ]
        
        # Initialize progress tracking
        downloaded_segments = 0
        last_update_time = time.time()
        last_adjustment_time = time.time()
        update_interval = 0.5
        adjustment_interval = 2.0  # Check system load every 2 seconds
        
        # Start with optimal workers
        num_workers = get_optimal_workers()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=num_workers)
        active_futures = set()
        pending_tasks = list(download_tasks)
        
        try:
            while pending_tasks or active_futures:
                # Submit new tasks if we have capacity
                while pending_tasks and len(active_futures) < num_workers:
                    task = pending_tasks.pop(0)
                    future = executor.submit(download_segment, task)
                    active_futures.add(future)
                
                # Check completed futures
                done_futures = set()
                for future in list(active_futures):
                    if future.done():
                        downloaded_segments += 1 if future.result() else 0
                        done_futures.add(future)
                active_futures -= done_futures
                
                current_time = time.time()
                
                # Adjust workers based on system load
                if current_time - last_adjustment_time >= adjustment_interval:
                    cpu_percent, memory_percent = get_system_load()
                    new_workers = adjust_workers(num_workers, cpu_percent, memory_percent)
                    
                    if new_workers != num_workers:
                        num_workers = new_workers
                        # Create new executor with adjusted worker count
                        old_executor = executor
                        executor = concurrent.futures.ThreadPoolExecutor(max_workers=num_workers)
                        # Let old executor finish existing tasks
                        old_executor.shutdown(wait=False)
                    
                    last_adjustment_time = current_time
                
                # Update progress with emojis
                if current_time - last_update_time >= update_interval:
                    progress = (downloaded_segments / total_segments) * 100
                    elapsed_time = current_time - start_time
                    
                    # Calculate speed
                    if elapsed_time > 0:
                        bytes_downloaded = sum(
                            os.path.getsize(os.path.join(temp_dir, f))
                            for f in os.listdir(temp_dir)
                            if f.endswith('.ts')
                        )
                        speed = bytes_downloaded / elapsed_time
                        
                        # Estimate remaining time
                        if downloaded_segments > 0:
                            remaining_time = (elapsed_time / downloaded_segments) * (total_segments - downloaded_segments)
                        else:
                            remaining_time = 0
                        
                        # Get current system load
                        cpu_percent, memory_percent = get_system_load()
                        
                        # Status emoji based on progress
                        status_emoji = "🚀" if speed > 1024*1024 else "⏳"
                        
                        progress_data = {
                            "status": "downloading",
                            "progress": progress,
                            "elapsed": format_time(int(elapsed_time)),
                            "remaining": format_time(int(remaining_time)),
                            "speed": format_speed(speed),
                            "message": f"{status_emoji} Segments: {downloaded_segments}/{total_segments} | 👥 Workers: {num_workers} | 💻 CPU: {cpu_percent:.1f}% | 🧠 RAM: {memory_percent:.1f}%"
                        }
                        
                        progress_tracker.update_progress(process_id, progress_data)
                        last_update_time = current_time
                        last_speed = speed  # Store last speed for final report
        
        finally:
            executor.shutdown(wait=True)
        
        # Verify all segments were downloaded
        if downloaded_segments < total_segments:
            raise Exception(f"❌ Download incomplete: {downloaded_segments}/{total_segments} segments")
        
        # Update progress for merging phase
        progress_tracker.update_progress(process_id, {
            "status": "processing",
            "progress": 95,
            "message": "🔄 Merging segments..."
        })
        
        # Convert M3U8 to MP4
        convert_m3u8_to_mp4(local_m3u8_path, output_path)

        # Generate and display download report
        total_time = time.time() - start_time
        report = generate_download_report(total_segments, total_time, last_speed, output_path)
        
        # Log report to console
        logger.info("\n" + report)
        
        # Update final progress with report
        progress_tracker.update_progress(process_id, {
            "status": "complete",
            "progress": 100,
            "message": report
        })
        
        return filename
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Download failed: {error_msg}")
        
        # Update error progress
        progress_tracker.update_progress(process_id, {
            "status": "error",
            "message": f"❌ Error: {error_msg}"
        })
        
        # Clean up output file if it exists
        if os.path.exists(output_path):
            os.remove(output_path)
            
        raise Exception(error_msg)
        
    finally:
        # Clean up temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def get_video_bitrate(file_path: str) -> float:
    """Get video bitrate in Kbps using FFprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        bitrate = float(result.stdout.strip()) / 1000  # Convert to Kbps
        return bitrate
    except:
        return 0

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
        
        logger.info("\n" + "="*50)
        logger.info("🎬 Starting Video Processing")
        logger.info("="*50)
        
        # Get video info
        video_info = get_video_info(input_path)
        if not video_info:
            raise Exception("Could not get video information")
            
        logger.info(f"\n📊 Video Information:")
        logger.info(f"   ├─ 🕒 Time Range: {start_time} to {end_time}")
        logger.info(f"   ├─ 🎥 Codec: {video_info['codec']}")
        logger.info(f"   ├─ ⚡ FPS: {video_info['fps']}")
        logger.info(f"   └─ 📊 Bitrate: {video_info['bitrate']} Kbps\n")
        
        # Process screen share area
        screen_crop = crop_data['screen']
        logger.info("🖥️ Processing Screen Recording...")
        logger.info("\n")
        
        # Build filter string with quality checks
        screen_filters = [
            f'crop={int(screen_crop["width"])}:{int(screen_crop["height"])}:{int(screen_crop["x"])}:{int(screen_crop["y"])}'
        ]

        # Add FPS filter if needed
        if video_info['fps'] > 30:
            screen_filters.append('fps=30')
            
        # Add bitrate control if needed
        bitrate_args = []
        if video_info['bitrate'] > 250:
            bitrate_args = ['-b:v', '250k']
        
        screen_command = [
            'ffmpeg',
            '-hide_banner',         # Hide FFmpeg compilation details
            '-loglevel', 'error',   # Only show errors
            '-i', input_path,
            '-ss', start_time,
            '-to', end_time,
            '-filter:v', ','.join(screen_filters),
            *bitrate_args,
            '-c:v', 'libx264',
            '-an',  # No audio for screen share
            '-y',
            screen_output
        ]
        
        try:
            subprocess.run(screen_command, capture_output=True, text=True, check=True)
            output_files.append(screen_output)
            
            # Check screen recording bitrate
            screen_bitrate = get_video_bitrate(screen_output)
            logger.info(f"✅ Screen recording processed successfully - Bitrate: {screen_bitrate:.1f} Kbps")
            if screen_bitrate > 250:
                logger.warning(f"⚠️ Screen recording bitrate ({screen_bitrate:.1f} Kbps) is higher than recommended (250 Kbps)")
                logger.warning("⚠️ Please check with tech team to fix this")
            
            progress_tracker.update_progress(process_id, {
                "status": "processing",
                "message": "🎥 Processing webcam video...",
                "progress": 50
            })
        except subprocess.CalledProcessError as e:
            raise Exception(f"❌ Screen processing failed: {e.stderr}")
        
        # Process webcam area
        logger.info("\n📸 Processing Webcam Recording...")
        webcam_crop = crop_data['webcam']
        logger.info("\n")
        
        # Build filter string with quality checks for webcam
        webcam_filters = [
            f'crop={int(webcam_crop["width"])}:{int(webcam_crop["height"])}:{int(webcam_crop["x"])}:{int(webcam_crop["y"])}'
        ]
        
        # Add FPS filter if needed
        if video_info['fps'] > 30:
            webcam_filters.append('fps=30')

        if video_info['bitrate'] > 100:
            bitrate_args = ['-b:v', '100k']

        webcam_command = [
            'ffmpeg',
            '-hide_banner',         # Hide FFmpeg compilation details
            '-loglevel', 'error',   # Only show errors
            '-i', input_path,
            '-ss', start_time,
            '-to', end_time,
            '-filter:v', ','.join(webcam_filters),
            *bitrate_args,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-y',
            webcam_output
        ]
        
        try:
            subprocess.run(webcam_command, capture_output=True, text=True, check=True)
            output_files.append(webcam_output)
            
            # Check webcam recording bitrate
            webcam_bitrate = get_video_bitrate(webcam_output)
            logger.info(f"✅ Webcam video processed successfully - Bitrate: {webcam_bitrate:.1f} Kbps")
            if webcam_bitrate > 100:
                logger.warning(f"⚠️ Webcam recording bitrate ({webcam_bitrate:.1f} Kbps) is higher than recommended (100 Kbps)")
                logger.warning("⚠️ Please check with tech team to fix this")
            
            # Final success message with bitrate info
            logger.info("\n" + "="*50)
            logger.info("\n")
            logger.info("✨ Video Processing Complete!")
            logger.info(f"   ├─ 🖥️ Screen: {os.path.basename(screen_output)} ({screen_bitrate:.1f} Kbps)")
            logger.info(f"   └─ 📸 Webcam: {os.path.basename(webcam_output)} ({webcam_bitrate:.1f} Kbps)")
            logger.info("\n")
            logger.info("="*50 + "\n")
            
            progress_tracker.update_progress(process_id, {
                "status": "complete",
                "message": "✅ Processing complete",
                "progress": 100
            })
        except subprocess.CalledProcessError as e:
            raise Exception(f"❌ Webcam processing failed: {e.stderr}")
        
        return output_files
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Processing failed: {error_msg}")
        
        # Update error progress
        progress_tracker.update_progress(process_id, {
            "status": "error",
            "message": f"❌ Error: {error_msg}"
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

def get_video_info(file_path: str) -> dict:
    """Get video metadata using FFprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,r_frame_rate,bit_rate',
            '-of', 'json',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
        # Parse frame rate
        fps_fraction = video_info['streams'][0]['r_frame_rate'].split('/')
        fps = float(fps_fraction[0]) / float(fps_fraction[1])
        
        # Convert bitrate from bits/s to Kbps
        bitrate = int(video_info['streams'][0]['bit_rate']) / 1000
        
        info = {
            'codec': video_info['streams'][0]['codec_name'],
            'fps': fps,
            'bitrate': bitrate
        }

        # Log processed info
        print("Video Info:", json.dumps(info, indent=2))

        return info

    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None