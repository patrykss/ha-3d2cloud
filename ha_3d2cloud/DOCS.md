# HA 3d2cloud Documentation

## Configuration
Configure your YouTube API credentials and title template in the Add-on Configuration tab.

## Printer Setup (Moonraker Post-Processing)
Add this script to your printer to send recordings directly to HA 3d2cloud and free up printer storage immediately:
```bash
#!/bin/bash
VIDEO_PATH="$1"
FILENAME=$(basename "$VIDEO_PATH")

curl -X POST "http://HOME_ASSISTANT_IP:8080/api/upload" \
  -F "file=@$VIDEO_PATH" \
  -F "filename=$FILENAME"

if [ $? -eq 0 ]; then
    rm -f "$VIDEO_PATH"
    echo "Sent to HA 3d2cloud and cleared local storage."
fi
```
