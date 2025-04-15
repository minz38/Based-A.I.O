# import shutil
import zipfile
from enum import Enum
from json import dump as jdump, load as jload
from os import getenv
from os import makedirs, path, remove, rename, walk
from pathlib import Path
from shutil import move as smove, rmtree as srmtree

import gspread
import requests
import yt_dlp
from oauth2client.service_account import ServiceAccountCredentials
from pydub import AudioSegment

from config_handler import GuildConfigHandler
from logger import LoggerManager

logger = LoggerManager(name="GoogleSheetHandler", level="INFO", log_name="webapp").get_logger()

DATA_PATH: Path = Path(getenv("DATA_PATH", "./data"))
CONFIG_PATH: Path = DATA_PATH / getenv("CONFIG_FOLDER_PATH", "config")
GUILD_CONFIG: Path = CONFIG_PATH / getenv("GUILD_CONFIG_FOLDER_NAME", "guilds")
TEMP_PATH: Path = DATA_PATH / getenv("TEMP_FOLDER_NAME", "temp")
GS_TEMP_FOLDER: Path = TEMP_PATH / getenv("GS_TEMP_FOLDER", "gs")
GOOGLE_CREDENTIAL_FOLDER: Path = DATA_PATH / getenv("GOOGLE_CREDENTIAL_FOLDER", "google-credentials")
CDN_PATH: Path = Path(getenv("CDN_PATH", "cdn"))

data_json: Path = GS_TEMP_FOLDER / "data.json"
temp_files: Path = GS_TEMP_FOLDER / "temp_files"


class QuestionType(Enum):
    TEXT_QUESTION = 'TEXT_QUESTION'
    SOUND_QUESTION = 'SOUND_QUESTION'
    CHALLENGE_PICTURE_QUESTION = 'CHALLENGE_PICTURE_QUESTION'


class Question:
    def __init__(self, question_type, question_text, answer_a, answer_b, answer_c, answer_d, correct_answer, picture,
                 picture_resize, sound, sound_loop, timestamp):
        self.question_type = question_type
        self.question_text = str(question_text)
        self.answer_a = str(answer_a)
        self.answer_b = str(answer_b)
        self.answer_c = str(answer_c)
        self.answer_d = str(answer_d)
        self.correct_answer = str(correct_answer)
        self.picture = None if picture == "" else picture
        self.picture_height = str('80%')
        self.picture_width = str('80%')
        self.sound = None if sound == "" else sound
        self.sound_loop = bool(sound_loop)
        self.timestamp = None if timestamp == "" else timestamp
        if self.question_type == 1:
            self.question_type = QuestionType.TEXT_QUESTION.value
        elif self.question_type == 2:
            self.question_type = QuestionType.SOUND_QUESTION.value
        elif self.question_type == 3:
            self.question_type = QuestionType.CHALLENGE_PICTURE_QUESTION.value
        if picture_resize != '':
            self.picture_width, self.picture_height = picture_resize.split('x')
            self.picture_height += '%'
            self.picture_width += '%'
        if sound_loop == '':
            self.sound_loop = False
        elif sound_loop != '':
            self.sound_loop = True

    def __str__(self):
        return (
            f"Question Type: {self.question_type}\n"
            f"Question Text: {self.question_text}\n"
            f"Answer A: {self.answer_a}\n"
            f"Answer B: {self.answer_b}\n"
            f"Answer C: {self.answer_c}\n"
            f"Answer D: {self.answer_d}\n"
            f"Correct Answer: {self.correct_answer}\n"
            f"Picture: {self.picture}\n"
            f"Picture Height: {self.picture_height}\n"
            f"Picture Width: {self.picture_width}\n"
            f"Sound: {self.sound}\n"
            f"Sound Loop: {self.sound_loop}\n"
            f"Timestamp: {self.timestamp}\n"
            f"------------------------------"
        )

    def __dict__(self):
        return {
            # "Question_ID": getattr(self, 'ID', ''),
            "question_type": self.question_type,
            "question_text": self.question_text,
            "answer_a": self.answer_a,
            "answer_b": self.answer_b,
            "answer_c": self.answer_c,
            "answer_d": self.answer_d,
            "correct_answer": self.correct_answer,
            "picture": {
                "path": self.picture,
                "height": self.picture_height,
                "width": self.picture_width
            },
            "sound": {
                "path": self.sound,
                "loop": self.sound_loop,
                "timestamp": self.timestamp
            }
        }

    def knightx(self):
        return {
            "question_type": self.question_type,
            "question_text": self.question_text,
            "answer_a": self.answer_a,
            "answer_b": self.answer_b,
            "answer_c": self.answer_c,
            "answer_d": self.answer_d,
            "correct_answer": self.correct_answer,
            "picture": {
                "path": self.picture,
                "height": self.picture_height,
                "width": self.picture_width
            },
            "sound": {
                "path": self.sound,
                "loop": self.sound_loop
            }
        }


