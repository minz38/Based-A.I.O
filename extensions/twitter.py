import os
import json
import discord
from discord import app_commands
from discord.ext import tasks, commands
import tweepy
import dependencies.encryption_handler as encryption_handler

config_path = "configs/guilds/"

encryption_key = encryption_handler.load_key_from_config()

twitter_keys = ["twitter_consumer_key",
                "twitter_consumer_secret",
                "twitter_access_token",
                "twitter_access_token_secret",
                "twitter_user_id",
                "twitter_report_channel_id"]


class TwitterFetcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="twitter", description="Perform various operations using Twitter API.")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(operation=[app_commands.Choice(name="Setup", value="twitter_setup"),
                                     app_commands.Choice(name="Start", value="start_twitter_event")])
    async def twitter_command(self, interaction: discord.Interaction, operation: app_commands.Choice[str]):

        match operation.value:
            case "twitter_setup":
                guild_id = interaction.guild_id

                # Information message before showing the modal
                embed = discord.Embed(
                    title="Security Notice",
                    description=(
                        "Your Twitter credentials will be stored **encrypted**, "
                        "but please only proceed if you trust the host "
                        "of this bot.\n\nFor full security, consider running the bot yourself. "
                        "You can find it online at [Based A.I.O GitHub](https://github.com/minz38/Based-A.I.O)."
                    ),
                    color=discord.Color.yellow()
                )

                # Create a view with "Proceed" and "Abort" buttons
                view = ConfirmView(guild_id=guild_id, bot=self.bot)

                # Send the warning message with the buttons
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)  # noqa
                pass

            case "start_twitter_event":
                with open(os.path.join(config_path, f"{interaction.guild_id}.json"), 'r') as f:
                    guild_config = json.load(f)
                pass


# modal to enter Twitter API credentials and store them into the guild's config file
# required fields: consumer_key, consumer_secret, access_token, access_token_secret
# second modal twitter_user_id, discord_report_channel
class TwitterCredentialsModal(discord.ui.Modal, title="Enter Twitter API Credentials"):
    def __init__(self, guild_id,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild_id = guild_id

    consumer_key = discord.ui.TextInput(label="Consumer key",
                                        style=discord.TextStyle.short,
                                        required=True)
    consumer_secret = discord.ui.TextInput(label="Consumer Secret",
                                           style=discord.TextStyle.short,
                                           required=True)
    access_token = discord.ui.TextInput(label="Access Token",
                                        style=discord.TextStyle.short,
                                        required=True)
    access_token_secret = discord.ui.TextInput(label="Access Token Secret",
                                               style=discord.TextStyle.short,
                                               required=True)

    async def on_submit(self, interaction: discord.Interaction):
        with open(os.path.join(config_path, f"{self.guild_id}.json"), 'r') as f:
            guild_config = json.load(f)

        encrypted_consumer_secret = encryption_handler.encrypt(self.consumer_secret.value, encryption_key)
        encrypted_access_token_secret = encryption_handler.encrypt(self.access_token_secret.value, encryption_key)
        credentials = {
            "twitter_consumer_key": self.consumer_key.value,
            "twitter_consumer_secret": encrypted_consumer_secret,
            "twitter_access_token": self.access_token.value,
            "twitter_access_token_secret": encrypted_access_token_secret,
        }

        # append or overwrite the current guild config keys
        guild_config.update(credentials)

        # save the updated guild config back to the file
        with open(os.path.join(config_path, f"{self.guild_id}.json"), 'w') as f:
            json.dump(guild_config, f, indent=4)

        view = NextStep(guild_id=self.guild_id)

        # Send a success message to the user
        await interaction.response.send_message(content="Twitter API credentials saved successfully!", view=view) # noqa


class SetupModalStepTwo(discord.ui.Modal, title="Setup Step 2"):
    def __init__(self, guild_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild_id = guild_id

    user_id = discord.ui.TextInput(label="Twitter User ID",
                                   style=discord.TextStyle.short,
                                   required=True)
    report_channel_id = discord.ui.TextInput(label="Discord Report Channel ID",
                                             style=discord.TextStyle.short,
                                             required=True)

    async def on_submit(self, interaction: discord.Interaction):
        with open(os.path.join(config_path, f"{self.guild_id}.json"), 'r') as f:
            guild_config = json.load(f)

        credentials = {
            "twitter_user_id": self.user_id.value,
            "twitter_report_channel_id": self.report_channel_id.value,
        }

        # append or overwrite the current guild config keys
        guild_config.update(credentials)

        # save the updated guild config back to the file
        with open(os.path.join(config_path, f"{self.guild_id}.json"), 'w') as f:
            json.dump(guild_config, f, indent=4)

        # Send a success message to the user
        await interaction.response.send_message("Twitter API credentials saved successfully!") # noqa


# confirm view
class ConfirmView(discord.ui.View):
    def __init__(self, guild_id, bot):
        super().__init__(timeout=600)
        self.guild_id = guild_id
        self.bot = bot

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TwitterCredentialsModal(guild_id=self.guild_id)
        await interaction.response.send_modal(modal) # noqa

    @discord.ui.button(label="Abort", style=discord.ButtonStyle.red)
    async def abort_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Twitter API setup aborted.") # noqa
        self.stop()  # Stops the view from listening for more button clicks

    @discord.ui.button(label="Delete Config", style=discord.ButtonStyle.grey)
    async def delete_config_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild_config_file = os.path.join(config_path, f"{self.guild_id}.json")
        if os.path.exists(guild_config_file):
            with open(guild_config_file, 'r') as f:
                guild_config = json.load(f)

            for entry in twitter_keys:
                guild_config.pop(entry, None)

            # save the updated guild config back to the file
            with open(guild_config_file, 'w') as f:
                json.dump(guild_config, f, indent=4)

            # Send a success message to the user
            await interaction.response.send_message("Twitter API credentials and configuration deleted successfully!") # noqa
            self.stop()  # Stops the view from listening for


class NextStep(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=600)
        self.guild_id = guild_id

    @discord.ui.button(label="Next", style=discord.ButtonStyle.green)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # send second modal
        modal = SetupModalStepTwo(guild_id=self.guild_id)
        await interaction.response.send_modal(modal)  # noqa
        self.stop()  # Stops the view from listening for more button clicks


class SetupModal(discord.ui.Modal, title="Setup Twitter Event"):
    def __init__(self, guild_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild_id = guild_id

    event_name = discord.ui.TextInput(label="Event Name",
                                      style=discord.TextStyle.short,
                                      required=True)
    event_description = discord.ui.TextInput(label="Event Description",
                                             style=discord.TextStyle.short,
                                             required=True)
    event_date = discord.ui.TextInput(label="Event Date (YYYY-MM-DD)",
                                      style=discord.TextStyle.short,
                                      required=True)


class TweepyFetcher(commands.Cog):
    def __init__(self, bot, guild_id):
        self.bot = bot
        self.guild_id = guild_id

        with open(os.path.join(config_path, f"{guild_id}.json"), 'r') as f:
            self.config = json.load(f)


# Add the cog to the bot
async def setup(bot):
    await bot.add_cog(TwitterFetcher(bot))
