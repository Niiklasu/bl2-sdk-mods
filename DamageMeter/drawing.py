from __future__ import annotations
from types import EllipsisType
from typing import TYPE_CHECKING, cast
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

# allow to change via options in the future
start_x: int = 600
start_y: int = 35
bg_padding: int = 10
width: int = 200
start_height: int = 0
y_inc: int = 40


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


# values changing every frame
class DrawingState:
    canvas: Canvas = None
    num_displayed_lines: int = 0
    width: int = 0


# has to be called every frame for other functions to work (weird setup, but alas)
def reset_state(canvas: Canvas, font: Font = font_willowbody_18pt) -> None:
    DrawingState.canvas = canvas
    DrawingState.canvas.Font = font
    DrawingState.num_displayed_lines = 0
    DrawingState.width = 0


def get_text_width(text: str) -> int:
    values = DrawingState.canvas.TextSize(text, 0, 0)
    # super hacky but SOMETIMES the return value is just an (float, float) tuple without an ellipsis at the start
    for value in values:
        if isinstance(value, EllipsisType):
            continue
        return value


def draw_text_new_line(text: str, color: Object.Color) -> None:
    ds = DrawingState
    draw_text(
        text=text,
        color=color,
        y=start_y + ds.num_displayed_lines * y_inc,
    )
    ds.num_displayed_lines += 1


def draw_text(
    text: str,
    color: Object.Color,
    *,
    x: int = start_x,
    y: int = start_y,
) -> None:
    width = get_text_width(text)
    if width > DrawingState.width:
        DrawingState.width = width

    canvas = DrawingState.canvas
    canvas.SetPos(x, y)
    canvas.SetDrawColorStruct(color)
    canvas.DrawText(text, True, 1, 1, font_render_info)


def draw_line(length: int, color: Object.Color) -> None:
    ds = DrawingState
    draw_text(
        text="-" * length,
        color=color,
        y=start_y + ds.num_displayed_lines * y_inc - y_inc / 2,
    )


def draw_rectangle(x: int, y: int, width: int, height: int, color: Object.Color) -> None:
    canvas = DrawingState.canvas
    canvas.SetPos(x, y)
    canvas.SetDrawColorStruct(color)
    tex = find_object("Texture2D", "EngineResources.WhiteSquareTexture")
    canvas.DrawRect(width, height, tex)


def draw_background(color: Object.Color) -> None:
    if DrawingState.canvas is None:
        return
    draw_rectangle(
        start_x - bg_padding,
        start_y - bg_padding,
        DrawingState.width + bg_padding * 2,
        start_height + DrawingState.num_displayed_lines * y_inc + bg_padding * 2,
        color,
    )
