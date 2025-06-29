import argparse
import numpy as np
from PIL import Image
import cairosvg
from skimage.measure import find_contours
import cadquery as cq


def svg_to_png(svg_path: str, png_path: str, dpi: int = 600):
    cairosvg.svg2png(url=svg_path, write_to=png_path, dpi=dpi)


def quantize_to_grayscale(image: Image.Image, color_count: int) -> Image.Image:
    if image.mode in ('RGBA', 'LA'):
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image.convert("RGBA"))
    gray_image = image.convert('L')
    np_gray = np.array(gray_image)
    np_alpha = np.array(image.convert('RGBA'))[..., 3]
    levels = np.linspace(0, 255, color_count, endpoint=True).astype(np.uint8)
    idxs = np.abs(np_gray[..., None] - levels).argmin(axis=-1)
    quantized = levels[idxs]
    quantized[np_alpha == 0] = 0  # transparent pixels to 0 level
    return Image.fromarray(quantized, mode='L')


def get_contours_for_level(np_gray, level):
    # Find contours of the specific grayscale level mask
    mask = (np_gray == level).astype(np.uint8)
    contours = find_contours(mask, 0.5)
    return contours


def contour_to_cq_wire(contour, scale=1.0):
    # Convert a numpy Nx2 contour to a CadQuery Wire (closed loop)
    points = [(x * scale, y * scale) for y, x in contour]  # note skimage: row=y, col=x
    if len(points) < 3:
        return None
    # Create a CadQuery wire from points
    wire = cq.Workplane("XY").polyline(points).close()
    return wire


def main(svg_file, output_file, color_count=5,
         base_height=1.0, step_height=0.5, dpi=600, scale=1.0):
    png_file = svg_file + ".temp.png"
    svg_to_png(svg_file, png_file, dpi=dpi)
    img = Image.open(png_file)
    gray_img = quantize_to_grayscale(img, color_count)
    np_gray = np.array(gray_img)

    levels = np.linspace(255, 0, color_count, endpoint=True).astype(np.uint8)

    assembly = cq.Assembly()

    for i, level in enumerate(levels):
        contours = get_contours_for_level(np_gray, level)
        height = base_height + i * step_height

        for j, contour in enumerate(contours):
            if contour.shape[0] < 3:
                continue
            wire = contour_to_cq_wire(contour, scale)
            if wire is None:
                continue
            try:
                solid = wire.extrude(height)
                # Add to assembly with a unique name
                assembly.add(solid, name=f"level_{i}_contour_{j}")
            except Exception as e:
                print(f"Warning: skipping contour due to error: {e}")

    if len(assembly.objects) == 0:
        raise RuntimeError("No solids generated from image")

    # Export assembly as STEP
    assembly.save(output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert SVG to extruded grayscale STEP using CadQuery")
    parser.add_argument("svg_file", help="Input SVG file path")
    parser.add_argument("output_file", help="Output STEP filename")
    parser.add_argument("--color_count", type=int, default=5,
                        help="Number of grayscale levels")
    parser.add_argument("--base_height", type=float, default=1.0,
                        help="Base extrusion height for lightest color")
    parser.add_argument("--step_height", type=float, default=0.5,
                        help="Additional extrusion height per darker level")
    parser.add_argument("--dpi", type=int, default=600,
                        help="Rasterization DPI for SVG to PNG")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Scaling factor for coordinates")
    args = parser.parse_args()

    main(args.svg_file, args.output_file,
         args.color_count, args.base_height, args.step_height,
         args.dpi, args.scale)
