import os
import yt_dlp
import asyncio
import shutil
from logger import LoggerManager
import re

logger = LoggerManager(name="Music Downloader", level="info", log_file="logs/youtube_downloader.log").get_logger()
path_to_ffmpeg = 'dependencies/ffmpeg.exe'


async def download_music(video_url):
    logger.info(f"Downloading music from {video_url}")
    music_output_path = 'temp/youtube/music'

    os.makedirs(music_output_path, exist_ok=True)

    # Format: Mp3, Quality: best, convert to mp3 using ffmpeg
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{music_output_path}/song.%(ext)s',  # %(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'ffmpeg_location': path_to_ffmpeg,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    }

    try:
        # download the audio using yt_dlp, return the filepath once its downloaded
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            file_title = info_dict.get('title', 'unknown_title')
            file_path = f"{music_output_path}/song.mp3"
            logger.info(f"Downloaded music to {file_path}")
            return file_path

    except Exception as e:
        logger.error(f"Error downloading music: {e}")
        return False


async def download_video(video_url):
    logger.info(f"Downloading video from {video_url}")
    video_output_path = 'temp/youtube/video'

    os.makedirs(video_output_path, exist_ok=True)

    # Format: mp4, convert to mp4 using ffmpeg
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': f'{video_output_path}/%(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'ffmpeg_location': path_to_ffmpeg,
    }

    try:
        # download the video using yt_dlp, return the filepath once its downloaded
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            file_title = info_dict.get('title', 'unknown_title')
            file_path = f"{video_output_path}/{file_title}.mp4"
            logger.info(f"Downloaded video to {file_path}")
            filesize = os.path.getsize(file_path)
            if filesize <= 1024 * 1024 * 100:
                return file_path
            else:
                logger.warning(f"Video file {file_path} is too large, it's {filesize / (1024 * 1024)} "
                               f"MB. Skipping download.")
                return False

    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        return False


def sanitize_filename(filename):
    # Replace invalid characters with underscores or remove them
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


async def delete_temp_files():
    temp_dir = 'temp/youtube'
    if os.path.exists(temp_dir):
        # remove the whole directory and its contents
        shutil.rmtree(temp_dir)
        logger.info("Deleted temporary files")
