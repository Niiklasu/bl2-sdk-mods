from __future__ import annotations
import sys
from typing import TYPE_CHECKING, Callable
from ui_utils.option_box import OptionBox, OptionBoxButton
from ui_utils.hud_message import show_hud_message
from ui_utils.chat import show_chat_message
from loot_counter.option_box import buttons
from loot_counter import (
    DEFAULT_FARM,
    FARM_PATH,
    CounterState,
    Rarity,
    load_farm,
    save_farm,
    save_session_info,
)
from legacy_compat import legacy_compat

if TYPE_CHECKING:
    with legacy_compat():
        import UserFeedback
else:
    with legacy_compat():
        from Mods import UserFeedback


class TextInput(UserFeedback.TextInputBox):
    def __init__(
        self,
        title: str,
        on_submit: Callable[[str], None],
    ):
        super().__init__(title)
        self.OnSubmit = on_submit
        self.Show()


def is_invalid_filename(filename: str, platform: str = sys.platform) -> bool:
    if not filename or filename in {".", ".."}:
        return True

    invalid_chars = '<>:"/\\|?*' if platform.startswith("win") else "/"

    if any(char in filename for char in invalid_chars):
        return True

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
            return True

    # Length limit (255 for most filesystems)
    if len(filename) > 255:
        return True

    return False


