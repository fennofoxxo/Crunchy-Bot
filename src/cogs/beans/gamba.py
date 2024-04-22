import asyncio
import datetime
import random
import re

import discord
from bot import CrunchyBot
from control.ai_manager import AIManager
from control.controller import Controller
from control.event_manager import EventManager
from control.item_manager import ItemManager
from control.logger import BotLogger
from control.role_manager import RoleManager
from control.settings_manager import SettingsManager
from datalayer.database import Database
from discord import app_commands
from discord.ext import commands
from events.beans_event import BeansEvent
from events.types import BeansEventType
from items.types import ItemType
from view.settings_modal import SettingsModal


class Gamba(commands.Cog):

    def __init__(self, bot: CrunchyBot) -> None:
        self.bot = bot
        self.logger: BotLogger = bot.logger
        self.database: Database = bot.database
        self.controller: Controller = bot.controller
        self.item_manager: ItemManager = self.controller.get_service(ItemManager)
        self.event_manager: EventManager = self.controller.get_service(EventManager)
        self.role_manager: RoleManager = self.controller.get_service(RoleManager)
        self.settings_manager: SettingsManager = self.controller.get_service(
            SettingsManager
        )
        self.ai_manager: AIManager = self.controller.get_service(AIManager)

    @staticmethod
    async def __has_permission(interaction: discord.Interaction) -> bool:
        author_id = 90043934247501824
        return (
            interaction.user.id == author_id
            or interaction.user.guild_permissions.administrator
        )

    async def __check_enabled(self, interaction: discord.Interaction) -> bool:
        guild_id = interaction.guild_id

        if not self.settings_manager.get_beans_enabled(guild_id):
            await self.bot.command_response(
                self.__cog_name__, interaction, "Beans module is currently disabled."
            )
            return False

        if interaction.channel_id not in self.settings_manager.get_beans_channels(
            guild_id
        ):
            await self.bot.command_response(
                self.__cog_name__,
                interaction,
                "Beans commands cannot be used in this channel.",
            )
            return False

        stun_base_duration = self.item_manager.get_item(guild_id, ItemType.BAT).value
        stunned_remaining = self.event_manager.get_stunned_remaining(
            guild_id, interaction.user.id, stun_base_duration
        )
        if stunned_remaining > 0:
            timestamp_now = int(datetime.datetime.now().timestamp())
            remaining = int(timestamp_now + stunned_remaining)
            await self.bot.command_response(
                self.__cog_name__,
                interaction,
                f"You are currently stunned from a bat attack. Try again <t:{remaining}:R>",
            )
            return False

        return True

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.logger.log(
            "init", str(self.__cog_name__) + " loaded.", cog=self.__cog_name__
        )

    @app_commands.command(name="gamba", description="Gamba away your beans.")
    @app_commands.guild_only()
    async def gamba(self, interaction: discord.Interaction, amount: int | None = None):
        if not await self.__check_enabled(interaction):
            return

        guild_id = interaction.guild_id
        user_id = interaction.user.id
        beans_gamba_min = self.settings_manager.get_beans_gamba_min(guild_id)
        beans_gamba_max = self.settings_manager.get_beans_gamba_max(guild_id)
        default_cooldown = self.settings_manager.get_beans_gamba_cooldown(guild_id)
        timestamp_now = int(datetime.datetime.now().timestamp())

        if amount is not None and not (
            beans_gamba_min <= amount and amount <= beans_gamba_max
        ):
            prompt = (
                f"<user>{interaction.user.display_name}</user>"
                f"I tried to bet more than `🅱️{beans_gamba_max}` or less than `🅱️{beans_gamba_min} beans,"
                " which is not acceptable. Please tell me what i did wrong and keep the formatting between"
                " the backticks (including them) like in my message. Also keep it short."
            )
            response = await self.ai_manager.prompt(prompt, max_tokens=60)

            if response is None or len(response) == 0:
                response = f"Between `🅱️{beans_gamba_min}` and `🅱️{beans_gamba_max}` you fucking monkey."

            await self.bot.command_response(
                self.__cog_name__,
                interaction,
                response,
                ephemeral=False,
            )
            return

        await interaction.response.defer()

        default_amount = self.settings_manager.get_beans_gamba_cost(guild_id)

        if amount is None:
            amount = default_amount

        current_balance = self.database.get_member_beans(guild_id, user_id)

        if current_balance < amount:

            prompt = (
                f"<user>{interaction.user.display_name}</user>"
                "I tried to bet beans but i dont have any,"
                " which is not acceptable. Please tell me what i did wrong. Also keep it short, 30 words or less."
            )
            response = await self.ai_manager.prompt(prompt)

            if response is None or len(response) == 0:
                response = "You're out of beans, idiot."

            await self.bot.command_response(
                self.__cog_name__,
                interaction,
                response,
                ephemeral=False,
            )
            return

        last_gamba_cost_event = self.database.get_last_beans_event(
            guild_id, user_id, BeansEventType.GAMBA_COST
        )
        last_gamba_payout_event = self.database.get_last_beans_event(
            guild_id, user_id, BeansEventType.GAMBA_PAYOUT
        )

        if last_gamba_cost_event is not None:

            current_date = datetime.datetime.now()
            last_gamba_beans_date = last_gamba_cost_event.datetime

            delta = current_date - last_gamba_beans_date
            delta_seconds = delta.total_seconds()

            last_gamba_amount = abs(last_gamba_cost_event.value)
            cooldown = default_cooldown

            if last_gamba_payout_event.value != 0:
                # only go on cooldown when previous gamba was a win
                cooldown = default_cooldown * (last_gamba_amount / default_amount)

            if delta_seconds <= cooldown:
                remaining = cooldown - delta_seconds
                cooldowntimer = int(timestamp_now + remaining)

                prompt = (
                    f"<user>{interaction.user.display_name}</user>"
                    f"tell me that my gamble is still on cooldown, using this expression: '<t:{cooldowntimer}:R>'."
                    " Use it in a sentence like you would in place of 'in 10 minutes' or ' 'in 5 hours', for example "
                    f" 'You may try again <t:{cooldowntimer}:R>'"
                    " I am an idiot for trying to gamba while its on cooldown, so please tell me off for it. Also keep it short, 30 words or less."
                )
                response = await self.ai_manager.prompt(prompt)

                if response is None or len(response) == 0:
                    response = (
                        f"Gamba is on cooldown. Try again in <t:{cooldowntimer}:R>.",
                    )

                await self.bot.command_response(
                    self.__cog_name__,
                    interaction,
                    response,
                    ephemeral=False,
                )
                message = await interaction.original_response()
                channel_id = message.channel.id
                message_id = message.id

                await asyncio.sleep(remaining)

                message = (
                    await self.bot.get_guild(guild_id)
                    .get_channel(channel_id)
                    .fetch_message(message_id)
                )
                await message.delete()
                return

        event = BeansEvent(
            datetime.datetime.now(),
            guild_id,
            BeansEventType.GAMBA_COST,
            user_id,
            -int(amount),
        )
        await self.controller.dispatch_event(event)

        response = f"You paid `🅱️{amount}` beans to gamba."

        display_values = [
            "\n**0x**",
            "\n**2x**🎲",
            "\n**3x**🎲🎲",
            "\n**5x**🎲🎲🎲",
            "\n**10x**🎲🎲🎲🎲",
            "\n**100x**🎲🎲🎲🎲🎲",
        ]

        payout = 0

        loss = 0.53
        times_two = 0.27
        times_three = 0.14
        times_five = 0.05
        # times_ten = 0.009
        jackpot = 0.001

        # (0.27*2)+(0.14*3)+(0.05*5)+(0.009*10)+(0.001*100)
        result = random.random()

        name_result = re.findall(r"\(+(.*?)\)", interaction.user.display_name)

        name = interaction.user.display_name
        title = ""
        if len(name_result) > 0:
            name = name_result[0]
            title_result = re.findall(r"\(+.*?\)(.*)", interaction.user.display_name)

            if len(title_result) > 0:
                title = title_result[0].strip()

        prompt = f"My name is {name} "
        if len(title) > 0:
            prompt += f"and i am {title}"
        prompt += ". I tried to bet my beans on the beans gamble,"
        prompt += "I tried to bet my beans on the beans gamble,"
        if result <= loss:
            final_display = 0
            final = "You lost. It is what it is."
            prompt += "but i lost them all. Please make fun of me."
        elif result > loss and result <= (loss + times_two):
            final_display = 1
            payout = amount * 2
            final = f"You won! Your payout is `🅱️{payout}` beans."
            prompt += f"and i won `🅱️{payout}` beans, which is a small amount. Please congratulate me, but not too much."
        elif result > (loss + times_two) and result <= (loss + times_two + times_three):
            final_display = 2
            payout = amount * 3
            final = f"Wow you got lucky! Your payout is `🅱️{payout}` beans."
            prompt += f"and i won `🅱️{payout}` beans, which is amoderate amount. Please congratulate me."
        elif result > (loss + times_two + times_three) and result <= (
            loss + times_two + times_three + times_five
        ):
            final_display = 3
            payout = amount * 5
            final = f"Your luck is amazing! Your payout is `🅱️{payout}` beans."
            prompt += f"and i won `🅱️{payout}` beans, which is a large amount. Please congratulate me."
        elif result > (loss + times_two + times_three + times_five) and result <= (
            1 - jackpot
        ):
            final_display = 4
            payout = amount * 10
            final = f"**BIG WIN!** Your payout is `🅱️{payout}` beans."
            prompt += f"and i won `🅱️{payout}` beans, which is a massive amount."
            prompt += " Please congratulate me a lot and freak out a little because it is so rare."
        elif result > (1 - jackpot) and result <= 1:
            final_display = 5
            payout = amount * 100
            final = f"**JACKPOT!!!** Your payout is `🅱️{payout}` beans."
            prompt += f"and i hit the jackpot! Now im rich, i got  `🅱️{payout}` beans as a payout! "
            prompt += "Please congratulate me a lot and praise me. Completely freak out about it and break character a little."

        if result > loss:
            prompt += " please mention the amount of beans i won."
            prompt += " please keep the formatting between the backticks (including them) like in my message."

        prompt += " Also keep it super concise, 25 words or less preferably unless its a jackpot, and refer to the gamble as gamba."

        final_ai = await self.ai_manager.prompt(prompt)

        if final_ai is not None and len(response) > 0:
            final = final_ai

        final = "\n" + final

        display = display_values[0]
        await self.bot.command_response(
            self.__cog_name__, interaction, response, ephemeral=False
        )

        message = await interaction.original_response()
        i = 0
        current = i
        while i <= 12 or current != final_display:
            current = i % len(display_values)
            display = display_values[current]
            await asyncio.sleep((1 / 30) * i * 2)
            await message.edit(content=response + display)
            i += 1

        today = datetime.datetime.now().date()
        today_timestamp = datetime.datetime(
            year=today.year, month=today.month, day=today.day
        ).timestamp()

        user_daily_gamba_count = self.database.get_beans_daily_gamba_count(
            guild_id,
            user_id,
            BeansEventType.GAMBA_COST,
            default_amount,
            today_timestamp,
        )
        beans_bonus_amount = 0
        match user_daily_gamba_count:
            case 10:
                beans_bonus_amount = self.settings_manager.get_beans_bonus_amount_10(
                    interaction.guild_id
                )
            case 25:
                beans_bonus_amount = self.settings_manager.get_beans_bonus_amount_25(
                    interaction.guild_id
                )

        if beans_bonus_amount > 0:
            final += f"\n🎉 You reached **{user_daily_gamba_count}** gambas for today! Enjoy these bonus beans `🅱️{beans_bonus_amount}` 🎉"

            event = BeansEvent(
                datetime.datetime.now(),
                guild_id,
                BeansEventType.BONUS_PAYOUT,
                user_id,
                beans_bonus_amount,
            )
            await self.controller.dispatch_event(event)

        event = BeansEvent(
            datetime.datetime.now(),
            guild_id,
            BeansEventType.GAMBA_PAYOUT,
            user_id,
            payout,
        )
        await self.controller.dispatch_event(event)

        cooldowntimer = int(default_cooldown * amount / default_amount)
        if payout == 0 and amount > default_amount:
            cooldowntimer = int(default_cooldown)
        remaining = int(timestamp_now + cooldowntimer)
        timer = f"\nYou can gamble again <t:{remaining}:R>."
        await message.edit(content=response + display + final + timer)
        channel_id = message.channel.id
        message_id = message.id
        await asyncio.sleep(max(0, cooldowntimer - 10))
        message = (
            await self.bot.get_guild(guild_id)
            .get_channel(channel_id)
            .fetch_message(message_id)
        )
        await message.edit(content=response + display + final)

    @app_commands.command(
        name="gamba_setup",
        description="Opens a dialog to edit various gamba beans settings.",
    )
    @app_commands.check(__has_permission)
    @app_commands.guild_only()
    async def gamba_setup(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        modal = SettingsModal(
            self.bot,
            self.settings_manager,
            self.__cog_name__,
            interaction.command.name,
            "Settings for Gamba related Features",
        )

        modal.add_field(
            guild_id,
            SettingsManager.BEANS_SUBSETTINGS_KEY,
            SettingsManager.BEANS_GAMBA_DEFAULT_KEY,
            int,
        )
        modal.add_field(
            guild_id,
            SettingsManager.BEANS_SUBSETTINGS_KEY,
            SettingsManager.BEANS_GAMBA_COOLDOWN_KEY,
            int,
        )
        modal.add_field(
            guild_id,
            SettingsManager.BEANS_SUBSETTINGS_KEY,
            SettingsManager.BEANS_GAMBA_MIN_KEY,
            int,
        )
        modal.add_field(
            guild_id,
            SettingsManager.BEANS_SUBSETTINGS_KEY,
            SettingsManager.BEANS_GAMBA_MAX_KEY,
            int,
        )

        modal.add_constraint(
            [SettingsManager.BEANS_GAMBA_MIN_KEY, SettingsManager.BEANS_GAMBA_MAX_KEY],
            lambda a, b: a <= b,
            "Gamba minimum must be smaller than gamba maximum.",
        )

        await interaction.response.send_modal(modal)


async def setup(bot) -> None:
    await bot.add_cog(Gamba(bot))