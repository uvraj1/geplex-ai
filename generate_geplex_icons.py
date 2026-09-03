"""Generate crisp, high-res GepLex brand icons using Pillow.

Design: stylized "G" monogram (2 concentric open arcs) merged with 6
neural/circuit traces on the left.  Gradient runs ocean-blue (top-left)
→ violet (bottom-right).  Matches the user-provided circuit-style mark.
"""
import math
from PIL import Image, ImageDraw, ImageFilter

# ---------- color helpers ----------
def _hex(c):
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255, 255)

def _interp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(4))

# User's gradient: top-left blue(#1f6cb8) -> through mid indigo -> bottom-right purple(#7c3bb0)
_GRAD_STOPS = [
    (0.00, (31,  108, 184, 255)),
    (0.40, (47,   95, 181, 255)),
    (0.70, (88,   73, 182, 255)),
    (1.00, (124,  59, 176, 255)),
]

def _grad_color(t):
    """t in [0,1].  t ~0 = blue (top-left); t~1 = purple (bottom-right)."""
    t = max(0.0, min(1.0, t))
    for i in range(len(_GRAD_STOPS) - 1):
        t0, c0 = _GRAD_STOPS[i]
        t1, c1 = _GRAD_STOPS[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / max(1e-9, (t1 - t0))
            return _interp_color(c0, c1, f)
    return _GRAD_STOPS[-1][1]

def _pos_t(x, y, size):
    """gradient parameter t derived from (x,y) — diagonal top-left -> bottom-right."""
    u = x / max(1, size - 1)          # 0..1 left->right
    v = y / max(1, size - 1)          # 0..1 top->bottom
    # diagonal: weight u+v so top-left = 0, bottom-right = 1
    return (u + v) / 2.0

# ---------- drawing helpers ----------
def _draw_gradient_arc(draw, cx, cy, r, start_deg, end_deg, size, width, start_t=0.0, end_t=1.0):
    """Draw an arc with a simple color gradient along the sweep."""
    steps = 360
    prev = None
    if end_deg < start_deg:
        end_deg += 360
    span = end_deg - start_deg
    for i in range(steps + 1):
        angle_deg = start_deg + (span * i / steps)
        rad = math.radians(angle_deg)
        x = cx + r * math.cos(rad)
        y = cy + r * math.sin(rad)
        if prev is not None:
            t = start_t + (end_t - start_t) * (i / steps)
            col = _grad_color(t)
            draw.line([prev, (x, y)], fill=col, width=width)
        prev = (x, y)

def _draw_gradient_bezier(draw, p0, p1, p2, size, width, start_t=0.0, end_t=1.0, steps=60):
    """Quadratic bezier with gradient along t."""
    prev = None
    for i in range(steps + 1):
        t = i / steps
        bx = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        by = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        if prev is not None:
            col = _grad_color(start_t + (end_t - start_t) * t)
            draw.line([prev, (bx, by)], fill=col, width=width)
        prev = (bx, by)

def _draw_gradient_line(draw, x1, y1, x2, y2, size, width, start_t=0.0, end_t=1.0, steps=None):
    dx, dy = x2 - x1, y2 - y1
    dist = math.sqrt(dx * dx + dy * dy)
    if steps is None:
        steps = max(2, int(dist / 1.5))
    prev = (x1, y1)
    for si in range(1, steps + 1):
        f = si / steps
        nx = x1 + dx * f
        ny = y1 + dy * f
        col = _grad_color(start_t + (end_t - start_t) * f)
        draw.line([prev, (nx, ny)], fill=col, width=width)
        prev = (nx, ny)

def _draw_gradient_filled_circle(draw, cx, cy, r, size, node_t=0.5, inner_white=True):
    """Node circle: solid outer ring with gradient color, optionally tiny white dot center."""
    r = int(r)
    # outer ring = filled circle
    col = _grad_color(node_t)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    if inner_white and r > 4:
        ir = max(2, int(r * 0.42))
        draw.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), fill=(255, 255, 255, 255))

