import asyncio
import datetime
import importlib
import random

import discord
from combat.actors import Actor, Character
from combat.encounter import Encounter, EncounterContext, TurnData
from combat.enemies import *  # noqa: F403
from combat.enemies.types import EnemyType
from combat.skills.skill import CharacterSkill, Skill
from combat.skills.types import (
    SkillEffect,
    SkillInstance,
    StatusEffectApplication,
    StatusEffectTrigger,
)
from config import Config
from control.combat.combat_actor_manager import CombatActorManager
from control.combat.combat_embed_manager import CombatEmbedManager
from control.combat.combat_gear_manager import CombatGearManager
from control.combat.combat_skill_manager import CombatSkillManager
from control.combat.context_loader import ContextLoader
from control.combat.object_factory import ObjectFactory
from control.combat.status_effect_manager import CombatStatusEffectManager
from control.controller import Controller
from control.item_manager import ItemManager
from control.logger import BotLogger
from control.service import Service
from control.settings_manager import SettingsManager
from control.types import ControllerModuleMap
from datalayer.database import Database
from discord.ext import commands
from events.bot_event import BotEvent
from events.combat_event import CombatEvent
from events.encounter_event import EncounterEvent
from events.inventory_event import InventoryEvent
from events.types import (
    CombatEventType,
    EncounterEventType,
    EventType,
    UIEventType,
)
from events.ui_event import UIEvent
from view.combat.combat_turn_view import CombatTurnView
from view.combat.embed import EnemyOverviewEmbed
from view.combat.engage_view import EnemyEngageView
from view.combat.grace_period import GracePeriodView
from view.combat.leave_view import EncounterLeaveView


