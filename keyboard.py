# Copyright (C) 2013-2016 Jean-Francois Romang (jromang@posteo.de)
#                         Shivkumar Shivaji ()
#                         Jürgen Précour (LocutusOfPenguin@posteo.de)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import threading
import chess
import time
import logging
from utilities import *


class KeyboardInput(Observable, threading.Thread):
    def __init__(self):
        super(KeyboardInput, self).__init__()

    def run(self):
        while True:
            raw = input('PicoChess v'+version+':>').strip()
            cmd = raw.lower()

            try:
                # commands like "newgame:<w|b>" or "setup:<legal_fen_string>"
                # or "print:<legal_fen_string>"
                #
                # for simulating a dgt board use the following commands
                # "fen:<legal_fen_string>" or "button:<0-4>"
                #
                # everything else is regarded as a move string
                if cmd.startswith('newgame:'):
                    side = cmd.split(':')[1]
                    if side == 'w':
                        self.fire(Event.DGT_FEN(fen='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR'))
                    elif side == 'b':
                        self.fire(Event.DGT_FEN(fen='RNBKQBNR/PPPPPPPP/8/8/8/8/pppppppp/rnbkqbnr'))
                    else:
                        raise ValueError(raw)
                else:
                    if cmd.startswith('print:'):
                        fen = raw.split(':')[1]
                        print(chess.Board(fen))
                    elif cmd.startswith('setup:'):
                        fen = raw.split(':')[1]
                        uci960 = False  # make it easy for the moment
                        bit_board = chess.Board(fen, uci960)
                        if bit_board.is_valid():
                            self.fire(Event.SETUP_POSITION(fen=bit_board.fen(), uci960=uci960))
                        else:
                            raise ValueError(fen)
                    # Here starts the simulation of a dgt-board!
                    # Let the user send events like the board would do
                    elif cmd.startswith('fen:'):
                        fen = raw.split(':')[1]
                        # dgt board only sends the basic fen => be sure
                        # it's same no matter what fen the user entered
                        self.fire(Event.DGT_FEN(fen=fen.split(' ')[0]))
                    elif cmd.startswith('button:'):
                        button = int(cmd.split(':')[1])
                        if button not in range(5):
                            raise ValueError(button)
                        self.fire(Event.DGT_BUTTON(button=button))
                    # end simulation code
                    else:
                        # move => fen => virtual board sends fen
                        move = chess.Move.from_uci(cmd)
                        self.fire(Event.KEYBOARD_MOVE(move=move))
            except ValueError as e:
                logging.warning('Invalid user input [%s]', raw)


class TerminalDisplay(DisplayMsg, threading.Thread):
    def __init__(self):
        super(TerminalDisplay, self).__init__()

    def run(self):
        while True:
            # Check if we have something to display
            message = self.msg_queue.get()
            for case in switch(message):
                if case(MessageApi.COMPUTER_MOVE):
                    print('\n' + str(message.game))
                    print(message.game.fen())
                    print('emulate user to make the computer move...sleeping for one second')
                    time.sleep(1)
                    logging.debug('emulate user now finished doing computer move')
                    DisplayMsg.show(Message.DGT_FEN(fen=message.game.board_fen()))
                    break
                if case(MessageApi.SEARCH_STARTED):
                    if message.engine_status == EngineStatus.THINK:
                        print('Computer starts thinking')
                    if message.engine_status == EngineStatus.PONDER:
                        print('Computer starts pondering')
                    if message.engine_status == EngineStatus.WAIT:
                        print('Computer starts waiting - hmmm')
                    break
                if case(MessageApi.SEARCH_STOPPED):
                    if message.engine_status == EngineStatus.THINK:
                        print('Computer stops thinking')
                    if message.engine_status == EngineStatus.PONDER:
                        print('Computer stops pondering')
                    if message.engine_status == EngineStatus.WAIT:
                        print('Computer stops waiting - hmmm')
                    break
                if case():  # Default
                    pass
