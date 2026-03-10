import logging
import random
import requests
import subprocess
import os
import re
from io import BytesIO
from typing import Optional, Tuple

# Cache to store asset IDs so we only hit the Wikidata API once per script run
_GAC_ASSETS_CACHE = []

def get_image_url(args) -> Optional[str]:
    global _GAC_ASSETS_CACHE
    
    # 1. Fetch a massive list of artworks if we haven't already
    if not _GAC_ASSETS_CACHE:
        logging.info('Fetching a wide variety of artworks from Wikidata...')
        
        # Wikidata SPARQL query for Google Arts & Culture asset IDs (P4701)
        url = "https://query.wikidata.org/sparql"
        query = """
        SELECT ?asset_id WHERE {
          ?item wdt:P4701 ?asset_id.
        }
        LIMIT 10000
        """
        headers = {
            "User-Agent": "RandomGACDownloader/1.0",
            "Accept": "application/sparql-results+json"
        }
        
        try:
            response = requests.get(url, params={'query': query}, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            bindings = data.get('results', {}).get('bindings', [])
            if not bindings:
                raise ValueError("Empty image list received from Wikidata")

            _GAC_ASSETS_CACHE = [item['asset_id']['value'] for item in bindings]
            logging.info(f"Successfully cached {len(_GAC_ASSETS_CACHE)} unique asset IDs.")
            
        except (requests.RequestException, ValueError, KeyError) as e:
            logging.error(f"Error getting image list from Wikidata: {str(e)}")
            return None

    # 2. Pick a random asset ID from the 10,000 available
    selected_id = random.choice(_GAC_ASSETS_CACHE)
    
    # 3. Construct the valid Google Arts & Culture webpage URL.
    # 'wd' acts as a placeholder slug, which GAC accepts as long as the ID is valid.
    return f"https://artsandculture.google.com/asset/wd/{selected_id}"

def get_image(args, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    download_high_res = args.download_high_res

    if download_high_res:
        logging.info(f'Downloading high-res image from {image_url}')
        output_file: str = "temp.jpg"

        try:
            subprocess.run(["dezoomify-rs", "--max-width", "5001", "--compression", "0", image_url, output_file], check=True)
            with open(output_file, 'rb') as f:
                image_data: BytesIO = BytesIO(f.read())
            os.remove(output_file)  # Clean up the temporary file
            return image_data, 'JPEG'
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to download high-res image: {str(e)}")
            return None, None
        except OSError as e:
            logging.error(f"Failed to remove temporary file: {str(e)}")
            # Continue execution even if file removal fails
            return image_data, 'JPEG' # Make sure to return the data even if cleanup fails
            
    else:
        try:
            logging.info(f'Fetching webpage to extract direct image URL from {image_url}')
            
            # 1. Fetch the actual HTML of the Google Arts & Culture page
            page_response = requests.get(image_url)
            page_response.raise_for_status()
            
            # 2. Use regex to find the OpenGraph image meta tag
            # It usually looks like <meta property="og:image" content="https://lh3.googleusercontent.com/...">
            match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', page_response.text)
            
            if not match:
                logging.error("Could not find the direct image URL within the webpage HTML.")
                return None, None
                
            direct_image_url = match.group(1)
            
            # 3. Strip any existing size parameters (everything after the '=') and add yours
            base_url = direct_image_url.split('=')[0]
            final_image_url = f"{base_url}=w3840-h2160-c"
            
            logging.info(f'Downloading direct image from {final_image_url}')
            
            # 4. Download the actual image file
            image_response = requests.get(final_image_url)
            image_response.raise_for_status()
            image_data = BytesIO(image_response.content)
        
            return image_data, 'JPEG'
            
        except (requests.RequestException, ValueError, KeyError) as e:
            logging.error(f"Error getting image: {str(e)}")
            return None, None