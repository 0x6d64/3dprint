#!/usr/bin/env python3
"""
SVG to STL Heightmap Converter

This script converts an SVG image to a grayscale heightmap and generates
an STL file suitable for 3D printing. Colors are reduced to a specified
number of grayscale levels, with each level extruded to different heights.

Requirements:
    pip install cairosvg pillow numpy-stl scikit-learn

Usage:
    python svg_to_stl.py input.svg output.stl --color_count 5 --base_height 2.0 --step_height 1.0 --resolution 100
"""

import argparse
import numpy as np
from PIL import Image
import cairosvg
from sklearn.cluster import KMeans
from stl import mesh
import io
import sys


def svg_to_image(svg_path, width=None, height=None):
    """Convert SVG to PIL Image with alpha channel preserved."""
    try:
        # Read SVG file
        with open(svg_path, 'rb') as svg_file:
            svg_data = svg_file.read()

        # Convert SVG to PNG bytes
        png_data = cairosvg.svg2png(
            bytestring=svg_data,
            output_width=width,
            output_height=height
        )

        # Convert to PIL Image and preserve alpha channel
        image = Image.open(io.BytesIO(png_data))
        return image.convert('RGBA')

    except Exception as e:
        print(f"Error converting SVG to image: {e}")
        sys.exit(1)


def reduce_colors_kmeans(image, n_colors, alpha_threshold=128):
    """Reduce image colors using K-means clustering, excluding transparent pixels."""
    # Convert image to numpy array
    img_array = np.array(image)
    h, w, c = img_array.shape

    # Create transparency mask (alpha < threshold = transparent)
    if c == 4:  # RGBA
        alpha_channel = img_array[:, :, 3]
        transparency_mask = alpha_channel < alpha_threshold
        # Use RGB channels for color analysis
        rgb_array = img_array[:, :, :3]
    else:  # RGB
        transparency_mask = np.zeros((h, w), dtype=bool)
        rgb_array = img_array

    # Get non-transparent pixels only
    non_transparent_mask = ~transparency_mask
    non_transparent_pixels = rgb_array[non_transparent_mask]

    if len(non_transparent_pixels) == 0:
        print("Warning: Image is completely transparent!")
        return np.zeros((h, w, 3), dtype=int), np.array([]), transparency_mask

    print(f"   Processing {len(non_transparent_pixels)} non-transparent pixels out of {h * w} total")

    # Apply K-means clustering only to non-transparent pixels
    kmeans = KMeans(n_clusters=min(n_colors, len(non_transparent_pixels)),
                    random_state=42, n_init=10)
    kmeans.fit(non_transparent_pixels)

    # Get cluster centers (representative colors)
    colors = kmeans.cluster_centers_.astype(int)

    # Create new image with reduced colors
    new_image = np.zeros((h, w, 3), dtype=int)

    # Assign colors only to non-transparent pixels
    if len(non_transparent_pixels) > 0:
        labels = kmeans.labels_
        new_colors = colors[labels]
        new_image[non_transparent_mask] = new_colors

    return new_image, colors, transparency_mask


def convert_to_grayscale_levels(image, colors, transparency_mask):
    """Convert reduced color image to grayscale levels, excluding transparent areas."""
    if len(colors) == 0:
        return np.zeros(transparency_mask.shape, dtype=int), np.array([])

    # Convert colors to grayscale using luminance formula
    gray_values = []
    for color in colors:
        r, g, b = color
        # Standard luminance formula
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        gray_values.append(gray)

    # Sort colors by brightness (darkest to lightest)
    sorted_indices = np.argsort(gray_values)
    sorted_colors = colors[sorted_indices]
    sorted_grays = np.array(gray_values)[sorted_indices]

    # Create mapping from original colors to level indices
    h, w, c = image.shape
    level_image = np.full((h, w), -1, dtype=int)  # -1 indicates transparent/no extrusion

    # Only assign levels to non-transparent pixels
    non_transparent_mask = ~transparency_mask

    for i, color in enumerate(sorted_colors):
        # Find non-transparent pixels matching this color
        color_mask = np.all(image == color, axis=2) & non_transparent_mask
        level_image[color_mask] = i

    return level_image, sorted_grays


def create_heightmap(level_image, base_height, step_height):
    """Create heightmap from level image, with -1 indicating no extrusion."""
    heightmap = np.zeros_like(level_image, dtype=float)

    # Create mask for areas that should be extruded (not transparent)
    extrusion_mask = level_image >= 0

    # Assign heights: level 0 (darkest) gets base_height,
    # each subsequent level gets additional step_height
    # Transparent areas (level -1) remain at height 0
    for level in range(level_image.max() + 1):
        if level >= 0:  # Skip negative levels (transparent)
            mask = level_image == level
            heightmap[mask] = base_height + level * step_height

    return heightmap, extrusion_mask


