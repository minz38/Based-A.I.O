import discord
import re
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager
from dependencies.twitter_handler import Tweet
from dependencies.attachment_dowloader import download_attachment_from_url as dl

logger = LoggerManager(name="Twitter Commands", level="INFO", log_file="logs/twitter.log").get_logger()

TEMP_PATH = "temp/twitter_attachments/"


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
            filename = await dl(attachment, TEMP_PATH)
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

    # @app_commands.command(name="tweet_suggest", description="Create a Tweet and vote for it")
    # @app_commands.allowed_installs(guilds=True, users=False)
    # @app_commands.guild_only()
    # async def tweet_suggest(self, interaction: discord.Interaction, text: str, attachments: str) -> None:
    #     logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
    #     await interaction.response.defer(thinking=True, ephemeral=False)  # noqa


async def setup(bot):
    await bot.add_cog(TwitterPosting(bot))
