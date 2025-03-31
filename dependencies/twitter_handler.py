import tweepy
from os import getenv
from typing import Annotated
# from dotenv import load_dotenv
from logger import LoggerManager

logger = LoggerManager(name="Twitter Handler", level="INFO", log_file="logs/twitter.log").get_logger()

# load_dotenv()
API_KEY: str | None = getenv('TWITTER_API_KEY', None)
API_KEY_SECRET: str | None = getenv('TWITTER_API_KEY_SECRET', None)
ACCESS_TOKEN: str | None = getenv('TWITTER_ACCESS_TOKEN', None)
ACCESS_TOKEN_SECRET: str | None = getenv('TWITTER_ACCESS_TOKEN_SECRET', None)
BEARER_TOKEN: str | None = getenv('TWITTER_BEARER_TOKEN', None)

TWEET_TEXT = Annotated[str, " Max Length: 280"]
TWEET_MAX_IMG_FILESIZE: int = 5  # TODO: JPEG | PNG In Megabytes
TWEET_MAX_VID_FILESIZE: int = 15  # TODO: MP4, MOV in Megabytes


class Tweet:
    def __init__(self):
        self.api: tweepy.API | None = None
        self.auth: tweepy.OAuth1UserHandler | None = None
        self.client: tweepy.Client | None = None
        self.authenticate_api()
        self.authenticate_client()

    def authenticate_api(self) -> bool:
        self.auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

        try:
            api = tweepy.API(self.auth, wait_on_rate_limit=True)
            user: tweepy.User = api.verify_credentials()
            if user:
                logger.info(f"Authenticated Twitter API as: {user.screen_name}")
                self.api = api
                return True
            else:
                logger.error("Failed to authenticate Twitter API")
                return False

        except Exception as e:
            logger.error(f"Failed to authenticate Twitter API: {str(e)}")
            return False

    def authenticate_client(self) -> bool:
        client: tweepy.Client = tweepy.Client(
            bearer_token=BEARER_TOKEN,
            consumer_key=API_KEY,
            consumer_secret=API_KEY_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET
        )

        try:
            me = client.get_me()
            logger.info(f"Authenticated Twitter Client as: {me.data.username}")
            self.client = client
            return True

        except tweepy.TweepyException as e:
            logger.error(f"Failed to authenticate Twitter Client {e}")
            return False

    def upload_attachments(self, filepath: str) -> str | bool:

        try:
            file: tweepy.Media = self.api.media_upload(filename=filepath)
            logger.info(f"Twitter API file uploaded: {file.media_id}")
            return file.media_id

        except Exception as e:
            logger.error(f"Twitter API file upload caused an Error: {e}")
            return False

    def delete_tweet(self, tweet_id: int) -> tuple[any, bool]:
        try:
            x = self.client.delete_tweet(id=tweet_id)
            return x, True  # Todo verify return type
        except tweepy.TweepyException as e:
            logger.error(f"{e}")
            return None, False

    def post_tweet(self, message: TWEET_TEXT, attachments: list[str] = None) -> tuple[any, bool]:
        uploaded_files: list[str] = []

        if len(message) > 280:
            raise ValueError("Tweet exceeds 280 characters.")

        if attachments:
            uploaded_files: list[str] = []
            for attachment in attachments:
                x = self.upload_attachments(attachment)
                if x:
                    uploaded_files.append(x)

                else:
                    return f"'{attachment}' couldn't be uploaded to Twitter", False

        tweet_message = message

        try:
            response = self.client.create_tweet(
                       text=tweet_message,
                       media_ids=uploaded_files if uploaded_files else None
                )

            if response and hasattr(response, "data"):
                logger.info("Tweet posted successfully")
                return response, True

        except Exception as e:
            logger.error(f"Failed to publish Tweet: {e}")
            return f"Failed to publish Tweet: {e}", False
