#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construct Curved Planar Reformation (CPR) volumes from MEDIS contour files.

Generates two complementary views:
1. Cross-sectional CPR: Straightened 3D volume (scroll through vessel like a pipe)
2. Longitudinal CPR: Rotated 3D volume (same data, axes permuted for longitudinal viewing)

Usage:
    python medis_to_cpr.py <medis_txt> <nifti_cta> <output_dir>

Output:
    {patient_id}_{vessel}_cpr_cross.nii.gz   - Cross-sectional volume (U, V, S)
    {patient_id}_{vessel}_cpr_long.nii.gz    - Longitudinal volume (S, U, V)
"""

import numpy as np
import SimpleITK as sitk
from scipy.interpolate import CubicSpline
from scipy.ndimage import map_coordinates
import os
import sys
import argparse


def parse_medis_contours_with_slicedist(filepath: str) -> tuple:
    """
    Parse MEDIS contour file, extracting contours and SliceDistance values.
    
    Returns:
        contours: {'Lumen': [np.array, ...], 'VesselWall': [np.array, ...]}
        slice_distances: {'Lumen': [float, ...], 'VesselWall': [float, ...]}
        metadata: {'vessel_name': 'lad', 'patient_id': '...', ...}
    """
    contours = {'Lumen': [], 'VesselWall': []}
    slice_distances = {'Lumen': [], 'VesselWall': []}
    metadata = {}
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Parse metadata headers
        if line.startswith('# vessel_name'):
            metadata['vessel_name'] = line.split(':')[1].strip()
            i += 1
        elif line.startswith('# patient_id'):
            metadata['patient_id'] = line.split(':')[1].strip()
            i += 1
        elif line.startswith('# Contour index:'):
            # Start of a new contour block
            group = None
            num_points = 0
            slice_dist = 0.0
            
            # Read contour metadata
            while i < len(lines) and not lines[i].strip().startswith('# Number of points:'):
                current_line = lines[i].strip()
                if current_line.startswith('# group:'):
                    group = current_line.split(':')[1].strip()
                elif current_line.startswith('# SliceDistance:'):
                    try:
                        slice_dist = float(current_line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
                
                if current_line.startswith('# Contour index:') and group is not None:
                    break
                i += 1
            
            # Parse number of points
            if i < len(lines) and lines[i].strip().startswith('# Number of points:'):
                try:
                    num_points = int(lines[i].split(':')[1].strip())
                except (ValueError, IndexError):
                    num_points = 0
                i += 1
                
                # Read the actual points
                points = []
                for _ in range(num_points):
                    if i < len(lines):
                        parts = lines[i].strip().split()
                        if len(parts) >= 3:
                            try:
                                points.append([float(parts[0]), float(parts[1]), float(parts[2])])
                            except ValueError:
                                pass
                        i += 1
                
                # Store the contour if valid
                if len(points) > 2 and group in contours:
                    contours[group].append(np.array(points))
                    slice_distances[group].append(slice_dist)
        else:
            i += 1
    
    return contours, slice_distances, metadata


def extract_centerline(contours: list) -> np.ndarray:
    """
    Extract centerline from lumen contours as centroids (center of mass).
    
    Args:
        contours: List of Nx3 contour arrays
    
    Returns:
        centerline: Mx3 array of centerline points
    """
    centerline = np.array([np.mean(c, axis=0) for c in contours])
    return centerline


def compute_tangent_vectors(centerline: np.ndarray) -> np.ndarray:
    """
    Compute tangent vectors using central differences.
    """
    n = len(centerline)
    tangents = np.zeros_like(centerline)
    
    # Central difference for interior points
    tangents[1:-1] = centerline[2:] - centerline[:-2]
    
    # Forward difference for first point
    tangents[0] = centerline[1] - centerline[0]
    
    # Backward difference for last point
    tangents[-1] = centerline[-1] - centerline[-2]
    
    # Normalize
    norms = np.linalg.norm(tangents, axis=1, keepdims=True)
    tangents = tangents / (norms + 1e-10)
    
    return tangents


def compute_rotation_minimizing_frame(tangents: np.ndarray) -> tuple:
    """
    Compute the projection-step Rotation Minimizing Frame (Bishop Frame).
    Avoids the "twist" problem of Frenet-Serret frames.

    This is retained for comparison/backwards compatibility. The production
    CPR pipeline uses compute_double_reflection_rmf(), which has lower twist
    drift on real coronary geometry.
    
    Returns:
        normals: Nx3 unit normal vectors
        binormals: Nx3 unit binormal vectors
    """
    n = len(tangents)
    normals = np.zeros_like(tangents)
    binormals = np.zeros_like(tangents)
    
    # Initialize: pick arbitrary vector perpendicular to first tangent
    T0 = tangents[0]
    
    # Choose axis least aligned with tangent
    if abs(T0[0]) <= abs(T0[1]) and abs(T0[0]) <= abs(T0[2]):
        ref = np.array([1.0, 0.0, 0.0])
    elif abs(T0[1]) <= abs(T0[2]):
        ref = np.array([0.0, 1.0, 0.0])
    else:
        ref = np.array([0.0, 0.0, 1.0])
    
    # Initial normal via cross product
    normals[0] = np.cross(T0, ref)
    normals[0] /= np.linalg.norm(normals[0])
    binormals[0] = np.cross(T0, normals[0])
    
    # Propagate frame along centerline
    for i in range(1, n):
        Ti = tangents[i]
        Ni_prev = normals[i - 1]
        
        # Project previous normal onto plane perpendicular to current tangent
        Ni = Ni_prev - np.dot(Ni_prev, Ti) * Ti
        norm = np.linalg.norm(Ni)
        
        if norm < 1e-10:
            Ni = Ni_prev
        else:
            Ni = Ni / norm
        
        normals[i] = Ni
        binormals[i] = np.cross(Ti, Ni)
    
    return normals, binormals


def compute_double_reflection_rmf(centerline: np.ndarray,
                                  tangents: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute Rotation Minimizing Frame using Wang et al. 2008 double reflection.

    This is second-order accurate and is the default frame method for exported
    CPR/VesselScene data.
    """
    n = len(tangents)
    normals = np.zeros_like(tangents)
    binormals = np.zeros_like(tangents)

    T0 = tangents[0]
    if abs(T0[0]) <= abs(T0[1]) and abs(T0[0]) <= abs(T0[2]):
        ref = np.array([1.0, 0.0, 0.0])
    elif abs(T0[1]) <= abs(T0[2]):
        ref = np.array([0.0, 1.0, 0.0])
    else:
        ref = np.array([0.0, 0.0, 1.0])

    normals[0] = np.cross(T0, ref)
    normals[0] /= np.linalg.norm(normals[0])
    binormals[0] = np.cross(T0, normals[0])

    for i in range(1, n):
        v1 = centerline[i] - centerline[i - 1]
        c1 = float(v1 @ v1)
        if c1 < 1e-20:
            normals[i] = normals[i - 1]
            normals[i] -= (normals[i] @ tangents[i]) * tangents[i]
            normals[i] /= np.linalg.norm(normals[i])
            binormals[i] = np.cross(tangents[i], normals[i])
            continue

        T_l = tangents[i - 1] - (2.0 / c1) * (v1 @ tangents[i - 1]) * v1
        N_l = normals[i - 1] - (2.0 / c1) * (v1 @ normals[i - 1]) * v1

        v2 = tangents[i] - T_l
        c2 = float(v2 @ v2)
        if c2 < 1e-20:
            normals[i] = N_l
        else:
            normals[i] = N_l - (2.0 / c2) * (v2 @ N_l) * v2

        # Re-orthogonalize against current tangent to neutralize round-off.
        normals[i] -= (normals[i] @ tangents[i]) * tangents[i]
        normals[i] /= np.linalg.norm(normals[i])
        binormals[i] = np.cross(tangents[i], normals[i])

    return normals, binormals


