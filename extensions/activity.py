import os
import json
import datetime
import discord
from discord.ext import commands
from discord import app_commands, Interaction
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

        # Load data for each guild | also creates null entries for each user if they don't exist
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

    @app_commands.command(name="inactivity_check", description="list inactive users.")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(days=[app_commands.Choice(name="30 days", value=30),
                                app_commands.Choice(name="60 days", value=60),
                                app_commands.Choice(name="90 days", value=90)])
    async def inactivity_check(self, interaction: discord.Interaction, days: int = 30):
        channel_counter = 0
        message_counter = 0
        past_month = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        last_message_list = {}

        # Defer the interaction to prevent timeout
        await interaction.response.defer(thinking=True)  # noqa

        try:
            for channel in interaction.guild.text_channels:  # Iterate only over text channels
                channel_counter += 1
                # Check permissions before fetching the history
                if not channel.permissions_for(interaction.guild.me).read_message_history:
                    logger.warning(f"Bot lacks 'Read Message History' in {channel.name}")
                    continue

                # Fetch channel history after the specified date
                async for message in channel.history(after=past_month):

                    # Skip messages from bots
                    if message.author.bot:
                        continue
                    message_counter += 1
                    # Log each message processed for debugging purposes
                    logger.debug(f"Message from {message.author} at {message.created_at} in {channel.name}")

                    # Track the most recent message timestamp for each user
                    if message.author.id not in last_message_list:
                        last_message_list[message.author.id] = message.created_at
                    else:
                        if message.created_at > last_message_list[message.author.id]:
                            last_message_list[message.author.id] = message.created_at

        except Exception as e:
            logger.error(f"Failed to retrieve channel history during inactivity_check: {e}")
            await interaction.response.send_message(content="Failed to retrieve channel history.")  # noqa
            return

        # Find users who haven't sent a message in the last {days} days
        inactive_users = []
        for member in interaction.guild.members:
            if member.bot:
                continue
            last_message_time = last_message_list.get(member.id)
            if not last_message_time or last_message_time < past_month:
                inactive_users.append(member)

        if inactive_users:
            # user_list = "\n".join([member.display_name for member in inactive_users])
            mention_member_list = "\n".join([f"<@{member.id}>" for member in inactive_users])
            embed = discord.Embed(title=f"List of Inactive Users in the last {days} days",
                                  description=
                                  f"""
                                  Processed **{message_counter}** in **{channel_counter}** channels and found
                                  **{len(inactive_users)}** users who haven't sent a message in the last **{days}** 
                                  days. 
                                  """)
            embed.add_field(name="Inactive Users", value=mention_member_list, inline=False)
            embed.set_footer(text=f"created by {interaction.user.name}")
            await interaction.followup.send(embed=embed)

        else:
            await interaction.followup.send(content="No inactive users found in the last 30 days.")  # noqa


# Add the COG to the bot
async def setup(bot):
    await bot.add_cog(Inactivity(bot))
