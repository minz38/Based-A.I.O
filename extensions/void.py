import json
import discord
import asyncio
import datetime
from pathlib import Path
from logger import LoggerManager
from discord import app_commands
from discord.ext import commands

logger = LoggerManager(name="Void", level="INFO", log_file="logs/Void.log").get_logger()


class VoidCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.void_channels = {}  # {guild_id: {channel_id: void_time_in_hours}}
        self.tasks = {}
        self.load_all_configs()
        self.bot.loop.create_task(self.check_voided_messages())

    # Utility function to get the config path for each guild
    @staticmethod
    def get_config_path(guild_id) -> Path:
        return Path(f"configs/guilds/{guild_id}_void.json")

    # Load all configurations on startup
    def load_all_configs(self) -> None:
        for guild in self.bot.guilds:
            self.load_guild_config(guild.id)

    # Load configuration for a specific guild
    def load_guild_config(self, guild_id) -> None:
        config_path = self.get_config_path(guild_id)
        if config_path.is_file():
            with open(config_path, "r") as file:
                config = json.load(file)
            void_channels = config.get("void_channels", {})
            self.void_channels[guild_id] = {
                int(channel_id): config['void_channels'][channel_id]
                for channel_id in void_channels
            }
        else:
            self.void_channels[guild_id] = {}
            # Create an empty config file
            self.save_void_config(guild_id)

    # Save the void configuration for a guild
    def save_void_config(self, guild_id) -> None:
        config_path = self.get_config_path(guild_id)
        config = {"void_channels": {}}

        if guild_id in self.void_channels:
            config["void_channels"] = {
                str(channel_id): void_time
                for channel_id, void_time in self.void_channels[guild_id].items()
            }

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as file:
            json.dump(config, file, indent=4)

    # Command Group for void commands
    void_group = app_commands.Group(
        name="void",
        description="Manage the void channel settings."
    )

    # Command to enable the void on a channel
    @void_group.command(
        name="enable",
        description="Enable the void in a specified channel."
    )
    @app_commands.describe(
        channel="The channel to enable the void in.",
        void_time="Time in hours after which messages are deleted (default: 24)."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def enable(self, interaction: discord.Interaction, channel: discord.TextChannel, void_time: int = 24) -> None:
        guild_id = interaction.guild_id
        channel_id = channel.id

        if void_time <= 0:
            await interaction.response.send_message(  # noqa
                "⚠️ Please provide a valid number of hours (> 0).", ephemeral=True
            )
            return

        if guild_id not in self.void_channels:
            self.void_channels[guild_id] = {}

        self.void_channels[guild_id][channel_id] = void_time
        self.save_void_config(guild_id)
        logger.info(f"Void enabled in channel {channel.name} (Guild: {interaction.guild.name}) for {void_time} hours.")

        await interaction.response.send_message(  # noqa
            f"🟢 Void enabled in {channel.mention}. Messages will be deleted after {void_time} hour(s).",
            ephemeral=True
        )

    # Command to disable the void on a channel
    @void_group.command(
        name="disable",
        description="Disable the void in a specified channel."
    )
    @app_commands.describe(
        channel="The channel to disable the void in."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def disable(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        guild_id = interaction.guild_id
        channel_id = channel.id

        if guild_id in self.void_channels and channel_id in self.void_channels[guild_id]:
            del self.void_channels[guild_id][channel_id]
            self.save_void_config(guild_id)
            logger.info(f"Void disabled in channel {channel.name} (Guild: {interaction.guild.name}).")
            await interaction.response.send_message(  # noqa
                f"🔴 Void disabled in {channel.mention}.", ephemeral=True
            )
        else:
            await interaction.response.send_message( # noqa
                "⚠️ The void is not enabled in this channel.", ephemeral=True
            )

    # Command to check the status of void channels in the guild
    @void_group.command(
        name="status",
        description="Check the void settings in this guild."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def status(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id

        if guild_id in self.void_channels and self.void_channels[guild_id]:
            message = "📄 **Void Channels:**\n"
            for channel_id, void_time in self.void_channels[guild_id].items():
                channel = self.bot.get_channel(channel_id)
                if channel:
                    message += f"🔹 {channel.mention} - Messages are deleted after {void_time} hour(s).\n"
                else:
                    message += (f"🔹 Channel ID {channel_id} (Not Found) -"
                                f" Messages are deleted after {void_time} hour(s).\n")
            await interaction.response.send_message(  # noqa
                message, ephemeral=True
            )
        else:
            await interaction.response.send_message(  # noqa
                "📄 No channels have the void enabled.", ephemeral=True
            )

    # Background task to check and delete messages in voided channels
    async def check_voided_messages(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():  # Todo: review if this is the best approach to keep the while loop alive
            try:
                current_time = discord.utils.utcnow()
                for guild_id, channels in self.void_channels.items():
                    for channel_id, void_time in channels.items():
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            # Calculate the cutoff time
                            cutoff = current_time - datetime.timedelta(hours=void_time)
                            # Fetch messages older than the cutoff
                            async for message in channel.history(limit=None, oldest_first=True):
                                if message.created_at < cutoff:
                                    if not message.pinned:
                                        try:
                                            await message.delete()
                                            await asyncio.sleep(1)  # Sleep to prevent hitting rate limits
                                        except Exception as e:
                                            logger.error(f"Error deleting message in {channel.name}: {e}")
                                    else:
                                        logger.debug(f"Skipping pinned message in {channel.name}")
                                else:
                                    # Since messages are in chronological order, we can break early
                                    break
                        else:
                            logger.warning(f"Channel ID {channel_id} not found in guild ID {guild_id}.")
                # Sleep for a while before the next check (e.g., 5 minutes)
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in check_voided_messages loop: {e}")
                await asyncio.sleep(300)

    # Ensure tasks are cancelled when the cog is unloaded
    def cog_unload(self) -> None:
        if self.tasks:
            for task in self.tasks.values():
                task.cancel()

    # Event listener to handle when a new guild is available (e.g., bot joins a new guild)
    @commands.Cog.listener()
    async def on_guild_join(self, guild) -> None:
        self.load_guild_config(guild.id)

    # Event listener to handle when the bot leaves a guild
    @commands.Cog.listener()
    async def on_guild_remove(self, guild) -> None:
        guild_id = guild.id
        if guild_id in self.void_channels:
            del self.void_channels[guild_id]
            config_path = self.get_config_path(guild_id)
            if config_path.is_file():
                config_path.unlink()
            logger.info(f"Removed void settings for guild ID {guild_id}.")

    # Event listener to handle when a new channel is created
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel) -> None:
        guild_id = channel.guild.id
        channel_id = channel.id
        if guild_id in self.void_channels and channel_id in self.void_channels[guild_id]:
            del self.void_channels[guild_id][channel_id]
            self.save_void_config(guild_id)
            logger.info(f"Removed void settings for deleted channel {channel.name} (Guild: {channel.guild.name}).")


async def setup(bot) -> None:
    await bot.add_cog(VoidCog(bot))
