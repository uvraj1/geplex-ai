"""Generate crisp, high-res Geplex Cloud AI brand icons using Pillow (fast)."""
import math
from PIL import Image, ImageDraw, ImageFilter

def _interp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(4))

def _cloud_outline_points(cx, cy, scale):
    base_pts = [
        (cx - 186 * scale, cy + 108 * scale),
        (cx - 230 * scale, cy + 108 * scale),
        (cx - 250 * scale, cy + 80 * scale),
        (cx - 250 * scale, cy + 20 * scale),
        (cx - 230 * scale, cy - 20 * scale),
        (cx - 200 * scale, cy - 40 * scale),
        (cx - 200 * scale, cy - 80 * scale),
        (cx - 170 * scale, cy - 120 * scale),
        (cx - 130 * scale, cy - 160 * scale),
        (cx - 80 * scale, cy - 190 * scale),
        (cx - 20 * scale, cy - 205 * scale),
        (cx + 40 * scale, cy - 200 * scale),
        (cx + 90 * scale, cy - 200 * scale),
        (cx + 140 * scale, cy - 180 * scale),
        (cx + 180 * scale, cy - 150 * scale),
        (cx + 210 * scale, cy - 130 * scale),
        (cx + 250 * scale, cy - 130 * scale),
        (cx + 275 * scale, cy - 100 * scale),
        (cx + 285 * scale, cy - 60 * scale),
        (cx + 280 * scale, cy - 20 * scale),
        (cx + 295 * scale, cy + 10 * scale),
        (cx + 300 * scale, cy + 50 * scale),
        (cx + 290 * scale, cy + 85 * scale),
        (cx + 270 * scale, cy + 115 * scale),
        (cx + 240 * scale, cy + 140 * scale),
        (cx + 200 * scale, cy + 150 * scale),
        (cx + 170 * scale, cy + 145 * scale),
        (cx + 165 * scale, cy + 170 * scale),
        (cx + 140 * scale, cy + 190 * scale),
        (cx + 100 * scale, cy + 200 * scale),
        (cx + 60 * scale, cy + 195 * scale),
        (cx + 30 * scale, cy + 180 * scale),
        (cx + 10 * scale, cy + 200 * scale),
        (cx - 30 * scale, cy + 200 * scale),
        (cx - 60 * scale, cy + 185 * scale),
        (cx - 90 * scale, cy + 165 * scale),
        (cx - 120 * scale, cy + 180 * scale),
        (cx - 150 * scale, cy + 182 * scale),
        (cx - 180 * scale, cy + 160 * scale),
        (cx - 186 * scale, cy + 108 * scale),
    ]
    return base_pts

