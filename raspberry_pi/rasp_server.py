"""
created by hychoi
"""
import argparse
import json
import logging
import matplotlib.pyplot as plt
import os
import serial
import socket
import time
from typing import Tuple, Union

from const import APPROVED_IP, CMD_SENSING, CMD_CONTROL, INIT_CHAR, TERMINATE_CHAR
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


def is_valid_actions(actions: str) -> bool:
    """
    Check if actions are correct
     - init, terminate characters ('<' , '>')
     - type (int or float)
     - valid (range)

    Args:
        actions: <The activation time of time> ex. <300>
    Returns:
        bool: True if actions are normal else raise error.
    """

    data_start = actions.find(INIT_CHAR)
    data_end = actions.find(TERMINATE_CHAR)
    action_data = actions[data_start + 1:data_end]  # actions = <data>
    try:
        action_data = int(action_data)
    except:
        return False

    if len(action_data) != 1:
        return False

    if action_data < 0 and action_data > 300:
        return False
    return True


def commu_serial(cmd: str, debug=False):
    """
    Serial communication between Raspberry Pi and Arduino
    Update obs

    Args:
        cmd: "<obs>" or 25 characters <05.1f,05.1f,03d,03d,03d> (eg. <-10.0,066.5,255,150,128>)
        debug: if True, Don't send data to New Relic server

    Raises:
        ValueError:
            The command was not delivered properly.
            There are problems in CO2 sensor.
            Wrong command
        TimeoutError
    """

    global serial_restart, timeout_count
    retry = 0
    try:
        if cmd == CMD_SENSING:
            arduino.write(cmd.encode())
            recv = 1
            start = time.time()
            while recv:
                if arduino.in_waiting != 0:
                    if retry > 2:
                        raise ValueError(f"Retried {cmd.encode()} 3 times")
                    content = arduino.readline()[:-2].decode()
                    if "wrong" in content:  # The command was not delivered properly.
                        logger.warning(content)
                        arduino.write(cmd.encode())
                        retry += 1
                        continue

                    elif "___" in content:  # End signal
                        logger.debug(content)
                        recv = 0

                    else:
                        logger.info(content)

                if time.time() - start > 30:
                    raise TimeoutError("Arduino obs timeout")

        elif is_valid_actions(cmd):
            arduino.write(cmd.encode())
            recv = 1
            start = time.time()
            while recv:
                if arduino.in_waiting != 0:
                    if retry > 2:
                        raise ValueError(f"Retried {cmd.encode()} 3 times")
                    content = arduino.readline()[:-2].decode()
                    if "wrong" in content:  # The command was not delivered properly.
                        logger.warning(content)
                        arduino.write(cmd.encode())
                        retry += 1
                        continue

                    elif "___" in content:  # End signal
                        logger.debug(content)
                        recv = 0

                    else:
                        logger.info(content)

                if time.time() - start > 30:
                    raise TimeoutError("Arduino act timeout")

        else:
            raise ValueError(f"{cmd} is wrong command.")

    except Exception as e:
        logger.error(f"serial commu failed - {e.__str__()}")
        if (
            "timeout" not in e.__str__() or timeout_count > 1
        ):  # 3rd timeout -> serial restart
            timeout_count = 0
            serial_restart = 1
        else:
            timeout_count += 1


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
            if not debug:
                plt.imsave(
                    os.path.join(epi_name, "img", "RGB" + get_KST_date() + ".jpg"), rgbd_image[..., :3]
                )
                plt.imsave(
                    os.path.join(epi_name, "img", "depth" + get_KST_date() + ".jpg"), rgbd_image[..., 3:]
                )
            stringimg = rgbd_image.tobytes()
            client_socket.sendall((str(len(stringimg))).encode().ljust(16) + stringimg)
            logger.debug("img done.")
            obs = commu_serial(CMD_SENSING)
            if not debug:
                with open(
                    os.path.join(epi_name, "obs", "obs" + get_KST_date() + ".json"), "w"
                ) as f:
                    json.dump(obs, f)
            obs_string = json.dumps(obs)
            client_socket.sendall(
                (str(len(obs_string))).encode().ljust(16) + obs_string.encode()
            )
            logger.debug("obs done.")

        elif cmd == CMD_CONTROL:
            control = recv_all(client_socket, 3).decode()
            commu_serial("<" + control + ">", debug)
            with open(
                os.path.join(epi_name, "act", "act" + get_KST_date() + ".json"), "w"
            ) as f:
                json.dump({"pump": int(control)}, f)
            logger.debug("act performed")
        else:
            logger.warning(cmd)
            raise ValueError(f"{cmd} is not a correct command.")

        logger.info(f"{cmd} - received from {str(addr[0])}:{str(addr[1])}\n")

    except Exception as e:
        logger.error(e.__str__())

    finally:
        client_socket.close()


