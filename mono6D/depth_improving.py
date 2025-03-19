import os
import numpy as np
import cv2
from scipy.ndimage import median_filter
from scipy.sparse import diags
from scipy.sparse.linalg import bicgstab, cg

# Add necessary paths
import sys
sys.path.append(os.path.join(os.getcwd(), 'optical_flow'))
sys.path.append(os.path.join(os.getcwd(), 'bgu_matlab'))

# Liu's optical flow parameters
alpha = 0.012
ratio = 1
minWidth = 20
nOuterFPIterations = 7
nInnerFPIterations = 1
nSORIterations = 30
para = [alpha, ratio, minWidth, nOuterFPIterations, nInnerFPIterations, nSORIterations]

# Parameter Setting
texture_path = '_input_videos/'
depth_path = '_input_videos/'

upscale_size = (2048, 1024)  # Note: Python uses (width, height) whereas MATLAB uses (height, width)
downscale_size = (int(upscale_size[0] * 0.8), int(upscale_size[1] * 0.8))

# Parameters
params = {
    'lambda_data': 4e-2,  # data
    'lambda2': 1,  # edge
    'gamma': 1e-2,  # temporal
    'smoothness': 1e-2,  # smoothness
    'smweight_windowsize': 3,
    'scale_factor_smoothness': 1e+3,
    'tol': 1e-6,
    'maxiter': 30,
    'solver': 'bicgstab',
    'pad_size': 65,  # padding size
    'upscale_size': upscale_size,
    'downscale_size': downscale_size,
    'bilateral_sigma': 2,
    'svweight_patchsize': 7,
    'scale_factor': 1e+5,
    'video_duration': 20,
    'upsampling': 'bilinear',
    'starting_point_in_sec': 0,
    'left_right': 'none',
    'weight_type': 'tukey',
    'wrs_window_size': 3,
    'extended_filename': '1'
}

min_meter_in_depth = 0.3

def clip01(img):
    """Clip image values to [0, 1] range"""
    return np.clip(img, 0, 1)

