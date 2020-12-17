
from games.game_interface import Game


class Challenge(Game.Action):

    """This action cannot be played directly"""

    async def validate(self, game, sid, target=None) -> bool:
        return False

    async def activate(self, game, sid, target=None):
        pass


class Income(Game.Action):

    async def validate(self, game, sid, target=None) -> bool:
        return game.players[sid].state['coins'] < 10

    async def activate(self, game, sid, target=None):
        game.players[sid].state['coins'] += 1


class ForeignAid(Game.Action):

    async def validate(self, game, sid, target=None) -> bool:
        return game.players[sid].state['coins'] < 10

    async def activate(self, game, sid, target=None):
        game.players[sid].state['coins'] += 2


class Coup(Game.Action):

    async def validate(self, game, sid, target=None) -> bool:
        return game.players[sid].state['coins'] >= 7

    async def activate(self, game, sid, target=None):
        game.players[sid].state['coins'] -= 7
        await game.kill(target)


class Duke(Game.Action):

    async def validate(self, game, sid, target=None):
        return game.players[sid].state['coins'] < 10

    async def activate(self, game, sid, target=None):
        game.players[sid].state['coins'] += 3


class Contessa(Game.Action):

    """This action cannot be played directly"""

    async def validate(self, game, sid, target=None) -> bool:
        return False

    async def activate(self, game, sid, target=None):
        pass


class Captain(Game.Action):

    async def validate(self, game, sid, target=None):
        return game.players[sid].state['coins'] < 10

    async def activate(self, game, sid, target=None):
        amount = min(2, game.players[target].state['coins'])
        game.players[target].state['coins'] -= amount
        game.players[sid].state['coins'] += amount


class Assassin(Game.Action):

    async def validate(self, game, sid, target=None):
        return 3 <= game.players[sid].state['coins'] < 10

    async def activate(self, game, sid, target=None):
        game.players[sid].state['coins'] -= 3
        await game.kill(target)


class Ambassador(Game.Action):

    async def validate(self, game, sid, target=None):
        return True

    async def activate(self, game, sid, target=None):
        await game.swap(sid, 2)
