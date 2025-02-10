from __future__ import annotations
from types import EllipsisType
from typing import TYPE_CHECKING, cast
from mods_base import options
from unrealsdk import find_object, make_struct

if TYPE_CHECKING:
    from bl2 import Canvas, Object, Font

    # might be too much boilerplate
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


# values that (potentially) changing every frame
class DrawingState:
    canvas: Canvas = None
    screen_width: int = 1920
    screen_height: int = 1080

    # the max width/lines is the width/count of the last frame
    running_max_width: int = 0
    running_num_lines: int = 0
    max_width: int = 0
    max_lines: int = 0

    text_height: int = 0
    y_inc: int = 40

    x_pos: int = 35
    y_pos: int = 400
    bg_padding_x: int = 10
    bg_padding_y: int = 5
    bg_opacity: int = 255


def on_bg_opacity_change(option: options.SliderOption, value: int) -> None:
    DrawingState.bg_opacity = value


def on_x_pos_change(option: options.SliderOption, value: int) -> None:
    DrawingState.x_pos = value


def on_y_pos_change(option: options.SliderOption, value: int) -> None:
    DrawingState.y_pos = value


def on_y_inc_change(option: options.SliderOption, value: int) -> None:
    DrawingState.y_inc = value


opt_bg_opacity = options.SliderOption(
    identifier="Background Opacity",
    value=255,
    min_value=0,
    max_value=255,
    description="The opacity of the background",
    on_change=on_bg_opacity_change,
)

opt_x_pos = options.SliderOption(
    identifier="X Position",
    value=35,
    min_value=0,
    max_value=1720,
    description="The x position of the damage meter. Default value is 35",
    on_change=on_x_pos_change,
)
opt_y_pos = options.SliderOption(
    identifier="Y Position",
    value=400,
    min_value=0,
    max_value=1040,
    description="The y position of the damage meter. Default value is 400",
    on_change=on_y_pos_change,
)

opt_y_inc = options.SliderOption(
    identifier="Y Increment",
    value=40,
    min_value=0,
    max_value=100,
    description="The distance between each line of text. Default value is 40",
    on_change=on_y_inc_change,
)
# helper colors
axton_green_color: Object.Color = make_struct_color("Color", R=0, G=100, B=0, A=255)
maya_yellow_color: Object.Color = make_struct_color("Color", R=200, G=200, B=0, A=255)
salvador_orange_color: Object.Color = make_struct_color("Color", R=200, G=70, B=10, A=255)
zero_cyan_color: Object.Color = make_struct_color("Color", R=0, G=120, B=160, A=255)
gaige_purple_color: Object.Color = make_struct_color("Color", R=100, G=10, B=130, A=255)
krieg_red_color: Object.Color = make_struct_color("Color", R=100, G=10, B=0, A=255)

# allow to change via options in the future
gray_color_bg: Object.Color = make_struct_color("Color", R=125, G=125, B=125, A=255)
black_color: Object.Color = make_struct_color("Color", R=0, G=0, B=0, A=255)
white_color: Object.Color = make_struct_color("Color", R=255, G=255, B=255, A=255)
gold_color: Object.Color = make_struct_color("Color", R=255, G=165, B=0, A=255)


# some stuff that DrawText needs for the out variable so we fill with dummy values
glow: Object.LinearColor = make_struct_linear_color("LinearColor", R=0, G=0, B=0, A=255)
glow_outer: Object.Vector2D = make_struct_vector_2d("Vector2D", X=0, Y=0)
glow_inner: Object.Vector2D = make_struct_vector_2d("Vector2D", X=0, Y=0)

font_willowbody_18pt: Font = cast("Font", find_object("Font", "ui_fonts.font_willowbody_18pt"))

glow_info = make_struct_glow_info(
    "DepthFieldGlowInfo",
    bEnableGlow=True,
    GlowColor=glow,
    GlowOuterRadius=glow_outer,
    GlowInnerRadius=glow_inner,
)
font_render_info = make_struct_font_render_info(
    "FontRenderInfo", bClipText=True, bEnableShadow=True, GlowInfo=glow_info
)


# has to be called every frame for other functions to work (weird setup, but alas)
def reset_state(canvas: Canvas, font: Font = font_willowbody_18pt) -> None:
    ds = DrawingState
    ds.canvas = canvas
    ds.canvas.Font = font

    # magic numbers that are <= the size of the box
    opt_x_pos.max_value = canvas.SizeX - 200
    opt_y_pos.max_value = canvas.SizeY - 50

    # update the max width/lines of the last frame
    ds.max_width = ds.running_max_width
    ds.running_max_width = 0
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
    if width > ds.running_max_width:
        ds.running_max_width = width
    ds.text_height = height

    canvas = ds.canvas
    canvas.SetPos(x, y)
    canvas.SetDrawColorStruct(color)
    canvas.DrawText(text, True, 1, 1, font_render_info)


def draw_text_new_line(text: str, color: Object.Color) -> None:
    ds = DrawingState
    draw_text(
        text=text,
        color=color,
        x=ds.x_pos,
        y=ds.y_pos + ds.running_num_lines * ds.y_inc,
    )
    ds.running_num_lines += 1


def draw_rectangle(x: int, y: int, width: int, height: int, color: Object.Color) -> None:
    canvas = DrawingState.canvas
    canvas.SetPos(x, y)
    canvas.SetDrawColorStruct(color)
    tex = find_object("Texture2D", "EngineResources.WhiteSquareTexture")
    canvas.DrawRect(width, height, tex)


def draw_hline_under_text(color: Object.Color, thickness: int = 1) -> None:
    ds = DrawingState
    draw_rectangle(
        x=ds.x_pos - ds.bg_padding_x,
        y=ds.y_pos + ds.running_num_lines * ds.y_inc - (ds.y_inc - ds.text_height) // 2,
        width=DrawingState.max_width + 2 * ds.bg_padding_x,
        height=thickness,
        color=color,
    )


def draw_background(color: Object.Color) -> None:
    if DrawingState.canvas is None:
        return
    ds = DrawingState
    color.A = ds.bg_opacity
    draw_rectangle(
        x=ds.x_pos - ds.bg_padding_x,
        y=ds.y_pos - ds.bg_padding_y,
        width=DrawingState.max_width + ds.bg_padding_x * 2,
        height=DrawingState.max_lines * ds.y_inc + ds.bg_padding_y * 2,
        color=color,
    )
