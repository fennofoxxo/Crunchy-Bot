import discord
from combat.gear.droppable import Droppable, DroppableBase
from combat.gear.types import Base, EquipmentSlot, Rarity
from combat.skills.types import SkillEffect, SkillType


class BaseSkill(DroppableBase):

    DEFAULT_IMAGE_PATH = "img/skills/"
    DEFAULT_IMAGE_NAME = {
        SkillEffect.PHYSICAL_DAMAGE: "physical.png",
        SkillEffect.MAGICAL_DAMAGE: "magical.png",
        SkillEffect.HEALING: "healing.png",
    }

    def __init__(
        self,
        name: str,
        skill_type: SkillType,
        description: str,
        information: str,
        skill_effect: SkillEffect,
        cooldown: int,
        scaling: float,
        min_level: int = 1,
        max_level: int = 99,
        droppable: bool = True,
        hits: int = 1,
        stacks: int = None,
        reset_after_encounter: bool = False,
        weight: int = 100,
        image: str = None,
        image_path: str = None,
    ):
        super().__init__(
            base_type=Base.SKILL,
            slot=EquipmentSlot.SKILL,
            type=skill_type,
            min_level=min_level,
            max_level=max_level,
            weight=weight,
            droppable=droppable,
        )
        self.name = name
        self.skill_type = skill_type
        self.description = description
        self.information = information
        self.skill_effect = skill_effect
        self.cooldown = cooldown
        self.scaling = scaling
        self.hits = hits
        self.stacks = stacks
        self.reset_after_encounter = reset_after_encounter
        self.image = image
        self.image_path = image_path

        if self.image is None:
            self.image = self.DEFAULT_IMAGE_NAME[self.skill_effect]

        self.attachment_name = f"{self.type.name}_{self.image}"

        if self.image_path is None:
            self.image_path = self.DEFAULT_IMAGE_PATH


