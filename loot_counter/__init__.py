from __future__ import annotations
import json
import sys
import pathlib
import enum
from types import ModuleType
from typing import TYPE_CHECKING, Callable, Optional, TypedDict, cast
from coroutines.loop import PostRenderCoroutine, WaitUntil, start_coroutine_post_render
from legacy_compat import legacy_compat
from mods_base import get_pc, options
from mods_base.keybinds import keybind
from mods_base.mod_factory import build_mod
from mods_base.settings import SETTINGS_DIR
from mods_base.hook import hook

Quickload = Optional[ModuleType]
with legacy_compat():
    try:
        import Quickload
    except ImportError:
        Quickload = None

if TYPE_CHECKING:
    from bl2 import WillowPickup, WillowItem, WillowInventory, WillowPawn, PauseGFxMovie
    from ui import drawing
else:
    from .ui import drawing


class RunData(TypedDict):
    runs: int
    tracked_rarities: dict[Rarity, int]
    tracked_items: dict[str, int]
    show_rarity: bool


class Rarity(str, enum.Enum):
    Uniques = "Uniques"
    Legendaries = "Legendaries"
    Pearlescents = "Pearlescents"
    Seraphs = "Seraphs"
    Effervescents = "Effervescents"


RANGES = {
    Rarity.Legendaries: [5, 7, 8, 9, 10],
    Rarity.Pearlescents: [500],
    Rarity.Seraphs: [501],
    Rarity.Effervescents: [506],
}
CLASS_WHITELIST = ["WillowWeapon", "WillowArtifact", "WillowGrenadeMod", "WillowShield", "WillowClassMod"]

BASE_PATH: pathlib.Path = SETTINGS_DIR / "LootCounter"
FARM_PATH: pathlib.Path = BASE_PATH / "farms"
DEFAULT_FARM: str = "default"
LAST_SESSION_FILE: str = r"last_session.txt"

# Options and keybinds

opt_enabled_by_default = options.BoolOption(
    identifier="Enabled by default",
    value=True,
    description="Whether the loot counter should be enabled by default",
)


@keybind("Toggle Loot Counter", "F3")
def toggle_loot_counter() -> None:
    CounterState.is_enabled = not CounterState.is_enabled


@keybind("Open Options", "F4")
def open_options() -> None:
    opt_box.show()


# Count Items


class CounterState:
    is_enabled: bool = opt_enabled_by_default.value

    current_farm: str = DEFAULT_FARM
    run_data: RunData = {
        "runs": 1,
        "tracked_rarities": {
            Rarity.Uniques: 0,
            Rarity.Legendaries: 0,
            Rarity.Pearlescents: 0,
            Rarity.Seraphs: 0,
            Rarity.Effervescents: 0,
        },
        "tracked_items": {},
        "show_rarity": True,
    }
    blocked_item: WillowInventory | None = None

    original_reload_map: Callable[[bool], None] | None = None


def count_item(inventory: WillowInventory, value: int) -> None:
    if CounterState.blocked_item is inventory:
        CounterState.blocked_item = None
        return
    if inventory.Class.Name not in CLASS_WHITELIST:
        return
    # all whitelisted classes are WillowItems
    item = cast("WillowItem", inventory)
    for rarity, values in RANGES.items():
        if item.RarityLevel in values:
            break
    else:
        if item.GenerateFunStatsText().find("#dc4646") != -1:
            rarity = Rarity.Uniques
        else:
            return

    data = CounterState.run_data
    data["tracked_rarities"][rarity] += value

    dropName = item.GenerateHumanReadableName()
    for tracked_item in data["tracked_items"]:
        if dropName.find(tracked_item) != -1:
            data["tracked_items"][tracked_item] += value


@hook("WillowGame.WillowPickup:EnableRagdollCollision")
def on_inventory_associated(
    obj: WillowPickup,
    _args: WillowPickup._EnableRagdollCollision.args,
    _ret: WillowPickup._EnableRagdollCollision.ret,
    _func: WillowPickup._EnableRagdollCollision,
) -> None:
    if not CounterState.is_enabled:
        return
    count_item(obj.Inventory, 1)


