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

import logging
import queue
import os
import platform
import subprocess
import urllib.request
import socket
import json
import time
from threading import Timer

import uci
import configparser

try:
    import enum
except ImportError:
    import enum34 as enum


# picochess version
version = '063'

evt_queue = queue.Queue()
serial_queue = queue.Queue()

msgdisplay_devices = []
dgtdisplay_devices = []


class AutoNumber(enum.Enum):
    def __new__(cls):  # Autonumber
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


class EventApi():
    # User events
    FEN = 'EVT_FEN'  # User has moved one or more pieces, and we have a new fen position
    LEVEL = 'EVT_LEVEL'  # User sets engine level (from 1 to 20)
    NEW_GAME = 'EVT_NEW_GAME'  # User starts a new game
    DRAWRESIGN = 'EVT_DRAWRESIGN'  # User declares a resignation or draw
    USER_MOVE = 'EVT_USER_MOVE'  # User sends a move
    KEYBOARD_MOVE = 'EVT_KEYBOARD_MOVE'  # Keyboard sends a move (to be transfered to a fen)
    REMOTE_MOVE = 'EVT_REMOTE_MOVE'  # Remote player move
    SET_OPENING_BOOK = 'EVT_SET_OPENING_BOOK'  # User chooses an opening book
    NEW_ENGINE = 'EVT_NEW_ENGINE'  # Change engine
    SET_INTERACTION_MODE = 'EVT_SET_INTERACTION_MODE'  # Change interaction mode
    SETUP_POSITION = 'EVT_SETUP_POSITION'  # Setup custom position
    STARTSTOP_THINK = 'EVT_STARTSTOP_THINK'  # Engine should start/stop thinking
    STARTSTOP_CLOCK = 'EVT_STARTSTOP_CLOCK'  # Clock should start/stop
    SET_TIME_CONTROL = 'EVT_SET_TIME_CONTROL'  # User sets time control
    UCI_OPTION_SET = 'EVT_UCI_OPTION_SET'  # Users sets an UCI option, contains 'name' and 'value' (strings)
    SHUTDOWN = 'EVT_SHUTDOWN'  # User wants to shutdown the machine
    REBOOT = 'EVT_REBOOT'  # User wants to reboot the machine
    ALTERNATIVE_MOVE = 'EVT_ALTERNATIVE_MOVE'  # User wants engine to recalculate the position
    # dgt events
    DGT_BUTTON = 'EVT_DGT_BUTTON'  # User pressed a button at the dgt clock
    DGT_FEN = 'EVT_DGT_FEN'  # DGT board sends a fen
    # Engine events
    BEST_MOVE = 'EVT_BEST_MOVE'  # Engine has found a move
    NEW_PV = 'EVT_NEW_PV'  # Engine sends a new principal variation
    NEW_SCORE = 'EVT_NEW_SCORE'  # Engine sends a new score
    OUT_OF_TIME = 'EVT_OUT_OF_TIME'  # Clock flag fallen
    DGT_CLOCK_STARTED = 'EVT_DGT_CLOCK_STARTED'  # DGT Clock is running


class MessageApi():
    # Messages to display devices
    COMPUTER_MOVE = 'MSG_COMPUTER_MOVE'  # Show computer move
    BOOK_MOVE = 'MSG_BOOK_MOVE'  # Show book move
    NEW_PV = 'MSG_NEW_PV'  # Show the new Principal Variation
    REVIEW_MOVE = 'MSG_REVIEW_MOVE'  # Player is reviewing a game
    ENGINE_READY = 'MSG_ENGINE_READY'
    ENGINE_STARTUP = 'MSG_ENGINE_STARTUP'  # first time a new engine is ready
    ENGINE_FAIL = 'MSG_ENGINE_FAIL'
    LEVEL = 'MSG_LEVEL'  # User sets engine level (from 0 to 20).
    TIME_CONTROL = 'MSG_TIME_CONTROL'
    OPENING_BOOK = 'MSG_OPENING_BOOK'  # User chooses an opening book
    DGT_BUTTON = 'MSG_DGT_BUTTON'  # Clock button pressed
    DGT_FEN = 'MSG_DGT_FEN'  # DGT Board sends a fen
    DGT_CLOCK_VERSION = 'MSG_DGT_CLOCK_VERSION'  # DGT Board sends the clock version
    DGT_CLOCK_TIME = 'MSG_DGT_CLOCK_TIME'  # DGT Clock time message

    INTERACTION_MODE = 'MSG_INTERACTON_MODE'  # Interaction mode
    PLAY_MODE = 'MSG_PLAY_MODE'  # Play mode
    START_NEW_GAME = 'MSG_START_NEW_GAME'
    COMPUTER_MOVE_DONE_ON_BOARD = 'MSG_COMPUTER_MOVE_DONE_ON_BOARD'  # User has done the compute move on board
    WAIT_STATE = 'MSG_WAIT_STATE'  # picochess waits for the user
    SEARCH_STARTED = 'MSG_SEARCH_STARTED'  # Engine has started to search
    SEARCH_STOPPED = 'MSG_SEARCH_STOPPED'  # Engine has stopped the search
    USER_TAKE_BACK = 'MSG_USER_TACK_BACK'  # User takes back his move while engine is searching
    RUN_CLOCK = 'MSG_RUN_CLOCK'  # Say to run autonomous clock, contains time_control
    STOP_CLOCK = 'MSG_STOP_CLOCK'  # Stops the clock
    USER_MOVE = 'MSG_USER_MOVE'  # Player has done a move on board
    UCI_OPTION_LIST = 'MSG_UCI_OPTION_LIST'  # Contains 'options', a dict of the current engine's UCI options
    GAME_ENDS = 'MSG_GAME_ENDS'  # The current game has ended, contains a 'result' (GameResult) and list of 'moves'

    SYSTEM_INFO = 'MSG_SYSTEM_INFO'  # Information about picochess such as version etc
    STARTUP_INFO = 'MSG_STARTUP_INFO'  # Information about the startup options
    NEW_SCORE = 'MSG_NEW_SCORE'  # Score
    ALTERNATIVE_MOVE = 'MSG_ALTERNATIVE_MOVE'  # User wants another move to be calculated
    JACK_CONNECTED_ERROR = 'MSG_JACK_CONNECTED_ERROR'  # User connected fully|partly the clock via jack => remove it
    NO_CLOCK_ERROR = 'MSG_NO_CLOCK_ERROR'  # User hasnt connected a clock
    NO_EBOARD_ERROR = 'MSG_NO_EBOARD_ERROR'  # User hasnt connected an E-Board
    EBOARD_VERSION = 'MSG_EBOARD_VERSION'  # Startup Message after a successful connection to an E-Board


