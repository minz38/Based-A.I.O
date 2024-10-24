import os
import json
import datetime
import discord
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager
from typing import Any

# Initialize the logger
logger = LoggerManager(name="Inactivity", level="INFO", log_file="logs/Inactivity.log").get_logger()


class Inactivity(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.voice_channel_join_times: dict = {}
        self.active_guilds: list[int] = []

        self.excluded_roles: dict[int, list[int]] = {}  # New dictionary to store excluded roles per guild

        # Ensure the activity folder exists
        if not os.path.exists('activity'):
            os.makedirs('activity')
            logger.info("Created activity folder")

    async def cog_load(self):
        await self.load_active_guilds()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Any, before: Any, after: Any) -> None:
        if member.bot:
            return

        # Get the excluded roles for the guild
        guild_id = member.guild.id
        excluded_roles = self.excluded_roles.get(guild_id, [])

        # Check if member has any excluded roles
        if any(role.id in excluded_roles for role in member.roles):
            return  # Skip tracking for this member

        # User joins a voice channel
        if before.channel is None and after.channel is not None:
            # Get the guild from the after state (since they just joined)
            time: datetime = datetime.datetime.now()
            self.voice_channel_join_times[member.id] = time

        # User leaves the voice channel
        elif before.channel is not None and after.channel is None:
            # Get the guild from the before state (since they just left)
            join_time = self.voice_channel_join_times.pop(member.id, None)

            if join_time:
                duration = int((datetime.datetime.now() - join_time).total_seconds())
                await self.store_voice_times(guild_id=guild_id, member=member, time=duration)

    async def store_voice_times(self, guild_id: int, member: Any, time: Any) -> None:
        if guild_id in self.active_guilds:
            # File path where the activity data is stored
            file_path: str = f'activity/{guild_id}.json'

            # Load existing data from the file if it exists, or initialize an empty dictionary
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    voice_data = json.load(f)
            else:
                voice_data: dict = {}

            user_id: str = str(member.id)  # Use the user ID as a string
            date: str = datetime.datetime.now().strftime("%Y-%m")  # Get the current year and month in YYYY-MM

            # If the user doesn't have an entry in the JSON, initialize it
            if user_id not in voice_data:
                voice_data[user_id] = {}

            # If the user doesn't have an entry for the current month, initialize it
            if date not in voice_data[user_id]:
                voice_data[user_id][date] = {"voice_times": 0}

            # Add the duration to the existing time
            voice_data[user_id][date]["voice_times"] += time

            # Save the updated data back to the file
            with open(file_path, 'w') as f:
                json.dump(voice_data, f, indent=4)

    async def load_active_guilds(self):
        """Load active guilds with voice tracking enabled and their excluded roles."""
        logger.info("Loading active guilds with voice tracking enabled.")
        for file in os.listdir('configs/guilds'):
            if file.endswith('.json') and not file.startswith('gs'):
                guild_id = int(file.split('.')[0])
                with open(f'configs/guilds/{file}', 'r') as f:
                    guild_config = json.load(f)
                    # If 'voice_tracking' is in active_extensions, add the guild_id to active_guilds
                    if "voice_tracking" in guild_config.get('active_extensions', []):
                        self.active_guilds.append(guild_id)
                    # Load excluded roles
                    excluded_roles = guild_config.get('voice_excluded_roles', [])
                    self.excluded_roles[guild_id] = excluded_roles
        logger.info(f"Total active guilds loaded: {len(self.active_guilds)}")

    @app_commands.command(name="vc_tracking", description="Setup the Voicechannel Tracking feature.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(operation=[
        app_commands.Choice(name="Enable", value=1),
        app_commands.Choice(name="Disable", value=0),
        app_commands.Choice(name="Status", value=2)
    ])
    async def voice_tracking(self, interaction: discord.Interaction, operation: int) -> None:
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        admin_log_cog = interaction.client.get_cog("AdminLog")
        if admin_log_cog:
            await admin_log_cog.log_interaction(
                interaction,
                text=f"Voice Tracking {['Enabled', 'Disabled'][operation-1]} for guild: {interaction.guild.name})",
                priority="info"
            )

        match operation:

            case 1:  # Enable
                guild_id = interaction.guild.id
                if guild_id not in self.active_guilds:
                    self.active_guilds.append(guild_id)
                    # update active_extensions in the guild config file configs/guilds/{guild_id}.json
                    config_file = f'configs/guilds/{guild_id}.json'
                    if os.path.exists(config_file):
                        with open(config_file, 'r') as file:
                            guild_config = json.load(file)
                    else:
                        guild_config = {'active_extensions': []}

                    guild_config.setdefault('active_extensions', []).append('voice_tracking')
                    with open(config_file, 'w') as f:
                        json.dump(guild_config, f, indent=4)
                    logger.info(f"Voice tracking enabled for guild: {interaction.guild.name} ({guild_id})")
                    await interaction.response.send_message(content="Voice tracking enabled successfully.")
                else:
                    await interaction.response.send_message(
                        content="Voice tracking is already enabled for this guild.")
                    logger.warning(f"Voice tracking already enabled for guild: {interaction.guild.name} ({guild_id})")

            case 0:  # Disable
                guild_id = interaction.guild.id
                if guild_id in self.active_guilds:
                    self.active_guilds.remove(guild_id)
                    config_file = f'configs/guilds/{guild_id}.json'
                    if os.path.exists(config_file):
                        with open(config_file, 'r') as f:
                            guild_config = json.load(f)
                            if 'voice_tracking' in guild_config.get('active_extensions', []):
                                guild_config['active_extensions'].remove('voice_tracking')
                            with open(config_file, 'w') as file:
                                json.dump(guild_config, file, indent=4)
                    logger.info(f"Voice tracking disabled for guild: {interaction.guild.name} ({guild_id})")
                    await interaction.response.send_message(
                        content="Voice tracking disabled successfully.")
                else:
                    await interaction.response.send_message(
                        content="Voice tracking is already disabled for this guild.")
                    logger.warning(f"Voice tracking already disabled for guild: {interaction.guild.name} ({guild_id})")

            case 2:  # Status
                if int(interaction.guild_id) in self.active_guilds:
                    await interaction.response.send_message(content="Voice tracking is enabled for this guild.")
                else:
                    await interaction.response.send_message(
                        content="Voice tracking is disabled for this guild.")

            case _:
                raise ValueError("Invalid operation. Please choose 'Enable' or 'Disable'.")

    @app_commands.command(name="inactivity_check", description="List inactive users.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(days=[
        app_commands.Choice(name="30 days", value=30),
        app_commands.Choice(name="60 days", value=60),
        app_commands.Choice(name="90 days", value=90)
    ])
    async def inactivity_check(self, interaction: discord.Interaction, days: int = 30) -> None:
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}, days: {days}")
        admin_log_cog = interaction.client.get_cog("AdminLog")
        if admin_log_cog:
            await admin_log_cog.log_interaction(
                interaction,
                text=f"Inactivity Check for {days} days for guild: {interaction.guild.name}",
                priority="info"
            )

        channel_counter: int = 0
        message_counter: int = 0
        past_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        last_message_list: dict = {}
        voice_times: dict = {}

        guild = interaction.guild
        guild_id = guild.id
        excluded_roles = self.excluded_roles.get(guild_id, [])

        # Defer the interaction to prevent timeout
        await interaction.response.defer(thinking=True)

        # Load voice activity data from the JSON file for the guild
        voice_data_file: str = f'activity/{guild_id}.json'

        if os.path.isfile(voice_data_file):
            with open(voice_data_file, 'r') as f:
                voice_times = json.load(f)

        try:
            for channel in guild.text_channels:  # Iterate only over text channels
                channel_counter += 1
                # Check permissions before fetching the history
                if not channel.permissions_for(guild.me).read_message_history:
                    logger.warning(f"Bot lacks 'Read Message History' in {channel.name}")
                    continue

                # Fetch channel history after the specified date
                async for message in channel.history(after=past_date):
                    # Skip messages from bots or excluded roles
                    if message.author.bot:
                        continue
                    if any(role.id in excluded_roles for role in message.author.roles):
                        continue

                    message_counter += 1
                    # Track the most recent message timestamp for each user
                    if message.author.id not in last_message_list:
                        last_message_list[message.author.id] = message.created_at
                    else:
                        if message.created_at > last_message_list[message.author.id]:
                            last_message_list[message.author.id] = message.created_at

        except Exception as e:
            logger.error(f"Failed to retrieve channel history during inactivity_check: {e}")
            await interaction.followup.send(content="Failed to retrieve channel history.")
            return

        # Find users who haven't sent a message in the last {days} days and gather their voice times
        inactive_users = []
        for member in guild.members:
            if member.bot:
                continue
            if any(role.id in excluded_roles for role in member.roles):
                continue

            last_message_time: datetime.datetime = last_message_list.get(member.id)
            if not last_message_time or last_message_time < past_date:
                # Get the total voice time for this user over the past {days}
                total_voice_seconds: int = 0
                user_id = str(member.id)

                if user_id in voice_times:
                    # Loop through the months that are relevant for the specified days
                    for year_month, voice_data in voice_times[user_id].items():
                        year, month = map(int, year_month.split("-"))

                        # Make activity_date timezone-aware by attaching the UTC timezone
                        activity_date: datetime.datetime = datetime.datetime(year, month, 1,
                                                                             tzinfo=datetime.timezone.utc)

                        # Check if the activity date falls within the last {days}
                        if activity_date >= past_date.replace(day=1):  # Compare with the first day of the month
                            total_voice_seconds += voice_data.get("voice_times", 0)

                # Convert total voice time to hours and minutes
                hours, remainder = divmod(total_voice_seconds, 3600)
                minutes = remainder // 60

                inactive_users.append((member, hours, minutes))

        # Create the embed
        if inactive_users:
            mention_member_list: str = "\n".join([
                f"<@{member.id}> - Voice Time: {hours}h {minutes}m"
                for member, hours, minutes in inactive_users
            ])
            embed = discord.Embed(title=f"List of Inactive Users in the last {days} days",
                                  description=f"Processed **{message_counter}** messages in **{channel_counter}** "
                                              f"channels and found **{len(inactive_users)}** users who haven't sent "
                                              f"a message in the last **{days}** days.",
                                  color=discord.Color.blue())
            embed.add_field(name="Inactive Users", value=mention_member_list, inline=False)
            embed.set_footer(text=f"Created by {interaction.user.name}")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(content=f"No inactive users found in the last {days} days.")

    @app_commands.command(name="vc_tracking_exclude", description="Manage roles to exclude from activity tracking.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(action=[app_commands.Choice(name="Add", value="add"),
                                  app_commands.Choice(name="Remove", value="remove"),
                                  app_commands.Choice(name="List", value="list")])
    async def exclude_roles(self, interaction: discord.Interaction, action: str, role: discord.Role = None) -> None:
        """
        Manage roles to exclude from activity tracking.
        Actions: add, remove, list
        """
        logger.info(
            f"Command: {interaction.command.name} used by {interaction.user.name}, action: {action}, role: {role}")

        admin_log_cog = interaction.client.get_cog("AdminLog")
        role_name = role.name if role else "None"
        if admin_log_cog:
            await admin_log_cog.log_interaction(
                interaction,
                text=f"VC Tracking Exclude - {action} role: {role_name} for guild: "
                     f"{interaction.guild.name}",
                priority="info"
            )
        guild_id = interaction.guild.id

        if action.lower() == "add":
            if role is None:
                await interaction.response.send_message("Please specify a role to add to the exclusion list.")
                return
            excluded_roles = self.excluded_roles.get(guild_id, [])
            if role.id not in excluded_roles:
                excluded_roles.append(role.id)
                self.excluded_roles[guild_id] = excluded_roles
                # Save to guild config
                await self.update_guild_config_excluded_roles(guild_id, excluded_roles)
                await interaction.response.send_message(f"Role {role.name} added to the exclusion list.")
            else:
                await interaction.response.send_message(f"Role {role.name} is already in the exclusion list.")

        elif action.lower() == "remove":
            if role is None:
                await interaction.response.send_message("Please specify a role to remove from the exclusion list.")
                return
            excluded_roles = self.excluded_roles.get(guild_id, [])
            if role.id in excluded_roles:
                excluded_roles.remove(role.id)
                self.excluded_roles[guild_id] = excluded_roles
                # Save to guild config
                await self.update_guild_config_excluded_roles(guild_id, excluded_roles)
                await interaction.response.send_message(f"Role {role.name} removed from the exclusion list.")
            else:
                await interaction.response.send_message(f"Role {role.name} is not in the exclusion list.")

        elif action.lower() == "list":
            excluded_roles = self.excluded_roles.get(guild_id, [])
            if excluded_roles:
                role_mentions = [interaction.guild.get_role(role_id).mention for role_id in excluded_roles if
                                 interaction.guild.get_role(role_id)]
                roles_list = "\n".join(role_mentions)
                await interaction.response.send_message(f"Excluded roles:\n{roles_list}")
            else:
                await interaction.response.send_message("No roles are currently excluded from tracking.")

        else:
            await interaction.response.send_message("Invalid action. Please use 'add', 'remove', or 'list'.")

    async def update_guild_config_excluded_roles(self, guild_id: int, excluded_roles: list[int]) -> None:
        """Update the guild's config file with the new list of excluded roles."""
        config_file = f'configs/guilds/{guild_id}.json'
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                guild_config = json.load(f)
        else:
            guild_config = {}

        guild_config['voice_excluded_roles'] = excluded_roles
        with open(config_file, 'w') as f:
            json.dump(guild_config, f, indent=4)


# Add the COG to the bot
async def setup(bot) -> None:
    await bot.add_cog(Inactivity(bot))
