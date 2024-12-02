# m3u8-video-processor

A Flask-based web application that allows users to download, trim, and crop videos. The application specifically handles m3u8 video streams and can split videos into separate screen share and webcam components.

## Features

- Download videos from m3u8 streams
- Trim videos with precise timestamp control
- Crop videos into separate components (screen share and webcam areas)
- Real-time progress tracking
- User-friendly web interface
- Preview functionality for crop areas

## Prerequisites

Before running the application, ensure you have the following installed on your system:

1. Python 3.8 or higher
2. FFmpeg (for video processing)
3. FFprobe (comes with FFmpeg, used for video information)

### Installing Required Software

1. Install Homebrew (if not already installed):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

2. Install Python using Homebrew:
```bash
brew install python
```

3. Install FFmpeg using Homebrew:
```bash
brew install ffmpeg
```

4. Verify installations:
```bash
python3 --version
ffmpeg -version
ffprobe -version
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/kshnvagale/m3u8-video-processor.git
cd m3u8-video-processor
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install the required Python packages:
```bash
pip install -r requirements.txt
```

## Directory Setup

The application requires two directories for operation. They will be created automatically when running the app, but you can create them manually:

```bash
mkdir uploads
mkdir temp
```

## Running the Application

1. Ensure you're in the project directory and your virtual environment is activated:
```bash
source venv/bin/activate
```

2. Start the Flask application:
```bash
python3 app.py
```

3. Open your web browser and navigate to:
```
http://localhost:5000 or http://127.0.0.1:5000
```

## Using the Application

### Part 1: Downloading a Video

1. Enter the m3u8 URL of the video you want to process
2. Provide a filename for the downloaded video (must end with .mp4)
3. Click "Download & Convert"
4. Wait for the download and conversion process to complete

### Part 2: Processing the Video

1. Select the downloaded video from the dropdown menu
2. Set the start and end times for trimming:
   - Either manually enter timestamps in HH:MM:SS format
   - Or use the video player and "Set Current Time" buttons
3. Configure crop areas:
   - Click "Adjust Screen Area" to set the main screen recording area
   - Click "Adjust Webcam Area" to set the webcam recording area
   - Use the crop interface to adjust the areas as needed
   - Click "Save Crop" when satisfied with each area
4. Enter a filename for the processed video
5. Click "Process Video"
6. Once processing is complete, click "Download Processed Videos" to get the ZIP file containing both cropped videos

## File Structure

```
m3u8-video-processor/
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── videoCropper.js
│       └── formHandler.js
├── templates/
│   └── index.html
├── uploads/
├── temp/
├── app.py
├── video_processor.py
└── requirements.txt
```

## Troubleshooting

### Common Issues:

1. **FFmpeg not found error:**
   - Run `brew reinstall ffmpeg`
   - Verify by running `ffmpeg -version`

2. **Permission errors:**
   - Run `chmod 755 uploads temp`
   - Ensure your user has write permissions to these directories

3. **Video processing fails:**
   - Check if the input video file is corrupted
   - Run `brew doctor` to verify Homebrew installations
   - Check system resources (Activity Monitor)
   - Verify timestamps are valid

4. **M3u8 download fails:**
   - Verify the URL is accessible
   - Check if the stream is still active
   - Test your internet connection

## Support

For support, please open an issue in the GitHub repository: https://github.com/kshnvagale/m3u8-video-processor/issues