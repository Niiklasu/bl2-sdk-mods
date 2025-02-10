from __future__ import annotations
from typing import TYPE_CHECKING
from unrealsdk import find_object

if TYPE_CHECKING:
    from bl2 import Canvas, Object

    make_struct_color = Object.Color.make_struct
    make_struct_linear_color = Object.LinearColor.make_struct
    make_struct_vector_2d = Object.Vector2D.make_struct
    make_struct_glow_info = Canvas.DepthFieldGlowInfo.make_struct
    make_struct_font_render_info = Canvas.FontRenderInfo.make_struct

black_color: Object.Color = make_struct_color("Color", R=0, G=0, B=0, A=255)
white_color: Object.Color = make_struct_color("Color", R=255, G=255, B=255, A=255)
gold_color: Object.Color = make_struct_color("Color", R=255, G=165, B=0, A=255)

black_glow: Object.LinearColor = make_struct_linear_color("LinearColor", R=0, G=0, B=0, A=255)
white_glow: Object.LinearColor = make_struct_linear_color("LinearColor", R=255, G=255, B=255, A=255)
gold_glow: Object.LinearColor = make_struct_linear_color("LinearColor", R=255, G=165, B=0, A=255)
glow_outer: Object.Vector2D = make_struct_vector_2d("Vector2D", X=50, Y=10)
glow_inner: Object.Vector2D = make_struct_vector_2d("Vector2D", X=210, Y=90)

glow_info = make_struct_glow_info(
    "DepthFieldGlowInfo",
    bEnableGlow=True,
    GlowColor=gold_glow,
    GlowOuterRadius=glow_outer,
    GlowInnerRadius=glow_inner,
)
font_render_info = make_struct_font_render_info(
    "FontRenderInfo", bClipText=True, bEnableShadow=True, GlowInfo=glow_info
)


class DrawingState:
    x: int = 600
    y: int = 35
    y_inc: int = 40
    canvas: Canvas = None
    num_displayed_lines: int = 0
    initialized: bool = False


def init(canvas: Canvas) -> None:
    DrawingState.canvas = canvas
    DrawingState.canvas.Font = find_object("Font", "ui_fonts.font_willowbody_18pt")


def draw_text(
    text: str,
    color: Object.Color,
    x: int = DrawingState.x,
    y: int = DrawingState.y + DrawingState.num_displayed_lines * DrawingState.y_inc,
    count_line: bool = True,
) -> None:
    ds = DrawingState
    ds.canvas.SetPos(x, y)
    ds.canvas.SetDrawColorStruct(color)
    ds.canvas.DrawText(text, True, 1, 1, font_render_info)
    if count_line is True:
        ds.num_displayed_lines += 1


def draw_line(length: int, color: Object.Color) -> None:
    ds = DrawingState
    draw_text(
        text="-" * length,
        color=color,
        y=ds.y + ds.num_displayed_lines * ds.y_inc - ds.y_inc / 2,
        doCount=False,
    )