class DgtApi():
    # Commands to the DgtHw/Pi (or the virtual hardware)
    DISPLAY_MOVE = 'DGT_DISPLAY_MOVE'
    DISPLAY_TEXT = 'DGT_DISPLAY_TEXT'
    LIGHT_CLEAR = 'DGT_LIGHT_CLEAR'
    LIGHT_SQUARES = 'DGT_LIGHT_SQUARES'
    CLOCK_STOP = 'DGT_CLOCK_STOP'
    CLOCK_START = 'DGT_CLOCK_START'
    CLOCK_END = 'DGT_END_CLOCK'
    CLOCK_VERSION = 'DGT_CLOCK_VERSION'
    CLOCK_TIME = 'DGT_CLOCK_TIME'
    SERIALNR = 'DGT_SERIALNR'


@enum.unique
class Menu(enum.Enum):
    TOP_MENU = 'B00_menu_top_menu'  # Top Level Menu
    MODE_MENU = 'B00_menu_mode_menu'  # Default Menu
    POSITION_MENU = 'B00_menu_position_menu'  # Setup position menu
    TIME_MENU = 'B00_menu_time_menu'  # Time controls menu
    BOOK_MENU = 'B00_menu_book_menu'  # Book menu
    ENGINE_MENU = 'B00_menu_engine_menu'  # Engine menu
    SYSTEM_MENU = 'B00_menu_system_menu'  # Settings menu


class MenuLoop(object):
    def __init__(self):
        super(MenuLoop, self).__init__()

    @staticmethod
    def next(m):
        if m == Menu.MODE_MENU:
            return Menu.POSITION_MENU
        elif m == Menu.POSITION_MENU:
            return Menu.TIME_MENU
        elif m == Menu.TIME_MENU:
            return Menu.BOOK_MENU
        elif m == Menu.BOOK_MENU:
            return Menu.ENGINE_MENU
        elif m == Menu.ENGINE_MENU:
            return Menu.SYSTEM_MENU
        elif m == Menu.SYSTEM_MENU:
            return Menu.MODE_MENU
        return Menu.TOP_MENU

    @staticmethod
    def prev(m):
        if m == Menu.MODE_MENU:
            return Menu.SYSTEM_MENU
        elif m == Menu.POSITION_MENU:
            return Menu.MODE_MENU
        elif m == Menu.TIME_MENU:
            return Menu.POSITION_MENU
        elif m == Menu.BOOK_MENU:
            return Menu.TIME_MENU
        elif m == Menu.ENGINE_MENU:
            return Menu.BOOK_MENU
        elif m == Menu.SYSTEM_MENU:
            return Menu.ENGINE_MENU
        return Menu.TOP_MENU


@enum.unique
class Mode(enum.Enum):
    NORMAL = 'B00_mode_normal_menu'
    ANALYSIS = 'B00_mode_analysis_menu'
    KIBITZ = 'B00_mode_kibitz_menu'
    OBSERVE = 'B00_mode_observe_menu'
    REMOTE = 'B00_mode_remote_menu'


