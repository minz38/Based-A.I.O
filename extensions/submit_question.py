import discord
from discord.ext import commands
from discord import app_commands
# from data.configs.config import DiscordConfig
from dependencies.google_sheets_handler import push_question_to_gs  # todo, use it from the class directly
from logger import LoggerManager

# from src.google_sheets_handler import push_question_to_gs
# from colorama import init, Fore


# guild_id = DiscordConfig.guid_id

logger = LoggerManager(name="Submit Question", level="INFO", log_file="logs/GoogleSheetHandler.log").get_logger()


class QuestionView(discord.ui.View):
    def __init__(self, data, timeout=60, cog_ref=None):
        super().__init__(timeout=timeout)
        self.data = data
        self.cog_ref = cog_ref

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green)
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        logger.info(f"user: {interaction.user.display_name} submitted a Question\n    {self.data}")
        # print(f"{Fore.GREEN}user: {interaction.user.display_name} Submitted a Question\n    {self.data}")
        try:
            await interaction.response.defer(ephemeral=True)  # noqa
            result = push_question_to_gs(data=self.data)
            if result:
                if self.cog_ref and self.cog_ref.last_question_message:
                    await self.cog_ref.last_question_message.edit(
                        content="Successfully Submitted question, you can now close this window", embed=None, view=None)
            else:
                if self.cog_ref and self.cog_ref.last_question_message:
                    await self.cog_ref.last_question_message.edit(content="Question was not Submitted. Internal Error"
                                                                          "missing Result from google sheets handler",
                                                                  embed=None, view=None)
        except Exception as e:
            print(f"{e}")
            if self.cog_ref and self.cog_ref.last_question_message:
                await self.cog_ref.last_question_message.edit(content="Question was not Submitted. Internal Error",
                                                              embed=None, view=None)

        self.stop()

    @discord.ui.button(label="Retry", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        logger.info(f"user: {interaction.user.display_name} did not submit the question")
        # print(f"{Fore.YELLOW}user: {interaction.user.display_name} did not submit the question'")
        await self.cog_ref.last_question_message.edit(content="Question was not Submitted",
                                                      embed=None, view=None)
        self.stop()

    async def on_timeout(self):
        if self.cog_ref and self.cog_ref.last_question_message:
            try:
                await self.cog_ref.last_question_message.edit(content="The interaction has timed out.", embed=None,
                                                              view=None)
            except discord.NotFound:
                pass  # Message was deleted, do nothing
        self.stop()


class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_question_message = None

    @app_commands.command(name='submit_question', description='Submit a Question for the upcoming Drinking night')
    @app_commands.choices(
        question_type=[
            app_commands.Choice(name="Regular Text Question", value=1),
            app_commands.Choice(name="Sound Question", value=2),
            app_commands.Choice(name="Challenge Question", value=3),
        ],
        question_text: str = [

    ]
    )
    async def submit_question(
            self, interaction: discord.Interaction,
            question_type: int = SlashOption(description="Type of the question  "
                                                         "1: Regular Text Question"
                                                         "2: Sound Question"
                                                         "3: Challenge Question",
                                             choices={1, 2, 3}),
            question_text: str = SlashOption(description="The text of the question", required=True,
                                             max_length=100),
            answer_a: str = SlashOption(description="Answer option A", required=True, max_length=50),
            answer_b: str = SlashOption(description="Answer option B", required=True, max_length=50),
            answer_c: str = SlashOption(description="Answer option C", required=True, max_length=50),
            answer_d: str = SlashOption(description="Answer option D", required=True, max_length=50),
            correct_answer: str = SlashOption(description="The correct answer (a, b, c, d)",
                                              required=True, choices=["a", "b", "c", "d"]),
            picture: str = SlashOption(description="A link to the picture", required=False),
            picture_resize: str = SlashOption(
                description="Resize the Picture in % Default 80x80 (80%)",
                required=False, choices=["80x80", "70x70", "60x60", "50x50", "40x40"]),
            youtube_link: str = SlashOption(description="A link to the sound", required=False),
            audio_loop: bool = SlashOption(description="Should the sound loop", required=False,
                                           default=None),
            cut_audio: str = SlashOption(description="Timestamp for the sound (mm:ss-mm:ss)",
                                         required=False)
    ):
        sound = youtube_link
        sound_loop = audio_loop
        timestamp = cut_audio
        # Validation and formation of the inputs
        question_type_print = None
        if question_type:
            if question_type == 1:
                question_type_print = "Regular Text Question"
            elif question_type == 2:
                question_type_print = "Sound Question"
            elif question_type == 3:
                question_type_print = "Challenge Question"
            else:
                return await interaction.response.send_message(f"Invalid question type: {question_type}",
                                                               ephemeral=True)

        if picture and not picture.lower().startswith("https://"):
            return await interaction.response.send_message(f"Invalid picture link: {picture}", ephemeral=True)

        if sound and not sound.lower().startswith("https://"):
            return await interaction.response.send_message(f"Invalid sound link: {sound}", ephemeral=True)

        embed = discord.Embed(title="Confirm Your Question",
                              description="Please review your question details below and confirm.", color=0x00ff00)
        embed.add_field(name="Question Type", value=question_type_print, inline=False)
        embed.add_field(name="Question Text", value=question_text, inline=False)
        embed.add_field(name="Answer Option A", value=answer_a, inline=False)
        embed.add_field(name="Answer Option B", value=answer_b, inline=False)
        embed.add_field(name="Answer Option C", value=answer_c, inline=False)
        embed.add_field(name="Answer Option D", value=answer_d, inline=False)
        embed.add_field(name="Correct Answer", value=correct_answer, inline=False)
        embed.add_field(name="Picture", value=picture, inline=False)
        embed.add_field(name="Resize Picture %", value=picture_resize, inline=False)
        embed.add_field(name="Sound", value=sound, inline=False)
        embed.add_field(name="Sound Loop", value=sound_loop, inline=False)
        embed.add_field(name="cut_audio", value=timestamp, inline=False)

        # Create buttons for confirmation
        view = discord.ui.View()
        confirm_button = discord.ui.Button(label="Submit", style=discord.ButtonStyle.green)
        decline_button = discord.nextcord.ui.Button(label="Retry", style=discord.ButtonStyle.red)
        view.add_item(confirm_button)
        view.add_item(decline_button)

        data_list = [
            [question_type, question_text, answer_a, answer_b, answer_c, answer_d, correct_answer, picture,
             picture_resize, sound, sound_loop, timestamp]]

        view = QuestionView(data_list, cog_ref=self, timeout=300)
        print(f"User: {interaction.user.display_name} created a question \n    {data_list}")
        # await interaction.send(embed=embed, view=view, ephemeral=True)
        self.last_question_message = await interaction.send(embed=embed, view=view, ephemeral=True)  # noqa


def setup(bot):
    bot.add_cog(MyCog(bot))
