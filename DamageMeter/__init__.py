from __future__ import annotations
from collections import OrderedDict

from coroutines.loop import TickCoroutine, start_coroutine_tick

try:
    assert __import__("coroutines").__version_info__ >= (1, 0), "This mod requires coroutines version 1.0 or higher"
    assert __import__("mods_base").__version_info__ >= (1, 8), "Please update the SDK"
    assert __import__("unrealsdk").__version_info__ >= (1, 7, 0), "Please update the SDK"
    assert __import__("networking").__version_info__ >= (1, 1), "Please update the SDK"
    assert __import__("ui_utils").__version_info__ >= (1, 1), "Please update the SDK"
except (AssertionError, ImportError) as ex:
    import webbrowser

    webbrowser.open("https://bl-sdk.github.io/willow2-mod-db/requirements?mod=DamageMeter")
    raise ex
from enum import Enum
from typing import TYPE_CHECKING, TypedDict, cast
from DamageMeter import drawing
from coroutines import start_coroutine_post_render, WaitForSeconds, PostRenderCoroutine, WaitUntil
from mods_base import ENGINE, get_pc, hook, build_mod, options
from mods_base.keybinds import keybind
from mods_base.mod import CoopSupport, Game
from networking.decorators import broadcast, targeted
from networking.factory import add_network_functions
from unrealsdk import find_enum
from unrealsdk.unreal import BoundFunction
from ui_utils.hud_message import show_hud_message

if TYPE_CHECKING:
    from bl2 import (
        PlayerReplicationInfo,
        WillowGameInfo,
        WillowPlayerController,
        Object,
        GameEngine,
        WillowPawn,
        WorldInfo,
        WillowGameEngine,
    )


# region Enums, Types and Constants


class ColumnType(str, Enum):
    PARTY_PERCENT = "Party%"
    DAMAGE = "Dmg"
    DPS = "DPS"


class ColorBy(str, Enum):
    PLAYER = "Player"
    CLASS = "Class"


# single source of truth for character name we get from the game -> enum
class CharacterClass(str, Enum):
    AXTON = "Axton"
    MAYA = "Maya"
    SALVADOR = "Salvador"
    ZER0 = "Zero"
    GAIGE = "Gaige"
    KRIEG = "Krieg"


class CharacterAttributes(TypedDict):
    color: Object.Color
    display_name: str


class PlayerStats(TypedDict):
    number: int
    damage: int
    # tanked_damage: int
    character_class: CharacterClass
    dps: int
    pause_dps: int


ATTRIBUTES: dict[CharacterClass, CharacterAttributes] = {
    CharacterClass.AXTON: {"color": drawing.AXTON_GREEN_COLOR, "display_name": "Axton"},
    CharacterClass.MAYA: {"color": drawing.MAYA_YELLOW_COLOR, "display_name": "Maya"},
    CharacterClass.SALVADOR: {"color": drawing.SALVADOR_ORANGE_COLOR, "display_name": "Salvador"},
    CharacterClass.ZER0: {"color": drawing.ZERO_CYAN_COLOR, "display_name": "Zer0"},
    CharacterClass.GAIGE: {"color": drawing.GAIGE_PURPLE_COLOR, "display_name": "Gaige"},
    CharacterClass.KRIEG: {"color": drawing.KRIEG_RED_COLOR, "display_name": "Krieg"},
}

PLAYER_COLORS = [
    drawing.AXTON_GREEN_COLOR,
    drawing.ZERO_CYAN_COLOR,
    drawing.KRIEG_RED_COLOR,
    drawing.GAIGE_PURPLE_COLOR,
]


TITLE = "Damage Meter"
# endregion
# region Options and Keybinds


def on_default_active_change(_, value: bool) -> None:
    if value and DamageMeterState.is_hidden:
        DamageMeterState.is_hidden = False
        DamageMeterState.is_paused = False


opt_default_active = options.BoolOption(
    identifier="Active by Default",
    value=False,
    description="Whether the mod should be active by default",
    on_change=on_default_active_change,
)

