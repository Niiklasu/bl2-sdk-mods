from __future__ import annotations

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
from collections import OrderedDict
from enum import Enum
from typing import TYPE_CHECKING, TypedDict, cast
from DamageMeter import drawing
from coroutines import start_coroutine_post_render, WaitForSeconds, PostRenderCoroutine, WaitUntil
from mods_base import ENGINE, get_pc, hook, build_mod, options
from mods_base.keybinds import keybind
from mods_base.mod import CoopSupport, Game
from networking.decorators import targeted
from networking.factory import add_network_functions
from unrealsdk import find_enum
from unrealsdk.hooks import Type
from ui_utils.hud_message import show_hud_message

if TYPE_CHECKING:
    from bl2 import (
        WillowGameViewportClient,
        WillowPlayerController,
        Object,
        GameEngine,
        WillowPawn,
        WorldInfo,
        WillowGameEngine,
        Canvas,
    )


# region Enums, Types and Constants


class ColumnType(str, Enum):
    PARTY_PERCENT = "Party%"
    DAMAGE = "Dmg"
    DPS = "DPS"


class ColorBy(str, Enum):
    PLAYER = "Player"
    CLASS = "Class"


class CharacterAttributes(TypedDict):
    color: Object.Color
    display_name: str


class PlayerStats(TypedDict):
    number: int
    character_class: str
    damage: int
    dps: float
    start_epoch: float


ATTRIBUTES: dict[str, CharacterAttributes] = {
    "Axton": {"color": drawing.AXTON_GREEN_COLOR, "display_name": "Axton"},
    "Maya": {"color": drawing.MAYA_YELLOW_COLOR, "display_name": "Maya"},
    "Salvador": {"color": drawing.SALVADOR_ORANGE_COLOR, "display_name": "Salvador"},
    "Zero": {"color": drawing.ZERO_CYAN_COLOR, "display_name": "Zer0"},
    "Gaige": {"color": drawing.GAIGE_PURPLE_COLOR, "display_name": "Gaige"},
    "Krieg": {"color": drawing.KRIEG_RED_COLOR, "display_name": "Krieg"},
}

PLAYER_COLORS = [
    drawing.AXTON_GREEN_COLOR,
    drawing.ZERO_CYAN_COLOR,
    drawing.GAIGE_PURPLE_COLOR,
    drawing.KRIEG_RED_COLOR,
    drawing.MAYA_YELLOW_COLOR,
    drawing.SALVADOR_ORANGE_COLOR,
]

TITLE = "Damage Meter"

# super ugly for now, might update one day
DEFAULT_OPT_VALUES = {
    "Active by Default": False,
    "Show Example UI": False,
    "Colored By": ColorBy.CLASS,
    "Show Bars": True,
    "Show Class": True,
    "Show DPS": True,
    "Show Total Damage": True,
    "Show Party Percentage": True,
}
DEFAULT_OPT_VALUES.update(drawing.DEFAULT_OPT_VALUES)

# endregion
# region Options


def on_default_active_change(_, value: bool) -> None:
    if value and DamageMeterState.is_hidden:
        DamageMeterState.is_hidden = False
        DamageMeterState.is_paused = False


opt_default_active = options.BoolOption(
    identifier="Active by Default",
    value=DEFAULT_OPT_VALUES["Active by Default"],
    description="Whether the mod should be active by default",
    on_change=on_default_active_change,
)

opt_show_example_ui = options.BoolOption(
    identifier="Show Example UI",
    value=DEFAULT_OPT_VALUES["Show Example UI"],
    description="Show an example meter. More than 4 players to show you the different options. IMPORTANT: Toggle off when you're done.",
)

opt_color_by = options.SpinnerOption(
    identifier="Colored By",
    value=DEFAULT_OPT_VALUES["Colored By"],
    choices=[cb.value for cb in ColorBy],
    description="CLASS means multiple players with the same class get the same color, PLAYER means each player gets a unique color",
    wrap_enabled=True,
)