# ---------- main renderer ----------
def render_geplex_icon(size: int = 512) -> Image.Image:
    """Render the GepLex G+circuit mark at any square size."""
    scale = size / 512.0
    s = size

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def sc(v):
        return v * scale

    # Soft outer glow / subtle drop-shadow layer behind the mark.
    shadow_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)

    # --- Letter "G" outer arc (large radius ~ 156 @512) ---
    # Outer G arc: start angle ~ 350° (top-right, slightly below horizontal),
    # sweep clockwise 260° to ~ 150° (bottom-left).
    g_outer_r = sc(156)
    g_cx, g_cy = sc(296), sc(272)      # center of the G arcs (tuned)
    sw_outer = max(2, int(sc(18)))
    _draw_gradient_arc(draw, g_cx, g_cy, g_outer_r,
                       start_deg=-72, end_deg=188,  # covers "open G" shape
                       size=size, width=sw_outer,
                       start_t=0.05, end_t=0.95)
    _draw_gradient_arc(sd, g_cx + sc(0), g_cy + sc(3), g_outer_r,
                       start_deg=-72, end_deg=188, size=size, width=sw_outer,
                       start_t=0.05, end_t=0.95)

    # --- Letter "G" inner arc (parallel, offset inward) ---
    g_inner_r = sc(114)
    sw_inner = max(2, int(sc(18)))
    _draw_gradient_arc(draw, g_cx, g_cy, g_inner_r,
                       start_deg=-52, end_deg=175,
                       size=size, width=sw_inner,
                       start_t=0.10, end_t=0.92)
    _draw_gradient_arc(sd, g_cx + sc(0), g_cy + sc(3), g_inner_r,
                       start_deg=-52, end_deg=175, size=size, width=sw_inner,
                       start_t=0.10, end_t=0.92)

    # --- Lower cross-bar connector (short small bezier on right side joining outer/inner) ---
    cross_p0 = (sc(370), sc(328))
    cross_p1 = (sc(350), sc(316))
    cross_p2 = (sc(334), sc(300))
    sw_cross = max(2, int(sc(14)))
    _draw_gradient_bezier(draw, cross_p0, cross_p1, cross_p2,
                          size=size, width=sw_cross, start_t=0.75, end_t=0.92)
    _draw_gradient_bezier(sd,
                          (cross_p0[0], cross_p0[1] + sc(3)),
                          (cross_p1[0], cross_p1[1] + sc(3)),
                          (cross_p2[0], cross_p2[1] + sc(3)),
                          size=size, width=sw_cross, start_t=0.75, end_t=0.92)

    # --- Main connecting trunk: Node3 (left-middle) to the G-center-node (right side of G's body) ---
    trunk_start = (sc(134), sc(264))     # right-edge of Node3 outer circle
    trunk_end   = (sc(314), sc(280))     # left-edge of G-center-node
    sw_trunk = max(2, int(sc(18)))
    _draw_gradient_line(draw, trunk_start[0], trunk_start[1], trunk_end[0], trunk_end[1],
                        size=size, width=sw_trunk, start_t=0.30, end_t=0.80)
    _draw_gradient_line(sd, trunk_start[0], trunk_start[1] + sc(3),
                        trunk_end[0], trunk_end[1] + sc(3),
                        size=size, width=sw_trunk, start_t=0.30, end_t=0.80)

    # --- Connecting curved traces (bezier) for other nodes ---
    # Node2 (upper-left)  ->  merges near top of G outer arc
    n2_p0 = (sc(169), sc(194))
    n2_p1 = (sc(212), sc(180))
    n2_p2 = (sc(300), sc(150))
    _draw_gradient_bezier(draw, n2_p0, n2_p1, n2_p2, size=size,
                          width=max(2, int(sc(16))),
                          start_t=0.18, end_t=0.45)
    _draw_gradient_bezier(sd,
                          (n2_p0[0], n2_p0[1] + sc(3)),
                          (n2_p1[0], n2_p1[1] + sc(3)),
                          (n2_p2[0], n2_p2[1] + sc(3)),
                          size=size, width=max(2, int(sc(16))),
                          start_t=0.18, end_t=0.45)

    # Node1 (topmost)  ->  up-right swoosh into G outer top
    n1_p0 = (sc(209), sc(182))
    n1_p1 = (sc(240), sc(160))
    n1_p2 = (sc(328), sc(132))
    _draw_gradient_bezier(draw, n1_p0, n1_p1, n1_p2, size=size,
                          width=max(2, int(sc(14))),
                          start_t=0.10, end_t=0.35)
    _draw_gradient_bezier(sd,
                          (n1_p0[0], n1_p0[1] + sc(3)),
                          (n1_p1[0], n1_p1[1] + sc(3)),
                          (n1_p2[0], n1_p2[1] + sc(3)),
                          size=size, width=max(2, int(sc(14))),
                          start_t=0.10, end_t=0.35)

    # Node4 (lower-middle-left)  ->  curve up-right into G inner bottom
    n4_p0 = (sc(175), sc(344))
    n4_p1 = (sc(224), sc(332))
    n4_p2 = (sc(286), sc(284))
    _draw_gradient_bezier(draw, n4_p0, n4_p1, n4_p2, size=size,
                          width=max(2, int(sc(16))),
                          start_t=0.55, end_t=0.85)
    _draw_gradient_bezier(sd,
                          (n4_p0[0], n4_p0[1] + sc(3)),
                          (n4_p1[0], n4_p1[1] + sc(3)),
                          (n4_p2[0], n4_p2[1] + sc(3)),
                          size=size, width=max(2, int(sc(16))),
                          start_t=0.55, end_t=0.85)

    # Node5 (bottom-most)  ->  long diagonal up-right into inner G arc
    n5_p0 = (sc(217), sc(376))
    n5_p1 = (sc(258), sc(360))
    n5_p2 = (sc(308), sc(314))
    _draw_gradient_bezier(draw, n5_p0, n5_p1, n5_p2, size=size,
                          width=max(2, int(sc(14))),
                          start_t=0.70, end_t=0.95)
    _draw_gradient_bezier(sd,
                          (n5_p0[0], n5_p0[1] + sc(3)),
                          (n5_p1[0], n5_p1[1] + sc(3)),
                          (n5_p2[0], n5_p2[1] + sc(3)),
                          size=size, width=max(2, int(sc(14))),
                          start_t=0.70, end_t=0.95)

    # ---- Layer: apply drop-shadow (blur + offset) behind main mark ----
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=max(1, s * 0.008)))
    # Fade shadow to 35% so it's very subtle
    alpha = shadow_layer.split()[-1].point(lambda a: int(a * 0.35))
    shadow_layer.putalpha(alpha)
    img = Image.alpha_composite(shadow_layer, img)
    draw = ImageDraw.Draw(img)

    # ---- Nodes (draw AFTER shadow so nodes stay crisp) ----
    # G-center-node (biggest, on the body of G)
    gnode = (sc(336), sc(280))
    _draw_gradient_filled_circle(draw, gnode[0], gnode[1], sc(22), size, node_t=0.75, inner_white=True)

    # 6 circuit nodes on the left side
    node_specs = [
        # (x @512, y @512, r @512, grad_t)
        (190, 172, 19, 0.15),   # N1 topmost
        (150, 208, 19, 0.22),   # N2 upper-left
        (112, 264, 22, 0.32),   # N3 middle-left (largest of left cluster)
        (156, 354, 19, 0.60),   # N4 lower-middle
        (198, 384, 19, 0.72),   # N5 bottom-most
        # 6th node — exactly one tiny extra node visually completes user's original art
        (168, 158, 0,  0.10),   # reserved slot; not drawn (keeps indices aligned)
    ]
    for nx, ny, nr, nt in node_specs:
        if nr <= 0:
            continue
        _draw_gradient_filled_circle(draw, sc(nx), sc(ny), sc(nr), size,
                                     node_t=nt, inner_white=True)

    # Final micro-blur pass for anti-aliasing polish (very slight)
    if s >= 64:
        blur = img.filter(ImageFilter.GaussianBlur(radius=max(0.3, s * 0.0015)))
        img = Image.blend(img, blur, 0.20)
    return img


