import sys
import os
import json
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

# Allow standalone execution from any working directory.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger.logger import SystemLogger

class CloudinaryManager:
    """
    Handles post-session video uploads to Cloudinary.
    Configures the Cloudinary SDK with the provided credentials and
    exposes a single upload method that returns the CDN URL of the
    transcoded video.
    """

    def __init__(self, cloud_name, api_key, api_secret):
        """
        Initialises the Cloudinary SDK with the account credentials.

        Args:
            cloud_name (str): Cloudinary cloud name.
            api_key (str): Cloudinary API key.
            api_secret (str): Cloudinary API secret.
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
        Uploads a local video file to Cloudinary and returns its CDN URL.

        The file is uploaded with resource_type="video" and transcoded to
        MP4 (H.264), making it universally playable in web browsers.
        The resulting URL is stored in the database and used by the
        web dashboard to embed the session recording.

        Args:
            file_path (str): Absolute or relative path to the .avi file.

        Returns:
            str | None: The HTTPS CDN URL of the uploaded video,
                        or None if the upload failed.
        """
        if not os.path.exists(file_path):
            self.logger.log("WARNING", f"File not found: {file_path}")
            return None

        try:
            self.logger.log("INFO", f"Uploading {file_path}...")
            response = cloudinary.uploader.upload(file_path, resource_type="video", format="mp4")
            url = response.get("secure_url")
            self.logger.log("INFO", f"Upload successful: {url}")
            return url
        except Exception as e:
            self.logger.log("ERROR", f"Upload failed: {e}")
            return None

# --- Standalone Test ---
if __name__ == "__main__":
    print("--- Starting Cloudinary Upload Test ---")
    
    # Load credentials from the project root .env file.
    load_dotenv()

    config_path = os.path.join("monitor", "config.json")
    if not os.path.exists(config_path):
         config_path = os.path.join("..", "monitor", "config.json")

    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        creds = config.get("cloudinary", {})
        
        # Overwrite the "ENV_VAR" placeholders with real credentials from .env.
        creds['cloud_name'] = os.getenv('CLOUDINARY_CLOUD_NAME')
        creds['api_key'] = os.getenv('CLOUDINARY_API_KEY')
        creds['api_secret'] = os.getenv('CLOUDINARY_API_SECRET')
            
    except Exception as e:
        print(f"Error reading config file: {e}")
        sys.exit(1)

    if not creds['api_key']:
        print("Error: API Keys not found in .env file.")
        sys.exit(1)

    manager = CloudinaryManager(**creds)

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
