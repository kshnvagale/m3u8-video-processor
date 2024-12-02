# m3u8-video-processor (Windows Guide)

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

1. Install Python:
   - Download Python from [python.org](https://www.python.org/downloads/)
   - During installation, make sure to check "Add Python to PATH"
   - Verify installation by opening Command Prompt and typing:
   ```cmd
   python --version
   ```

2. Install FFmpeg:
   - Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html#build-windows)
   - Download the latest release build (choose Windows 64-bit)
   - Extract the downloaded zip file
   - Copy the extracted folder to `C:\Program Files`
   - Rename the folder to `ffmpeg`
   - Add FFmpeg to System PATH:
     - Open System Properties (Win + R, type `sysdm.cpl`)
     - Click "Environment Variables"
     - Under "System Variables", find and select "Path"
     - Click "Edit"
     - Click "New"
     - Add `C:\Program Files\ffmpeg\bin`
     - Click "OK" on all windows
   - Verify installation by opening a new Command Prompt and typing:
   ```cmd
   ffmpeg -version
   ffprobe -version
   ```

## Installation

1. Clone the repository:
   - Install Git from [git-scm.com](https://git-scm.com/download/win) if you haven't
   - Open Command Prompt and run:
   ```cmd
   git clone https://github.com/kshnvagale/m3u8-video-processor.git
   cd m3u8-video-processor
   ```

2. Create and activate a virtual environment:
```cmd
python -m venv venv
venv\Scripts\activate
```

3. Install the required Python packages:
```cmd
pip install -r requirements.txt
```

## Directory Setup

The application requires two directories for operation. They will be created automatically when running the app, but you can create them manually:

```cmd
mkdir uploads
mkdir temp
```

## Running the Application

1. Ensure you're in the project directory and your virtual environment is activated:
```cmd
venv\Scripts\activate
```

2. Start the Flask application:
```cmd
python app.py
```

3. Open your web browser and navigate to:
```
http://localhost:5000
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

1. **'python' is not recognized:**
   - Ensure Python is added to PATH during installation
   - Try using `py` instead of `python`
   - Restart Command Prompt after installation

2. **'ffmpeg' is not recognized:**
   - Double-check FFmpeg PATH configuration
   - Ensure you've restarted Command Prompt after adding to PATH
   - Verify FFmpeg files are in `C:\Program Files\ffmpeg\bin`

3. **Permission errors:**
   - Run Command Prompt as Administrator
   - Check Windows Defender or antivirus settings
   - Ensure full permissions on project directory

4. **pip install fails:**
   - Update pip: `python -m pip install --upgrade pip`
   - Try installing packages individually
   - Check firewall settings

5. **Video processing fails:**
   - Check if input video file is corrupted
   - Verify FFmpeg installation
   - Check available disk space
   - Verify timestamps are valid

6. **M3u8 download fails:**
   - Verify URL is accessible
   - Check if stream is still active
   - Test internet connection
   - Check Windows Firewall settings

## Support

For support, please open an issue in the GitHub repository: https://github.com/kshnvagale/m3u8-video-processor/issues

## Windows-Specific Notes

1. Always use Command Prompt or PowerShell as Administrator when installing packages or running the application for the first time.
2. If using Windows Defender or other antivirus, you may need to add Python and FFmpeg to the exclusions list.
3. For path-related issues, using absolute paths might help (e.g., `C:\path\to\your\video`).
4. If you encounter SSL certificate errors, you may need to install certificates or use `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package_name>`