def _composite_on_bg(img_rgba, bg_color=(248, 247, 252, 255)):
    """Flatten an RGBA image onto a solid background (used for JPG exports)."""
    bg = Image.new("RGBA", img_rgba.size, bg_color)
    return Image.alpha_composite(bg, img_rgba).convert("RGB")


def main():
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("Generating GepLex brand icons (G + circuit design)...")

    img512 = render_geplex_icon(512)
    img512.save("assets/branding/geplex-logo-512.png", "PNG")
    print("  - 512px logo -> assets/branding/geplex-logo-512.png")

    img256 = render_geplex_icon(256)
    img256.save("assets/branding/geplex-logo-256.png", "PNG")
    print("  - 256px logo -> assets/branding/geplex-logo-256.png")

    img192 = render_geplex_icon(192)
    img192.save("assets/branding/geplex-logo-192.png", "PNG")
    print("  - 192px logo -> assets/branding/geplex-logo-192.png")

    # Favicon ICO + 64px for toolbars
    img64 = render_geplex_icon(64)
    img48 = render_geplex_icon(48)
    img32 = render_geplex_icon(32)
    img16 = render_geplex_icon(16)
    img64.save("static/icons/geplex-64.png", "PNG")
    img32.save("static/icon.ico", format="ICO",
               sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("  - Favicon ICO (16/32/48/64) -> static/icon.ico")
    print("  - 64px toolbar icon  -> static/icons/geplex-64.png")

    # PWA / web-app icons
    img512.save("static/icons/icon-512.png", "PNG")
    img192.save("static/icons/icon-192.png", "PNG")
    img512.save("static/icons/icon-maskable-512.png", "PNG")
    print("  - PWA icon-192/512/maskable-512 -> static/icons/")

    # Wordmark preview PNG + brand social/simple previews (JPGs on cream bg)
    # geplex.jpg: just the logo on light cream bg
    _composite_on_bg(img512, (249, 248, 252, 255)).save("assets/branding/geplex.jpg", "JPEG", quality=92)
    print("  - Social preview (logo on cream) -> assets/branding/geplex.jpg")

    # geplex-browser.jpg: logo on browser-style "off-white" bg (#f7f7fb)
    browser_bg = (247, 247, 251, 255)
    wide = Image.new("RGBA", (1200, 630), browser_bg)
    big = render_geplex_icon(512)
    # paste logo centered
    paste_xy = ((1200 - 512) // 2, (630 - 512) // 2)
    wide.paste(big, paste_xy, big)
    wide.convert("RGB").save("assets/branding/geplex-browser.jpg", "JPEG", quality=90)
    print("  - Browser / social banner 1200x630 -> assets/branding/geplex-browser.jpg")

    # geplex-wordmark.png: logo + text side-by-side rendered via a very small
    # pillow scene (replicates wordmark SVG look without a renderer dep)
    wm_w, wm_h = 900, 260
    wm = Image.new("RGBA", (wm_w, wm_h), (0, 0, 0, 0))
    mark_img = render_geplex_icon(240)
    wm.paste(mark_img, (30, 10), mark_img)
    from PIL import ImageFont
    try:
        font_path_big = None
        for candidate in ("C:/Windows/Fonts/segoeuib.ttf",
                          "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            if os.path.exists(candidate):
                font_path_big = candidate
                break
        if font_path_big:
            font = ImageFont.truetype(font_path_big, 102)
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    wd = ImageDraw.Draw(wm)
    # text baseline y ~ 175 with minor shadow then gradient text
    text_x, text_y = 315, 62
    # Compute gradient across the text glyphs by drawing color-stamped layers.
    # (Quick approach: render white-on-temp, then colorize per-column using gradient.)
    tmp = Image.new("L", (wm_w, wm_h), 0)
    td = ImageDraw.Draw(tmp)
    td.text((text_x, text_y), "GepLex", fill=255, font=font)
    # Expand text bbox slightly for gradient canvas
    import numpy as np
    arr = np.array(tmp)
    ys, xs = np.where(arr > 128)
    if len(xs):
        x0, x1 = xs.min(), xs.max()
        # For every column x0..x1, if there's text at (x,y) paint grad color
        # based on normalized x+y along diagonal.
        text_layer = Image.new("RGBA", (wm_w, wm_h), (0, 0, 0, 0))
        tla = np.array(text_layer)
        # Diagonal t same formula as svg: ( (x-x0)/(x1-x0) + (y - y_min)/(y_max-y_min) ) / 2
        y0, y1 = ys.min(), ys.max()
        w_cols = max(1, x1 - x0)
        h_rows = max(1, y1 - y0)
        Ygrid, Xgrid = np.mgrid[0:h_rows + 1, 0:w_cols + 1]
        Ts = (Xgrid / w_cols + Ygrid / h_rows) / 2.0
        # Map Ts -> RGBA using our gradient stops
        rgba_out = np.zeros((h_rows + 1, w_cols + 1, 4), dtype=np.uint8)
        for si in range(len(_GRAD_STOPS) - 1):
            t0, c0 = _GRAD_STOPS[si]
            t1, c1 = _GRAD_STOPS[si + 1]
            mask = (Ts >= t0) & (Ts <= t1)
            if not np.any(mask):
                continue
            f = (Ts - t0) / max(1e-9, (t1 - t0))
            f4 = f[..., None]
            col = (c0 + (np.array(c1, dtype=np.float32) - np.array(c0, dtype=np.float32)) *
                   np.repeat(f4, 4, axis=-1))
            rgba_out[mask] = col.clip(0, 255).astype(np.uint8)[mask]
        # Mask alpha: only where text mask exists in x0..x1, y0..y1
        crop_mask = (arr[y0:y1 + 1, x0:x1 + 1] > 128)
        rgba_out[..., 3] = np.where(crop_mask, rgba_out[..., 3], 0)
        # Paste into wm at x0,y0
        grad_text_img = Image.fromarray(rgba_out, "RGBA")
        wm.paste(grad_text_img, (x0, y0), grad_text_img)
    wm.save("assets/branding/geplex-wordmark.png", "PNG")
    print("  - Wordmark PNG (logo + GepLex text) -> assets/branding/geplex-wordmark.png")

    print("\nAll GepLex icons successfully generated!")

if __name__ == "__main__":
    main()