def imcut(img, left_right):
    """Cut image based on left_right parameter"""
    if left_right == 'left':
        return img[:, :img.shape[1]//2, :]
    elif left_right == 'right':
        return img[:, img.shape[1]//2:, :]
    else:
        return img

def detect_edges(img):
    """Edge detection function"""
    # Simplified edge detection using Sobel operator
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img.astype(np.float32), cv2.COLOR_RGB2GRAY)
    else:
        gray = img.astype(np.float32)
    
    # Fallback to Sobel operator
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    
    # Compute gradient magnitude
    edges = np.sqrt(sobelx**2 + sobely**2)
    
    # Apply Gaussian blur to reduce noise
    edges = cv2.GaussianBlur(edges, (3, 3), 0)
    
    # Enhance edges with histogram equalization
    edges = cv2.equalizeHist((edges * 255).astype(np.uint8)).astype(np.float32) / 255.0
    
    # Normalize to [0, 1]
    edges = (edges - edges.min()) / (edges.max() - edges.min() + 1e-10)
    
    return edges

def compute_depth_weight(depth, params):
    """Compute spatially-varying weight for the depth data"""
    # Simplified implementation - edge-aware weighting
    if len(depth.shape) == 3:
        depth_gray = cv2.cvtColor(depth.astype(np.float32), cv2.COLOR_RGB2GRAY)
    else:
        depth_gray = depth.astype(np.float32)
    
    # Compute depth gradients
    grad_x = cv2.Sobel(depth_gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(depth_gray, cv2.CV_32F, 0, 1, ksize=3)
    
    # Compute gradient magnitude
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)
    
    # Map gradient magnitude to weights (higher gradient = lower weight)
    weights = np.exp(-grad_mag * 5.0)
    
    return weights

def vectorize_any(img):
    """Flatten the array"""
    return img.flatten()

def weight_compute(edge_map, window_size, weight_type):
    """Compute edge-aware weights"""
    if weight_type == 'tukey':
        # Tukey's biweight function with appropriate scaling
        c = 4.685  # Tunable parameter
        weights = np.ones_like(edge_map)
        mask = edge_map <= c
        tmp = (1 - (edge_map/c)**2)
        weights[mask] = tmp[mask]**2
    else:
        # Exponential weighting as fallback
        sigma = 0.1
        weights = np.exp(-edge_map / sigma)
    
    # Apply local window averaging for smoothness
    if window_size > 1:
        kernel = np.ones((window_size, window_size)) / (window_size * window_size)
        weights = cv2.filter2D(weights, -1, kernel)
    
    return weights

def eight_neighbour_extract(weights):
    """Extract 8-neighborhood weights as a structured dictionary"""
    # Horizontal neighbors (east-west)
    w_e = np.roll(weights, -1, axis=1)
    w_w = np.roll(weights, 1, axis=1)
    
    # Vertical neighbors (north-south)
    w_n = np.roll(weights, 1, axis=0)
    w_s = np.roll(weights, -1, axis=0)
    
    # Diagonal neighbors
    w_ne = np.roll(np.roll(weights, -1, axis=1), 1, axis=0)
    w_nw = np.roll(np.roll(weights, 1, axis=1), 1, axis=0)
    w_se = np.roll(np.roll(weights, -1, axis=1), -1, axis=0)
    w_sw = np.roll(np.roll(weights, 1, axis=1), -1, axis=0)
    
    return {
        'center': weights,
        'east': w_e,
        'west': w_w,
        'north': w_n,
        'south': w_s,
        'northeast': w_ne,
        'northwest': w_nw,
        'southeast': w_se,
        'southwest': w_sw
    }

def compute_smoothness_weight(depth, params):
    """Compute smoothness weights based on depth"""
    if len(depth.shape) == 3:
        depth_gray = cv2.cvtColor(depth.astype(np.float32), cv2.COLOR_RGB2GRAY)
    else:
        depth_gray = depth.astype(np.float32)
    
    # Compute depth gradients
    grad_x = cv2.Sobel(depth_gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(depth_gray, cv2.CV_32F, 0, 1, ksize=3)
    
    # Compute gradient magnitude
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)
    
    # Scale by factor from params
    scaled_grad = grad_mag * params['scale_factor_smoothness']
    
    # Convert to weights (higher gradient = lower weight)
    weights = np.exp(-scaled_grad)
    
    return weights

def create_laplacian_matrix(weights, height, width):
    """Create a Laplacian matrix for the optimization problem"""
    n = height * width
    
    # Diagonal elements
    diag_vals = np.ones(n) * 8  # 8 neighbors
    
    # Off-diagonal elements for each direction
    offsets = [
        -width,          # north
        -width + 1,      # northeast
        1,               # east
        width + 1,       # southeast
        width,           # south
        width - 1,       # southwest
        -1,              # west
        -width - 1       # northwest
    ]
    
    # Create sparse Laplacian matrix
    L = diags([diag_vals] + [-np.ones(n-abs(offset)) for offset in offsets],
              [0] + offsets, shape=(n, n), format='csr')
    
    return L

def optimize_objective(depth, weights, mask, params):
    """Optimize the objective function (non-temporal case)"""
    if len(depth.shape) == 3:
        depth_working = depth[:,:,0].copy()
    else:
        depth_working = depth.copy()
    
    height, width = depth_working.shape
    n = height * width
    
    # Flatten input arrays
    depth_flat = depth_working.flatten()
    
    # Data term weight
    lambda_data = np.ones(n) * params['lambda_data']
    
    # Create Laplacian matrix for smoothness term
    L = create_laplacian_matrix(weights['w_sm'], height, width)
    L = L * params['smoothness']
    
    # Build the system matrix A = (λI + L)
    I = diags([lambda_data], [0], shape=(n, n), format='csr')
    A = I + L
    
    # Right-hand side b = λd
    b = lambda_data * depth_flat
    
    # Solve the system Ax = b
    if params['solver'] == 'bicgstab':
        x, info = bicgstab(A, b, tol=params['tol'], maxiter=params['maxiter'])
    else:
        x, info = cg(A, b, tol=params['tol'], maxiter=params['maxiter'])
    
    if info != 0:
        print(f"Warning: solver did not converge, info={info}")
    
    # Reshape to 2D
    depth_optimized = x.reshape(height, width)
    
    return depth_optimized

def warp_with_flow(image, flow):
    """Warp an image using optical flow"""
    h, w = image.shape[:2]
    
    # Create meshgrid for coordinates
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    
    # Add flow to coordinates
    flow_x = flow[:,:,0]
    flow_y = flow[:,:,1]
    
    new_x = x + flow_x
    new_y = y + flow_y
    
    # Clip coordinates to image boundaries
    new_x = np.clip(new_x, 0, w-1)
    new_y = np.clip(new_y, 0, h-1)
    
    # Interpolate
    warped = cv2.remap(image, new_x, new_y, cv2.INTER_LINEAR)
    
    return warped

def optimize_objective_temporal(depth, weights, mask, flows, prev_depth, params):
    """Optimize the objective function with temporal consistency"""
    if len(depth.shape) == 3:
        depth_working = depth[:,:,0].copy()
    else:
        depth_working = depth.copy()
    
    if len(prev_depth.shape) == 3:
        prev_depth_working = prev_depth[:,:,0].copy()
    else:
        prev_depth_working = prev_depth.copy()
    
    # Warp previous depth to current frame using optical flow
    warped_prev_depth = warp_with_flow(prev_depth_working, flows)
    
    height, width = depth_working.shape
    n = height * width
    
    # Flatten arrays
    depth_flat = depth_working.flatten()
    prev_depth_flat = warped_prev_depth.flatten()
    
    # Data term weight
    lambda_data = np.ones(n) * params['lambda_data']
    
    # Temporal term weight
    gamma = np.ones(n) * params['gamma']
    
    # Create Laplacian matrix for smoothness term
    L = create_laplacian_matrix(weights['w_sm'], height, width)
    L = L * params['smoothness']
    
    # Build the system matrix A = (λI + γI + L)
    I = diags([lambda_data + gamma], [0], shape=(n, n), format='csr')
    A = I + L
    
    # Right-hand side b = λd + γd_prev
    b = lambda_data * depth_flat + gamma * prev_depth_flat
    
    # Solve the system Ax = b
    if params['solver'] == 'bicgstab':
        x, info = bicgstab(A, b, tol=params['tol'], maxiter=params['maxiter'])
    else:
        x, info = cg(A, b, tol=params['tol'], maxiter=params['maxiter'])
    
    if info != 0:
        print(f"Warning: solver did not converge, info={info}")
    
    # Reshape to 2D
    depth_optimized = x.reshape(height, width)
    
    return depth_optimized

def Coarse2FineTwoFrames(prev_img, curr_img, para):
    """Calculate optical flow between two frames"""
    # Convert inputs to grayscale if they're RGB
    if len(prev_img.shape) == 3:
        prev_gray = cv2.cvtColor(prev_img.astype(np.float32), cv2.COLOR_RGB2GRAY)
        curr_gray = cv2.cvtColor(curr_img.astype(np.float32), cv2.COLOR_RGB2GRAY)
    else:
        prev_gray = prev_img.squeeze().astype(np.float32)
        curr_gray = curr_img.squeeze().astype(np.float32)
    
    # Ensure values are in [0, 1] for optical flow
    prev_gray = np.clip(prev_gray, 0, 1)
    curr_gray = np.clip(curr_gray, 0, 1)
    
    # Convert to uint8 for OpenCV
    prev_gray_u8 = (prev_gray * 255).astype(np.uint8)
    curr_gray_u8 = (curr_gray * 255).astype(np.uint8)
    
    # Calculate flow using Farneback method
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray_u8, curr_gray_u8, None, 
        para[0], para[1], 15, 
        3, 5, 1.2, 0
    )
    
    # Return separate x and y components and the combined flow
    return flow[:,:,0], flow[:,:,1], flow

