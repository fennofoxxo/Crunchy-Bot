from typing import Literal, Optional
import discord
from discord import app_commands
from discord.ext import commands
from bot import CrunchyBot
from datalayer.database import Database
from control.controller import Controller
from control.event_manager import EventManager
from control.logger import BotLogger
from control.settings import BotSettings
from view.ranking_embed import RankingEmbed
from view.types import RankingType
from view.ranking_view import RankingView
from view.statistics_embed import StatisticsEmbed


class Statistics(commands.Cog):

    def __init__(self, bot: CrunchyBot):
        self.bot = bot
        self.logger: BotLogger = bot.logger
        self.settings: BotSettings = bot.settings
        self.database: Database = bot.database
        self.event_manager: EventManager = bot.event_manager
        self.controller: Controller = bot.controller

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.log(
            "init", str(self.__cog_name__) + " loaded.", cog=self.__cog_name__
        )

    @commands.command()
    @commands.guild_only()
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: Optional[Literal["~", "*", "^"]] = None,
    ) -> None:

        mara = 90043934247501824
        mia = 219145051375271937
        fuzia = 106752187530481664

        if ctx.author.id not in [mara, mia, fuzia]:
            raise commands.NotOwner("You do not own this bot.")

        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @app_commands.command(
        name="stats", description="See your or other peoples statistics."
    )
    @app_commands.describe(
        user="Leave this empty for your own statistics.",
    )
    @app_commands.guild_only()
    async def stats(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ):
        await interaction.response.defer()

        police_img = discord.File("./img/police.png", "police.png")
        jail_img = discord.File("./img/jail.png", "jail.png")

        user = user if user is not None else interaction.user
        user_id = user.id

        log_message = f"{interaction.user.name} used command `{interaction.command.name}` on {user.name}."
        self.logger.log(interaction.guild_id, log_message, cog=self.__cog_name__)

        user_statistics = self.event_manager.get_user_statistics(user_id)

        embed = StatisticsEmbed(self.bot, interaction, user, user_statistics)

        await interaction.followup.send("", embed=embed, files=[police_img, jail_img])

    @app_commands.command(name="rankings", description="Crunchy user rankings.")
    @app_commands.guild_only()
    async def rankings(self, interaction: discord.Interaction):

        log_message = (
            f"{interaction.user.name} used command `{interaction.command.name}`."
        )
        self.logger.log(interaction.guild_id, log_message, cog=self.__cog_name__)
        await interaction.response.defer()

        ranking_data = self.event_manager.get_user_rankings(
            interaction.guild_id, RankingType.BEANS
        )

        embed = RankingEmbed(self.bot, interaction, RankingType.BEANS, ranking_data)
        view = RankingView(self.bot, interaction)

        ranking_img = discord.File("./img/jail_wide.png", "ranking_img.png")
        police_img = discord.File("./img/police.png", "police.png")
        await interaction.followup.send(
            "", embed=embed, view=view, files=[police_img, ranking_img]
        )


async def setup(bot):
    await bot.add_cog(Statistics(bot))
