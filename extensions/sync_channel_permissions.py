import discord
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager

logger = LoggerManager(name="Sync", level="INFO", log_file="logs/sync.log").get_logger()


class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='sync', description='Sync channel permissions with the channels Category')
    @app_commands.guild_only()
    async def sync_channels(self, interaction: discord.Interaction) -> None:
        # Retrieve the AdminLog cog and use log_interaction()
        admin_log_cog = self.bot.get_cog("AdminLog")
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        channel: discord.TextChannel = interaction.channel

        if not channel.category or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(  # noqa
                "This channel doesn't belong to a category.",
                ephemeral=True
            )
            logger.error(f"Channel {channel.mention} doesn't belong to a category.")
            return

        try:
            await channel.edit(sync_permissions=True)
            await interaction.response.send_message("Channel permissions synchronized with the category.",  # noqa
                                                    ephemeral=True)
            logger.info(f"Synced: Channel {channel.mention}  with Category {channel.category.name}")

            if admin_log_cog:
                await admin_log_cog.log_interaction(
                    interaction,
                    text=f"Synced: Channel {interaction.channel.mention}  with Category "
                         f"{interaction.channel.category.mention}",
                    priority="info"
                )
        except Exception as e:
            await interaction.response.send_message(  # noqa
                "Failed to sync channel permissions with the category.",
                ephemeral=True
            )
            logger.error(f"Failed to sync: Channel {channel.mention} with Category {channel.category.name} - {e}")


async def setup(bot):
    await bot.add_cog(Sync(bot))
