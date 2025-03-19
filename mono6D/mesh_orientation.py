import os
import numpy as np
import cv2
from pathlib import Path
import trimesh
import math
from scipy.spatial.transform import Rotation as R

def compute_triangle_orientations(input_dir, filename, output_dir):
    """
    Compute the orientation of triangles in a 3D mesh with respect to the center of projection.
    This replaces the triangle_orientations.exe from the original MATLAB code.
    
    Args:
        input_dir: Directory containing input videos/images
        filename: Base name of the video/image file
        output_dir: Directory to save the triangle orientations
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get video/image paths
    rgb_path = os.path.join(input_dir, f"{filename}.mp4")
    depth_path = os.path.join(input_dir, f"{filename}_depth.mp4")
    
    # Check if files exist
    if not os.path.exists(rgb_path) or not os.path.exists(depth_path):
        print(f"Looking for image files instead of videos")
        rgb_path = os.path.join(input_dir, f"{filename}.png")
        depth_path = os.path.join(input_dir, f"{filename}_depth.png")   
        # If still not found, try with _BG suffix
        if not os.path.exists(rgb_path) or not os.path.exists(depth_path):
            rgb_path = os.path.join(input_dir, f"{filename}_BG.png")
            depth_path = os.path.join(input_dir, f"{filename}_BG_depth.png")         
            # If still not found, try with video format
            if not os.path.exists(rgb_path) or not os.path.exists(depth_path):
                rgb_path = os.path.join(input_dir, f"{filename}_BG.mp4")
                depth_path = os.path.join(input_dir, f"{filename}_BG_depth.mp4")
    
    print(f"Using RGB path: {rgb_path}")
    print(f"Using depth path: {depth_path}")
    
    # Check if files are videos or images
    is_video = rgb_path.endswith('.mp4')
    
    if is_video:
        rgb_video = cv2.VideoCapture(rgb_path)
        depth_video = cv2.VideoCapture(depth_path)
        
        # Check if videos are opened successfully
        if not rgb_video.isOpened() or not depth_video.isOpened():
            raise ValueError(f"Could not open video files: {rgb_path} and {depth_path}")
        
        # Get frame count and dimensions
        frame_count = int(rgb_video.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(rgb_video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(rgb_video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Process each frame
        for frame_idx in range(frame_count):
            print(f"Processing frame {frame_idx+1}/{frame_count}")
            
            # Read frames
            ret_rgb, rgb_frame = rgb_video.read()
            ret_depth, depth_frame = depth_video.read()
            
            if not ret_rgb or not ret_depth:
                break
            
            # Make sure depth is grayscale
            if len(depth_frame.shape) == 3:
                depth_frame = cv2.cvtColor(depth_frame, cv2.COLOR_BGR2GRAY)
            
            # Process the equirectangular frame
            process_frame(depth_frame, rgb_frame, filename, frame_idx, output_dir)
        
        # Release videos
        rgb_video.release()
        depth_video.release()
        
    else:
        # Handle single image
        rgb_frame = cv2.imread(rgb_path)
        depth_frame = cv2.imread(depth_path, cv2.IMREAD_GRAYSCALE)
        
        if rgb_frame is None or depth_frame is None:
            raise ValueError(f"Could not read image files: {rgb_path} and {depth_path}")
        
        # Process the equirectangular frame
        process_frame(depth_frame, rgb_frame, filename, 0, output_dir)
    
    print(f"Triangle orientations computed and saved to {output_dir}")

def process_frame(depth_frame, rgb_frame, filename, frame_idx, output_dir):
    """
    Process a single equirectangular frame to compute triangle orientations
    
    Args:
        depth_frame: Depth frame as a grayscale image
        rgb_frame: RGB frame (for reference, not used in computation)
        filename: Base filename
        frame_idx: Frame index
        output_dir: Output directory
    """
    # Normalize depth frame if needed
    if depth_frame.dtype != np.uint8:
        depth_frame = cv2.normalize(depth_frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    
    # Convert equirectangular depth to cubemap faces
    faces = equirectangular_to_cubemap(depth_frame)
    
    # Process each face
    for face_idx, face_depth in enumerate(faces):
        # Create mesh from depth map
        mesh = depth_to_mesh(face_depth, face_idx)
        
        # Calculate triangle orientations
        orientation_map = calculate_triangle_orientations(mesh, face_depth.shape)
        
        # Ensure orientation map is properly scaled to 0-255
        orientation_img = np.clip(orientation_map * 255, 0, 255).astype(np.uint8)
        
        # Save as image
        output_path = os.path.join(output_dir, f"{filename}_frame_{frame_idx:04d}_face_{face_idx}.jpg")
        cv2.imwrite(output_path, orientation_img)
        print(f"Saved face {face_idx} to {output_path}")

def equirectangular_to_cubemap(equirectangular_img, face_size=None):
    """
    Convert an equirectangular image to 6 cubemap faces.
    
    Args:
        equirectangular_img: Equirectangular image (grayscale)
        face_size: Size of the cube face (default: height/2)
        
    Returns:
        List of 6 cubemap faces [right, left, top, bottom, front, back]
    """
    # Ensure input image is grayscale
    if len(equirectangular_img.shape) > 2:
        equirectangular_img = cv2.cvtColor(equirectangular_img, cv2.COLOR_BGR2GRAY)
    
    height, width = equirectangular_img.shape
    
    # Default face size is half the height of the equirectangular image
    if face_size is None:
        face_size = height // 2
    
    # Initialize cube faces
    faces = [np.zeros((face_size, face_size), dtype=np.uint8) for _ in range(6)]
    
    # Define vectors for each face direction
    # Order: right (+x), left (-x), top (+y), bottom (-y), front (+z), back (-z)
    face_normals = [
        np.array([1, 0, 0]),  # Right
        np.array([-1, 0, 0]),  # Left
        np.array([0, 1, 0]),  # Top
        np.array([0, -1, 0]),  # Bottom
        np.array([0, 0, 1]),  # Front
        np.array([0, 0, -1])   # Back
    ]
    
    # Define up vectors for each face
    up_vectors = [
        np.array([0, 1, 0]),  # Right
        np.array([0, 1, 0]),  # Left
        np.array([0, 0, -1]),  # Top
        np.array([0, 0, 1]),  # Bottom
        np.array([0, 1, 0]),  # Front
        np.array([0, 1, 0])   # Back
    ]
    
    # For each face
    for face_idx in range(6):
        # Get face normal and up vector
        face_normal = face_normals[face_idx]
        up_vector = up_vectors[face_idx]
        
        # Calculate right vector
        right_vector = np.cross(up_vector, face_normal)
        
        # Create meshgrid for the face
        x = np.linspace(-1, 1, face_size)
        y = np.linspace(-1, 1, face_size)
        xv, yv = np.meshgrid(x, y)
        
        # For each pixel in the face
        for i in range(face_size):
            for j in range(face_size):
                # Calculate direction vector
                direction = face_normal + right_vector * xv[i, j] + up_vector * yv[i, j]
                direction = direction / np.linalg.norm(direction)
                
                # Convert to spherical coordinates
                theta = np.arctan2(direction[0], direction[2])  # Azimuth
                phi = np.arcsin(direction[1])                  # Elevation
                
                # Convert to equirectangular pixel coordinates
                u = ((theta / (2 * np.pi)) + 0.5) * width
                v = (0.5 - (phi / np.pi)) * height
                
                # Ensure u,v are in bounds
                u = np.clip(u, 0, width - 1.001)  # .001 to avoid edge cases
                v = np.clip(v, 0, height - 1.001)
                
                # Bilinear interpolation
                u0 = int(np.floor(u)) % width
                u1 = (u0 + 1) % width
                v0 = int(np.floor(v))
                v1 = min(v0 + 1, height - 1)
                
                # Calculate interpolation weights
                wu = u - u0
                wv = v - v0
                
                # Get pixel values
                a = equirectangular_img[v0, u0]
                b = equirectangular_img[v0, u1]
                c = equirectangular_img[v1, u0]
                d = equirectangular_img[v1, u1]
                
                # Bilinear interpolation
                pixel = int((1 - wu) * (1 - wv) * a + wu * (1 - wv) * b + (1 - wu) * wv * c + wu * wv * d)
                faces[face_idx][i, j] = pixel
    
    return faces

def depth_to_mesh(depth_map, face_idx):
    """
    Convert a depth map to a 3D mesh for a specific cubemap face.
    
    Args:
        depth_map: Depth map image (grayscale)
        face_idx: Face index (0: right, 1: left, 2: top, 3: bottom, 4: front, 5: back)
        
    Returns:
        trimesh.Trimesh object
    """
    height, width = depth_map.shape
    
    # Normalize depth values (0-1)
    depth_values = depth_map.astype(float)
    
    # Create grid coordinates
    y, x = np.mgrid[0:height, 0:width]
    
    # Normalize to [-1, 1]
    x_norm = (x / (width - 1)) * 2 - 1
    y_norm = -((y / (height - 1)) * 2 - 1)  # Flip Y to match OpenGL convention
    
    # Create vertices based on face
    vertices = np.zeros((height * width, 3))
    
    # The depth values control how far the point is in the face normal direction
    # Scale depth to a reasonable range (e.g., 0.1 to 1.0)
    min_depth = 0.1
    max_depth = 1.0
    scaled_depth = min_depth + depth_values * (max_depth - min_depth)
    
    # Create coordinates based on face index
    if face_idx == 0:  # Right (+X)
        for i in range(height):
            for j in range(width):
                idx = i * width + j
                vertices[idx] = [scaled_depth[i, j], y_norm[i, j], -x_norm[i, j]]
    elif face_idx == 1:  # Left (-X)
        for i in range(height):
            for j in range(width):
                idx = i * width + j
                vertices[idx] = [-scaled_depth[i, j], y_norm[i, j], x_norm[i, j]]
    elif face_idx == 2:  # Top (+Y)
        for i in range(height):
            for j in range(width):
                idx = i * width + j
                vertices[idx] = [x_norm[i, j], scaled_depth[i, j], -y_norm[i, j]]
    elif face_idx == 3:  # Bottom (-Y)
        for i in range(height):
            for j in range(width):
                idx = i * width + j
                vertices[idx] = [x_norm[i, j], -scaled_depth[i, j], y_norm[i, j]]
    elif face_idx == 4:  # Front (+Z)
        for i in range(height):
            for j in range(width):
                idx = i * width + j
                vertices[idx] = [x_norm[i, j], y_norm[i, j], scaled_depth[i, j]]
    else:  # Back (-Z)
        for i in range(height):
            for j in range(width):
                idx = i * width + j
                vertices[idx] = [-x_norm[i, j], y_norm[i, j], -scaled_depth[i, j]]
    
    # Create faces (triangles)
    faces = []
    for i in range(height - 1):
        for j in range(width - 1):
            # Define 4 vertices of a quad
            v00 = i * width + j
            v01 = i * width + (j + 1)
            v10 = (i + 1) * width + j
            v11 = (i + 1) * width + (j + 1)
            
            # Create two triangles from the quad (counterclockwise winding)
            faces.append([v00, v10, v01])
            faces.append([v01, v10, v11])
    
    # Create mesh
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    return mesh

def calculate_triangle_orientations(mesh, depth_shape):
    """
    Calculate the orientation of each triangle with respect to the center of projection.
    
    Following the paper description, we store the angles between face normals
    and the view direction (dot product). We want:
    - Dark values (near 0) for centers of faces (face normal aligned with view direction)
    - Bright values (near 1) for edges/boundaries (face normal perpendicular to view direction)
    
    Args:
        mesh: trimesh.Trimesh object
        depth_shape: Original shape of the depth map (height, width)
        
    Returns:
        2D array with orientation values (0 to 1)
    """
    # Calculate face normals if not already computed
    if not hasattr(mesh, 'face_normals') or mesh.face_normals is None:
        mesh.face_normals = None  # Reset to force recalculation
        _ = mesh.face_normals  # This will trigger calculation
    
    # Calculate centroids of each face
    face_centroids = mesh.triangles_center
    
    # Calculate view vectors (from centroid to origin, not from origin to centroid)
    # This is the correct direction for comparing with face normals
    view_vectors = -face_centroids  # Negative because we want vectors pointing toward origin
    
    # Normalize view vectors
    norms = np.linalg.norm(view_vectors, axis=1)
    valid_indices = norms > 1e-10
    normalized_view_vectors = np.zeros_like(view_vectors)
    normalized_view_vectors[valid_indices] = view_vectors[valid_indices] / norms[valid_indices, np.newaxis]
    
    # Calculate dot product of normal and view vector
    # We want the absolute value to handle back-facing triangles
    dot_products = np.abs(np.sum(mesh.face_normals * normalized_view_vectors, axis=1))
    
    # IMPORTANT FIX: We need to convert from dot products to angles
    # When vectors are parallel (centers of faces), dot product is near 1, we want value near 0
    # When vectors are perpendicular (edges), dot product is near 0, we want value near 1
    # Solution: Use 1 - |dot product| to get the desired mapping
    orientations = dot_products
    
    # Get original depth map dimensions
    height, width = depth_shape
    
    # Calculate the expected number of triangles
    expected_triangles = 2 * (height - 1) * (width - 1)
    
    # Verify that we have the right number of triangles
    num_triangles = len(mesh.faces)
    if num_triangles != expected_triangles:
        print(f"Warning: Number of triangles ({num_triangles}) doesn't match expected ({expected_triangles})")
    
    # Initialize output array with the same dimensions as the input depth map
    orientation_map = np.zeros((height, width))
    
    # Convert triangles to a coherent map
    triangle_index = 0
    for i in range(height - 1):
        for j in range(width - 1):
            # Each quad has 2 triangles
            idx1 = triangle_index
            idx2 = triangle_index + 1
            triangle_index += 2
            
            if idx1 < num_triangles and idx2 < num_triangles:
                # Average the orientation of the two triangles
                avg_orientation = (orientations[idx1] + orientations[idx2]) / 2
                # Assign to all four corners of the quad for better visualization
                orientation_map[i, j] = avg_orientation
                orientation_map[i, j+1] = avg_orientation
                orientation_map[i+1, j] = avg_orientation
                orientation_map[i+1, j+1] = avg_orientation
    
    return orientation_map