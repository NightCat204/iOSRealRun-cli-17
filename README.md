# iOSRealRun-cli-17

## 用法简介

### 前置条件

1. 系统是 `Windows` 或 `MacOS`
2. iPhone 或 iPad 系统版本大于等于 17
3. Windows 需要安装 iTunes
4. 已安装 `Python3` 和 `pip3`
5. **重要**: 只能有一台 iPhone 或 iPad 连接到电脑，否则会出问题

### 步骤

1. 克隆本项目到本地并进入项目目录

    ```
    https://github.com/NightCat204/iOSRealRun-cli.git
    ```

2. 安装依赖（建议使用虚拟环境）  
    ```shell
    conda create -n iOSRealRun python=3.12
    
    pip3 install -r requirements.txt
    ```
    如果 `pip3` 无法安装，请使用 `pip` 替代  
    如果提示没有需要的版本，请尝试不适用国内源  

3. 修改配置和路线文件

    1. 获取跑步路径，格式和其使用的格式完全相同，**但是请只画一圈**，项目预置了画的不太行的紫金港操场和海宁操场路径（在配置文件 `config.yaml` 里改路线的文件名），建议所有人都自己画路径  

        > 打开[路径拾取网站](https://fakerun.myth.cx/)。通过点击地图构造路径。点击时无需考虑间距，会自动用直线连接。路径点击完成后，单击上方的路径坐标——复制，将坐标数据复制到剪贴板  

    2. 打开脚本目录里的 `route.txt` 文件，将刚复制的内容原封不动的粘贴进去，保存并退出  

    3. 在脚本目录中的 `config.yaml` 文件中设置 `v` 变量以设置速度(m/s)

4. 将设备连接到电脑，解锁，如果请求信任的提示框，请点击信任

5. Windows **以管理员身份** 打开终端（cmd 或 PowerShell），先进入项目目录，然后执行以下命令  
    ```shell
    python main.py
    ```
    MacOS 打开终端，先进入项目目录，然后执行以下命令  
    ```shell
    sudo python3 main.py
    ```
    > 需要 管理员 或 root 权限是因为需要创建 tun 设备  

6. 按照提示操作，如果一直说没有设备连接，Windows请确保 iTunes 已安装（可能需要打开），重新运行程序，在第3步时请确保设备已连接，解锁并信任

7. 结束请务必使用 `Ctrl + C` 终止程序，否则无法恢复定位

8. 如果定位未恢复，可以重启手机解决
