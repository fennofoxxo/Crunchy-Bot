from combat.actors import Actor
from combat.encounter import EncounterContext
from combat.gear.types import Rarity
from combat.skills.skill import Skill
from combat.skills.skills import *  # noqa: F403
from combat.skills.types import SkillTarget, SkillType
from control.controller import Controller
from control.logger import BotLogger
from control.service import Service
from datalayer.database import Database
from discord.ext import commands
from events.bot_event import BotEvent


class CombatSkillManager(Service):

    CHARACTER_ENCOUNTER_SCALING_FACOTR = 0.9
    OPPONENT_ENCOUNTER_SCALING_FACTOR = 1.2
    OPPONENT_LEVEL_SCALING_FACTOR = 0.2

    def __init__(
        self,
        bot: commands.Bot,
        logger: BotLogger,
        database: Database,
        controller: Controller,
    ):
        super().__init__(bot, logger, database)
        self.controller = controller
        self.log_name = "Combat Skills"

    async def listen_for_event(self, event: BotEvent):
        pass

    async def get_weapon_skill(
        self, skill_type: SkillType, rarity: Rarity, level: int
    ) -> Skill:
        skill = globals()[skill_type]
        instance = skill()
        weapon_skill = Skill(base_skill=instance, rarity=rarity, level=level)
        return weapon_skill

    async def get_enemy_skill(self, skill_type: SkillType) -> Skill:
        skill = globals()[skill_type]
        instance = skill()
        enemy_skill = Skill(base_skill=instance, rarity=Rarity.NORMAL, level=1)
        return enemy_skill

    async def get_base_skill(self, skill_type: SkillType) -> Skill:
        skill = globals()[skill_type]
        instance = skill()
        return instance

    async def get_character_default_target(
        self, source: Actor, skill: Skill, context: EncounterContext
    ) -> Actor:

        match skill.base_skill.default_target:
            case SkillTarget.OPPONENT:
                return context.opponent
            case SkillTarget.SELF:
                return source