class ModeLoop(object):
    def __init__(self):
        super(ModeLoop, self).__init__()

    @staticmethod
    def next(m):
        if m == Mode.NORMAL:
            return Mode.ANALYSIS
        elif m == Mode.ANALYSIS:
            return Mode.KIBITZ
        elif m == Mode.KIBITZ:
            return Mode.OBSERVE
        elif m == Mode.OBSERVE:
            return Mode.REMOTE
        elif m == Mode.REMOTE:
            return Mode.NORMAL
        return 'error ModeLoop next'

    @staticmethod
    def prev(m):
        if m == Mode.NORMAL:
            return Mode.REMOTE
        elif m == Mode.ANALYSIS:
            return Mode.NORMAL
        elif m == Mode.KIBITZ:
            return Mode.ANALYSIS
        elif m == Mode.OBSERVE:
            return Mode.KIBITZ
        elif m == Mode.REMOTE:
            return Mode.OBSERVE
        return 'error ModeLoop prev'


@enum.unique
class PlayMode(enum.Enum):
    USER_WHITE = 'B10_playmode_white_user'
    USER_BLACK = 'B10_playmode_black_user'


class TimeMode(enum.Enum):
    FIXED = 'B00_timemode_fixed_menu'  # Fixed seconds per move
    BLITZ = 'B00_timemode_blitz_menu'  # Fixed time per game
    FISCHER = 'B00_timemode_fischer_menu'  # Fischer increment


class TimeModeLoop(object):
    def __init__(self):
        super(TimeModeLoop, self).__init__()

    @staticmethod
    def next(m):
        if m == TimeMode.FIXED:
            return TimeMode.BLITZ
        elif m == TimeMode.BLITZ:
            return TimeMode.FISCHER
        elif m == TimeMode.FISCHER:
            return TimeMode.FIXED
        return 'error TimeMode next'

    @staticmethod
    def prev(m):
        if m == TimeMode.FIXED:
            return TimeMode.FISCHER
        elif m == TimeMode.BLITZ:
            return TimeMode.FIXED
        elif m == TimeMode.FISCHER:
            return TimeMode.BLITZ
        return 'error TimeMode prev'


class Settings(enum.Enum):
    VERSION = 'B00_settings_version_menu'
    IPADR = 'B00_settings_ipadr_menu'
    SOUND = 'B00_settings_sound_menu'
    LANGUAGE = 'B00_settings_language_menu'


class SettingsLoop(object):
    def __init__(self):
        super(SettingsLoop, self).__init__()

    @staticmethod
    def next(m):
        if m == Settings.VERSION:
            return Settings.IPADR
        elif m == Settings.IPADR:
            return Settings.SOUND
        elif m == Settings.SOUND:
            return Settings.LANGUAGE
        elif m == Settings.LANGUAGE:
            return Settings.VERSION
        return 'error Setting next'

    @staticmethod
    def prev(m):
        if m == Settings.VERSION:
            return Settings.LANGUAGE
        if m == Settings.LANGUAGE:
            return Settings.SOUND
        elif m == Settings.SOUND:
            return Settings.IPADR
        elif m == Settings.IPADR:
            return Settings.VERSION
        return 'error Setting prev'


class Language(enum.Enum):
    EN = 'B00_language_en_menu'
    DE = 'B00_language_de_menu'
    NL = 'B00_language_nl_menu'
    FR = 'B00_language_fr_menu'
    ES = 'B00_language_es_menu'


class LanguageLoop(object):
    def __init__(self):
        super(LanguageLoop, self).__init__()

    @staticmethod
    def next(m):
        if m == Language.EN:
            return Language.DE
        elif m == Language.DE:
            return Language.NL
        elif m == Language.NL:
            return Language.FR
        elif m == Language.FR:
            return Language.ES
        elif m == Language.ES:
            return Language.EN
        return 'error Language next'

    @staticmethod
    def prev(m):
        if m == Language.EN:
            return Language.ES
        if m == Language.ES:
            return Language.FR
        if m == Language.FR:
            return Language.NL
        elif m == Language.NL:
            return Language.DE
        elif m == Language.DE:
            return Language.EN
        return 'error Language prev'


@enum.unique
class GameResult(enum.Enum):
    MATE = 'B00_gameresult_mate_menu'
    STALEMATE = 'B00_gameresult_stalemate_menu'
    OUT_OF_TIME = 'B00_gameresult_time_menu'
    INSUFFICIENT_MATERIAL = 'B00_gameresult_material_menu'
    SEVENTYFIVE_MOVES = 'B00_gameresult_moves_menu'
    FIVEFOLD_REPETITION = 'B00_gameresult_repetition_menu'
    ABORT = 'B00_gameresult_abort_menu'
    RESIGN_WHITE = 'B00_gameresult_white_menu'
    RESIGN_BLACK = 'B00_gameresult_black_menu'
    DRAW = 'B00_gameresult_draw_menu'


class EngineStatus(AutoNumber):
    THINK = ()
    PONDER = ()
    WAIT = ()


