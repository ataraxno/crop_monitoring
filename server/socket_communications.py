import json
import socket
import time
import datetime
import logging
import pytz

import numpy as np


def timetz(*args):
    tzinfo = pytz.timezone("Asia/Seoul")
    return datetime.datetime.now(tzinfo).timetuple()

def create_logger(logger_name, file_dir=None):
    # Create Logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Check handler exists
    if len(logger.handlers) > 0:
        return logger  # Logger already exists

    formatter = logging.Formatter(
        "[%(asctime)s] - %(name)s - [%(levelname)s] - %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    formatter.converter = timetz
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)
    logger.addHandler(stream_handler)

    if file_dir is not None:
        file_handler = logging.FileHandler(f"{file_dir}/log.txt")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    return logger

logger = create_logger("COMM")

# Receive data equal to the number of [count] from [socket]
def _recvall(socket, count):
    buf = b""
    while count:
        newbuf = socket.recv(count)
        if not newbuf:
            return None
        buf += newbuf
        count -= len(newbuf)
    return buf


def recv_img(host, port):
    """ Receive images using socket communication.

    Args:
        host (str, optional): DDNS address of Raspberry Pi. 
        port (int, optional): Port opened

    Returns:
        ndarray or -1:
            Current images (480, 640, 4).
            if recv failed, img = -1
    """
    
    #NOTE: After finishing connect all sensors, add receiving sensor data from Raspberry Pi

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.settimeout(15)

    retry = 1
    error = 0

    while retry:
        msg = f"{error} error"
        try:
            client_socket.connect((host, port))
            msg = "connected to Raspberry Pi 3B+"
            logger.debug(msg)

            client_socket.sendall("sensing".encode())
            msg = "send `get_sensing_data` signal"
            logger.debug(msg)

            img_length = _recvall(client_socket, 16)
            img = _recvall(client_socket, int(img_length))
            msg = "recv img"
            logger.debug(msg)

            img = np.frombuffer(img, dtype="uint16").reshape(480, 640, 4)
            msg = "convert img"
            logger.debug(msg)
            retry = 0

        except Exception as e:
            logger.warning(e)
            if error > 2:
                logger.error(f"recv failed after {msg}")
                img = -1
                retry = 0
            else:
                error += 1
                time.sleep(1)

    client_socket.close()
    return img