def resample_centerline(centerline: np.ndarray, target_spacing: float) -> np.ndarray:
    """
    Resample centerline to uniform spacing using cubic spline interpolation.
    
    Args:
        centerline: Nx3 array of centerline points
        target_spacing: Desired spacing between points (mm)
    
    Returns:
        resampled: Mx3 array with uniform spacing
    """
    # Calculate cumulative arc length
    diffs = np.diff(centerline, axis=0)
    segment_lengths = np.linalg.norm(diffs, axis=1)
    arc_length = np.concatenate([[0], np.cumsum(segment_lengths)])
    total_length = arc_length[-1]
    
    if total_length < 1e-6:
        return centerline
    
    # Number of points for target spacing
    n_points = max(int(total_length / target_spacing) + 1, 2)
    
    # Create uniform arc length samples
    new_arc_length = np.linspace(0, total_length, n_points)
    
    # Interpolate each coordinate
    resampled = np.zeros((n_points, 3))
    for axis in range(3):
        cs = CubicSpline(arc_length, centerline[:, axis])
        resampled[:, axis] = cs(new_arc_length)
    
    return resampled


def create_cross_sectional_cpr(
    volume: np.ndarray,
    spacing: tuple,
    origin: tuple,
    centerline: np.ndarray,
    normals: np.ndarray,
    binormals: np.ndarray,
    cross_section_size_mm: float = 30.0,
    pixel_resolution: float = None,
    direction: np.ndarray = None,
    interpolation_order: int = 1,
) -> tuple:
    """
    Create cross-sectional CPR volume (straightened vessel).
    
    Args:
        volume: 3D CTA volume as numpy array
        spacing: (sx, sy, sz) voxel spacing in mm
        origin: (ox, oy, oz) volume origin in world coordinates
        centerline: Nx3 centerline points in world coordinates
        normals: Nx3 normal vectors
        binormals: Nx3 binormal vectors
        cross_section_size_mm: Size of cross-section in mm (default 30mm = 3cm)
        pixel_resolution: Output pixel size in mm (default: use CTA spacing)
    
    Returns:
        cpr_volume: 3D numpy array (u, v, s)
        cpr_spacing: (du, dv, ds) output spacing
    """
    if pixel_resolution is None:
        # Use average of CTA in-plane spacing
        pixel_resolution = (spacing[0] + spacing[1]) / 2

    # Inverse direction matrix for world->voxel transform. Defaults to identity.
    if direction is None:
        D_inv = np.eye(3)
    else:
        D_inv = np.asarray(direction).reshape(3, 3).T  # orthonormal, so transpose = inverse

    n_slices = len(centerline)
    slice_size = int(cross_section_size_mm / pixel_resolution)
    half_size = slice_size // 2

    # Create UV grid (centered at 0)
    u_coords = np.arange(-half_size, half_size) * pixel_resolution
    v_coords = np.arange(-half_size, half_size) * pixel_resolution
    U, V = np.meshgrid(u_coords, v_coords, indexing='xy')

    # Output volume
    cpr_volume = np.zeros((slice_size, slice_size, n_slices), dtype=np.float32)

    print(f"  Creating cross-sectional CPR: {slice_size}x{slice_size}x{n_slices}")

    for i in range(n_slices):
        P = centerline[i]
        N = normals[i]
        B = binormals[i]

        # Compute world coordinates for this slice: W = P + u*N + v*B
        world_x = P[0] + U * N[0] + V * B[0]
        world_y = P[1] + U * N[1] + V * B[1]
        world_z = P[2] + U * N[2] + V * B[2]

        # World -> local (relative to origin) -> voxel index, accounting for direction matrix
        lx = world_x - origin[0]
        ly = world_y - origin[1]
        lz = world_z - origin[2]
        voxel_x = (D_inv[0, 0] * lx + D_inv[0, 1] * ly + D_inv[0, 2] * lz) / spacing[0]
        voxel_y = (D_inv[1, 0] * lx + D_inv[1, 1] * ly + D_inv[1, 2] * lz) / spacing[1]
        voxel_z = (D_inv[2, 0] * lx + D_inv[2, 1] * ly + D_inv[2, 2] * lz) / spacing[2]

        # Sample CT intensities. Use order=1 for linear CT reformats,
        # order=0 only for label/mask volumes or deliberately voxelated demos.
        coords = [voxel_x.ravel(), voxel_y.ravel(), voxel_z.ravel()]
        sampled = map_coordinates(volume, coords, order=interpolation_order, mode='constant', cval=-1024)
        cpr_volume[:, :, i] = sampled.reshape(slice_size, slice_size)
    
    # Compute slice spacing from centerline
    if n_slices > 1:
        centerline_diffs = np.diff(centerline, axis=0)
        slice_spacing = np.mean(np.linalg.norm(centerline_diffs, axis=1))
    else:
        slice_spacing = pixel_resolution
    
    cpr_spacing = (pixel_resolution, pixel_resolution, slice_spacing)
    
    return cpr_volume, cpr_spacing


