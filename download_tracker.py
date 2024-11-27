import time
from dataclasses import dataclass
from typing import Dict, List
import statistics

@dataclass
class SegmentInfo:
    size: int
    download_time: float
    timestamp: float

class DownloadTracker:
    def __init__(self, total_segments: int):
        self.total_segments: int = total_segments
        self.downloaded_segments: int = 0
        self.total_bytes: int = 0
        self.segment_history: List[SegmentInfo] = []
        self.start_time: float = time.time()
        
    def update(self, segment_size: int, segment_download_time: float) -> Dict:
        """
        Update tracker with information about the latest downloaded segment
        Returns a dictionary with current download statistics
        """
        current_time = time.time()
        
        # Update counters
        self.downloaded_segments += 1
        self.total_bytes += segment_size
        
        # Record segment info
        self.segment_history.append(SegmentInfo(
            size=segment_size,
            download_time=segment_download_time,
            timestamp=current_time
        ))
        
        # Calculate progress percentage
        progress = (self.downloaded_segments / self.total_segments) * 100
        
        # Calculate download speed (last 5 segments or all if less than 5)
        recent_segments = self.segment_history[-5:] if len(self.segment_history) > 5 else self.segment_history
        if recent_segments:
            recent_speeds = [
                s.size / s.download_time for s in recent_segments if s.download_time > 0
            ]
            current_speed = statistics.mean(recent_speeds) if recent_speeds else 0
        else:
            current_speed = 0
        
        # Estimate time remaining
        if current_speed > 0:
            segments_remaining = self.total_segments - self.downloaded_segments
            average_segment_size = self.total_bytes / self.downloaded_segments
            estimated_remaining_bytes = segments_remaining * average_segment_size
            estimated_time_remaining = estimated_remaining_bytes / current_speed
        else:
            estimated_time_remaining = 0
        
        return {
            'progress': progress,
            'downloaded_segments': self.downloaded_segments,
            'total_segments': self.total_segments,
            'downloaded_bytes': self.total_bytes,
            'current_speed': current_speed,  # bytes per second
            'estimated_time_remaining': estimated_time_remaining,  # seconds
            'elapsed_time': current_time - self.start_time  # seconds
        }
    
    def format_size(size_bytes: int) -> str:
        """Convert bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"
    
    def format_speed(speed_bytes: float) -> str:
        """Convert bytes/sec to human readable format"""
        return f"{DownloadTracker.format_size(speed_bytes)}/s"
    
    def format_time(seconds: float) -> str:
        """Convert seconds to human readable format"""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"