@enum.unique
class BeepLevel(enum.Enum):
    YES = 0x0f  # Always ON
    NO = 0x00  # Always OFF
    CONFIG = 0x01  # Takeback, GameEnd, NewGame and ComputerMove
    BUTTON = 0x02  # All Events coming from button press
    MAP = 0x04  # All Events coming from Queen placing at start pos (line3-6)
    OKAY = 0x08  # All Events from "ok" (confirm) messages incl. "you move"


@enum.unique
class DgtCmd(enum.Enum):
    """ COMMAND CODES FROM PC TO BOARD """
    # Commands not resulting in returning messages:
    DGT_SEND_RESET = 0x40  # Puts the board in IDLE mode, cancelling any UPDATE mode
    DGT_STARTBOOTLOADER = 0x4e  # Makes a long jump to the FC00 boot loader code. Start FLIP now
    # Commands resulting in returning message(s):
    DGT_SEND_CLK = 0x41  # Results in a DGT_MSG_BWTIME message
    DGT_SEND_BRD = 0x42  # Results in a DGT_MSG_BOARD_DUMP message
    DGT_SEND_UPDATE = 0x43  # Results in DGT_MSG_FIELD_UPDATE messages and DGT_MSG_BWTIME messages
    # as long as the board is in UPDATE mode
    DGT_SEND_UPDATE_BRD = 0x44  # Results in DGT_MSG_FIELD_UPDATE messages as long as the board is in UPDATE_BOARD mode
    DGT_RETURN_SERIALNR = 0x45  # Results in a DGT_MSG_SERIALNR message
    DGT_RETURN_BUSADRES = 0x46  # Results in a DGT_MSG_BUSADRES message
    DGT_SEND_TRADEMARK = 0x47  # Results in a DGT_MSG_TRADEMARK message
    DGT_SEND_EE_MOVES = 0x49  # Results in a DGT_MSG_EE_MOVES message
    DGT_SEND_UPDATE_NICE = 0x4b  # Results in DGT_MSG_FIELD_UPDATE messages and DGT_MSG_BWTIME messages,
    # the latter only at time changes, as long as the board is in UPDATE_NICE mode
    DGT_SEND_BATTERY_STATUS = 0x4c  # New command for bluetooth board. Requests the battery status from the board.
    DGT_SEND_VERSION = 0x4d  # Results in a DGT_MSG_VERSION message
    DGT_SEND_BRD_50B = 0x50  # Results in a DGT_MSG_BOARD_DUMP_50 message: only the black squares
    DGT_SCAN_50B = 0x51  # Sets the board in scanning only the black squares. This is written in EEPROM
    DGT_SEND_BRD_50W = 0x52  # Results in a DGT_MSG_BOARD_DUMP_50 message: only the black squares
    DGT_SCAN_50W = 0x53  # Sets the board in scanning only the black squares. This is written in EEPROM.
    DGT_SCAN_100 = 0x54  # Sets the board in scanning all squares. This is written in EEPROM
    DGT_RETURN_LONG_SERIALNR = 0x55  # Results in a DGT_LONG_SERIALNR message
    DGT_SET_LEDS = 0x60  # Only for the Revelation II to switch a LED pattern on. This is a command that
    # has three extra bytes with data.
    # Clock commands, returns ACK message if mode is in UPDATE or UPDATE_NICE
    DGT_CLOCK_MESSAGE = 0x2b  # This message contains a command for the clock.


class DgtClk(enum.Enum):
    DGT_CMD_CLOCK_DISPLAY = 0x01  # This command can control the segments of six 7-segment characters,
    # two dots, two semicolons and the two '1' symbols.
    DGT_CMD_CLOCK_ICONS = 0x02  # Used to control the clock icons like flags etc.
    DGT_CMD_CLOCK_END = 0x03  # This command clears the message and brings the clock back to the
    # normal display (showing clock times).
    DGT_CMD_CLOCK_BUTTON = 0x08  # Requests the current button pressed (if any).
    DGT_CMD_CLOCK_VERSION = 0x09  # This commands requests the clock version.
    DGT_CMD_CLOCK_SETNRUN = 0x0a  # This commands controls the clock times and counting direction, when
    # the clock is in mode 23. A clock can be paused or counting down. But
    # counting up isn't supported on current DGT XL's (1.14 and lower) yet.
    DGT_CMD_CLOCK_BEEP = 0x0b  # This clock command turns the beep on, for a specified time (64ms * byte 5)
    DGT_CMD_CLOCK_ASCII = 0x0c  # This clock commands sends a ASCII message to the clock that
    # can be displayed only by the DGT3000.
    DGT_CMD_CLOCK_START_MESSAGE = 0x03
    DGT_CMD_CLOCK_END_MESSAGE = 0x00
    DGT_ACK_CLOCK_BUTTON = 0x88  # Ack of a clock button


