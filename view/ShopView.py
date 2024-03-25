import discord

from MaraBot import MaraBot
from datalayer.UserRankings import UserRankings
from view.RankingEmbed import RankingEmbed
from view.RankingType import RankingType
from view.ShopEmbed import ShopEmbed

class ShopMenu(discord.ui.View):
    
    def __init__(self, bot: MaraBot, interaction: discord.Interaction):
        self.interaction = interaction
        self.bot = bot
        super().__init__(timeout=100)
        self.add_item(Dropdown())
        self.selected = None


    @discord.ui.button(label='Buy', style=discord.ButtonStyle.green, row=1)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Confirming', ephemeral=True)
        self.value = True
        self.stop()

    async def set_selected(self, interaction: discord.Interaction, item_id: int):
        self.selected = item_id
        await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        else:
            emb = discord.Embed(
                description=f"Only the author of the command can perform this action.",
                color=16711680
            )
            await interaction.response.send_message(embed=emb, ephemeral=True)
            return False
    
    async def on_timeout(self):
        # remove buttons on timeout
        message = await self.interaction.original_response()
        await message.edit(view=None)

class Dropdown(discord.ui.Select):
    
    def __init__(self):
        options = [
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.SPAM_SCORE], description='Who is the biggest spammer?', emoji='📢', value=RankingType.SPAM_SCORE),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.SLAP], description='Who slapped the most users?', emoji='✋', value=RankingType.SLAP),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.PET], description='Who petted the most users?', emoji='🥰', value=RankingType.PET),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.FART], description='Who farted on the most users?', emoji='💩', value=RankingType.FART),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.SLAP_RECIEVED], description='Who was slapped the most?', emoji='💢', value=RankingType.SLAP_RECIEVED),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.PET_RECIEVED], description='Who was petted the most?', emoji='💜', value=RankingType.PET_RECIEVED),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.FART_RECIEVED], description='Who was farted on the most?', emoji='💀', value=RankingType.FART_RECIEVED),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.JAIL_TOTAL], description='Who spent the most time in jail?', emoji='⏲', value=RankingType.JAIL_TOTAL),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.JAIL_COUNT], description='Who has the most jail sentences?', emoji='🏛', value=RankingType.JAIL_COUNT),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.TIMEOUT_TOTAL], description='Who spent the most time in timeout?', emoji='⏰', value=RankingType.TIMEOUT_TOTAL),
            discord.SelectOption(label=RankingEmbed.TITLES[RankingType.TIMEOUT_COUNT], description='Who has the most timeouts?', emoji='🔁', value=RankingType.TIMEOUT_COUNT)
        ]

        super().__init__(placeholder='Select an item.', min_values=1, max_values=1, options=options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        view: ShopMenu = self.view
        
        if await view.interaction_check(interaction):
            await view.set_selected(interaction, int(self.values[0]))