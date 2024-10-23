import os
import json
import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from dependencies.google_sheets_handler import GoogleSheetHandler
import dependencies.encryption_handler as encryption_handler
from logger import LoggerManager

logger = LoggerManager(name="QuestionHandler", level="INFO", log_file="logs/QuestionHandler.log").get_logger()

key: bytes = encryption_handler.load_key_from_config()


# NOTE: FFMPEG and FFPROBE needs to be installed in the root directory of the bot as well as in the
# dependencies directory

# TODO: Add admin-log outputs

# create a class and a slash command for the cog


class QuestionHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="webapp",
                          description="Handle pull & push of question between the google sheet and the CDN")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(operation=[app_commands.Choice(name="Pull & Push", value="pull_and_push"),
                                     app_commands.Choice(name="setup", value="setup")])
    async def webapp(self, interaction: discord.Interaction, operation: app_commands.Choice[str]) -> None:
        # load the guild config file
        logger.info(
            f"Command: {interaction.command.name} with option: {operation.value} used by {interaction.user.name}")

        match operation.value:
            # case "pull":
            #     try:
            #         pull_from_spreadsheet(spreadsheet_id, filename)
            #         await message.edit(
            #             content="✅ Questions pulled successfully!")
            #     except Exception as e:
            #         logger.error(f"Could not pull questions from spreadsheet: {e}")
            #         await message.edit(content="Could not pull questions from spreadsheet.")

            # case "push"
            #     try:
            #         file = discord.File(f'{filename}.zip')
            #         # Send the file
            #         await message.edit(content="✅ All files have been uploaded to the CDN")
            #     except Exception as e:
            #         logger.error(f"Could not send file to CDN: {e}")
            #         await message.edit(content="Could not send file to CDN.")

            # case "zip":
            #     try:
            #         # check if zip file exists
            #         if os.path.exists(f'{filename}.zip'):
            #             file = discord.File(f'{filename}.zip')
            #             # Send the file
            #             logger.info(f"Zip file exists, sending it to Discord.")
            #             await message.edit(content="✅ Zip Successfully created:", file=file)
            #
            #         else:
            #             logger.error(f"Zip file does not exist.")
            #             await message.edit(content="No zip file found. Execute /webapp pull first.")
            #
            #     except Exception as e:
            #         logger.error(f"Could not send file to Discord: {e}")
            #         await message.edit(content="Could not send file to Discord.")

            case "pull_and_push":
                with open(f'configs/guilds/{interaction.guild_id}.json', 'r') as config_file:
                    config = json.load(config_file)
                keys: list[str] = ["gs_id", "gs_worksheet_name", "gs_credentials_file", "sftp_output_path", "cdn_url",
                                   "cdn_port", "cdn_user", "cdn_password", "cdn_file_path"]

                if any(k not in config for k in keys):
                    return await interaction.response.send_message(
                        content="The Guild Config file is missing or incomplete.\n"
                                "Please setup the webapp handler with `/webapp setup`."
                    )

                else:
                    # Send the initial response
                    await interaction.response.send_message(
                        content=f"Processing {operation.value}...\nLean back and get a coffee ☕️"
                    )

                    # Retrieve the original response message
                    message = await interaction.original_response()

                    try:
                        gs = GoogleSheetHandler(interaction.guild_id)

                        # Run pull_from_spreadsheet in a thread
                        questions = await asyncio.to_thread(gs.pull_from_spreadsheet)

                        if questions:
                            await message.edit(content="✅ Step 1/2 successfully... Uploading all files...")

                            # Run process_all in a thread
                            result = await asyncio.to_thread(gs.process_all)

                            if result:
                                await message.edit(content="✅ Step 2/2 successfully... "
                                                           "All files have been processed and uploaded to the CDN")
                            else:
                                await message.edit(content="Could not process all files.")
                        else:
                            await message.edit(content="No questions were pulled from the spreadsheet.")
                    except Exception as e:
                        logger.error(f"Could not pull & push questions: {e}")
                        await message.edit(content="Could not process all files.")

            case "setup":
                embed = discord.Embed(
                    title="Security Notice",
                    description=(
                        "Your credentials will be stored **encrypted**, but please only proceed if you trust the host "
                        "of this bot.\n\nFor full security, consider running the bot yourself. "
                        "You can find it online at [Based A.I.O GitHub](https://github.com/minz38/Based-A.I.O)."
                    ),
                    color=discord.Color.yellow()
                )

                # Create a view with "Proceed" and "Abort" buttons
                view = ConfirmView(interaction)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)  # noqa

            case _:
                await interaction.response.send_message("Invalid operation.")  # noqa
                logger.error(f"Invalid operation: {operation.value}")