class EncounterManager(Service):

    def __init__(
        self,
        bot: commands.Bot,
        logger: BotLogger,
        database: Database,
        controller: Controller,
    ):
        super().__init__(bot, logger, database)
        self.controller = controller
        self.settings_manager: SettingsManager = self.controller.get_service(
            SettingsManager
        )
        self.item_manager: ItemManager = self.controller.get_service(ItemManager)
        self.skill_manager: CombatSkillManager = self.controller.get_service(
            CombatSkillManager
        )
        self.actor_manager: CombatActorManager = self.controller.get_service(
            CombatActorManager
        )
        self.embed_manager: CombatEmbedManager = self.controller.get_service(
            CombatEmbedManager
        )
        self.gear_manager: CombatGearManager = self.controller.get_service(
            CombatGearManager
        )
        self.status_effect_manager: CombatStatusEffectManager = (
            self.controller.get_service(CombatStatusEffectManager)
        )
        self.context_loader: ContextLoader = self.controller.get_service(ContextLoader)
        self.factory: ObjectFactory = self.controller.get_service(ObjectFactory)
        self.log_name = "Encounter"

    async def listen_for_event(self, event: BotEvent):
        match event.type:
            case EventType.ENCOUNTER:
                if not event.synchronized:
                    return
                encounter_event: EncounterEvent = event
                match encounter_event.encounter_event_type:
                    case EncounterEventType.NEW_ROUND:
                        await self.refresh_encounter_thread(
                            encounter_event.encounter_id
                        )
                    case EncounterEventType.INITIATE:
                        await self.initiate_encounter(encounter_event.encounter_id)
                    case EncounterEventType.MEMBER_ENGAGE:
                        await self.add_member_to_encounter(
                            encounter_event.encounter_id, encounter_event.member_id
                        )
                    case EncounterEventType.ENEMY_DEFEAT:
                        await self.update_guild_status(event.guild_id)

            case EventType.COMBAT:
                combat_event: CombatEvent = event
                if not event.synchronized:
                    return
                if combat_event.combat_event_type not in [
                    CombatEventType.ENEMY_END_TURN,
                    CombatEventType.MEMBER_END_TURN,
                    CombatEventType.ENEMY_TURN,
                ]:
                    return
                await self.refresh_encounter_thread(combat_event.encounter_id)

    async def create_encounter(
        self, guild_id: int, enemy_type: EnemyType = None, level: int = None
    ):
        max_encounter_level = await self.database.get_guild_level(guild_id)
        min_encounter_level = max(
            1, int(max_encounter_level * Config.ENCOUNTER_MIN_LVL_SCALING)
        )

        if level is not None:
            encounter_level = min(max_encounter_level, level)
        else:
            encounter_level = random.randint(min_encounter_level, max_encounter_level)

        if enemy_type is not None:
            enemy = await self.factory.get_enemy(enemy_type)
            if not (
                encounter_level >= enemy.min_level
                and encounter_level <= enemy.max_level
            ):
                raise TypeError
        else:
            enemies = [
                await self.factory.get_enemy(enemy_type) for enemy_type in EnemyType
            ]
            possible_enemies = [
                enemy
                for enemy in enemies
                if encounter_level >= enemy.min_level
                and encounter_level <= enemy.max_level
                and not enemy.is_boss
            ]

            spawn_weights = [enemy.weighting for enemy in possible_enemies]
            spawn_weights = [1.0 / w for w in spawn_weights]
            sum_weights = sum(spawn_weights)
            spawn_weights = [w / sum_weights for w in spawn_weights]

            enemy = random.choices(possible_enemies, weights=spawn_weights)[0]

        effective_encounter_level = encounter_level
        if enemy.is_boss:
            effective_encounter_level += 1

        roll = random.uniform(0.95, 1.05)
        enemy_health = (
            enemy.health
            * Config.ENEMY_HEALTH_SCALING[effective_encounter_level]
            * Config.AVERAGE_PLAYER_POTENCY
        )
        enemy_health *= pow(
            Config.ENEMY_HEALTH_LVL_FALLOFF, (encounter_level - enemy.min_level)
        )
        enemy_health *= roll

        return Encounter(guild_id, enemy.type, encounter_level, enemy_health)

    async def spawn_encounter(
        self,
        guild: discord.Guild,
        channel_id: int,
        enemy_type: EnemyType = None,
        level: int = None,
    ):
        log_message = f"Encounter was spawned in {guild.name}."
        self.logger.log(guild.id, log_message, cog=self.log_name)

        encounter = await self.create_encounter(
            guild.id, enemy_type=enemy_type, level=level
        )
        embed = await self.embed_manager.get_spawn_embed(encounter)

        enemy = await self.factory.get_enemy(encounter.enemy_type)
        view = EnemyEngageView(self.controller, enemy)
        channel = guild.get_channel(channel_id)

        message = await channel.send("", embed=embed, view=view)
        encounter.message_id = message.id
        encounter.channel_id = message.channel.id

        encounter_id = await self.database.log_encounter(encounter)

        view.set_message(message)
        await view.refresh_ui(embed=embed, encounter_id=encounter_id)

        event = EncounterEvent(
            datetime.datetime.now(),
            guild.id,
            encounter_id,
            self.bot.user.id,
            EncounterEventType.SPAWN,
        )
        await self.controller.dispatch_event(event)

    async def apply_late_join_penalty(self, encounter_id: int, member_id: int) -> str:
        encounter = await self.database.get_encounter_by_encounter_id(encounter_id)
        encounter_events = await self.database.get_encounter_events_by_encounter_id(
            encounter_id
        )
        combat_events = await self.database.get_combat_events_by_encounter_id(
            encounter_id
        )
        enemy = await self.factory.get_enemy(encounter.enemy_type)
        status_effects = await self.database.get_status_effects_by_encounter(
            encounter_id
        )
        opponent = await self.actor_manager.get_opponent(
            enemy,
            encounter.enemy_level,
            encounter.max_hp,
            encounter_events,
            combat_events,
            status_effects,
        )

        max_enemy_hp = encounter.max_hp
        current_enemy_hp = await self.actor_manager.get_actor_current_hp(
            opponent, combat_events
        )

        combat_progress = current_enemy_hp / max_enemy_hp

        if combat_progress >= 0.5:
            return ""

        if combat_progress < 0.5:
            additional_message = "You joined late, so you will get a 50% loot penalty."
            event = EncounterEvent(
                datetime.datetime.now(),
                encounter.guild_id,
                encounter.id,
                member_id,
                EncounterEventType.PENALTY50,
            )
            await self.controller.dispatch_event(event)
        elif combat_progress <= 0.25:
            additional_message = "You joined late, so you will get a 75% loot penalty."
            event = EncounterEvent(
                datetime.datetime.now(),
                encounter.guild_id,
                encounter.id,
                member_id,
                EncounterEventType.PENALTY75,
            )
            await self.controller.dispatch_event(event)

        return additional_message

    async def create_encounter_thread(
        self, encounter: Encounter, first_member_id: int
    ) -> discord.Thread:
        channel = self.bot.get_channel(encounter.channel_id)
        enemy = await self.factory.get_enemy(encounter.enemy_type)
        thread = await channel.create_thread(
            name=f"Encounter: {enemy.name}",
            type=discord.ChannelType.public_thread,
            auto_archive_duration=60,
        )

        await self.database.log_encounter_thread(
            encounter.id, thread.id, encounter.guild_id, encounter.channel_id
        )

        return thread

    async def add_member_to_encounter(self, encounter_id: int, member_id: int):
        thread_id = await self.database.get_encounter_thread(encounter_id)

        encounter = await self.database.get_encounter_by_encounter_id(encounter_id)
        thread = None
        initiate_combat = False
        new_thread = False
        additional_message = ""

        if thread_id is None:
            thread = await self.create_encounter_thread(encounter, member_id)
            initiate_combat = True
            new_thread = True
        else:
            thread = self.bot.get_channel(encounter.channel_id).get_thread(thread_id)
            additional_message = await self.apply_late_join_penalty(
                encounter_id, member_id
            )

        if thread is None:
            return

        enemy = await self.factory.get_enemy(encounter.enemy_type)
        if enemy.min_encounter_scale > 1:
            initiate_combat = False
            participants = (
                await self.database.get_encounter_participants_by_encounter_id(
                    encounter.id
                )
            )
            if len(participants) == enemy.min_encounter_scale:
                initiate_combat = True

        if new_thread and not initiate_combat:
            wait_embed = await self.embed_manager.get_waiting_for_party_embed(
                enemy.min_encounter_scale
            )
            message = await thread.send(content="", embed=wait_embed)

        if initiate_combat:
            round_embed = await self.embed_manager.get_initiation_embed()
            # will trigger the combat start on expiration
            view = GracePeriodView(self.controller, encounter)
            message = await thread.send(content="", embed=round_embed, view=view)
            view.set_message(message)

        user = self.bot.get_guild(encounter.guild_id).get_member(member_id)
        await thread.add_user(user)

        embed = self.embed_manager.get_actor_join_embed(
            user, additional_message=additional_message
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await thread.send("", embed=embed)

        encounters = await self.database.get_encounter_participants(encounter.guild_id)
        enemy = await self.factory.get_enemy(encounter.enemy_type)
        max_encounter_size = enemy.max_players
        if len(encounters[encounter.id]) >= max_encounter_size:
            event = UIEvent(UIEventType.COMBAT_FULL, encounter.id)
            await self.controller.dispatch_ui_event(event)

    async def skip_turn(
        self,
        actor: Actor,
        context: EncounterContext,
        reason: str,
        timeout: bool = False,
        silent: bool = False,
    ):
        if not silent:
            embed = self.embed_manager.get_turn_skip_embed(actor, reason, context)
            await self.context_loader.append_embed_to_round(context, embed)

        combat_event_type = CombatEventType.MEMBER_END_TURN
        if actor.is_enemy:
            combat_event_type = CombatEventType.ENEMY_END_TURN

        if timeout:
            event = CombatEvent(
                datetime.datetime.now(),
                context.encounter.guild_id,
                context.encounter.id,
                actor.id,
                actor.id,
                None,
                None,
                None,
                CombatEventType.MEMBER_TURN_SKIP,
            )
            await self.controller.dispatch_event(event)

        event = CombatEvent(
            datetime.datetime.now(),
            context.encounter.guild_id,
            context.encounter.id,
            actor.id,
            actor.id,
            None,
            None,
            None,
            combat_event_type,
        )
        await self.controller.dispatch_event(event)

    async def opponent_turn(self, context: EncounterContext):
        opponent = context.opponent

        context = await self.handle_turn_status_effects(
            context, opponent, StatusEffectTrigger.START_OF_TURN
        )

        if context.is_concluded():
            await self.refresh_encounter_thread(context.encounter.id)
            return

        controller_type = opponent.enemy.controller
        controller_class = getattr(
            importlib.import_module(
                "control.combat.enemy."
                + ControllerModuleMap.get_module(controller_type)
            ),
            controller_type,
        )
        enemy_controller = self.controller.get_service(controller_class)

        await enemy_controller.handle_turn(context)

        await self.handle_turn_status_effects(
            context, opponent, StatusEffectTrigger.END_OF_TURN
        )

        event = CombatEvent(
            datetime.datetime.now(),
            context.encounter.guild_id,
            context.encounter.id,
            opponent.id,
            None,
            None,
            None,
            None,
            CombatEventType.ENEMY_END_TURN,
        )
        await self.controller.dispatch_event(event)

    async def handle_turn_status_effects(
        self,
        context: EncounterContext,
        actor: Actor,
        trigger: StatusEffectTrigger,
    ):
        context = await self.context_loader.load_encounter_context(context.encounter.id)

        for active_actor in context.get_current_initiative():
            if active_actor.id == actor.id:
                actor = active_actor

        triggered_status_effects = await self.status_effect_manager.actor_trigger(
            context, actor, trigger
        )

        if len(triggered_status_effects) <= 0:
            return context

        effect_data = await self.status_effect_manager.handle_status_effects(
            context, actor, triggered_status_effects
        )

        if len(effect_data) > 0:
            status_effect_embed = self.embed_manager.get_status_effect_embed(
                actor, effect_data
            )
            await self.context_loader.append_embed_to_round(
                context, status_effect_embed
            )

        context = await self.context_loader.load_encounter_context(context.encounter.id)

        if not context.new_turn():
            await self.refresh_encounter_thread(context.encounter.id)

        return context

    async def calculate_character_aoe_skill(
        self,
        context: EncounterContext,
        skill: Skill,
        source: Character,
        available_targets: list[Actor],
    ) -> tuple[list[tuple[Actor, SkillInstance, float], discord.Embed]]:
        damage_data = []

        effect_modifier, post_embed = (
            await self.status_effect_manager.handle_attack_status_effects(
                context, source, skill
            )
        )
        for target in available_targets:
            instances = await self.skill_manager.get_skill_effect(
                source, skill, combatant_count=context.get_combat_scale()
            )
            instance = instances[0]
            instance.apply_effect_modifier(effect_modifier)

            current_hp = await self.actor_manager.get_actor_current_hp(
                target, context.combat_events
            )

            total_damage = await self.actor_manager.get_skill_damage_after_defense(
                target, skill, instance.scaled_value
            )

            if skill.base_skill.skill_effect == SkillEffect.HEALING:
                total_damage *= -1

            new_target_hp = min(max(0, current_hp - total_damage), target.max_hp)

            damage_data.append((target, instance, new_target_hp))
        return damage_data, post_embed

    async def calculate_character_skill(
        self,
        context: EncounterContext,
        skill: Skill,
        source: Character,
        target: Actor,
    ) -> tuple[list[tuple[Actor, SkillInstance, float], discord.Embed]]:
        skill_instances = await self.skill_manager.get_skill_effect(
            source, skill, combatant_count=context.get_combat_scale()
        )

        skill_value_data = []
        hp_cache = {}

        for instance in skill_instances:
            effect_modifier, post_embed = (
                await self.status_effect_manager.handle_attack_status_effects(
                    context,
                    source,
                    skill,
                )
            )
            instance.apply_effect_modifier(effect_modifier)

            total_skill_value = await self.actor_manager.get_skill_damage_after_defense(
                target, skill, instance.scaled_value
            )

            target_id = target.id
            if target_id is None:
                target_id = -1

            if target_id not in hp_cache:
                hp_cache[target_id] = await self.actor_manager.get_actor_current_hp(
                    target, context.combat_events
                )

            current_hp = hp_cache[target_id]

            if skill.base_skill.skill_effect != SkillEffect.HEALING:
                total_skill_value *= -1

            new_target_hp = min(max(0, current_hp + total_skill_value), target.max_hp)
            hp_cache[target_id] = new_target_hp

            skill_value_data.append((target, instance, new_target_hp))

        return skill_value_data, post_embed

    async def combatant_turn(
        self,
        context: EncounterContext,
        character: Character,
        skill_data: CharacterSkill,
        target: Actor = None,
    ):
        context = await self.handle_turn_status_effects(
            context, character, StatusEffectTrigger.START_OF_TURN
        )

        if context.is_concluded():
            await self.refresh_encounter_thread(context.encounter.id)
            return

        if target is None:
            target = await self.skill_manager.get_character_default_target(
                character, skill_data.skill, context
            )

        if skill_data.skill.base_skill.aoe:
            # assumes party targeted
            damage_data, post_embed = await self.calculate_character_aoe_skill(
                context, skill_data.skill, character, context.get_active_combatants()
            )
        else:
            damage_data, post_embed = await self.calculate_character_skill(
                context, skill_data.skill, character, target
            )

        turn = TurnData(
            actor=character,
            skill=skill_data.skill,
            damage_data=damage_data,
            post_embed=post_embed,
        )

        await self.context_loader.append_embed_generator_to_round(
            context, self.embed_manager.handle_actor_turn_embed(turn, context)
        )

        if turn.post_embed is not None:
            await self.context_loader.append_embed_to_round(context, turn.post_embed)

        for target, damage_instance, _ in turn.damage_data:
            total_damage = await self.actor_manager.get_skill_damage_after_defense(
                target, turn.skill, damage_instance.scaled_value
            )

            await self.status_effect_manager.handle_post_attack_status_effects(
                context,
                character,
                target,
                skill_data.skill,
                damage_instance,
            )

            for skill_status_effect in turn.skill.base_skill.status_effects:
                application_value = None
                match skill_status_effect.application:
                    case StatusEffectApplication.ATTACK_VALUE:
                        application_value = damage_instance.value
                    case StatusEffectApplication.DEFAULT:
                        pass

                status_effect_target = target
                if skill_status_effect.self_target:
                    status_effect_target = character

                await self.status_effect_manager.apply_status(
                    context,
                    character,
                    status_effect_target,
                    skill_status_effect.status_effect_type,
                    skill_status_effect.stacks,
                    application_value,
                )

            event = CombatEvent(
                datetime.datetime.now(),
                context.encounter.guild_id,
                context.encounter.id,
                character.id,
                target.id,
                skill_data.skill.base_skill.skill_type,
                total_damage,
                skill_data.skill.id,
                CombatEventType.MEMBER_TURN,
            )
            await self.controller.dispatch_event(event)

        await self.handle_turn_status_effects(
            context, character, StatusEffectTrigger.END_OF_TURN
        )

        event = CombatEvent(
            datetime.datetime.now(),
            context.encounter.guild_id,
            context.encounter.id,
            character.id,
            None,
            None,
            None,
            None,
            CombatEventType.MEMBER_END_TURN,
        )
        await self.controller.dispatch_event(event)

    async def combatant_timeout(
        self,
        context: EncounterContext,
        character: Character,
    ):
        timeout_count = context.get_timeout_count(character.id)
        message = (
            f"{character.name} was inactive for too long, their turn will be skipped."
        )
        timeout_count += 1

        if timeout_count >= Config.TIMEOUT_COUNT_LIMIT:
            event = EncounterEvent(
                datetime.datetime.now(),
                context.encounter.guild_id,
                context.encounter.id,
                character.id,
                EncounterEventType.MEMBER_OUT,
            )
            await self.controller.dispatch_event(event)
            message += f" They reached {Config.TIMEOUT_COUNT_LIMIT} total timeouts and will be excluded from the fight."

        await self.skip_turn(character, context, message, timeout=True)

    async def conclude_encounter(self, context: EncounterContext, success: bool = True):

        if success:
            embed = await self.embed_manager.get_combat_success_embed(context)
        else:
            embed = await self.embed_manager.get_combat_failed_embed(context)

        await context.thread.send("", embed=embed)

        event = EncounterEvent(
            datetime.datetime.now(),
            context.encounter.guild_id,
            context.encounter.id,
            self.bot.user.id,
            EncounterEventType.END,
        )
        await self.controller.dispatch_event(event)

        if success:
            await self.payout_loot(context)

    async def payout_loot(self, context: EncounterContext):
        loot = await self.gear_manager.roll_enemy_loot(context)

        now = datetime.datetime.now()

        for member, member_loot in loot.items():

            await asyncio.sleep(1)
            # beans = member_loot[0]
            beans = 0
            embeds = []
            loot_head_embed = await self.embed_manager.get_loot_embed(member, beans)
            embeds.append(loot_head_embed)

            message = await context.thread.send(f"<@{member.id}>", embeds=embeds)

            # event = BeansEvent(
            #     now,
            #     member.guild.id,
            #     BeansEventType.COMBAT_LOOT,
            #     member.id,
            #     beans,
            # )
            # await self.controller.dispatch_event(event)

            for drop in member_loot[1]:
                embeds.append(drop.get_embed())
                await asyncio.sleep(1)
                await message.edit(embeds=embeds)

            item = member_loot[2]
            if item is not None:
                embeds.append(item.get_embed(self.bot, show_price=False))

                await asyncio.sleep(1)

                await message.edit(embeds=embeds)

                event = InventoryEvent(
                    now,
                    member.guild.id,
                    member.id,
                    item.type,
                    1,
                )
                await self.controller.dispatch_event(event)

    async def context_needs_update_check(self, context: EncounterContext) -> bool:
        already_defeated = []
        update_context = False

        for event in context.encounter_events:
            match event.encounter_event_type:
                case EncounterEventType.MEMBER_DEFEAT | EncounterEventType.ENEMY_DEFEAT:
                    already_defeated.append(event.member_id)

        for actor in context.actors:
            if actor.id in already_defeated:
                continue

            health = await self.actor_manager.get_actor_current_hp(
                actor, context.combat_events
            )

            if health <= 0:
                update_context = True
                if actor.is_enemy:
                    controller_type = actor.enemy.controller
                    controller_class = getattr(
                        importlib.import_module(
                            "control.combat.enemy."
                            + ControllerModuleMap.get_module(controller_type)
                        ),
                        controller_type,
                    )
                    enemy_controller = self.controller.get_service(controller_class)

                    await enemy_controller.on_defeat(context, actor)
                    continue

                encounter_event_type = EncounterEventType.MEMBER_DEFEAT
                embed = self.embed_manager.get_actor_defeated_embed(actor)
                await context.thread.send("", embed=embed)

                event = EncounterEvent(
                    datetime.datetime.now(),
                    context.encounter.guild_id,
                    context.encounter.id,
                    actor.id,
                    encounter_event_type,
                )
                await self.controller.dispatch_event(event)

            if context.new_round() and actor.leaving:
                event = EncounterEvent(
                    datetime.datetime.now(),
                    context.encounter.guild_id,
                    context.encounter.id,
                    actor.id,
                    EncounterEventType.MEMBER_OUT,
                )
                await self.controller.dispatch_event(event)
                update_context = True

        return update_context

    async def delete_previous_combat_info(self, thread: discord.Thread):
        async for message in thread.history(limit=100):
            if len(message.embeds) == 1 and message.author.id == self.bot.user.id:
                embed = message.embeds[0]
                if embed.image.url is not None:
                    await message.delete()
                    break

    async def get_previous_enemy_info(self, thread: discord.Thread):
        async for message in thread.history(limit=100):
            if len(message.embeds) == 1 and message.author.id == self.bot.user.id:
                embed = message.embeds[0]
                if embed.image.url is not None:
                    return message
        return None

    async def initiate_encounter(self, encounter_id: int):
        encounter = await self.database.get_encounter_by_encounter_id(encounter_id)
        enemy = await self.factory.get_enemy(encounter.enemy_type)
        controller_type = enemy.controller
        controller_class = getattr(
            importlib.import_module(
                "control.combat.enemy."
                + ControllerModuleMap.get_module(controller_type)
            ),
            controller_type,
        )
        enemy_controller = self.controller.get_service(controller_class)
        await enemy_controller.intro(encounter_id)
        await self.refresh_encounter_thread(encounter_id)

    async def refresh_encounter_thread(self, encounter_id: int):
        context = await self.context_loader.load_encounter_context(encounter_id)

        if await self.context_needs_update_check(context):
            context = await self.context_loader.load_encounter_context(encounter_id)

        if context.is_concluded():
            return

        if context.opponent.defeated:
            await self.delete_previous_combat_info(context.thread)
            await self.conclude_encounter(context)
            return

        if len(context.get_active_combatants()) <= 0:
            await self.delete_previous_combat_info(context.thread)
            await self.conclude_encounter(context, success=False)
            return

        current_actor = context.get_current_actor()

        if current_actor.id == context.beginning_actor.id and not context.new_round():
            event = EncounterEvent(
                datetime.datetime.now(),
                context.encounter.guild_id,
                context.encounter.id,
                self.bot.user.id,
                EncounterEventType.NEW_ROUND,
            )
            await self.controller.dispatch_event(event)
            return

        round_message = await self.context_loader.get_previous_turn_message(
            context.thread
        )
        if round_message is not None:
            round_embeds = round_message.embeds
            cont = round_embeds[0].title == "Round Continued.."
            round_embed = await self.embed_manager.get_round_embed(context, cont=cont)
            round_embeds[0] = round_embed
            await round_message.edit(embeds=round_embeds, attachments=[])

        if not context.new_turn():
            return

        enemy_embed = await self.embed_manager.get_combat_embed(context)

        if context.new_round():
            await self.delete_previous_combat_info(context.thread)
            leave_view = EncounterLeaveView(self.controller)
            message = await context.thread.send("", embed=enemy_embed, view=leave_view)
            leave_view.set_message(message)
            round_embed = await self.embed_manager.get_round_embed(context)
            await context.thread.send(content="", embed=round_embed)
        else:
            message = await self.get_previous_enemy_info(context.thread)
            if message is not None:
                await message.edit(embed=enemy_embed)

        if current_actor.is_enemy:
            await self.opponent_turn(context)
            return

        if current_actor.defeated:
            await self.skip_turn(
                current_actor, context, f"{current_actor.name} is defeated."
            )
            return

        if current_actor.leaving:
            await self.skip_turn(
                current_actor,
                context,
                f"{current_actor.name} has left the encounter and will be removed in the next round.",
            )
            return

        if current_actor.is_out:
            await self.skip_turn(current_actor, context, "", silent=True)
            return

        enemy_embeds = await self.embed_manager.get_character_turn_embeds(context)

        view = await CombatTurnView.create(self.controller, current_actor, context)

        message = await context.thread.send(
            f"<@{current_actor.id}>", embeds=enemy_embeds, view=view
        )
        view.set_message(message)
        return

    async def update_guild_status(self, guild_id: int):
        combat_channels = await self.settings_manager.get_combat_channels(guild_id)
        guild = self.bot.get_guild(guild_id)

        guild_level = await self.database.get_guild_level(guild.id)
        progress = await self.database.get_guild_level_progress(guild.id, guild_level)
        requirement = Config.LEVEL_REQUIREMENTS[guild_level]

        if progress >= requirement:
            if (guild_level) not in Config.BOSS_LEVELS:
                guild_level += 1
                await self.database.set_guild_level(guild.id, guild_level)
            else:
                pass
                # TODO: check if boss is defeated

        for channel_id in combat_channels:
            channel = guild.get_channel(channel_id)
            if channel is None:
                continue

            async for message in channel.history(limit=1, oldest_first=True):
                if message.author != self.bot.user or message.embeds is None:
                    await self.refresh_combat_messages(guild_id)
                    return

                embed_title = message.embeds[0].title
                if embed_title[:16] != "Combat Zone":
                    await self.refresh_combat_messages(guild_id)
                    return

                guild_level = await self.database.get_guild_level(guild.id)
                progress = await self.database.get_guild_level_progress(
                    guild.id, guild_level
                )
                head_embed = EnemyOverviewEmbed(
                    self.bot.user,
                    guild_level,
                    progress,
                )
                await message.edit(embed=head_embed)
                break

    async def refresh_combat_messages(self, guild_id: int):
        combat_channels = await self.settings_manager.get_combat_channels(guild_id)

        guild = self.bot.get_guild(guild_id)

        for channel_id in combat_channels:
            channel = guild.get_channel(channel_id)
            if channel is None:
                continue

            await channel.purge()

            guild_level = await self.database.get_guild_level(guild.id)
            progress = await self.database.get_guild_level_progress(
                guild.id, guild_level
            )

            head_embed = EnemyOverviewEmbed(
                self.bot.user,
                guild_level,
                progress,
            )

            await channel.send(content="", embed=head_embed)
