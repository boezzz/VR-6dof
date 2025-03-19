import os
import cv2
import numpy as np
from scipy import ndimage
from cubic2equi import cubic2equi

def compute_transparency_values(folder, filename_in):
    """
    Compute transparency values from triangle orientations and save as a viewable video.
    Following the paper:
    - Areas with orientations near 0 (black in orientation maps) represent surfaces parallel to view direction
    - Areas with orientations near 1 (white in orientation maps) represent potential disocclusion boundaries
    - We want to make potential disocclusion boundaries more transparent
    
    Args:
        folder: Path to the triangle orientations folder
        filename_in: Base name of the input file
    """
    # Get all jpg files in the folder
    files = [f for f in os.listdir(folder) if f.endswith('.jpg')]
    num_frames = len(files) // 6
    
    print(f"Found {len(files)} jpg files in folder, processing {num_frames} frames")
    
    # Create output video file path
    output_path = os.path.join(folder, f"{filename_in}_alphaproc.mp4")
    print(f"Will create video at: {output_path}")
    
    # Initialize VideoWriter with H.264 codec (more compatible)
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    
    # Process the first frame to determine dimensions
    print("Processing first frame to determine dimensions")
    
    # Process frame 0
    equi_orientation = process_frame_orientations(folder, filename_in, 0)
    
    # Get dimensions of the equirectangular output
    height, width = equi_orientation.shape[:2]
    print(f"Equirectangular output dimensions: {width}x{height}")
    
    # Initialize video writer
    alpha_video = cv2.VideoWriter(output_path, fourcc, 30, (width, height))
    
    # Process and write the first frame
    alpha_frame = process_alpha_map(equi_orientation)
    alpha_video.write(alpha_frame)
    
    # Process remaining frames
    for f in range(1, num_frames):
        print(f"Processing frame {f}/{num_frames-1}")
        
        # Process frame
        equi_orientation = process_frame_orientations(folder, filename_in, f)
        
        # Create alpha map
        alpha_frame = process_alpha_map(equi_orientation)
        
        # Write frame
        alpha_video.write(alpha_frame)
    
    # Release video writer
    alpha_video.release()
    print(f"Finished processing. Video saved to {output_path}")
    
    # Check if output file was created and has content
    if os.path.exists(output_path):
        print(f"Output file exists: {output_path}")
        print(f"Output file size: {os.path.getsize(output_path)} bytes")
    else:
        print(f"Output file does not exist: {output_path}")

def process_frame_orientations(folder, filename, frame_idx):
    """
    Process a single frame by reading and combining all 6 cube faces.
    
    Args:
        folder: Path to the folder containing orientation maps
        filename: Base filename
        frame_idx: Frame index
    
    Returns:
        Equirectangular orientation map
    """
    bname = os.path.join(folder, f"{filename}_frame_{frame_idx:04d}")
    
    # Check if files exist
    face_files = [f"{bname}_face_{i}.jpg" for i in range(6)]
    for face_file in face_files:
        if not os.path.exists(face_file):
            print(f"WARNING: File does not exist: {face_file}")
    
    # Load and prepare cube faces
    try:
        # Load and rotate faces according to equirectangular projection requirements
        bottom = cv2.rotate(cv2.imread(f"{bname}_face_3.jpg", cv2.IMREAD_GRAYSCALE), cv2.ROTATE_90_CLOCKWISE)
        top = cv2.rotate(cv2.imread(f"{bname}_face_2.jpg", cv2.IMREAD_GRAYSCALE), cv2.ROTATE_90_COUNTERCLOCKWISE)
        left = cv2.imread(f"{bname}_face_1.jpg", cv2.IMREAD_GRAYSCALE)
        back = cv2.imread(f"{bname}_face_5.jpg", cv2.IMREAD_GRAYSCALE)
        right = cv2.imread(f"{bname}_face_0.jpg", cv2.IMREAD_GRAYSCALE)
        front = cv2.imread(f"{bname}_face_4.jpg", cv2.IMREAD_GRAYSCALE)
        
        # Convert to 3-channel for cubic2equi function
        bottom3 = cv2.cvtColor(bottom, cv2.COLOR_GRAY2BGR)
        top3 = cv2.cvtColor(top, cv2.COLOR_GRAY2BGR)
        left3 = cv2.cvtColor(left, cv2.COLOR_GRAY2BGR)
        back3 = cv2.cvtColor(back, cv2.COLOR_GRAY2BGR)
        right3 = cv2.cvtColor(right, cv2.COLOR_GRAY2BGR)
        front3 = cv2.cvtColor(front, cv2.COLOR_GRAY2BGR)
        
        # Convert to equirectangular projection
        out = cubic2equi(top3, bottom3, left3, right3, front3, back3)
        
        # Extract grayscale channel and flip vertically if needed
        out_gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        
        # Resize to standard dimensions (2048x1024)
        out_resized = cv2.resize(out_gray, (2048, 1024))
        
        return out_resized
        
    except Exception as e:
        print(f"Error processing frame orientations: {e}")
        # Return a blank image as fallback
        return np.zeros((1024, 2048), dtype=np.uint8)

def process_alpha_map(orientation_map):
    """
    Process an orientation map to create an alpha (transparency) map.
    
    The orientation map now has:
    - Dark values (near 0) for centers of faces (face normal aligned with view direction)
    - Bright values (near 1) for edges/boundaries (face normal perpendicular to view direction)
    
    We want to make edges/boundaries more transparent in the final alpha map.
    
    Args:
        orientation_map: The orientation map (grayscale)
        
    Returns:
        BGR image with alpha values
    """
    # Normalize to 0-1
    input_map = orientation_map.astype(np.float32) / 255.0
    
    # The orientation map now correctly represents the angle between face normals and view direction
    # - Values close to 1 (bright) = face normal parallel to view direction (center of faces)
    # - Values close to 0 (dark) = face normal perpendicular to view direction (edges/boundaries)
    
    # 1. First, we need to enhance edges (dark areas in the orientation map)
    # We'll invert the map to focus on edges (make them bright)
    inverted = 1.0 - input_map
    
    # 2. Closing operation: erode then dilate
    # Create a disk-shaped structuring element (equivalent to MATLAB's strel('disk',2))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    
    # Erode the inverted image (equivalent to MATLAB's imerode(imcomplement(out), se))
    eroded = cv2.erode(inverted, kernel)
    
    # Dilate the eroded image (equivalent to MATLAB's imdilate(aa, se))
    dilated = cv2.dilate(eroded, kernel)
    
    # 3. Thresholding (bb.*double(bb>0.8) in MATLAB)
    threshold = 0.8
    thresholded = dilated * (dilated > threshold)
    
    # 4. Gaussian blur (imgaussfilt(cc,11,'FilterSize',7) in MATLAB)
    # FilterSize=7 is the kernel size, sigma=11 is the standard deviation
    smoothed = cv2.GaussianBlur(thresholded, (7, 7), 11)
    
    # Apply logistic function to create a smooth transition
    c = 0.5  # midpoint
    k = 8.0  # steepness
    sigmoid = 1.0 / (1.0 + np.exp(-k * (smoothed - c)))
    
    # Clean up very small values and saturate high values
    sigmoid[sigmoid < 0.1] = 0
    sigmoid[sigmoid > 0.8] = 1
    
    # Invert values: 
    # 1 (white) = fully opaque
    # 0 (black) = fully transparent
    alpha_map = 1.0 - sigmoid
    
    # Create a 3-channel BGR image
    alpha_bgr = np.stack([alpha_map, alpha_map, alpha_map], axis=2) * 255
    
    return alpha_bgr.astype(np.uint8)