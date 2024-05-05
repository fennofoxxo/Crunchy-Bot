import discord
from datalayer.types import ItemTrigger

from items.types import ItemGroup, ItemType, ShopCategory


class Item:

    def __init__(
        self,
        name: str, 
        item_type: ItemType,
        group: ItemGroup,
        shop_category: ShopCategory,
        description: str,
        emoji: str,
        cost: int,
        value: int,
        view_class: str = None,
        allow_amount: bool = False,
        base_amount: int = 1,
        max_amount: int = None,
        trigger: list[ItemTrigger] = None,
        hide_in_shop: bool = False,
        weight: int = None,
        controllable: bool = False,
        useable: bool = False,
        permanent: bool = False
    ):
        self.name = name
        self.type = item_type
        self.group = group
        self.shop_category = shop_category
        self.description = description
        self.cost = cost
        self.value = value
        self.emoji = emoji
        self.view_class = view_class
        self.allow_amount = allow_amount
        self.base_amount = base_amount
        self.max_amount = max_amount
        self.trigger = trigger
        self.hide_in_shop = hide_in_shop
        self.weight = weight
        if self.weight is None:
            self.weight = max(self.cost, 100)
        self.controllable = controllable
        self.useable = useable
        self.permanent = permanent
    
    def activated(self, action: ItemTrigger):
        if self.trigger is None:
            return False
        return action in self.trigger
    
    def get_embed(self, color=None, amount_in_cart: int = 1) -> discord.Embed:
        if color is None:
            color=discord.Colour.purple()
        title = f'> {self.emoji} {self.name} {self.emoji}'

        if self.permanent:
            title = f'> {self.emoji} *{self.name}* {self.emoji}'

        description = self.description
        max_width = 53
        if len(description) < max_width:
            spacing = max_width - len(description)
            description += ' '*spacing
            
        if self.permanent:
            suffix = f'🅱️[34m{self.cost*amount_in_cart}'
            suffix_len = len(suffix) - 5
        else:
            suffix = f'🅱️{self.cost*amount_in_cart}'
            suffix_len = len(suffix)
        spacing = max_width - suffix_len 
        info_block = f'```python\n"{description}"\n\n{' '*spacing}{suffix}```'

        if self.permanent:
            info_block = f'```ansi\n[33m"{description}"[0m\n\n{' '*spacing}{suffix}```'
        
        embed = discord.Embed(title=title, description=info_block, color=color)
        
        return embed
    
    def add_to_embed(self, embed: discord.Embed, max_width: int, count: int=None, show_price: bool = False, name_suffix: str='', disabled: bool = False) -> None:
        title = f'> ~*  {self.emoji} {self.name} {self.emoji}  *~ {name_suffix}'

        if self.permanent:
            title = f'> ~* {self.emoji} *{self.name}* {self.emoji} *~ {name_suffix}'

        description = self.description
        
        if len(description) < max_width:
            spacing = max_width - len(description)
            description += ' '*spacing
        prefix = ''
        suffix = ''

        if self.permanent:
            if show_price:
                if count is None:
                    suffix = f'🅱️[34m{self.cost}'
                else:
                    prefix = f'owned: [34m{count}[0m'
                    suffix = f'🅱️[34m{self.cost}'
            else:
                if count is not None:
                    if disabled:
                        prefix = "[DISABLED]"
                    suffix = f'amount: [34m{count}'

            suffix_len = len(suffix) - 5
            prefix_len = max(0, len(prefix) - 5)

            spacing = max_width - prefix_len - suffix_len
            info_block = f'```ansi\n[33m"{description}"[0m\n\n{prefix}{' '*spacing}{suffix}```'
        else:
            if show_price:
                if count is None:
                    suffix = f'🅱️{self.cost}'
                else:
                    prefix = f'owned: {count}'
                    suffix = f'🅱️{self.cost}'
            else:
                if count is not None:
                    if disabled:
                        prefix = "[DISABLED]"
                    suffix = f'amount: {count}'

            suffix_len = len(suffix) 
            prefix_len = len(prefix)

            spacing = max_width - prefix_len - suffix_len
            info_block = f'```python\n"{description}"\n\n{prefix}{' '*spacing}{suffix}```'

        
        embed.add_field(name=title, value=info_block, inline=False)
