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
TWITTER_USERNAME: str | None = getenv("TWITTER_USERNAME", None)

TWEET_TEXT = Annotated[str, " Max Length: 280"]
TWEET_MAX_IMG_FILESIZE: int = 5  # TODO: JPEG | PNG In Megabytes
TWEET_MAX_VID_FILESIZE: int = 15  # TODO: MP4, MOV in Megabytes



class Tweet:
    """
    A class to handle Twitter API operations.

    This class provides methods to authenticate with the Twitter API,
    upload media attachments, and post tweets.
    """

    def __init__(self):
        """
        Initialize the Tweet class.

        Sets up API, auth, and client attributes and authenticates both API and client.
        """
        self.api: tweepy.API | None = None
        self.auth: tweepy.OAuth1UserHandler | None = None
        self.client: tweepy.Client | None = None
        self.username: str | None = None
        self.authenticate_api()
        self.authenticate_client()

    def authenticate_api(self) -> bool:
        """
        Authenticate the Twitter API using OAuth1UserHandler.

        Returns:
            bool: True if authentication is successful, False otherwise.
        """
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
        """
        Authenticate the Twitter client using provided credentials.

        Returns:
            bool: True if authentication is successful, False otherwise.
        """
        client: tweepy.Client = tweepy.Client(
            bearer_token=BEARER_TOKEN,
            consumer_key=API_KEY,
            consumer_secret=API_KEY_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET
        )

        try:
            # me = client.get_me()
            # logger.info(f"Authenticated Twitter Client as: {me.data.username}")
            self.client = client
            logger.info(f"Twitter Client Authenticated!")
            # self.username = me.data.username
            return True

        except tweepy.TweepyException as e:
            logger.error(f"Failed to authenticate Twitter Client {e}")
            return False

    def get_username(self) -> str | None:
        if self.username:
            return self.username

        if TWITTER_USERNAME:
            return TWITTER_USERNAME
        try:
            me = self.client.get_me()
            self.username = me.data.username
            return self.username

        except Exception as e:
            logger.error(f"Failed to get Twitter username: {e}")
            return None

    def upload_attachments(self, filepath: str) -> str | bool:
        """
        Upload a file attachment to Twitter.

        Args:
            filepath (str): The path to the file to be uploaded.

        Returns:
            str | bool: The media ID if upload is successful, False otherwise.
        """
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
        """
        Post a tweet with optional media attachments.
    
        This function creates and posts a tweet using the authenticated Twitter client.
        It can include text and optional media attachments (images or videos).
    
        Args:
            message (TWEET_TEXT): The text content of the tweet. Must not exceed 280 characters.
            attachments (list[str], optional): A list of file paths to media attachments (images or videos).
                Defaults to None.
    
        Returns:
            tuple[any, bool]: A tuple containing two elements:
                - The response from the Twitter API (type varies) or an error message (str)
                - A boolean indicating whether the tweet was successfully posted (True) or not (False)
    
        Raises:
            ValueError: If the tweet message exceeds 280 characters.
    
        Note:
            - The function will attempt to upload all attachments before posting the tweet.
            - If any attachment fails to upload, the tweet will not be posted.
        """
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
                    return None, False

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
            return None, False
