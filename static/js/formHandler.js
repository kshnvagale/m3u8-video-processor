// Helper Functions

function startProgressPolling(process_id, options = {}) {
    const {
        onProgress = () => {},
        onComplete = () => {},
        onError = () => {},
        interval = 1000
    } = options;
    
    const pollProgress = async () => {
        try {
            const response = await fetch(`/check-progress/${process_id}`);
            const data = await response.json();
            
            console.log('Progress update:', data);  // For debugging
            
            if (data.status === 'error') {
                onError(data.message);
                return false;
            }
            
            if (data.status === 'complete') {
                onComplete(data);
                return false;
            }
            
            onProgress(data);
            return true;
            
        } catch (error) {
            console.error('Progress check error:', error);
            onError('Failed to check progress');
            return false;
        }
    };
    
    const poll = async () => {
        const shouldContinue = await pollProgress();
        if (shouldContinue) {
            setTimeout(poll, interval);
        }
    };
    
    poll();
}





function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function timeToSeconds(time) {
    if (!time) return 0;
    const [hours, minutes, seconds] = time.split(':').map(Number);
    return hours * 3600 + minutes * 60 + seconds;
}

function showError(container, message) {
    container.innerHTML = `<div class="error-message">Error: ${message}</div>`;
}

function validateTimeFormat(time) {
    return /^([0-1][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])$/.test(time);
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Video Selection and Duration Handler
    document.getElementById('video-select').addEventListener('change', async (e) => {
        const filename = e.target.value;
        const videoInfo = document.getElementById('video-info');
        const videoPlayer = document.getElementById('video-player');
        const cropSection = document.querySelector('.crop-section');
        
        if (!filename) {
            videoInfo.style.display = 'none';
            videoPlayer.style.display = 'none';
            cropSection.style.display = 'none';
            return;
        }
    
        try {
            const response = await fetch(`/get-duration/${filename}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.message || 'Failed to get video duration');
            }
            
            if (data.success) {
                document.getElementById('video-duration').textContent = data.duration;
                videoInfo.style.display = 'block';
                
                // Update video source and display video player
                const videoSource = document.getElementById('video-source');
                videoSource.src = `/download/${filename}`;
                videoPlayer.load();
                videoPlayer.style.display = 'block';
                
                // Show crop section after video loads
                videoPlayer.onloadedmetadata = () => {
                    cropSection.style.display = 'block';
                };
            } else {
                throw new Error(data.message || 'Failed to get video duration');
            }
        } catch (error) {
            console.error('Error getting video duration:', error);
            alert(`Error getting video duration: ${error.message}`);
            videoInfo.style.display = 'none';
            videoPlayer.style.display = 'none';
            cropSection.style.display = 'none';
        }
    });

    // Time Setting Buttons
    document.getElementById('set-start-time').addEventListener('click', () => {
        const videoPlayer = document.getElementById('video-player');
        const startTimeInput = document.getElementById('start-time');
        startTimeInput.value = formatTime(videoPlayer.currentTime);
    });

    document.getElementById('set-end-time').addEventListener('click', () => {
        const videoPlayer = document.getElementById('video-player');
        const endTimeInput = document.getElementById('end-time');
        endTimeInput.value = formatTime(videoPlayer.currentTime);
    });

    // Download Button Handler
    document.getElementById('download-btn').addEventListener('click', async () => {
        const videoUrl = document.getElementById('video-url').value.trim();
        const filename = document.getElementById('filename').value.trim();
    
        if (!videoUrl || !filename) {
            alert('Please enter both video URL and filename');
            return;
        }
    
        const downloadBtn = document.getElementById('download-btn');
        const progressContainer = document.getElementById('download-progress-container');
        const progressStage = document.getElementById('download-progress-stage');
        const progressFill = document.querySelector('.progress-fill');
        const progressDetails = document.getElementById('download-progress-details');
        const statusDiv = document.getElementById('download-status');
    
        downloadBtn.disabled = true;
        progressContainer.style.display = 'block';
        statusDiv.textContent = '';
    
        try {
            const response = await fetch('/download-video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `video_url=${encodeURIComponent(videoUrl)}&filename=${encodeURIComponent(filename)}`
            });
    
            const data = await response.json();
            
            if (data.success) {
                startProgressPolling(data.process_id, {
                    onProgress: (progress) => {
                        console.log('Progress update:', progress);  // For debugging
                        
                        const progressStage = document.getElementById('download-progress-stage');
                        const progressFill = document.querySelector('.progress-fill');
                        const progressPercent = document.querySelector('.progress-percent');
                        const timeElapsed = document.getElementById('time-elapsed');
                        const timeLeft = document.getElementById('time-left');
                        const downloadSpeed = document.getElementById('download-speed');
                        
                        // Update progress message
                        if (progress.message) {
                            progressStage.textContent = progress.message;
                        }
                        
                        // Update progress bar and percentage
                        if (progress.progress !== undefined) {
                            const percent = Math.min(Math.round(progress.progress), 100);
                            progressFill.style.width = `${percent}%`;
                            progressPercent.textContent = `${percent}%`;
                        }
                        
                        // Update time elapsed
                        if (progress.elapsed) {
                            timeElapsed.textContent = progress.elapsed;
                        }
                        
                        // Update time remaining
                        if (progress.remaining) {
                            timeLeft.textContent = progress.remaining;
                        } else {
                            timeLeft.textContent = 'Calculating...';
                        }
                        
                        // Update download speed
                        if (progress.speed) {
                            downloadSpeed.textContent = progress.speed;
                        } else {
                            downloadSpeed.textContent = 'Calculating...';
                        }
                    },
                    onComplete: () => {
                        progressContainer.style.display = 'none';
                        statusDiv.innerHTML = '<div class="success-message">Download complete!</div>';
                        downloadBtn.disabled = false;
                        window.location.reload();
                    },
                    onError: (error) => {
                        progressContainer.style.display = 'none';
                        statusDiv.innerHTML = `<div class="error-message">Error: ${error}</div>`;
                        downloadBtn.disabled = false;
                    }
                });
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            progressContainer.style.display = 'none';
            statusDiv.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
            downloadBtn.disabled = false;
        }
    });

    // Process Button Handler
    document.getElementById('process-btn').addEventListener('click', async () => {
        const inputFile = document.getElementById('video-select').value;
        const startTime = document.getElementById('start-time').value.trim();
        const endTime = document.getElementById('end-time').value.trim();
        const trimFilename = document.getElementById('trim-filename').value.trim();
        const videoDuration = document.getElementById('video-duration').textContent;

        // Validation checks
        if (!inputFile) {
            alert('Please select a video');
            return;
        }
        if (!startTime || !endTime) {
            alert('Please enter both start and end times');
            return;
        }
        if (!trimFilename) {
            alert('Please enter a filename for the processed video');
            return;
        }

        // Validate time format
        if (!validateTimeFormat(startTime) || !validateTimeFormat(endTime)) {
            alert('Times must be in HH:MM:SS format');
            return;
        }

        // Convert times to seconds for comparison
        const startSeconds = timeToSeconds(startTime);
        const endSeconds = timeToSeconds(endTime);
        const durationSeconds = timeToSeconds(videoDuration);

        // Validate time values
        if (startSeconds >= endSeconds) {
            alert('End time must be greater than start time');
            return;
        }
        if (startSeconds >= durationSeconds) {
            alert('Start time cannot be greater than video duration');
            return;
        }
        if (endSeconds > durationSeconds) {
            alert('End time cannot be greater than video duration');
            return;
        }

        // Get crop data
        const cropData = videoCropper.getCropData();
        if (!cropData.screen || !cropData.webcam) {
            alert('Please configure both screen and webcam crop areas');
            return;
        }

        const processBtn = document.getElementById('process-btn');
        const progressContainer = document.getElementById('process-progress-container');
        const statusDiv = document.getElementById('process-status');
        const downloadContainer = document.getElementById('download-container');

        processBtn.disabled = true;
        progressContainer.style.display = 'block';
        statusDiv.textContent = '';
        downloadContainer.textContent = '';

        try {
            const response = await fetch('/process-video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    input_file: inputFile,
                    start_time: startTime,
                    end_time: endTime,
                    filename: trimFilename,
                    crop_data: cropData
                })
            });

            const data = await response.json();
            
            if (data.success) {
                startProgressPolling(data.process_id, {
                    onProgress: (progress) => {
                        const progressStage = document.getElementById('process-progress-stage');
                        progressStage.textContent = progress.message || 'Processing video...';
                        
                        // Update progress bar if available
                        if (progress.progress !== undefined) {
                            const progressFill = document.querySelector('#process-progress-container .progress-fill');
                            if (progressFill) {
                                progressFill.style.width = `${progress.progress}%`;
                            }
                        }
                    },
                    onComplete: (data) => {
                        // Hide progress container
                        progressContainer.style.display = 'none';
                        
                        // Show download link if available
                        if (data.download_url) {
                            downloadContainer.innerHTML = `
                                <a href="${data.download_url}" class="download-btn">Download Processed Videos</a>
                            `;
                        }
                        
                        // Show success message
                        statusDiv.innerHTML = '<div class="success-message">Video processed successfully!</div>';
                        
                        // Re-enable the process button
                        processBtn.disabled = false;
                    },
                    onError: (error) => {
                        progressContainer.style.display = 'none';
                        statusDiv.innerHTML = `<div class="error-message">Error: ${error}</div>`;
                        processBtn.disabled = false;
                    }
                });
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            progressContainer.style.display = 'none';
            statusDiv.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
            processBtn.disabled = false;
        }
    });

    // Cleanup Modal Functionality
    const cleanupBtn = document.getElementById('cleanup-btn');
    const cleanupModal = document.getElementById('confirm-cleanup-modal');
    const cancelCleanupBtn = document.getElementById('cancel-cleanup');
    const closeCleanupSpan = document.querySelector('#confirm-cleanup-modal .close');

    // Open modal when cleanup button is clicked
    cleanupBtn.addEventListener('click', () => {
        cleanupModal.style.display = 'block';
    });

    // Close modal when X is clicked
    closeCleanupSpan.addEventListener('click', () => {
        cleanupModal.style.display = 'none';
    });

    // Close modal when Cancel is clicked
    cancelCleanupBtn.addEventListener('click', () => {
        cleanupModal.style.display = 'none';
    });

    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        if (event.target === cleanupModal) {
            cleanupModal.style.display = 'none';
        }
    });

    // Handle cleanup confirmation
    const confirmCleanupBtn = document.getElementById('confirm-cleanup');
    const cleanupStatus = document.getElementById('cleanup-status');

    confirmCleanupBtn.addEventListener('click', async () => {
        try {
            // Show loading state
            confirmCleanupBtn.disabled = true;
            confirmCleanupBtn.textContent = 'Cleaning...';
            
            const response = await fetch('/cleanup', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Close modal
                cleanupModal.style.display = 'none';
                
                // Show success message
                cleanupStatus.innerHTML = `<div class="success-message">${data.message}</div>`;
                
                // Reload the page after 2 seconds
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                throw new Error(data.message);
            }
            
        } catch (error) {
            cleanupStatus.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
        } finally {
            // Reset button state
            confirmCleanupBtn.disabled = false;
            confirmCleanupBtn.textContent = 'Delete';
        }
    });
});