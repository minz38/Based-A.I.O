import discord
from enum import Enum
from discord.ext import commands
from discord import app_commands
from dep.logger import LoggerManager
from typing import Optional, Annotated
from dep.google_sheets_handler import GoogleSheetHandler

logger = LoggerManager(name="Submit Question", level="INFO", log_name="webapp").get_logger()


class QuestionView(discord.ui.View):
    def __init__(self, data, timeout=60, cog_ref=None, inter=None) -> None:
        super().__init__(timeout=timeout)
        self.data = data
        self.cog_ref = cog_ref
        self.inter: discord.Interaction = inter


    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green)
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        logger.info(f"user: {self.cog_ref.username} submitted the Question")
        # print(f"{Fore.GREEN}user: {interaction.user.display_name} Submitted a Question\n    {self.data}")
        gs_handler = GoogleSheetHandler(guild_id=self.cog_ref.guild_id)
        admin_log_cog = self.inter.client.get_cog("AdminLog")
        try:
            # await interaction.response.defer(ephemeral=True)

            result = gs_handler.push_question_to_gs(data=self.data)
            if result:
                if self.cog_ref and self.cog_ref.last_question_message:
                    await self.cog_ref.last_question_message.edit(
                        content="Successfully Submitted question, you can now close this window", embed=None, view=None)

                if admin_log_cog:
                    await admin_log_cog.log_interaction(
                        interaction=self.inter,
                        priority="info",
                        text=f"User submitted a question to the Google Sheets."
                    )
            else:
                if self.cog_ref and self.cog_ref.last_question_message:
                    await self.cog_ref.last_question_message.edit(
                        content="Question was not Submitted. Internal Error missing Result from google sheets handler",
                        embed=None,
                        view=None
                    )
                if admin_log_cog:
                    await admin_log_cog.log_interaction(
                        interaction=self.inter,
                        priority="error",
                        text=f"User encountered an error while submitting the question: 44092"
                    )

        except Exception as e:
            print(f"{e}")
            if self.cog_ref and self.cog_ref.last_question_message:
                await self.cog_ref.last_question_message.edit(content="Question was not Submitted. Internal Error",
                                                              embed=None, view=None)

        self.stop()

    @discord.ui.button(label="Retry", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        logger.info(f"user: {self.cog_ref.username}  did not submit the question")
        # print(f"{Fore.YELLOW}user: {interaction.user.display_name} did not submit the question'")
        await self.cog_ref.last_question_message.edit(content="Question was not Submitted",
                                                      embed=None, view=None)
        admin_log_cog = self.inter.client.get_cog("AdminLog")
        if admin_log_cog:
            await admin_log_cog.log_interaction(
                interaction=self.inter,
                priority="error",
                text=f"User did not submit the question to the Google Sheets."
            )

        self.stop()

    async def on_timeout(self):
        if self.cog_ref and self.cog_ref.last_question_message:
            try:
                await self.cog_ref.last_question_message.edit(
                    content="The interaction has timed out.",
                    embed=None,
                    view=None
                )
            except discord.NotFound:
                pass  # Message was deleted, do nothing

        self.stop()


class QuestionType(Enum):
    Regular_Text_Question = 1
    Sound_Question = 2
    Challenge_Question = 3


class CorrectAnswer(Enum):
    A = 'a'
    B = 'b'
    C = 'c'
    D = 'd'


class PictureResize(Enum):
    Size_80x80 = "80x80"
    Size_70x70 = "70x70"
    Size_60x60 = "60x60"
    Size_50x50 = "50x50"
    Size_40x40 = "40x40"


class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_question_message = None
        self.username = None
        self.guild_id = None

    @app_commands.command(name='submit_question', description='Submit a Question for the upcoming Drinking night')
    @app_commands.describe(
        question_type='Question Type',
        question_text='The text of the question',
        answer_a='Answer option A',
        answer_b='Answer option B',
        answer_c='Answer option C',
        answer_d='Answer option D',
        correct_answer='The correct answer (a, b, c, d)',
        picture='A link to the picture',
        picture_resize='Resize the Picture in % (Default: 80x80)',
        youtube_link='A link to the sound',
        audio_loop='Should the sound loop',
        cut_audio='Timestamp for the sound (mm:ss-mm:ss)'
    )
    async def submit_question(
            self,
            interaction: discord.Interaction,
            question_type: QuestionType,
            question_text: Annotated[str, app_commands.Range[str, 5, 100]],
            answer_a: Annotated[str, app_commands.Range[str, 1, 50]],
            answer_b: Annotated[str, app_commands.Range[str, 1, 50]],
            answer_c: Annotated[str, app_commands.Range[str, 1, 50]],
            answer_d: Annotated[str, app_commands.Range[str, 1, 50]],
            correct_answer: CorrectAnswer,
            picture: Optional[str] = None,
            picture_resize: Optional[PictureResize] = None,
            youtube_link: Optional[str] = None,
            audio_loop: Optional[bool] = None,
            cut_audio: Optional[str] = None
    ):
        question_type_print = question_type.name.replace('_', ' ')
        question_type: int = int(question_type.value)
        picture_resize: str = str(picture_resize.value) if picture_resize else None
        correct_answer: str = str(correct_answer.value)
        sound: str = youtube_link
        sound_loop: bool = audio_loop
        timestamp: str = cut_audio

        if picture and not picture.lower().startswith("https://"):
            return await interaction.response.send_message(  # noqa
                f"Invalid picture link: {picture}", ephemeral=True
            )

        if sound and not sound.lower().startswith("https://"):
            return await interaction.response.send_message(  # noqa
                f"Invalid sound link: {sound}", ephemeral=True
            )

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
        decline_button = discord.ui.Button(label="Retry", style=discord.ButtonStyle.red)
        view.add_item(confirm_button)
        view.add_item(decline_button)

        data_list = [
            [question_type, question_text, answer_a, answer_b, answer_c, answer_d, correct_answer, picture,
             picture_resize, sound, sound_loop, timestamp]]

        self.username = interaction.user.display_name
        self.guild_id = interaction.guild.id
        view = QuestionView(data_list, cog_ref=self, timeout=300, inter=interaction)
        print(f"User: {interaction.user.display_name} created a question \n    {data_list}")
        # await interaction.send(embed=embed, view=view, ephemeral=True)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)  # noqa
        self.last_question_message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(MyCog(bot))
