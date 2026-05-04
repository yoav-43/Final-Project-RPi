# cloudinary_server_manager — Cloud Video Storage

Uploads the local drive recording to Cloudinary at the end of each session. Cloudinary transcodes the `.avi` file to MP4 and serves it via CDN, making it embeddable in the web dashboard.

## Files

| File | Description |
|------|-------------|
| `cloudinary_server_manager.py` | `CloudinaryManager` class — configures the Cloudinary SDK and handles video uploads. |

## Class: `CloudinaryManager`

```python
CloudinaryManager(cloud_name, api_key, api_secret)
```

All three credentials are loaded from `.env` at startup by `DriverMonitor` and passed in directly. They are never stored in `config.json` or committed to version control.

### Constructor

Calls `cloudinary.config(...)` to initialize the SDK globally. Logs success or failure via `SystemLogger`.

### `upload_video(file_path) → url | None`

Uploads a local video file to Cloudinary.

```python
cloudinary.uploader.upload(file_path, resource_type="video", format="mp4")
```

Key details:
- `resource_type="video"` is required for video files (the default `"image"` type would fail).
- `format="mp4"` instructs Cloudinary to transcode the `.avi` (MJPG codec) to H.264 MP4, which is universally playable in browsers.
- Returns the `secure_url` (HTTPS CDN link) on success, or `None` on failure.
- Checks that the file exists before attempting the upload.

The returned URL is passed to `HerokuClient.end_drive()` and stored in the `drives` table, where the web dashboard uses it to render the `<video>` player.

## Credentials Setup

Add the following to your `.env` file in the project root:

```
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

Obtain these from your [Cloudinary Console](https://cloudinary.com/console) under **Settings → Access Keys**.

## Standalone Test

```bash
# From project root
python3 cloudinary_server_manager/cloudinary_server_manager.py
```

Loads credentials from `.env`, looks for `test_output.avi` in the current directory, and uploads it. Generate the test file first by running `image_processor/image_processor.py`.

## Dependencies

```
cloudinary
python-dotenv
```
