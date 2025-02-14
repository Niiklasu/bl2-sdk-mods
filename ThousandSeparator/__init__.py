from __future__ import annotations
import re

from legacy_compat import unrealsdk
from mods_base.mod_factory import build_mod
from unrealsdk.hooks import prevent_hooking_direct_calls

try:
    assert __import__("unrealsdk").__version_info__ >= (1, 7, 0), "Please update the SDK"
except (AssertionError, ImportError) as ex:
    import webbrowser

    webbrowser.open("https://bl-sdk.github.io/willow2-mod-db/requirements?mod=DamageMeter")
from typing import TYPE_CHECKING, cast
from mods_base import hook, options
from unrealsdk.unreal import BoundFunction
from unrealsdk.hooks import Type

if TYPE_CHECKING:
    from bl2 import ItemCardGFxObject


format_string = "{number:_}"


def on_change_separator(_, value: str) -> None:
    global format_string
    if value == "Comma":
        format_string = "{number:,}"
    elif value == "None":
        format_string = "{number}"
    else:
        format_string = "{number:_}"


opt_separator = options.SpinnerOption(
    identifier="Separator",
    value="Space",
    choices=["Space", "Underscore", "Comma", "Period", "None"],
    wrap_enabled=True,
    on_change=on_change_separator,
)


@hook("WillowGame.ItemCardGFxObject:SetTopStat", Type.POST)
def set_top_stat(
    obj: ItemCardGFxObject,
    args: ItemCardGFxObject._SetTopStat.args,
    _ret: ItemCardGFxObject._SetTopStat.ret,
    func: ItemCardGFxObject._SetTopStat,
) -> None:
    valueText = args.ValueText
    match = re.search(f"\d+", valueText)
    if match:
        number = match.group()
        formatted_num = format_string.format(number=int(number))
        if opt_separator.value == "Period":
            formatted_num = formatted_num.replace("_", ".")
        elif opt_separator.value == "Space":
            formatted_num = formatted_num.replace("_", " ")
        new_val = valueText[: match.start()] + formatted_num + valueText[match.end() :]
    else:
        new_val = valueText
    with prevent_hooking_direct_calls():
        func.__call__(args.StatIndex, args.LabelText, new_val, args.CompareArrow, args.AuxText, args.IconName)


build_mod()
