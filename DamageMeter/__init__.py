from __future__ import annotations

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
from networking.decorators import broadcast
from networking.factory import add_network_functions
from unrealsdk import find_enum
from unrealsdk.unreal import BoundFunction
from ui_utils.hud_message import show_hud_message

if TYPE_CHECKING:
    from bl2 import (
        WillowGameReplicationInfo,
        WillowPlayerController,
        Object,
        GameEngine,
        WillowPawn,
        WorldInfo,
        WillowGameEngine,
    )


# region Enums, Types and Constants


# maybe overengineered but whatever, maybe this will be useful in the future
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
    pause_dps: int


class Columns(TypedDict):
    title: str
    position_from_right: int


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

RHS_COLUMNS: dict[str, int] = {
    "Party%": 0,
    "Dmg": 1,
    "DPS": 2,
}

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


def reset_damage_meter() -> None:
    DamageMeterState.highest_damage = 1
    for player in DamageMeterState.player_stats:
        DamageMeterState.player_stats[player].update(damage=0)


@keybind("Enable/Disable Meter", key="F10")
def start_meter() -> None:
    reset_damage_meter()
    DamageMeterState.is_hidden = not DamageMeterState.is_hidden
    DamageMeterState.is_paused = DamageMeterState.is_hidden


@keybind("Reset Meter", key="O")
def reset_meter() -> None:
    reset_damage_meter()
    show_hud_message(TITLE, "Stats resetted")


@keybind("(Un)Pause Meter", key="P")
def pause_meter() -> None:
    DamageMeterState.is_paused = not DamageMeterState.is_paused
    if DamageMeterState.is_paused:
        for player in DamageMeterState.player_stats:
            current_epoch = cast("GameEngine", ENGINE).GetCurrentWorldInfo().TimeSeconds
            DamageMeterState.player_stats[player].update(
                pause_dps=human_format(
                    DamageMeterState.player_stats[player]["damage"] / (current_epoch - DamageMeterState.start_epoch + 1)
                )
            )
        DamageMeterState.pause_start_epoch = cast("GameEngine", ENGINE).GetCurrentWorldInfo().TimeSeconds
    else:
        DamageMeterState.start_epoch += (
            cast("GameEngine", ENGINE).GetCurrentWorldInfo().TimeSeconds - DamageMeterState.pause_start_epoch
        )
    show_hud_message(TITLE, "Damage tracking paused" if DamageMeterState.is_paused else "Damage tracking resumed")


# endregion
# region Current State


# dummy_stats: dict[str, PlayerStats] = {
#     "Player1": {"number": 1, "damage": 1_000_000, "character_class": CharacterClass.SALVADOR},
#     "Player2": {"number": 2, "damage": 250_000_000, "character_class": CharacterClass.GAIGE},
#     "Player3": {"number": 3, "damage": 1_000_000_000, "character_class": CharacterClass.KRIEG},
# }


class DamageMeterState:
    is_hidden: bool = True
    is_paused: bool = True
    player_stats: dict[str, PlayerStats] = {}
    highest_damage: int = 1
    next_player_nr: int = 0
    start_epoch: float = 0
    pause_start_epoch: float = 0


# endregion
# region Hooks and Coroutines


# TODO
# @hook("WillowGame.WillowGameReplicationInfo:AddPRI")
# def on_add_pri(
#     obj: WillowGameReplicationInfo,
#     args: WillowGameReplicationInfo._AddPRI.args,
#     _ret: WillowGameReplicationInfo._AddPRI.ret,
#     _func: BoundFunction,
# ) -> None:
#     print("ADD PRI")
#     print(args.PRI.PlayerName)
#     print(str(obj.PRIArray))


# @hook("WillowGame.WillowGameReplicationInfo:RemovePRI")
# def on_remove_pri(
#     obj: WillowGameReplicationInfo,
#     args: WillowGameReplicationInfo._RemovePRI.args,
#     _ret: WillowGameReplicationInfo._RemovePRI.ret,
#     _func: BoundFunction,
# ) -> None:
#     print("REMOVE PRI")
#     print(args.PRI.PlayerName)
#     print(str(obj.PRIArray))


## Reset my stats on spawn (changing character/reloading game)


@hook("WillowGame.WillowPlayerController:ShouldLoadSaveGameOnSpawn")
def on_spawn(
    pc: WillowPlayerController,
    args: WillowPlayerController._ShouldLoadSaveGameOnSpawn.args,
    _ret: WillowPlayerController._ShouldLoadSaveGameOnSpawn.ret,
    _func: BoundFunction,
) -> None:
    # have to check if hook is called client side, for now we always ignore client side
    if is_client():
        return
    if not args.bIsInitialSpawn:
        return
    DamageMeterState.player_stats[pc.PlayerReplicationInfo.PlayerName] = {
        "number": DamageMeterState.next_player_nr,
        "damage": 0,
        # "tanked_damage": 0,
        "character_class": CharacterClass(pc.PlayerClass.CharacterNameId.CharacterName),
    }
    DamageMeterState.next_player_nr += 1


