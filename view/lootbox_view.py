import discord

from control.controller import Controller
from events.types import UIEventType
from events.ui_event import UIEvent
from view.view_menu import ViewMenu


class LootBoxView(ViewMenu):

    def __init__(self, controller: Controller, owner_id: int = None):
        super().__init__(timeout=None)
        self.controller = controller
        self.add_item(ClaimButton())
        self.owner_id = owner_id
        self.controller_class = "LootBoxViewController"
        self.controller_module = "lootbox_view_controller"
        self.controller.register_view(self)

    async def claim(self, interaction: discord.Interaction):
        await interaction.response.defer()
        event = UIEvent(
            UIEventType.CLAIM_LOOTBOX,
            (interaction, self.owner_id),
            self.id,
        )
        await self.controller.dispatch_ui_event(event)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def listen_for_ui_event(self, event: UIEvent):
        if event.get_view_id() != self.id:
            return
        match event.get_type():
            case UIEventType.STOP_INTERACTIONS:
                self.stop()


class ClaimButton(discord.ui.Button):

    def __init__(self):
        super().__init__(label="Mine!", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        view: LootBoxView = self.view

        await view.claim(interaction)