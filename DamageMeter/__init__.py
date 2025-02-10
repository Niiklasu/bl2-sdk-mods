from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict, cast
from DamageMeter import drawing
from mods_base.keybinds import keybind
from mods_base.mod import CoopSupport, Game
from networking.decorators import broadcast
from networking.factory import add_network_functions
from unrealsdk import find_object, find_enum
from mods_base import ENGINE, hook, build_mod, options
from unrealsdk.unreal import BoundFunction

if TYPE_CHECKING:
    from bl2 import WillowGameEngine, WillowPlayerController, WillowPawn, WorldInfo, WillowGame


def on_default_active_change(_option: options.BoolOption, value: bool) -> None:
    DamageMeterState.is_logging = value


defaultActive = options.BoolOption(
    "DefaultActive",
    False,
    description="Whether the mod should be active by default",
    on_change=on_default_active_change,
)


class PlayerStats(TypedDict):
    damage: int
    # tanked_damage: int
    class_name: str


class DamageMeterState:
    is_logging = defaultActive.value
    player_stats: dict[str, PlayerStats] = {}


# from slide mod by @juso40
def is_client() -> bool:
    e_net_mode: WorldInfo.ENetMode = cast("WorldInfo.ENetMode", find_enum("ENetMode"))
    return cast("WillowGameEngine", ENGINE).GetCurrentWorldInfo().NetMode == e_net_mode.NM_Client


@broadcast.json_message
def store_stats(stats: dict[str, PlayerStats]) -> None:
    DamageMeterState.player_stats = stats


@hook("WillowGame.WillowPawn:TookDamageFromEnemy")
def took_damage_from_enemy(
    obj: WillowPawn,
    args: WillowPawn._TookDamageFromEnemy.args,
    __ret: WillowPawn._TookDamageFromEnemy.ret,
    __func: BoundFunction,
) -> None:
    # seems like hook isnt called on clients anyway (? not versed enought in sdk mods yet)
    # making sure to avoid unknown territory in case it is for some people
    if is_client():
        return

    # add tanked damage stats in the future
    # if obj.Class.Name == "WillowPlayerPawn":
    #     return

    instigator = args.InstigatedBy

    # discord if enviroment damage or other AI
    if instigator is None or instigator.Class.Name != "WillowPlayerController":
        return
    instigator = cast("WillowPlayerController", instigator)

    player_name = instigator.PlayerReplicationInfo.PlayerName
    new_stats = DamageMeterState.player_stats.copy()

    if player_name not in new_stats:
        new_stats[player_name] = {
            "damage": 0,
            # "tanked_damage": 0,
            "class_name": instigator.PlayerClass.CharacterNameId.CharacterName,
        }

    # FinalDamage only includes flesh/armor damage
    # Could split this for more detailed stats in the future
    damage_summary = args.Pipeline.DamageSummary
    new_stats[player_name]["damage"] += int(damage_summary.FinalDamage) + int(damage_summary.DamageDealtToShields)

    # call the broadcast function so all clients get the new stats
    store_stats(new_stats)


# straight from SO @rtaft https://stackoverflow.com/a/45846841
def human_format(num: float) -> str:
    num = float("{:.3g}".format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return "{}{}".format("{:f}".format(num).rstrip("0").rstrip("."), ["", "K", "M", "B", "T", "Q", "E"][magnitude])


@hook("WillowGame.WillowGameViewportClient:PostRender")
def post_render(
    obj: WillowGame.WillowGameViewportClient,
    args: WillowGame.WillowGameViewportClient._PostRender.args,
    __ret: WillowGame.WillowGameViewportClient._PostRender.ret,
    __func: BoundFunction,
) -> None:
    if not DamageMeterState.is_logging:
        return

    if args.Canvas is None:
        return

    if drawing.DrawingState.canvas is None:
        drawing.init(args.Canvas)

    drawing.DrawingState.num_displayed_lines = 0
    drawing.draw_text("DamageMeter", drawing.white_color)

    for player_name, stats in DamageMeterState.player_stats.items():
        drawing.draw_text(
            player_name + " - " + stats["class_name"] + ": " + human_format(stats["damage"]),
            drawing.white_color,
        )


@keybind("Show/Hide Meter", key="F10")
def start_meter() -> None:
    DamageMeterState.is_logging = not DamageMeterState.is_logging
    DamageMeterState.player_stats = {}


@keybind("Reset Meter", key="P")
def reset_meter() -> None:
    DamageMeterState.player_stats = {}


mod = build_mod(
    keybinds=[start_meter, reset_meter],
    hooks=[took_damage_from_enemy, post_render],
    coop_support=CoopSupport.RequiresAllPlayers,  # not all but atleast host
    supported_games=Game.BL2,
)

add_network_functions(mod)