def heightmap_to_stl(heightmap, extrusion_mask, output_path, scale_xy=1.0):
    """Convert heightmap to STL mesh, only extruding non-transparent areas."""
    h, w = heightmap.shape

    # Create a mapping from 2D coordinates to vertex indices
    vertex_map = {}
    vertices = []
    faces = []

    print("Generating mesh vertices...")

    # Generate vertices only for areas that should be extruded
    vertex_idx = 0
    for y in range(h):
        for x in range(w):
            if extrusion_mask[y, x]:
                # Top surface vertex
                vertices.append([x * scale_xy, y * scale_xy, heightmap[y, x]])
                vertex_map[(x, y, 'top')] = vertex_idx
                vertex_idx += 1

                # Bottom surface vertex (only if needed for side faces)
                vertices.append([x * scale_xy, y * scale_xy, 0.0])
                vertex_map[(x, y, 'bottom')] = vertex_idx
                vertex_idx += 1

    vertices = np.array(vertices)

    if len(vertices) == 0:
        print("Error: No vertices to extrude (image is completely transparent)")
        return

    print("Generating mesh faces...")

    # Generate faces for top surface
    for y in range(h - 1):
        for x in range(w - 1):
            # Check if all four corners should be extruded
            corners = [
                (x, y), (x + 1, y),
                (x, y + 1), (x + 1, y + 1)
            ]

            extruded_corners = [(cx, cy) for cx, cy in corners if extrusion_mask[cy, cx]]

            # Only create faces if we have a complete quad
            if len(extruded_corners) == 4:
                v1 = vertex_map[(x, y, 'top')]
                v2 = vertex_map[(x + 1, y, 'top')]
                v3 = vertex_map[(x, y + 1, 'top')]
                v4 = vertex_map[(x + 1, y + 1, 'top')]

                # Triangle 1: v1, v2, v3
                faces.append([v1, v2, v3])
                # Triangle 2: v2, v4, v3
                faces.append([v2, v4, v3])

    # Generate faces for bottom surface (reversed winding)
    for y in range(h - 1):
        for x in range(w - 1):
            corners = [
                (x, y), (x + 1, y),
                (x, y + 1), (x + 1, y + 1)
            ]

            extruded_corners = [(cx, cy) for cx, cy in corners if extrusion_mask[cy, cx]]

            if len(extruded_corners) == 4:
                v1 = vertex_map[(x, y, 'bottom')]
                v2 = vertex_map[(x + 1, y, 'bottom')]
                v3 = vertex_map[(x, y + 1, 'bottom')]
                v4 = vertex_map[(x + 1, y + 1, 'bottom')]

                # Triangle 1: v1, v3, v2 (reversed)
                faces.append([v1, v3, v2])
                # Triangle 2: v2, v3, v4 (reversed)
                faces.append([v2, v3, v4])

    # Generate side faces along edges of extruded areas
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # right, down, left, up

    for y in range(h):
        for x in range(w):
            if not extrusion_mask[y, x]:
                continue

            # Check each direction for edges
            for dx, dy in directions:
                nx, ny = x + dx, y + dy

                # If neighbor is outside bounds or not extruded, create side face
                if (nx < 0 or nx >= w or ny < 0 or ny >= h or
                        not extrusion_mask[ny, nx]):

                    # Create side face based on direction
                    if dx == 1 and dy == 0:  # right edge
                        if y < h - 1 and extrusion_mask[y + 1, x]:
                            v1_top = vertex_map[(x, y, 'top')]
                            v2_top = vertex_map[(x, y + 1, 'top')]
                            v1_bottom = vertex_map[(x, y, 'bottom')]
                            v2_bottom = vertex_map[(x, y + 1, 'bottom')]

                            faces.append([v1_top, v2_top, v1_bottom])
                            faces.append([v2_top, v2_bottom, v1_bottom])

                    elif dx == 0 and dy == 1:  # bottom edge
                        if x < w - 1 and extrusion_mask[y, x + 1]:
                            v1_top = vertex_map[(x, y, 'top')]
                            v2_top = vertex_map[(x + 1, y, 'top')]
                            v1_bottom = vertex_map[(x, y, 'bottom')]
                            v2_bottom = vertex_map[(x + 1, y, 'bottom')]

                            faces.append([v1_top, v1_bottom, v2_top])
                            faces.append([v2_top, v1_bottom, v2_bottom])

                    elif dx == -1 and dy == 0:  # left edge
                        if y < h - 1 and extrusion_mask[y + 1, x]:
                            v1_top = vertex_map[(x, y, 'top')]
                            v2_top = vertex_map[(x, y + 1, 'top')]
                            v1_bottom = vertex_map[(x, y, 'bottom')]
                            v2_bottom = vertex_map[(x, y + 1, 'bottom')]

                            faces.append([v1_top, v1_bottom, v2_top])
                            faces.append([v2_top, v1_bottom, v2_bottom])

                    elif dx == 0 and dy == -1:  # top edge
                        if x < w - 1 and extrusion_mask[y, x + 1]:
                            v1_top = vertex_map[(x, y, 'top')]
                            v2_top = vertex_map[(x + 1, y, 'top')]
                            v1_bottom = vertex_map[(x, y, 'bottom')]
                            v2_bottom = vertex_map[(x + 1, y, 'bottom')]

                            faces.append([v1_top, v2_top, v1_bottom])
                            faces.append([v2_top, v2_bottom, v1_bottom])

    if len(faces) == 0:
        print("Error: No faces generated")
        return

    faces = np.array(faces)

    print(f"Generated {len(vertices)} vertices and {len(faces)} faces")

    # Create STL mesh
    stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
    for i, face in enumerate(faces):
        for j in range(3):
            stl_mesh.vectors[i][j] = vertices[face[j], :]

    # Save STL file
    stl_mesh.save(output_path)
    print(f"STL file saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Convert SVG to STL heightmap')
    parser.add_argument('input_svg', help='Input SVG file path')
    parser.add_argument('output_stl', help='Output STL file path')
    parser.add_argument('--color_count', type=int, default=5,
                        help='Number of grayscale levels (default: 5)')
    parser.add_argument('--base_height', type=float, default=2.0,
                        help='Height of the lightest color in mm (default: 2.0)')
    parser.add_argument('--step_height', type=float, default=1.0,
                        help='Additional height per color level in mm (default: 1.0)')
    parser.add_argument('--resolution', type=int, default=100,
                        help='Image resolution for processing (default: 100)')
    parser.add_argument('--alpha_threshold', type=int, default=128,
                        help='Alpha threshold for transparency (0-255, default: 128)')
    parser.add_argument('--scale_xy', type=float, default=0.5,
                        help='XY scale factor in mm per pixel (default: 0.5)')

    args = parser.parse_args()

    print(f"Converting SVG to STL heightmap...")
    print(f"Input: {args.input_svg}")
    print(f"Output: {args.output_stl}")
    print(f"Color levels: {args.color_count}")
    print(f"Base height: {args.base_height}mm")
    print(f"Step height: {args.step_height}mm")
    print(f"Resolution: {args.resolution}px")

    # Step 1: Convert SVG to image
    print("\n1. Converting SVG to image...")
    image = svg_to_image(args.input_svg, width=args.resolution, height=args.resolution)
    print(f"   Image size: {image.size}")

    # Step 2: Reduce colors using K-means
    print("\n2. Reducing colors...")
    reduced_image, colors, transparency_mask = reduce_colors_kmeans(image, args.color_count, args.alpha_threshold)
    print(f"   Reduced to {len(colors)} colors")

    if len(colors) == 0:
        print("Error: No non-transparent pixels found in image!")
        return

    # Step 3: Convert to grayscale levels
    print("\n3. Converting to grayscale levels...")
    level_image, gray_values = convert_to_grayscale_levels(reduced_image, colors, transparency_mask)
    print(f"   Gray levels: {gray_values}")

    # Step 4: Create heightmap
    print("\n4. Creating heightmap...")
    heightmap, extrusion_mask = create_heightmap(level_image, args.base_height, args.step_height)
    max_height = args.base_height + (args.color_count - 1) * args.step_height
    print(f"   Height range: {args.base_height}mm to {max_height}mm")

    extruded_pixels = np.sum(extrusion_mask)
    total_pixels = extrusion_mask.size
    print(f"   Extruding {extruded_pixels}/{total_pixels} pixels ({extruded_pixels / total_pixels * 100:.1f}%)")

    # Step 5: Generate STL
    print("\n5. Generating STL mesh...")
    heightmap_to_stl(heightmap, extrusion_mask, args.output_stl, args.scale_xy)

    print(f"\nConversion complete!")
    print(
        f"STL dimensions: {heightmap.shape[1] * args.scale_xy:.1f} x {heightmap.shape[0] * args.scale_xy:.1f} x {max_height:.1f} mm")


if __name__ == "__main__":
    main()