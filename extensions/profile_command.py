import discord
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager
from bot import bot as shadow_bot

logger = LoggerManager(name="ProfileFetch", level="INFO", log_file="logs/bot.log").get_logger()
dateFormat = "%d.%m.%Y"  # Customize this as needed


def create_profile_embeds(member: discord.Member) -> list[discord.Embed]:
    """
    Creates a list of embeds containing the user's profile information.
    """
    # Fetch avatar URLs
    global_avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    server_avatar_url = member.display_avatar.url
    profile_link = f"https://discord.com/users/{member.id}"

    # Determine user status with emoji
    status_emojis = {
        "online": "🟢",
        "idle": "🟠",
        "dnd": "🔴",
        "offline": "⚫"
    }
    status_emoji = status_emojis.get(member.status.name, "⚫")
    usr_status = f"{status_emoji} {member.status.name.capitalize()}"

    # Look for a custom status if available
    custom_status = None
    for activity in member.activities:
        if activity.type == discord.ActivityType.custom:
            custom_status = activity.name or activity.state
            break

    # Format user details
    usr_discord_created = member.created_at.strftime(dateFormat)
    usr_guild_joined = member.joined_at.strftime(dateFormat)
    usr_roles = ", ".join([f"`{role.name}`" for role in member.roles])
    userinfo = (
        f"Nickname: {member.nick}\n"
        f"Discord Created: {usr_discord_created}\n"
        f"Server Joined: {usr_guild_joined}\n"
        f"Current Roles: ||{usr_roles}||\n"
        f"User Status: {usr_status}\n"
    )
    if custom_status:
        userinfo += f"Custom Status: {custom_status}\n"

    # Main profile embed
    embed0 = discord.Embed(title=f"{member.name}'s Profile", url=profile_link, color=discord.Color.blue())
    embed0.add_field(name="Username", value=f"{member}", inline=True)
    embed0.add_field(name="User ID", value=f"{member.id}", inline=True)
    embed0.add_field(name="User Information", value=userinfo, inline=False)
    embed0.add_field(name="Server Avatar", value=f"[Click Here]({server_avatar_url})", inline=True)
    embed0.add_field(name="Global Avatar", value=f"[Click Here]({global_avatar_url})", inline=True)
    embed0.set_thumbnail(url=server_avatar_url)

    # Separate embed for the server avatar image
    embed1 = discord.Embed(title=f"{member.name}'s Server Avatar", url=profile_link, color=discord.Color.blue())
    embed1.set_image(url=server_avatar_url)

    # Separate embed for the global avatar image
    embed2 = discord.Embed(title=f"{member.name}'s Global Avatar", url=profile_link, color=discord.Color.green())
    embed2.set_image(url=global_avatar_url)

    return [embed0, embed1, embed2]


class ProfileFetch(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='profile',
                          description="Fetch a user's profile information")
    @app_commands.describe(user_id="The user ID to fetch")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, private_channels=False, dms=False)
    async def profile(self, interaction: discord.Interaction, user_id: str = None) -> None:
        logger.info(f"Fetch profile for user ID: {user_id} by {interaction.user.name}")

        if user_id is None:
            await interaction.response.send_message("User ID must be provided.", ephemeral=True)
            return

        try:
            member = interaction.guild.get_member(int(user_id))
        except ValueError:
            await interaction.response.send_message("Invalid user ID format.", ephemeral=True)
            return

        if member is None:
            await interaction.response.send_message(
                f"User with ID {user_id} not found in this guild.", ephemeral=True
            )
            return

        embeds = create_profile_embeds(member)
        await interaction.response.send_message(embeds=embeds)
        logger.info(f"Sent profile pictures for user ID: {user_id}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfileFetch(bot))


@shadow_bot.tree.context_menu(name="Profile")
async def return_profile(interaction: discord.Interaction, user: discord.User) -> None:
    """
    Context menu command that fetches a user's profile.
    """
    logger.info(f"Fetch profile for user ID: {user.id} by {interaction.user.name}")

    if interaction.guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    member = interaction.guild.get_member(user.id)
    if member is None:
        await interaction.response.send_message(
            f"User with ID {user.id} not found in this guild.", ephemeral=True
        )
        return

    embeds = create_profile_embeds(member)
    await interaction.response.send_message(embeds=embeds)
    logger.info(f"Sent profile pictures for user ID: {user.id}")
