import sys
import argparse
import numpy as np
from PIL import Image
import cairosvg
from stl import mesh


def svg_to_png(svg_path: str, png_path: str, dpi: int = 300):
    cairosvg.svg2png(url=svg_path, write_to=png_path, dpi=dpi)


def quantize_to_grayscale(image: Image.Image, color_count: int) -> Image.Image:
    if image.mode in ('RGBA', 'LA'):
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image.convert("RGBA"))
    gray_image = image.convert('L')  # Convert to grayscale
    np_gray = np.array(gray_image)
    np_alpha = np.array(image.convert('RGBA'))[..., 3]  # Extract alpha channel
    levels = np.linspace(0, 255, color_count, endpoint=True).astype(np.uint8)
    idxs = np.abs(np_gray[..., None] - levels).argmin(axis=-1)
    quantized = levels[idxs]
    quantized[np_alpha == 0] = 0  # Set fully transparent pixels to level 0 (excluded)
    return Image.fromarray(quantized, mode='L')


def generate_height_map(gray_image: Image.Image,
                        base_height: float,
                        step_height: float,
                        color_count: int) -> np.ndarray:
    np_gray = np.array(gray_image)
    levels = np.linspace(255, 0, color_count, endpoint=True).astype(np.uint8)
    height_map = np.zeros_like(np_gray, dtype=np.float32)
    for i, level in enumerate(levels):
        height = base_height + i * step_height
        height_map[np_gray == level] = height
    return height_map


def height_map_to_mesh(height_map: np.ndarray, alpha_mask: np.ndarray,
                       scale: float = 1.0) -> mesh.Mesh:
    rows, cols = height_map.shape
    vertices = []
    vertex_indices = -np.ones((rows, cols), dtype=int)  # -1 means no vertex (transparent)
    faces = []

    def vertex_index(r, c):
        return vertex_indices[r, c]

    # Create vertices only for non-transparent pixels
    idx = 0
    for r in range(rows):
        for c in range(cols):
            if alpha_mask[r, c]:  # Only add vertex if not transparent
                z = height_map[r, c]
                vertices.append([c * scale, r * scale, z])
                vertex_indices[r, c] = idx
                idx += 1

    vertices = np.array(vertices)

    # Create faces only if all corners are valid (non-transparent)
    for r in range(rows - 1):
        for c in range(cols - 1):
            if (vertex_index(r, c) == -1 or
                vertex_index(r, c + 1) == -1 or
                vertex_index(r + 1, c) == -1 or
                vertex_index(r + 1, c + 1) == -1):
                continue  # Skip faces with transparent corners

            v0 = vertex_index(r, c)
            v1 = vertex_index(r, c + 1)
            v2 = vertex_index(r + 1, c)
            v3 = vertex_index(r + 1, c + 1)
            faces.append([v0, v1, v2])
            faces.append([v1, v3, v2])

    faces = np.array(faces)
    stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
    for i, face in enumerate(faces):
        for j in range(3):
            stl_mesh.vectors[i][j] = vertices[face[j], :]

    return stl_mesh


def main(svg_file, color_count, base_height, step_height, output_file):
    png_file = svg_file + ".temp.png"
    svg_to_png(svg_file, png_file)

    img = Image.open(png_file)
    gray_img = quantize_to_grayscale(img, color_count)
    height_map = generate_height_map(gray_img, base_height, step_height, color_count)

    # Extract alpha mask from original image: True = opaque/semi-opaque, False = fully transparent
    alpha_mask = np.array(img.convert('RGBA'))[..., 3] > 0

    stl_mesh = height_map_to_mesh(height_map, alpha_mask)
    stl_mesh.save(output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("svg_file", help="Path to input SVG file")
    parser.add_argument("output_file", help="Output STL filename")
    parser.add_argument("--color_count", type=int, default=5,
                        help="Number of grayscale levels")
    parser.add_argument("--base_height", type=float, default=1.0,
                        help="Base height for the lightest color")
    parser.add_argument("--step_height", type=float, default=0.5,
                        help="Additional height per darker step")
    args = parser.parse_args()

    main(args.svg_file, args.color_count, args.base_height,
         args.step_height, args.output_file)
