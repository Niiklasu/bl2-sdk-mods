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
from copy import deepcopy
from typing import TYPE_CHECKING, TypedDict, cast
from unrealsdk import find_enum
from unrealsdk.hooks import Type
from coroutines.loop import TickCoroutine, start_coroutine_tick
from coroutines import (
    PostRenderCoroutine,
    WaitForSeconds,
    WaitUntil,
    start_coroutine_post_render,
)
from mods_base import ENGINE, build_mod, get_pc, hook, options
from mods_base.keybinds import keybind
from mods_base.mod import CoopSupport, Game
from networking.decorators import targeted
from networking.factory import add_network_functions
from ui_utils.hud_message import show_hud_message
from .meter_options import (
    MeterOptions,
    RHS_COLUMNS,
    ColorBy,
    ColumnType,
    opt_grp_columns,
    opt_color_by,
    opt_show_bars,
    opt_show_class,
)
from .ui import drawing
from .ui.options import opt_show_example_ui

if TYPE_CHECKING:
    from bl2 import (
        Canvas,
        GameEngine,
        Object,
        WillowGameEngine,
        WillowGameViewportClient,
        WillowPawn,
        WillowPlayerController,
        WorldInfo,
    )


# region Types and Constants


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
    drawing.ZERO_CYAN_COLOR,
    drawing.AXTON_GREEN_COLOR,
    drawing.GAIGE_PURPLE_COLOR,
    drawing.KRIEG_RED_COLOR,
    drawing.MAYA_YELLOW_COLOR,
    drawing.SALVADOR_ORANGE_COLOR,
]

TITLE = "Damage Meter"

# endregion
# region Options


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

opt_include_overkill_damage = options.BoolOption(
    identifier="Include Overkill Damage",
    value=True,
    description="Whether to include overkill damage in the damage meter. E.g. killing an enemy with 100 health with a 200 damage shot would add 200 damage to the meter.",
)

opt_dps_update_interval = options.SliderOption(
    identifier="DPS Updates Interval in ms",
    value=500,
    min_value=100,
    max_value=5000,
    step=100,
    description="How often the DPS should be updated. Default is 500ms = 0.5 seconds.",
)

opt_share_per_five = options.SliderOption(
    identifier="Share Data Interval in ms",
    value=1000,
    min_value=100,
    max_value=5000,
    step=100,
    description="How often the data should be shared with clients. Lower values can lead to performance problems for the other clients. Default is 1000 ms = 1 second.",
)
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
    show_hud_message(TITLE, "Stats reset")


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
# region Manage Players, Calculate and Send Stats


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
    # dont think this is needed, but just to be sure
    if is_client():
        return

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

    # a bit hacky, but wait with dps calculation until first damage
    if max(stats["damage"] for stats in DamageMeterState.player_stats.values()) == 0:
        for player in DamageMeterState.player_stats:
            DamageMeterState.player_stats[player]["start_epoch"] = get_current_epoch()

    # FinalDamage only includes flesh/armor damage
    # Could split this for more detailed stats in the future
    damage_summary = args.Pipeline.DamageSummary
    damage = damage_summary.FinalDamage + damage_summary.DamageDealtToShields

    if not opt_include_overkill_damage.value:
        if damage > damage_summary.PreviousHealth:
            damage = damage_summary.PreviousHealth
    DamageMeterState.player_stats[instigator.PlayerReplicationInfo.PlayerName]["damage"] += int(damage)


## track dps independently of damage dealt
def coroutine_calculate_dps() -> TickCoroutine:
    while True:
        yield WaitForSeconds(opt_dps_update_interval.value / 1000)
        if not mod.is_enabled:
            return
        if is_client():
            continue

        # deepcopy to prevent error if player disconnects during iteration
        current_stats = deepcopy(DamageMeterState.player_stats)
        current_epoch = get_current_epoch()
        for player_name, stats in current_stats.items():
            if not DamageMeterState.is_paused:
                stats["dps"] = max(stats["damage"] / (current_epoch - stats["start_epoch"] + 1), 0)
        DamageMeterState.player_stats = current_stats


## send stats to clients


def coroutine_send_stats() -> TickCoroutine:
    while True:
        yield WaitForSeconds(opt_share_per_five.value / 1000)
        if not mod.is_enabled:
            return
        if is_client():
            continue

        pc = get_pc_cast()
        disconnected_players = []
        for player_name, stats in DamageMeterState.player_stats.items():

            # mark disconnected players
            pri = next((pri for pri in pc.WorldInfo.GRI.PRIArray if pri.PlayerName == player_name), None)
            if pri is None:
                disconnected_players.append(player_name)
                continue

            # send stats to clients
            if pri != pc.PlayerReplicationInfo:
                send_stats_single_target(pri, DamageMeterState.player_stats)

        # remove disconnected players
        for player in disconnected_players:
            del DamageMeterState.player_stats[player]


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


canv = drawing.Drawing(options=MeterOptions, hidden_options=[MeterOptions.FONT, MeterOptions.SHOW_BARS])


def draw_meter(canvas: Canvas, player_stats: dict[str, PlayerStats]) -> None:
    canv.reset_state(canvas)
    canv.draw_background()

    class_title_text = " - Class" if opt_show_class.value else ""
    canv.draw_text_current_line("Name" + class_title_text, drawing.GOLD_COLOR)

    pos = 0
    for type, toggled_option in RHS_COLUMNS.items():
        if toggled_option.value:
            canv.draw_text_rhs_column(type.value, pos, drawing.GOLD_COLOR)
            pos += 1

    canv.new_line()

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
            canv.draw_bar(percent, variable_color)
        else:
            text_color = variable_color
            canv.draw_hline_top(drawing.WHITE_COLOR)

        values: dict[ColumnType, str] = {
            ColumnType.PARTY_PERCENT: f"{player_damage / total_damage if total_damage > 0 else 1:.0%}",
            ColumnType.DAMAGE: human_format(player_damage),
            ColumnType.DPS: human_format(stats["dps"]),
        }

        class_text = (" - " + class_attrs["display_name"]) if opt_show_class.value else ""
        canv.draw_text_current_line(player_name + class_text, text_color)

        pos = 0
        for type, toggled_option in RHS_COLUMNS.items():
            if toggled_option.value:
                canv.draw_text_rhs_column(values[type], pos, text_color)
                pos += 1

        canv.new_line()


## draw meter in game
def coroutine_draw_meter() -> PostRenderCoroutine:
    while True:
        yield WaitUntil(lambda: get_pc().GetHUDMovie() is not None)
        if not mod.is_enabled:
            return
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
    start_coroutine_tick(coroutine_calculate_dps())
    opt_show_example_ui.value = False


mod = build_mod(
    options=[
        opt_default_active,
        opt_include_overkill_damage,
        opt_dps_update_interval,
        opt_share_per_five,
        canv.opt_group,
    ],
    on_enable=on_enable,
    coop_support=CoopSupport.RequiresAllPlayers,  # not all but atleast host
    supported_games=Game.BL2,
)


add_network_functions(mod)

# endregion