opt_show_bars = options.BoolOption(
    identifier="Show Bars",
    value=DEFAULT_OPT_VALUES["Show Bars"],
    description="Whether to show bars for the damage or just the text",
)

opt_show_class = options.BoolOption(
    identifier="Show Class",
    value=DEFAULT_OPT_VALUES["Show Class"],
    description="Whether to show the class of the player or not",
)


def toggle_columns(type: ColumnType, value: bool) -> None:
    RHS_COLUMNS[type] = value


opt_show_dps = options.BoolOption(
    identifier="Show DPS",
    value=DEFAULT_OPT_VALUES["Show DPS"],
    description="Whether to show the DPS column or not",
)

opt_show_total_dmg = options.BoolOption(
    identifier="Show Total Damage",
    value=DEFAULT_OPT_VALUES["Show Total Damage"],
    description="Whether to show the total damage column or not",
)

opt_show_party_percent = options.BoolOption(
    identifier="Show Party Percentage",
    value=DEFAULT_OPT_VALUES["Show Party Percentage"],
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
    children=[opt_show_dps, opt_show_total_dmg, opt_show_party_percent],
    description="Which columns to show in the damage meter",
)

opt_grp_drawing = options.NestedOption(
    identifier="UI Options",
    children=[
        opt_show_example_ui,
        opt_color_by,
        # opt_show_bars,
        opt_show_class,
        drawing.opt_x_pos,
        drawing.opt_y_pos,
        drawing.opt_bg_opacity,
        drawing.opt_width,
        drawing.opt_line_height,
        drawing.opt_column_width,
        # drawing.opt_font,
        opt_grp_columns,
    ],
    description="Options for drawing the UI of the damage meter",
)


def reset_ui_options(_) -> None:
    reset_options(opt_grp_drawing.children)


def reset_options(opts: list[options.BaseOption]) -> None:
    for option in opts:
        if isinstance(option, options.ValueOption):
            option.value = DEFAULT_OPT_VALUES[option.identifier]
        elif isinstance(option, options.GroupedOption) or isinstance(option, options.NestedOption):
            reset_options(option.children)


opt_reset_ui = options.ButtonOption(
    identifier="Reset UI",
    description="Reset the UI to the default position. IMPORTANT: Leave the UI Options menu and re-enter to see the changes on the sliders.",
    on_press=reset_ui_options,
)

opt_grp_drawing.children.append(opt_reset_ui)

# endregion
# region Keybinds


def reset_damage_meter() -> None:
    for player in DamageMeterState.player_stats:
        DamageMeterState.player_stats[player].update(damage=0, dps=0)


@keybind("Enable/Disable Meter", key="F10")
def start_meter() -> None:
    DamageMeterState.is_hidden = not DamageMeterState.is_hidden
    if is_client():
        return
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
    current_state = DamageMeterState

    # first add back time that passed during the pause,
    # then "oficially" unpause to make sure the coroutine definetly uses the correct time
    if current_state.is_paused:
        for player in current_state.player_stats:

            # players that joined after the pause started need to be handled separately
            if current_state.player_stats[player]["start_epoch"] > current_state.pause_start_epoch:
                current_state.player_stats[player]["start_epoch"] = get_current_epoch()
            else:
                current_state.player_stats[player]["start_epoch"] += (
                    get_current_epoch() - current_state.pause_start_epoch
                )
    else:
        current_state.pause_start_epoch = get_current_epoch()

    current_state.is_paused = not current_state.is_paused
    show_hud_message(TITLE, "Damage tracking " + ("paused" if current_state.is_paused else "resumed"))


# endregion
# region Calculate and Send Stats


## State


class DamageMeterState:
    # Client side
    is_hidden: bool = not opt_default_active.value

    # Server side
    is_paused: bool = False
    pause_start_epoch: float = 0

    # Shared from server to client
    player_stats: dict[str, PlayerStats] = {}


## helper functions


def get_pc_cast() -> WillowPlayerController:
    return cast("WillowPlayerController", get_pc())


