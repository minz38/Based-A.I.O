import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from logger import LoggerManager
import dependencies.encryption_handler as encryption_handler
from extensions.vrcapi.vrc_api import VrchatApiHandler

# Initialize the logger
logger = LoggerManager(name="VRC-API", level="INFO", log_file="logs/vrc-api.log").get_logger()

# Define the path for guild configuration
CONFIG_PATH = "configs/guilds"

# Load the encryption key from the config
key = encryption_handler.load_key_from_config()

json_keys = ["vrc_username", "vrc_password", "vrc_totp", "vrc_group_id", "moderator_channel_id",
                        "moderator_role", "log_channel_id"]


# Create a Modal class for the form
class VrchatCredentialsModal(discord.ui.Modal, title="Enter VRChat Credentials"):
    vrc_username = discord.ui.TextInput(label="VRChat Username", style=discord.TextStyle.short, required=True)
    vrc_password = discord.ui.TextInput(label="VRChat Password", style=discord.TextStyle.short, required=True)
    vrc_totp = discord.ui.TextInput(label="TOTP Secret", style=discord.TextStyle.short, required=True)
    vrc_group_id = discord.ui.TextInput(label="VRChat Group ID", style=discord.TextStyle.short, required=True)

    def __init__(self, guild_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        # Encrypt the password and TOTP secret using the encryption handler
        encrypted_password = encryption_handler.encrypt(self.vrc_password.value, key)
        encrypted_totp = encryption_handler.encrypt(self.vrc_totp.value, key)

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
        await interaction.response.defer(ephemeral=True)

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
        await interaction.response.send_modal(AdditionalSettingsModal(guild_id=self.guild_id,
                                                                      initial_data=self.initial_data))


class AdditionalSettingsModal(discord.ui.Modal, title="Enter Additional Settings"):
    moderator_channel_id = discord.ui.TextInput(label="Moderator Channel ID",style=discord.TextStyle.short,
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
        await interaction.response.send_message("Additional settings have been successfully stored!", ephemeral=True)


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
            await interaction.response.send_message(content="VRChat credentials have been successfully deleted.")
        else:
            # If no credentials exist, notify the user
            await interaction.response.send_message(content="No VRChat credentials found to delete.")


# Create the cog
class VrchatApi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_vrchat", description="Setup VRChat API for this Guild")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @discord.app_commands.default_permissions(manage_guild=True)
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
    @app_commands.command(name="vrc", description="Perform Various VRChat API opperations")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def vrc(self, interaction: discord.Interaction, operation: str):
        if operation == "initialize class":
            vrc = VrchatApiHandler(interaction.guild_id)
            await interaction.response.send_message(f"VRChat API initialized for guild {vrc.vrc_group_id} "
                                                    f"{vrc.vrc_username}.")


# set up the cog
async def setup(bot):
    await bot.add_cog(VrchatApi(bot))