class SetupModalStep1(discord.ui.Modal, title="Setup Webapp Handler"):
    gs_credentials_file = discord.ui.TextInput(
        label="Google Sheets Credentials JSON",
        style=discord.TextStyle.short,
        required=True,
        placeholder='{json data with brackets}'
    )

    gs_id = discord.ui.TextInput(
        label="Google Sheet ID",
        style=discord.TextStyle.short,
        required=True,
        default='1SPU_HOQypJbNYU_cDYKYC313YtvQIKrP0xZKEWHh4_s',
        placeholder='1SPU_HOQypJbNYU_cDYKYC313YtvQIKrP0xZKEWHh4_s'
    )

    gs_worksheet_name = discord.ui.TextInput(
        label="Google Sheets Worksheet Name",
        style=discord.TextStyle.short,
        required=True,
        default='0001',
        placeholder='0001'
    )
    sftp_output_path = discord.ui.TextInput(
        label="SFTP Output Path",
        style=discord.TextStyle.short,
        required=True,
        default="/home/administrator/basedfiles/",
        placeholder='/home/administrator/basedfiles/'
    )

    def __init__(self, interaction: discord.Interaction) -> None:
        super().__init__(title=self.title, timeout=600)
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction) -> None:
        gs_credentials_file = self.gs_credentials_file.value
        # overwrite the file if it already exists
        with open(f'configs/guilds/gs_credentials-{interaction.guild_id}.json', 'w') as f:
            json.dump(json.loads(gs_credentials_file), f)
            logger.info(f"Google Sheets Credentials saved for guild: {interaction.guild.name} ({interaction.guild.id})")

        with open(f'configs/guilds/{interaction.guild_id}.json', 'r') as x:
            config = json.load(x)

        gs_data = {
            "gs_id": self.gs_id.value,
            "gs_worksheet_name": self.gs_worksheet_name.value,
            "gs_credentials_file": f'configs/guilds/gs_credentials-{interaction.guild_id}.json',
            "sftp_output_path": self.sftp_output_path.value
        }
        # add or replace the keys inside the guild config
        config.update(gs_data)

        with open(f'configs/guilds/{interaction.guild_id}.json', 'w') as y:
            json.dump(config, y, indent=4)

        await interaction.response.send_message(content="Webapp handler setup successfully.\n"
                                                        "Please proceed to setup the CDN handler.", ephemeral=True)


class SetupModalStep2(discord.ui.Modal, title="Setup CDN Handler"):
    cdn_url = discord.ui.TextInput(
        label="CDN URL",
        style=discord.TextStyle.short,
        required=True,
        placeholder='cdn.killua.de'
    )

    cdn_port = discord.ui.TextInput(
        label="CDN Port",
        style=discord.TextStyle.short,
        required=True,
        placeholder='22'
    )

    cdn_user = discord.ui.TextInput(
        label="CDN User",
        style=discord.TextStyle.short,
        required=True
    )

    cdn_password = discord.ui.TextInput(
        label="CDN Password",
        style=discord.TextStyle.short,
        required=True
    )

    cdn_file_path = discord.ui.TextInput(
        label="CDN File Path",
        style=discord.TextStyle.short,
        required=True,
        placeholder='http://cdn.killua.de/'
    )

    def __init__(self, interaction: discord.Interaction) -> None:
        super().__init__(title=self.title, timeout=600)
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cdn_url = self.cdn_url.value
        cdn_port = self.cdn_port.value
        cdn_user = self.cdn_user.value
        cdn_password = self.cdn_password.value
        cdn_file_path = self.cdn_file_path.value

        with open(f'configs/guilds/{interaction.guild_id}.json', 'r') as x:
            config = json.load(x)

        cdn_data = {
            "cdn_url": cdn_url,
            "cdn_port": cdn_port,
            "cdn_user": encryption_handler.encrypt(cdn_user, key),
            "cdn_password": encryption_handler.encrypt(cdn_password, key),
            "cdn_file_path": cdn_file_path
        }

        # add or replace the keys inside the guild config
        config.update(cdn_data)

        with open(f'configs/guilds/{interaction.guild_id}.json', 'w') as y:
            json.dump(config, y, indent=4)

        await interaction.response.send_message(content="CDN handler setup successfully.", ephemeral=True)


class ConfirmView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction) -> None:
        super().__init__(timeout=600)

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.green)
    async def proceed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle the 'Proceed' button click."""
        # Show the VRChat credentials modal when user proceeds
        await interaction.response.send_modal(SetupModalStep1(interaction))
        logger.info(f"User {interaction.user} started the process for guild {interaction.guild.name}")
        self.stop()  # Stops the view from listening for more button clicks

    @discord.ui.button(label="Abort", style=discord.ButtonStyle.red)
    async def abort_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle the 'Abort' button click."""
        # Inform the user that the process has been canceled
        await interaction.response.send_message("Process aborted. No credentials were saved.", ephemeral=True)  # noqa
        logger.info(f"User {interaction.user} aborted the process for guild {interaction.guild.name}")
        self.stop()  # Stops the view from listening for more button clicks

    @discord.ui.button(label="CDN Setup", style=discord.ButtonStyle.gray)
    async def setup_cdn_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetupModalStep2(interaction))
        logger.info(f"User {interaction.user} started the CDN setup process for guild {interaction.guild.name}")
        self.stop()


async def setup(bot):
    await bot.add_cog(QuestionHandler(bot))
