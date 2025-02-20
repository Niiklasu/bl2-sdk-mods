from ui_utils.option_box import OptionBox, OptionBoxButton
from loot_counter.option_box import buttons
from loot_counter import (
    CounterState,
)


def manage_option_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_run:
        run_box.show()
    elif opt_button == buttons.opt_item:
        item_box.show()
    elif opt_button == buttons.opt_setcount:
        setcount_box.show()
    elif opt_button == buttons.opt_toggle_rarity:
        CounterState.show_rarity = not CounterState.show_rarity


def manage_run_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_run_create:
        # TODO
        pass
    elif opt_button == buttons.opt_run_list:
        # TODO
        pass
    elif opt_button == buttons.opt_run_load:
        # TODO
        pass
    elif opt_button == buttons.opt_run_delete:
        # TODO
        pass
    elif opt_button == buttons.opt_run_rename:
        # TODO
        pass
    elif opt_button == buttons.opt_run_reset:
        # TODO
        pass


def manage_setcount_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_setcount_run:
        # TODO
        pass
    elif opt_button == buttons.opt_setcount_item:
        # TODO
        pass
    elif opt_button == buttons.opt_setcount_rarity:
        rarity_box.show()


def manage_rarity_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_setcount_legendary:
        # TODO
        pass
    elif opt_button == buttons.opt_setcount_pearlescent:
        # TODO
        pass
    elif opt_button == buttons.opt_setcount_seraph:
        # TODO
        pass
    elif opt_button == buttons.opt_setcount_effervescent:
        # TODO
        pass
    elif opt_button == buttons.opt_setcount_unique:
        # TODO
        pass


def manage_item_input(caller: OptionBox, opt_button: OptionBoxButton) -> None:
    if opt_button == buttons.opt_item_add:
        # TODO
        pass
    elif opt_button == buttons.opt_item_remove:
        # TODO
        pass
    elif opt_button == buttons.opt_item_reset:
        # TODO
        pass


run_box = OptionBox(
    title="Run Options",
    message="Select an option to open the corresponding action",
    buttons=[
        buttons.opt_run_create,
        buttons.opt_run_list,
        buttons.opt_run_load,
        buttons.opt_run_delete,
        buttons.opt_run_rename,
        buttons.opt_run_reset,
    ],
    on_select=manage_run_input,
)

setcount_box = OptionBox(
    title="Set Count Options",
    message="Select an option to set a specific count",
    buttons=[
        buttons.opt_setcount_run,
        buttons.opt_setcount_item,
        buttons.opt_setcount_rarity,
    ],
    on_select=manage_setcount_input,
)

rarity_box = OptionBox(
    title="Set Rarity Count",
    message="Select an option to set a specific rarity count",
    buttons=[
        buttons.opt_setcount_legendary,
        buttons.opt_setcount_pearlescent,
        buttons.opt_setcount_seraph,
        buttons.opt_setcount_effervescent,
        buttons.opt_setcount_unique,
    ],
    on_select=manage_rarity_input,
)

item_box = OptionBox(
    title="Item Options",
    message="Select an option to open the corresponding action",
    buttons=[
        buttons.opt_item_add,
        buttons.opt_item_remove,
        buttons.opt_item_reset,
    ],
    on_select=manage_item_input,
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
