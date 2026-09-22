import logging
import multiprocessing

from pymobiledevice3.lockdown import create_using_usbmux, LockdownClient

from pymobiledevice3.cli.remote import install_driver_if_required
from pymobiledevice3.cli.remote import select_device, RemoteServiceDiscoveryService
from pymobiledevice3.cli.remote import start_tunnel
from pymobiledevice3.cli.remote import verify_tunnel_imports

from pymobiledevice3.services.amfi import AmfiService

from pymobiledevice3.exceptions import NoDeviceConnectedError

# 子进程 -> 主进程的队列消息标记
TUNNEL_OK = "ok"
TUNNEL_ERROR = "error"

def get_usbmux_lockdownclient():
    while True:
        try:
            lockdown = create_using_usbmux()
        except NoDeviceConnectedError:
            print("请连接设备后按回车...")
            input()
        else:
            break
    while True:
        lockdown = create_using_usbmux()
        if lockdown.all_values.get("PasswordProtected"):
            print("请解锁设备后按回车...")
            input()
        else:
            break
    return create_using_usbmux()

def get_version(lockdown: LockdownClient):
    return lockdown.all_values.get("ProductVersion")

def get_developer_mode_status(lockdown: LockdownClient):
    return lockdown.developer_mode_status

def reveal_developer_mode(lockdown: LockdownClient):
    AmfiService(lockdown).create_amfi_show_override_path_file()

def enable_developer_mode(lockdown: LockdownClient):
    AmfiService(lockdown).enable_developer_mode()

def get_serverrsd():
    install_driver_if_required()
    if not verify_tunnel_imports():
        exit(1)
    return select_device(None)


async def tunnel(rsd: RemoteServiceDiscoveryService, queue: multiprocessing.Queue):
    """建立隧道并把结果回传给主进程。

    成功与失败都必须往队列里写一条消息：隧道建立失败时（例如 QUIC 握手
    抛 ConnectionError）若什么都不写，主进程的 queue.get() 会永久阻塞。
    """
    try:
        async with start_tunnel(rsd, None) as tunnel_result:
            queue.put((TUNNEL_OK, tunnel_result.address, tunnel_result.port))
            await tunnel_result.client.wait_closed()
    except BaseException as exc:
        # BaseException 覆盖 SystemExit / KeyboardInterrupt：
        # 这些同样会让子进程退出而不写队列
        queue.put((TUNNEL_ERROR, type(exc).__name__, str(exc)))
        raise