class DgtMsg(enum.IntEnum):
    """
    DESCRIPTION OF THE MESSAGES FROM BOARD TO PC
    """
    MESSAGE_BIT = 0x80  # The Message ID is the logical OR of MESSAGE_BIT and ID code
    # ID codes
    DGT_NONE = 0x00
    DGT_BOARD_DUMP = 0x06
    DGT_BWTIME = 0x0d
    DGT_FIELD_UPDATE = 0x0e
    DGT_EE_MOVES = 0x0f
    DGT_BUSADRES = 0x10
    DGT_SERIALNR = 0x11
    DGT_TRADEMARK = 0x12
    DGT_VERSION = 0x13
    DGT_BOARD_DUMP_50B = 0x14  # Added for Draughts board
    DGT_BOARD_DUMP_50W = 0x15  # Added for Draughts board
    DGT_BATTERY_STATUS = 0x20  # Added for Bluetooth board
    DGT_LONG_SERIALNR = 0x22  # Added for Bluetooth board
    # DGT_MSG_BOARD_DUMP is the message that follows on a DGT_SEND_BOARD command
    DGT_MSG_BOARD_DUMP = (MESSAGE_BIT | DGT_BOARD_DUMP)
    DGT_SIZE_BOARD_DUMP = 67
    DGT_SIZE_BOARD_DUMP_DRAUGHTS = 103
    DGT_MSG_BOARD_DUMP_50B = (MESSAGE_BIT | DGT_BOARD_DUMP_50B)
    DGT_SIZE_BOARD_DUMP_50B = 53
    DGT_MSG_BOARD_DUMP_50W = (MESSAGE_BIT | DGT_BOARD_DUMP_50W)
    DGT_SIZE_BOARD_DUMP_50W = 53
    DGT_MSG_BWTIME = (MESSAGE_BIT | DGT_BWTIME)
    DGT_SIZE_BWTIME = 10
    DGT_MSG_FIELD_UPDATE = (MESSAGE_BIT | DGT_FIELD_UPDATE)
    DGT_SIZE_FIELD_UPDATE = 5
    DGT_MSG_TRADEMARK = (MESSAGE_BIT | DGT_TRADEMARK)
    DGT_MSG_BUSADRES = (MESSAGE_BIT | DGT_BUSADRES)
    DGT_SIZE_BUSADRES = 5
    DGT_MSG_SERIALNR = (MESSAGE_BIT | DGT_SERIALNR)
    DGT_SIZE_SERIALNR = 8
    DGT_MSG_LONG_SERIALNR = (MESSAGE_BIT | DGT_LONG_SERIALNR)
    DGT_SIZE_LONG_SERIALNR = 13
    DGT_MSG_VERSION = (MESSAGE_BIT | DGT_VERSION)
    DGT_SIZE_VERSION = 5
    DGT_MSG_BATTERY_STATUS = (MESSAGE_BIT | DGT_BATTERY_STATUS)
    DGT_SIZE_BATTERY_STATUS = 7
    DGT_MSG_EE_MOVES = (MESSAGE_BIT | DGT_EE_MOVES)
    # Definition of the one-byte EEPROM message codes
    EE_POWERUP = 0x6a
    EE_EOF = 0x6b
    EE_FOURROWS = 0x6c
    EE_EMPTYBOARD = 0x6d
    EE_DOWNLOADED = 0x6e
    EE_BEGINPOS = 0x6f
    EE_BEGINPOS_ROT = 0x7a
    EE_START_TAG = 0x7b
    EE_WATCHDOG_ACTION = 0x7c
    EE_FUTURE_1 = 0x7d
    EE_FUTURE_2 = 0x7e
    EE_NOP = 0x7f
    EE_NOP2 = 0x00


class Observable(object):  # Input devices are observable
    def __init__(self):
        super(Observable, self).__init__()

    @staticmethod
    def fire(event):
        evt_queue.put(event)


class DisplayMsg(object):  # Display devices (DGT XL clock, Piface LCD, pgn file...)
    def __init__(self):
        super(DisplayMsg, self).__init__()
        self.msg_queue = queue.Queue()
        msgdisplay_devices.append(self)

    @staticmethod
    def show(message):  # Sends a message on each display device
        for display in msgdisplay_devices:
            display.msg_queue.put(message)


class DisplayDgt(object):  # Display devices (DGT XL clock, Piface LCD, pgn file...)
    def __init__(self):
        super(DisplayDgt, self).__init__()
        self.dgt_queue = queue.Queue()
        dgtdisplay_devices.append(self)

    @staticmethod
    def show(message):  # Sends a message on each display device
        for display in dgtdisplay_devices:
            display.dgt_queue.put(message)


# switch/case instruction in python
class switch(object):
    def __init__(self, value):
        if type(value) is int:
            self.value = value
        else:
            self.value = value._type
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args:  # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False


class BaseClass(object):
    def __init__(self, classtype):
        self._type = classtype

    def __repr__(self):
        return self._type


def ClassFactory(name, argnames, BaseClass=BaseClass):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            # here, the argnames variable is the one passed to the ClassFactory call
            if key not in argnames:
                raise TypeError("argument %s not valid for %s" % (key, self.__class__.__name__))
            setattr(self, key, value)
        BaseClass.__init__(self, name)
    newclass = type(name, (BaseClass,),{"__init__": __init__})
    return newclass


