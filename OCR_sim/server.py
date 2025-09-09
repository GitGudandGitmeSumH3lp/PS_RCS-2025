# server.py
from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import shutil
from ocr import process_image

app = Flask(__name__)
UPLOAD_FOLDER = 'images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """Process uploaded image and extract RTS code"""
    try:
        # Check if file is present in request
        if 'image' not in request.files:
            return jsonify({
                'success': False, 
                'error': 'No file uploaded'
            })
        
        file = request.files['image']
        
        # Check if file was selected
        if file.filename == '':
            return jsonify({
                'success': False, 
                'error': 'No file selected'
            })
        
        # Check if file has allowed extension
        if file and allowed_file(file.filename):
            # Create uploads directory if it doesn't exist
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            
            # Save the file
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process the image
            result = process_image(filepath)
            
            # Clean up: remove the uploaded file after processing
            if os.path.exists(filepath):
                os.remove(filepath)
            
            return jsonify(result)
        else:
            return jsonify({
                'success': False, 
                'error': 'Invalid file type. Please upload a PNG, JPG, or JPEG file.'
            })
            
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': f'Error processing image: {str(e)}'
        })

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

if __name__ == '__main__':
    # Run on all interfaces with external access
    app.run(host='0.0.0.0', port=5000, debug=True)