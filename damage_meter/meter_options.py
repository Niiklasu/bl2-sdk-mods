from collections import OrderedDict
from enum import Enum
from mods_base import options
from .ui.options import BaseOptions


class ColumnType(str, Enum):
    PARTY_PERCENT = "Party%"
    DAMAGE = "Dmg"
    DPS = "DPS"


class ColorBy(str, Enum):
    PLAYER = "Player"
    CLASS = "Class"


opt_color_by = options.SpinnerOption(
    identifier="Colored By",
    value=ColorBy.CLASS,
    choices=[cb.value for cb in ColorBy],
    description="CLASS means multiple players with the same class get the same color, PLAYER means each player gets a unique color",
    wrap_enabled=True,
)
opt_color_by.default_value = ColorBy.CLASS

opt_show_bars = options.BoolOption(
    identifier="Show Bars",
    value=True,
    description="Whether to show bars for the damage or just the text",
)
opt_show_bars.default_value = True

opt_show_class = options.BoolOption(
    identifier="Show Class",
    value=True,
    description="Whether to show the class of the player or not",
)
opt_show_class.default_value = True

opt_show_dps = options.BoolOption(
    identifier="Show DPS",
    value=True,
    description="Whether to show the DPS column or not",
)
opt_show_dps.default_value = True

opt_show_total_dmg = options.BoolOption(
    identifier="Show Total Damage",
    value=True,
    description="Whether to show the total damage column or not",
)
opt_show_total_dmg.default_value = True

opt_show_party_percent = options.BoolOption(
    identifier="Show Party Percentage",
    value=True,
    description="Whether to show the party percentage column or not",
)
opt_show_party_percent.default_value = True


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


class MeterOptions(BaseOptions):
    COLORED_BY = "Colored By"
    SHOW_BARS = "Show Bars"
    SHOW_CLASS = "Show Class"
    COLUMN_OPTS = "Columns"

    _extended_options = {
        COLORED_BY: opt_color_by,
        SHOW_BARS: opt_show_bars,
        SHOW_CLASS: opt_show_class,
        COLUMN_OPTS: opt_grp_columns,
    }
    _options = {**BaseOptions._options, **_extended_options}


MeterOptions.set_default(option=MeterOptions.Y_POS, value=350)
MeterOptions.set_default(option=MeterOptions.WIDTH, value=425)
