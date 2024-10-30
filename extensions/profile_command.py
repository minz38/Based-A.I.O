import discord
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager
from datetime import datetime

logger = LoggerManager(name="ProfileFetch", level="INFO", log_file="logs/bot.log").get_logger()
dateFormat = "%d.%m.%Y"  # Customize this as needed


class ProfileFetch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='profile',
                          description='Fetch a user\'s profile information')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, private_channels=False, dms=False)
    async def profile(self, interaction: discord.Interaction,
                      user_id: str = None) -> None:

        logger.info(f"Fetch profile for user ID: {user_id} by {interaction.user.name}")

        admin_log_cog = interaction.client.get_cog("AdminLog")
        if admin_log_cog:
            await admin_log_cog.log_interaction(interaction=interaction,
                                                priority="info",
                                                text=f"on user {user_id}")
        if user_id is not None:
            # Fetch the member object from the guild
            member = interaction.guild.get_member(int(user_id))

            if member is None:
                await interaction.response.send_message(f"User with ID {user_id} not found in this guild.",  # noqa
                                                        ephemeral=True)
                return

            # Fetch the global profile picture URL and the server-specific avatar
            global_avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
            server_avatar_url = member.display_avatar.url  # This will fetch the server-specific avatar

            # Discord profile link
            profile_link = f"https://discord.com/users/{member.id}"

            # Mapping of status to corresponding emoji
            status_emojis = {
                "online": "🟢",
                "idle": "🟠",
                "dnd": "🔴",
                "offline": "⚫"
            }

            # Get the emoji for the user's status
            status_emoji = status_emojis.get(member.status.name, "⚫")
            usr_status = f"{status_emoji} {member.status.name.capitalize()}"

            # Fetch custom status if available
            custom_status = None
            for activity in member.activities:
                if activity.type == discord.ActivityType.custom:
                    custom_status = activity.name or activity.state
                    break

            # User information: Discord date joined, Member of this server since, current Roles on this server
            usr_discord_created = member.created_at.strftime(dateFormat)
            usr_guild_joined = member.joined_at.strftime(dateFormat)
            usr_roles = ", ".join([f"`{role.name}`" for role in member.roles])

            userinfo = f"Nickname: {member.nick}\n" \
                       f"Discord Created: {usr_discord_created}\n" \
                       f"Server Joined: {usr_guild_joined}\n" \
                       f"Current Roles: ||{usr_roles}||\n" \
                       f"User Status: {usr_status}\n"

            if custom_status:
                userinfo += f"Custom Status: {custom_status}\n"

            # Create an embed to display the profile information
            embed0 = discord.Embed(title=f"{member.name}'s Profile", url=profile_link, color=discord.Color.blue())
            embed0.add_field(name="Username", value=f"{member}", inline=True)
            embed0.add_field(name="User ID", value=f"{member.id}", inline=True)
            embed0.add_field(name="User Information", value=userinfo, inline=False)

            # Add images as fields to the embed
            embed0.add_field(name="Server Avatar", value=f"[Click Here]({server_avatar_url})", inline=True)
            embed0.add_field(name="Global Avatar", value=f"[Click Here]({global_avatar_url})", inline=True)

            # Set the server-specific avatar as the thumbnail and the global avatar as the embed image
            embed0.set_thumbnail(url=server_avatar_url)  # Display the server-specific avatar as the thumbnail

            # Create the first embed for the server-specific avatar
            embed1 = discord.Embed(title=f"{member.name}'s Server Avatar", url=profile_link,
                                   color=discord.Color.blue())
            embed1.set_image(url=server_avatar_url)  # Display the server-specific avatar

            # Create the second embed for the global avatar
            embed2 = discord.Embed(title=f"{member.name}'s Global Avatar", url=profile_link,
                                   color=discord.Color.green())
            embed2.set_image(url=global_avatar_url)  # Display the global avatar

            # Respond with both embeds
            await interaction.response.send_message(embeds=[embed0, embed1, embed2])
            logger.info(f"Sent profile pictures for user ID: {user_id}")
        else:
            await interaction.response.send_message("Something went wrong.",
                                                    ephemeral=True)


async def setup(bot):
    await bot.add_cog(ProfileFetch(bot))
