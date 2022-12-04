import os
import time
import numpy as np
import cv2
import pyrealsense2.pyrealsense2 as rs

def get_rgbd_img(path_to_save=None):
    pipeline = rs.pipeline()
    config = rs.config()

    # Get device product line for setting a supporting resolution
    pipeline_wrapper = rs.pipeline_wrapper(pipeline)
    pipeline_profile = config.resolve(pipeline_wrapper)
    device = pipeline_profile.get_device()
    device_product_line = str(device.get_info(rs.camera_info.product_line))

    found_rgb = False
    for s in device.sensors:
        if s.get_info(rs.camera_info.name) == 'RGB Camera':
            found_rgb = True
            break
    if not found_rgb:
        print("Depth camera with Color sensor are not installed correctly")
        exit(0)

    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 15)

    if device_product_line == 'L500':
        config.enable_stream(rs.stream.color, 960, 540, rs.format.bgr8, 15)
    else:
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 15)

    # Start streaming
    pipeline.start(config)

    # Wait for a coherent pair of frames: depth and color
    frames = pipeline.wait_for_frames()
    depth_frame = frames.get_depth_frame()
    color_frame = frames.get_color_frame()
    
    # Convert images to numpy arrays
    depth_image = np.asanyarray(depth_frame.get_data())
    color_image = np.asanyarray(color_frame.get_data())

    # Apply colormap on depth image (image must be converted to 8-bit per pixel first)
    # depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)

    depth_colormap_dim = depth_image.shape[:2]
    depth_image = depth_image.reshape(*depth_colormap_dim, -1)
    color_colormap_dim = color_image.shape[:2]

    # If depth and color resolutions are different, resize color image to match depth image for display
    if depth_colormap_dim != color_colormap_dim:
        print(f"Resize color image to match depth image: {color_colormap_dim} -> {depth_colormap_dim}")
        color_image = cv2.resize(color_image, dsize=(depth_colormap_dim[1], depth_colormap_dim[0]), interpolation=cv2.INTER_AREA)
    rgbd_image = np.concatenate((color_image, depth_image), axis = -1)

    if path_to_save is not None:
        filename4rgb = f'{time.strftime("%Y_%m_%d_%H_%M_%S")}_color.jpg'
        filename4depth = f'{time.strftime("%Y_%m_%d_%H_%M_%S")}_depth.jpg'
        if path_to_save == "auto":
            path_to_save = "img"
        os.makedirs(path_to_save, exist_ok=True)
        cv2.imwrite(os.path.join(path_to_save, filename4rgb), rgbd_image[..., :3])
        cv2.imwrite(os.path.join(path_to_save, filename4depth), rgbd_image[..., 3:])

    # Stop streaming
    pipeline.stop()

    return rgbd_image