// Helper Functions
function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function timeToSeconds(time) {
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
                throw new Error(data.message);
            }
        } catch (error) {
            alert(`Error getting video duration: ${error.message}`);
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

        if (!videoUrl) {
            alert('Please enter a video URL');
            return;
        }

        if (!filename) {
            alert('Please enter a filename');
            return;
        }

        const downloadBtn = document.getElementById('download-btn');
        const progressContainer = document.getElementById('download-progress-container');
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
                const eventSource = new EventSource(`/progress/${data.process_id}`);
                
                eventSource.onmessage = (event) => {
                    const progressData = JSON.parse(event.data);
                    document.getElementById('download-progress-stage').textContent = progressData.message;
                };

                eventSource.onerror = () => {
                    eventSource.close();
                    // Hide progress container
                    progressContainer.style.display = 'none';
                    statusDiv.innerHTML = `<div class="success-message">Video downloaded and converted successfully!</div>`;
                    // Re-enable button and reload page to update video list
                    downloadBtn.disabled = false;
                    window.location.reload();
                };
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            // Hide progress container on error
            progressContainer.style.display = 'none';
            showError(statusDiv, error.message);
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
                const eventSource = new EventSource(`/progress/${data.process_id}`);
                
                eventSource.onmessage = (event) => {
                    const progressData = JSON.parse(event.data);
                    document.getElementById('process-progress-stage').textContent = progressData.message;
                };

                eventSource.onerror = () => {
                    eventSource.close();
                    // Hide progress container
                    progressContainer.style.display = 'none';
                    // Show download link
                    downloadContainer.innerHTML = `<a href="${data.download_url}" class="download-btn">Download Processed Videos</a>`;
                    // Show success message
                    statusDiv.innerHTML = `<div class="success-message">Video processed successfully!</div>`;
                    // Re-enable the process button
                    processBtn.disabled = false;
                };
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            // Hide progress container on error
            progressContainer.style.display = 'none';
            statusDiv.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
            processBtn.disabled = false;
        }
    });
});