## Registering and Distributing Damage


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

    # add tanked damage stats in the future
    if obj.Class.Name == "WillowPlayerPawn":
        return

    instigator = args.InstigatedBy

    # discord if enviroment damage or other AI
    if instigator is None or instigator.Class.Name != "WillowPlayerController":
        return
    instigator = cast("WillowPlayerController", instigator)

    # ignore self damage
    if instigator == obj.Controller:
        return

    player_name = instigator.PlayerReplicationInfo.PlayerName
    new_stats = DamageMeterState.player_stats

    if player_name not in new_stats:
        new_stats[player_name] = {
            "damage": 0,
            # "tanked_damage": 0,
            "character_class": CharacterClass(instigator.PlayerClass.CharacterNameId.CharacterName),
        }

    # maybe a bit hacky, but we want to start the timer on the fist damage instance
    if DamageMeterState.highest_damage == 1:
        DamageMeterState.start_epoch = cast("GameEngine", ENGINE).GetCurrentWorldInfo().TimeSeconds

    # FinalDamage only includes flesh/armor damage
    # Could split this for more detailed stats in the future
    damage_summary = args.Pipeline.DamageSummary
    new_stats[player_name]["damage"] += int(damage_summary.FinalDamage) + int(damage_summary.DamageDealtToShields)


# how to check for client from the slide mod by @juso40
e_net_mode: WorldInfo.ENetMode = cast("WorldInfo.ENetMode", find_enum("ENetMode"))


def is_client() -> bool:
    return cast("WillowGameEngine", ENGINE).GetCurrentWorldInfo().NetMode == e_net_mode.NM_Client


@broadcast.json_message
def client_store_stats(stats: dict[str, PlayerStats]) -> None:
    if not is_client():
        return
    DamageMeterState.player_stats = stats


def coroutine_send_stats_every_second() -> PostRenderCoroutine:
    while True:
        yield WaitForSeconds(0.5)
        client_store_stats(DamageMeterState.player_stats)


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
        drawing.draw_background(drawing.GRAY_COLOR_BG)

        # currently having to make sure the dolumn header and values are aligned.
        # user should customize columns in the future, fix that then
        drawing.draw_text_current_line("Name - Class", drawing.GOLD_COLOR)
        for title, position_from_right in RHS_COLUMNS.items():
            drawing.draw_text_rhs_column(title, position_from_right, drawing.GOLD_COLOR)

        drawing.new_line()

        # sort by damage dealt

        current_epoch = cast("GameEngine", ENGINE).GetCurrentWorldInfo().TimeSeconds
        total_damage = max(1, sum(stats["damage"] for stats in current_state.player_stats.values()))
        for player_name, stats in sorted(
            current_state.player_stats.items(), key=lambda x: x[1]["damage"], reverse=True
        ):
            class_attrs = ATTRIBUTES[stats["character_class"]]
            my_damage = stats["damage"]
            if my_damage > current_state.highest_damage:
                current_state.highest_damage = my_damage

            # is used for either the bar or text, depending on whether the bars are shown
            variable_color = (
                class_attrs["color"]
                if opt_color_by.value == ColorBy.CLASS.value
                # for testing and in case someone is able to play w/ more than 4 players
                else PLAYER_COLORS[min(len(PLAYER_COLORS) - 1, stats["number"])]
            )
            if opt_show_bars.value:
                text_color = drawing.WHITE_COLOR
                drawing.draw_bar(my_damage / current_state.highest_damage, variable_color)
            else:
                text_color = variable_color
                drawing.draw_hline_top(drawing.WHITE_COLOR)

            drawing.draw_text_current_line(
                player_name + " - " + class_attrs["display_name"],
                text_color,
            )
            drawing.draw_text_rhs_column(f"{my_damage / total_damage:.0%}", RHS_COLUMNS["Party%"], text_color)
            drawing.draw_text_rhs_column(human_format(my_damage), RHS_COLUMNS["Dmg"], text_color)
            drawing.draw_text_rhs_column(
                (
                    stats["pause_dps"]
                    if DamageMeterState.is_paused
                    else human_format(my_damage / (current_epoch - DamageMeterState.start_epoch + 1))
                ),
                RHS_COLUMNS["DPS"],
                text_color,
            )
            drawing.new_line()


# endregion
# region Mod Setup


def on_enable():
    start_coroutine_post_render(coroutine_send_stats_every_second())
    start_coroutine_post_render(coroutine_draw_meter())


mod = build_mod(
    options=[
        opt_default_active,
        opt_color_by,
        opt_show_bars,
        drawing.opt_grp_drawing,
    ],
    on_enable=on_enable,
    coop_support=CoopSupport.RequiresAllPlayers,  # not all but atleast host
    supported_games=Game.BL2,
)


add_network_functions(mod)

# endregion