opt_color_by = options.SpinnerOption(
    identifier="Colored By",
    value=ColorBy.CLASS,
    choices=[cb.value for cb in ColorBy],
    description="Class means multiple players with the same class get the same color, Player means each player gets a unique color",
    wrap_enabled=True,
)


opt_show_bars = options.BoolOption(
    identifier="Show Bars",
    value=True,
    description="Whether to show bars for the damage or just the text",
)

opt_show_class = options.BoolOption(
    identifier="Show Class",
    value=True,
    description="Whether to show the class of the player or not",
)


def toggle_columns(type: ColumnType, value: bool) -> None:
    RHS_COLUMNS[type] = value


opt_show_dps = options.BoolOption(
    identifier="Show DPS",
    value=True,
    description="Whether to show the DPS column or not",
)

opt_show_total_dmg = options.BoolOption(
    identifier="Show Total Damage",
    value=True,
    description="Whether to show the total damage column or not",
)

opt_show_party_percent = options.BoolOption(
    identifier="Show Party Percentage",
    value=True,
    description="Whether to show the party percentage column or not",
)

RHS_COLUMNS: dict[ColumnType, options.BoolOption] = OrderedDict(
    [
        (ColumnType.PARTY_PERCENT, opt_show_party_percent),
        (ColumnType.DAMAGE, opt_show_total_dmg),
        (ColumnType.DPS, opt_show_dps),
    ]
)

opt_grp_columns = options.GroupedOption(
    identifier="Columns",
    children=[opt_show_party_percent, opt_show_total_dmg, opt_show_dps],
    description="Which columns to show in the damage meter",
)


def reset_damage_meter() -> None:
    DamageMeterState.highest_damage = 0
    for player in DamageMeterState.player_stats:
        DamageMeterState.player_stats[player].update(damage=0, dps=0, pause_dps=0)


@keybind("Enable/Disable Meter", key="F10")
def start_meter() -> None:
    DamageMeterState.is_hidden = not DamageMeterState.is_hidden
    DamageMeterState.is_paused = DamageMeterState.is_hidden
    if not is_client():
        reset_damage_meter()


@keybind("Reset Meter", key="O")
def reset_meter() -> None:
    if is_client():
        return
    reset_damage_meter()
    show_hud_message(TITLE, "Stats resetted")


@keybind("(Un)Pause Meter", key="P")
def pause_meter() -> None:
    if is_client():
        return
    clients_store_stats(DamageMeterState.player_stats, DamageMeterState.is_paused)
    DamageMeterState.is_paused = not DamageMeterState.is_paused
    if DamageMeterState.is_paused:
        for player in DamageMeterState.player_stats:
            DamageMeterState.player_stats[player].update(
                pause_dps=human_format(
                    DamageMeterState.player_stats[player]["damage"]
                    / (get_current_epoch() - DamageMeterState.start_epoch + 1)
                )
            )
        DamageMeterState.pause_start_epoch = get_current_epoch()
    else:
        DamageMeterState.start_epoch += get_current_epoch() - DamageMeterState.pause_start_epoch
    show_hud_message(TITLE, "Damage tracking " + "paused" if DamageMeterState.is_paused else "resumed")


# endregion
# region Current State


# dummy_stats: dict[str, PlayerStats] = {
#     "Player1": {"number": 1, "damage": 0, "character_class": CharacterClass.SALVADOR, "dps": 0, "pause_dps": 0},
#     "Player2": {"number": 2, "damage": 0, "character_class": CharacterClass.GAIGE, "dps": 0, "pause_dps": 0},
#     "Player3": {"number": 3, "damage": 0, "character_class": CharacterClass.KRIEG, "dps": 0, "pause_dps": 0},
# }


class DamageMeterState:
    is_hidden: bool = True
    is_paused: bool = True
    player_stats: dict[str, PlayerStats] = {}
    highest_damage: int = 0
    next_player_nr: int = 0
    start_epoch: float = 0
    pause_start_epoch: float = 0

    # for the host to keep track of the clients
    # only necessary because broadcoast sends too early and causes some console spam on the client that isnt game breaking but annoying
    PRIs: list[PlayerReplicationInfo] = []


