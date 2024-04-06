from typing import List
import discord
from bot import CrunchyBot
from control.controller import Controller
from control.event_manager import EventManager
from control.item_manager import ItemManager
from control.logger import BotLogger
from control.role_manager import RoleManager
from control.settings import BotSettings
from control.service import Service
from datalayer.database import Database
from events.ui_event import UIEvent
from view.view_menu import ViewMenu


class ViewController(Service):

    def __init__(self, bot: CrunchyBot):
        super().__init__()
        self.bot = bot
        self.logger: BotLogger = bot.logger
        self.settings: BotSettings = bot.settings
        self.database: Database = bot.database
        self.event_manager: EventManager = bot.event_manager
        self.role_manager: RoleManager = bot.role_manager
        self.item_manager: ItemManager = bot.item_manager
        self.controller: Controller = bot.controller
        self.views: List[ViewMenu] = []

    def register_view(self, view: ViewMenu) -> None:
        self.views.append(view)

    def detach_view(self, view: ViewMenu) -> None:
        self.views.remove(view)

    async def listen_for_ui_event(self, event: UIEvent) -> None:
        for view in self.views:
            await view.listen_for_ui_event(event)

    async def interaction_check(
        self, interaction: discord.Interaction, user_id: int
    ) -> bool:
        if interaction.user.id == user_id:
            return True
        else:
            await interaction.response.send_message(
                "Only the author of the command can perform this action.",
                ephemeral=True,
            )
            return False
