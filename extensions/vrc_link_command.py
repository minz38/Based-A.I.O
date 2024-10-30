import os
import json
import discord
from discord.ext import commands
from discord import app_commands

# Define the file path for storing VRChat user links
VRCHAT_LINK_FILE = 'temp/vrc/vrchat_user_link_map.json'


class VRChatProfileModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(
            timeout=300  # Timeout for the modal
        )

        # Add a text input field to the modal
        self.vrchat_profile_id = discord.ui.TextInput(
            label="VRChat Profile ID",
            placeholder="Enter your VRChat Profile ID...",
            required=True,  # Make this field required
            max_length=100  # Maximum length of the input
        )

        # Add the text input to the modal
        self.add_item(self.vrchat_profile_id)

    async def callback(self, interaction: discord.Interaction):
        # This is called when the user submits the modal
        vrchat_profile_id = self.vrchat_profile_id.value
        user_id = interaction.user.id
        user_name = interaction.user.name
        server_id = interaction.guild.id

        # Prepare the data to be saved
        link_data = {
            'server_id': server_id,
            'user_id': user_id,
            'user_name': user_name,
            'vrchat_id': vrchat_profile_id,
            'announced': False  # Indicates whether the link has been announced to the server
        }

        # Ensure the directory and file exist
        directory = os.path.dirname(VRCHAT_LINK_FILE)
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Load existing data or create the file if it doesn't exist
        if os.path.exists(VRCHAT_LINK_FILE):
            with open(VRCHAT_LINK_FILE, 'r') as f:
                vrchat_links = json.load(f)
        else:
            vrchat_links = []

        # Check if the user already has an entry
        user_exists = False
        for link in vrchat_links:
            if link['user_id'] == user_id and link['server_id'] == server_id:
                # Update the existing entry
                link['vrchat_id'] = vrchat_profile_id
                user_exists = True
                break

        # If the user doesn't exist, add a new entry
        if not user_exists:
            vrchat_links.append(link_data)

        # Save the updated list back to the JSON file
        with open(VRCHAT_LINK_FILE, 'w') as f:
            json.dump(vrchat_links, f, indent=4)

        # Send a confirmation message
        await interaction.response.send_message(f"VRChat Profile ID `{vrchat_profile_id}`"
                                                f" has been linked to your account.", ephemeral=False)


class LinkVRChatAccount(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='link', description='Link your VRChat account to your Discord account')
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def link(self, interaction: discord.Interaction,
                   user: discord.Member = None,
                   vrchat_id: str = None) -> None:

        # If no user or vrchat_id provided, show the modal (for users)
        if user is None and vrchat_id is None:
            modal = VRChatProfileModal()
            await interaction.response.send_modal(modal)  # Show the modal when the command is used

        # If both user and vrchat_id are provided, set the VRChat ID manually (for admins)
        elif user and vrchat_id:
            # user_id = user.id
            # user_name = user.name
            # server_id = interaction.guild.id

            # Prepare the data to be saved
            link_data = {
                'server_id': interaction.guild.id,
                'user_id': user.id,
                'user_name': user.name,
                'vrchat_id': vrchat_id,
                'announced': False  # Indicates whether the link has been announced to the server
            }

            # Ensure the directory and file exist
            directory = os.path.dirname(VRCHAT_LINK_FILE)
            if not os.path.exists(directory):
                os.makedirs(directory)

            # Load existing data or create the file if it doesn't exist
            if os.path.exists(VRCHAT_LINK_FILE):
                with open(VRCHAT_LINK_FILE, 'r') as f:
                    vrchat_links = json.load(f)
            else:
                vrchat_links = []

            # Check if the user already has an entry
            user_exists = False
            for link in vrchat_links:
                if link['user_id'] == user.id and link['server_id'] == interaction.guild.id:
                    # Update the existing entry
                    link['vrchat_id'] = vrchat_id
                    user_exists = True
                    break

            # If the user doesn't exist, add a new entry
            if not user_exists:
                vrchat_links.append(link_data)

            # Save the updated list back to the JSON file
            with open(VRCHAT_LINK_FILE, 'w') as f:
                json.dump(vrchat_links, f, indent=4)

            # Send a confirmation message
            await interaction.response.send_message(f"VRChat Profile ID `{vrchat_id}`"
                                                    f" has been linked to `{user.name}`.", ephemeral=False)


async def setup(bot):
    await bot.add_cog(LinkVRChatAccount(bot))
