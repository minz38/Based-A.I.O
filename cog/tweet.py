import re
from os import getenv
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dep.logger import LoggerManager

from dep.attachment_dowloader import download_attachment_from_url as dl
from dep.config_handler import DATA_PATH
from dep.twitter_handler import Tweet

logger = LoggerManager(name="Twitter Commands", level="INFO", log_name="twitter").get_logger()

TEMP_PATH: Path = DATA_PATH / getenv("TEMP_FOLDER_NAME","temp")


class TwitterPosting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.x = Tweet()

    @app_commands.command(name="tweet_create", description="create Twitter posts")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.guild_only()
    async def tweet_create(self, interaction: discord.Interaction, text: str, attachments: str | None = None) -> None:
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        await interaction.response.defer(thinking=True, ephemeral=False)  # noqa
        f = attachments.split() if attachments else []
        twitter_attachments = []

        for attachment in f:
            filename: Path = await dl(attachment, TEMP_PATH)
            twitter_attachments.append(filename)

        msg, status = self.x.post_tweet(message=f"{text}",
                                        attachments=twitter_attachments if twitter_attachments else None)

        if status and msg:
            username = self.x.get_username()
            message = f"Tweet created! \nhttps://vxtwitter.com/{username}/status/{msg.data['id']}"
            await interaction.followup.send(message)

        if not status:
            await interaction.followup.send(f"something went wrong: E-4489")  # noqa

    @app_commands.command(name="tweet_delete", description="delete a Twitter posts")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.guild_only()
    async def tweet_delete(self, interaction: discord.Interaction, tweet: str) -> None:
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        await interaction.response.defer(thinking=True, ephemeral=False)  # noqa
        try:
            tweet_id: int = int(re.findall(r'\d+', tweet)[0])

        except IndexError:
            await interaction.response.send_message("Invalid tweet ID.")  # noqa
            return

        status = self.x.delete_tweet(tweet_id)
        # TODO Rework below, the api might not return any information during a delete request and it succeeds
        #  even if the tweet does not exist.
        msg = "Tweet deleted successfully." if status else "Failed to delete tweet."
        if status:
            await interaction.followup.send(msg, ephemeral=False)  # noqa

        if not status:
            await interaction.followup.send(msg, ephemeral=False)  # noqa

async def setup(bot):
    await bot.add_cog(TwitterPosting(bot))
