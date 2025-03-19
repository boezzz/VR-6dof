import numpy as np
import cv2

def cubic2equi(top, bottom, left, right, front, back):
    """
    Convert cubemap images to equirectangular projection.
    
    Args:
        top, bottom, left, right, front, back: Face images from a cubemap
        
    Returns:
        Equirectangular projected image
    """
    # Ensure all faces have the same dimensions
    assert top.shape == bottom.shape == left.shape == right.shape == front.shape == back.shape
    
    # Get the face size
    face_size = top.shape[0]
    
    # Create output equirectangular image (2:1 aspect ratio)
    equi_height = face_size
    equi_width = 2 * face_size
    
    # Add channel dimension if grayscale
    if len(top.shape) == 2:
        channels = 1
        equi = np.zeros((equi_height, equi_width, 1), dtype=np.uint8)
    else:
        channels = top.shape[2]
        equi = np.zeros((equi_height, equi_width, channels), dtype=np.uint8)
    
    # Create meshgrid for equirectangular coordinates
    x = np.linspace(0, 2*np.pi, equi_width)
    y = np.linspace(-np.pi/2, np.pi/2, equi_height)
    xv, yv = np.meshgrid(x, y)
    
    # Convert to Cartesian coordinates
    x = np.cos(yv) * np.cos(xv)
    y = np.sin(yv)
    z = np.cos(yv) * np.sin(xv)
    
    # Determine which face to use for each pixel
    abs_x, abs_y, abs_z = np.abs(x), np.abs(y), np.abs(z)
    max_xyz = np.maximum(np.maximum(abs_x, abs_y), abs_z)
    
    # Calculate normalized coordinates for each face
    u = np.zeros_like(x)
    v = np.zeros_like(y)
    
    # Process front face (+z)
    mask = (z == max_xyz)
    u[mask] = -x[mask] / z[mask]
    v[mask] = -y[mask] / z[mask]
    u[mask] = (u[mask] + 1) * 0.5 * (face_size - 1)
    v[mask] = (v[mask] + 1) * 0.5 * (face_size - 1)
    for c in range(channels):
        equi[mask, c] = front[v[mask].astype(np.int32), u[mask].astype(np.int32)] if channels == 1 else front[v[mask].astype(np.int32), u[mask].astype(np.int32), c]
    
    # Process back face (-z)
    mask = (-z == max_xyz)
    u[mask] = x[mask] / (-z[mask])
    v[mask] = -y[mask] / (-z[mask])
    u[mask] = (u[mask] + 1) * 0.5 * (face_size - 1)
    v[mask] = (v[mask] + 1) * 0.5 * (face_size - 1)
    for c in range(channels):
        equi[mask, c] = back[v[mask].astype(np.int32), u[mask].astype(np.int32)] if channels == 1 else back[v[mask].astype(np.int32), u[mask].astype(np.int32), c]
    
    # Process left face (-x)
    mask = (-x == max_xyz)
    u[mask] = z[mask] / (-x[mask])
    v[mask] = -y[mask] / (-x[mask])
    u[mask] = (u[mask] + 1) * 0.5 * (face_size - 1)
    v[mask] = (v[mask] + 1) * 0.5 * (face_size - 1)
    for c in range(channels):
        equi[mask, c] = left[v[mask].astype(np.int32), u[mask].astype(np.int32)] if channels == 1 else left[v[mask].astype(np.int32), u[mask].astype(np.int32), c]
    
    # Process right face (+x)
    mask = (x == max_xyz)
    u[mask] = -z[mask] / x[mask]
    v[mask] = -y[mask] / x[mask]
    u[mask] = (u[mask] + 1) * 0.5 * (face_size - 1)
    v[mask] = (v[mask] + 1) * 0.5 * (face_size - 1)
    for c in range(channels):
        equi[mask, c] = right[v[mask].astype(np.int32), u[mask].astype(np.int32)] if channels == 1 else right[v[mask].astype(np.int32), u[mask].astype(np.int32), c]
    
    # Process top face (+y)
    mask = (y == max_xyz)
    u[mask] = -x[mask] / y[mask]
    v[mask] = -z[mask] / y[mask]
    u[mask] = (u[mask] + 1) * 0.5 * (face_size - 1)
    v[mask] = (v[mask] + 1) * 0.5 * (face_size - 1)
    for c in range(channels):
        equi[mask, c] = top[v[mask].astype(np.int32), u[mask].astype(np.int32)] if channels == 1 else top[v[mask].astype(np.int32), u[mask].astype(np.int32), c]
    
    # Process bottom face (-y)
    mask = (-y == max_xyz)
    u[mask] = -x[mask] / (-y[mask])
    v[mask] = z[mask] / (-y[mask])
    u[mask] = (u[mask] + 1) * 0.5 * (face_size - 1)
    v[mask] = (v[mask] + 1) * 0.5 * (face_size - 1)
    for c in range(channels):
        equi[mask, c] = bottom[v[mask].astype(np.int32), u[mask].astype(np.int32)] if channels == 1 else bottom[v[mask].astype(np.int32), u[mask].astype(np.int32), c]
    
    return equi