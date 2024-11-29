import os
import json
from threading import Lock

class ProgressTracker:
    def __init__(self):
        self._progress = {}
        self._lock = Lock()
        
        # Create progress directory if it doesn't exist
        self.progress_dir = 'progress'
        if not os.path.exists(self.progress_dir):
            os.makedirs(self.progress_dir)
    
    def update_progress(self, process_id: str, data: dict):
        """Update progress for a specific process"""
        progress_file = os.path.join(self.progress_dir, f"{process_id}.json")
        with self._lock:
            with open(progress_file, 'w') as f:
                json.dump(data, f)
    
    def get_progress(self, process_id: str) -> dict:
        """Get progress for a specific process"""
        progress_file = os.path.join(self.progress_dir, f"{process_id}.json")
        try:
            with self._lock:
                with open(progress_file, 'r') as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"status": "unknown"}
    
    def clear_progress(self, process_id: str):
        """Clear progress for a specific process"""
        progress_file = os.path.join(self.progress_dir, f"{process_id}.json")
        try:
            with self._lock:
                os.remove(progress_file)
        except FileNotFoundError:
            pass

# Global instance
progress_tracker = ProgressTracker()