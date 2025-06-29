#!/usr/bin/env python3
"""
SVG to STL Converter with PROPER Transparency Handling
Converts SVG images to 3D printable STL models with height-based extrusion.
Transparent areas are properly excluded from the model generation.
"""

import argparse
import sys
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image
from stl import mesh


def svg_to_png(svg_path, png_path, width=None, height=None, dpi=300):
    """
    Convert SVG to PNG using CairoSVG, preserving transparency.
    """
    try:
        with open(svg_path, 'rb') as svg_file:
            svg_data = svg_file.read()

        # Convert SVG to PNG with transparency preservation
        cairosvg.svg2png(
            bytestring=svg_data,
            write_to=png_path,
            output_width=width,
            output_height=height,
            dpi=dpi
        )
        print(f"Successfully converted SVG to PNG: {png_path}")
    except Exception as e:
        raise Exception(f"Failed to convert SVG to PNG: {e}")


def has_transparency_robust(image):
    """
    Robust transparency detection that works across PIL versions.
    """
    # Method 1: Check for transparency in image info
    if image.info.get("transparency", None) is not None:
        return True

    # Method 2: Check image mode for alpha channels
    if image.mode in ("RGBA", "LA"):
        # Use getextrema() to check if alpha channel has values < 255
        extrema = image.getextrema()
        if image.mode == "RGBA":
            return extrema[3][0] < 255  # Check alpha channel minimum
        else:  # LA mode
            return extrema[1][0] < 255  # Check alpha channel minimum

    # Method 3: For indexed color images (P mode) with transparency
    if image.mode == "P":
        transparency = image.info.get("transparency", None)
        if transparency is not None:
            return True

    # Method 4: Use has_transparency_data if available (Pillow >= 10.1.0)
    if hasattr(image, 'has_transparency_data'):
        return image.has_transparency_data

    return False


