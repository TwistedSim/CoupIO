import importlib
import pkgutil
import inspect

from client import bots
from client.bot_interface import BotInterface


def iter_namespace(ns_pkg):
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


def extract_bots(bot_module):
    return [obj for name, obj in inspect.getmembers(bot_module) if inspect.isclass(obj)]


def auto_discover_bots():

    discovered_bot_files = {
        name: importlib.import_module(name)
        for finder, name, ispkg
        in iter_namespace(bots)
    }

    discovered_bots = {}
    for name, module in discovered_bot_files.items():
        for bot in extract_bots(module):
            if issubclass(bot, BotInterface):
                if bot.__name__ in discovered_bots:
                    print(f"WARNING: 2 bots with the same name existed ({bot.__name__} in file {name}).")
                discovered_bots[bot.__name__] = bot

    return discovered_bots
