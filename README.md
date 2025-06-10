# Bright Horizon Attachment Downloader

Usage:

1. Set environment variables:
   ```
   export BH_USERNAME="your_username"
   export BH_PASSWORD="your_password" 
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the script:
   ```
   python client.py
   ```

The script will:
- Log in to your Bright Horizons account
- Retrieve your children's profiles
- Download all attachments (photos, videos, etc.) from the last 30 days
- Save attachments to a 'downloads' directory, organized by date
- Skip any files that have already been downloaded

Files will be saved as: `downloads/YYYY-MM-DD_filename.[mp4|mov|jpg]`
