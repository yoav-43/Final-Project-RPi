import sys
import os
import json
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

# Fix import path for running standalone
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger.logger import SystemLogger

class CloudinaryManager:
    """
    Handles video uploads to Cloudinary storage.
    """

    def __init__(self, cloud_name, api_key, api_secret):
        """
        Configures the Cloudinary API.
        """
        self.logger = SystemLogger("Cloudinary")
        try:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            self.logger.log("INFO", "Cloudinary configured successfully.")
        except Exception as e:
            self.logger.log("ERROR", f"Configuration failed: {e}")

    def upload_video(self, file_path):
        """
        Uploads a video file to the cloud.

        Args:
            file_path (str): Local path to the .mp4 file.

        Returns:
            str: The secure URL of the uploaded video, or None if failed.
        """
        if not os.path.exists(file_path):
            self.logger.log("WARNING", f"File not found: {file_path}")
            return None

        try:
            self.logger.log("INFO", f"Uploading {file_path}...")
            # resource_type="video" is crucial for .mp4 uploads
            response = cloudinary.uploader.upload(file_path, resource_type="video", format="mp4")
            url = response.get("secure_url")
            self.logger.log("INFO", f"Upload successful: {url}")
            return url
        except Exception as e:
            self.logger.log("ERROR", f"Upload failed: {e}")
            return None

# --- TEST MODE ---
if __name__ == "__main__":
    print("--- Starting Cloudinary Upload Test ---")
    
    # 1. Load Environment Variables (Critical step!)
    load_dotenv()

    # 2. Locate Config File
    config_path = os.path.join("monitor", "config.json")
    if not os.path.exists(config_path):
         config_path = os.path.join("..", "monitor", "config.json")

    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)

    # 3. Load Credentials & Overwrite with Env Vars
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        creds = config.get("cloudinary", {})
        
        # FIX: Overwrite the "ENV_VAR" placeholders with real keys from .env
        creds['cloud_name'] = os.getenv('CLOUDINARY_CLOUD_NAME')
        creds['api_key'] = os.getenv('CLOUDINARY_API_KEY')
        creds['api_secret'] = os.getenv('CLOUDINARY_API_SECRET')
            
    except Exception as e:
        print(f"Error reading config file: {e}")
        sys.exit(1)

    if not creds['api_key']:
        print("Error: API Keys not found in .env file.")
        sys.exit(1)

    # Initialize Manager with real credentials
    manager = CloudinaryManager(**creds)

    # 4. Locate Video File
    video_file = "test_output.avi"
    
    if not os.path.exists(video_file):
        print(f"Error: {video_file} not found.")
        print("Run 'python3 monitor/image_processor.py' first to generate it.")
    else:
        print(f"Found video file: {video_file}")
        url = manager.upload_video(video_file)
        
        if url:
            print(f"\nSUCCESS! Browser-ready link:\n{url}\n")
        else:
            print("\nFAILED to upload video.")