def Server(
    USB: str, BRATE: int, HOST: str, PORT: int
) -> Tuple[serial.Serial, socket.socket]:
    """
    Start rasp server to communicate with Data server (using socket).

    Args:
        USB: USB port where Arduino is connected; ex) '/dev/ttyACM0'
        BRATE: brate rate for Arduino
        HOST: Current Raspberry Pi IP address
        PORT: Port designation (default: 9999)

    Returns:
        arduino: serial.Serial
        server_socket: socket.socket
    """

    # serial ready (Arduino)
    arduino = serial.Serial(USB, baudrate=BRATE, timeout=1)
    logger.info(f"Arduino port: {str(arduino.name)}")

    ready = 1
    init = 0
    start = time.time()
    while ready:
        if arduino.in_waiting != 0:
            content = arduino.readline()[:-2].decode()
            if "Scanning all addresses, please wait..." in content:
                init = 1
            if "No sensors found, please check connections and restart the Arduino." in content:
                raise ValueError("Arudino system needs to be checked.")
            if init:
                logger.info(content)
            if ("Total number of sensors found" in content) and init:
                ready = 0

        if time.time() - start > 30:  # when data is not coming
            logger.warning("There is no proper incoming data from the Arduino.")
            ready = 0

    # socket ready (Server)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    logger.info(f"Rasp is ready to service... ({HOST}:{PORT})\n")

    return arduino, server_socket


def main(args):
    """
    Raspberry Pi Server
    Communicate with server by socket communication
    Communicate with arduino by serial communication

    Args:
        args (parser.parse_args()) - port:9999 (default)

    KeyboardInterrupt:
        Terminate server

    Raises:
        "Socket error - ~": Error raised when socket.accept()
        "Binder error - ~": Error raised in binder()
    """
    global serial_restart, arduino
    EXIT = 0

    if not args.debug:
        # save data locally
        os.makedirs(epi_name, exist_ok=True)
        os.makedirs(os.path.join(epi_name, "img"), exist_ok=True)
        os.makedirs(os.path.join(epi_name, "obs"), exist_ok=True)
        os.makedirs(os.path.join(epi_name, "act"), exist_ok=True)

    while True:
        if EXIT:
            break
        ip = get_ip()
        arduino, server_socket = Server(USB=USB, BRATE=BRATE, HOST=ip, PORT=args.port)

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
                arduino.close()
                logger.error(f"Socket error - {e.__str__()}")
                break

            try:
                binder(client_socket, addr, args.debug)

            except Exception as e:
                server_socket.close()
                arduino.close()
                logger.error(f"Binder error - {e.__str__()}")
                break

            if serial_restart:
                logger.error("Restart due to serial commu problem")
                server_socket.close()
                arduino.close()
                time.sleep(1)
                serial_restart = 0
                break

    server_socket.close()
    arduino.close()


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

    serial_restart = 0
    timeout_count = 0

    # Arduino address
    arduino = None
    USB = "/dev/ttyACM0"  # fixed
    BRATE = 115200  # fixed

    epi_name = f"Server{get_KST_date()}"

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
    
    if not args.debug:
        file_handler = logging.FileHandler(os.path.join(epi_name, "log.txt"))
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    main(args)
