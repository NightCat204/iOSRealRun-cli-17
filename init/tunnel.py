import asyncio
import logging
import multiprocessing
import os

from driver import connect

def tunnel_proc(queue: multiprocessing.Queue):
    # 子进程有独立的 logging 状态，需单独配置，与主进程保持一致
    _debug = os.environ.get("DEBUG", False)
    _level = logging.DEBUG if _debug else logging.WARNING
    for _name in ("wintun", "quic", "asyncio", "urllib3.connectionpool"):
        logging.getLogger(_name).setLevel(_level)
    # zeroconf 在 macOS 上会产生已知的非致命 mDNS socket 警告（[Errno 55]），
    # 单独抑制到 ERROR 级别，DEBUG 模式下仍完整输出
    logging.getLogger("zeroconf").setLevel(logging.DEBUG if _debug else logging.ERROR)

    server_rsd = connect.get_serverrsd()
    asyncio.run(connect.tunnel(server_rsd, queue))


def tunnel():
    # start the tunnel in another process
    queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=tunnel_proc, args=(queue,))
    process.start()
    
    # get the address and port of the tunnel
    address, port = queue.get()

    return process, address, port