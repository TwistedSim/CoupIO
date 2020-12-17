import sys

from games.game_interface import GameInterface, Game


class CoupGame(GameInterface):

    MinPlayer = 2
    MaxPlayer = 6

    class Influence:
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_action = None
        cards = []
        cards.extend(Duke() for _ in range(3))
        cards.extend(Captain() for _ in range(3))
        cards.extend(Assassin() for _ in range(3))
        cards.extend(Contessa() for _ in range(3))
        cards.extend(Ambassador() for _ in range(3))
        self.deck = Game.Deck(cards)

    async def start(self):
        self.current_action = None
        self.deck.reset()
        for p in self.players:
            self.players[p].state['coins'] = 2
            self.players[p].state['influences'] = [[card, True] for card in self.deck.take(2)]
        await super().start()

    async def deserialize_action(self, action):
        try:
            if type(action) is dict:
                action_type = getattr(sys.modules[__name__], action['type'])
            elif type(action) is str:
                action_type = getattr(sys.modules[__name__], action)
                action = {'type': action, 'args': [], 'kwargs': {}}
            else:
                await self.sio.send(f'Invalid action', room=self.current_player.sid)
                return
        except (KeyError, ModuleNotFoundError):
            return

        if not issubclass(action_type, Game.Action):
            await self.sio.send(f'Invalid action', room=self.current_player.sid)
            return

        return action_type(*action['args'], **action['kwargs'])

    async def validate_action(self, test_action, sid, target_pid):

        action = await self.deserialize_action(test_action)

        if action is None:
            return

        if target_pid is not None and target_pid not in (self.players[p].pid for p in self.players):
            await self.sio.send(f'Invalid player selected: {target_pid}', room=self.current_player.sid)
            return

        target = self.pid_to_sid(target_pid)

        if target and self.is_player_dead(target):
            await self.sio.send(f'Selected player is dead: {target_pid}', room=self.current_player.sid)
            return

        if not await action.validate(self, sid, target):
            await self.sio.send(f'Invalid action', room=self.current_player.sid)
            return

        return action

    async def next_turn(self):
        self.current_action = None

        try:
            action, target_pid = await self.sio.call('turn', to=self.current_player.sid)
            self.current_action = await self.validate_action(action, self.current_player.sid, target_pid)
        except TypeError as err:
            target_pid = None
            print(err)
            pass

        if self.current_action is None:
            await self.eliminate(self.current_player.sid)
        else:

            if type(self.current_action) in {Income, ForeignAid, Ambassador, Duke}:
                target_pid = None

            if type(self.current_action) in {Coup, Income}:
                await self.sio.emit(
                    'action',
                    data=(self.current_player.pid, target_pid, self.current_action['type']),
                    room=self.uuid,
                    #  skip_sid=self.current_player.sid
                )
            elif type(self.current_action) in {Assassin, Captain, Ambassador, Duke, ForeignAid}:
                await self.sio.emit(
                    'action',
                    data=(self.current_player.pid, target_pid, self.current_action['type']),
                    room=self.uuid,
                    #  skip_sid=self.current_player.sid,
                    #  callback=self.on_react  TODO add reaction
                )
            if target_pid is not None:
                print(f'Player {self.current_player.pid} use action {self.current_action} on player {target_pid}')
            else:
                print(f'Player {self.current_player.pid} use action {self.current_action}')
            await self.current_action.activate(self, self.current_player.sid, self.pid_to_sid(target_pid))

    async def kill(self, target):
        #  Shortcut if player only have one card left
        if self.player_influence_alive(target) > 1:
            selected_influence = await self.sio.call('kill', to=target)
            influence = await self.deserialize_action(selected_influence)
            if influence is not None:
                if [influence, True] in self.players[target].state['influences']:
                    idx = self.players[target].state['influences'].index([influence, True])
                    self.players[target].state['influences'][idx][1] = False
                    await self.sio.send(f'Player {self.players[target].pid} remove the {influence["type"]} from his influences', room=self.uuid)
                    print(f'Player {self.players[target].pid} removed the {influence["type"]}')
                    return
            await self.sio.send(f'Invalid influence returned: {selected_influence}', room=self.players[target].sid)
            await self.eliminate(target)
        else:
            await self.eliminate(target, invalid_action=False)

    async def swap(self, target, count):
        new_cards = ['' for _ in range(count)]  # TODO: draw cards
        # TODO: Validate selected card
        # TODO: Swap the cards
        kept_cards = await self.sio.call('swap', (self.uuid, new_cards), to=target)

    async def replace(self, target, influence):
        # TODO: replace the influence with another
        pass

    async def block(self, sid, target, influence):
        # TODO: emit on_action to others
        # TODO: check target answer, if pass, block action, otherwise, challenge
        # TODO: wait if there is a challenger before the target answer
        # return if block succeed
        pass

    async def challenge(self, sid, target, action):
        self.sio.send('Current player was challenged', room=self.uuid)
        succeed = any(inf[1] is True and type(inf[0]) is action for inf in self.players[sid].state['influences'])
        if succeed:
            await self.replace(sid, self.__class__.__name__)
            await self.kill(target)
        else:
            await self.kill(sid)

    async def eliminate(self, target, invalid_action=True):
        print(f'Player {self.players[target].pid} was eliminated. invalid_action={invalid_action}')
        if invalid_action:
            await self.sio.send(f'Player {self.players[target].pid} was eliminated for an invalid action.', room=self.uuid)
        else:
            await self.sio.send(f'Player {self.players[target].pid} is eliminate.', room=self.uuid)
        for influence in self.players[target].state['influences']:
            influence[1] = False
        self.players[target].alive = False

    def player_influence_alive(self, sid):
        return len(list(filter(lambda x: x[1] is True, self.players[sid].state['influences'])))

    def is_player_dead(self, sid):
        return self.player_influence_alive(sid) == 0


