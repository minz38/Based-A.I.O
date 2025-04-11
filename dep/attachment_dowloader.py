import random
import string
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

from dep.logger import LoggerManager

logger = LoggerManager(name="Attachment downloader", level="INFO", log_name="bot").get_logger()


async def download_attachment_from_url(url: str, save_dir: Path) -> Path:
    # Generate random 8-character filename (letters + digits)
    random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    # Extract extension from URL
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix
    filename = f"{random_name}{ext}"

    # Create directory if it doesn't exist
    save_dir.mkdir(parents=True, exist_ok=True)

    # Construct full save path
    save_path: Path = save_dir / filename

    # Download the file
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(save_path, 'wb') as f:
                    f.write(await resp.read())
                logger.info(f"Downloaded file to {save_path}")
                return save_path
            else:
                logger.error(f"Error downloading file to path: {save_path}")
                raise Exception(f"Failed to download file: HTTP {resp.status}")
