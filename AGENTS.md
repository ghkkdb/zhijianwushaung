# AGENTS.md

## 项目概览

这是一个仅面向 Windows 的 Python 桌面自动化工具，用于 `指尖无双`。

主程序功能：

- 启动前校验绑定机器码的授权文件；
- 通过 Win32 窗口句柄截取目标游戏窗口；
- 使用 OpenCV 对 `img/` 目录中的模板图进行匹配；
- 使用 `pywin32` 向后台窗口发送鼠标和键盘消息；
- 提供 Tkinter UI，用于配置检测关卡、结算/存档动作、点击坐标、窗口分辨率和操作流程。

授权工具功能：

- `license_tool.py` 使用 `private_key.pem` 签发授权文件；
- `machine_code.py` 从 Windows 标识生成稳定机器码；
- 生成的 `.lic` 文件由主程序读取。

## 重要文件

- `main.py`：主 GUI 程序和自动化逻辑。
- `machine_code.py`：机器指纹和机器码生成。
- `license_tool.py`：授权/密钥生成工具，包含 CLI 和 Tkinter UI。
- `zhijianwushuang.spec`：主程序 PyInstaller onedir 打包配置。
- `license_generator.spec`：授权生成器 PyInstaller onedir 打包配置。
- `img/`：OpenCV 模板图片，主程序打包时需要包含。
- `config.json`：运行配置，源码运行时位于项目目录，打包运行时应放在 exe 同级目录。
- `license.lic`：运行授权文件，应放在 `zhijianwushuang.exe` 同级目录。
- `private_key.pem`：授权签名私钥，只能用于授权生成器，不要随客户版主程序分发。

## 运行依赖

项目只支持 Windows。主程序依赖：

- Python 3.10 64 位；
- `pywin32`；
- `opencv-python` / `cv2`；
- `numpy`；
- `cryptography`；
- Python 自带的 Tkinter / Tcl / Tk。

程序直接使用 Windows API，不适合在 macOS 或 Linux 上运行。

## 开发命令

从源码运行主程序：

```powershell
python main.py
```

运行授权生成器 UI：

```powershell
python license_tool.py
```

打印当前机器码：

```powershell
python license_tool.py machine-code
```

命令行生成授权：

```powershell
python license_tool.py issue --machine-code XXXXXXXX-XXXXXXXX --licensed-to "client"
```

## 推荐打包方式

优先使用已验证可用的 Python 3.10 环境打包，不要使用全局 Conda base 环境或 Python 3.13。

当前已验证环境：

```powershell
D:\anaconda3\envs\ymjh_venv\python.exe
```

推荐打包命令：

```powershell
$env:CONDA_PREFIX='D:\anaconda3\envs\ymjh_venv'
& 'D:\anaconda3\envs\ymjh_venv\python.exe' -m PyInstaller .\zhijianwushuang.spec --noconfirm --clean --distpath .\dist_py310_fixed
Copy-Item -LiteralPath license.lic -Destination .\dist_py310_fixed\zhijianwushuang\license.lic -Force
Copy-Item -LiteralPath config.json -Destination .\dist_py310_fixed\zhijianwushuang\config.json -Force
```

构建后主程序路径：

```powershell
D:\Desktop\zhijianwushaung\dist_py310_fixed\zhijianwushuang\zhijianwushuang.exe
```

授权生成器打包：

```powershell
pyinstaller --clean --noconfirm license_generator.spec
```

## 打包注意事项

- 主程序只使用 `zhijianwushuang.spec` 打包。
- 客户版主程序只能打包 `img/` 等运行数据，不要打包 `private_key.pem`。
- `license.lic` 和 `config.json` 应在打包后复制到 `zhijianwushuang.exe` 同级目录。
- `license_generator.spec` 会包含 `private_key.pem`，该构建只用于内部授权生成，不要发给客户。
- 保持 onedir 模式，除非明确要求 onefile。
- 打包前尽量关闭正在运行的旧版 `zhijianwushuang.exe`，否则 PyInstaller 可能无法删除旧输出目录中的 `.pyd` 或 `.dll`。
- 每次修改打包配置后必须做启动冒烟测试：启动 exe，观察 5 秒内是否弹出 import/Tcl/Tk 异常窗口。

## 已踩坑记录

### 1. 不要用 Conda base / Python 3.13 打主程序包

曾经用 `D:\anaconda3\python.exe` 打包，生成的 exe 内含：

```text
python313.dll
```

运行时报错：

```text
Error importing numpy: you should not try to import numpy from its source directory
ImportError: DLL load failed while importing _multiarray_umath
```

这不是业务代码问题，而是 NumPy 运行时 DLL 没有被正确打入包，或 Conda NumPy/MKL 依赖被错误过滤。

