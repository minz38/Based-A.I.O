import os
import yt_dlp
import shutil
from logger import LoggerManager
import re

logger = LoggerManager(name="Music Downloader", level="info", log_file="logs/youtube_downloader.log").get_logger()


# path_to_ffmpeg = "/code/ff/ffmpeg"

async def download_music(video_url: str) -> str | bool:
    """
    Downloads music from a given YouTube video URL.

    Parameters:
    video_url (str): The URL of the YouTube video from which to download music.

    Returns:
    str | bool: The path to the downloaded music file if successful, or False if an error occurred.

    The function uses the yt_dlp library to download the audio from the specified YouTube video URL.
    The downloaded audio is then converted to MP3 format using the FFmpeg library.
    The function logs the progress and any errors encountered during the download process.
    """
    logger.info(f"Downloading music from {video_url}")
    music_output_path: str = 'temp/youtube/music'

    os.makedirs(music_output_path, exist_ok=True)

    # Format: Mp3, Quality: best, convert to mp3 using ffmpeg
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{music_output_path}/song.%(ext)s',  # %(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    }

    try:
        # download the audio using yt_dlp, return the filepath once its downloaded
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict: dict[str] = ydl.extract_info(video_url, download=True)
            file_title = info_dict.get('title', 'unknown_title')
            file_path: str = f"{music_output_path}/song.mp3"
            logger.info(f"Downloaded music to {file_path}")
            return file_path

    except Exception as e:
        logger.error(f"Error downloading music: {e}")
        return False


async def download_video(video_url: str) -> str | bool:
    logger.info(f"Downloading video from {video_url}")
    video_output_path: str = 'temp/youtube/video'

    os.makedirs(video_output_path, exist_ok=True)

    # Format: mp4, convert to mp4 using ffmpeg
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': f'{video_output_path}/video.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        # 'ffmpeg_location': path_to_ffmpeg,
    }

    try:
        # download the video using yt_dlp, return the filepath once its downloaded
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict: dict[str] = ydl.extract_info(video_url, download=True)
            # file_title = info_dict.get('title', 'unknown_title')
            file_path: str = f"{video_output_path}/video.mp4"
            logger.info(f"Downloaded video to {file_path}")
            filesize: int = os.path.getsize(file_path)
            if filesize <= 1024 * 1024 * 100:
                return file_path
            else:
                logger.warning(f"Video file {file_path} is too large, it's {filesize / (1024 * 1024)} "
                               f"MB. Skipping download.")
                return False

    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return False


def sanitize_filename(filename: str) -> str:
    # Replace invalid characters with underscores or remove them
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


async def delete_temp_files() -> None:
    temp_dir: str = 'temp/youtube'
    if os.path.exists(temp_dir):
        # remove the whole directory and its contents
        shutil.rmtree(temp_dir)
        logger.info("Deleted temporary files")