def get_current_epoch() -> float:
    return cast("GameEngine", ENGINE).GetCurrentWorldInfo().TimeSeconds


e_net_mode: WorldInfo.ENetMode = cast("WorldInfo.ENetMode", find_enum("ENetMode"))


def is_client() -> bool:
    return cast("WillowGameEngine", ENGINE).GetCurrentWorldInfo().NetMode == e_net_mode.NM_Client


## add new players to the meter
@hook("WillowGame.WillowPlayerController:SpawningProcessComplete", Type.PRE)
def on_spawn(
    obj: WillowPlayerController,
    __args: WillowPlayerController._SpawningProcessComplete.args,
    __ret: WillowPlayerController._SpawningProcessComplete.ret,
    __func: WillowPlayerController._SpawningProcessComplete,
) -> None:
    if is_client():
        return
    current_state = DamageMeterState
    player_name = obj.PlayerReplicationInfo.PlayerName
    if player_name in current_state.player_stats:
        number = current_state.player_stats[player_name]["number"]
    else:
        number = len(current_state.player_stats)

    current_state.player_stats[player_name] = {
        "number": number,
        "character_class": obj.PlayerClass.CharacterNameId.CharacterName,
        "damage": 0,
        "dps": 0,
        "start_epoch": get_current_epoch(),
    }


## track damage dealt
@hook("WillowGame.WillowPawn:TookDamageFromEnemy")
def took_damage_from_enemy(
    obj: WillowPawn,
    args: WillowPawn._TookDamageFromEnemy.args,
    __ret: WillowPawn._TookDamageFromEnemy.ret,
    __func: WillowPawn._TookDamageFromEnemy,
) -> None:
    if DamageMeterState.is_paused:
        return

    # discard if a player got damaged (prevent counting friendly fire/damaging yourself)
    # could track taken damage in the future
    if obj.Class.Name == "WillowPlayerPawn":
        return

    # discard enviroment / other AI damage
    instigator = args.InstigatedBy
    if instigator is None or instigator.Class.Name != "WillowPlayerController":
        return
    instigator = cast("WillowPlayerController", instigator)

    # wait with dps calculation until first damage
    if max(stats["damage"] for stats in DamageMeterState.player_stats.values()) == 0:
        for player in DamageMeterState.player_stats:
            DamageMeterState.player_stats[player]["start_epoch"] = get_current_epoch()

    # FinalDamage only includes flesh/armor damage
    # Could split this for more detailed stats in the future
    damage_summary = args.Pipeline.DamageSummary
    DamageMeterState.player_stats[instigator.PlayerReplicationInfo.PlayerName]["damage"] += int(
        damage_summary.FinalDamage + damage_summary.DamageDealtToShields
    )


## send stats to clients
def coroutine_send_stats() -> TickCoroutine:
    while True:
        yield WaitForSeconds(0.25)
        if is_client():
            continue

        # create a copy for the rare case that the dict canges size during iteration
        current_stats = DamageMeterState.player_stats.copy()
        current_epoch = get_current_epoch()

        for player, stats in current_stats.items():

            # remove disconnected players
            player_pri = next((pri for pri in get_pc_cast().WorldInfo.GRI.PRIArray if pri.PlayerName == player), None)
            if player_pri == None:
                del current_stats[player]
                continue

            if not DamageMeterState.is_paused:
                stats["dps"] = max(stats["damage"] / (current_epoch - stats["start_epoch"] + 1), 0)

            # send stats only to clients
            if player_pri == get_pc_cast().PlayerReplicationInfo:
                continue
            send_stats_single_target(player_pri, current_stats)


@targeted.json_message
def send_stats_single_target(stats: dict[str, PlayerStats]) -> None:
    DamageMeterState.player_stats = stats


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


