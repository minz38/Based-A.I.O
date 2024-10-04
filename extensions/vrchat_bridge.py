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

        # Path for the guild's config file
        guild_config_file = os.path.join(CONFIG_PATH, f"{self.guild_id}.json")

        # Ensure the directory exists
        os.makedirs(CONFIG_PATH, exist_ok=True)

        # Load existing data if the file exists
        if os.path.exists(guild_config_file):
            with open(guild_config_file, 'r') as f:
                data = json.load(f)
        else:
            data = {}

        # Store the VRChat credentials in the guild's config file
        data.update(credentials)

        # Save the updated data to the guild's config file
        with open(guild_config_file, 'w') as f:
            json.dump(data, f, indent=4)

        logger.info(f"Stored VRChat credentials for guild {self.guild_id}")

        # Respond to the user
        await interaction.response.send_message("VRChat credentials have been successfully stored!", ephemeral=True) # noqa


# Create a view for the buttons
class ConfirmView(discord.ui.View):
    def __init__(self, guild_id, bot):
        super().__init__(timeout=120)  # View timeout after 60 seconds
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
            if data.get("vrc_username"):
                del data["vrc_username"]
            if data.get("vrc_password"):
                del data["vrc_password"]
            if data.get("vrc_totp"):
                del data["vrc_totp"]
            if data.get("vrc_group_id"):
                del data["vrc_group_id"]

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


# set up the cog
async def setup(bot):
    await bot.add_cog(VrchatApi(bot))
