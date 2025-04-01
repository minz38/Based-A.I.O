import discord
import re
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager
from dependencies.twitter_handler import Tweet

logger = LoggerManager(name="Twitter Commands", level="INFO", log_file="logs/twitter.log").get_logger()


class TwitterPosting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.x = Tweet()

    @app_commands.command(name="tweet_create", description="create Twitter posts")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.guild_only()
    async def tweet_create(self, interaction: discord.Interaction, text: str, attachments: bool = False) -> None:
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        msg, status = self.x.post_tweet(f"{text}")
        if status:
            await interaction.response.send_message(msg)  # noqa

        if not status:
            await interaction.response.send_message(msg)  # noqa

    @app_commands.command(name="tweet_delete", description="delete a Twitter posts")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.guild_only()
    async def tweet_delete(self, interaction: discord.Interaction, tweet: str | int) -> None:
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        try:
            tweet_id: int = int(re.findall(r'\d+', tweet)[0])

        except IndexError:
            await interaction.response.send_message("Invalid tweet ID.")  # noqa
            return

        status = self.x.delete_tweet(tweet_id)
        msg = "Tweet deleted successfully." if status else "Failed to delete tweet."
        if status:
            await interaction.response.send_message(msg)  # noqa

        if not status:
            await interaction.response.send_message(msg)  # noqa


async def setup(bot):
    await bot.add_cog(TwitterPosting(bot))