def draw_meter(canvas: Canvas, player_stats: dict[str, PlayerStats]) -> None:
    drawing.reset_state(canvas)
    drawing.draw_background()

    class_title_text = " - Class" if opt_show_class.value else ""
    drawing.draw_text_current_line("Name" + class_title_text, drawing.GOLD_COLOR)

    pos = 0
    for type, toggled_option in RHS_COLUMNS.items():
        if toggled_option.value:
            drawing.draw_text_rhs_column(type.value, pos, drawing.GOLD_COLOR)
            pos += 1

    drawing.new_line()

    # sort by damage dealt

    total_damage = sum(stat["damage"] for stat in player_stats.values())
    for player_name, stats in sorted(player_stats.items(), key=lambda x: x[1]["damage"], reverse=True):
        class_attrs = ATTRIBUTES[stats["character_class"]]
        player_damage = stats["damage"]

        # is used for either the bar or text, depending on whether the bars are shown
        variable_color = (
            class_attrs["color"] if opt_color_by.value == ColorBy.CLASS.value else PLAYER_COLORS[stats["number"]]
        )

        if opt_show_bars.value:
            highest_damage = max(stats["damage"] for stats in player_stats.values())
            percent = player_damage / highest_damage if highest_damage > 0 else 1
            text_color = drawing.WHITE_COLOR
            drawing.draw_bar(percent, variable_color)
        else:
            text_color = variable_color
            drawing.draw_hline_top(drawing.WHITE_COLOR)

        values: dict[ColumnType, str] = {
            ColumnType.PARTY_PERCENT: f"{player_damage / total_damage if total_damage > 0 else 1:.0%}",
            ColumnType.DAMAGE: human_format(player_damage),
            ColumnType.DPS: human_format(stats["dps"]),
        }

        class_text = (" - " + class_attrs["display_name"]) if opt_show_class.value else ""
        drawing.draw_text_current_line(player_name + class_text, text_color)

        pos = 0
        for type, toggled_option in RHS_COLUMNS.items():
            if toggled_option.value:
                drawing.draw_text_rhs_column(values[type], pos, text_color)
                pos += 1

        drawing.new_line()


## draw meter in game
def coroutine_draw_meter() -> PostRenderCoroutine:
    while True:
        yield WaitUntil(lambda: get_pc().GetHUDMovie() is not None)
        canvas = yield
        if DamageMeterState.is_hidden or opt_show_example_ui.value:
            continue
        draw_meter(canvas, DamageMeterState.player_stats)


# draw example meter when setting is enabled
@hook("WillowGame.WillowGameViewportClient:PostRender", Type.POST)
def draw_example_ui(
    __obj: WillowGameViewportClient,
    args: WillowGameViewportClient._PostRender.args,
    __ret: WillowGameViewportClient._PostRender.ret,
    __func: WillowGameViewportClient._PostRender,
) -> None:
    if not opt_show_example_ui.value:
        return
    canvas = args.Canvas
    if canvas is None:
        return
    draw_meter(
        canvas,
        {
            "Player1": {"damage": 1245678900, "dps": 7650, "character_class": "Zero", "number": 0},
            "Player2": {"damage": 5238901230, "dps": 804321, "character_class": "Maya", "number": 1},
            "Player3": {"damage": 28941234560, "dps": 3021098, "character_class": "Krieg", "number": 2},
            "Player4": {"damage": 39012345678, "dps": 43008765, "character_class": "Gaige", "number": 3},
            "Player5": {"damage": 8123456789, "dps": 5650, "character_class": "Axton", "number": 4},
            "Player6": {"damage": 40123456789, "dps": 2021098, "character_class": "Krieg", "number": 5},
        },
    )
    drawing.draw_text_current_line("EXAMPLE UI - TOGGLE OFF AFTER CONFIGURATING", drawing.RED_COLOR)


# endregion
# region Mod Setup


def on_enable():
    start_coroutine_post_render(coroutine_draw_meter())
    start_coroutine_tick(coroutine_send_stats())
    opt_show_example_ui.value = False


mod = build_mod(
    options=[
        opt_default_active,
        opt_grp_drawing,
    ],
    on_enable=on_enable,
    coop_support=CoopSupport.RequiresAllPlayers,  # not all but atleast host
    supported_games=Game.BL2,
)


add_network_functions(mod)

# endregion
