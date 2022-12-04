"""
created by hychoi
"""
import argparse
import logging
import os
import serial
import socket
from typing import Tuple, Union

from const import APPROVED_IP, CMD_SENSING, CMD_CONTROL
from get_rgbd_img import get_rgbd_img
from utils import get_KST_date, TimedInput


def get_ip() -> str:
    """
    get my ip (In this case, get ip of currnent raspberry pi)

    Returns:
        ip
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def recv_all(sock: socket.socket, count: int) -> Union[bytes, None]:
    """
    Receive all data from Server (or Client)

    Args:
        sock: socket.Socket object (where the data sent from)
        count: the numbers of character

    Returns:
        data: data byte object
        None when the numbers of character != len(newbuf)
    """

    buf = b""
    while count:
        newbuf = sock.recv(count)
        if not newbuf:
            return None
        buf += newbuf
        count -= len(newbuf)
    return buf


def binder(client_socket: socket.socket, addr: str, debug=False):
    """
    Data communication between server and raspberry pi
    Save data locally

    Args:
        client_socket: Accepted client socket object
        addr: Address of accepted client socket
        debug: if True, do not save the data in local directory

    Raises:
        ValueError: Error raised when command from server is not a correct command (obs or act).
    """

    try:
        cmd = recv_all(client_socket, 7).decode()
        logger.debug(f"cmd: {cmd}")
        if cmd == CMD_SENSING:
            img_save_path = os.path.join(epi_name, "img")
            if debug: img_save_path = None
            rgbd_image = get_rgbd_img(img_save_path)
            stringimg = rgbd_image.tobytes()
            client_socket.sendall((str(len(stringimg))).encode().ljust(16) + stringimg)
            logger.debug("img sent")
            # NOTE: get sensing data
            logger.debug("obs sent")

        elif cmd == CMD_CONTROL:
            # NOTE: control 
            pass
        else:
            logger.warning(cmd)
            raise ValueError(f"{cmd} is not a correct command.")

        logger.info(f"{cmd} - received from {str(addr[0])}:{str(addr[1])}\n")

    except Exception as e:
        logger.error(e.__str__())

    finally:
        client_socket.close()


def Server(
    HOST: str, PORT: int
) -> Tuple[serial.Serial, socket.socket]:
    """
    Start rasp server to communicate with Data server (using socket).

    Args:
        HOST: Current Raspberry Pi IP address
        PORT: Port designation (default: 9999)

    Returns:
        server_socket: socket.socket
    """

    # socket ready (Server)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    logger.info(f"Rasp is ready to service... ({HOST}:{PORT})\n")

    return server_socket


def main(args):
    """
    Raspberry Pi Server
    Communicate with server by socket communication

    Args:
        args (parser.parse_args()) - port:9999 (default)

    KeyboardInterrupt:
        Terminate server

    Raises:
        "Socket error - ~": Error raised when socket.accept()
        "Binder error - ~": Error raised in binder()
    """
    EXIT = 0

    while True:
        if EXIT:
            break
        ip = get_ip()
        server_socket = Server(HOST=ip, PORT=args.port)

        while True:
            try:
                while True:
                    client_socket, addr = server_socket.accept()
                    client_socket.settimeout(30)
                    if "*" in APPROVED_IP or addr[0] in APPROVED_IP:
                        break
                    client_socket.close()
                    logger.warning(str(addr[0]) + ":" + str(addr[1]) + " is refused.\n")
                logger.debug("________________________________________________")
                logger.debug("Connected by " + str(addr[0]) + ":" + str(addr[1]))

            except KeyboardInterrupt:
                # terminate the server: ctrl + C
                while True:
                    result = TimedInput(
                        "Do you want to terminate the server? (y/n) : ", "timeout", 3
                    )
                    try:
                        if result.lower() in ("y", "yes"):
                            logger.warning("Terminate Server")
                            server_socket.close()
                            EXIT = 1
                            break
                        elif result.lower() in ("n", "no"):
                            logger.info("Termination canceled")
                            break
                        elif result == "timeout":
                            print("")
                            logger.info("Timed out for typing. Termination canceled")
                            break
                        else:
                            continue
                    except:
                        continue

                if EXIT:
                    break
                else:
                    continue

            except Exception as e:
                server_socket.close()
                logger.error(f"Socket error - {e.__str__()}")
                break

            try:
                binder(client_socket, addr, args.debug)

            except Exception as e:
                server_socket.close()
                logger.error(f"Binder error - {e.__str__()}")
                break

    server_socket.close() 


# ----------------------------------------------------------------------------
epi_name = f"Server{get_KST_date()}"

# save data locally
os.makedirs(epi_name, exist_ok=True)
os.makedirs(os.path.join(epi_name, "img"), exist_ok=True)
os.makedirs(os.path.join(epi_name, "obs"), exist_ok=True)
os.makedirs(os.path.join(epi_name, "act"), exist_ok=True)

# logging
logger = logging.getLogger("Server")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(asctime)s] - %(name)s - [%(levelname)s] - %(message)s", "%Y-%m-%d %H:%M:%S"
)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)

file_handler = logging.FileHandler(os.path.join(epi_name, "log.txt"))
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RaspServer communication with Server and Arduino",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-p", "--port", type=int, default=9999, help="PORT for socket communication"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Do not save files"
    )
    args = parser.parse_args()

    main(args)
