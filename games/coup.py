import asyncio
import time

from games.game_interface import GameInterface, Game


class CoupGame(GameInterface):

    MinPlayer = 2
    MaxPlayer = 6

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.turn_is_over = False
        self.last_reaction_time = time.time()
        self.is_resolved = asyncio.Condition()

    async def add_player(self, sid):
        await super().add_player(sid)
        self.players[sid] = {
            'coins': 0,
            'influences': None,
        }

    async def start(self):
        await super().start()
        for p in self.players:
            self.players[p]['coins'] = 2

    async def next_turn(self):
        self.turn_is_over = False
        async with self.lock:
            self.actions.clear()
            action, target_pid = await self.sio.call('turn', to=self.current_player.sid)

            if target_pid is not None and target_pid not in (p.pid for p in self.players):
                await self.sio.send(f'Invalid player selected: {target_pid}', room=self.current_player.sid)
                await self.eliminate(self.current_player.sid)
            elif not action.validate():
                await self.sio.send(f'Invalid action', room=self.current_player.sid)
                await self.eliminate(self.current_player.sid)

            self.actions.append(action)

            if type(action) in {Coup, Income}:
                await self.sio.emit(
                    'action',
                    data=(self.current_player.pid, target_pid, action),
                    room=self.uuid,
                    skip_sid=self.current_player.sid
                )
            elif type(action) in {Assassin, Captain, Ambassador, Duke, ForeignAid}:
                await self.sio.emit(
                    'action',
                    data=(self.current_player.pid, target_pid, action),
                    room=self.uuid,
                    skip_sid=self.current_player.sid,
                    callback=self.on_react
                )

                try:
                    # let time for the other clients to react
                    await asyncio.wait_for(self.is_resolved.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    self.sio.send('Nobody reacted to the action', room=self.uuid)

        async with self.lock:
            self.turn_is_over = True
            target = next(filter(lambda p: p.pid == target_pid, self.players))
            await action.activate(self.current_player.sid, target)
            await self.next_turn()

    async def on_react(self, sid, target, action):
        # The first client to react take the lock
        event_start_time = time.time()
        async with self.lock:
            if self.turn_is_over:
                await self.sio.send(f'You cannot react at this moment. Turn is over.', room=sid)
            elif self.last_reaction_time > event_start_time:
                await self.sio.send(f'Action was already reacted by another player', room=sid)
            elif action.validate():
                self.lock.cancel()  # TODO validate this behavior
                self.last_reaction_time = time.time()
                self.actions.append(action)
                if isinstance(action, Challenge):
                    self.is_resolved.notify()
                else:
                    await self.sio.emit('action', (target, self.current_player.pid, action), room=self.uuid, callback=self.on_react)
                    await self.sio.sleep(0.05)  # let time for the other clients to react
            else:
                await self.sio.send(f'Invalid reaction', room=sid)
                await self.eliminate(sid)

    async def challenge(self, sid, target):
        self.sio.send('Current player was challenged', room=self.uuid)
        succeed = any(type(inf) is type(self) for inf in self.players[sid]['influences'])
        if succeed:
            await self.replace(sid, self.__class__.__name__)
            await self.kill(target)
        else:
            await self.kill(sid)

    async def kill(self, target):
        self.sio.send(f'Player {self.players[target].pid}\'s influence got killed', room=self.uuid)
        #  Shortcut if player only have one card left
        if all(map(lambda inf: inf.alive, self.players[target]['influences'])):
            selected_influence = await self.sio.call('kill', to=target)
            if selected_influence in self.players[target]['influences']:
                self.players[target].state['influences'][selected_influence].alive = False
            else:
                await self.eliminate(target)
        else:
            await self.eliminate(target)

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

    async def eliminate(self, sid):
        for influence in self.players.state['influences']:
            influence.alive = False


class Challenge(Game.Action):

    async def validate(self, sid, target=None) -> bool:
        return len(self.game.actions) > 0

    async def activate(self, sid, target=None):
        await self.game.challenge(sid, target)


class Income(Game.Action):

    async def validate(self, sid, target=None) -> bool:
        return len(self.game.actions) == 0 and self.game.players[sid]['coins'] < 10

    async def activate(self, sid, target=None):
        self.game.players[sid]['coins'] += 1


class ForeignAid(Game.Action):

    async def validate(self, sid, target=None) -> bool:
        return len(self.game.actions) == 0 and self.game.players[sid]['coins'] < 10

    async def activate(self, sid, target=None):
        self.game.players[sid]['coins'] += 2


class Coup(Game.Action):
    
    async def validate(self, sid, target=None) -> bool:
        return len(self.game.actions) == 0 and self.game.players[sid]['coins'] >= 7

    async def activate(self, sid, target=None):
        self.game.players[sid]['coins'] -= 7
        await self.game.kill(sid, target)


class Duke(Game.Action):
    
    async def validate(self, sid, target=None):
        return (len(self.game.actions) == 0 and self.game.players[sid]['coins'] < 10) or isinstance(self.game.actions[-1], ForeignAid)

    async def activate(self, sid, target=None):
        if self.game.current_action is None:
            self.game.players[sid]['coins'] += 3
        elif isinstance(self.game.current_action, ForeignAid):
            self.game.block()


class Contessa(Game.Action):

    async def validate(self, sid, target=None) -> bool:
        return isinstance(self.game.actions[-1], Assassin)

    async def activate(self, sid, target=None):
        if isinstance(self.game.current_action, Assassin):
            self.game.block()


class Captain(Game.Action):

    async def validate(self, sid, target=None):
        return (len(self.game.actions) == 0 and self.game.players[sid]['coins'] < 10) or isinstance(self.game.actions[-1], Captain)

    async def activate(self, sid, target=None):
        if self.game.current_action is None:
            amount = min(2, self.game.players[target]['coins'])
            self.game.players[target]['coins'] -= amount
            self.game.players[sid]['coins'] += amount
        if isinstance(self.game.current_action, Captain):
            self.game.block()


class Assassin(Game.Action):

    async def validate(self, sid, target=None):
        return len(self.game.actions) == 0 and self.game.players[sid]['coins'] >= 3

    async def activate(self, sid, target=None):
        self.game.players[sid]['coins'] -= 3
        await self.game.kill(sid, target)


class Ambassador(Game.Action):
    
    async def validate(self, sid, target=None):
        return len(self.game.actions) == 0 \
               or isinstance(self.game.actions[-1], Captain) \
               or isinstance(self.game.actions[-1], Ambassador)

    async def activate(self, sid, target=None):
        if isinstance(self.game.current_action, Ambassador):
            self.game.swap(sid, 2)
        elif isinstance(self.game.current_action, Captain):
            self.game.block()
