from __future__ import annotations
from collections import OrderedDict
from enum import Enum
from mods_base import options
from typing import TYPE_CHECKING, cast
from unrealsdk import find_object

if TYPE_CHECKING:
    from bl2 import Font


class ColumnType(str, Enum):
    PARTY_PERCENT = "Party%"
    DAMAGE = "Dmg"
    DPS = "DPS"


class ColorBy(str, Enum):
    PLAYER = "Player"
    CLASS = "Class"


class Options(str, Enum):
    SHOW_EXAMPLE_UI = "Show Example UI"
    COLORED_BY = "Colored By"
    SHOW_BARS = "Show Bars"
    SHOW_CLASS = "Show Class"
    BACKGROUND_OPACITY = "Background Opacity"
    X_POSITION = "X Position"
    Y_POSITION = "Y Position"
    METER_WIDTH = "Meter Width"
    LINE_HEIGHT = "Line Height"
    TEXT_FONT = "Text Font"
    COLUMN_WIDTH = "Column Width"
    SHOW_DPS = "Show DPS"
    SHOW_TOTAL_DAMAGE = "Show Total Damage"
    SHOW_PARTY_PERCENTAGE = "Show Party Percentage"


# got these from yets actionSkillCountdown mod
FONTS: dict[str, Font] = {
    # buggy
    # "willowhead": cast("Font", find_object("Font", "UI_Fonts.Font_Willowhead_8pt")),
    "willowbody": cast("Font", find_object("Font", "ui_fonts.font_willowbody_18pt")),
    "hudmedium": cast("Font", find_object("Font", "UI_Fonts.Font_Hud_Medium")),
    "smallfont": cast("Font", find_object("Font", "EngineFonts.SmallFont")),
    "tinyfont": cast("Font", find_object("Font", "EngineFonts.TinyFont")),
}

DEFAULT_OPT_VALUES = {
    Options.SHOW_EXAMPLE_UI: False,
    Options.COLORED_BY: ColorBy.CLASS,
    Options.SHOW_BARS: True,
    Options.SHOW_CLASS: True,
    Options.BACKGROUND_OPACITY: 150,
    Options.X_POSITION: 35,
    Options.Y_POSITION: 350,
    Options.METER_WIDTH: 425,
    Options.LINE_HEIGHT: 35,
    Options.TEXT_FONT: "hudmedium",
    Options.COLUMN_WIDTH: 70,
    Options.SHOW_DPS: True,
    Options.SHOW_TOTAL_DAMAGE: True,
    Options.SHOW_PARTY_PERCENTAGE: True,
}
opt_show_example_ui = options.BoolOption(
    identifier=Options.SHOW_EXAMPLE_UI.value,
    value=DEFAULT_OPT_VALUES[Options.SHOW_EXAMPLE_UI],
    description="Show an example meter. More than 4 players to show you the different options. IMPORTANT: Toggle off when you're done.",
)

opt_color_by = options.SpinnerOption(
    identifier=Options.COLORED_BY.value,
    value=DEFAULT_OPT_VALUES[Options.COLORED_BY],
    choices=[cb.value for cb in ColorBy],
    description="CLASS means multiple players with the same class get the same color, PLAYER means each player gets a unique color",
    wrap_enabled=True,
)

opt_show_bars = options.BoolOption(
    identifier=Options.SHOW_BARS.value,
    value=DEFAULT_OPT_VALUES[Options.SHOW_BARS],
    description="Whether to show bars for the damage or just the text",
)

opt_show_class = options.BoolOption(
    identifier=Options.SHOW_CLASS.value,
    value=DEFAULT_OPT_VALUES[Options.SHOW_CLASS],
    description="Whether to show the class of the player or not",
)

opt_bg_opacity = options.SliderOption(
    identifier=Options.BACKGROUND_OPACITY.value,
    value=DEFAULT_OPT_VALUES[Options.BACKGROUND_OPACITY],
    min_value=0,
    max_value=255,
    description=f"The opacity of the background. Default value is {DEFAULT_OPT_VALUES[Options.BACKGROUND_OPACITY]}",
)

opt_x_pos = options.SliderOption(
    identifier=Options.X_POSITION.value,
    value=DEFAULT_OPT_VALUES[Options.X_POSITION],
    min_value=0,
    max_value=1720,
    description=f"The x position of the damage meter. Default value is {DEFAULT_OPT_VALUES[Options.X_POSITION]}",
)

opt_y_pos = options.SliderOption(
    identifier=Options.Y_POSITION.value,
    value=DEFAULT_OPT_VALUES[Options.Y_POSITION],
    min_value=0,
    max_value=1040,
    description=f"The y position of the damage meter. Default value is {DEFAULT_OPT_VALUES[Options.Y_POSITION]}",
)

opt_width = options.SliderOption(
    identifier=Options.METER_WIDTH.value,
    value=DEFAULT_OPT_VALUES[Options.METER_WIDTH],
    min_value=200,
    max_value=1000,
    description=f"The width of the damage meter. Default value is {DEFAULT_OPT_VALUES[Options.METER_WIDTH]}",
)

opt_line_height = options.SliderOption(
    identifier=Options.LINE_HEIGHT.value,
    value=DEFAULT_OPT_VALUES[Options.LINE_HEIGHT],
    min_value=10,
    max_value=200,
    description=f"The height of each line. Default value is {DEFAULT_OPT_VALUES[Options.LINE_HEIGHT]}",
)

opt_font = options.DropdownOption(
    identifier=Options.TEXT_FONT.value,
    value=DEFAULT_OPT_VALUES[Options.TEXT_FONT],
    choices=list(FONTS.keys()),
    description=f"The font to use for the damage meter. Default value is {DEFAULT_OPT_VALUES[Options.TEXT_FONT]}",
)

opt_column_width = options.SliderOption(
    identifier=Options.COLUMN_WIDTH.value,
    value=DEFAULT_OPT_VALUES[Options.COLUMN_WIDTH],
    min_value=10,
    max_value=200,
    description=f"The width of each column in the damage meter. Default value is {DEFAULT_OPT_VALUES[Options.COLUMN_WIDTH]}",
)

opt_show_dps = options.BoolOption(
    identifier=Options.SHOW_DPS.value,
    value=DEFAULT_OPT_VALUES[Options.SHOW_DPS],
    description="Whether to show the DPS column or not",
)

opt_show_total_dmg = options.BoolOption(
    identifier=Options.SHOW_TOTAL_DAMAGE.value,
    value=DEFAULT_OPT_VALUES[Options.SHOW_TOTAL_DAMAGE],
    description="Whether to show the total damage column or not",
)

opt_show_party_percent = options.BoolOption(
    identifier=Options.SHOW_PARTY_PERCENTAGE.value,
    value=DEFAULT_OPT_VALUES[Options.SHOW_PARTY_PERCENTAGE],
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
        opt_x_pos,
        opt_y_pos,
        opt_bg_opacity,
        opt_width,
        opt_line_height,
        opt_column_width,
        # opt_font,
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