def bilateralFilter(img, guide, min_val, max_val, sigma):
    """Apply bilateral filtering using a guide image"""
    # Ensure inputs are in the right format
    img_float = img.astype(np.float32)
    guide_float = guide.astype(np.float32)
    
    # If guide is multi-channel but img is single-channel, convert guide to gray
    if len(guide_float.shape) == 3 and len(img_float.shape) == 2:
        guide_float = cv2.cvtColor(guide_float, cv2.COLOR_RGB2GRAY)
    
    # Apply joint bilateral filter
    filtered = cv2.ximgproc.jointBilateralFilter(img_float, guide_float, 9, sigma, sigma*2)
    
    return filtered

def flowToColor(flow):
    """Convert optical flow to color visualization"""
    # Calculate magnitude and angle
    mag, ang = cv2.cartToPolar(flow[:,:,0], flow[:,:,1])
    
    # Normalize magnitude to [0, 1]
    mag_max = np.max(mag) if np.max(mag) > 0 else 1.0
    mag_norm = np.clip(mag / mag_max, 0, 1)
    
    # Create HSV representation
    hsv = np.zeros((flow.shape[0], flow.shape[1], 3), dtype=np.float32)
    hsv[:,:,0] = ang * 180 / np.pi / 2  # Hue represents direction
    hsv[:,:,1] = np.ones_like(mag_norm)  # Full saturation
    hsv[:,:,2] = mag_norm  # Value represents magnitude
    
    # Convert to RGB
    bgr = cv2.cvtColor((hsv * 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    
    return rgb

def preserve_depth_format(original_depth, processed_depth):
    """Preserve the format of the original depth map in the processed output"""
    # Check if original depth is grayscale or color
    if len(original_depth.shape) == 2 or (len(original_depth.shape) == 3 and original_depth.shape[2] == 1):
        # Original is grayscale
        if len(processed_depth.shape) == 3 and processed_depth.shape[2] > 1:
            # Convert processed to grayscale
            return cv2.cvtColor(processed_depth, cv2.COLOR_BGR2GRAY)
        return processed_depth
    else:
        # Original is color
        if len(processed_depth.shape) == 2 or (len(processed_depth.shape) == 3 and processed_depth.shape[2] == 1):
            # Convert processed to color (using same colormap as original)
            if np.max(processed_depth) <= 1.0:
                processed_depth = (processed_depth * 255).astype(np.uint8)
            
            # Apply the same colormap as the original depth
            # This is an approximation - for exact matching you'd need the specific colormap used
            colored = cv2.applyColorMap(processed_depth, cv2.COLORMAP_JET)
            return colored
        return processed_depth

def improve_depth(filename):
    # Debug output path
    debugpath = f'_improved_depth/{filename}/'
    flowpath = os.path.join(debugpath, 'flow/')
    videopath = os.path.join(debugpath, 'videos/')
    edgepath = os.path.join(debugpath, 'edges/')
    w_smpath = os.path.join(debugpath, 'w_sm/')
    w_datapath = os.path.join(debugpath, 'w_data/')

    # Create directories if they don't exist
    for path in [debugpath, flowpath, videopath, edgepath, w_smpath, w_datapath]:
        os.makedirs(path, exist_ok=True)

    # Save parameters
    np.save(os.path.join(debugpath, 'params.npy'), params)

    # Open video files
    texture_video = cv2.VideoCapture(os.path.join(texture_path, f"{filename}.mp4"))
    depth_video = cv2.VideoCapture(os.path.join(depth_path, f"{filename}_depth.mp4"))
    
    if not texture_video.isOpened() or not depth_video.isOpened():
        print(f"Error: Could not open video files for {filename}")
        return
    
    # Get video properties
    fps = texture_video.get(cv2.CAP_PROP_FPS)
    total_num_frames = min(
        int(texture_video.get(cv2.CAP_PROP_FRAME_COUNT)),
        int(depth_video.get(cv2.CAP_PROP_FRAME_COUNT))
    ) - 1
    
    # Read the first frame of depth video to determine the format
    ret, first_depth_frame = depth_video.read()
    if not ret:
        print("Error reading first depth frame")
        return
    
    # Reset depth video to start
    depth_video.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    # Get frame dimensions for output videos
    width = int(upscale_size[0])
    height = int(upscale_size[1])
    
    # codec
    possible_codecs = [
        ('mp4v', '.mp4')
    ]
    
    tv_writer = None
    dv_writer = None
    
    for codec, ext in possible_codecs:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            
            texture_output_path = os.path.join(videopath, f"{filename}{ext}")
            depth_output_path = os.path.join(videopath, f"{filename}_depth{ext}")
            
            tv_writer = cv2.VideoWriter(
                texture_output_path, 
                fourcc, fps, upscale_size
            )
            
            dv_writer = cv2.VideoWriter(
                depth_output_path, 
                fourcc, fps, upscale_size
            )
            
            if tv_writer.isOpened() and dv_writer.isOpened():
                print(f"Successfully created video writers using codec: {codec}")
                break
            else:
                # Close failed writers and try next codec
                tv_writer.release()
                dv_writer.release()
                tv_writer = None
                dv_writer = None
        except Exception as e:
            print(f"Failed to create video writers with codec {codec}: {e}")
            continue
    
    if tv_writer is None or dv_writer is None:
        print("Warning: Could not create video writers with any codec.")
    
    num_frames = 1
    prev_depth_frame = None
    prev_img = None
    
    start_frame = int(fps * params['starting_point_in_sec'])
    end_frame = min(total_num_frames, int(start_frame + fps * params['video_duration']))
    
    # Skip to start frame
    if start_frame > 0:
        texture_video.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        depth_video.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    
    for t in range(start_frame, end_frame):
        print(f"\nProcessing depth for frame {t:05d} / {end_frame}")
        
        # Read frames
        ret, img = texture_video.read()
        ret_d, depth = depth_video.read()
        
        if not ret or not ret_d:
            print(f"Error reading frame {t}")
            break
                      
        # Convert to float and normalize
        img = img.astype(np.float32) / 255.0
        depth = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX)
        depth = np.uint8(depth)

        
        # Apply left/right cropping if needed
        img = imcut(img, params['left_right'])
        depth = imcut(depth, params['left_right'])
        
        origimg = img.copy()
        
        # Use only the first channel if depth is RGB
        if len(depth.shape) == 3 and depth.shape[2] > 1:
            # Use first channel for processing
            depth_processing = depth[:,:,0].copy()
        else:
            depth_processing = depth.copy()
        
        
        # Image padding to handle artifacts around boundaries
        pad_size = params['pad_size']
        # Circular padding in x-direction
        img_padded = np.pad(img, ((0, 0), (pad_size, pad_size), (0, 0)), mode='wrap')
        # Symmetric padding in y-direction
        img_padded = np.pad(img_padded, ((pad_size, pad_size), (0, 0), (0, 0)), mode='symmetric')
        origimg_pad = img_padded.copy()
        
        # Padding for depth
        if len(depth_processing.shape) == 2:
            # Circular padding in x-direction
            depth_padded = np.pad(depth_processing, ((0, 0), (pad_size, pad_size)), mode='wrap')
            # Symmetric padding in y-direction
            depth_padded = np.pad(depth_padded, ((pad_size, pad_size), (0, 0)), mode='symmetric')
        
        padarray_size = depth_padded.shape
        
        # Resize for processing
        img_resized = cv2.resize(img_padded, params['downscale_size'])
        depth_resized = cv2.resize(depth_padded, params['downscale_size'])
        
        # Edge detection
        edgemap_img = detect_edges(img_resized)
        
        # Prepare depth for edge detection if needed
        if len(depth_resized.shape) == 2:
            depth_3ch = np.stack([depth_resized] * 3, axis=2)
        else:
            depth_3ch = depth_resized
            
        depth_edges = detect_edges(depth_3ch)
        
        # Combine edge maps
        if len(edgemap_img.shape) == 2 and len(depth_edges.shape) == 2:
            edgemap = edgemap_img + depth_edges
        else:
            # Handle different dimensions
            if len(edgemap_img.shape) == 3 and len(depth_edges.shape) == 2:
                edgemap = edgemap_img[:,:,0] + depth_edges
            elif len(edgemap_img.shape) == 2 and len(depth_edges.shape) == 3:
                edgemap = edgemap_img + depth_edges[:,:,0]
            else:
                edgemap = edgemap_img[:,:,0] + depth_edges[:,:,0]
        
        # Normalize combined edge map
        edgemap = edgemap / (edgemap.max() + 1e-10)
        
        # Create mask (valid pixels)
        maskimg = np.ones_like(depth_resized)
        
        # Compute data weight
        weight_data = compute_depth_weight(depth_resized, params)
        
        # Apply median filter to weights
        weight_filtered = median_filter(weight_data, size=3)
        
        # Scale lambdas by the weight
        data_lambda = vectorize_any(weight_filtered) * params['lambda_data']
        
        # Compute edge-aware weights
        weights = {'w_rs': weight_compute(edgemap, params['wrs_window_size'], params['weight_type'])}
        
        # Compute smoothness weights
        if len(depth_resized.shape) == 2:
            weights['w_sm'] = eight_neighbour_extract(compute_smoothness_weight(depth_resized, params))
        else:
            weights['w_sm'] = eight_neighbour_extract(compute_smoothness_weight(depth_resized[:,:,0], params))
        
        # Save edge maps and weights for debugging
        cv2.imwrite(os.path.join(edgepath, f'edge_{num_frames:04d}.png'), (edgemap * 255).astype(np.uint8))
        cv2.imwrite(os.path.join(w_datapath, f'data_weight_{num_frames:04d}.png'), 
                   (weight_filtered * 255).astype(np.uint8))
        
        # Process differently if not the first frame
        if num_frames > 1 and prev_img is not None and prev_depth_frame is not None:
            # Flow estimation for temporal consistency
            vx, vy, flows = Coarse2FineTwoFrames(prev_img, img_resized, para)
            
            # Save flow visualization
            flow_color = flowToColor(flows)
            # cv2.imwrite(os.path.join(flowpath, f'flow_{num_frames:04d}.png'), (flow_color * 255).astype(np.uint8))
            
            # Depth cleaning with temporal consistency
            depth_propagated = optimize_objective_temporal(
                depth_resized, weights, maskimg, flows, prev_depth_frame, params
            )
        else:
            # Depth cleaning without temporal consistency for first frame
            depth_propagated = optimize_objective(depth_resized, weights, maskimg, params)
        
        # Save current frame data for next iteration
        prev_depth_frame = depth_propagated.copy()
        prev_img = img_resized.copy()
        
        # Resize back to original padded size
        if len(padarray_size) == 2:
            depth_propagated_resized = cv2.resize(depth_propagated, (padarray_size[1], padarray_size[0]))
        else:
            depth_propagated_resized = cv2.resize(depth_propagated, (padarray_size[1], padarray_size[0]))
        
        # Clip values to [0, 1]
        depth_propagated_resized = clip01(depth_propagated_resized)
        
        # Bilateral filtering for edge-aware smoothing
        if len(origimg_pad.shape) == 3:
            greyimg_pad = cv2.cvtColor(origimg_pad.astype(np.float32), cv2.COLOR_RGB2GRAY)
        else:
            greyimg_pad = origimg_pad.astype(np.float32)
            
        min_val = np.min(greyimg_pad)
        max_val = np.max(greyimg_pad)
        
        # Apply joint bilateral filter using the guide image
        try:
            depth_bilateral = bilateralFilter(
                depth_propagated_resized, greyimg_pad, min_val, max_val, params['bilateral_sigma']
            )
        except Exception as e:
            print(f"Error in bilateral filtering: {e}")
            depth_bilateral = depth_propagated_resized
        
        # Crop padding
        if len(depth_bilateral.shape) == 2:
            depth_bilateral = depth_bilateral[pad_size:padarray_size[0]-pad_size, 
                                             pad_size:padarray_size[1]-pad_size]
        else:
            depth_bilateral = depth_bilateral[pad_size:padarray_size[0]-pad_size, 
                                              pad_size:padarray_size[1]-pad_size]
        
        # Upsampling
        if params['upsampling'] == 'bilinear':
            depth_bilateral = cv2.resize(depth_bilateral, upscale_size)
        elif params['upsampling'] == 'bgu':
            # Fallback to bilinear if BGU is not implemented
            depth_bilateral = cv2.resize(depth_bilateral, upscale_size)
            print("BGU upsampling not implemented, using bilinear instead")
        
        # Write frames to video
        orig_resized = cv2.resize(origimg, upscale_size)
        
        # Convert floating point images to uint8 for video writing
        orig_resized_uint8 = (orig_resized * 255).astype(np.uint8)
        
        # Ensure depth represents only depth information (white = closer)
        # If depth is single channel, convert to 3-channel for video writing
        if len(depth_bilateral.shape) == 2:
            # Create a pure depth representation - single channel to 3-channel BGR
            # Keep the original depth convention (white = closer)
            depth_bilateral_uint8 = (depth_bilateral * 255).astype(np.uint8)
            # depth_bilateral_uint8 = cv2.cvtColor(depth_bilateral_uint8, cv2.COLOR_GRAY2BGR)
        else:
            # For multi-channel depth, use only first channel for actual depth
            # and make all channels the same to represent only depth
            # Preserve the original depth convention (white = closer)
            depth_channel = depth_bilateral[:,:,0]  # Use first channel as depth
            depth_bilateral_uint8 = np.stack([depth_channel, depth_channel, depth_channel], axis=2)
            depth_bilateral_uint8 = (depth_bilateral_uint8 * 255).astype(np.uint8)
        
        # Save frames - either to video or as images
        if tv_writer is not None and tv_writer.isOpened() and dv_writer is not None and dv_writer.isOpened():
            try:
                tv_writer.write(orig_resized_uint8)
                dv_writer.write(depth_bilateral_uint8)
            except Exception as e:
                print(f"Error writing frame to video: {e}")
                # Save individual frames as fallback
                cv2.imwrite(os.path.join(videopath, f"{filename}_{t:04d}.png"), orig_resized_uint8)
                cv2.imwrite(os.path.join(videopath, f"{filename}_depth_{t:04d}.png"), depth_bilateral_uint8)
        else:
            # Save individual frames if video writers are not available
            print("no video writer, saving individual frames instead")
            cv2.imwrite(os.path.join(videopath, f"{filename}_{t:04d}.png"), orig_resized_uint8)
            cv2.imwrite(os.path.join(videopath, f"{filename}_depth_{t:04d}.png"), depth_bilateral_uint8)
        
        num_frames += 1
    
    # Release video resources
    texture_video.release()
    depth_video.release()
    
    if tv_writer is not None:
        tv_writer.release()
    if dv_writer is not None:
        dv_writer.release()
    
    print(f"Video processing complete. Output saved to {videopath}")