def render_geplex_icon(size: int = 512) -> Image.Image:
    scale = size / 512.0
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = s / 2.0, s / 2.0
    cloud_pts = _cloud_outline_points(cx, cy, scale)

    stroke_w = max(4, int(s * 0.013))
    for i in range(len(cloud_pts) - 1):
        p1 = cloud_pts[i]
        p2 = cloud_pts[i + 1]
        frac = i / max(1, len(cloud_pts) - 2)
        if frac < 0.35:
            col = _interp_color((124, 58, 237, 255), (99, 102, 241, 255), frac / 0.35)
        elif frac < 0.70:
            col = _interp_color((99, 102, 241, 255), (14, 165, 233, 255), (frac - 0.35) / 0.35)
        else:
            col = _interp_color((14, 165, 233, 255), (16, 185, 129, 255), (frac - 0.70) / 0.30)
        draw.line([p1, p2], fill=col, width=stroke_w)

    fill_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    fill_draw = ImageDraw.Draw(fill_img)
    fill_draw.polygon([(int(p[0]), int(p[1])) for p in cloud_pts], fill=(30, 27, 75, 205))
    for y in range(s):
        t = y / s
        fill_col = _interp_color((30, 27, 75, 205), (12, 74, 110, 200), t)
        for x in range(s):
            px = fill_img.getpixel((x, y))
            if px[3] > 0:
                fill_img.putpixel((x, y), fill_col)
    img = Image.alpha_composite(img, fill_img)
    draw = ImageDraw.Draw(img)

    g_cx = cx + (6 * scale)
    g_cy = cy + (-6 * scale)
    g_rx = s * 0.26
    g_ry = s * 0.19
    g_w = max(4, int(s * 0.011))
    prev_pt = None
    for ai, angle in enumerate(range(250, 530, 3)):
        rad = math.radians(angle)
        x = g_cx + g_rx * math.cos(rad)
        y = g_cy + g_ry * math.sin(rad)
        pt = (x, y)
        if prev_pt is not None:
            frac = ai / max(1, ((530 - 250) // 3) - 1)
            if frac < 0.5:
                col = _interp_color((167, 139, 250, 255), (34, 211, 238, 255), frac * 2)
            else:
                col = _interp_color((34, 211, 238, 255), (52, 211, 153, 255), (frac - 0.5) * 2)
            draw.line([prev_pt, pt], fill=col, width=g_w)
        prev_pt = pt

    g_xs = g_cx + g_rx * 0.92
    g_xe = g_cx + s * 0.38
    for xi in range(int(g_xs), int(g_xe) + 1):
        frac = (xi - g_xs) / max(1, (g_xe - g_xs))
        col = _interp_color((34, 211, 238, 255), (52, 211, 153, 255), frac)
        for wy in range(-g_w // 2, g_w // 2 + 1):
            yy = int(g_cy + wy)
            if 0 <= xi < s and 0 <= yy < s:
                draw.point((xi, yy), fill=col)

    core_r = int(s * 0.034)
    for r_i in range(core_r, 0, -1):
        t = r_i / core_r
        if t < 0.6:
            col = _interp_color((224, 242, 254, 255), (56, 189, 248, 255), t / 0.6)
        else:
            col = _interp_color((56, 189, 248, 255), (99, 102, 241, 255), (t - 0.6) / 0.4)
        draw.ellipse((g_cx - r_i, g_cy - r_i, g_cx + r_i, g_cy + r_i), outline=col, width=2)

    inner_r = int(s * 0.020)
    draw.ellipse((g_cx - inner_r, g_cy - inner_r, g_cx + inner_r, g_cy + inner_r), fill=(255, 255, 255, 255))
    dot_r = max(2, int(s * 0.010))
    draw.ellipse((g_cx - dot_r, g_cy - dot_r, g_cx + dot_r, g_cy + dot_r), fill=(99, 102, 241, 255))

    node_r = max(2, int(s * 0.012))
    node_specs = [
        (cx - s * 0.40, cy - s * 0.10, (167, 139, 250, 255)),
        (cx + s * 0.43, cy - s * 0.14, (34, 211, 238, 255)),
        (cx + s * 0.38, cy + s * 0.14, (52, 211, 153, 255)),
    ]
    for nx, ny, ncol in node_specs:
        draw.ellipse((nx - node_r, ny - node_r, nx + node_r, ny + node_r), fill=ncol)

    glow_layer = img.filter(ImageFilter.GaussianBlur(radius=max(1, s * 0.02)))
    glow_layer = Image.blend(Image.new("RGBA", (s, s), (0, 0, 0, 0)), glow_layer, alpha=0.55)
    result = Image.alpha_composite(glow_layer, img)
    return result

def main():
    print("Generating Geplex Cloud AI icons...")
    img512 = render_geplex_icon(512)
    img512.save("static/icons/icon-512.png", "PNG")
    img512.save("static/icons/icon-maskable-512.png", "PNG")
    print("  - 512px icons saved")

    img192 = render_geplex_icon(192)
    img192.save("static/icons/icon-192.png", "PNG")
    print("  - 192px icon saved")

    img32 = render_geplex_icon(32)
    img16 = render_geplex_icon(16)
    img48 = render_geplex_icon(48)
    img32.save("static/icon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print("  - Favicon ICO saved")
    print("All Geplex Cloud AI icons successfully generated!")

if __name__ == "__main__":
    main()
