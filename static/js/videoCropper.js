class VideoCropper {
    constructor() {
        this.cropper = null;
        this.currentCropType = null;
        this.cropData = {
            screen: null,
            webcam: null
        };
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Setup modal events
        const modal = document.getElementById('crop-modal');
        const closeBtn = document.querySelector('.close');
        
        closeBtn.onclick = () => this.closeModal();
        window.onclick = (event) => {
            if (event.target === modal) {
                this.closeModal();
            }
        };

        // Setup crop adjustment buttons
        document.getElementById('adjust-screen-crop').onclick = () => this.startCrop('screen');
        document.getElementById('adjust-webcam-crop').onclick = () => this.startCrop('webcam');
        document.getElementById('save-crop').onclick = () => this.saveCrop();
        document.getElementById('preview-crops').onclick = () => this.previewCrops();

        // Listen for video load
        document.getElementById('video-player').addEventListener('loadedmetadata', () => {
            document.querySelector('.crop-section').style.display = 'block';
        });
    }

    async startCrop(type) {
        this.currentCropType = type;
        const video = document.getElementById('video-player');
        
        // Create a canvas and capture the current video frame
        const canvas = document.getElementById('screenshot-canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Show the modal with the captured frame
        const modal = document.getElementById('crop-modal');
        const cropImage = document.getElementById('crop-image');
        
        cropImage.src = canvas.toDataURL();
        modal.style.display = 'block';

        // Initialize or update cropper
        if (this.cropper) {
            this.cropper.destroy();
        }

        // Get default crop area based on type
        const defaultCrop = this.getDefaultCropArea(type, video.videoWidth, video.videoHeight);

        const options = {
            viewMode: 1,
            dragMode: 'move',
            autoCropArea: 0.8,
            restore: false,
            guides: true,
            center: true,
            highlight: true,
            cropBoxMovable: true,
            cropBoxResizable: true,
            toggleDragModeOnDblclick: false,
            data: this.cropData[type] || defaultCrop
        };

        this.cropper = new Cropper(cropImage, options);
    }

    getDefaultCropArea(type, width, height) {
        if (type === 'screen') {
            // Default screen area (left side)
            return {
                x: 0,
                y: 0,
                width: width * 0.8,
                height: height * 0.8
            };
        } else {
            // Default webcam area (top right corner)
            const webcamWidth = width * 0.2;
            const webcamHeight = height * 0.2;
            return {
                x: width - webcamWidth,
                y: 0,
                width: webcamWidth,
                height: webcamHeight
            };
        }
    }

    saveCrop() {
        if (!this.cropper) return;

        // Get crop data
        const data = this.cropper.getData();
        this.cropData[this.currentCropType] = data;

        // Update preview
        this.updatePreview(this.currentCropType);

        // Close modal
        this.closeModal();
    }

    updatePreview(type) {
        const video = document.getElementById('video-player');
        const previewDiv = document.getElementById(`${type}-crop-preview`);
        const data = this.cropData[type];

        if (!data) return;

        // Create a temporary canvas for the preview
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        // Set canvas size to match crop dimensions
        canvas.width = data.width;
        canvas.height = data.height;
        
        // Draw cropped area
        ctx.drawImage(video, 
            data.x, data.y, data.width, data.height,
            0, 0, canvas.width, canvas.height
        );

        // Update preview div
        previewDiv.style.backgroundImage = `url(${canvas.toDataURL()})`;
    }

    closeModal() {
        const modal = document.getElementById('crop-modal');
        modal.style.display = 'none';
        if (this.cropper) {
            this.cropper.destroy();
            this.cropper = null;
        }
    }

    previewCrops() {
        if (!this.cropData.screen || !this.cropData.webcam) {
            alert('Please configure both screen and webcam crop areas first');
            return;
        }

        // Update both previews
        this.updatePreview('screen');
        this.updatePreview('webcam');
    }

    getCropData() {
        return this.cropData;
    }
}

// Initialize cropper when document is ready
let videoCropper;
document.addEventListener('DOMContentLoaded', () => {
    videoCropper = new VideoCropper();
});