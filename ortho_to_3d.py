#!/usr/bin/env python3
"""Reconstruct 3D model from dimensioned orthographic projections in Rerun.

Dimensions (from engineering drawing):
  Width (X):  75  (25 + 25 + 25)
  Depth (Y):  50  (25 + 25)
  Height (Z): 37  (12 base + 25 upper)

Shape: rectangular base with a trapezoidal upper prism.
  Base block: 75 x 50 x 12
  Upper section: trapezoidal cross-section, extruded y=0..25
  Cross-section (front view): slope from (20,12) to (55,37), flat top to (75,37)
"""

import math
import numpy as np
import rerun as rr


def build_shape():
    """Build triangle mesh and feature edges for the dimensioned shape."""

    # 14 unique vertices
    V = np.array([
        [0, 0, 0],      # 0
        [75, 0, 0],     # 1
        [75, 50, 0],    # 2
        [0, 50, 0],     # 3
        [0, 0, 12],     # 4
        [20, 0, 12],    # 5
        [75, 25, 12],   # 6
        [75, 50, 12],   # 7
        [0, 50, 12],    # 8
        [20, 25, 12],   # 9
        [55, 0, 37],    # 10
        [75, 0, 37],    # 11
        [75, 25, 37],   # 12
        [55, 25, 37],   # 13
    ], dtype=np.float32)

    # Slope normal: perpendicular to slope direction (35,0,25) and extrusion (0,1,0)
    s = math.sqrt(74)
    slope_n = (-5 / s, 0, 7 / s)

    # Face definitions: (normal, list_of_triangle_index_triples)
    # Concave polygons are manually triangulated via ear decomposition.
    faces = [
        # 1. Bottom (z=0)
        ((0, 0, -1), [(0, 3, 2), (0, 2, 1)]),
        # 2. Front (y=0) — concave at vertex 5
        ((0, -1, 0), [(0, 1, 11), (0, 11, 10), (0, 10, 4), (10, 5, 4)]),
        # 3. Back (y=50)
        ((0, 1, 0), [(3, 8, 7), (3, 7, 2)]),
        # 4. Left (x=0)
        ((-1, 0, 0), [(0, 4, 8), (0, 8, 3)]),
        # 5. Right (x=75) — concave at vertex 6
        ((1, 0, 0), [(1, 2, 7), (1, 7, 12), (1, 12, 11), (7, 6, 12)]),
        # 6. Top flat (z=37)
        ((0, 0, 1), [(10, 11, 12), (10, 12, 13)]),
        # 7. Slope
        (slope_n, [(5, 10, 13), (5, 13, 9)]),
        # 8. Base top (z=12) — concave at vertex 9
        ((0, 0, 1), [(4, 5, 6), (4, 6, 7), (4, 7, 8), (5, 9, 6)]),
        # 9. Upper back (y=25)
        ((0, 1, 0), [(9, 13, 12), (9, 12, 6)]),
    ]

    verts, norms, tris = [], [], []

    for normal, triangles in faces:
        for i0, i1, i2 in triangles:
            base = len(verts)
            verts.extend([V[i0].tolist(), V[i1].tolist(), V[i2].tolist()])
            norms.extend([list(normal)] * 3)
            tris.append([base, base + 1, base + 2])

    # All edges are feature edges (no coplanar adjacent faces)
    edge_pairs = [
        (0, 1), (0, 3), (0, 4), (1, 2), (1, 11), (2, 3), (2, 7),
        (3, 8), (4, 5), (4, 8), (5, 9), (5, 10), (6, 7), (6, 9),
        (6, 12), (7, 8), (9, 13), (10, 11), (10, 13), (11, 12), (12, 13),
    ]
    edges = [[V[a].tolist(), V[b].tolist()] for a, b in edge_pairs]

    return (
        np.array(verts, dtype=np.float32),
        np.array(norms, dtype=np.float32),
        np.array(tris, dtype=np.uint32),
        edges,
    )


def main():
    vertices, normals, triangles, edges = build_shape()

    rr.init("ortho_3d")
    rr.connect_grpc("rerun+http://127.0.0.1:9876/proxy")

    rr.log("shape/solid", rr.Mesh3D(
        vertex_positions=vertices,
        vertex_normals=normals,
        triangle_indices=triangles,
        vertex_colors=np.full(
            (len(vertices), 4), [150, 180, 220, 255], dtype=np.uint8
        ),
    ))

    rr.log("shape/wireframe", rr.LineStrips3D(
        edges,
        colors=[[30, 30, 60, 255]],
        radii=[0.3],
    ))

    print(f"Sent: {len(triangles)} tris, {len(edges)} edges")


if __name__ == "__main__":
    main()
