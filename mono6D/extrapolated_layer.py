import os
import numpy as np
import cv2

def create_extrapolated_layer(filename):
    """
    Create the extrapolated layer from the RGB and depth videos.
    
    Args:
        filename: Base name of the video file
    """
    in_path = "_input_videos"
    out_path = f"_extrapolated_layer/{filename}"
    os.makedirs(out_path, exist_ok=True)
    
    # Read RGB and Depth videos
    rgb_path = os.path.join(in_path, f"{filename}.mp4")
    depth_path = os.path.join(f"_improved_depth/{filename}/videos", f"{filename}_depth.mp4")
    
    fg_rgb_vid = cv2.VideoCapture(rgb_path)
    fg_depth_vid = cv2.VideoCapture(depth_path)
    
    if not fg_rgb_vid.isOpened() or not fg_depth_vid.isOpened():
        raise ValueError(f"Could not open video files: {rgb_path} and {depth_path}")
    
    # Get frame for size reference
    ret_rgb, rgb_tex = fg_rgb_vid.read()
    ret_depth, d_tex = fg_depth_vid.read()
    
    if not ret_rgb or not ret_depth:
        raise ValueError("Could not read frames from videos")
    
    height, width = rgb_tex.shape[:2]
    
    # Determine total frames and sample frames
    total_frames_rgb = int(fg_rgb_vid.get(cv2.CAP_PROP_FRAME_COUNT))
    total_frames_depth = int(fg_depth_vid.get(cv2.CAP_PROP_FRAME_COUNT))
    total_frames = min(total_frames_rgb, total_frames_depth)
    n_frames = min(300, total_frames)  # Sample up to 300 frames
    frame_samples = np.round(np.linspace(0, total_frames - 1, n_frames)).astype(int)
    
    # Initialize storage arrays
    depth_block = np.zeros((height, width, n_frames), dtype=np.float32)
    rgb_block_r = np.zeros((height, width, n_frames), dtype=np.float32)
    rgb_block_g = np.zeros((height, width, n_frames), dtype=np.float32)
    rgb_block_b = np.zeros((height, width, n_frames), dtype=np.float32)
    
    # Read and store frames
    for idx, frame_no in enumerate(frame_samples):
        fg_rgb_vid.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        fg_depth_vid.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        
        ret_rgb, rgb_tex = fg_rgb_vid.read()
        ret_depth, d_tex = fg_depth_vid.read()
        
        if not ret_rgb or not ret_depth:
            continue
        
        rgb_tex = rgb_tex.astype(np.float32) / 255.0  # Normalize to [0,1]
        d_tex = d_tex.astype(np.float32) / 255.0
        
        rgb_block_r[:, :, idx] = rgb_tex[:, :, 0]
        rgb_block_g[:, :, idx] = rgb_tex[:, :, 1]
        rgb_block_b[:, :, idx] = rgb_tex[:, :, 2]
        depth_block[:, :, idx] = d_tex[:, :, 0]
    
    # Compute robust median of the min depth values
    sorted_depth = np.sort(depth_block, axis=2)
    depth_out = np.median(sorted_depth[:, :, :15], axis=2)
    
    # Compute color based on sorted depth indices
    color_out = np.zeros((height, width, 3), dtype=np.float32)
    color_out[:, :, 0] = np.median(np.take_along_axis(rgb_block_r, np.argsort(depth_block, axis=2)[:, :, :15], axis=2), axis=2)
    color_out[:, :, 1] = np.median(np.take_along_axis(rgb_block_g, np.argsort(depth_block, axis=2)[:, :, :15], axis=2), axis=2)
    color_out[:, :, 2] = np.median(np.take_along_axis(rgb_block_b, np.argsort(depth_block, axis=2)[:, :, :15], axis=2), axis=2)
    
    # Save images
    cv2.imwrite(os.path.join(out_path, f"{filename}_BG.png"), (color_out * 255).astype(np.uint8))
    cv2.imwrite(os.path.join(out_path, f"{filename}_BG_depth.png"), (depth_out * 255).astype(np.uint8))
    
    print(f"Extrapolated layer created successfully for {filename}.")