def create_longitudinal_cpr(
    volume: np.ndarray,
    spacing: tuple,
    origin: tuple,
    centerline: np.ndarray,
    tangents: np.ndarray,
    normals: np.ndarray,
    binormals: np.ndarray,
    cross_section_size_mm: float = 30.0,
    pixel_resolution: float = None,
    direction: np.ndarray = None,
    interpolation_order: int = 1,
) -> tuple:
    """
    Create longitudinal CPR volume (rotated view of vessel).
    
    Same data as cross-sectional CPR but with axes permuted for longitudinal viewing:
    - Cross-sectional: (U, V, S) - scroll S to move along vessel
    - Longitudinal: (S, U, V) - scroll V to pan through vessel depth (front-to-back)
    
    This provides the full 3D straightened block, allowing the viewer's MPR tools
    to rotate the viewing angle 360 degrees around the centerline.
    
    Returns:
        long_volume: 3D numpy array (S, U, V) - rotated view
        long_spacing: (ds, du, dv) output spacing
    """
    if pixel_resolution is None:
        pixel_resolution = (spacing[0] + spacing[1]) / 2

    if direction is None:
        D_inv = np.eye(3)
    else:
        D_inv = np.asarray(direction).reshape(3, 3).T

    n_slices = len(centerline)
    slice_size = int(cross_section_size_mm / pixel_resolution)
    half_size = slice_size // 2

    # Create UV grid (centered at 0)
    u_coords = np.arange(-half_size, half_size) * pixel_resolution
    v_coords = np.arange(-half_size, half_size) * pixel_resolution
    U, V = np.meshgrid(u_coords, v_coords, indexing='xy')

    # Output volume: (S, U, V) - longitudinal orientation
    long_volume = np.zeros((n_slices, slice_size, slice_size), dtype=np.float32)

    print(f"  Creating longitudinal CPR: {n_slices}x{slice_size}x{slice_size} (S×U×V)")

    for i in range(n_slices):
        P = centerline[i]
        N = normals[i]
        B = binormals[i]

        world_x = P[0] + U * N[0] + V * B[0]
        world_y = P[1] + U * N[1] + V * B[1]
        world_z = P[2] + U * N[2] + V * B[2]

        lx = world_x - origin[0]
        ly = world_y - origin[1]
        lz = world_z - origin[2]
        voxel_x = (D_inv[0, 0] * lx + D_inv[0, 1] * ly + D_inv[0, 2] * lz) / spacing[0]
        voxel_y = (D_inv[1, 0] * lx + D_inv[1, 1] * ly + D_inv[1, 2] * lz) / spacing[1]
        voxel_z = (D_inv[2, 0] * lx + D_inv[2, 1] * ly + D_inv[2, 2] * lz) / spacing[2]

        coords = [voxel_x.ravel(), voxel_y.ravel(), voxel_z.ravel()]
        sampled = map_coordinates(volume, coords, order=interpolation_order, mode='constant', cval=-1024)
        long_volume[i, :, :] = sampled.reshape(slice_size, slice_size)
    
    # Compute slice spacing from centerline
    if n_slices > 1:
        centerline_diffs = np.diff(centerline, axis=0)
        slice_spacing = np.mean(np.linalg.norm(centerline_diffs, axis=1))
    else:
        slice_spacing = pixel_resolution
    
    long_spacing = (slice_spacing, pixel_resolution, pixel_resolution)
    
    return long_volume, long_spacing