class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.timer_running = False

    def _run(self):
        self.timer_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def is_running(self):
        return self.timer_running

    def start(self):
        if not self.timer_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.timer_running = True

    def stop(self):
        self._timer.cancel()
        self.timer_running = False


class Dgt():
    DISPLAY_MOVE = ClassFactory(DgtApi.DISPLAY_MOVE, ['move', 'fen', 'beep', 'duration', 'wait'])
    DISPLAY_TEXT = ClassFactory(DgtApi.DISPLAY_TEXT, ['l', 'm', 's', 'beep', 'duration', 'wait'])
    LIGHT_CLEAR = ClassFactory(DgtApi.LIGHT_CLEAR, [])
    LIGHT_SQUARES = ClassFactory(DgtApi.LIGHT_SQUARES, ['squares'])
    CLOCK_END = ClassFactory(DgtApi.CLOCK_END, ['wait', 'force'])
    CLOCK_STOP = ClassFactory(DgtApi.CLOCK_STOP, [])
    CLOCK_START = ClassFactory(DgtApi.CLOCK_START, ['time_left', 'time_right', 'side', 'wait', 'callback'])
    CLOCK_VERSION = ClassFactory(DgtApi.CLOCK_VERSION, ['main_version', 'sub_version', 'attached'])
    CLOCK_TIME = ClassFactory(DgtApi.CLOCK_TIME, ['time_left', 'time_right'])
    SERIALNR = ClassFactory(DgtApi.SERIALNR, [])


class Message():
    # Messages to display devices
    COMPUTER_MOVE = ClassFactory(MessageApi.COMPUTER_MOVE, ['result', 'fen', 'game', 'time_control'])
    BOOK_MOVE = ClassFactory(MessageApi.BOOK_MOVE, ['result'])
    NEW_PV = ClassFactory(MessageApi.NEW_PV, ['pv', 'mode', 'fen'])
    REVIEW_MOVE = ClassFactory(MessageApi.REVIEW_MOVE, ['move', 'fen', 'game', 'mode'])
    ENGINE_READY = ClassFactory(MessageApi.ENGINE_READY, ['eng', 'eng_text', 'engine_name', 'has_levels', 'has_960'])
    ENGINE_STARTUP = ClassFactory(MessageApi.ENGINE_STARTUP, ['shell', 'path', 'has_levels', 'has_960'])
    ENGINE_FAIL = ClassFactory(MessageApi.ENGINE_FAIL, [])
    LEVEL = ClassFactory(MessageApi.LEVEL, ['level', 'level_text'])
    TIME_CONTROL = ClassFactory(MessageApi.TIME_CONTROL, ['time_text'])
    OPENING_BOOK = ClassFactory(MessageApi.OPENING_BOOK, ['book_name', 'book_text'])
    DGT_BUTTON = ClassFactory(MessageApi.DGT_BUTTON, ['button'])
    DGT_FEN = ClassFactory(MessageApi.DGT_FEN, ['fen'])
    DGT_CLOCK_VERSION = ClassFactory(MessageApi.DGT_CLOCK_VERSION, ['main_version', 'sub_version', 'attached'])
    DGT_CLOCK_TIME = ClassFactory(MessageApi.DGT_CLOCK_TIME, ['time_left', 'time_right'])

    INTERACTION_MODE = ClassFactory(MessageApi.INTERACTION_MODE, ['mode', 'mode_text'])
    PLAY_MODE = ClassFactory(MessageApi.PLAY_MODE, ['play_mode'])
    START_NEW_GAME = ClassFactory(MessageApi.START_NEW_GAME, ['time_control'])
    COMPUTER_MOVE_DONE_ON_BOARD = ClassFactory(MessageApi.COMPUTER_MOVE_DONE_ON_BOARD, [])
    WAIT_STATE = ClassFactory(MessageApi.WAIT_STATE, [])
    SEARCH_STARTED = ClassFactory(MessageApi.SEARCH_STARTED, ['engine_status'])
    SEARCH_STOPPED = ClassFactory(MessageApi.SEARCH_STOPPED, ['engine_status'])
    USER_TAKE_BACK = ClassFactory(MessageApi.USER_TAKE_BACK, [])
    RUN_CLOCK = ClassFactory(MessageApi.RUN_CLOCK, ['turn', 'time_control', 'callback'])
    STOP_CLOCK = ClassFactory(MessageApi.STOP_CLOCK, [])
    USER_MOVE = ClassFactory(MessageApi.USER_MOVE, ['move', 'game'])
    UCI_OPTION_LIST = ClassFactory(MessageApi.UCI_OPTION_LIST, ['options'])
    GAME_ENDS = ClassFactory(MessageApi.GAME_ENDS, ['result', 'play_mode', 'game', 'custom_fen'])

    SYSTEM_INFO = ClassFactory(MessageApi.SYSTEM_INFO, ['info'])
    STARTUP_INFO = ClassFactory(MessageApi.STARTUP_INFO, ['info'])
    NEW_SCORE = ClassFactory(MessageApi.NEW_SCORE, ['score', 'mate', 'mode'])
    ALTERNATIVE_MOVE = ClassFactory(MessageApi.ALTERNATIVE_MOVE, [])
    JACK_CONNECTED_ERROR = ClassFactory(MessageApi.JACK_CONNECTED_ERROR, [])
    NO_CLOCK_ERROR = ClassFactory(MessageApi.NO_CLOCK_ERROR, ['text'])
    NO_EBOARD_ERROR = ClassFactory(MessageApi.NO_EBOARD_ERROR, ['text', 'is_pi'])
    EBOARD_VERSION = ClassFactory(MessageApi.EBOARD_VERSION, ['text', 'channel'])


