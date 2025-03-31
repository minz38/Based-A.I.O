import discord
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager
from dependencies.twitter_handler import Tweet

logger = LoggerManager(name="Twitter Commands", level="INFO", log_file="logs/twitter.log").get_logger()


class TwitterPosting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.x = Tweet()

    @app_commands.command(name="tweet", description="create & delete Twitter posts")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.guild_only()
    async def tweet(self, interaction: discord.Interaction, text: str):
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        msg, status = self.x.post_tweet(f"{text}")
        if status:
            await interaction.response.send_message(msg)

        if not status:
            await interaction.response.send_message(msg)


async def setup(bot):
    await bot.add_cog(TwitterPosting(bot))
