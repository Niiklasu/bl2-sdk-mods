from __future__ import annotations
from typing import TYPE_CHECKING
from unrealsdk import find_object, make_struct
from .options import FONTS, BaseOptions

if TYPE_CHECKING:
    from bl2 import Canvas, Object

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


AXTON_GREEN_COLOR: Object.Color = make_struct_color("Color", R=0, G=100, B=0, A=255)
MAYA_YELLOW_COLOR: Object.Color = make_struct_color("Color", R=200, G=200, B=0, A=255)
SALVADOR_ORANGE_COLOR: Object.Color = make_struct_color("Color", R=130, G=50, B=0, A=255)
ZERO_CYAN_COLOR: Object.Color = make_struct_color("Color", R=0, G=80, B=110, A=255)
GAIGE_PURPLE_COLOR: Object.Color = make_struct_color("Color", R=100, G=10, B=130, A=255)
KRIEG_RED_COLOR: Object.Color = make_struct_color("Color", R=100, G=10, B=0, A=255)

GRAY_COLOR_BG: Object.Color = make_struct_color("Color", R=125, G=125, B=125, A=255)
BLACK_COLOR: Object.Color = make_struct_color("Color", R=0, G=0, B=0, A=255)
WHITE_COLOR: Object.Color = make_struct_color("Color", R=255, G=255, B=255, A=255)
GOLD_COLOR: Object.Color = make_struct_color("Color", R=255, G=165, B=0, A=255)
RED_COLOR: Object.Color = make_struct_color("Color", R=255, G=0, B=0, A=255)

# some stuff that DrawText neeself for the out variable so we fill with dummy values
GLOW: Object.LinearColor = make_struct_linear_color("LinearColor", R=0, G=0, B=0, A=255)
GLOW_OUTER: Object.Vector2D = make_struct_vector_2d("Vector2D", X=0, Y=0)
GLOW_INNER: Object.Vector2D = make_struct_vector_2d("Vector2D", X=0, Y=0)

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


