import contextlib

import discord

from control.controller import Controller
from events.types import UIEventType
from events.ui_event import UIEvent
from items.item import Item
from items.types import ItemType
from view.shop_embed import ShopEmbed
from view.view_menu import ViewMenu


class ShopView(ViewMenu):

    def __init__(
        self,
        controller: Controller,
        interaction: discord.Interaction,
        items: list[Item],
        user_balance: int,
    ):
        super().__init__(timeout=300)
        self.controller = controller
        self.items = items
        self.guild_name = interaction.guild.name
        self.member_id = interaction.user.id
        self.guild_id = interaction.guild_id
        self.current_page = 0
        self.selected: ItemType = None
        self.item_count = len(self.items)
        self.page_count = int(self.item_count / ShopEmbed.ITEMS_PER_PAGE) + (
            self.item_count % ShopEmbed.ITEMS_PER_PAGE > 0
        )

        self.message = None
        self.user_balance = user_balance

        self.controller_class = "ShopViewController"
        self.controller_module = "shop_view_controller"
        self.controller.register_view(self)
        self.refresh_elements()

    async def listen_for_ui_event(self, event: UIEvent):
        match event.get_type():
            case UIEventType.SHOP_USER_REFRESH:
                user_id = event.get_payload()[0]
                if user_id != self.member_id:
                    return
                user_balance = event.get_payload()[1]
                await self.refresh_ui(user_balance=user_balance)

        if event.get_view_id() != self.id:
            return

        match event.get_type():
            case UIEventType.SHOP_REFRESH:
                await self.refresh_ui(user_balance=event.get_payload(), disabled=False)
            case UIEventType.SHOP_DISABLE:
                await self.refresh_ui(disabled=event.get_payload())

    def set_message(self, message: discord.Message):
        self.message = message

    async def buy(self, interaction: discord.Interaction):
        await interaction.response.defer()
        event = UIEvent(
            UIEventType.SHOP_BUY,
            (interaction, self.selected),
            self.id,
        )
        await self.controller.dispatch_ui_event(event)

    async def flip_page(self, interaction: discord.Interaction, right: bool = False):
        await interaction.response.defer()
        self.current_page = (self.current_page + (1 if right else -1)) % self.page_count
        self.selected = None
        event = UIEvent(
            UIEventType.SHOP_CHANGED,
            (self.guild_id, self.member_id),
            self.id,
        )
        await self.controller.dispatch_ui_event(event)

    def refresh_elements(self, user_balance: int = None, disabled: bool = False):
        start = ShopEmbed.ITEMS_PER_PAGE * self.current_page
        end = min((start + ShopEmbed.ITEMS_PER_PAGE), self.item_count)
        page_display = f"Page {self.current_page + 1}/{self.page_count}"

        if user_balance is not None:
            self.user_balance = user_balance

        self.clear_items()
        self.add_item(Dropdown(self.items[start:end], self.selected, disabled))
        self.add_item(PageButton("<", False, disabled))
        self.add_item(BuyButton(disabled))
        self.add_item(PageButton(">", True, disabled))
        self.add_item(CurrentPageButton(page_display))
        self.add_item(BalanceButton(self.user_balance))

    async def refresh_ui(self, user_balance: int = None, disabled: bool = False):
        self.refresh_elements(user_balance, disabled)
        start = ShopEmbed.ITEMS_PER_PAGE * self.current_page
        embed = ShopEmbed(self.guild_name, self.member_id, self.items, start)
        await self.message.edit(embed=embed, view=self)

    async def set_selected(self, interaction: discord.Interaction, item_type: ItemType):
        self.selected = item_type
        await interaction.response.defer()

    async def on_timeout(self):
        with contextlib.suppress(discord.HTTPException):
            await self.message.edit(view=None)
        self.controller.detach_view(self)


class BuyButton(discord.ui.Button):

    def __init__(self, disabled: bool = False):
        super().__init__(
            label="Buy", style=discord.ButtonStyle.green, row=1, disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view

        if await view.interaction_check(interaction):
            await view.buy(interaction)


class PageButton(discord.ui.Button):

    def __init__(self, label: str, right: bool, disabled: bool = False):
        self.right = right
        super().__init__(
            label=label, style=discord.ButtonStyle.grey, row=1, disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view

        if await view.interaction_check(interaction):
            await view.flip_page(interaction, self.right)


class CurrentPageButton(discord.ui.Button):

    def __init__(self, label: str):
        super().__init__(
            label=label, style=discord.ButtonStyle.grey, row=1, disabled=True
        )


class BalanceButton(discord.ui.Button):

    def __init__(self, balance: int):
        self.balance = balance
        super().__init__(label=f"🅱️{balance}", style=discord.ButtonStyle.blurple, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view

        if await view.interaction_check(interaction):
            await interaction.response.defer(ephemeral=True)
            event = UIEvent(UIEventType.SHOW_INVENTORY, interaction)
            await view.controller.dispatch_ui_event(event)


class Dropdown(discord.ui.Select):

    def __init__(self, items: list[Item], selected: ItemType, disabled: bool = False):

        options = []

        for item in items:
            option = discord.SelectOption(
                label=item.get_name(),
                description="",
                emoji=item.get_emoji(),
                value=item.get_type(),
                default=(selected == item.get_type()),
            )

            options.append(option)

        super().__init__(
            placeholder="Select an item.",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view

        if await view.interaction_check(interaction):
            await view.set_selected(interaction, self.values[0])
