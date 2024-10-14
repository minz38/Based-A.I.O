import os
import json
import datetime
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from dateutil.relativedelta import relativedelta
from logger import LoggerManager

# Initialize the logger
logger = LoggerManager(name="Inactivity", level="INFO", log_file="logs/Inactivity.log").get_logger()


# Inactivity Bot extension inside this class
class Inactivity(commands.Cog):
    def __init__(self, bot):
        """
        Initialize the Inactivity cog with the provided bot instance.

        Parameters:
        bot (discord.ext.commands.Bot): The bot instance to which this cog will be added.

        Returns:
        None
        """
        self.bot = bot
        self.voice_channel_join_times = {}

        # Ensure the activity folder exists
        if not os.path.exists('activity'):
            os.makedirs('activity')
            logger.debug("Created activity folder")

        # Load data for each guild | also creates null entries for each user if they don't exist'
        for guild in bot.guilds:
            self.initialize_guild_activity(guild.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Listener for message events. Updates user activity in the activity log when a message is sent.

        Parameters:
        message (discord.Message): The message object that triggered the event.

        Returns:
        None
        """
        
        # Only track if the message is not from a bot and is inside a server
        if not message.author.bot and message.guild:
            self.update_user_activity(
                message.guild.id,
                message.author.id,
                {"message_count": 1}
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        Listener for voice state update events. Tracks user's voice channel activity.

        Parameters:
        member (discord.Member): The member object that triggered the event.
        before (discord.VoiceState): The voice state before the update.
        after (discord.VoiceState): The voice state after the update.

        Returns:
        None
        """
        
        if member.bot:
            return

        # User joins a voice channel
        if before.channel is None and after.channel is not None:
            # Get the guild from the after state (since they just joined)
            guild_id = after.channel.guild.id
            self.voice_channel_join_times[member.id] = datetime.datetime.now()

        # User leaves the voice channel
        elif before.channel is not None and after.channel is None:
            # Get the guild from the before state (since they just left)
            guild_id = before.channel.guild.id
            join_time = self.voice_channel_join_times.pop(member.id, None)

            if join_time:
                duration = int((datetime.datetime.now() - join_time).total_seconds())
                self.update_user_activity(
                    guild_id,
                    member.id,
                    {"voice_channel_time": duration}
                )

    @staticmethod
    def load_activity_data(guild_id):
        """Load the activity data from the JSON file."""
        file_path = f'activity/{guild_id}.json'
        if not os.path.exists(file_path):
            return {}
        with open(file_path, 'r') as f:
            return json.load(f)

    def initialize_guild_activity(self, guild_id):
        """Initialize the activity log for a guild."""
        file_path = f'activity/{guild_id}.json'

        # If the file doesn't exist, create an empty structure
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump({}, f)  # Empty dict to start

        # Load existing data
        with open(file_path, 'r') as f:
            data = json.load(f)

        # Add missing users to the JSON file
        for guild in self.bot.guilds:
            if guild.id == guild_id:
                for member in guild.members:
                    if not member.bot and str(member.id) not in data:
                        data[str(member.id)] = {
                            "year": {
                                str(datetime.datetime.now().year): {
                                    "month": {
                                        str(datetime.datetime.now().month): {
                                            "message_count": 0,
                                            "voice_channel_time": 0,
                                            "last_activity": None
                                        }
                                    }
                                }
                            }
                        }

        # Save the updated data back to the file
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        logger.debug(f"Activity log for guild {guild_id} initialized")

    @staticmethod
    def update_user_activity(guild_id, user_id, update_data):
        """
        Update the activity log for a user.

        Parameters:
        guild_id (int): The ID of the guild for which the activity log is being updated.
        user_id (int): The ID of the user whose activity log is being updated.
        update_data (dict): A dictionary containing the keys and values to be updated in the user's activity log.

        Returns:
        None

        The function reads the activity log for the specified guild and user, updates the relevant data, and saves the
        updated log back to the file.
        If the user's data is not present in the log, it initializes the user's data with default values.
        """
        file_path = f'activity/{guild_id}.json'

        with open(file_path, 'r') as f:
            data = json.load(f)

        current_year = str(datetime.datetime.now().year)
        current_month = str(datetime.datetime.now().month)

        # Initialize user data if not present
        if str(user_id) not in data:
            data[str(user_id)] = {
                "year": {
                    current_year: {
                        "month": {
                            current_month: {
                                "message_count": 0,
                                "voice_channel_time": 0,
                                "last_activity": None
                            }
                        }
                    }
                }
            }

        # Update activity data for the current year and month
        year_data = data[str(user_id)]["year"].setdefault(current_year, {"month": {}})
        month_data = year_data["month"].setdefault(current_month, {
            "message_count": 0,
            "voice_channel_time": 0,
            "last_activity": None
        })

        # Apply updates
        for key, value in update_data.items():
            if key in month_data:
                month_data[key] += value  # Increment counts
            else:
                month_data[key] = value

        # Update last activity timestamp
        month_data["last_activity"] = datetime.datetime.now().strftime('%d.%m.%Y')

        # Save the updated data back to the file
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)

    @app_commands.command(name="activity", description="Check user's activity status.")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(inactive_for=[
        app_commands.Choice(name="1 month", value=1),
        app_commands.Choice(name="2 months", value=2),
        app_commands.Choice(name="3 months", value=3),
        app_commands.Choice(name="6 months", value=6),
        app_commands.Choice(name="12 months", value=12)
    ])
    async def activity_check(self, interaction: discord.Interaction, inactive_for: int = 1):
        guild_id = interaction.guild.id
        data = self.load_activity_data(guild_id)

        current_date = datetime.datetime.now()
        active_users = []
        inactive_users = []

        # Calculate the starting point (X months ago)
        start_date = current_date - relativedelta(months=inactive_for)
        current_year = str(current_date.year)
        current_month = str(current_date.month)

        # Go through each user in the JSON data
        for user_id, activity_data in data.items():
            user = interaction.guild.get_member(int(user_id))

            if user is None or user.bot:
                continue  # Skip bots or members no longer in the guild

            last_activity_date = None
            total_messages = 0
            total_voice_time_seconds = 0

            # Track whether the user has been active in the past X months
            active_in_period = False

            # Check activity for the past X months
            for i in range(inactive_for):
                check_date = current_date - relativedelta(months=i)
                check_year = str(check_date.year)
                check_month = str(check_date.month)

                if check_year in activity_data["year"]:
                    year_data = activity_data["year"][check_year]
                    if check_month in year_data["month"]:
                        month_data = year_data["month"][check_month]
                        total_messages += month_data.get("message_count", 0)
                        total_voice_time_seconds += month_data.get("voice_channel_time", 0)
                        last_activity = month_data.get("last_activity")

                        # If the user has activity in this month, mark them as active
                        if last_activity and last_activity != "null":
                            activity_date = datetime.datetime.strptime(last_activity, '%d.%m.%Y')
                            if activity_date >= start_date:
                                last_activity_date = activity_date
                                active_in_period = True

            # Convert voice time from seconds to hours
            total_voice_time_hours = total_voice_time_seconds / 3600

            if active_in_period:
                active_users.append((user.display_name, last_activity_date, total_messages, total_voice_time_hours))
            else:
                inactive_users.append((user.display_name, total_messages, total_voice_time_hours))

        # Sort active users by last activity date (most recent first)
        active_users.sort(key=lambda x: x[1], reverse=True)

        # Sort inactive users by name (or leave unsorted if preferred)
        inactive_users.sort(key=lambda x: x[0])

        # Prepare embed to show the results
        embed = discord.Embed(
            title=f"User Activity Check (Inactive for {inactive_for} months)",
            description=f"Showing active and inactive users in the last {inactive_for} months",
            color=discord.Color.blue()
        )

        # Add top 10 active users
        if active_users:
            active_list = "\n".join([
                f"**{name}** - Last Active: {date.strftime('%d.%m.%Y')} - Messages: {messages}, Voice Time: {voice_time:.2f} hrs"
                for name, date, messages, voice_time in active_users[:10]
            ])
            embed.add_field(name="Top 10 Active Users", value=active_list, inline=False)
        else:
            embed.add_field(name="Top 10 Active Users", value="No active users found", inline=False)

        # Add top 10 inactive users
        if inactive_users:
            inactive_list = "\n".join([
                f"**{name}** - Last Active: Never - Messages: {messages}, Voice Time: {voice_time:.2f} hrs"
                for name, messages, voice_time in inactive_users[:10]
            ])
            embed.add_field(name="Top 10 Inactive Users", value=inactive_list, inline=False)
        else:
            embed.add_field(name="Top 10 Inactive Users", value="No inactive users found", inline=False)

        # Send the embed message
        await interaction.response.send_message(embed=embed)  # noqa


# Add the COG to the bot
async def setup(bot):
    await bot.add_cog(Inactivity(bot))