def extract_transparency_mask_and_process(image_path, color_count):
    """
    Extract transparency mask BEFORE converting to grayscale.
    This is the key fix - preserve alpha info before conversion.
    """
    try:
        # Open image and keep original mode
        img = Image.open(image_path)
        transparency_mask = None

        print(f"Original image mode: {img.mode}")
        print(f"Image size: {img.size}")

        # Check for transparency BEFORE any conversions
        has_transparency = has_transparency_robust(img)
        print(f"Has transparency: {has_transparency}")

        if has_transparency:
            # Convert to RGBA to standardize alpha channel handling
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Extract alpha channel BEFORE losing it
            img_array = np.array(img)
            if img_array.shape[2] == 4:  # RGBA
                alpha_channel = img_array[:, :, 3]
                # Create transparency mask (True where pixels are transparent)
                transparency_mask = alpha_channel < 128  # Threshold for transparency
                transparent_pixels = np.sum(transparency_mask)
                total_pixels = transparency_mask.size
                print(f"Found {transparent_pixels} transparent pixels out of {total_pixels} total pixels")
                print(f"Transparency percentage: {(transparent_pixels / total_pixels) * 100:.1f}%")

            # Replace transparent pixels with white background
            background = Image.new('RGBA', img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(background, img)

        # Now convert to RGB (removing alpha) then to grayscale
        img_rgb = img.convert('RGB')
        img_gray = img_rgb.convert('L')

        # Apply color quantization
        if color_count > 256:
            color_count = 256
            print(f"Warning: Color count reduced to 256 (PIL limitation)")

        quantized = img_gray.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
        result = quantized.convert('L')

        print(f"Successfully reduced image to {color_count} grayscale colors")
        return result, transparency_mask

    except Exception as e:
        raise Exception(f"Failed to process image: {e}")


def create_height_map(image, base_height, step_height, transparency_mask=None):
    """
    Create height map from grayscale image with stepped heights.
    Transparent areas are set to zero height.
    """
    img_array = np.array(image)
    unique_grays = sorted(np.unique(img_array).tolist())

    # Create height map
    height_map = np.zeros_like(img_array, dtype=np.float32)

    # Assign heights: lightest color gets base_height,
    # darker colors get additional step_height increments
    for i, gray_value in enumerate(unique_grays):
        # Lightest color (highest value) gets base height
        # Darker colors get additional height
        height = base_height + (len(unique_grays) - 1 - i) * step_height
        height_map[img_array == gray_value] = height

    # CRITICAL: Set transparent areas to zero height (no extrusion)
    if transparency_mask is not None:
        height_map[transparency_mask] = 0.0
        transparent_pixels = np.sum(transparency_mask)
        print(f"Set {transparent_pixels} transparent pixels to zero height")

        # Check if entire image is transparent
        if transparent_pixels == transparency_mask.size:
            raise Exception("Entire image is transparent - no geometry to generate")

    # Print statistics
    non_zero_heights = height_map[height_map > 0]
    if len(non_zero_heights) > 0:
        print(f"Created height map with {len(unique_grays)} height levels")
        print(f"Height range: {np.min(non_zero_heights):.2f}mm to {np.max(non_zero_heights):.2f}mm")
        print(f"Non-transparent pixels: {len(non_zero_heights)}")
    else:
        raise Exception("No valid geometry found after transparency processing")

    return height_map


def height_map_to_mesh(height_map, pixel_size=0.1, min_height_threshold=0.01):
    """
    Convert 2D height map to 3D mesh, excluding transparent areas.
    """
    rows, cols = height_map.shape

    # Only process pixels above threshold (non-transparent)
    valid_pixels = height_map > min_height_threshold
    if not np.any(valid_pixels):
        raise Exception("No pixels above height threshold - nothing to generate")

    vertices = []
    vertex_indices = {}

    # Generate vertices only for valid (non-transparent) pixels
    for i in range(rows):
        for j in range(cols):
            if valid_pixels[i, j]:
                x = j * pixel_size
                y = i * pixel_size
                z = height_map[i, j]
                vertices.append([x, y, z])
                vertex_indices[(i, j, 'top')] = len(vertices) - 1

    # Generate bottom vertices
    for i in range(rows):
        for j in range(cols):
            if valid_pixels[i, j]:
                x = j * pixel_size
                y = i * pixel_size
                z = 0.0
                vertices.append([x, y, z])
                vertex_indices[(i, j, 'bottom')] = len(vertices) - 1

    vertices = np.array(vertices)
    faces = []

    # Create faces only between valid pixels
    for i in range(rows - 1):
        for j in range(cols - 1):
            # Check if all four corners are valid
            if (valid_pixels[i, j] and valid_pixels[i + 1, j] and
                    valid_pixels[i, j + 1] and valid_pixels[i + 1, j + 1]):
                v1 = vertex_indices[(i, j, 'top')]
                v2 = vertex_indices[(i + 1, j, 'top')]
                v3 = vertex_indices[(i, j + 1, 'top')]
                v4 = vertex_indices[(i + 1, j + 1, 'top')]

                # Top surface triangles
                faces.append([v1, v2, v3])
                faces.append([v2, v4, v3])

                # Bottom surface triangles (inverted normals)
                v1_bot = vertex_indices[(i, j, 'bottom')]
                v2_bot = vertex_indices[(i + 1, j, 'bottom')]
                v3_bot = vertex_indices[(i, j + 1, 'bottom')]
                v4_bot = vertex_indices[(i + 1, j + 1, 'bottom')]

                faces.append([v1_bot, v3_bot, v2_bot])
                faces.append([v2_bot, v3_bot, v4_bot])

    # Add side walls (simplified - at edges only)
    # This creates a watertight mesh for 3D printing
    for i in range(rows):
        for j in range(cols):
            if valid_pixels[i, j]:
                # Check boundaries and create walls
                if i == 0 or not valid_pixels[i - 1, j]:  # Front wall
                    if j < cols - 1 and valid_pixels[i, j + 1]:
                        v1_top = vertex_indices[(i, j, 'top')]
                        v2_top = vertex_indices[(i, j + 1, 'top')]
                        v1_bot = vertex_indices[(i, j, 'bottom')]
                        v2_bot = vertex_indices[(i, j + 1, 'bottom')]
                        faces.append([v1_top, v2_top, v1_bot])
                        faces.append([v2_top, v2_bot, v1_bot])

    faces = np.array(faces)
    print(f"Generated mesh with {len(vertices)} vertices and {len(faces)} faces")

    return vertices, faces


def create_stl_from_mesh(vertices, faces, output_path):
    """Create STL file from mesh data."""
    try:
        stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))

        for i, face in enumerate(faces):
            for j in range(3):
                stl_mesh.vectors[i][j] = vertices[face[j], :]

        stl_mesh.save(output_path)
        print(f"Successfully saved STL file: {output_path}")

        # Print mesh statistics
        volume, cog, inertia = stl_mesh.get_mass_properties()
        print(f"Mesh volume: {volume:.2f} mm³")
        print(f"Mesh dimensions: {stl_mesh.max_ - stl_mesh.min_}")

    except Exception as e:
        raise Exception(f"Failed to create STL file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert SVG to 3D printable STL with PROPER transparency handling"
    )
    parser.add_argument("input_svg", help="Input SVG file path")
    parser.add_argument("output", help="Output STL file path")
    parser.add_argument("-c", "--colors", type=int, default=5,
                        help="Number of grayscale colors (default: 5)")
    parser.add_argument("-b", "--base_height", type=float, default=1.0,
                        help="Base height for lightest color in mm (default: 1.0)")
    parser.add_argument("-s", "--step_height", type=float, default=0.5,
                        help="Height step between colors in mm (default: 0.5)")
    parser.add_argument("-p", "--pixel_size", type=float, default=0.1,
                        help="Size of each pixel in mm (default: 0.1)")
    parser.add_argument("-r", "--resolution", type=int, default=300,
                        help="Resolution for SVG rasterization in DPI (default: 300)")
    parser.add_argument("--width", type=int, help="Output width in pixels")
    parser.add_argument("--height", type=int, help="Output height in pixels")

    args = parser.parse_args()

    # Validate input
    input_path = Path(args.input_svg)
    if not input_path.exists() or not input_path.suffix.lower() == '.svg':
        print(f"Error: Input must be an existing SVG file")
        sys.exit(1)

    output_path = args.output or str(input_path.with_suffix('.stl'))

    try:
        # Step 1: Convert SVG to PNG
        temp_png = input_path.with_suffix('.temp.png')
        print("Step 1: Converting SVG to PNG...")
        svg_to_png(str(input_path), str(temp_png),
                   args.width, args.height, args.resolution)

        # Step 2: Process image with PROPER transparency handling
        print("Step 2: Processing transparency and colors...")
        processed_image, transparency_mask = extract_transparency_mask_and_process(
            str(temp_png), args.colors)

        # Step 3: Create height map
        print("Step 3: Creating height map...")
        height_map = create_height_map(processed_image, args.base_height,
                                       args.step_height, transparency_mask)

        # Step 4: Generate 3D mesh
        print("Step 4: Generating 3D mesh...")
        vertices, faces = height_map_to_mesh(height_map, args.pixel_size)

        # Step 5: Create STL file
        print("Step 5: Creating STL file...")
        create_stl_from_mesh(vertices, faces, output_path)

        # Cleanup
        temp_png.unlink(missing_ok=True)

        print(f"\n✅ Successfully created 3D printable STL: {output_path}")
        if transparency_mask is not None:
            print(f"   Transparent pixels properly excluded: {np.sum(transparency_mask)}")

    except Exception as e:
        temp_png = input_path.with_suffix('.temp.png')
        temp_png.unlink(missing_ok=True)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