def reset_current_farm() -> None:
    CounterState.run_data = {
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


# Main menu


def manage_option_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_run:
        run_box.show()
    elif opt_button == buttons.opt_item:
        item_box.show()
    elif opt_button == buttons.opt_setcount:
        setcount_box.show()
    elif opt_button == buttons.opt_toggle_rarity:
        CounterState.run_data["show_rarity"] = not CounterState.run_data["show_rarity"]


# Run Menu


def _create_farm(name: str) -> None:
    if is_invalid_filename(name):
        show_hud_message("Loot Counter", "Invalid farm name")
        return
    if (FARM_PATH / (name + ".json")).exists():
        show_hud_message("Loot Counter", "A farm with that name already exists")
        return
    save_farm(CounterState.current_farm)
    reset_current_farm()
    CounterState.current_farm = name
    save_session_info()


def _manage_load_run(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    save_farm(CounterState.current_farm)
    load_farm(opt_button.name)
    save_session_info()


def _delete_farm(name: str) -> None:
    if name == DEFAULT_FARM:
        show_hud_message("Loot Counter", "Cannot delete the default farm")
        return
    if not (FARM_PATH / (name + ".json")).exists():
        show_chat_message("Farm not found")
        return

    (FARM_PATH / (name + ".json")).unlink()
    if CounterState.current_farm == name:
        load_farm(DEFAULT_FARM)
        save_session_info()


def _rename_farm(name: str) -> None:
    if is_invalid_filename(name):
        show_hud_message("Loot Counter", "Invalid farm name")
        return
    if (FARM_PATH / (name + ".json")).exists():
        show_hud_message("Loot Counter", "A farm with that name already exists")
        return
    (FARM_PATH / (CounterState.current_farm + ".json")).rename(FARM_PATH / (name + ".json"))
    CounterState.current_farm = name
    save_session_info()


def _manage_run_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_run_create:
        TextInput(
            title="Create New Run",
            on_submit=_create_farm,
        )
    elif opt_button == buttons.opt_run_load:
        farms = []
        for file in FARM_PATH.iterdir():
            farms.append(OptionBoxButton(name=file.stem))
        farms_box = OptionBox(
            title="Available Farms",
            message="Select a farm to load",
            buttons=[*farms],
            on_select=_manage_load_run,
        )
        farms_box.show()
    elif opt_button == buttons.opt_run_delete:
        TextInput(
            title="Name of run to delete",
            on_submit=_delete_farm,
        )
    elif opt_button == buttons.opt_run_rename:
        TextInput(
            title="New name for current run",
            on_submit=_rename_farm,
        )
    elif opt_button == buttons.opt_run_reset:
        reset_current_farm()
        save_farm(CounterState.current_farm)


# Set count menu


def _set_run_count(count: str) -> None:
    CounterState.run_data["runs"] = int(count)


def _set_item(item: str) -> None:
    if item not in CounterState.run_data["tracked_items"]:
        show_chat_message("Item not found")
        return

    def _set_item_count(count: str) -> None:
        CounterState.run_data["tracked_items"][item] = int(count)

    TextInput(
        title="Set Item Count",
        on_submit=_set_item_count,
    )


def _set_rarity_count(rarity: Rarity, count: int) -> None:
    CounterState.run_data["tracked_rarities"][rarity] = count


def _manage_setcount_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_setcount_run:
        TextInput(
            title="Set Run Count",
            on_submit=_set_run_count,
        )
    elif opt_button == buttons.opt_setcount_item:
        TextInput(
            title="Choose item to set",
            on_submit=_set_item,
        )

    elif opt_button == buttons.opt_setcount_rarity:
        rarity_box.show()


def _manage_rarity_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_setcount_unique:
        TextInput(
            title="Set Unique Count",
            on_submit=lambda count: _set_rarity_count(Rarity.Uniques, int(count)),
        )
    elif opt_button == buttons.opt_setcount_legendary:
        TextInput(
            title="Set Legendary Count",
            on_submit=lambda count: _set_rarity_count(Rarity.Legendaries, int(count)),
        )
    elif opt_button == buttons.opt_setcount_pearlescent:
        TextInput(
            title="Set Pearlescent Count",
            on_submit=lambda count: _set_rarity_count(Rarity.Pearlescents, int(count)),
        )
    elif opt_button == buttons.opt_setcount_seraph:
        TextInput(
            title="Set Seraph Count",
            on_submit=lambda count: _set_rarity_count(Rarity.Seraphs, int(count)),
        )
    elif opt_button == buttons.opt_setcount_effervescent:
        TextInput(
            title="Set Effervescent Count",
            on_submit=lambda count: _set_rarity_count(Rarity.Effervescents, int(count)),
        )


# Item menu


def _add_item(item: str) -> None:
    if item in CounterState.run_data["tracked_items"]:
        show_chat_message("Item already exists")
        return
    CounterState.run_data["tracked_items"].update({item: 0})


def _remove_item(item: str) -> None:
    if item not in CounterState.run_data["tracked_items"]:
        show_chat_message("Item not found")
        return
    CounterState.run_data["tracked_items"].pop(item, None)


def _reset_item(item: str) -> None:
    if item not in CounterState.run_data["tracked_items"]:
        show_chat_message("Item not found")
        return
    CounterState.run_data["tracked_items"].update({item: 0})


def _manage_item_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_item_add:
        TextInput(
            title="Add Item",
            on_submit=_add_item,
        )
    elif opt_button == buttons.opt_item_remove:
        TextInput(
            title="Remove Item",
            on_submit=_remove_item,
        )
    elif opt_button == buttons.opt_item_reset:
        TextInput(
            title="Reset Item Count",
            on_submit=_reset_item,
        )


run_box = OptionBox(
    title="Run Options",
    message="Select an option to open the corresponding action",
    buttons=[
        buttons.opt_run_create,
        buttons.opt_run_load,
        buttons.opt_run_delete,
        buttons.opt_run_rename,
        buttons.opt_run_reset,
    ],
    on_select=_manage_run_input,
)

setcount_box = OptionBox(
    title="Set Count Options",
    message="Select an option to set a specific count",
    buttons=[
        buttons.opt_setcount_run,
        buttons.opt_setcount_item,
        buttons.opt_setcount_rarity,
    ],
    on_select=_manage_setcount_input,
)

rarity_box = OptionBox(
    title="Set Rarity Count",
    message="Select an option to set a specific rarity count",
    buttons=[
        buttons.opt_setcount_unique,
        buttons.opt_setcount_legendary,
        buttons.opt_setcount_pearlescent,
        buttons.opt_setcount_seraph,
        buttons.opt_setcount_effervescent,
    ],
    on_select=_manage_rarity_input,
)

item_box = OptionBox(
    title="Item Options",
    message="Select an option to open the corresponding action",
    buttons=[
        buttons.opt_item_add,
        buttons.opt_item_remove,
        buttons.opt_item_reset,
    ],
    on_select=_manage_item_input,
)

opt_box = OptionBox(
    title="Loot Counter",
    message="Select an option to open the corresponding menu",
    buttons=[
        buttons.opt_run,
        buttons.opt_item,
        buttons.opt_setcount,
        buttons.opt_toggle_rarity,
    ],
    on_select=manage_option_input,
)
