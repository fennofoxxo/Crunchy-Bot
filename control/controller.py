import importlib

from discord.ext import commands

from control.logger import BotLogger
from control.service import Service
from control.view.view_controller import ViewController
from datalayer.database import Database
from events.bot_event import BotEvent
from events.ui_event import UIEvent
from view.view_menu import ViewMenu


class Controller:

    def __init__(
        self,
        bot: commands.Bot,
        logger: BotLogger,
        database: Database,
    ):
        self.bot = bot
        self.logger = logger
        self.database = database

        self.services: list[Service] = []
        self.view_controllers: list[ViewController] = []
        self.views: list[ViewMenu] = []

    def register_view(self, view: ViewMenu):
        class_name = view.controller_class
        module_name = view.controller_module
        controller_class = getattr(
            importlib.import_module("control.view." + module_name), class_name
        )
        self.views.append(view)
        self.add_view_controller(controller_class)

    def detach_view(self, view: ViewMenu):
        if view in self.views:
            self.views.remove(view)

    async def dispatch_event(self, event: BotEvent):
        for service in self.services:
            await service.listen_for_event(event)
        for view_controller in self.view_controllers:
            await view_controller.listen_for_event(event)

    async def dispatch_ui_event(self, event: UIEvent):
        for view_controller in self.view_controllers:
            await view_controller.listen_for_ui_event(event)
        for view in self.views:
            await view.listen_for_ui_event(event)

    def get_service(self, service_class: type[Service]) -> Service:
        for service in self.services:
            if isinstance(service, service_class):
                return service

        new_service = service_class(self.bot, self.logger, self.database, self)
        self.services.append(new_service)
        return new_service

    def add_view_controller(self, controller: type[ViewController]) -> ViewController:
        for view_controller in self.view_controllers:
            if isinstance(view_controller, controller):
                return

        new_controller = controller(self.bot, self.logger, self.database, self)
        self.view_controllers.append(new_controller)