class Event():
    # User events
    FEN = ClassFactory(EventApi.FEN, ['fen'])
    LEVEL = ClassFactory(EventApi.LEVEL, ['level', 'level_text'])
    NEW_GAME = ClassFactory(EventApi.NEW_GAME, [])
    DRAWRESIGN = ClassFactory(EventApi.DRAWRESIGN, ['result'])
    USER_MOVE = ClassFactory(EventApi.USER_MOVE, ['move'])
    KEYBOARD_MOVE = ClassFactory(EventApi.KEYBOARD_MOVE, ['move'])
    REMOTE_MOVE = ClassFactory(EventApi.REMOTE_MOVE, ['move', 'fen'])
    SET_OPENING_BOOK = ClassFactory(EventApi.SET_OPENING_BOOK, ['book', 'book_text'])
    NEW_ENGINE = ClassFactory(EventApi.NEW_ENGINE, ['eng', 'eng_text', 'level', 'level_text'])
    SET_INTERACTION_MODE = ClassFactory(EventApi.SET_INTERACTION_MODE, ['mode', 'mode_text'])
    SETUP_POSITION = ClassFactory(EventApi.SETUP_POSITION, ['fen', 'uci960'])
    STARTSTOP_THINK = ClassFactory(EventApi.STARTSTOP_THINK, [])
    STARTSTOP_CLOCK = ClassFactory(EventApi.STARTSTOP_CLOCK, [])
    SET_TIME_CONTROL = ClassFactory(EventApi.SET_TIME_CONTROL, ['time_control', 'time_text'])
    UCI_OPTION_SET = ClassFactory(EventApi.UCI_OPTION_SET, [])
    SHUTDOWN = ClassFactory(EventApi.SHUTDOWN, [])
    REBOOT = ClassFactory(EventApi.REBOOT, [])
    ALTERNATIVE_MOVE = ClassFactory(EventApi.ALTERNATIVE_MOVE, [])
    # dgt events
    DGT_BUTTON = ClassFactory(EventApi.DGT_BUTTON, ['button'])
    DGT_FEN = ClassFactory(EventApi.DGT_FEN, ['fen'])
    # Engine events
    BEST_MOVE = ClassFactory(EventApi.BEST_MOVE, ['result', 'inbook'])
    NEW_PV = ClassFactory(EventApi.NEW_PV, ['pv'])
    NEW_SCORE = ClassFactory(EventApi.NEW_SCORE, ['score', 'mate'])
    OUT_OF_TIME = ClassFactory(EventApi.OUT_OF_TIME, ['color'])
    DGT_CLOCK_STARTED = ClassFactory(EventApi.DGT_CLOCK_STARTED, ['callback'])


def get_opening_books():
    program_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
    book_list = sorted(os.listdir(program_path + 'books'))
    library = []
    for book in book_list:
        # Can't use isfile() as that doesn't count links
        if not os.path.isdir('books' + os.sep + book):
            library.append((book[2:book.index('.')], 'books' + os.sep + book))
    return library


def get_installed_engines(engine_shell, engine_path):
    return read_engine_ini(engine_shell, (engine_path.rsplit(os.sep, 1))[0])


def write_engine_ini(engine_path=None):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    if not engine_path:
        program_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
        engine_path = program_path + 'engines' + os.sep + platform.machine()
    engine_list = sorted(os.listdir(engine_path))
    config = configparser.ConfigParser()
    for engine_file_name in engine_list:
        print(engine_file_name)
        if is_exe(engine_path + os.sep + engine_file_name):
            engine = uci.Engine(engine_path + os.sep + engine_file_name)
            if engine:
                try:
                    config[engine_file_name[2:]] = {
                        'file': engine_file_name,
                        'name': engine.get().name,
                        'has_levels': engine.has_levels(),
                        'has_chess960': engine.has_chess960()
                    }
                except AttributeError:
                    pass
                engine.quit()
    with open(engine_path + os.sep + 'engines.ini', 'w') as configfile:
        config.write(configfile)