def save_nifti(volume: np.ndarray, spacing: tuple, output_path: str, description: str = ""):
    """
    Save volume as NIfTI file using SimpleITK.
    """
    # Create SimpleITK image
    sitk_image = sitk.GetImageFromArray(volume.transpose(2, 1, 0))  # Convert to ITK order
    sitk_image.SetSpacing(spacing)
    sitk_image.SetOrigin((0, 0, 0))  # CPR volumes are in their own coordinate system
    
    # Add description metadata
    if description:
        sitk_image.SetMetaData("0008|103e", description)  # Series Description
    
    # Write file
    sitk.WriteImage(sitk_image, output_path, useCompression=True)
    print(f"  Saved: {output_path}")
    print(f"    Size: {volume.shape}, Spacing: {spacing}")


def save_centerline_json(centerline: np.ndarray, normals: np.ndarray, binormals: np.ndarray, 
                         tangents: np.ndarray, output_path: str,
                         frame_method: str = "double_reflection_wang2008"):
    """
    Save centerline and frame data as JSON for later mesh/point transformation.
    """
    import json
    
    data = {
        "centerline": centerline.tolist(),
        "tangents": tangents.tolist(),
        "normals": normals.tolist(),
        "binormals": binormals.tolist(),
        "n_points": len(centerline),
        "frame_method": frame_method,
        "description": "Rotation Minimizing Frame for CPR coordinate transformation"
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"  Saved centerline frame: {output_path}")


