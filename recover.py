"""
recover.py — 紧急恢复定位脚本

主程序异常退出导致设备定位卡住时，运行此脚本恢复真实定位。
用法（与 main.py 相同）：
    python recover.py          # macOS 会自动请求 sudo
    python recover.py          # Windows 需以管理员身份运行
"""
import ctypes
import logging
import os
import sys

try:
    import coloredlogs
except ModuleNotFoundError:
    coloredlogs = None


def _install_logging(level: int):
    if coloredlogs is not None:
        coloredlogs.install(level=level)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            force=True,
        )


def _ensure_root():
    if sys.platform == "darwin":
        if os.geteuid() != 0:
            script_path = os.path.abspath(__file__)
            print("需要 root 权限创建 tun 设备，正在使用当前 Python 解释器重新启动...")
            os.execvp("sudo", ["sudo", sys.executable, script_path, *sys.argv[1:]])
    elif sys.platform == "win32":
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("请以管理员权限运行")
            sys.exit(1)
    else:
        print("仅支持 macOS 和 Windows")
        sys.exit(1)


def main():
    _install_logging(logging.INFO)
    logger = logging.getLogger(__name__)

    _ensure_root()

    try:
        from driver import connect, location
        from init import tunnel as tunnel_module
        from pymobiledevice3.cli.developer import DvtSecureSocketProxyService
        from pymobiledevice3.cli.remote import RemoteServiceDiscoveryService
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown"
        print(f"缺少依赖: {missing}")
        if sys.platform == "darwin" and os.geteuid() == 0:
            print("请先激活虚拟环境，再直接运行 `python recover.py`（程序会自动请求 sudo）")
        else:
            print("请在当前环境安装依赖：pip3 install -r requirements.txt")
        sys.exit(1)

    print("正在连接设备...")
    try:
        lockdown = connect.get_usbmux_lockdownclient()
    except Exception as exc:
        logger.error(f"连接设备失败: {exc}")
        sys.exit(1)

    version = connect.get_version(lockdown)
    logger.info(f"设备系统版本: {version}")
    if version.split(".")[0] < "17":
        print("仅支持 iOS 17 及以上版本，请重启手机以恢复定位")
        sys.exit(1)

    if not connect.get_developer_mode_status(lockdown):
        print("设备未开启开发者模式，无法通过程序恢复定位，请重启手机")
        sys.exit(1)

    print("正在建立隧道...")
    process = None
    try:
        process, address, port = tunnel_module.tunnel()
        logger.info("隧道已建立")

        with RemoteServiceDiscoveryService((address, port)) as rsd:
            with DvtSecureSocketProxyService(rsd) as dvt:
                location.clear_location(dvt)
                print("定位已恢复")
    except KeyboardInterrupt:
        print("\n已中断，定位可能未完全恢复，请重启手机")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"恢复定位失败: {exc}")
        print("恢复失败，请重启手机")
        sys.exit(1)
    finally:
        if process is not None and process.is_alive():
            process.terminate()
            logger.info("隧道已关闭")


if __name__ == "__main__":
    main()
