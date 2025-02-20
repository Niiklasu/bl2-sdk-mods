from __future__ import annotations
import json
import sys
import os
import pathlib
import enum
from types import ModuleType
from typing import TYPE_CHECKING, Callable, Optional, TypedDict, cast
from coroutines.loop import PostRenderCoroutine, WaitUntil, start_coroutine_post_render
from legacy_compat import legacy_compat
from mods_base import get_pc, options
from mods_base.keybinds import keybind
from mods_base.settings import SETTINGS_DIR
from mods_base.hook import hook
from mods_base.mod_factory import build_mod
from .ui import drawing

Quickload = Optional[ModuleType]
with legacy_compat():
    try:
        import Quickload
    except ImportError:
        Quickload = None

if TYPE_CHECKING:
    from bl2 import WillowPickup, WillowItem, WillowInventory, WillowPawn, TextChatGFxMovie, WillowPlayerController


class RunData(TypedDict):
    runs: int
    tracked_rarities: dict[Rarity, int]
    tracked_items: dict[str, int]


class Rarity(str, enum.Enum):
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
LAST_SESSION_FILE: str = r"last_session.txt"

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


class CounterState:
    is_enabled: bool = opt_enabled_by_default.value
    show_rarity: bool = True

    current_farm: str = "default"
    run_data: RunData = {
        "runs": 1,
        "tracked_rarities": {
            Rarity.Legendaries: 0,
            Rarity.Pearlescents: 0,
            Rarity.Seraphs: 0,
            Rarity.Effervescents: 0,
        },
        "tracked_items": {},
    }

    original_reload_map: Callable | None = None


def reset_current_farm() -> None:
    run_data = CounterState.run_data
    run_data.runs = 1
    run_data.tracked_rarities = {
        Rarity.Legendaries: 0,
        Rarity.Pearlescents: 0,
        Rarity.Seraphs: 0,
        Rarity.Effervescents: 0,
    }
    run_data.tracked_items = {}


def is_valid_filename(filename: str, platform: str = sys.platform) -> bool:
    if not filename or filename in {".", ".."}:
        return False

    invalid_chars = '<>:"/\\|?*' if platform.startswith("win") else "/"

    if any(char in filename for char in invalid_chars):
        return False

    if platform.startswith("win"):
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }
        if filename.upper() in reserved_names:
            return False

    # Length limit (255 for most filesystems)
    if len(filename) > 255:
        return False

    return True


def save_farm(filename: str) -> None:
    with (FARM_PATH / f"{filename}.json").open("w") as file:
        file.write(json.dumps(CounterState.run_data))


def load_farm(filename: str) -> None:
    with (FARM_PATH / f"{filename}.json").open("r") as file:
        loaded_data = cast("RunData", json.load(file))
        data = CounterState.run_data
        CounterState.current_farm = filename
        data["runs"] = loaded_data["runs"]
        for rarity in Rarity:
            data[rarity] = loaded_data["tracked_rarities"][rarity.name]
        data["tracked_items"] = loaded_data["tracked_items"]


def save_session_info() -> None:
    with (BASE_PATH / LAST_SESSION_FILE).open("w") as file:
        file.write(CounterState.current_farm)


def override_reload_map() -> None:
    cs = CounterState
    if cs.is_enabled is True:
        cs.run_data["runs"] += 1
        save_farm(cs.current_farm)
        save_session_info()
    cs.original_reload_map()


def count_item(inventory: WillowInventory, value: int) -> None:
    if inventory.Class.Name not in CLASS_WHITELIST:
        return
    # all whitelisted classes are WillowItems
    item = cast("WillowItem", inventory)

    for rarity, values in RANGES.items():
        if item.RarityLevel in values:
            break
    else:
        return

    data = CounterState.run_data
    data["tracked_rarities"][rarity] += value

    dropName = item.GenerateHumanReadableName().lower()
    for tracked_item in data["tracked_items"]:
        if dropName.find(tracked_item) != -1:
            data[tracked_item] += value


@hook("WillowGame.WillowPickup:InventoryAssociated")
def on_inventory_associated(
    obj: WillowPickup,
    _args: WillowPickup._InventoryAssociated.args,
    _ret: WillowPickup._InventoryAssociated.ret,
    _func: WillowPickup._InventoryAssociated,
) -> None:
    if not CounterState.is_enabled:
        return
    count_item(obj.Inventory, 1)


@hook("WillowGame.WillowPickup:MissionStatusChanged")
def on_mission_status_changed(
    obj: WillowPickup,
    _args: WillowPickup._MissionStatusChanged.args,
    _ret: WillowPickup._MissionStatusChanged.ret,
    _func: WillowPickup._MissionStatusChanged,
) -> None:
    if not CounterState.is_enabled:
        return
    count_item(obj.Inventory, 1)


@hook("WillowGame.WillowPawn:TossInventory")
def on_toss_inventory(
    obj: WillowPawn,
    args: WillowPawn._TossInventory.args,
    _ret: WillowPawn._TossInventory.ret,
    _func: WillowPawn._TossInventory,
) -> None:
    if not CounterState.is_enabled:
        return
    count_item(args.Inv, -1)