# region Drawing Class
class Drawing:
    def __init__(
        self,
        *,
        options: type[BaseOptions] = BaseOptions,
        hidden_options: list[str] = [],
    ) -> None:
        self.options = options
        self.opt_group = options.create_group(
            shown_options=[opt for option, opt in options.all_options().items() if option not in hidden_options]
        )
        self.canvas = None
        self.screen_width: int = 1920
        self.screen_height: int = 1080

        self.running_num_lines: int = 0
        self.max_lines: int = 0

        self.text_height: int = 0

        self.bg_padding_x: int = 10
        self.bg_padding_y: int = 5

    # has to be called every frame for other functions to work (weird setup, but alas)
    def reset_state(self, canvas: Canvas) -> None:
        opts = self.options
        self.canvas = canvas
        self.canvas.Font = FONTS[opts.get_spinner(opts.FONT).value]

        opts.get_slider(opts.X_POS).max_value = canvas.SizeX - opts.get_slider(opts.WIDTH).value
        opts.get_slider(opts.Y_POS).max_value = (
            canvas.SizeY - opts.get_slider(opts.LINE_HEIGHT).value * self.running_num_lines
        )

        # update the max width/lines of the last frame
        self.max_lines = self.running_num_lines
        self.running_num_lines = 0

    def get_text_size(self, text: str) -> tuple[int, int]:
        values = self.canvas.TextSize(text, 0, 0)
        # SUPER hacky but SOMETIMES the return value is just (float, float) without an ellipsis at the start
        return (values[-2], values[-1])

    def draw_text(
        self,
        text: str,
        color: Object.Color,
        *,
        x: int = 0,
        y: int = 0,
    ) -> None:
        """Draws text at the given position with the given color. The position is the top left corner of the text"""
        width, height = self.get_text_size(text)
        self.text_height = height

        self.canvas.SetPos(x, y)
        self.canvas.SetDrawColorStruct(color)
        self.canvas.DrawText(text, True, 1, 1, FONT_RENDER_INFO)

    def draw_text_current_line(self, text: str, color: Object.Color, *, centered: bool = True) -> None:
        """
        Draws the text in the current line, calculated by the line count and line height.

        To get increase the line count and get into a new line call new_line().
        """
        opts = self.options
        centered_offset = opts.get_slider(opts.LINE_HEIGHT).value // 2 - self.text_height // 2 if centered else 0
        self.draw_text(
            text=text,
            color=color,
            x=opts.get_slider(opts.X_POS).value,
            y=opts.get_slider(opts.Y_POS).value
            + self.running_num_lines * opts.get_slider(opts.LINE_HEIGHT).value
            + centered_offset,
        )

    def draw_text_rhs_column(
        self, text: str, position_from_right: int, color: Object.Color, *, centered: bool = True
    ) -> None:
        """
        Draws text in the current line, but from the right side of the meter.

        A value of 0 for position_from_right means the rightmost column.
        Cendered specifies whether to vertically center the text.
        """
        opts = self.options
        centered_offset = opts.get_slider(opts.LINE_HEIGHT).value // 2 - self.text_height // 2 if centered else 0
        self.draw_text(
            text=text,
            color=color,
            x=opts.get_slider(opts.X_POS).value
            + opts.get_slider(opts.WIDTH).value
            - opts.get_slider(opts.RHS_COLUMN_WIDTH).value * (position_from_right + 1),
            y=opts.get_slider(opts.Y_POS).value
            + self.running_num_lines * opts.get_slider(opts.LINE_HEIGHT).value
            + centered_offset,
        )

    def new_line(
        self,
    ) -> None:
        """Moves the current line down by the line height"""
        self.running_num_lines += 1

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: Object.Color) -> None:
        """Draws a rectangle at the given position with the given size and color"""
        self.canvas.SetPos(x, y)
        self.canvas.SetDrawColorStruct(color)
        tex = find_object("Texture2D", "EngineResources.WhiteSquareTexture")
        self.canvas.DrawRect(width, height, tex)

    def draw_bar(self, percent: float, color: Object.Color) -> None:
        """Draws a bar at the current line, that is exactly one line tall and fills horizantally to the given percentage with the given color"""
        opts = self.options
        self.draw_rectangle(
            x=opts.get_slider(opts.X_POS).value - self.bg_padding_x,
            y=opts.get_slider(opts.Y_POS).value + self.running_num_lines * opts.get_slider(opts.LINE_HEIGHT).value,
            width=int(percent * (opts.get_slider(opts.WIDTH).value + self.bg_padding_x * 2)),
            height=opts.get_slider(opts.LINE_HEIGHT).value,
            color=color,
        )

    def draw_hline_top(self, color: Object.Color, thickness: int = 1) -> None:
        """Draws a small horizontal line at the top of the current line with the given color"""

        opts = self.options
        self.draw_rectangle(
            x=opts.get_slider(opts.X_POS).value - self.bg_padding_x,
            y=opts.get_slider(opts.Y_POS).value + self.running_num_lines * opts.get_slider(opts.LINE_HEIGHT).value,
            width=opts.get_slider(opts.WIDTH).value + self.bg_padding_x * 2,
            height=thickness,
            color=color,
        )

    def draw_background(self, color: Object.Color = GRAY_COLOR_BG) -> None:
        """Draws the background of the meter with the given color"""
        if self.canvas is None:
            return
        opts = self.options
        color.A = opts.get_slider(opts.BG_OPACITY).value
        self.draw_rectangle(
            x=opts.get_slider(opts.X_POS).value - self.bg_padding_x,
            y=opts.get_slider(opts.Y_POS).value - self.bg_padding_y,
            width=opts.get_slider(opts.WIDTH).value + self.bg_padding_x * 2,
            height=self.max_lines * opts.get_slider(opts.LINE_HEIGHT).value + self.bg_padding_y,
            color=color,
        )