@hook("WillowGame.WillowPickup:AdjustPickupPhysicsAndCollisionForBeingAttached")
def on_mission_status_changed(
    obj: WillowPickup,
    _args: WillowPickup._AdjustPickupPhysicsAndCollisionForBeingAttached.args,
    _ret: WillowPickup._AdjustPickupPhysicsAndCollisionForBeingAttached.ret,
    _func: WillowPickup._AdjustPickupPhysicsAndCollisionForBeingAttached,
) -> None:
    if not CounterState.is_enabled:
        return
    count_item(obj.Inventory, 1)


@hook("WillowGame.WillowPawn:TossInventory")
def on_toss_inventory(
    _obj: WillowPawn,
    args: WillowPawn._TossInventory.args,
    _ret: WillowPawn._TossInventory.ret,
    _func: WillowPawn._TossInventory,
) -> None:
    if not CounterState.is_enabled:
        return
    CounterState.blocked_item = args.Inv


# Drawing


canv = drawing.Drawing()


def coroutine_draw_meter() -> PostRenderCoroutine:
    while True:
        yield WaitUntil(lambda: get_pc().GetHUDMovie() is not None)
        if not mod.is_enabled:
            return
        state = CounterState
        if not state.is_enabled:
            continue
        canvas = yield
        canv.reset_state(canvas)
        canv.draw_background()
        canv.draw_text_current_line("Farming: " + state.current_farm, drawing.WHITE_COLOR)
        canv.new_line()
        canv.draw_text_current_line("Runs: " + str(state.run_data["runs"]), drawing.WHITE_COLOR)
        canv.new_line()
        canv.draw_hline_top(color=drawing.WHITE_COLOR)

        if state.run_data["show_rarity"]:
            for rarity, value in state.run_data["tracked_rarities"].items():
                canv.draw_text_current_line(f"{rarity.name}: {value}", drawing.WHITE_COLOR)
                canv.new_line()

        if len(state.run_data["tracked_items"]) > 0:
            canv.draw_hline_top(color=drawing.WHITE_COLOR)

        for item, value in state.run_data["tracked_items"].items():
            canv.draw_text_current_line(f"{item}: {value}", drawing.WHITE_COLOR)
            canv.new_line()


# (Re)load Game


def save_farm(filename: str) -> None:
    with (FARM_PATH / f"{filename}.json").open("w") as file:
        file.write(json.dumps(CounterState.run_data))


def load_farm(filename: str) -> None:
    with (FARM_PATH / f"{filename}.json").open("r") as file:
        loaded_data = cast("RunData", json.load(file))
        data = CounterState.run_data
        CounterState.current_farm = filename
        data["runs"] = loaded_data["runs"]
        data["show_rarity"] = loaded_data["show_rarity"]
        for rarity in Rarity:
            data["tracked_rarities"][rarity] = loaded_data["tracked_rarities"][rarity.name]
        data["tracked_items"] = loaded_data["tracked_items"]


def save_session_info() -> None:
    with (BASE_PATH / LAST_SESSION_FILE).open("w") as file:
        file.write(CounterState.current_farm)


def on_quit_game() -> None:
    if not CounterState.is_enabled:
        return
    CounterState.run_data["runs"] += 1
    save_farm(CounterState.current_farm)
    save_session_info()


def override_reload_map(skip_save: bool) -> None:
    on_quit_game()
    CounterState.original_reload_map(skip_save)


@hook("WillowGame.PauseGFxMovie:CompleteQuitToMenu")
def on_quit_to_menu(_obj, _args, _ret, _func) -> None:
    on_quit_game()


@hook("Engine.PlayerController.NotifyDisconnect")
def on_disconnect(_obj, _args, _ret, _func) -> None:
    on_quit_game()


# Mod setup


def on_enable() -> None:

    if Quickload is not None:
        CounterState.original_reload_map = Quickload._ReloadCurrentMap
        Quickload._ReloadCurrentMap = override_reload_map

    FARM_PATH.mkdir(parents=True, exist_ok=True)

    try:
        with (BASE_PATH / LAST_SESSION_FILE).open("r") as file:
            last_farm = file.read()
            load_farm(last_farm)
    except FileNotFoundError:
        pass

    start_coroutine_post_render(coroutine_draw_meter())


def on_disable() -> None:
    if Quickload is not None:
        Quickload._ReloadCurrentMap = CounterState.original_reload_map


# prevent circular import
from loot_counter.option_box.boxes import opt_box

mod = build_mod(
    on_enable=on_enable,
    on_disable=on_disable,
    options=[opt_enabled_by_default, canv.opt_group],
)
