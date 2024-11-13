import os
import json
import yt_dlp
import shutil
import zipfile
import gspread
import paramiko
import requests
from enum import Enum
from pydub import AudioSegment
from paramiko import SSHClient, AutoAddPolicy
from logger import LoggerManager
from oauth2client.service_account import ServiceAccountCredentials
import dependencies.encryption_handler as encryption_handler

logger = LoggerManager(name="GoogleSheetHandler", level="INFO", log_file="logs/GoogleSheetHandler.log").get_logger()

# path_to_ffmpeg: str = '/code/ff/ffmpeg'
# path_to_ffprobe: str = '/code/ff/ffprobe'


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
        self.cdn_url: str = ''
        self.cdn_port: int = 0
        self.cdn_user: str = ''
        self.cdn_password: str = ''
        self.gs_scope: list[str] = ["https://www.googleapis.com/auth/spreadsheets",
                                    "https://www.googleapis.com/auth/drive"]
        self.load_configs()

    def load_configs(self):
        with open(f'configs/guilds/{self.guild_id}.json', 'r') as config_file:
            config = json.load(config_file)

        self.gs_worksheet_name = config['gs_worksheet_name']
        self.gs_credentials_file = config['gs_credentials_file']
        self.gs_credentials = ServiceAccountCredentials.from_json_keyfile_name(
            self.gs_credentials_file, self.gs_scope)
        self.gs_client = gspread.authorize(self.gs_credentials)
        self.cdn_file_path = config['cdn_file_path']
        self.gs_id = config['gs_id']
        self.cdn_url = config['cdn_url']
        self.cdn_port = config['cdn_port']
        self.cdn_user = encryption_handler.decrypt(config['cdn_user'])
        self.cdn_password = encryption_handler.decrypt(config['cdn_password'])

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
        with open('data.json', 'w', ) as outfile:
            json.dump(questions, outfile, indent=4)

        return questions

    def download_sounds(self, question, index):
        sound_url = question['sound']['path']
        question_nr = index
        logger.debug(f'Downloading sound from {sound_url}')
        # try to download the sound file, expect errors. after downloading convert it using ffmpeg.exe
        try:
            temp_audio_path = f'temp_files/{self.gs_worksheet_name}-{question_nr}'
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_audio_path,  # Output file name with .mp3 extension
                'noplaylist': True,
                'quiet': True,
                # 'ffmpeg_location': path_to_ffmpeg,  # Path to ffmpeg.exe'
                # 'ffprobe_location': path_to_ffprobe,
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
        with open('data.json', 'r') as f:
            questions = json.load(f)
        # loop through the questions, for every question with the type SOUND_QUESTION
        # change the name of the sound files to the new one and store the file in {page}/{question_nr}.mp3
        for index, question in enumerate(questions):
            if question['sound']['path'] is not None and question['sound']['path'].startswith('https://'):
                try:
                    self.download_sounds(question, index)
                    nr = index
                    temp_audio_path = f'temp_files/{self.gs_worksheet_name}-{nr}.mp3'
                    if os.path.exists(temp_audio_path):
                        # move file to a new folder, if the folder doesn't exist create it
                        if not os.path.exists(f'{self.gs_worksheet_name}'):
                            os.makedirs(f'{self.gs_worksheet_name}')
                        # when the file already exists delete it first
                        if os.path.exists(f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.mp3'):
                            os.remove(f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.mp3')
                            logger.debug(
                                f'Moved {temp_audio_path} to {self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.mp3')
                        os.rename(temp_audio_path, f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.mp3')
                        question['sound']['path'] = f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.mp3'
                    if question['sound']['timestamp'] is not None:
                        self.trim_audio(question['sound']['path'], question['sound']['path'],
                                        question['sound']['timestamp'])
                        logger.debug(f'Trimmed audio file {question["sound"]["path"]}')
                    if question['sound']['path'] is not None:
                        question['sound']['path'] = (f'{self.cdn_file_path}'
                                                     f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.mp3')
                    else:
                        logger.debug(f'No trim needed for question {index}')
                except Exception as e:
                    logger.error(f'Error processing audio: {e}')

            with open('data.json', 'w') as f:
                json.dump(questions, f, indent=4)

    @staticmethod
    def parse_time(time_str):
        minutes, seconds = map(int, time_str.split(':'))
        return minutes, seconds

    def trim_audio(self, input_file, output_file, time_range):
        # Set paths to ffmpeg and ffprobe
        # AudioSegment.ffmpeg = path_to_ffmpeg
        # AudioSegment.converter = path_to_ffprobe

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
        with open('data.json', 'r') as f:
            questions = json.load(f)
        for index, question in enumerate(questions):
            if question['picture']['path'] and question['picture']['path'].startswith('https://'):
                try:
                    self.download_picture(question, index)
                    nr = index
                    temp_picture_path = f'temp_files/{self.gs_worksheet_name}-{nr}.jpg'
                    if os.path.exists(temp_picture_path):
                        # move file to a new folder, if the folder doesn't exist create it
                        if not os.path.exists(self.gs_worksheet_name):
                            os.makedirs(self.gs_worksheet_name)
                        # when the file already exists delete it first
                        if os.path.exists(f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.jpg'):
                            os.remove(f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.jpg')
                            logger.debug(
                                f'File {self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.jpg already exists, recreating file')
                        os.rename(temp_picture_path, f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.jpg')
                        question['picture']['path'] = (f'{self.cdn_file_path}'
                                                       f'{self.gs_worksheet_name}/{self.gs_worksheet_name}-{nr}.jpg')
                    else:
                        logger.debug(f'No picture found for question {index}')
                except Exception as e:
                    logger.error(f'Error downloading picture: {e}')

            with open('data.json', 'w') as f:
                json.dump(questions, f, indent=4)

    def download_picture(self, question, index):
        # download using requests
        url = question['picture']['path']
        r = requests.get(url, stream=True)
        with open(f'temp_files/{self.gs_worksheet_name}-{index}.jpg', 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)

    def move_json(self):
        with open('data.json', 'r') as f:
            data = json.load(f)

        # Check and remove the 'timestamp' key in the 'sound' dictionary
        for question in data:
            if 'sound' in question and 'timestamp' in question['sound']:
                del question['sound']['timestamp']

        with open('data.json', 'w') as f:
            json.dump(data, f, indent=4)
        if not os.path.exists(self.gs_worksheet_name):
            os.makedirs(self.gs_worksheet_name)
        if os.path.exists(f'{self.gs_worksheet_name}/data.json'):
            os.remove(f'{self.gs_worksheet_name}/data.json')
        os.rename('data.json', f'{self.gs_worksheet_name}/data.json')

    @staticmethod
    def zip_folder(folder_path: str, output_path: str):
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    # Create a relative path for files to keep the directory structure
                    relative_path = os.path.relpath(os.path.join(root, file), os.path.dirname(folder_path))
                    zipf.write(os.path.join(root, file), arcname=relative_path)
        logger.info(f"Zipped {folder_path} to {output_path}")

    async def delete_zip_folder(self):
        if os.path.exists(f'{self.gs_worksheet_name}.zip'):
            os.remove(f"{self.gs_worksheet_name}.zip")
            logger.info(f"Deleted Zip: {self.gs_worksheet_name}.zip")
        # delete folder
        if os.path.exists(self.gs_worksheet_name):
            shutil.rmtree(self.gs_worksheet_name)
            logger.info(f"Deleted Folder: {self.gs_worksheet_name}")

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
        local_directory = f'{self.gs_worksheet_name}'
        remote_directory = f'/var/www/cdn/html/{self.gs_worksheet_name}'

        # Establish an SSH client and set policies
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Connect to the server
            ssh.connect(self.cdn_url,
                        port=self.cdn_port,
                        username=self.cdn_user,
                        password=self.cdn_password)
            sftp = ssh.open_sftp()
            logger.debug(f"Connected to {self.cdn_url}:{self.cdn_port}")

            # Attempt to change into the remote directory or create if it doesn't exist
            try:
                sftp.chdir(remote_directory)
                logger.debug(f"Changed to existing directory {remote_directory}")
            except IOError:
                logger.debug(f"Creating directory {remote_directory}")
                try:
                    sftp.mkdir(remote_directory)
                    sftp.chdir(remote_directory)
                    logger.debug(f"Changed to new directory {remote_directory}")
                except Exception as e:
                    logger.error(f"Failed to create directory {remote_directory}: {e}")
                    return

            # Upload the entire folder recursively
            for root, dirs, files in os.walk(local_directory):
                for dir in dirs:
                    remote_path = os.path.join(remote_directory,
                                               os.path.relpath(os.path.join(root, dir), local_directory)).replace('\\',
                                                                                                                  '/')
                    try:
                        sftp.chdir(remote_path)
                    except IOError:
                        logger.info(f"Creating remote directory {remote_path}")
                        sftp.mkdir(remote_path)

                for file in files:
                    local_path = os.path.join(root, file)
                    remote_path = os.path.join(remote_directory, os.path.relpath(local_path, local_directory)).replace(
                        '\\',
                        '/')
                    logger.info(f"Uploading {local_path} to {remote_path}")
                    sftp.put(local_path, remote_path)

            logger.info(f"All files and directories have been uploaded to CDN successfully.")
            return True

        except Exception as e:
            logger.error(f"Failed to upload files to CDN: {str(e)}")
            return False

        finally:
            if sftp:
                sftp.close()
            if ssh:
                ssh.close()

    def delete_remote_folder(self):
        # Assuming CdnConfig and other necessary imports are defined elsewhere in the project
        folder_path = f'/var/www/cdn/html/{self.gs_worksheet_name}'

        # Establish an SSH client and set policies
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())

        try:
            # Connect to the server
            ssh.connect(self.cdn_url,
                        port=self.cdn_port,
                        username=self.cdn_user,
                        password=self.cdn_password)
            logger.debug(f"Connected to {self.cdn_url}:{self.cdn_port}")

            # Execute command to delete files and folders recursively
            stdin, stdout, stderr = ssh.exec_command(f'rm -rf {folder_path}')
            errors = stderr.read().decode('utf-8')
            if errors:
                raise Exception(f"Error deleting remote folder: {errors}")
            logger.debug(f"Folder deleted successfully.")
        except Exception as e:
            logger.error(f"Failed to delete remote folder: {str(e)}")
        finally:
            # Close the SSH connection
            ssh.close()

    def process_all(self):
        try:
            self.process_audio()
            self.process_picture()
            self.move_json()
            self.delete_remote_folder()
            self.feed_cdn()
            self.zip_folder(f'{self.gs_worksheet_name}', f'{self.gs_worksheet_name}.zip')
            return True
        except Exception as e:
            logger.error(f"Failed to process all files: {str(e)}")
            return False
