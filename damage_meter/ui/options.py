from __future__ import annotations
from typing import TYPE_CHECKING, Any, Type, TypeVar, cast
from unrealsdk import find_object
from mods_base import options

if TYPE_CHECKING:
    from bl2 import Font


FONTS: dict[str, Font] = {
    "willowhead": cast("Font", find_object("Font", "UI_Fonts.Font_Willowhead_8pt")),
    "willowbody": cast("Font", find_object("Font", "ui_fonts.font_willowbody_18pt")),
    "hudmedium": cast("Font", find_object("Font", "UI_Fonts.Font_Hud_Medium")),
    "smallfont": cast("Font", find_object("Font", "EngineFonts.SmallFont")),
    "tinyfont": cast("Font", find_object("Font", "EngineFonts.TinyFont")),
}

opt_show_example_ui = options.BoolOption(
    identifier="Show Example UI",
    value=False,
    description="Show an example UI",
)
opt_show_example_ui.default_value = False

opt_bg_opacity = options.SliderOption(
    identifier="Background Opacity",
    value=150,
    min_value=0,
    max_value=255,
    description="The opacity of the background",
)
opt_bg_opacity.default_value = 150

opt_x_pos = options.SliderOption(
    identifier="X Position",
    value=35,
    min_value=0,
    max_value=1920,
    description="The x position of the UI",
)
opt_x_pos.default_value = 35

opt_y_pos = options.SliderOption(
    identifier="Y Position",
    value=35,
    min_value=0,
    max_value=1080,
    description="The y position of the UI",
)
opt_y_pos.default_value = 35

opt_width = options.SliderOption(
    identifier="Width",
    value=200,
    min_value=10,
    max_value=1000,
    description="The width of the UI",
)
opt_width.default_value = 200

opt_line_height = options.SliderOption(
    identifier="Line Height",
    value=35,
    min_value=10,
    max_value=200,
    description="The height of each line",
)
opt_line_height.default_value = 35

opt_rhs_column_width = options.SliderOption(
    identifier="Right-Hand Side Columns Width",
    value=70,
    min_value=10,
    max_value=200,
    description="The width of each column on the right-hand side in the UI",
)
opt_rhs_column_width.default_value = 70

opt_font = options.SpinnerOption(
    identifier="Font",
    value="hudmedium",
    choices=list(FONTS.keys()),
    description="The font to use for the UI",
)
opt_font.default_value = "hudmedium"


T = TypeVar("T", bound=options.BaseOption)


class BaseOptions:
    SHOW_EXAMPLE_UI = "Show Example UI"
    BG_OPACITY = "Background Opacity"
    X_POS = "X Position"
    Y_POS = "Y Position"
    WIDTH = "Width"
    LINE_HEIGHT = "Line Height"
    RHS_COLUMN_WIDTH = "Right-Hand Side Columns Width"
    FONT = "Font"

    _options: dict[str, options.BaseOption] = {
        SHOW_EXAMPLE_UI: opt_show_example_ui,
        BG_OPACITY: opt_bg_opacity,
        X_POS: opt_x_pos,
        Y_POS: opt_y_pos,
        WIDTH: opt_width,
        LINE_HEIGHT: opt_line_height,
        RHS_COLUMN_WIDTH: opt_rhs_column_width,
        FONT: opt_font,
    }

    @classmethod
    def get(cls, option: str) -> options.BaseOption:
        config = cls._options.get(option)
        if config is None:
            raise ValueError(f"Option {option} does not exist")
        return config

    @classmethod
    def _get_cast(cls, option: str, typ: Type[T]) -> T:
        opt = cls.get(option)
        if not isinstance(opt, typ):
            raise ValueError(f"Option {option} is not a {typ.__name__}")
        return cast(T, opt)

    @classmethod
    def get_bool(cls, option: str) -> options.BoolOption:
        return cls._get_cast(option, options.BoolOption)

    @classmethod
    def get_slider(cls, option: str) -> options.SliderOption:
        return cls._get_cast(option, options.SliderOption)

    @classmethod
    def get_spinner(cls, option: str) -> options.SpinnerOption:
        return cls._get_cast(option, options.SpinnerOption)

    @classmethod
    def set_default(cls, option: str, value: Any) -> None:
        if option not in cls._options:
            raise ValueError(f"Option {option} does not exist")
        opt = cls._options[option]
        if not isinstance(opt, options.ValueOption):
            raise ValueError(f"Option {option} is not a value option")
        opt.value = value
        opt.default_value = value

    @classmethod
    def all_options(cls) -> dict[str, options.BaseOption]:
        return cls._options.copy()

    def create_group(shown_options: list[options.BaseOption]) -> options.NestedOption:
        grp_drawing = options.NestedOption(
            identifier="UI Options",
            children=[*shown_options],
            description="Options for drawing the UI",
        )

        def reset_ui_options(_) -> None:
            reset_options(grp_drawing.children)

        def reset_options(opts: list[options.BaseOption]) -> None:
            for option in opts:
                if isinstance(option, options.ValueOption):
                    option.value = option.default_value
                elif isinstance(option, options.GroupedOption) or isinstance(option, options.NestedOption):
                    reset_options(option.children)

        reset_ui = options.ButtonOption(
            identifier="Reset UI",
            description="Reset the UI to the default position. IMPORTANT: Leave the UI Options menu and re-enter to see the changes on the sliders.",
            on_press=reset_ui_options,
        )

        grp_drawing.children.append(reset_ui)
        return grp_drawing