# endregion
# region Functions, Hooks and Coroutines

## helper functions


def get_current_epoch() -> float:
    return cast("GameEngine", ENGINE).GetCurrentWorldInfo().TimeSeconds


# how to check for client from the slide mod by @juso40
e_net_mode: WorldInfo.ENetMode = cast("WorldInfo.ENetMode", find_enum("ENetMode"))


def is_client() -> bool:
    return cast("WillowGameEngine", ENGINE).GetCurrentWorldInfo().NetMode == e_net_mode.NM_Client


## Add/Remove Players


@hook("WillowGame.WillowPlayerController:ShouldLoadSaveGameOnSpawn")
def on_spawn(
    obj: WillowPlayerController,
    args: WillowPlayerController._ShouldLoadSaveGameOnSpawn.args,
    _ret: WillowPlayerController._ShouldLoadSaveGameOnSpawn.ret,
    _func: BoundFunction,
) -> None:
    # have to check if hook is called client side, for now we always ignore client side
    if is_client():
        return
    if not args.bIsInitialSpawn:
        return
    DamageMeterState.player_stats[obj.PlayerReplicationInfo.PlayerName] = {
        "number": DamageMeterState.next_player_nr,
        "damage": 0,
        # "tanked_damage": 0,
        "character_class": CharacterClass(obj.PlayerClass.CharacterNameId.CharacterName),
        "pause_dps": 0,
        "dps": 0,
    }
    DamageMeterState.next_player_nr += 1
    DamageMeterState.PRIs.append(obj.PlayerReplicationInfo)


@hook("WillowGame.WillowGameInfo:Logout")
def on_logout(
    obj: WillowGameInfo,
    args: WillowGameInfo._Logout.args,
    ret: WillowGameInfo._Logout.ret,
    _func: BoundFunction,
) -> None:
    if is_client():
        return
    try:
        del DamageMeterState.player_stats[args.Exiting.PlayerReplicationInfo.PlayerName]
        DamageMeterState.next_player_nr -= 1
        DamageMeterState.PRIs.remove(args.Exiting.PlayerReplicationInfo)
    except KeyError:
        # logout gets called during login / too early sometimes, so we ignore the error.
        # maybe a better hook exists to handle this
        pass


## Registering Damage and Distributing Stats


@hook("WillowGame.WillowPawn:TookDamageFromEnemy")
def took_damage_from_enemy(
    obj: WillowPawn,
    args: WillowPawn._TookDamageFromEnemy.args,
    __ret: WillowPawn._TookDamageFromEnemy.ret,
    __func: BoundFunction,
) -> None:
    # hook is only called on the server, so we broadcast the data to the clients in a coroutine
    if DamageMeterState.is_paused:
        return

    # add tanked damage stats in the future (also prevents counting friendly fire for now)
    if obj.Class.Name == "WillowPlayerPawn":
        return

    instigator = args.InstigatedBy

    # discard if enviroment damage or other AI
    if instigator is None or instigator.Class.Name != "WillowPlayerController":
        return
    instigator = cast("WillowPlayerController", instigator)

    # ignore self damage
    if instigator == obj.Controller:
        return

    player_name = instigator.PlayerReplicationInfo.PlayerName
    new_stats = DamageMeterState.player_stats

    if DamageMeterState.highest_damage == 0:
        DamageMeterState.start_epoch = get_current_epoch()
    # FinalDamage only includes flesh/armor damage
    # Could split this for more detailed stats in the future
    damage_summary = args.Pipeline.DamageSummary
    new_stats[player_name]["damage"] += int(damage_summary.FinalDamage) + int(damage_summary.DamageDealtToShields)


def clients_store_stats(stats: dict[str, PlayerStats], is_paused: bool) -> None:
    for pri in DamageMeterState.PRIs:
        inner_store_stats(pri, stats, is_paused)


@targeted.json_message
def inner_store_stats(stats: dict[str, PlayerStats], is_paused: bool) -> None:
    DamageMeterState.player_stats = stats
    DamageMeterState.is_paused = is_paused