处理原则：

- 不要用 Python 3.13 Conda base 打客户版主程序；
- 使用 Python 3.10 64 位环境；
- 确认构建前该环境可以成功导入：

```powershell
& 'D:\anaconda3\envs\ymjh_venv\python.exe' -c "import cv2, numpy, win32gui, cryptography; print('ok')"
```

### 2. 注意 `CONDA_PREFIX` 造成 Tcl/Tk 版本混用

曾经用完整路径调用：

```powershell
& 'D:\anaconda3\envs\ymjh_venv\python.exe' -m PyInstaller ...
```

但外层环境变量仍是：

```text
CONDA_PREFIX=D:\anaconda3
```

导致 `zhijianwushuang.spec` 从 base 环境拿了 Tcl/Tk DLL，包内混入 Tcl/Tk 8.6.14，而 Python 3.10 环境实际需要 Tcl/Tk 8.6.13。

运行时报错：

```text
Can't find a usable init.tcl
version conflict for package "Tcl": have 8.6.14, need exactly 8.6.13
```

修复原则：

- `zhijianwushuang.spec` 中 `ENV_PREFIX` 必须使用 `sys.prefix`，不要优先使用外部 `CONDA_PREFIX`。
- 打包时显式设置：

```powershell
$env:CONDA_PREFIX='D:\anaconda3\envs\ymjh_venv'
```

- 打包必须加 `--clean`，避免复用错误缓存。
- 构建日志中应看到使用：

```text
D:\anaconda3\envs\ymjh_venv\Library\bin\tcl86t.dll
D:\anaconda3\envs\ymjh_venv\Library\bin\tk86t.dll
```

### 3. 不要随意过滤 NumPy 必需 DLL

pip wheel 版本的 NumPy 会带有 `numpy.libs`。其中可能出现类似：

```text
libscipy_openblas*.dll
```

虽然文件名带 `scipy`，但它是 NumPy 需要的 OpenBLAS 运行库。不要因为名字里有 `scipy` 就删除，否则可能再次触发 `_multiarray_umath` 导入失败。

### 4. 有问题的旧输出目录

以下目录曾经出现过打包环境或运行库问题，不应作为交付版本使用：

```text
dist_new
dist_py310
```

当前应优先使用：

```text
dist_py310_fixed
```

## 打包前检查清单

1. 确认使用 Python 3.10 环境：

```powershell
& 'D:\anaconda3\envs\ymjh_venv\python.exe' -c "import sys; print(sys.version); print(sys.prefix)"
```

2. 确认依赖能导入：

```powershell
& 'D:\anaconda3\envs\ymjh_venv\python.exe' -c "import cv2, numpy, win32gui, cryptography, tkinter; print('ok')"
```

3. 确认 Tcl/Tk 版本：

```powershell
& 'D:\anaconda3\envs\ymjh_venv\python.exe' -c "import tkinter; t=tkinter.Tcl(); print(t.eval('info patchlevel')); print(t.eval('info library'))"
```

期望输出应指向：

```text
D:/anaconda3/envs/ymjh_venv/Library/lib/tcl8.6
```

4. 使用 `--clean` 打包。

5. 复制 `license.lic` 和 `config.json` 到 exe 同级目录。

6. 启动 exe 做冒烟测试。可用命令：

```powershell
$p = Start-Process -FilePath '.\dist_py310_fixed\zhijianwushuang\zhijianwushuang.exe' -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 5
if ($p.HasExited) { "EXITED $($p.ExitCode)" } else { Stop-Process -Id $p.Id -Force; "STARTED_OK" }
```

输出 `STARTED_OK` 表示至少没有启动即崩溃。

## 代码注意事项

- `main.py` 里存在顶层 helper 和 `if __name__ == "__main__":` 内嵌 helper 的重复实现；GUI 运行时使用内嵌版本。
- 源码中部分中文字符串可能存在乱码。除非专门做编码修复，不要随意批量改编码。
- 模板路径通过 `img_path()` 获取，需同时支持源码运行和 PyInstaller `_MEIPASS` 运行。
- 长时间等待必须尽量使用 `interruptible_sleep()`，避免停止按钮响应慢。
- 不要阻塞 Tkinter 主线程；识别、按键、移动流程应放在 daemon thread 中。

## 安全要求

- 不要把 `private_key.pem` 随客户版主程序分发。
- 不要随意替换 `main.py` 中嵌入的公钥，除非重新生成密钥对并重新签发所有客户授权。
- 不要删除 `dist/` 中已有客户 `.lic` 文件，除非明确要求。
- 修改点击坐标、模板阈值、分辨率、默认动作流程前要确认影响范围，这些配置会直接影响游戏内自动化行为。
