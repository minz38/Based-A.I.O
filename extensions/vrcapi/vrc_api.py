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


class VrchatApiHandler:
    def __init__(self, guild, call, variable):
        self.guild = guild
        self.call = call
        self.variable = variable

        config_check_result = self.check_config()

        if not config_check_result:
            raise ValueError(f"Config check failed for guild: {self.guild}")

    # check if a config exists for the current guild
    async def check_config(self):
        with open(f'config/{self.guild}.json', 'r') as conf:
            config = json.load(conf)

        # check if the required keys exist in the config
        # required keys: username, password, totp_secret, group_id, moderator_channel_id, moderator_role, log_channel_id
        required_keys = ['username',
                         'password',
                         'totp_secret',
                         'group_id',
                         'moderator_channel_id',
                         'moderator_role',
                         'log_channel_id']

        if not all(key in config for key in required_keys):
            return False

        else:

            return config

    async def get_group_audit_log(self):
        pass

    async def generate_totp_code(self):

        pass
