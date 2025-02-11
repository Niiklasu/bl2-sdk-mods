from __future__ import annotations
from types import EllipsisType
from typing import TYPE_CHECKING, Any, cast
from mods_base import options
from unrealsdk import find_object, make_struct

if TYPE_CHECKING:
    from bl2 import Canvas, Object, Font

    # might be a bit too much boilerplate
    make_struct_color = Object.Color.make_struct
    make_struct_linear_color = Object.LinearColor.make_struct
    make_struct_vector_2d = Object.Vector2D.make_struct
    make_struct_glow_info = Canvas.DepthFieldGlowInfo.make_struct
    make_struct_font_render_info = Canvas.FontRenderInfo.make_struct
else:
    make_struct_color = make_struct_color = make_struct
    make_struct_linear_color = make_struct_linear_color = make_struct
    make_struct_vector_2d = make_struct_vector_2d = make_struct
    make_struct_glow_info = make_struct_glow_info = make_struct
    make_struct_font_render_info = make_struct_font_render_info = make_struct


# region Constants
AXTON_GREEN_COLOR: Object.Color = make_struct_color("Color", R=0, G=100, B=0, A=255)
MAYA_YELLOW_COLOR: Object.Color = make_struct_color("Color", R=200, G=200, B=0, A=255)
SALVADOR_ORANGE_COLOR: Object.Color = make_struct_color("Color", R=130, G=50, B=0, A=255)
ZERO_CYAN_COLOR: Object.Color = make_struct_color("Color", R=0, G=80, B=110, A=255)
GAIGE_PURPLE_COLOR: Object.Color = make_struct_color("Color", R=100, G=10, B=130, A=255)
KRIEG_RED_COLOR: Object.Color = make_struct_color("Color", R=100, G=10, B=0, A=255)

# allow to change via options in the future
GRAY_COLOR_BG: Object.Color = make_struct_color("Color", R=125, G=125, B=125, A=255)
BLACK_COLOR: Object.Color = make_struct_color("Color", R=0, G=0, B=0, A=255)
WHITE_COLOR: Object.Color = make_struct_color("Color", R=255, G=255, B=255, A=255)
GOLD_COLOR: Object.Color = make_struct_color("Color", R=255, G=165, B=0, A=255)

# some stuff that DrawText needs for the out variable so we fill with dummy values
GLOW: Object.LinearColor = make_struct_linear_color("LinearColor", R=0, G=0, B=0, A=255)
GLOW_OUTER: Object.Vector2D = make_struct_vector_2d("Vector2D", X=0, Y=0)
GLOW_INNER: Object.Vector2D = make_struct_vector_2d("Vector2D", X=0, Y=0)


# got these from yets actionSkillCountdown mod
FONTS: dict[str, Font] = {
    # "willowhead": cast("Font", find_object("Font", "UI_Fonts.Font_Willowhead_8pt")),
    "willowbody": cast("Font", find_object("Font", "ui_fonts.font_willowbody_18pt")),
    "hudmedium": cast("Font", find_object("Font", "UI_Fonts.Font_Hud_Medium")),
    "smallfont": cast("Font", find_object("Font", "EngineFonts.SmallFont")),
    "tinyfont": cast("Font", find_object("Font", "EngineFonts.TinyFont")),
}

GLOW_INFO = make_struct_glow_info(
    "DepthFieldGlowInfo",
    bEnableGlow=True,
    GlowColor=GLOW,
    GlowOuterRadius=GLOW_OUTER,
    GlowInnerRadius=GLOW_INNER,
)
FONT_RENDER_INFO = make_struct_font_render_info(
    "FontRenderInfo", bClipText=True, bEnableShadow=True, GlowInfo=GLOW_INFO
)

# endregion
# region Options

opt_bg_opacity = options.SliderOption(
    identifier="Background Opacity",
    value=150,
    min_value=0,
    max_value=255,
    description="The opacity of the background. Default value is 150",
)

opt_x_pos = options.SliderOption(
    identifier="X Position",
    value=35,
    min_value=0,
    max_value=1720,
    description="The x position of the damage meter. Default value is 35",
)

opt_y_pos = options.SliderOption(
    identifier="Y Position",
    value=350,
    min_value=0,
    max_value=1040,
    description="The y position of the damage meter. Default value is 350",
)

opt_line_height = options.SliderOption(
    identifier="Line Height",
    value=30,
    min_value=0,
    max_value=100,
    description="The height of each line. Default value is 30",
)

opt_width = options.SliderOption(
    identifier="Meter Width",
    value=350,
    min_value=200,
    max_value=800,
    description="The width of the damage meter. Default value is 350",
)