def get_pc_cast() -> WillowPlayerController:
    return cast("WillowPlayerController", get_pc())


@hook("WillowGame.TextChatGFxMovie:AddChatMessage")
def onChatCommand(
    obj: TextChatGFxMovie,
    args: TextChatGFxMovie._AddChatMessage.args,
    _ret: TextChatGFxMovie._AddChatMessage.ret,
    _func: TextChatGFxMovie._AddChatMessage,
) -> None:
    msg = args.msg.lower()
    pc = get_pc_cast()
    if args.PRI != pc.PlayerReplicationInfo:
        return True

    state = CounterState
    if not state.is_enabled and msg.startswith(".rc"):
        pc.ConsoleCommand("say Please toggle the main keybind to use the chat commands", 0)
        return True

    if msg.startswith(".rc") is False:
        return True
    splitstring = args.msg.split(" ", 3)
    subcom = splitstring[1].lower()
    subsubcom = splitstring[2].lower() if len(splitstring) > 2 else ""
    option = splitstring[3] if len(splitstring) > 3 else ""

    if subcom == "run" or subcom == "r":
        if subsubcom == "create" or subsubcom == "c":
            save_farm(option)
            reset_current_farm()
            state.current_farm = option
            save_session_info()
        elif subsubcom == "load" or subsubcom == "l":
            load_farm(option)
            save_session_info()
        elif subsubcom == "delete" or subsubcom == "d":
            if os.path.exists(FARM_PATH / (option + ".json")):
                os.remove(FARM_PATH / (option + ".json"))
        elif subsubcom == "rename":
            if os.path.exists(FARM_PATH / (option + ".json")):
                pc.ConsoleCommand("say A farm with that name already exists", 0)
                return
            os.rename(
                FARM_PATH / (state.current_farm + ".json"),
                FARM_PATH / (option + ".json"),
            )
            state.current_farm = option
            save_session_info()

        elif subsubcom == "reset":
            reset_current_farm()

    elif subcom == "setcount" or subcom == "sc":
        if subsubcom == "run" or subsubcom == "r":
            state.run_data["runs"] = int(option)
        elif subsubcom == "item" or subsubcom == "i":
            split = option.rsplit(" ", 1)
            if split[0] in state.run_data["tracked_items"]:
                state.run_data["tracked_items"][split[0]] = int(split[1])
        elif subsubcom == "legendary" or subsubcom == "l":
            state.run_data["tracked_rarities"][Rarity.Legendaries] = int(option)
        elif subsubcom == "pearl" or subsubcom == "p":
            state.run_data["tracked_rarities"][Rarity.Pearlescents] = int(option)
        elif subsubcom == "seraph" or subsubcom == "s":
            state.run_data["tracked_rarities"][Rarity.Seraphs] = int(option)
        elif subsubcom == "effervescent" or subsubcom == "e":
            state.run_data["tracked_rarities"][Rarity.Effervescents] = int(option)

    elif subcom == "list" or subcom == "l":
        farmnames = []
        for file in os.listdir(FARM_PATH):
            farmnames.append(file[:-5])
        if len(farmnames) == 0:
            pc.ConsoleCommand("say No farms saved", 0)
        else:
            pc.ConsoleCommand("say Saved farms: " + ", ".join(farmnames), 0)

    elif subcom == "item" or subcom == "i":
        if subsubcom == "add" or subsubcom == "a":
            state.run_data["tracked_items"][option.lower()] = 0
        elif subsubcom == "remove" or subsubcom == "r":
            del state.run_data["tracked_items"][option]

    return True


def coroutine_draw_meter() -> PostRenderCoroutine:
    while True:
        yield WaitUntil(lambda: get_pc().GetHUDMovie() is not None)
        if not mod.is_enabled:
            return
        state = CounterState
        if not state.is_enabled:
            continue
        canvas = yield
        drawing.reset_state(canvas)
        drawing.draw_background()
        drawing.draw_text_current_line("Farming: " + state.current_farm, drawing.WHITE_COLOR)
        drawing.new_line()
        drawing.draw_text_current_line("Runs: " + str(state.run_data["runs"]), drawing.WHITE_COLOR)
        drawing.draw_hline_top(color=drawing.WHITE_COLOR)

        if state.show_rarity:
            for rarity, value in state.run_data["tracked_rarities"].items():
                drawing.draw_text_current_line(f"{rarity.name}: {value}", drawing.WHITE_COLOR)
                drawing.new_line()

        if len(state.run_data["tracked_items"]) > 0:
            drawing.draw_hline_top(color=drawing.WHITE_COLOR)

        for item, value in state.run_data["tracked_items"].items():
            drawing.draw_text_current_line(f"{item}: {value}", drawing.WHITE_COLOR)
            drawing.new_line()


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


mod = build_mod(
    on_enable=on_enable,
    on_disable=on_disable,
)

# prevent circular import
from loot_counter.option_box.boxes import opt_box
