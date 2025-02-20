from ui_utils.option_box import OptionBoxButton

opt_run = OptionBoxButton(
    name="Run Options",
    tip="Menu for run options (create, load, list, delete, rename, reset)",
)

opt_run_create = OptionBoxButton(
    name="Create Run",
    tip="Create a new run",
)

opt_run_list = OptionBoxButton(
    name="List Runs",
    tip="List all runs",
)

opt_run_load = OptionBoxButton(
    name="Load Run",
    tip="Load an existing run",
)

opt_run_delete = OptionBoxButton(
    name="Delete Run",
    tip="Delete the current run",
)

opt_run_rename = OptionBoxButton(
    name="Rename Run",
    tip="Rename the current run",
)

opt_run_reset = OptionBoxButton(
    name="Reset Run",
    tip="Reset the current run",
)


# Set count options

opt_setcount = OptionBoxButton(
    name="Set Count Options",
    tip="Menu for manually setting numbers (run, item or rarity count)",
)

opt_setcount_run = OptionBoxButton(
    name="Set Count",
    tip="Set the count of the current run",
)

opt_setcount_item = OptionBoxButton(
    name="Set Count",
    tip="Set the count of a specific item",
)

opt_setcount_rarity = OptionBoxButton(
    name="Set Count",
    tip="Set the count of a specific rarity",
)


opt_setcount_legendary = OptionBoxButton(
    name="Set Legendary Count",
    tip="Set the count of legendary items",
)

opt_setcount_pearlescent = OptionBoxButton(
    name="Set Pearlescent Count",
    tip="Set the count of pearlescent items",
)

opt_setcount_seraph = OptionBoxButton(
    name="Set Seraph Count",
    tip="Set the count of seraph items",
)

opt_setcount_effervescent = OptionBoxButton(
    name="Set Effervescent Count",
    tip="Set the count of effervescent items",
)

opt_setcount_unique = OptionBoxButton(
    name="Set Unique Count",
    tip="Set the count of unique items",
)


# Item options

opt_item = OptionBoxButton(
    name="Item Options",
    tip="Menu for item options (add, remove, reset)",
)

opt_item_add = OptionBoxButton(
    name="Add Item",
    tip="Add an item to the current run tracker",
)

opt_item_remove = OptionBoxButton(
    name="Remove Item",
    tip="Remove an item from the current run tracker",
)

opt_item_reset = OptionBoxButton(
    name="Reset Item",
    tip="Reset the count of an item",
)

# Hide rarity option

opt_toggle_rarity = OptionBoxButton(
    name="Toggle Rarity tracker",
    tip="Toggle the tracker for rarity",
)