def coroutine_send_stats() -> PostRenderCoroutine:
    while True:
        yield WaitForSeconds(0.5)
        clients_store_stats(DamageMeterState.player_stats, DamageMeterState.is_paused)


def coroutine_calc_dps() -> TickCoroutine:
    while True:
        yield WaitForSeconds(0.1)
        if DamageMeterState.is_paused:
            continue
        current_epoch = get_current_epoch()
        for player in DamageMeterState.player_stats:
            stats = DamageMeterState.player_stats[player]
            stats["dps"] = stats["damage"] / (current_epoch - DamageMeterState.start_epoch + 1)


# endregion
# region Drawing


# straight from SO @rtaft https://stackoverflow.com/a/45846841
def human_format(num: float) -> str:
    num = float("{:.3g}".format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return "{}{}".format("{:f}".format(num).rstrip("0").rstrip("."), ["", "K", "M", "B", "T", "Q", "E"][magnitude])


def coroutine_draw_meter() -> PostRenderCoroutine:
    while True:
        yield WaitUntil(lambda: get_pc().GetHUDMovie() is not None)
        canvas = yield
        current_state = DamageMeterState
        if current_state.is_hidden:
            continue

        drawing.reset_state(canvas)
        drawing.draw_background()

        class_title_text = " - Class" if opt_show_class.value else ""
        drawing.draw_text_current_line("Name" + class_title_text, drawing.GOLD_COLOR)

        pos = 0
        for type, toggld_option in RHS_COLUMNS.items():
            if toggld_option.value:
                drawing.draw_text_rhs_column(type.value, pos, drawing.GOLD_COLOR)
                pos += 1

        drawing.new_line()

        # sort by damage dealt
        total_damage = sum(stats["damage"] for stats in current_state.player_stats.values())
        for player_name, stats in sorted(
            current_state.player_stats.items(), key=lambda x: x[1]["damage"], reverse=True
        ):
            class_attrs = ATTRIBUTES[stats["character_class"]]
            player_damage = stats["damage"]

            # is used for either the bar or text, depending on whether the bars are shown
            variable_color = (
                class_attrs["color"]
                if opt_color_by.value == ColorBy.CLASS.value
                # for testing and in case someone is able to play w/ more than 4 players
                else PLAYER_COLORS[min(len(PLAYER_COLORS) - 1, stats["number"])]
            )

            if opt_show_bars.value:
                if player_damage > current_state.highest_damage:
                    current_state.highest_damage = player_damage
                percent = player_damage / current_state.highest_damage if current_state.highest_damage > 0 else 1
                text_color = drawing.WHITE_COLOR
                drawing.draw_bar(percent, variable_color)
            else:
                text_color = variable_color
                drawing.draw_hline_top(drawing.WHITE_COLOR)

            values: dict[ColumnType, str] = {
                ColumnType.PARTY_PERCENT: f"{player_damage / total_damage if total_damage > 0 else 1:.0%}",
                ColumnType.DAMAGE: human_format(player_damage),
                ColumnType.DPS: human_format(stats["pause_dps"] if DamageMeterState.is_paused else stats["dps"]),
            }

            class_text = (" - " + class_attrs["display_name"]) if opt_show_class.value else ""
            drawing.draw_text_current_line(player_name + class_text, text_color)

            pos = 0
            for type, toggld_option in RHS_COLUMNS.items():
                if toggld_option.value:
                    drawing.draw_text_rhs_column(values[type], pos, text_color)
                    pos += 1

            drawing.new_line()


# endregion
# region Mod Setup


def on_enable():
    start_coroutine_post_render(coroutine_draw_meter())
    if not is_client():
        start_coroutine_post_render(coroutine_send_stats())
        start_coroutine_tick(coroutine_calc_dps())


mod = build_mod(
    options=[
        opt_default_active,
        opt_color_by,
        opt_show_bars,
        opt_show_class,
        drawing.opt_grp_drawing,
        opt_grp_columns,
    ],
    on_enable=on_enable,
    coop_support=CoopSupport.RequiresAllPlayers,  # not all but atleast host
    supported_games=Game.BL2,
)


add_network_functions(mod)

# endregion
