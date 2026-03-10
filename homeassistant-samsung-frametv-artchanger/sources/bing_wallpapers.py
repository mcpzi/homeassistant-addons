import logging
import random
import requests
from io import BytesIO
from typing import Tuple, Optional

# Cache the master list so we only download it once per script run
_BING_ARCHIVE_CACHE = []

def get_image_url(args) -> Optional[str]:
    global _BING_ARCHIVE_CACHE
    
    # 1. Fetch the master list of all successfully archived images
    if not _BING_ARCHIVE_CACHE:
        logging.info('Fetching the master list of available Bing wallpapers...')
        # We use the .min.json endpoint to save bandwidth
        api_url = "https://bing.npanuhin.me/US/en.min.json"
        
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            
            # The API returns a large list of dictionaries containing image metadata
            data = response.json()
            
            if not data:
                raise ValueError("Empty data received from Bing archive.")
                
            # 2. Extract all pre-verified storage URLs
            _BING_ARCHIVE_CACHE = [item['url'] for item in data if 'url' in item]
            logging.info(f"Successfully cached {len(_BING_ARCHIVE_CACHE)} guaranteed valid wallpaper URLs.")
            
        except (requests.RequestException, ValueError, KeyError) as e:
            logging.error(f"Error fetching Bing archive list: {str(e)}")
            return None

    if not _BING_ARCHIVE_CACHE:
        return None
        
    # 3. Pick a random URL from the guaranteed-to-exist list!
    return random.choice(_BING_ARCHIVE_CACHE)

def get_image(args, url) -> Tuple[Optional[BytesIO], Optional[str]]:
    try:
        response: requests.Response = requests.get(url)
        response.raise_for_status()
        image_data: BytesIO = BytesIO(response.content)
        return image_data, "JPEG"
    except requests.RequestException as e:
        logging.error(f"Failed to fetch Bing Wallpaper: {str(e)}")
        return None, None