class Skill(Droppable):

    BASE_LOOT_SKILLS = [
        SkillType.SECOND_WIND,
        SkillType.GIGA_BONK,
        SkillType.FIRE_BALL,
    ]

    EFFECT_COLOR_MAP = {
        SkillEffect.PHYSICAL_DAMAGE: discord.Color(int("F5A9B8", 16)),
        SkillEffect.MAGICAL_DAMAGE: discord.Color(int("5BCEFA", 16)),
        SkillEffect.HEALING: discord.Color.green(),
    }

    EFFECT_LABEL_MAP = {
        SkillEffect.PHYSICAL_DAMAGE: "Damage",
        SkillEffect.MAGICAL_DAMAGE: "Damage",
        SkillEffect.HEALING: "Healing",
    }

    RARITY_SORT_MAP = {
        Rarity.DEFAULT: 0,
        Rarity.NORMAL: 1,
        Rarity.MAGIC: 2,
        Rarity.RARE: 3,
        Rarity.LEGENDARY: 4,
        Rarity.UNIQUE: 5,
    }

    EFFECT_SORT_MAP = {
        SkillEffect.PHYSICAL_DAMAGE: 0,
        SkillEffect.MAGICAL_DAMAGE: 1,
        SkillEffect.HEALING: 2,
    }

    def __init__(
        self,
        base_skill: BaseSkill,
        rarity: Rarity,
        level: int,
        locked: bool = False,
        id: int = None,
    ):
        super().__init__(
            name=base_skill.name,
            base=base_skill,
            type=base_skill.skill_type,
            description=base_skill.description,
            information=base_skill.information,
            slot=EquipmentSlot.SKILL,
            level=level,
            rarity=rarity,
            scaling=base_skill.scaling,
            image=base_skill.image,
            image_path=base_skill.image_path,
        )
        self.locked = locked
        self.base_skill = base_skill
        self.id = id

        if self.image is None:
            self.image = self.DEFAULT_IMAGE_NAME

        if self.image_path is None:
            self.image_path = self.DEFAULT_IMAGE_PATH

    def get_embed(
        self,
        show_data: bool = True,
        show_info: bool = False,
        equipped: bool = False,
        show_locked_state: bool = False,
        max_width: int = 44,
    ) -> discord.Embed:
        # color = self.EFFECT_COLOR_MAP[self.base_skill.skill_effect]
        color = self.RARITY_COLOR_HEX_MAP[self.rarity]

        name = f"<- {self.name} ->"
        suffix = ""
        if equipped:
            color = discord.Color.purple()
            suffix += " [EQUIPPED]"
        elif self.locked and show_locked_state:
            suffix += " [🔒]"

        info_block = "```ansi\n"
        info_block += f"{Droppable.RARITY_COLOR_MAP[self.rarity]}{name}[0m{suffix}"

        slot = self.base.slot.value
        if SkillType.is_weapon_skill(self.base_skill.skill_type):
            slot = "Weapon Skill"

        spacing = " " * (max_width - len(name) - len(slot) - len(suffix) - 2)
        info_block += f"{spacing}[{slot}]"
        info_block += "```"

        description = f'"{self.description}"'

        if len(description) < max_width:
            spacing = max_width - len(description)
            description += " " * spacing

        prefixes = []
        suffixes = []

        if show_data:
            max_len_pre = 8
            max_len_suf = 8

            # Rarity
            name = "Rarity"
            spacing = " " * (max_len_suf - len(self.rarity.value))
            rarity_line = f"{name}: {self.rarity.value}{spacing}"
            rarity_line_colored = f"{name}: {Droppable.RARITY_COLOR_MAP[self.rarity]}{self.rarity.value}[0m{spacing}"
            suffixes.append((rarity_line_colored, len(rarity_line)))

            # Item Level
            name = "Level"
            spacing = " " * (max_len_suf - len(str(self.level)))
            level_line = f"{name}: {self.level}{spacing}"
            level_line_colored = f"{name}: [32m{self.level}[0m{spacing}"
            suffixes.append((level_line_colored, len(level_line)))

            # Base Value
            name = "Power"
            spacing = " " * (max_len_pre - len(name))
            base_value_text = f"{spacing}{name}: {self.scaling}"
            base_value_text_colored = f"{spacing}{name}: [35m{self.scaling}[0m"
            prefixes.append((base_value_text_colored, len(base_value_text)))

            # Type
            name = "Type"
            spacing = " " * (max_len_pre - len(name))
            type_text = f"{spacing}{name}: {self.base_skill.skill_effect.value}"
            type_text_colored = (
                f"{spacing}{name}: [35m{self.base_skill.skill_effect.value}[0m"
            )
            prefixes.append((type_text_colored, len(type_text)))

            # Cooldown
            if self.base_skill.cooldown > 0:
                name = "Cooldown"
                spacing = " " * (max_len_pre - len(name))
                cooldown_text = f"{spacing}{name}: {self.base_skill.cooldown} Turns"
                cooldown_text_colored = (
                    f"{spacing}{name}: [35m{self.base_skill.cooldown}[0m Turns"
                )
                prefixes.append((cooldown_text_colored, len(cooldown_text)))

            # Stacks
            max_stacks = self.base_skill.stacks
            if max_stacks is not None and max_stacks > 0:
                name = "Uses"
                spacing = " " * (max_len_pre - len(name))
                stacks_text = f"{spacing}{name}: {max_stacks} Turn(s)"
                stacks_text_colored = f"{spacing}{name}: [35m{max_stacks}[0m"

                if self.base_skill.reset_after_encounter:
                    append = " (per Combat)"
                else:
                    append = " (Total)"

                stacks_text += append
                stacks_text_colored += append

                prefixes.append((stacks_text_colored, len(stacks_text)))

            info_block += "```ansi\n"

            lines = max(len(prefixes), len(suffixes))

            for line in range(lines):
                prefix = ""
                suffix = ""
                len_prefix = 0
                len_suffix = 0
                if len(prefixes) > line:
                    len_prefix = prefixes[line][1]
                    prefix = prefixes[line][0]
                if len(suffixes) > line:
                    len_suffix = suffixes[line][1]
                    suffix = suffixes[line][0]

                spacing_width = max_width - len_prefix - len_suffix
                spacing = " " * spacing_width
                info_block += f"{prefix}{spacing}{suffix}\n"

            info_block += "```"

        info_block += f"```python\n{description}```"

        if show_info:
            info_block += f"```ansi\n[37m{self.information}```"

        embed = discord.Embed(title="", description=info_block, color=color)
        embed.set_thumbnail(url=f"attachment://{self.base_skill.attachment_name}")
        return embed


