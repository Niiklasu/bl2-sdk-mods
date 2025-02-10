from __future__ import annotations

try:
    assert __import__("coroutines").__version_info__ >= (1, 0), "This mod requires coroutines version 1.0 or higher"
    assert __import__("mods_base").__version_info__ >= (1, 8), "Please update the SDK"
    assert __import__("unrealsdk").__version_info__ >= (1, 7, 0), "Please update the SDK"
    assert __import__("networking").__version_info__ >= (1, 1), "Please update the SDK"
except (AssertionError, ImportError) as ex:
    import webbrowser

    webbrowser.open("https://bl-sdk.github.io/willow2-mod-db/requirements?mod=DamageMeter")
    raise ex


from enum import Enum
from typing import TYPE_CHECKING, ClassVar, TypedDict, cast
from DamageMeter import drawing
from coroutines import start_coroutine_post_render, WaitForSeconds, PostRenderCoroutine, WaitUntil
from mods_base import ENGINE, get_pc, hook, build_mod, options
from mods_base.keybinds import keybind
from mods_base.mod import CoopSupport, Game
from networking.decorators import broadcast
from networking.factory import add_network_functions
from unrealsdk import find_enum
from unrealsdk.unreal import BoundFunction

if TYPE_CHECKING:
    from bl2 import WillowGameEngine, WillowPlayerController, WillowPawn, WorldInfo, Canvas, FrontendGFxMovie


def on_default_active_change(_option: options.BoolOption, value: bool) -> None:
    if value and DamageMeterState.is_hidden:
        DamageMeterState.is_hidden = False
        DamageMeterState.is_paused = False


defaultActive = options.BoolOption(
    identifier="Active by Default",
    value=False,
    description="Whether the mod should be active by default",
    on_change=on_default_active_change,
)

TITLE = "Damage Meter"


# single source of truth for character name from game -> enum
class CharacterClass(str, Enum):
    AXTON = "Axton"
    MAYA = "Maya"
    SALVADOR = "Salvador"
    ZER0 = "Zero"
    GAIGE = "Gaige"
    KRIEG = "Krieg"


class CharacterAttributes(TypedDict):
    color: Canvas.Color
    display_name: str


ATTRIBUTES: dict[CharacterClass, CharacterAttributes] = {
    CharacterClass.AXTON: {"color": drawing.axton_green_color, "display_name": "Axton"},
    CharacterClass.MAYA: {"color": drawing.maya_yellow_color, "display_name": "Maya"},
    CharacterClass.SALVADOR: {"color": drawing.salvador_orange_color, "display_name": "Salvador"},
    CharacterClass.ZER0: {"color": drawing.zero_cyan_color, "display_name": "Zer0"},
    CharacterClass.GAIGE: {"color": drawing.gaige_purple_color, "display_name": "Gaige"},
    CharacterClass.KRIEG: {"color": drawing.krieg_red_color, "display_name": "Krieg"},
}


class PlayerStats(TypedDict):
    damage: int
    # tanked_damage: int
    character_class: CharacterClass


class DamageMeterState:
    is_hidden: ClassVar[bool] = True
    is_paused: ClassVar[bool] = True
    player_stats: ClassVar[dict[str, PlayerStats]] = {}


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
        "damage": 0,
        # "tanked_damage": 0,
        "character_class": CharacterClass(pc.PlayerClass.CharacterNameId.CharacterName),
    }


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
    # if obj.Class.Name == "WillowPlayerPawn":
    #     return

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

    # FinalDamage only includes flesh/armor damage
    # Could split this for more detailed stats in the future
    damage_summary = args.Pipeline.DamageSummary
    new_stats[player_name]["damage"] += int(damage_summary.FinalDamage) + int(damage_summary.DamageDealtToShields)


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
        if DamageMeterState.is_hidden:
            continue

        drawing.reset_state(canvas)
        drawing.draw_background(drawing.gray_color_bg)

        drawing.draw_text_new_line(TITLE, drawing.gold_color)

        for player_name, stats in DamageMeterState.player_stats.items():
            drawing.draw_hline_under_text(drawing.white_color)
            player_class_attributes = ATTRIBUTES[stats["character_class"]]
            drawing.draw_text_new_line(
                player_name + " - " + player_class_attributes["display_name"] + ": " + human_format(stats["damage"]),
                player_class_attributes["color"],
            )


# from slide mod by @juso40
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
        yield WaitForSeconds(1)
        client_store_stats(DamageMeterState.player_stats)


@keybind("Enable/Disable Meter", key="F10")
def start_meter() -> None:
    DamageMeterState.player_stats = {}
    DamageMeterState.is_hidden = not DamageMeterState.is_hidden
    DamageMeterState.is_paused = DamageMeterState.is_hidden


@keybind("Reset Meter", key="O")
def reset_meter() -> None:
    DamageMeterState.player_stats = {}


@keybind("(Un)Pause Meter", key="P")
def pause_meter() -> None:
    DamageMeterState.is_paused = not DamageMeterState.is_paused


def on_enable():
    start_coroutine_post_render(coroutine_send_stats_every_second())
    start_coroutine_post_render(coroutine_draw_meter())


mod = build_mod(
    options=[defaultActive, drawing.opt_bg_opacity, drawing.opt_x_pos, drawing.opt_y_pos, drawing.opt_y_inc],
    hooks=[took_damage_from_enemy, on_spawn],
    on_enable=on_enable,
    coop_support=CoopSupport.RequiresAllPlayers,  # not all but atleast host
    supported_games=Game.BL2,
)


add_network_functions(mod)
