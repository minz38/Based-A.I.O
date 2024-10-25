import discord
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager

logger = LoggerManager(name="StatusChanger", level="INFO", log_file="logs/StatusChanger.log").get_logger()
# push test

class PresenceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Command to change the bot's activity
    @app_commands.command(name="status", description="Change the bot's activity status.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(
        activity_type=[
            app_commands.Choice(name="Playing", value=0),
            app_commands.Choice(name="Streaming", value=1),
            app_commands.Choice(name="Listening", value=2),
            app_commands.Choice(name="Watching", value=3),
            app_commands.Choice(name="Competing", value=5),
            app_commands.Choice(name="None", value=6)
        ]
    )
    @app_commands.describe(
        activity_type="Select the type of activity.",
        activity_text="Enter the custom text for the activity."
    )
    async def activity(self, interaction: discord.Interaction, activity_type: int, activity_text: str):
        logger.info(f"user: {interaction.user.name} changed bot's activity to {activity_type} {activity_text}")

        if activity_type == 0:
            activity = discord.Game(name=activity_text)
        elif activity_type == 1:
            activity = discord.Streaming(name=activity_text, url="https://twitch.tv/your_channel")
        elif activity_type == 2:
            activity = discord.Activity(type=discord.ActivityType.listening, name=activity_text)
        elif activity_type == 3:
            activity = discord.Activity(type=discord.ActivityType.watching, name=activity_text)
        elif activity_type == 5:
            activity = discord.Activity(type=discord.ActivityType.competing, name=activity_text)
        elif activity_type == 6:
            activity = discord.Activity(type=discord.ActivityType.unknown, name=None)

        else:
            await interaction.response.send_message("Invalid activity type selected.", ephemeral=True)  # noqa
            return

        await self.bot.change_presence(activity=activity)
        await interaction.response.send_message(f"Bot activity changed to: {activity.name} {activity_text}", # noqa
                                                ephemeral=True)

        # Retrieve the AdminLog cog and use log_interaction()
        admin_log_cog = self.bot.get_cog("AdminLog")
        if admin_log_cog:
            await admin_log_cog.log_interaction(
                interaction,
                text=f"Bot activity changed to: {activity.type.name} | {activity_text}",  # noqa
                priority="info"
            )


async def setup(bot):
    await bot.add_cog(PresenceCog(bot))
