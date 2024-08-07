from collections import Counter
from functools import lru_cache

import discord
from combat.enemies.enemy import Enemy
from combat.equipment import CharacterEquipment
from combat.gear.types import CharacterAttribute, GearModifierType
from combat.skills.skill import Skill
from combat.skills.status_effect import ActiveStatusEffect
from combat.skills.types import SkillType
from config import Config


class Actor:

    def __init__(
        self,
        id: int,
        name: str,
        max_hp: int,
        initiative: int,
        is_enemy: bool,
        skills: list[Skill],
        skill_cooldowns: dict[SkillType, int],
        skill_stacks_used: dict[SkillType, int],
        status_effects: list[ActiveStatusEffect],
        defeated: bool,
        image_url: str,
        leaving: bool = False,
        is_out: bool = False,
    ):
        self.id = id
        self.name = name
        self.max_hp = max_hp
        self.initiative = initiative
        self.is_enemy = is_enemy
        self.skills = skills
        self.skill_cooldowns = skill_cooldowns
        self.skill_stacks_used = skill_stacks_used
        self.status_effects = status_effects
        self.defeated = defeated
        self.leaving = leaving
        self.is_out = is_out
        self.image_url = image_url

    def get_encounter_scaling(self, combatant_count: int = 1) -> float:
        pass


class Character(Actor):

    def __init__(
        self,
        member: discord.Member,
        skill_slots: dict[int, Skill],
        skill_cooldowns: dict[SkillType, int],
        skill_stacks_used: dict[int, int],
        status_effects: list[ActiveStatusEffect],
        equipment: CharacterEquipment,
        defeated: bool,
        leaving: bool = False,
        is_out: bool = False,
    ):
        self.member = member
        self.equipment = equipment
        max_hp = self.equipment.attributes[CharacterAttribute.MAX_HEALTH]
        initiative = (
            Config.CHARACTER_BASE_INITIATIVE
            + self.equipment.gear_modifiers[GearModifierType.DEXTERITY]
        )
        self.skill_slots = skill_slots
        super().__init__(
            id=member.id,
            name=member.display_name,
            max_hp=max_hp,
            initiative=initiative,
            is_enemy=False,
            skills=[skill for skill in skill_slots.values() if skill is not None],
            skill_cooldowns=skill_cooldowns,
            skill_stacks_used=skill_stacks_used,
            status_effects=status_effects,
            defeated=defeated,
            leaving=leaving,
            is_out=is_out,
            image_url=member.display_avatar.url,
        )


class Opponent(Actor):

    def __init__(
        self,
        id: int,
        enemy: Enemy,
        level: int,
        max_hp: int,
        skills: list[Skill],
        skill_cooldowns: dict[SkillType, int],
        skill_stacks_used: dict[int, int],
        status_effects: list[ActiveStatusEffect],
        defeated: bool,
    ):
        super().__init__(
            id=None,
            name=enemy.name,
            max_hp=max_hp,
            initiative=enemy.initiative,
            is_enemy=True,
            skills=skills,
            skill_cooldowns=skill_cooldowns,
            skill_stacks_used=skill_stacks_used,
            status_effects=status_effects,
            defeated=defeated,
            image_url=enemy.image_url,
        )
        self.level = level
        self.enemy = enemy
        self.id = id

        self.average_skill_multi = self.get_potency_per_turn()

    @lru_cache(maxsize=10)  # noqa: B019
    def get_potency_per_turn(self):
        sorted_skills = sorted(
            self.skills, key=lambda x: x.base_skill.base_value, reverse=True
        )

        max_depth = 1
        cooldowns: dict[SkillType, int] = {}
        initial_state: dict[SkillType, int] = {}

        for skill in sorted_skills:
            cooldowns[skill.base_skill.type] = skill.base_skill.cooldown
            initial_state[skill.base_skill.type] = 0
            max_depth *= skill.base_skill.cooldown + 1

        state_list: list[dict[SkillType, int]] = []
        skill_count = Counter()

        def get_rotation(
            state_list: list[dict[SkillType, int]],
            skill_count: Counter,
            state: dict[SkillType, int],
            depth_check: int,
        ) -> list[dict[SkillType, int]]:
            if state in state_list or depth_check <= 0:
                return

            state_list.append(state)

            next_state: dict[SkillType, int] = {}

            skills_chosen = 0

            for skill_type, cooldown in state.items():
                if cooldown <= 0 and skills_chosen < self.enemy.actions_per_turn:
                    next_state[skill_type] = cooldowns[skill_type]
                    skill_count[skill_type] += 1
                    skills_chosen += 1
                    continue

                next_state[skill_type] = max(0, cooldown - 1)

            if skills_chosen == 0:
                raise StopIteration("No available skill found.")

            get_rotation(state_list, skill_count, next_state, (depth_check - 1))

        get_rotation(state_list, skill_count, initial_state, max_depth)

        rotation_length = len(state_list)
        potency = 0

        for skill in sorted_skills:
            base_potency = skill.base_skill.base_value * skill.base_skill.hits
            potency_per_turn = (
                base_potency
                * skill_count[skill.base_skill.skill_type]
                / rotation_length
            )
            potency += potency_per_turn

        return potency