class GoogleSheetHandler:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.gs_worksheet_name: str = ''
        self.gs_credentials_file: str = ''
        self.gs_credentials = None
        self.gs_client = None
        self.cdn_file_path: str = ''
        self.gs_id: str = ''
        self.gs_scope: list[str] = ["https://www.googleapis.com/auth/spreadsheets",
                                    "https://www.googleapis.com/auth/drive"]
        self.load_configs()

    def load_configs(self):
        handler = GuildConfigHandler(self.guild_id)
        config: dict[str, any] = handler.get_config()

        self.gs_worksheet_name = config['gs_worksheet_name']
        self.gs_credentials_file = config['gs_credentials_file']
        self.gs_credentials = ServiceAccountCredentials.from_json_keyfile_name(
            self.gs_credentials_file, self.gs_scope)
        self.gs_client = gspread.authorize(self.gs_credentials)
        self.cdn_file_path = config['cdn_file_path']
        self.gs_id = config['gs_id']

    def pull_from_spreadsheet(self):
        sheet = self.gs_client.open_by_key(self.gs_id).worksheet(self.gs_worksheet_name)
        # rows = sheet.get_all_records()
        rows = sheet.get_all_records(empty2zero=False, head=1, default_blank="")
        logger.debug(f'fetched {len(rows)} records')

        questions = []
        for i, row in enumerate(rows, start=1):
            if not any(row.values()):
                logger.debug(f'No more records found. Breaking...')
                break
            question = Question(
                row['question_type'],
                row['question_text'],
                row['answer_a'],
                row['answer_b'],
                row['answer_c'],
                row['answer_d'],
                row['correct_answer'],
                row['picture'],
                row['picture_resize'],
                row['sound'],
                row['sound_loop'],
                row['timestamp']
            )
            # setattr(question, 'ID', f'{i}')  # Set attribute 'name' with QuestionX format
            questions.append(question.__dict__())
            logger.debug(f'Question {i} processed')

        # dump all the questions into a JSON file
        with open(data_json, 'w') as f:
            jdump(questions, f, indent=4)

        return questions

    def download_sounds(self, question, index):
        # check if the folder temp_files exist
        makedirs(temp_files, exist_ok=True)

        # Download the sound file from YouTube and convert it to MP3.
        # We're using youtube-dl for this task.
        # Note: You'll need to have youtube-dl installed and in your system's PATH.
        # Also, make sure you have ffmpeg installed and in your system's PATH for audio conversion.
        sound_url = question['sound']['path']
        question_nr = index
        logger.debug(f'Downloading sound from {sound_url}')
        # try to download the sound file, expect errors. after downloading convert it using ffmpeg.exe
        try:
            temp_audio_path: Path = temp_files / question_nr
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_audio_path,  # Output file name with .mp3 extension
                'noplaylist': True,
                'quiet': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',  # Force the output format to be MP3
                    'preferredquality': '192',  # Audio quality (bitrate)
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(sound_url, download=True)

        except Exception as e:
            logger.error(f'Error downloading sound: {e}')
        return question

    def process_audio(self):
        # Load the questions from data.json

        with open(data_json, 'r') as f:
            questions = jload(f)
        # loop through the questions, for every question with the type SOUND_QUESTION
        # change the name of the sound files to the new one and store the file in {page}/{question_nr}.mp3
        for index, question in enumerate(questions):
            if question['sound']['path'] is not None and question['sound']['path'].startswith('https://'):
                try:
                    self.download_sounds(question, index)
                    nr = index
                    temp_audio_path = temp_files / f"{nr}.mp3"
                    out_path: Path = GS_TEMP_FOLDER / self.gs_worksheet_name

                    if path.exists(temp_audio_path):
                        # move file to a new folder, if the folder doesn't exist create it
                        if not path.exists(out_path):
                            makedirs(out_path)
                        # when the file already exists delete it first
                        if path.exists(out_path / f"{nr}.mp3"):
                            remove(out_path / f"{nr}.mp3")
                            logger.debug(
                                f'Moved {temp_audio_path} to '
                                f'{self.gs_worksheet_name}/{nr}.mp3')
                        rename(temp_audio_path, out_path / f"{nr}.mp3")
                        question['sound']['path'] = out_path / f"{nr}.mp3"

                    if question['sound']['timestamp'] is not None:
                        self.trim_audio(question['sound']['path'], question['sound']['path'],
                                        question['sound']['timestamp'])
                        logger.debug(f'Trimmed audio file {question["sound"]["path"]}')
                    if question['sound']['path'] is not None:
                        question['sound']['path'] = (f'{self.cdn_file_path}'  # todo maybe change to a env path
                                                     f'{out_path}/{nr}.mp3')
                    else:
                        logger.debug(f'No trim needed for question {index}')
                except Exception as e:
                    logger.error(f'Error processing audio: {e}')

            with open(data_json, 'w') as f:
                jdump(questions, f, indent=4)

    @staticmethod
    def parse_time(time_str):
        minutes, seconds = map(int, time_str.split(':'))
        return minutes, seconds

    def trim_audio(self, input_file, output_file, time_range):
        # Load the audio file
        audio = AudioSegment.from_mp3(input_file)

        # Parse start time and end time from the time_range input
        start_time_str, end_time_str = time_range.split('-')
        start_minutes, start_seconds = self.parse_time(start_time_str)
        end_minutes, end_seconds = self.parse_time(end_time_str)

        # Convert start time and end time to milliseconds
        start_time_ms = start_minutes * 60 * 1000 + start_seconds * 1000
        end_time_ms = end_minutes * 60 * 1000 + end_seconds * 1000

        # Trim the audio
        trimmed_audio = audio[start_time_ms:end_time_ms]

        # Export the trimmed audio to the output file
        trimmed_audio.export(output_file, format="mp3")

    def process_picture(self):
        with open(data_json, 'r') as f:
            questions = jload(f)
        for index, question in enumerate(questions):
            if question['picture']['path'] and question['picture']['path'].startswith('https://'):
                try:
                    self.download_picture(question, index)
                    nr = index
                    # temp_picture_path = f'temp_files/{self.gs_worksheet_name}-{nr}.jpg'  # old version
                    temp_picture_path = temp_files / f"{nr}.jpg"
                    out_path: Path = GS_TEMP_FOLDER / self.gs_worksheet_name
                    if path.exists(temp_picture_path):
                        # move file to a new folder, if the folder doesn't exist create it
                        if not path.exists(out_path):
                            makedirs(out_path)
                        # when the file already exists delete it first
                        if path.exists(out_path / f"{nr}.jpg"):
                            remove(out_path / f"{nr}.jpg")
                            logger.debug(
                                f'File {out_path}/f"{nr}.jpg"'
                                f'already exists, recreating file')
                        rename(temp_picture_path, out_path / f"{nr}.jpg")
                        question['picture']['path'] = (f'{self.cdn_file_path}'  # TODO same here maybe switch it
                                                       f'{out_path}/{nr}.jpg')
                    else:
                        logger.debug(f'No picture found for question {index}')
                except Exception as e:
                    logger.error(f'Error downloading picture: {e}')

            with open(data_json, 'w') as f:
                jdump(questions, f, indent=4)

    def download_picture(self, question, index):
        # download using requests
        url = question['picture']['path']
        r = requests.get(url, stream=True)
        with open(temp_files / f"{index}.jpg", 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)

    def move_json(self):
        with open(data_json, 'r') as f:
            data = jload(f)

        # Check and remove the 'timestamp' key in the 'sound' dictionary
        for question in data:
            if 'sound' in question and 'timestamp' in question['sound']:
                del question['sound']['timestamp']

        with open(data_json, 'w') as f:
            jdump(data, f, indent=4)
        if not path.exists(GS_TEMP_FOLDER / self.gs_worksheet_name):
            makedirs(GS_TEMP_FOLDER / self.gs_worksheet_name)
        if path.exists(f'{GS_TEMP_FOLDER / self.gs_worksheet_name}/data.json'):
            remove(f'{GS_TEMP_FOLDER / self.gs_worksheet_name}/data.json')
        rename(data_json, f'{GS_TEMP_FOLDER / self.gs_worksheet_name}/data.json')

    @staticmethod
    def zip_folder(folder_path: str, output_path: str):
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in walk(folder_path):
                for file in files:
                    # Create a relative path for files to keep the directory structure
                    relative_path = path.relpath(path.join(root, file), path.dirname(folder_path))
                    zipf.write(path.join(root, file), arcname=relative_path)
        logger.info(f"Zipped {folder_path} to {output_path}")

    async def delete_zip_folder(self):
        if path.exists(GS_TEMP_FOLDER / '{self.gs_worksheet_name}.zip'):
            remove(GS_TEMP_FOLDER / "{self.gs_worksheet_name}.zip")
            logger.info(f"Deleted Zip: {GS_TEMP_FOLDER / self.gs_worksheet_name}.zip")
        # delete folder
        if path.exists(GS_TEMP_FOLDER / self.gs_worksheet_name):
            srmtree(GS_TEMP_FOLDER / self.gs_worksheet_name)
            logger.info(f"Deleted Folder: {GS_TEMP_FOLDER / self.gs_worksheet_name}")

    def push_question_to_gs(self, data):
        try:
            sheet = self.gs_client.open_by_key(self.gs_id).worksheet(self.gs_worksheet_name)
            sheet.append_rows(data)
            logger.info(f"Successfully pushed Question: '{data[0][1]}' to sheet: '{self.gs_worksheet_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to push Question: '{data[0][1]}' to sheet: '{self.gs_worksheet_name}': {e}")
            return False

    def feed_cdn(self):
        try:
            # delete the folder if it exists and recreate it
            if path.exists(CDN_PATH / self.gs_worksheet_name):
                srmtree(CDN_PATH / self.gs_worksheet_name)
            # create new directory in cdn and move files to it

            local_directory = GS_TEMP_FOLDER / self.gs_worksheet_name

            # move files to cdn directory
            smove(local_directory, CDN_PATH)
            logger.info(f"Moved files to CDN directory: {self.gs_worksheet_name}")
        except Exception as e:
            logger.error(f"Failed to move files to CDN directory: {str(e)}")
            return False

    def cleanup(self):
        cleanup_directory: Path = CDN_PATH / self.gs_worksheet_name
        cleanup_directory_2: Path = temp_files
        try:
            # delete the folder if it exists
            if path.exists(cleanup_directory):
                srmtree(cleanup_directory)
                logger.info(f"Deleted cleanup directory: {cleanup_directory}")
            if path.exists(cleanup_directory_2):
                srmtree(cleanup_directory_2)
                logger.info(f"Deleted cleanup directory: {cleanup_directory_2}")
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup directory: {str(e)}")
            return False

    def process_all(self):
        try:
            self.process_audio()
            self.process_picture()
            self.move_json()
            self.feed_cdn()
            # self.zip_folder(f'{self.gs_worksheet_name}', f'{self.gs_worksheet_name}.zip')
            return True
        except Exception as e:
            logger.error(f"Failed to process all files: {str(e)}")
            return False
