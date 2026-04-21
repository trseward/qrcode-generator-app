from PIL import Image, ImageDraw

# ICO bundles multiple resolutions; Windows selects the best match at runtime.
SIZES = [16, 32, 48, 64, 128, 256]

def draw_icon(size):
    # Start with a transparent square canvas.
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Scale spacing and corner radius so the same design works at all sizes.
    pad = max(1, size // 16)
    radius = max(3, size // 6)

    # Draw the dark rounded background tile and a neon border.
    d.rounded_rectangle([pad, pad, size-pad-1, size-pad-1],
                         radius=radius, fill=(25, 10, 45, 255))
    border = max(1, size // 32)
    d.rounded_rectangle([pad, pad, size-pad-1, size-pad-1],
                         radius=radius, outline=(255, 20, 180, 220), width=border)

    # Reserve an inner square where the QR-style motif is drawn.
    inner = max(3, size // 5)
    qx0, qy0 = pad + inner, pad + inner
    qx1, qy1 = size - pad - inner - 1, size - pad - inner - 1

    # Tiny icon fallback: fill the center when there is no room for cells.
    if qx1 <= qx0 or qy1 <= qy0:
        d.rectangle([pad+1, pad+1, size-pad-2, size-pad-2], fill=(255,20,180,255))
        return img

    # White backdrop keeps the QR modules legible against the dark tile.
    d.rectangle([qx0, qy0, qx1, qy1], fill=(255, 240, 255, 255))
    qr_size = qx1 - qx0
    cells = 7
    cell = qr_size / cells

    # Hand-crafted 7x7 "QR-like" pattern (visual branding, not encoded data).
    pattern = [
        [1,1,1,0,1,1,1],
        [1,0,1,0,1,0,1],
        [1,1,1,0,1,1,1],
        [0,0,0,0,0,1,0],
        [1,1,1,0,0,1,1],
        [1,0,0,0,1,0,1],
        [1,1,1,0,1,1,1],
    ]
    region_colors = {
        (0,0): (255, 20, 180, 255),
        (0,4): (160, 32, 240, 255),
        (4,0): (0, 230, 255, 255),
    }
    data_color = (60, 0, 100, 255)

    # Paint modules; use accent colors for three finder-like regions.
    for row in range(cells):
        for col in range(cells):
            if pattern[row][col]:
                cx0 = qx0 + col * cell
                cy0 = qy0 + row * cell
                cx1 = max(cx0, cx0 + cell - 1)
                cy1 = max(cy0, cy0 + cell - 1)
                if row < 3 and col < 3:
                    color = region_colors[(0,0)]
                elif row < 3 and col >= 4:
                    color = region_colors[(0,4)]
                elif row >= 4 and col < 3:
                    color = region_colors[(4,0)]
                else:
                    color = data_color
                d.rectangle([cx0, cy0, cx1, cy1], fill=color)

    # Add tiny corner sparkles on larger frames for extra contrast/detail.
    if size >= 64:
        spark_size = max(2, size // 32)
        for (sx, sy) in [(pad+2, pad+2), (size-pad-4, pad+2),
                          (pad+2, size-pad-4), (size-pad-4, size-pad-4)]:
            d.ellipse([sx, sy, sx+spark_size, sy+spark_size], fill=(255, 220, 0, 200))
    return img

# Build all size variants up front so they can be packed into one .ico file.
# Convert each frame to RGBA explicitly for reliable Windows icon rendering.
frames = []
for s in SIZES:
    frame = draw_icon(s).convert("RGBA")
    frames.append(frame)

# Save a multi-resolution ICO; explicit sizes help Windows choose crisp frames.
frames[0].save(
    "icon_neon.ico",
    format="ICO",
    sizes=[(s, s) for s in SIZES],
    append_images=frames[1:],
)

# Also export a PNG companion (useful for Tkinter's wm_iconphoto).
frames[-1].save("icon_neon.png", format="PNG")

print("icon_neon.ico and icon_neon.png written successfully")