opt_font = options.DropdownOption(
    identifier="Text Font",
    value="hudmedium",
    choices=list(FONTS.keys()),
    description="The font to use for the damage meter",
)

opt_grp_drawing = options.GroupedOption(
    identifier="Drawing",
    children=[opt_x_pos, opt_y_pos, opt_bg_opacity, opt_width, opt_line_height, opt_font],
)


# endregion
# region Current State
class DrawingState:
    canvas: Canvas = None
    screen_width: int = 1920
    screen_height: int = 1080

    running_num_lines: int = 0
    max_lines: int = 0

    text_height: int = 0

    bg_padding_x: int = 10
    bg_padding_y: int = 5

    # hardcoding which rhs columns exists for now (dmg, %total)
    rhs_column_widths: list[int] = [70, 75]


# endregion


# has to be called every frame for other functions to work (weird setup, but alas)
def reset_state(canvas: Canvas) -> None:
    ds = DrawingState
    ds.canvas = canvas
    ds.canvas.Font = FONTS[opt_font.value]

    opt_x_pos.max_value = canvas.SizeX - opt_width.value
    opt_y_pos.max_value = canvas.SizeY - opt_line_height.value * ds.running_num_lines

    # update the max width/lines of the last frame
    ds.max_lines = ds.running_num_lines
    ds.running_num_lines = 0


def get_text_size(text: str) -> tuple[int, int]:
    values = DrawingState.canvas.TextSize(text, 0, 0)
    # SUPER hacky but SOMETIMES the return value is just (float, float) without an ellipsis at the start
    return (values[-2], values[-1])


def draw_text(
    text: str,
    color: Object.Color,
    *,
    x: int = 0,
    y: int = 0,
) -> None:
    ds = DrawingState
    width, height = get_text_size(text)
    ds.text_height = height

    canvas = ds.canvas
    canvas.SetPos(x, y)
    canvas.SetDrawColorStruct(color)
    canvas.DrawText(text, True, 1, 1, FONT_RENDER_INFO)


def draw_text_current_line(text: str, color: Object.Color, *, centered: bool = True) -> None:
    ds = DrawingState
    centered_offset = opt_line_height.value // 2 - ds.text_height // 2 if centered else 0
    draw_text(
        text=text,
        color=color,
        x=opt_x_pos.value,
        y=opt_y_pos.value + ds.running_num_lines * opt_line_height.value + centered_offset,
    )


def draw_text_rhs_column(text: str, color: Object.Color, index_from_right: int, *, centered: bool = True) -> None:
    ds = DrawingState
    centered_offset = opt_line_height.value // 2 - ds.text_height // 2 if centered else 0
    draw_text(
        text=text,
        color=color,
        x=opt_x_pos.value + opt_width.value - sum(ds.rhs_column_widths[-1 - index_from_right :]),
        y=opt_y_pos.value + ds.running_num_lines * opt_line_height.value + centered_offset,
    )


def new_line() -> None:
    DrawingState.running_num_lines += 1


def draw_rectangle(x: int, y: int, width: int, height: int, color: Object.Color) -> None:
    canvas = DrawingState.canvas
    canvas.SetPos(x, y)
    canvas.SetDrawColorStruct(color)
    tex = find_object("Texture2D", "EngineResources.WhiteSquareTexture")
    canvas.DrawRect(width, height, tex)


def draw_bar(percent: float, color: Object.Color) -> None:
    ds = DrawingState
    draw_rectangle(
        x=opt_x_pos.value - ds.bg_padding_x,
        y=opt_y_pos.value + DrawingState.running_num_lines * opt_line_height.value,
        width=int(percent * opt_width.value) + ds.bg_padding_x * 2,
        height=opt_line_height.value,
        color=color,
    )


def draw_hline_top(color: Object.Color, thickness: int = 1) -> None:
    ds = DrawingState
    draw_rectangle(
        x=opt_x_pos.value - ds.bg_padding_x,
        y=opt_y_pos.value + ds.running_num_lines * opt_line_height.value,
        width=opt_width.value + ds.bg_padding_x * 2,
        height=thickness,
        color=color,
    )


def draw_background(color: Object.Color) -> None:
    if DrawingState.canvas is None:
        return
    ds = DrawingState
    color.A = opt_bg_opacity.value
    draw_rectangle(
        x=opt_x_pos.value - ds.bg_padding_x,
        y=opt_y_pos.value - ds.bg_padding_y,
        width=opt_width.value + ds.bg_padding_x * 2,
        height=ds.max_lines * opt_line_height.value + ds.bg_padding_y,
        color=color,
    )