def read_engine_ini(engine_shell=None, engine_path=None):
    config = configparser.ConfigParser()
    try:
        if engine_shell is None:
            if not engine_path:
                program_path = os.path.dirname(os.path.realpath(__file__)) + os.sep
                engine_path = program_path + 'engines' + os.sep + platform.machine()
            config.read(engine_path + os.sep + 'engines.ini')
        else:
            with engine_shell.open(engine_path + os.sep + 'engines.ini', 'r') as file:
                config.read_file(file)
    except FileNotFoundError:
        pass

    library = []
    for section in config.sections():
        library.append((engine_path + os.sep + config[section]['file'], section, config[section].getboolean('has_levels')))
    return library


def hours_minutes_seconds(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return h, m, s

try:
    from shutil import which
except ImportError:  # pragma: no cover
    # Implementation from Python 3.3
    import sys

    def which(cmd, mode=os.F_OK | os.X_OK, path=None):
        """Given a command, mode, and a PATH string, return the path which
        conforms to the given mode on the PATH, or None if there is no such
        file.

        `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
        of os.environ.get("PATH"), or can be overridden with a custom search
        path.

        """
        # Check that a given file can be accessed with the correct mode.
        # Additionally check that `file` is not a directory, as on Windows
        # directories pass the os.access check.
        def _access_check(fn, mode):
            return (os.path.exists(fn) and os.access(fn, mode)
                    and not os.path.isdir(fn))

        # If we're given a path with a directory part, look it up directly rather
        # than referring to PATH directories. This includes checking relative to the
        # current directory, e.g. ./script
        if os.path.dirname(cmd):
            if _access_check(cmd, mode):
                return cmd
            return None

        if path is None:
            path = os.environ.get("PATH", os.defpath)
        if not path:
            return None
        path = path.split(os.pathsep)

        if sys.platform == "win32":
            # The current directory takes precedence on Windows.
            if not os.curdir in path:
                path.insert(0, os.curdir)

            # PATHEXT is necessary to check on Windows.
            pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
            # See if the given file matches any of the expected path extensions.
            # This will allow us to short circuit when given "python.exe".
            # If it does match, only test that one, otherwise we have to try
            # others.
            if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
                files = [cmd]
            else:
                files = [cmd + ext for ext in pathext]
        else:
            # On other platforms you don't have things like PATHEXT to tell you
            # what file suffixes are executable, so just pass on cmd as-is.
            files = [cmd]

        seen = set()
        for dir in path:
            normdir = os.path.normcase(dir)
            if not normdir in seen:
                seen.add(normdir)
                for thefile in files:
                    name = os.path.join(dir, thefile)
                    if _access_check(name, mode):
                        return name
        return None


def update_picochess(auto_reboot=False):
    git = which('git.exe' if platform.system() == 'Windows' else 'git')
    if git:
        branch = subprocess.Popen([git, "rev-parse", "--abbrev-ref", "HEAD"],
                                  stdout=subprocess.PIPE).communicate()[0].decode(encoding='UTF-8').rstrip()
        if branch == 'stable' or branch == 'master':
            # Fetch remote repo
            output = subprocess.Popen([git, "remote", "update"],
                                      stdout=subprocess.PIPE).communicate()[0].decode(encoding='UTF-8')
            logging.debug(output)
            # Check if update is needed
            output = subprocess.Popen([git, "status", "-uno"],
                                      stdout=subprocess.PIPE).communicate()[0].decode(encoding='UTF-8')
            logging.debug(output)
            if 'up-to-date' not in output:
                # Update
                logging.debug('updating picochess')
                output = subprocess.Popen(["pip3", "install", "-r", "requirements.txt"],
                                          stdout=subprocess.PIPE).communicate()[0].decode(encoding='UTF-8')
                logging.debug(output)
                output = subprocess.Popen([git, "pull", "origin", branch],
                                          stdout=subprocess.PIPE).communicate()[0].decode(encoding='UTF-8')
                logging.debug(output)
                if auto_reboot:
                    reboot()


def shutdown(dgtpi):
    logging.debug('shutting down system')
    time.sleep(1)  # give some time to send out the pgn file
    if platform.system() == 'Windows':
        os.system('shutdown /s')
    elif dgtpi:
        os.system('systemctl isolate dgtpistandby.target')
    else:
        os.system('shutdown -h now')


def reboot():
    logging.debug('rebooting system')
    time.sleep(1)  # give some time to send out the pgn file
    os.system('reboot')


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("google.com", 80))
        return s.getsockname()[0]

    # TODO: Better handling of exceptions of socket connect
    except socket.error:
        logging.error("no internet connection!")
    finally:
        s.close()


def get_location():
    try:
        response = urllib.request.urlopen('http://www.telize.com/geoip/')
        j = json.loads(response.read().decode())
        country = j['country'] + ' ' if 'country' in j else ''
        country_code = j['country_code'] + ' ' if 'country_code' in j else ''
        city = j['city'] + ', ' if 'city' in j else ''
        return city + country + country_code
    except:
        return '?'