class Challenge(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None) -> bool:
        return game.current_action is not None

    async def activate(self, game: CoupGame, sid, target=None):
        await game.challenge(sid, target)


class Income(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None) -> bool:
        return game.current_action is None \
               and game.players[sid]['coins'] < 10

    async def activate(self, game: CoupGame, sid, target=None):
        game.players[sid]['coins'] += 1


class ForeignAid(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None) -> bool:
        return game.current_action is None \
               and game.players[sid].state['coins'] < 10

    async def activate(self, game: CoupGame, sid, target=None):
        game.players[sid].state['coins'] += 2


class Coup(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None) -> bool:
        return game.current_action is None \
               and game.players[sid].state['coins'] >= 7

    async def activate(self, game: CoupGame, sid, target=None):
        game.players[sid].state['coins'] -= 7
        await game.kill(target)


class Duke(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None):
        return (game.current_action is None and game.players[sid].state['coins'] < 10) \
               or isinstance(game.current_action, ForeignAid)

    async def activate(self, game: CoupGame, sid, target=None):
        if isinstance(game.current_action, Duke):
            game.players[sid].state['coins'] += 3
        elif isinstance(game.current_action, ForeignAid):
            await game.block(sid, target, Duke)


class Contessa(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None) -> bool:
        return isinstance(game.actions[-1], Assassin)

    async def activate(self, game: CoupGame, sid, target=None):
        if isinstance(game.current_action, Assassin):
            await game.block(sid, target, Contessa)


class Captain(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None):
        return (game.current_action is None and game.players[sid].state['coins'] < 10) \
               or isinstance(game.current_action, Captain)

    async def activate(self, game: CoupGame, sid, target=None):
        if isinstance(game.current_action, Captain):
            amount = min(2, game.players[target].state['coins'])
            game.players[target].state['coins'] -= amount
            game.players[sid].state['coins'] += amount
        #if isinstance(game.current_action, Captain):
        #    await game.block(sid, target, Captain)


class Assassin(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None):
        return game.current_action is None and 3 <= game.players[sid].state['coins'] < 10

    async def activate(self, game: CoupGame, sid, target=None):
        game.players[sid].state['coins'] -= 3
        await game.kill(target)


class Ambassador(Game.Action):

    async def validate(self, game: CoupGame, sid, target=None):
        return game.current_action is None \
               or isinstance(game.current_action, Captain) \
               or isinstance(game.current_action, Ambassador)

    async def activate(self, game: CoupGame, sid, target=None):
        if isinstance(game.current_action, Ambassador):
            await game.swap(sid, 2)
        elif isinstance(game.current_action, Captain):
            await game.block(sid, target, Ambassador)
