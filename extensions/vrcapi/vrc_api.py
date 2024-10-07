import os
import json
import pyotp
import vrchatapi
from vrchatapi.api import authentication_api
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.api.groups_api import GroupsApi
from vrchatapi.api.users_api import UsersApi
from dependencies.encryption_handler import decrypt
from logger import LoggerManager

logger = LoggerManager(name="VrchatApiHandler", level="INFO", log_file="logs/vrc-api.log").get_logger()


class VrchatApiHandler:
    def __init__(self, guild):
        self.guild = guild

        config_check_result = self.check_config()

        if not config_check_result:
            raise ValueError(f"Config check failed for guild: {self.guild}")

        if config_check_result:
            # assign the keys values to instance variables
            self.vrc_username = config_check_result['vrc_username']
            self.vrc_passwd = decrypt(config_check_result['vrc_password'])
            self.vrc_totp = decrypt(config_check_result['vrc_totp'])
            self.vrc_group_id = config_check_result['vrc_group_id']
            self.moderator_channel_id = config_check_result['moderator_channel_id']
            self.moderator_role = config_check_result['moderator_role']
            self.log_channel_id = config_check_result['log_channel_id']
            self.user_agent = 'Discord_Bridge/1.0 (Contact: pmph@mailbox.org)'

            # Create the VrchatAPI instance
            configuration = vrchatapi.Configuration(
                username=self.vrc_username,
                password=self.vrc_passwd
            )

            with vrchatapi.ApiClient(configuration) as self.api_client:
                self.api_client.user_agent = self.user_agent
                self.auth_api = authentication_api.AuthenticationApi(self.api_client)

            try:
                current_user = self.auth_api.get_current_user()
                logger.info(f'Logged in as: {current_user.display_name}')

            except UnauthorizedException as e:
                if e.status == 200:
                    if "Email 2 Factor Authentication" in e.reason:
                        self.auth_api.verify2_fa_email_code(
                            two_factor_email_code=TwoFactorEmailCode(input("Email 2FA Code: ")))
                    elif "2 Factor Authentication" in e.reason:
                        code = self.generate_totp_code()
                        self.auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(code=code))
                    self.current_user = self.auth_api.get_current_user()
                else:
                    logger.error("Exception when calling API: %s", e)

            except vrchatapi.ApiException as e:
                logger.error("Exception when calling API: %s", e)
            logger.info(f'Logged in as: {self.current_user.display_name}')  # Second logging corrected

            # use these to interact with the VRChat API
            self.group_api = GroupsApi(self.api_client)
            self.user_api = UsersApi(self.api_client)

    def generate_totp_code(self):
        totp = pyotp.TOTP(self.vrc_totp)
        return totp.now()

    # check if a config exists for the current guild
    def check_config(self):
        with open(f'configs/guilds/{self.guild}.json', 'r') as conf:
            config = json.load(conf)

        # check if the required keys exist in the config
        # required keys: username, password, totp_secret, group_id, moderator_channel_id, moderator_role, log_channel_id
        required_keys = ['vrc_username',
                         'vrc_password',
                         'vrc_totp',
                         'vrc_group_id',
                         'moderator_channel_id',
                         'moderator_role',
                         'log_channel_id']

        if not all(key in config for key in required_keys):
            return False

        else:

            return config

    def get_group_join_requests(self):

        try:
            join_requests = self.group_api.get_group_requests(self.vrc_group_id)

            if not join_requests:
                logger.error("No join requests found.")
                return None

            join_request_entries = []
            for request in join_requests:
                join_request_entry = {
                    "request_id": request.id,
                    "group_id": request.group_id,
                    "created_at": request.created_at,
                    "requester_display_name": request.user.display_name,
                    "requester_id": request.user.id,
                    "status": request.membership_status,
                    "joined_at": request.joined_at,
                    "user_thumbnail_url": request.user.thumbnail_url,
                    "current_user_avatar_thumbnail": request.user.current_avatar_thumbnail_image_url,
                    "profile_pic_override": request.user.profile_pic_override,
                    "user_icon_url": request.user.icon_url
                }

                # append request entry to the list
                join_request_entries.append(join_request_entry)
            logger.info("Fetched %s join requests.", len(join_requests))
            return join_request_entries

        except vrchatapi.ApiException as err:
            logger.error("Exception when fetching join Requests from vrc_api: %s\n", err)

    def get_user_profile(self, user_id):

        try:
            user_profile = self.user_api.get_user(user_id)
            # print(user_profile)
            profile_data = {
                "User ID": user_profile.id,
                "Display Name": user_profile.display_name,
                "Bio": user_profile.bio,
                "Bio Links": user_profile.bio_links,
                "Profile Picture URL": user_profile.current_avatar_image_url,
                "Avatar Image URL": user_profile.current_avatar_thumbnail_image_url,
                "Profile Pic Override": user_profile.profile_pic_override,
                "Profile Thumbnail Override": user_profile.profile_pic_override_thumbnail,
                "Status": user_profile.status,
                "Status Description": user_profile.status_description,
                "last Login": user_profile.last_login
            }
            return profile_data

        except vrchatapi.ApiException as er:
            print("Exception when calling API: %s\n", er)
            return None

    def handle_request(self, user_id, user_name, moderator_name, action):
        try:
            match action:
                case "Accept":
                    self.group_api.respond_group_join_request_with_http_info(
                        user_id=user_id,
                        group_id=self.vrc_group_id,
                        respond_group_join_request={"action": "accept", "block": False}
                    )
                    logger.info(f"VRC User {user_name} has been accepted into the group by {moderator_name}.")
                    return True
                case "Reject":
                    self.group_api.respond_group_join_request_with_http_info(
                        user_id=user_id,
                        group_id=self.vrc_group_id,
                        respond_group_join_request={"action": "reject", "block": False}
                    )
                    logger.info(f"VRC User {user_name} has been rejected by {moderator_name}.")
                    return True
                case "Block":
                    self.group_api.respond_group_join_request_with_http_info(
                        user_id=user_id,
                        group_id=self.vrc_group_id,
                        respond_group_join_request={"action": "deny", "block": True}
                    )
                    logger.info(f"VRC User {user_name} has been blocked by {moderator_name}.")
                    return True
                case _:
                    logger.error(f"Invalid action: {action}. Supported actions are 'Accept', 'Reject', 'Block'.")
                    return False

        except vrchatapi.ApiException as err:
            logger.error("Exception when handling join request: %s\n", err)
            return False
