import os
import shutil
import numpy as np
import cv2
from pathlib import Path

from depth_improving import improve_depth
from mesh_orientation import compute_triangle_orientations
from compute_alpha import compute_transparency_values
from extrapolated_layer import create_extrapolated_layer
from inpainted_layer import create_inpainted_layer

def main_process(filename):
    """
    Main processing pipeline for motion parallax for 360° RGBD video.
    
    This is a Python implementation of the preprocessing described in:
    Serrano, A., Kim, I., Chen, Z., DiVerdi, S., Gutierrez, D., Hertzmann, A., and Masia, B.
    "Motion parallax for 360° RGBD video"
    IEEE Transactions on Visualization and Computer Graphics, 2019.

    Translated to Python by Zhou B.
    
    Args:
        filename: Base name of the video file (without extension)
    """
    print("Starting preprocessing pipeline...")
    
    # Create output directories
    output_dirs = [
        f"_improved_depth/{filename}/videos",
        f"_triangle_orientations/{filename}",
        f"_extrapolated_layer/{filename}",
        f"_extrapolated_layer/{filename}/_triangle_orientations",
        f"_inpainted_layer/{filename}",
        f"_vid2viewer/{filename}"
    ]
    
    for directory in output_dirs:
        os.makedirs(directory, exist_ok=True)

    # Step 0: generate depth for video if none
    # TODO:


    # TODO: disable for now
    improve = False

    if improve:
        # Step 1: Depth improvement
        print("STARTING DEPTH PROCESSING")
        improve_depth(filename)
    else:
        # directly copy input files
        shutil.copy(f"_input_videos/{filename}.mp4", f"_improved_depth/{filename}/videos/{filename}.mp4")
        shutil.copy(f"_input_videos/{filename}_depth.mp4", f"_improved_depth/{filename}/videos/{filename}_depth.mp4")
    
    
    # Step 2: Compute triangle orientations
    print("COMPUTING TRIANGLE ORIENTATIONS")
    input_dir = f"_improved_depth/{filename}/videos/"
    output_dir = f"_triangle_orientations/{filename}"
    # compute_triangle_orientations(input_dir, filename, output_dir)
    
    # Step 3: Compute transparency values
    print("COMPUTING TRANSPARENCY VALUES")
    triangle_folder = f"_triangle_orientations/{filename}"
    compute_transparency_values(triangle_folder, filename)
    
    # Step 4: Create extrapolated layer
    print("COMPUTING EXTRAPOLATED LAYER")
    create_extrapolated_layer(filename)
    
    # Step 5: Compute triangle orientations for extrapolated layer
    print("COMPUTING TRIANGLE ORIENTATIONS OF EXTRAPOLATED LAYER")
    extrapolated_input = f"_extrapolated_layer/{filename}"
    extrapolated_output = f"_extrapolated_layer/{filename}/_triangle_orientations"
    compute_triangle_orientations(extrapolated_input, f"{filename}_BG", extrapolated_output)
    
    # Step 6: Compute transparency values for extrapolated layer
    print("COMPUTING TRANSPARENCY VALUES OF EXTRAPOLATED LAYER")
    compute_transparency_values(f"_extrapolated_layer/{filename}/_triangle_orientations", f"{filename}_BG")
    
    # Save alpha image
    bg_alpha_video = cv2.VideoCapture(f"_extrapolated_layer/{filename}/_triangle_orientations/{filename}_BG_alphaproc.mp4")
    ret, alpha_frame = bg_alpha_video.read()
    if ret:
        cv2.imwrite(f"_extrapolated_layer/{filename}/{filename}_BGA.png", alpha_frame)
    bg_alpha_video.release()
    
    # Step 7: Create inpainted layer
    print("COMPUTING INPAINTED LAYER")
    create_inpainted_layer(filename)
    
    # Step 8: Save final files to viewer directory
    print("SAVING INTO _vid2viewer FOLDER")
    copy_files_to_viewer(filename)
    
    # Step 9: Clean up temporary files (optional)
    print("DELETING TEMPORARY FILES")
    # Uncomment to enable cleanup
    cleanup_temp_files()
    
    print("Processing complete! Files are ready for the viewer.")

def copy_files_to_viewer(filename):
    """Copy the processed files to the viewer directory."""
    src_files = [
        (f"_improved_depth/{filename}/videos/{filename}.mp4", f"_vid2viewer/{filename}/{filename}.mp4"),
        (f"_improved_depth/{filename}/videos/{filename}_depth.mp4", f"_vid2viewer/{filename}/{filename}_depth.mp4"),
        (f"_triangle_orientations/{filename}/{filename}_alphaproc.mp4", f"_vid2viewer/{filename}/{filename}_alphaproc.mp4"),
        (f"_extrapolated_layer/{filename}/{filename}_BG.png", f"_vid2viewer/{filename}/{filename}_BG.png"),
        (f"_extrapolated_layer/{filename}/{filename}_BG_depth.png", f"_vid2viewer/{filename}/{filename}_BGD.png"),
        (f"_extrapolated_layer/{filename}/{filename}_BGA.png", f"_vid2viewer/{filename}/{filename}_BGA.png"),
        (f"_inpainted_layer/{filename}/{filename}_BG_inp.png", f"_vid2viewer/{filename}/{filename}_BG_inp.png"),
        (f"_inpainted_layer/{filename}/{filename}_BGD_inp.png", f"_vid2viewer/{filename}/{filename}_BGD_inp.png")
    ]
    
    for src, dst in src_files:
        shutil.copyfile(src, dst)

def cleanup_temp_files():
    """Remove temporary processing directories."""
    temp_dirs = ["_extrapolated_layer", "_improved_depth", "_inpainted_layer", "_triangle_orientations"]
    for directory in temp_dirs:
        shutil.rmtree(directory, ignore_errors=True)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process 360° RGBD video for motion parallax.")
    parser.add_argument("filename", help="Base name of the video file (without extension)")
    args = parser.parse_args()
    
    main_process(args.filename)