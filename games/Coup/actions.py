
from games.game_interface import Game


class Challenge(Game.Action):

    async def validate(self, game, sid, target=None) -> bool:
        return game.current_action is not None

    async def activate(self, game, sid, target=None):
        await game.challenge(sid, target)


class Income(Game.Action):

    async def validate(self, game, sid, target=None) -> bool:
        return game.current_action is None \
               and game.players[sid]['coins'] < 10

    async def activate(self, game, sid, target=None):
        game.players[sid]['coins'] += 1


class ForeignAid(Game.Action):

    async def validate(self, game, sid, target=None) -> bool:
        return game.current_action is None \
               and game.players[sid].state['coins'] < 10

    async def activate(self, game, sid, target=None):
        game.players[sid].state['coins'] += 2


class Coup(Game.Action):

    async def validate(self, game, sid, target=None) -> bool:
        return game.current_action is None \
               and game.players[sid].state['coins'] >= 7

    async def activate(self, game, sid, target=None):
        game.players[sid].state['coins'] -= 7
        await game.kill(target)


class Duke(Game.Action):

    async def validate(self, game, sid, target=None):
        return (game.current_action is None and game.players[sid].state['coins'] < 10) \
               or isinstance(game.current_action, ForeignAid)

    async def activate(self, game, sid, target=None):
        if isinstance(game.current_action, Duke):
            game.players[sid].state['coins'] += 3
        elif isinstance(game.current_action, ForeignAid):
            await game.block(sid, target, Duke)


class Contessa(Game.Action):

    async def validate(self, game, sid, target=None) -> bool:
        return isinstance(game.actions[-1], Assassin)

    async def activate(self, game, sid, target=None):
        if isinstance(game.current_action, Assassin):
            await game.block(sid, target, Contessa)


class Captain(Game.Action):

    async def validate(self, game, sid, target=None):
        return (game.current_action is None and game.players[sid].state['coins'] < 10) \
               or isinstance(game.current_action, Captain)

    async def activate(self, game, sid, target=None):
        if isinstance(game.current_action, Captain):
            amount = min(2, game.players[target].state['coins'])
            game.players[target].state['coins'] -= amount
            game.players[sid].state['coins'] += amount
        #if isinstance(game.current_action, Captain):
        #    await game.block(sid, target, Captain)


class Assassin(Game.Action):

    async def validate(self, game, sid, target=None):
        return game.current_action is None and 3 <= game.players[sid].state['coins'] < 10

    async def activate(self, game, sid, target=None):
        game.players[sid].state['coins'] -= 3
        await game.kill(target)


class Ambassador(Game.Action):

    async def validate(self, game, sid, target=None):
        return game.current_action is None \
               or isinstance(game.current_action, Captain) \
               or isinstance(game.current_action, Ambassador)

    async def activate(self, game, sid, target=None):
        if isinstance(game.current_action, Ambassador):
            await game.swap(sid, 2)
        elif isinstance(game.current_action, Captain):
            await game.block(sid, target, Ambassador)
