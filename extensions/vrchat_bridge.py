import os
import json
import shutil
import discord
from discord.ext import commands, tasks
from discord import app_commands, message
from logger import LoggerManager
from extensions.vrcapi.vrc_api import VrchatApiHandler
import dependencies.encryption_handler as encryption_handler


# Initialize the logger
logger = LoggerManager(name="VRC-API", level="INFO", log_file="logs/vrc-api.log").get_logger()

# Define the path for guild configuration
CONFIG_PATH: str = "configs/guilds"

# Load the encryption key from the config
key: bytes = encryption_handler.load_key_from_config()

json_keys: list[str] = ["vrc_username", "vrc_password", "vrc_totp", "vrc_group_id", "moderator_channel_id",
                        "moderator_role", "log_channel_id"]

TEMP_VRC_PATH: str = "temp/vrc"


# Create a Modal class for the form
class VrchatCredentialsModal(discord.ui.Modal, title="Enter VRChat Credentials"):
    vrc_username = discord.ui.TextInput(label="VRChat Username", style=discord.TextStyle.short, required=True)
    vrc_password = discord.ui.TextInput(label="VRChat Password", style=discord.TextStyle.short, required=True)
    vrc_totp = discord.ui.TextInput(label="TOTP Secret", style=discord.TextStyle.short, required=True)
    vrc_group_id = discord.ui.TextInput(label="VRChat Group ID", style=discord.TextStyle.short, required=True)

    def __init__(self, guild_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Encrypt the password and TOTP secret using the encryption handler
        encrypted_password: str = encryption_handler.encrypt(self.vrc_password.value, key)
        encrypted_totp: str = encryption_handler.encrypt(self.vrc_totp.value, key)

        # Create the credentials dictionary with the encrypted values
        credentials = {
            "vrc_username": self.vrc_username.value,
            "vrc_password": encrypted_password,  # Encrypted password
            "vrc_totp": encrypted_totp,  # Encrypted TOTP secret
            "vrc_group_id": self.vrc_group_id.value
        }
        # Load existing data from the guild's config file (if any)
        guild_config_file = os.path.join(CONFIG_PATH, f"{self.guild_id}.json")
        if os.path.exists(guild_config_file):
            with open(guild_config_file, 'r') as f:
                data = json.load(f)
        else:
            data = {}

        # Update the existing data with the new credentials
        data.update(credentials)

        # Defer the interaction and present the second modal
        await interaction.response.defer(ephemeral=True)  # noqa

        # Send the second modal for additional settings
        view = discord.ui.View()
        view.add_item(ProceedToAdditionalModalButton(guild_id=self.guild_id, initial_data=data))
        await interaction.followup.send("Click the button below to continue setting up additional settings.\n"
                                        "You you will need Moderator Channel ID, Moderator Role ID and A Log channel "
                                        "ID.",
                                        view=view,
                                        ephemeral=True)


class ProceedToAdditionalModalButton(discord.ui.Button):
    def __init__(self, guild_id, initial_data):
        super().__init__(label="Proceed to step 2", style=discord.ButtonStyle.green)
        self.guild_id = guild_id
        self.initial_data = initial_data

    async def callback(self, interaction: discord.Interaction):
        # Show the second modal for additional settings
        await interaction.response.send_modal(AdditionalSettingsModal(guild_id=self.guild_id,  # noqa
                                                                      initial_data=self.initial_data))


class AdditionalSettingsModal(discord.ui.Modal, title="Enter Additional Settings"):
    moderator_channel_id = discord.ui.TextInput(label="Moderator Channel ID", style=discord.TextStyle.short,
                                                required=True)
    moderator_role = discord.ui.TextInput(label="Moderator Role ID", style=discord.TextStyle.short,
                                          required=True)
    log_channel_id = discord.ui.TextInput(label="Log Channel ID", style=discord.TextStyle.short,
                                          required=True)

    def __init__(self, guild_id, initial_data, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild_id = guild_id
        self.initial_data = initial_data  # Contains data from the first modal

    async def on_submit(self, interaction: discord.Interaction):
        # Update the initial credentials with the new values
        self.initial_data.update({
            "moderator_channel_id": self.moderator_channel_id.value,
            "moderator_role": self.moderator_role.value,
            "log_channel_id": self.log_channel_id.value
        })

        # Path for the guild's config file
        guild_config_file = os.path.join(CONFIG_PATH, f"{self.guild_id}.json")

        # Ensure the directory exists
        os.makedirs(CONFIG_PATH, exist_ok=True)

        # Save the updated data to the guild's config file
        with open(guild_config_file, 'w') as f:
            json.dump(self.initial_data, f, indent=4)

        logger.info(f"Stored additional settings for guild {self.guild_id}")

        # Respond to the user
        await interaction.response.send_message("Additional settings have been successfully stored!",  # noqa
                                                ephemeral=True)


# Create a view for the buttons
class ConfirmView(discord.ui.View):
    def __init__(self, guild_id, bot):
        super().__init__(timeout=600)  # View timeout after 60 seconds
        self.guild_id = guild_id
        self.bot = bot

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.green)
    async def proceed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle the 'Proceed' button click."""
        # Show the VRChat credentials modal when user proceeds
        await interaction.response.send_modal(VrchatCredentialsModal(guild_id=self.guild_id)) # noqa

        logger.info(f"User {interaction.user} proceeded to input credentials for guild {self.guild_id}")
        self.stop()  # Stops the view from listening for more button clicks

    @discord.ui.button(label="Abort", style=discord.ButtonStyle.red)
    async def abort_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle the 'Abort' button click."""
        # Inform the user that the process has been canceled
        await interaction.response.send_message("Process aborted. No credentials were saved.", ephemeral=True) # noqa
        logger.info(f"User {interaction.user} aborted the process for guild {self.guild_id}")
        self.stop()  # Stops the view from listening for more button clicks

    @discord.ui.button(label="Delete config", style=discord.ButtonStyle.grey)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_config_file = os.path.join(CONFIG_PATH, f"{self.guild_id}.json")
        if os.path.exists(guild_config_file):
            with open(guild_config_file, 'r') as f:
                data = json.load(f)

            # Check if the key exists before trying to delete it
            for entry in json_keys:
                data.pop(entry, None)

            with open(guild_config_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Deleted VRChat credentials for guild {self.guild_id}")
            await interaction.response.send_message(content="VRChat credentials have been successfully deleted.")  # noqa
        else:
            # If no credentials exist, notify the user
            await interaction.response.send_message(content="No VRChat credentials found to delete.")  # noqa


# Create the cog
class VrchatApi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vrc_handler = None
        self.guild_id = None

        # Delete the temp/vrc folder if it exists
        if os.path.exists(TEMP_VRC_PATH):
            shutil.rmtree(TEMP_VRC_PATH)
            logger.info(f"Deleted folder on VRC-COG initialization: {TEMP_VRC_PATH}")

    @tasks.loop(minutes=60)
    async def my_background_task(self):
        # Ensure that the bot is logged in before running the task
        if self.vrc_handler is not None:
            # Fetch invite requests using self.vrc_handler
            invite_requests = self.vrc_handler.get_group_join_requests()

            if invite_requests:
                for request in invite_requests:
                    if self.track_invite_requests(guild_id=self.guild_id,
                                                  request_id=request['request_id'],
                                                  message_id=None):
                        user_id = request['requester_id']
                        profile_data = self.vrc_handler.get_user_profile(user_id)
                        # print(profile_data)
                        embed = discord.Embed(color=discord.Color.blue())
                        embed.title = f"{profile_data['Display Name']}"
                        embed.description = f"Requests to join the VRChat group"
                        embed.set_thumbnail(url=profile_data['Profile Thumbnail Override'])
                        embed.add_field(name="Bio", value=profile_data['Bio'], inline=False)
                        embed.add_field(name="Profile URL",
                                        value=f"[{profile_data['Display Name']}'s "
                                              f"Profile](<https://vrchat.com/home/user/{user_id}>)",
                                        inline=False)
                        channel = self.vrc_handler.moderator_channel_id
                        channel = self.bot.get_channel(int(channel))
                        # print(f"Sending invite request notification to {channel.name}") # debug
                        msg = await channel.send(embed=embed)

                        # add message to the tracked_invite_requests list
                        self.track_invite_requests(guild_id=self.guild_id,
                                                   request_id=request['request_id'],
                                                   message_id=msg.id)

                        # Pass message.id to the view
                        view = InviteRequestViewer(guild_id=self.guild_id,
                                                   vrc_handler=self.vrc_handler,
                                                   user_id=user_id,
                                                   user_name=profile_data['Display Name'],
                                                   moderator_name=None,
                                                   message_id=msg.id)

                        # Edit the message with the view
                        await msg.edit(view=view)
        else:
            logger.warning("Bot is not logged in, stopping the task.")
            self.my_background_task.stop()  # Stop the task if the bot is not logged in

    @my_background_task.before_loop
    async def before_my_background_task(self):
        await self.bot.wait_until_ready()
        logger.info("Bot is logged in, and is now checking for invites every 60 minutes.")

    @my_background_task.after_loop
    async def after_my_background_task(self):
        if self.my_background_task.is_being_cancelled():
            logger.info("Background task has been successfully stopped.")
        else:
            logger.info("Background task has finished normally.")

    @app_commands.command(name="setup_vrchat", description="Setup VRChat API for this Guild")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def setup_vrchat(self, interaction: discord.Interaction):
        """Command to set up the VRChat API by requesting user credentials."""
        guild_id = interaction.guild_id

        # Information message before showing the modal
        embed = discord.Embed(
            title="Security Notice",
            description=(
                "Your VRChat credentials will be stored **encrypted**, but please only proceed if you trust the host "
                "of this bot.\n\nFor full security, consider running the bot yourself. "
                "You can find it online at [Based A.I.O GitHub](https://github.com/minz38/Based-A.I.O)."
            ),
            color=discord.Color.yellow()
        )

        # Create a view with "Proceed" and "Abort" buttons
        view = ConfirmView(guild_id=guild_id, bot=self.bot)

        # Send the warning message with the buttons
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True) # noqa

    # Manually check for new guild join requests
    @app_commands.command(name="vrc", description="Perform Various VRChat API operations")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(operation=[app_commands.Choice(name="Check Login Status", value="check_login_status"),
                                     app_commands.Choice(name="Setup Invite Handler", value="setup_invite_handler"),
                                     app_commands.Choice(name="Log In", value="login"),
                                     app_commands.Choice(name="Log Out", value="logout"),
                                     app_commands.Choice(name="Get Invite Requests", value="get_invite_requests"),
                                     app_commands.Choice(name="Start listener", value="start_background_task"),
                                     app_commands.Choice(name="Stop listener", value="stop_background_task")])
    async def vrc(self, interaction: discord.Interaction, operation: app_commands.Choice[str]):
        """Handle VRChat API operations."""
        match operation.value:
            case "check_login_status":
                if self.vrc_handler:
                    # Add logic to check the current status using self.vrc_handler
                    await interaction.response.send_message(f"Logged in as "  # noqa
                                                            f"{self.vrc_handler.current_user.display_name}",
                                                            ephemeral=True)
                else:
                    await interaction.response.send_message("The bot is not logged in yet.", ephemeral=True)  # noqa

            case "setup_invite_handler":
                if self.vrc_handler:
                    # Call relevant invite handler logic here
                    await interaction.response.send_message("Setting up the invite handler...", ephemeral=True)  # noqa
                else:
                    await interaction.response.send_message("You need to log in first.", ephemeral=True)  # noqa

            case "login":
                # Call the login method and notify the user
                await self.vrc_bot_login(interaction)
            case "logout":
                if self.vrc_handler:
                    success = self.vrc_handler.logout()
                    if success:
                        await interaction.response.send_message("Logged out successfully.", ephemeral=True)  # noqa
                        if self.my_background_task.is_running():
                            self.my_background_task.stop()  # Stop the task if the bot is logged out
                        logger.info(f"User {interaction.user} logged out the VRC Bot & stopped the background task.")
                    else:
                        await interaction.response.send_message( # noqa
                            "Failed to log out. No active session or an error occurred.", ephemeral=True)
                else:
                    await interaction.response.send_message("You are already logged out.", ephemeral=True)  # noqa

            case "get_invite_requests":
                if self.vrc_handler:
                    await interaction.response.send_message("Fetching invite requests...", ephemeral=True)  # noqa

                    # Fetch invite requests using self.vrc_handler
                    invite_requests = self.vrc_handler.get_group_join_requests()

                    if invite_requests:
                        for request in invite_requests:
                            if self.track_invite_requests(guild_id=interaction.guild_id,
                                                          request_id=request['request_id'],
                                                          message_id=None):
                                user_id = request['requester_id']  # noqa
                                profile_data = self.vrc_handler.get_user_profile(user_id)
                                # print(profile_data)
                                embed = discord.Embed(color=discord.Color.blue())
                                embed.title = f"{profile_data['Display Name']}"
                                embed.description = f"Requests to join the VRChat group"
                                embed.set_thumbnail(url=profile_data['Profile Thumbnail Override'])
                                embed.add_field(name="Bio", value=profile_data['Bio'], inline=False)
                                embed.add_field(name="Profile URL",
                                                value=f"[{profile_data['Display Name']}'s "
                                                      f"Profile](<https://vrchat.com/home/user/{user_id}>)",
                                                inline=False)
                                guild_id: int = interaction.guild_id

                                msg: discord.Message = await interaction.followup.send(embed=embed, ephemeral=False)
                                # add message to the tracked_invite_requests list
                                self.track_invite_requests(guild_id=interaction.guild_id,
                                                           request_id=request['request_id'],
                                                           message_id=msg.id)

                                # Pass message.id to the view
                                view = InviteRequestViewer(guild_id=guild_id,
                                                           vrc_handler=self.vrc_handler,
                                                           user_id=user_id,
                                                           user_name=profile_data['Display Name'],
                                                           moderator_name=interaction.user.name,
                                                           message_id=msg.id)

                                # Edit the message with the view
                                await msg.edit(view=view)

                else:
                    await interaction.response.send_message("You need to log in first.", ephemeral=True)  # noqa

            case 'start_background_task':
                # Start the background task
                if not self.my_background_task.is_running():
                    self.my_background_task.start()
                    await interaction.response.send_message("Started the background task.")  # noqa
                else:
                    await interaction.response.send_message("The background task is already running.")  # noqa

            case 'stop_background_task':
                # Stop the background task
                if self.my_background_task.is_running():
                    logger.info("Attempting to stop the background task...")
                    self.my_background_task.stop()
                    await interaction.response.send_message("Stopped the background task.")  # noqa
                else:
                    await interaction.response.send_message("The background task is not running.")  # noqa

            case _:
                await interaction.response.send_message("Invalid operation. Please choose from the options provided.",  # noqa
                                                        ephemeral=True)

    async def vrc_bot_login(self, interaction: discord.Interaction):
        """Login the bot using VRChat API."""
        try:
            guild_id = interaction.guild_id
            self.guild_id = guild_id
            # Initialize the VrchatApiHandler
            self.vrc_handler = VrchatApiHandler(guild_id)

            # If successful, respond to the interaction
            await interaction.response.send_message(f"Logged in as {self.vrc_handler.current_user.display_name}") # noqa
            logger.info(f"VRChat API logged in for guild {guild_id}")

        except Exception as e:
            # If any error occurs during the login, notify the user
            logger.error(f"Failed to log in to VRChat API: {e}")
            await interaction.response.send_message("Failed to log in. Please check the logs for more details.", # noqa
                                                    ephemeral=True)

    @staticmethod
    def track_invite_requests(guild_id, request_id, message_id):
        # Check if the request_id has already been posted to the channel
        temp_file = f"temp/vrc/{guild_id}.json"

        if not os.path.exists("temp/vrc"):
            os.makedirs("temp/vrc")

        # Initialize temp_data
        temp_data = {}

        if os.path.exists(temp_file):
            # Load the existing data if the file exists
            with open(temp_file, "r") as f:
                temp_data = json.load(f)
        else:
            # Create the file if it doesn't exist and initialize with an empty dict
            with open(temp_file, "w") as f:
                json.dump({}, f)
                logger.info(f"Created VRC temporary file {temp_file}")

        # Now you can safely reference temp_data
        if request_id in temp_data and message_id is None:
            return False

        if request_id not in temp_data and message_id is None:
            return True

        if request_id not in temp_data and message_id is not None:
            temp_data[request_id] = message_id
            with open(temp_file, "w") as f:
                json.dump(temp_data, f, indent=4)
                logger.info(f"Updated VRC temporary file {temp_file}")
            return True
        # TODO: Add a method to edit messages if they have been responded trough VRChat instead of discord


class InviteRequestViewer(discord.ui.View):
    def __init__(self, guild_id: int, vrc_handler, user_id, user_name, moderator_name, message_id):
        super().__init__(timeout=None)
        self.vrc_handler = vrc_handler
        self.guild_id = guild_id
        self.user_id = user_id
        self.user_name = user_name
        self.moderator_name = moderator_name
        self.message_id = message_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def invite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.vrc_handler.handle_request(user_id=self.user_id,
                                           user_name=self.user_name,
                                           moderator_name=interaction.user.name,
                                           action="Accept"):

            msg = await interaction.channel.fetch_message(self.message_id)
            embed = msg.embeds[0]
            embed.colour = discord.Color.green()
            embed.set_footer(text=f"Accepted by {interaction.user.name}")
            accept_message = f"The user **{self.user_name}** has been accepted by **{interaction.user.name}**"
            await msg.edit(content=accept_message, view=None, embed=embed)

        else:
            await interaction.followup.send(content=f"Failed to accept {self.user_name}.\n"
                                                    f"Please check the logs for more details.")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.vrc_handler.handle_request(user_id=self.user_id,
                                           user_name=self.user_name,
                                           moderator_name=interaction.user.name,
                                           action="Reject"):

            msg = await interaction.channel.fetch_message(self.message_id) # noqa
            embed = msg.embeds[0]
            embed.colour = discord.Color.red()
            embed.set_footer(text=f"Rejected by {self.moderator_name}")
            reject_message = f"The user **{self.user_name}** has been rejected by **{self.moderator_name}**"
            await msg.edit(content=reject_message, view=None, embed=embed)

        else:
            await interaction.followup.send(content=f"Failed to reject {self.user_name}.\n"
                                                    f"Please check the logs for more details.")

    @discord.ui.button(label="Block & Reject", style=discord.ButtonStyle.grey)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def block_and_reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.vrc_handler.handle_request(user_id=self.user_id,
                                           user_name=self.user_name,
                                           moderator_name=interaction.user.name,
                                           action="Block"):

            msg = await interaction.channel.fetch_message(self.message_id)  # noqa
            embed = msg.embeds[0]
            embed.colour = discord.Color.red()
            embed.set_footer(text=f"Rejected & Blocked from further requests by {interaction.user.name}")
            reject_message: str = f"The user **{self.user_name}** has been rejected by **{interaction.user.name}**"
            await msg.edit(content=reject_message, view=None, embed=embed)

        else:
            await interaction.followup.send(content=f"Failed to reject {self.user_name}.\n"
                                                    f"Please check the logs for more details.")


# set up the cog
async def setup(bot):
    await bot.add_cog(VrchatApi(bot))