def construct_cpr(medis_path: str, cta_path: str, output_dir: str,
                  cross_section_mm: float = 30.0,
                  interpolation_order: int = 1) -> list:
    """
    Main function to construct CPR volumes from MEDIS file.
    
    Args:
        medis_path: Path to MEDIS contour TXT file
        cta_path: Path to CTA NIfTI volume
        output_dir: Output directory
        cross_section_mm: Cross-section size in mm (default 30mm = 3cm)
        interpolation_order: scipy map_coordinates order. Use 1 for CT intensity
            reformats and 0 for masks/labels.
    
    Returns:
        List of output file paths
    """
    print(f"\n{'='*60}")
    print(f"CPR Construction")
    print(f"{'='*60}")
    print(f"MEDIS file: {os.path.basename(medis_path)}")
    print(f"CTA file: {os.path.basename(cta_path)}")
    
    # Parse MEDIS contours
    print("\n1. Parsing MEDIS contours...")
    contours, slice_distances, metadata = parse_medis_contours_with_slicedist(medis_path)
    
    if not contours['Lumen']:
        raise ValueError("No Lumen contours found in MEDIS file")
    
    print(f"  Found {len(contours['Lumen'])} Lumen contours")
    
    # Extract centerline from lumen contours
    print("\n2. Extracting centerline (lumen centroids)...")
    centerline = extract_centerline(contours['Lumen'])
    print(f"  Centerline points: {len(centerline)}")
    
    # Load CTA volume
    print("\n3. Loading CTA volume...")
    cta_sitk = sitk.ReadImage(cta_path)
    cta_volume = sitk.GetArrayFromImage(cta_sitk).transpose(2, 1, 0)  # Convert to (x, y, z)
    cta_spacing = cta_sitk.GetSpacing()
    cta_origin = cta_sitk.GetOrigin()
    cta_direction = np.array(cta_sitk.GetDirection()).reshape(3, 3)
    print(f"  Volume shape: {cta_volume.shape}")
    print(f"  Spacing: {cta_spacing} mm")
    print(f"  Origin: {cta_origin}")
    print(f"  Direction: {cta_direction.flatten().tolist()}")
    print(f"  Interpolation order: {interpolation_order}")
    
    # Resample centerline to natural CTA spacing
    target_spacing = min(cta_spacing)  # Use finest resolution
    print(f"\n4. Resampling centerline to {target_spacing:.3f} mm spacing...")
    centerline_resampled = resample_centerline(centerline, target_spacing)
    print(f"  Resampled centerline: {len(centerline_resampled)} points")
    
    # Compute Rotation Minimizing Frame
    print("\n5. Computing Rotation Minimizing Frame...")
    tangents = compute_tangent_vectors(centerline_resampled)
    frame_method = "double_reflection_wang2008"
    normals, binormals = compute_double_reflection_rmf(centerline_resampled, tangents)
    print(f"  Frame method: {frame_method}")
    
    # Create cross-sectional CPR
    print("\n6. Creating cross-sectional CPR volume...")
    cpr_cross, cross_spacing = create_cross_sectional_cpr(
        cta_volume, cta_spacing, cta_origin,
        centerline_resampled, normals, binormals,
        cross_section_size_mm=cross_section_mm,
        pixel_resolution=target_spacing,
        direction=cta_direction,
        interpolation_order=interpolation_order,
    )
    
    # Create longitudinal CPR
    print("\n7. Creating longitudinal CPR volume...")
    cpr_long, long_spacing = create_longitudinal_cpr(
        cta_volume, cta_spacing, cta_origin,
        centerline_resampled, tangents, normals, binormals,
        cross_section_size_mm=cross_section_mm,
        pixel_resolution=target_spacing,
        direction=cta_direction,
        interpolation_order=interpolation_order,
    )
    
    # Generate output filenames
    patient_id = metadata.get('patient_id', 'unknown').replace(' ', '_')
    vessel_name = metadata.get('vessel_name', 'vessel').upper()
    
    os.makedirs(output_dir, exist_ok=True)
    
    output_files = []
    
    # Save cross-sectional CPR
    cross_path = os.path.join(output_dir, f"{patient_id}_{vessel_name}_cpr_cross.nii.gz")
    save_nifti(cpr_cross, cross_spacing, cross_path, 
               f"Cross-sectional CPR - {vessel_name}")
    output_files.append(cross_path)
    
    # Save longitudinal CPR
    long_path = os.path.join(output_dir, f"{patient_id}_{vessel_name}_cpr_long.nii.gz")
    save_nifti(cpr_long, long_spacing, long_path,
               f"Longitudinal CPR - {vessel_name}")
    output_files.append(long_path)
    
    # Save centerline frame for coordinate transformation
    frame_path = os.path.join(output_dir, f"{patient_id}_{vessel_name}_cpr_frame.json")
    save_centerline_json(centerline_resampled, normals, binormals, tangents, frame_path,
                         frame_method=frame_method)
    output_files.append(frame_path)
    
    print(f"\n{'='*60}")
    print("CPR Construction Complete!")
    print(f"{'='*60}")
    
    return output_files


def main():
    parser = argparse.ArgumentParser(
        description='Construct CPR volumes from MEDIS contour files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output files:
  {patient}_{vessel}_cpr_cross.nii.gz  - Cross-sectional straightened volume
  {patient}_{vessel}_cpr_long.nii.gz   - Longitudinal slice volume
  {patient}_{vessel}_cpr_frame.json    - Centerline frame for coordinate transform

Example:
  python medis_to_cpr.py medis_lad.txt cta.nii.gz ./output/
        """
    )
    parser.add_argument('medis_txt', help='MEDIS contour TXT file')
    parser.add_argument('nifti_cta', help='CTA NIfTI volume')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('--size', type=float, default=30.0,
                        help='Cross-section size in mm (default: 30)')
    parser.add_argument(
        '--interpolation',
        choices=['nearest', 'linear', 'cubic'],
        default='linear',
        help='Voxel resampling for CT intensities (default: linear). Use nearest for masks/labels.',
    )
    
    args = parser.parse_args()
    order = {'nearest': 0, 'linear': 1, 'cubic': 3}[args.interpolation]
    construct_cpr(args.medis_txt, args.nifti_cta, args.output_dir, args.size, order)


if __name__ == "__main__":
    main()
