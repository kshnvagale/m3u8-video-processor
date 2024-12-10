class VideoCropper {
    constructor() {
        this.cropper = null;
        this.currentCropType = null;
        this.cropData = {
            screen: null,
            webcam: null
        };
        this.maintainAspectRatio = true;  // Add this line
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
            data: this.cropData[type] || defaultCrop,
            crop: (event) => {
                // Update input fields when crop box changes
                const data = event.detail;
                document.getElementById('crop-x').value = Math.round(data.x);
                document.getElementById('crop-y').value = Math.round(data.y);
                document.getElementById('crop-width').value = Math.round(data.width);
                document.getElementById('crop-height').value = Math.round(data.height);
            }
        };

        this.cropper = new Cropper(cropImage, options);
        // Get references to all input fields
        const xInput = document.getElementById('crop-x');
        const yInput = document.getElementById('crop-y');
        const widthInput = document.getElementById('crop-width');
        const heightInput = document.getElementById('crop-height');

        // Get aspect ratio checkbox and add listener
            const aspectRatioCheckbox = document.getElementById('maintain-aspect-ratio');
            aspectRatioCheckbox.checked = this.maintainAspectRatio;

            aspectRatioCheckbox.addEventListener('change', (e) => {
            this.maintainAspectRatio = e.target.checked;
             if (this.cropper) {
            this.cropper.setAspectRatio(e.target.checked ? this.cropper.getData().width / this.cropper.getData().height : NaN);
         }
});



// Function to update cropper when inputs change
const updateFromInput = (e) => {
    if (!this.cropper) return;
    
    const data = this.cropper.getData();
    const newValue = parseInt(e.target.value) || 0;
    
    // Update the specific dimension that changed
    switch(e.target.id) {
        case 'crop-x':
            data.x = newValue;
            break;
        case 'crop-y':
            data.y = newValue;
            break;
        case 'crop-width':
            data.width = newValue;
            break;
        case 'crop-height':
            data.height = newValue;
            break;
    }
    
    // Apply the new data to the cropper
    this.cropper.setData(data);
};
    // Add event listeners to input fields
    xInput.addEventListener('input', updateFromInput);
    yInput.addEventListener('input', updateFromInput);
    widthInput.addEventListener('input', updateFromInput);
    heightInput.addEventListener('input', updateFromInput);


        // Update input fields with initial crop data
        const cropData = this.cropper.getData();
        xInput.value = Math.round(cropData.x);
        yInput.value = Math.round(cropData.y);
        widthInput.value = Math.round(cropData.width);
        heightInput.value = Math.round(cropData.height);
    }

    getDefaultCropArea(type, width, height) {
        if (type === 'screen') {
            // Default screen area (left side)
            return {
                x: 0,
                y: 0,
                width: width * 0.8,
                height: height
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