class CharacterSkill:

    def __init__(
        self,
        skill: Skill,
        last_used: int,
        stacks_used: int,
        min_roll: int,
        max_roll: int,
    ):
        self.skill = skill
        self.last_used = last_used
        self.stacks_used = stacks_used
        self.min_roll = min_roll
        self.max_roll = max_roll

    def on_cooldown(self):
        if self.last_used is None or self.skill.base_skill.cooldown is None:
            return False
        return self.last_used < self.skill.base_skill.cooldown

    def stacks_left(self):
        if self.skill.base_skill.stacks is None or self.stacks_used is None:
            return None
        return self.skill.base_skill.stacks - self.stacks_used

    def get_embed(
        self,
        show_data: bool = True,
        show_full_data: bool = False,
        show_info: bool = False,
        equipped: bool = False,
        show_locked_state: bool = False,
        max_width: int = 44,
    ) -> discord.Embed:
        # color = self.skill.EFFECT_COLOR_MAP[self.skill.base_skill.skill_effect]
        color = self.skill.RARITY_COLOR_HEX_MAP[self.skill.rarity]

        if self.stacks_left() is not None and self.stacks_left() <= 0:
            color = discord.Color.dark_grey()

        suffix = ""
        if equipped:
            color = discord.Color.purple()
            suffix += " [EQUIPPED]"
        elif self.skill.locked and show_locked_state:
            suffix += " [🔒]"
        name = f"<- {self.skill.base_skill.name} ->"

        info_block = "```ansi\n"
        info_block += (
            f"{Droppable.RARITY_COLOR_MAP[self.skill.rarity]}{name}[0m{suffix}"
        )

        slot = self.skill.base_skill.slot.value
        if SkillType.is_weapon_skill(self.skill.base_skill.skill_type):
            slot = "Weapon Skill"

        spacing = " " * (max_width - len(name) - len(slot) - len(suffix) - 2)
        info_block += f"{spacing}[{slot}]"
        info_block += "```"

        description = f'"{self.skill.base_skill.description}"'

        if len(description) < max_width:
            spacing = max_width - len(description)
            description += " " * spacing

        prefixes = []
        suffixes = []

        if show_data:
            max_len_pre = 8
            max_len_suf = 8

            if show_full_data:
                # Rarity
                name = "Rarity"
                spacing = " " * (max_len_suf - len(self.skill.rarity.value))
                rarity_line = f"{name}: {self.skill.rarity.value}{spacing}"
                rarity_line_colored = f"{name}: {Droppable.RARITY_COLOR_MAP[self.skill.rarity]}{self.skill.rarity.value}[0m{spacing}"
                suffixes.append((rarity_line_colored, len(rarity_line)))

                # Item Level
                name = "Level"
                spacing = " " * (max_len_suf - len(str(self.skill.level)))
                level_line = f"{name}: {self.skill.level}{spacing}"
                level_line_colored = f"{name}: [32m{self.skill.level}[0m{spacing}"
                suffixes.append((level_line_colored, len(level_line)))

            # Damage
            caption = self.skill.EFFECT_LABEL_MAP[self.skill.base_skill.skill_effect]
            spacing = " " * (max_len_pre - len(caption))
            damage_text = f"{spacing}{caption}: {self.min_roll} - {self.max_roll}"
            damage_text_colored = f"{spacing}{caption}: [35m{self.min_roll}[0m - [35m{self.max_roll}[0m"
            prefixes.append((damage_text_colored, len(damage_text)))

            # Type
            name = "Type"
            spacing = " " * (max_len_pre - len(name))
            type_text = f"{spacing}{name}: {self.skill.base_skill.skill_effect.value}"
            type_text_colored = (
                f"{spacing}{name}: [35m{self.skill.base_skill.skill_effect.value}[0m"
            )
            prefixes.append((type_text_colored, len(type_text)))

            # Cooldown
            if self.skill.base_skill.cooldown > 0:
                name = "Cooldown"
                spacing = " " * (max_len_pre - len(name))
                cooldown_text = (
                    f"{spacing}{name}: {self.skill.base_skill.cooldown} Turns"
                )
                cooldown_text_colored = (
                    f"{spacing}{name}: [35m{self.skill.base_skill.cooldown}[0m Turns"
                )
                prefixes.append((cooldown_text_colored, len(cooldown_text)))

            # Stacks
            max_stacks = self.skill.base_skill.stacks
            if max_stacks is not None and max_stacks > 0:
                name = "Uses"
                spacing = " " * (max_len_pre - len(name))

                if self.skill.base_skill.reset_after_encounter:
                    stacks_text = f"{spacing}{name}: {max_stacks}"
                    stacks_text_colored = f"{spacing}{name}: [35m{max_stacks}[0m"
                    append = " (per Combat)"
                else:
                    stacks_text = f"{spacing}{name}: {self.stacks_left()}/{max_stacks}"
                    stacks_text_colored = f"{spacing}{name}: [35m{self.stacks_left()}[0m/[35m{max_stacks}[0m"
                    append = " (Total)"

                stacks_text += append
                stacks_text_colored += append

                prefixes.append((stacks_text_colored, len(stacks_text)))

            info_block += "```ansi\n"

            lines = max(len(prefixes), len(suffixes))

            for line in range(lines):
                prefix = ""
                suffix = ""
                len_prefix = 0
                len_suffix = 0
                if len(prefixes) > line:
                    len_prefix = prefixes[line][1]
                    prefix = prefixes[line][0]
                if len(suffixes) > line:
                    len_suffix = suffixes[line][1]
                    suffix = suffixes[line][0]

                spacing_width = max_width - len_prefix - len_suffix
                spacing = " " * spacing_width
                info_block += f"{prefix}{spacing}{suffix}\n"

            cooldown_info = ""
            if self.skill.base_skill.cooldown > 0 and self.on_cooldown():
                cooldown_remaining = self.skill.base_skill.cooldown - self.last_used
                cooldown_info = f"\navailable in [35m{cooldown_remaining}[0m turn(s)"

            info_block += f"{cooldown_info}```"

        info_block += f"```python\n{description}```"

        if show_info:
            info_block += f"```ansi\n[37m{self.skill.base_skill.information}```"

        embed = discord.Embed(title="", description=info_block, color=color)
        embed.set_thumbnail(url=f"attachment://{self.skill.base_skill.attachment_name}")
        return embed

    def add_to_embed(
        self,
        embed: discord.Embed,
        show_info: bool = False,
        show_data: bool = False,
        max_width: int = 45,
    ) -> None:
        title = f"> {self.skill.name} "
        description = f'"{self.skill.description}"'

        cooldown_info = ""
        if self.skill.base_skill.cooldown > 0 and self.on_cooldown():
            cooldown_remaining = self.base_skill.skill.cooldown - self.last_used
            cooldown_info = f"\navailable in [35m{cooldown_remaining}[0m turn(s)"

        if len(description) < max_width:
            spacing = max_width - len(description)
            description += " " * spacing

        prefixes = []
        suffixes = []

        info_block = f"```python\n{description}```"

        if show_data:
            # Type
            type_text = f"    Type: {self.skill.base_skill.skill_effect.value}"
            type_text_colored = (
                f"    Type: [35m{self.skill.base_skill.skill_effect.value}[0m"
            )
            prefixes.append((type_text_colored, len(type_text)))

            # Cooldoqwn
            if self.cooldown > 0:
                cooldown_text = f"Cooldown: {self.skill.base_skill.cooldown} Turn(s)"
                cooldown_text_colored = (
                    f"Cooldown: [35m{self.skill.base_skill.cooldown}[0m Turn(s)"
                )
                prefixes.append((cooldown_text_colored, len(cooldown_text)))

            # Type
            damage_text = f"Damage: {self.min_roll} - {self.max_roll}"
            damage_text_colored = (
                f"Damage: [35m{self.min_roll}[0m - [35m{self.max_roll}[0m"
            )
            suffixes.append((damage_text_colored, len(damage_text)))

            info_block += "```ansi\n"

            lines = max(len(prefixes), len(suffixes))

            for line in range(lines):
                prefix = ""
                suffix = ""
                if len(prefixes) > line:
                    len_prefix = prefixes[line][1]
                    prefix = prefixes[line][0]
                if len(suffixes) > line:
                    len_suffix = suffixes[line][1]
                    suffix = suffixes[line][0]

                spacing_width = max_width - len_prefix - len_suffix
                spacing = " " * spacing_width
                info_block += f"{prefix}{spacing}{suffix}\n"

            info_block += cooldown_info
            info_block += "```"

        if show_info:
            info_block += f"```ansi\n[37m{self.skill.base_skill.information}```"

        embed.add_field(name=title, value=info_block, inline=False)
