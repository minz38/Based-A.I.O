import aiohttp
import random
import os
import string
from urllib.parse import urlparse


async def download_attachment_from_url(url: str, save_dir: str) -> str:
    # Generate random 8-character filename (letters + digits)
    random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    # Try to extract file extension from URL
    parsed = urlparse(url)
    basename = os.path.basename(parsed.path)
    _, ext = os.path.splitext(basename)
    filename = random_name + ext

    # Create full save path
    os.makedirs(save_dir, exist_ok=True)
    save_path: str = os.path.join(save_dir, filename)

    # Download the file
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(save_path, 'wb') as f:
                    f.write(await resp.read())
                return save_path
            else:
                raise Exception(f"Failed to download file: HTTP {resp.status}")

