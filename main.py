import win32gui
import win32api
import win32con
import time
import win32ui
import ctypes
import ctypes.wintypes
import cv2
import numpy as np
import os
import sys
import json
import base64
import glob
import hashlib
import queue
import urllib.request
import urllib.error
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from machine_code import get_machine_code

LICENSE_FILENAME = "license.lic"
AUTHOR_PASSWORD_SHA256 = "e95457047e432ff22c292c77e5962bf622f950ad0bf38155765b82d3d249d160"
LICENSE_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkZeoVFBVO4onlKZh6/i3
/WYaDtLpyTH7Qm8jZYQdJPAzxDeQDcW2Xf50Q0lcSJzEABmENQss7b9QMCT3uMWy
AELCGwk3r5ox9gE+vOj7o0/kpqpFFmjI7t/kRIs4UlmT0Mp0rEiP0tjMSXeXsCFJ
jn7JJ/e4RLHqpV0pOE9OSZDLt+nWHMK6t/fFDqmbY9afIbctggAqxBJRKsRicFss
uurPyKP3MQC1P0comQy1MyjRlORylJ6x889rdLrMujQgOlxjMPbrIcd+DkmaOOIh
d7Z6ZKIz1iat4nV1Imcfg+sUOKEz7t+UjhN9zjl5b9ihyGQgBX74aXMu6gQOunHm
VQIDAQAB
-----END PUBLIC KEY-----"""


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def license_path():
    exact_path = os.path.join(app_dir(), LICENSE_FILENAME)
    if os.path.exists(exact_path):
        return exact_path

    candidates = [
        path for path in glob.glob(os.path.join(app_dir(), "license*.lic"))
        if os.path.isfile(path)
    ]
    if candidates:
        return max(candidates, key=os.path.getmtime)
    return exact_path


def _load_license_file(path):
    with open(path, "r", encoding="utf-8") as f:
        license_data = json.load(f)
    payload_b64 = license_data["payload"]
    signature_b64 = license_data["signature"]
    payload_bytes = base64.b64decode(payload_b64)
    signature = base64.b64decode(signature_b64)
    payload = json.loads(payload_bytes.decode("utf-8"))
    return payload_bytes, signature, payload


def verify_license():
    current_machine_code = get_machine_code()
    path = license_path()
    if not os.path.exists(path):
        return False, "未找到授权文件。", current_machine_code

    try:
        payload_bytes, signature, payload = _load_license_file(path)
        public_key = serialization.load_pem_public_key(LICENSE_PUBLIC_KEY_PEM)
        public_key.verify(
            signature,
            payload_bytes,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    except (OSError, KeyError, ValueError, json.JSONDecodeError, InvalidSignature) as exc:
        return False, f"授权文件无效或已被篡改：{exc}", current_machine_code

    licensed_machine_code = str(payload.get("machine_code", "")).strip().upper()
    if licensed_machine_code != current_machine_code:
        return False, (
            "授权文件不属于当前机器。\n\n"
            f"当前机器码：{current_machine_code}\n"
            f"授权机器码：{licensed_machine_code or '未填写'}"
        ), current_machine_code

    expires_at = str(payload.get("expires_at", "")).strip()
    if expires_at:
        try:
            expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            return False, f"授权到期时间格式无效：{expires_at}", current_machine_code
        if datetime.now(timezone.utc) > expires:
            return False, f"授权已过期：{expires_at}", current_machine_code

    licensed_to = str(payload.get("licensed_to", "")).strip()
    suffix = f"，授权给：{licensed_to}" if licensed_to else ""
    return True, f"本机授权验证通过{suffix}。", current_machine_code


def ensure_license_or_exit():
    ok, message, machine_code = verify_license()
    if ok:
        return message

    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("授权验证失败")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = ttk.Frame(root, padding=(22, 18, 22, 18))
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)

    ttk.Label(frame, text="授权验证失败", font=("Microsoft YaHei UI", 14, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(frame, text=message, wraplength=420, justify="left").grid(
        row=1, column=0, sticky="w", pady=(12, 8)
    )
    ttk.Label(frame, text="当前机器码：").grid(row=2, column=0, sticky="w", pady=(4, 2))

    code_var = tk.StringVar(value=machine_code)
    code_entry = ttk.Entry(frame, textvariable=code_var, width=28, state="readonly")
    code_entry.grid(row=3, column=0, sticky="ew")

    status_var = tk.StringVar(value="")

    def copy_machine_code():
        root.clipboard_clear()
        root.clipboard_append(machine_code)
        root.update()
        status_var.set("机器码已复制。")

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=4, column=0, sticky="e", pady=(14, 0))
    ttk.Label(frame, textvariable=status_var).grid(row=5, column=0, sticky="w", pady=(8, 0))
    ttk.Button(button_frame, text="复制机器码", command=copy_machine_code).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(button_frame, text="关闭", command=root.quit).pack(side=tk.LEFT)

    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.protocol("WM_DELETE_WINDOW", root.quit)
    root.mainloop()
    root.destroy()
    sys.exit(1)

def click_relative_coordinate(hwnd, x, y):
    """
    向指定窗口句柄的客户区相对坐标发送鼠标左键点击事件
    """
    if not hwnd:
        print("无效的窗口句柄")
        return

    # Windows API 要求将 X 和 Y 坐标合并为一个 32位 整数 (lParam)
    # 低 16 位是 X 坐标，高 16 位是 Y 坐标
    lparam = win32api.MAKELONG(int(x), int(y))
    
    # 1. 发送鼠标左键按下消息 (WM_LBUTTONDOWN)
    # 参数说明: 目标句柄, 消息类型, wParam (按键修饰符, 这里是左键按下), lParam (坐标)
    win32api.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    
    # 【细节】适当的延迟非常重要！
    # 很多游戏引擎（如 Unity/UE）通过轮询来检测按键，如果按下和抬起太快，游戏可能识别不到。
    time.sleep(0.05 + 0.05 * np.random.rand()) # 添加 50ms - 100ms 的随机延迟，模拟真人
    
    # 2. 发送鼠标左键抬起消息 (WM_LBUTTONUP)
    win32api.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    
    print(f"已点击窗口句柄 {hwnd} 的相对坐标 ({x}, {y})")

def capture_window_to_cv2(hwnd):
    """
    根据窗口句柄截取客户区画面，并直接转换为 OpenCV 支持的 BGR 格式数组
    """
    # 1. 获取客户区大小 (排除标题栏和边框，只截取游戏实际画面)
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width = right - left
    height = bottom - top

    if width == 0 or height == 0:
        print("窗口已最小化或大小为 0")
        return None

    # 2. 获取设备上下文 (DC)
    hwnd_dc = win32gui.GetDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    # 3. 创建位图对象并在内存中开辟空间
    save_bitmap = win32ui.CreateBitmap()
    save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(save_bitmap)

    # 4. 执行截图
    # PrintWindow 的第三个参数设为 3 (PW_RENDERFULLCONTENT)，可以截取大部分硬件加速（DirectX/OpenGL）的游戏窗口
    result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
    
    if result == 0:
        # 如果 PrintWindow 失败，降级使用 BitBlt (传统的 GDI 拷贝)
        save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

    # 5. 将内存中的位图转换为 Numpy 数组
    bmp_info = save_bitmap.GetInfo()
    bmp_str = save_bitmap.GetBitmapBits(True)
    img_array = np.frombuffer(bmp_str, dtype=np.uint8)
    
    # 重塑数组形状：高度、宽度、4通道(BGRA)
    img_array.shape = (bmp_info['bmHeight'], bmp_info['bmWidth'], 4)

    # 6. 【非常重要】释放资源，否则会导致内存泄漏！
    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    # 7. OpenCV 默认使用 BGR 格式，我们需要丢弃 Alpha 通道 (透明度)
    img_cv2 = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
    
    return img_cv2

def find_template(main_img, template_path, threshold=0.8):
    """
    在主图中寻找模板图
    """
    # 读取你要寻找的小图 (模板)
    template = cv2.imread(template_path)
    if template is None:
        print(f"找不到模板文件: {template_path}，请检查路径。")
        return None

    # 获取模板的宽(tw)和高(th)
    th, tw = template.shape[:2]

    # 使用 OpenCV 的 matchTemplate 进行匹配 (使用归一化相关系数匹配法)
    result = cv2.matchTemplate(main_img, template, cv2.TM_CCOEFF_NORMED)
    
    # 提取匹配结果中的极值和对应坐标
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    # max_val 就是相似度，max_loc 就是匹配到的左上角坐标
    if max_val >= threshold:
        print(f"匹配成功！相似度: {max_val:.2f}, 坐标: {max_loc}")
        # 计算右下角坐标
        bottom_right = (max_loc[0] + tw, max_loc[1] + th)
        # 计算中心点坐标 (如果后续要写自动点击，点中心最稳)
        center_x = max_loc[0] + tw // 2
        center_y = max_loc[1] + th // 2
        # 点击中心点坐标
        # click_relative_coordinate(hwnd, center_x, center_y)
        
        return {
            "top_left": max_loc,
            "bottom_right": bottom_right,
            "center": (center_x, center_y),
            "confidence": max_val
        }
    else:
        print(f"匹配失败。当前最高相似度为: {max_val:.2f} (要求阈值: {threshold})")
        return None

if __name__ == "__main__":
    import tkinter as tk
    from tkinter import ttk, messagebox
    import threading
    import time
    import ctypes
    import win32gui
    import win32ui
    import win32api
    import win32con
    import cv2
    import numpy as np

    startup_license_message = ensure_license_or_exit()

    # 开启高 DPI 感知，防止由于 Windows 缩放导致获取的坐标偏移
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

    # ==========================================
    # 核心功能函数区
    # ==========================================
    def capture_window_to_cv2(hwnd):
        """根据窗口句柄后台截图，并转换为 OpenCV 格式"""
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        width = right - left
        height = bottom - top

        if width == 0 or height == 0:
            return None

        hwnd_dc = win32gui.GetDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(save_bitmap)

        # 3 代表 PW_RENDERFULLCONTENT，支持硬件加速窗口后台截图
        result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        if result == 0:
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

        bmp_info = save_bitmap.GetInfo()
        bmp_str = save_bitmap.GetBitmapBits(True)
        img_array = np.frombuffer(bmp_str, dtype=np.uint8)
        img_array.shape = (bmp_info['bmHeight'], bmp_info['bmWidth'], 4)

        # 释放资源防内存泄漏
        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        # 丢弃 Alpha 通道
        img_cv2 = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        return img_cv2

    def find_template(main_img, template_path, threshold=0.8, strict=False, edge_threshold=0.45, focus_threshold=0.82):
        """在主图中寻找模板图，返回中心坐标等信息"""
        template = cv2.imread(template_path)
        if template is None:
            update_log(f"❌ 找不到模板文件: {template_path}，请检查路径。")
            return None

        th, tw = template.shape[:2]
        if strict:
            main_match_img = cv2.cvtColor(main_img, cv2.COLOR_BGR2GRAY)
            template_match_img = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            main_match_img = main_img
            template_match_img = template

        result = cv2.matchTemplate(main_match_img, template_match_img, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            if strict:
                x, y = max_loc
                gray_patch = main_match_img[y:y + th, x:x + tw]
                if gray_patch.shape[:2] != template_match_img.shape[:2]:
                    return None

                patch_edges = cv2.Canny(gray_patch, 50, 150)
                template_edges = cv2.Canny(template_match_img, 50, 150)
                edge_result = cv2.matchTemplate(patch_edges, template_edges, cv2.TM_CCOEFF_NORMED)
                _, edge_score, _, _ = cv2.minMaxLoc(edge_result)

                focus_width = max(1, int(tw * 0.62))
                focus_patch = gray_patch[:, :focus_width]
                focus_template = template_match_img[:, :focus_width]
                focus_result = cv2.matchTemplate(focus_patch, focus_template, cv2.TM_CCOEFF_NORMED)
                _, focus_score, _, _ = cv2.minMaxLoc(focus_result)

                if edge_score < edge_threshold or focus_score < focus_threshold:
                    return None

            center_x = max_loc[0] + tw // 2
            center_y = max_loc[1] + th // 2
            return {
                "top_left": max_loc,
                "center": (center_x, center_y),
                "confidence": max_val
            }
        return None

    def click_relative_coordinate(hwnd, x, y):
        """向指定窗口句柄的客户区相对坐标发送后台鼠标点击"""
        if not hwnd:
            return
        lparam = win32api.MAKELONG(int(x), int(y))
        win32api.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        # 随机微小延迟防检测
        time.sleep(0.05 + 0.05 * np.random.rand()) 
        win32api.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        update_log(f"👉 已点击坐标 ({x}, {y})")

    def interruptible_sleep(seconds, match_event=None, interval=0.01):
        end_time = time.time() + seconds
        while time.time() < end_time:
            if not is_running:
                return False
            if match_event is not None and match_event.is_set():
                return False
            time.sleep(min(interval, max(0, end_time - time.time())))
        return True

    def send_key_down(hwnd, vk):
        scan_code = win32api.MapVirtualKey(vk, 0)
        lparam = 1 | (scan_code << 16)
        win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, vk, lparam)

    def send_key_up(hwnd, vk):
        scan_code = win32api.MapVirtualKey(vk, 0)
        lparam = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)
        win32api.SendMessage(hwnd, win32con.WM_KEYUP, vk, lparam)

    def tap_key(hwnd, vk, duration=0.05):
        send_key_down(hwnd, vk)
        interruptible_sleep(duration)
        send_key_up(hwnd, vk)

    def wait_until_matched(match_event, seconds):
        return interruptible_sleep(seconds, match_event=match_event)

    DEFAULT_MOVEMENT_ACTIONS = [
        {"key": "D", "duration": 2, "count": 1},
        {"key": "A", "duration": 0.1, "count": 1},
        {"key": "F", "duration": 0.05, "count": 1},
        {"key": "1", "duration": 0.05, "count": 1},
    ]

    SPECIAL_KEYS = {
        "SPACE": win32con.VK_SPACE,
        "ENTER": win32con.VK_RETURN,
        "TAB": win32con.VK_TAB,
        "ESC": win32con.VK_ESCAPE,
        "UP": win32con.VK_UP,
        "DOWN": win32con.VK_DOWN,
        "LEFT": win32con.VK_LEFT,
        "RIGHT": win32con.VK_RIGHT,
        "CTRL": win32con.VK_CONTROL,
        "SHIFT": win32con.VK_SHIFT,
        "ALT": win32con.VK_MENU,
    }

    def key_name_to_vk(key_name):
        key_name = str(key_name).strip().upper()
        if not key_name:
            raise ValueError("按键不能为空")
        if key_name in SPECIAL_KEYS:
            return SPECIAL_KEYS[key_name]
        if len(key_name) == 1 and ("A" <= key_name <= "Z" or "0" <= key_name <= "9"):
            return ord(key_name)
        if key_name.startswith("F") and key_name[1:].isdigit():
            number = int(key_name[1:])
            if 1 <= number <= 12:
                return win32con.VK_F1 + number - 1
        raise ValueError(f"不支持的按键: {key_name}")

    def normalize_movement_actions(actions):
        normalized = []
        for action in actions:
            key_name = str(action.get("key", "")).strip().upper()
            if not key_name:
                continue
            duration = float(action.get("duration", 0.05))
            count = int(action.get("count", 1))
            if duration < 0:
                raise ValueError("长按时长不能小于 0")
            if count < 0:
                raise ValueError("次数不能小于 0")
            key_name_to_vk(key_name)
            if count == 0:
                continue
            normalized.append({"key": key_name, "duration": duration, "count": count})
        return normalized

    def movement_loop(hwnd, match_event, movement_actions):
        movement_actions = normalize_movement_actions(movement_actions)
        update_log("开始执行未到达关卡前的按键动作。")
        while is_running and not match_event.is_set():
            for action in movement_actions:
                vk = key_name_to_vk(action["key"])
                for _ in range(action["count"]):
                    send_key_down(hwnd, vk)
                    completed = wait_until_matched(match_event, action["duration"])
                    send_key_up(hwnd, vk)
                    if not completed or match_event.is_set() or not is_running:
                        break
                    interruptible_sleep(0.08, match_event=match_event)
                if match_event.is_set() or not is_running:
                    break
            interruptible_sleep(0.2, match_event=match_event)
        update_log("按键动作已停止。")

    def img_path(filename):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "img", filename)
        if os.path.exists(path):
            return path
        png_png_path = path + ".png"
        if filename.endswith(".png") and os.path.exists(png_png_path):
            return png_png_path
        return path

    def app_dir():
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def config_path():
        return os.path.join(app_dir(), "config.json")

    def load_config():
        path = config_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config():
        data = {
            "match": match_var.get(),
            "action": action_var.get(),
            "arrive_click_x": arrive_click_x_var.get(),
            "arrive_click_y": arrive_click_y_var.get(),
            "save_confirm_x": save_confirm_x_var.get(),
            "save_confirm_y": save_confirm_y_var.get(),
            "enable_movement": enable_movement_var.get(),
            "resolution_width": resolution_width_var.get(),
            "resolution_height": resolution_height_var.get(),
            "lock_resolution_after_modify": lock_resolution_after_modify_var.get(),
            "movement_actions": collect_movement_actions(),
        }
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def collect_movement_actions():
        actions = []
        for key_var, duration_var, count_var in movement_action_vars:
            key_name = key_var.get().strip().upper()
            if not key_name:
                continue
            actions.append({
                "key": key_name,
                "duration": duration_var.get().strip(),
                "count": count_var.get().strip(),
            })
        return normalize_movement_actions(actions)

    def get_client_resolution(hwnd):
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        return right - left, bottom - top

    def set_client_resolution(hwnd, width, height):
        window_left, window_top, _, _ = win32gui.GetWindowRect(hwnd)
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        rect = ctypes.wintypes.RECT(0, 0, int(width), int(height))
        ctypes.windll.user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
        outer_width = rect.right - rect.left
        outer_height = rect.bottom - rect.top
        for _ in range(4):
            win32gui.MoveWindow(hwnd, window_left, window_top, outer_width, outer_height, True)
            actual_width, actual_height = get_client_resolution(hwnd)
            width_delta = int(width) - actual_width
            height_delta = int(height) - actual_height
            if width_delta == 0 and height_delta == 0:
                return actual_width, actual_height
            outer_width += width_delta
            outer_height += height_delta
        return get_client_resolution(hwnd)

    def refresh_window_frame(hwnd):
        win32gui.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED,
        )

    def restore_locked_resolution_window():
        global locked_resolution_hwnd, locked_window_style, locked_window_ex_style
        if locked_resolution_hwnd and win32gui.IsWindow(locked_resolution_hwnd):
            win32gui.SetWindowLong(locked_resolution_hwnd, win32con.GWL_STYLE, locked_window_style)
            win32gui.SetWindowLong(locked_resolution_hwnd, win32con.GWL_EXSTYLE, locked_window_ex_style)
            refresh_window_frame(locked_resolution_hwnd)
        locked_resolution_hwnd = None
        locked_window_style = None
        locked_window_ex_style = None

    def lock_window_manual_resize(hwnd):
        global locked_resolution_hwnd, locked_window_style, locked_window_ex_style
        if locked_resolution_hwnd == hwnd:
            return
        restore_locked_resolution_window()
        locked_resolution_hwnd = hwnd
        locked_window_style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        locked_window_ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        locked_style = locked_window_style & ~win32con.WS_THICKFRAME & ~win32con.WS_MAXIMIZEBOX
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, locked_style)
        refresh_window_frame(hwnd)

    def find_game_window():
        return win32gui.FindWindow(None, "指尖无双")

    def update_resolution_status(hwnd=None):
        if hwnd is None:
            hwnd = find_game_window()
        if not hwnd:
            resolution_status_var.set("当前窗口分辨率：未找到窗口")
            return None
        width, height = get_client_resolution(hwnd)
        resolution_status_var.set(f"当前窗口分辨率：{width} x {height}")
        return width, height

    def modify_resolution():
        try:
            width = int(resolution_width_var.get())
            height = int(resolution_height_var.get())
            if width <= 0 or height <= 0:
                raise ValueError("分辨率必须大于 0")
        except ValueError as exc:
            messagebox.showwarning("警告", f"分辨率格式错误：{exc}")
            return

        hwnd = find_game_window()
        if not hwnd:
            messagebox.showwarning("警告", "未找到指尖无双窗口")
            update_resolution_status(None)
            return

        actual_width, actual_height = set_client_resolution(hwnd, width, height)
        resolution_status_var.set(f"当前窗口分辨率：{actual_width} x {actual_height}")
        update_log(f"窗口分辨率已修改为 {actual_width} x {actual_height}")
        save_config()
        if lock_resolution_after_modify_var.get():
            lock_window_manual_resize(hwnd)
            update_log("已锁定目标窗口手动调整大小")
        else:
            restore_locked_resolution_window()

    def request_access_once():
        url = "http://www.pandahome023.cn/analysis/api.php?id=161"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "text/plain,*/*",
                    "Connection": "close",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                status_code = response.getcode()
                content = response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            return False, f"接口校验失败: HTTP {exc.code}", True
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return False, f"接口连接失败: {exc}", False

        if status_code != 200:
            return False, f"接口校验失败: HTTP {status_code}", True
        if "禁止访问" in content:
            return False, "接口返回禁止访问，任务已停止。", True
        return True, "接口校验通过。", True

    def check_access_allowed():
        result_queue = queue.Queue()
        cancel_event = threading.Event()
        status_var = tk.StringVar(value="正在连接接口，请稍候...")

        loading = tk.Toplevel(root)
        loading.title("接口校验")
        loading.resizable(False, False)
        loading.attributes("-topmost", True)
        loading.transient(root)
        loading.grab_set()

        frame = ttk.Frame(loading, padding=(22, 16, 22, 16))
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, textvariable=status_var, wraplength=360, justify=tk.LEFT).grid(
            row=0, column=0, sticky=tk.W
        )

        def cancel_check():
            cancel_event.set()
            result_queue.put((False, "接口校验已取消。"))
            loading.destroy()

        ttk.Button(frame, text="取消", command=cancel_check).grid(row=1, column=0, sticky=tk.E, pady=(12, 0))
        loading.protocol("WM_DELETE_WINDOW", cancel_check)
        loading.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - loading.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - loading.winfo_height()) // 2
        loading.geometry(f"+{max(0, x)}+{max(0, y)}")

        def worker():
            attempt = 1
            while not cancel_event.is_set():
                root.after(0, status_var.set, f"正在连接接口，第 {attempt} 次尝试...")
                allowed, message, connected = request_access_once()
                if connected:
                    result_queue.put((allowed, message))
                    root.after(0, loading.destroy)
                    return
                root.after(0, status_var.set, f"{message}\n10 秒后自动重试...")
                for _ in range(100):
                    if cancel_event.is_set():
                        return
                    time.sleep(0.1)
                attempt += 1

        threading.Thread(target=worker, daemon=True).start()
        root.wait_window(loading)
        try:
            return result_queue.get_nowait()
        except queue.Empty:
            return False, "接口校验已取消。"

    def verify_author_channel(reason):
        dialog = tk.Toplevel(root)
        dialog.title("作者通道")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.transient(root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=(18, 14, 18, 14))
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="接口校验未通过").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        ttk.Label(frame, text=reason, wraplength=360, justify=tk.LEFT).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )
        ttk.Label(frame, text="作者密码").grid(row=2, column=0, padx=(0, 8), sticky=tk.E)

        password_var = tk.StringVar()
        password_entry = ttk.Entry(frame, textvariable=password_var, width=28, show="*")
        password_entry.grid(row=2, column=1, sticky=tk.EW)

        result = {"allowed": False}

        def confirm():
            password_hash = hashlib.sha256(password_var.get().encode("utf-8")).hexdigest()
            if password_hash == AUTHOR_PASSWORD_SHA256:
                result["allowed"] = True
                dialog.destroy()
            else:
                messagebox.showwarning("作者通道", "密码错误", parent=dialog)
                password_var.set("")
                password_entry.focus_set()

        def cancel():
            dialog.destroy()

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=1, sticky=tk.E, pady=(12, 0))
        ttk.Button(button_frame, text="确定", command=confirm).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_frame, text="取消", command=cancel).pack(side=tk.LEFT)

        dialog.bind("<Return>", lambda _event: confirm())
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - dialog.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        password_entry.focus_set()
        root.wait_window(dialog)
        return result["allowed"]

    # ==========================================
    # 全局控制变量与关卡换算逻辑
    # ==========================================
    is_running = False
    author_channel_unlocked = False
    current_match_count = 0
    locked_resolution_hwnd = None
    locked_window_style = None
    locked_window_ex_style = None

    def count_to_stage(count):
        chapter = (count // 4) + 1
        sub_index = count % 4
        sub_map = {0: "1", 1: "2", 2: "3", 3: "boss"}
        return f"{chapter}-{sub_map[sub_index]}"

    def stage_to_count(chapter, sub_stage):
        sub_map = {"1": 0, "2": 1, "3": 2, "boss": 3}
        return (int(chapter) - 1) * 4 + sub_map[sub_stage]

    # ==========================================
    # 后台识别线程核心逻辑
    # ==========================================
    def recognition_loop(*args):
        global is_running
        click_x = 52
        click_y = 993
        save_confirm_x = 280
        save_confirm_y = 579
        enable_movement = False
        movement_actions = DEFAULT_MOVEMENT_ACTIONS
        if len(args) == 9:
            target_title, trigger_template_path, match_name, click_x, click_y, save_confirm_x, save_confirm_y, enable_movement, movement_actions = args
        elif len(args) == 8:
            target_title, trigger_template_path, match_name, click_x, click_y, save_confirm_x, save_confirm_y, enable_movement = args
        elif len(args) == 7:
            target_title, trigger_template_path, match_name, click_x, click_y, save_confirm_x, save_confirm_y = args
        elif len(args) == 5:
            target_title, trigger_template_path, match_name, click_x, click_y = args
        elif len(args) == 3 and isinstance(args[0], str):
            target_title, trigger_template_path, match_name = args
        elif len(args) == 3:
            _, target_title, _ = args
            trigger_template_path = img_path("22-1.png")
            match_name = "22-1"
        else:
            target_title, trigger_template_path = args
            match_name = trigger_template_path.rsplit("/", 1)[-1].replace(".png", "")
        
        hwnd = win32gui.FindWindow(None, target_title)
        if not hwnd:
            update_log(f"❌ 错误: 未找到标题为 '{target_title}' 的窗口！")
            is_running = False
            btn_start.config(state=tk.NORMAL)
            btn_stop.config(state=tk.DISABLED)
            return

        update_log(f"成功获取句柄: {hwnd}，开始后台挂机...")
        match_event = threading.Event()
        if enable_movement:
            movement_thread = threading.Thread(
                target=movement_loop,
                args=(hwnd, match_event, movement_actions),
                daemon=True
            )
            movement_thread.start()
        else:
            update_log("未启用未匹配期间按键动作。")
        
        def click_template_center(template_path, action_name):
            screen_img = capture_window_to_cv2(hwnd)
            if screen_img is None:
                update_log(f"{action_name}: 截图失败，无法识别。")
                return False

            match_result = find_template(screen_img, template_path, threshold=0.8)
            if not match_result:
                update_log(f"{action_name}: 未识别到 {template_path}。")
                return False

            center_x, center_y = match_result["center"]
            update_log(f"{action_name}: 识别成功，点击中心点 {match_result['center']}。")
            click_relative_coordinate(hwnd, center_x, center_y)
            return True

        while is_running:
            update_log(f"检测是否到达{match_name}关卡")
            screen_img = capture_window_to_cv2(hwnd)
            if screen_img is None:
                interruptible_sleep(0.2, match_event=match_event)
                continue

            match_result = find_template(
                screen_img,
                trigger_template_path,
                threshold=0.88,
                strict=True,
                edge_threshold=0.45,
                focus_threshold=0.82
            )
            if not match_result:
                interruptible_sleep(0.2, match_event=match_event)
                continue

            match_event.set()
            update_log(f"已到达{match_name}关卡，点击 ({click_x}, {click_y})。")
            click_relative_coordinate(hwnd, click_x, click_y)
            if not interruptible_sleep(1):
                break

            action = action_var.get()
            if action == "存档":
                if click_template_center(img_path("chundang_.png"), "存档"):
                    if not interruptible_sleep(0.5):
                        break
                    # 存档确定
                    update_log(f"点击存档确定坐标 ({save_confirm_x}, {save_confirm_y})。")
                    click_relative_coordinate(hwnd, save_confirm_x, save_confirm_y)
                update_log("存档流程完成，自动停止脚本。")
            elif action == "结算":
                if click_template_center(img_path("jiesuan_.png"), "结算"):
                    update_log("结算流程完成。")
            else:
                update_log(f"未知动作: {action}，请在下拉栏选择“结算”或“存档”。")

            is_running = False
            break

        btn_start.config(state=tk.NORMAL)
        btn_stop.config(state=tk.DISABLED)
        return

        while is_running:
            # 【判断是否到达目标关卡】
            if current_match_count >= target_count:
                update_log(f"🎉 已达到目标关卡: {count_to_stage(current_match_count)}")
                update_log("等待 5 秒后执行最终操作...")
                
                # 延时 5 秒 (切分为小段，防止卡死 UI)
                for _ in range(5):
                    if not is_running: break
                    time.sleep(1)
                    
                if not is_running: break # 用户强行停止
                
                # 1. 延时5秒后，点击固定位置 (49, 995)
                update_log("执行前置点击 (49, 995)...")
                click_relative_coordinate(hwnd, 49, 995)
                time.sleep(1) # 停顿1秒等待 UI 响应
                
                # 2. 根据用户设置执行最终动作
                action = action_var.get()
                if action == "结算":
                    update_log("执行用户指令: 结算 (123, 732)...")
                    click_relative_coordinate(hwnd, 123, 732)
                elif action == "存档":
                    update_log("执行用户指令: 存档 (284, 734)...")
                    click_relative_coordinate(hwnd, 284, 734)
                else:
                    update_log("用户选择无操作，跳过结算/存档。")
                    
                update_log("✅ 目标关卡所有操作已完成，自动停止！")
                is_running = False
                break

            current_stage = count_to_stage(current_match_count)
            update_log(f"正在寻找模板... (当前: {current_stage} | 识别次数: {current_match_count})")
            
            # 【执行截图与匹配】
            screen_img = capture_window_to_cv2(hwnd)
            if screen_img is not None:
                match_result = find_template(screen_img, template_path, threshold=0.8)
                
                if match_result:
                    update_log(f"✅ {current_stage} 匹配成功！目标坐标: {match_result['center']}")
                    
                    # 如果你想在每次匹配到时都点击目标，取消下面这行的注释:
                    # click_relative_coordinate(hwnd, match_result['center'][0], match_result['center'][1])
                    
                    current_match_count += 1
                    
                    # 如果达到目标，跳过本轮等待，直接进入下一轮执行结语动作
                    if current_match_count >= target_count:
                        continue
                    
                    next_stage = count_to_stage(current_match_count)
                    
                    # 读取 UI 上的等待秒数配置
                    try:
                        delay_seconds = int(delay_var.get())
                    except ValueError:
                        delay_seconds = 60
                        update_log("等待时间格式错误，使用默认60秒。")
                        
                    update_log(f"准备进入 {next_stage}。挂机等待 {delay_seconds} 秒...")
                    
                    for _ in range(delay_seconds):
                        if not is_running: break
                        time.sleep(1)
                else:
                    time.sleep(2) # 没找到模板，等2秒
            else:
                time.sleep(2) # 截图失败，等2秒
                
        # 收尾工作，恢复 UI 按钮状态
        btn_start.config(state=tk.NORMAL)
        btn_stop.config(state=tk.DISABLED)

    # ==========================================
    # UI 界面控制与布局
    # ==========================================
    def start_bot():
        global is_running, author_channel_unlocked
        allowed, access_msg = check_access_allowed()
        if not allowed:
            if author_channel_unlocked:
                access_msg = f"作者通道已保持：{access_msg}"
            elif verify_author_channel(access_msg):
                author_channel_unlocked = True
                access_msg = f"作者通道已通过：{access_msg}"
            else:
                messagebox.showwarning("禁止访问", access_msg)
                return

        if action_var.get() not in ("结算", "存档"):
            messagebox.showwarning("警告", "请先选择结算或存档识别。")
            return

        match_name = match_var.get()
        match_templates = {
            "25-2": img_path("25-2_.png"),
            "30-2": img_path("30-2_.png"),
            "40-2": img_path("40-2_.png"),
        }
        if match_name not in match_templates:
            messagebox.showwarning("警告", "请先选择匹配图片。")
            return

        trigger_template_path = match_templates[match_name]
        try:
            arrive_click_x = int(arrive_click_x_var.get())
            arrive_click_y = int(arrive_click_y_var.get())
            save_confirm_x = int(save_confirm_x_var.get())
            save_confirm_y = int(save_confirm_y_var.get())
            enable_movement = enable_movement_var.get()
            movement_actions = collect_movement_actions()
            if enable_movement and not movement_actions:
                raise ValueError("请至少填写一行动作配置")
        except ValueError as exc:
            messagebox.showwarning("警告", "坐标必须是整数。")
            return
        save_config()
        hwnd = find_game_window()
        update_resolution_status(hwnd)

        is_running = True
        btn_start.config(state=tk.DISABLED)
        btn_stop.config(state=tk.NORMAL)
        text_log.delete(1.0, tk.END)
        update_log(access_msg)

        t = threading.Thread(
            target=recognition_loop,
            args=("指尖无双", trigger_template_path, match_name, arrive_click_x, arrive_click_y, save_confirm_x, save_confirm_y, enable_movement, movement_actions),
            daemon=True
        )
        t.start()
        return

        chapter = combo_chapter.get()
        sub_stage = combo_sub.get()
        
        if not chapter or not sub_stage:
            messagebox.showwarning("警告", "请先选择目标关卡！")
            return
            
        target_count = stage_to_count(chapter, sub_stage)
        is_running = True
        current_match_count = 0  
        
        btn_start.config(state=tk.DISABLED)
        btn_stop.config(state=tk.NORMAL)
        text_log.delete(1.0, tk.END)
        
        # 启动后台线程 (确保你的 target.png 路径正确)
        t = threading.Thread(
            target=recognition_loop, 
            args=(target_count, "指尖无双", img_path("jin.png")), 
            daemon=True
        )
        t.start()

    def stop_bot():
        global is_running
        is_running = False
        update_log("⏹ 正在手动停止脚本...")
        btn_stop.config(state=tk.DISABLED)

    def update_log(msg):
        text_log.insert(tk.END, msg + "\n")
        text_log.see(tk.END)

    # --- 主窗口设置 ---
    root = tk.Tk()
    root.title("指尖无双 - 自动化工具")
    root.geometry("680x760")
    root.minsize(660, 700)
    root.attributes('-topmost', True) # 保持窗口置顶

    style = ttk.Style()
    style.configure("Title.TLabel", font=("Microsoft YaHei UI", 16, "bold"))
    style.configure("Section.TLabelframe.Label", font=("Microsoft YaHei UI", 10, "bold"))
    style.configure("Primary.TButton", padding=(18, 6))
    style.configure("Field.TLabel", padding=(0, 2))

    # 变量绑定
    saved_config = load_config()
    delay_var = tk.StringVar(value="60")   # 默认延时60秒
    action_var = tk.StringVar(value=saved_config.get("action", "结算")) # 默认操作
    match_var = tk.StringVar(value=saved_config.get("match", "30-2"))
    arrive_click_x_var = tk.StringVar(value=str(saved_config.get("arrive_click_x", "51")))
    arrive_click_y_var = tk.StringVar(value=str(saved_config.get("arrive_click_y", "925")))
    save_confirm_x_var = tk.StringVar(value=str(saved_config.get("save_confirm_x", "257")))
    save_confirm_y_var = tk.StringVar(value=str(saved_config.get("save_confirm_y", "545")))
    enable_movement_var = tk.BooleanVar(value=bool(saved_config.get("enable_movement", True)))
    resolution_width_var = tk.StringVar(value=str(saved_config.get("resolution_width", "526")))
    resolution_height_var = tk.StringVar(value=str(saved_config.get("resolution_height", "977")))
    lock_resolution_after_modify_var = tk.BooleanVar(value=bool(saved_config.get("lock_resolution_after_modify", False)))
    resolution_status_var = tk.StringVar(value="当前窗口分辨率：未读取")
    saved_movement_actions = saved_config.get("movement_actions", DEFAULT_MOVEMENT_ACTIONS)
    if not isinstance(saved_movement_actions, list) or not saved_movement_actions:
        saved_movement_actions = DEFAULT_MOVEMENT_ACTIONS
    movement_action_vars = []
    for index in range(6):
        action = saved_movement_actions[index] if index < len(saved_movement_actions) else {}
        movement_action_vars.append((
            tk.StringVar(value=str(action.get("key", ""))),
            tk.StringVar(value=str(action.get("duration", ""))),
            tk.StringVar(value=str(action.get("count", ""))),
        ))
    main_frame = ttk.Frame(root, padding=(16, 14, 16, 14))
    main_frame.pack(fill=tk.BOTH, expand=True)

    main_frame.columnconfigure(0, weight=1)

    ttk.Label(main_frame, text="指尖无双自动化工具", style="Title.TLabel").grid(row=0, column=0, sticky=tk.W, pady=(0, 14))

    frame_settings = ttk.LabelFrame(main_frame, text="运行设置", padding=(18, 14), style="Section.TLabelframe")
    frame_settings.grid(row=1, column=0, sticky=tk.EW)
    frame_settings.columnconfigure(1, weight=1)
    frame_settings.columnconfigure(3, weight=1)

    ttk.Label(frame_settings, text="检测关卡", style="Field.TLabel").grid(row=0, column=0, padx=(0, 10), pady=8, sticky=tk.E)
    combo_match = ttk.Combobox(frame_settings, textvariable=match_var, values=["25-2", "30-2", "40-2"], width=16, state="readonly")
    combo_match.grid(row=0, column=1, padx=(0, 24), pady=8, sticky=tk.W)
    combo_match.set(match_var.get() if match_var.get() in ("25-2", "30-2", "40-2") else "30-2")

    ttk.Label(frame_settings, text="游戏暂停坐标", style="Field.TLabel").grid(row=0, column=2, padx=(0, 10), pady=8, sticky=tk.E)
    frame_arrive_click = ttk.Frame(frame_settings)
    frame_arrive_click.grid(row=0, column=3, pady=8, sticky=tk.W)
    ttk.Label(frame_arrive_click, text="X").pack(side=tk.LEFT)
    ttk.Entry(frame_arrive_click, textvariable=arrive_click_x_var, width=8).pack(side=tk.LEFT, padx=(4, 12))
    ttk.Label(frame_arrive_click, text="Y").pack(side=tk.LEFT)
    ttk.Entry(frame_arrive_click, textvariable=arrive_click_y_var, width=8).pack(side=tk.LEFT, padx=(4, 0))

    ttk.Label(frame_settings, text="到达后执行动作", style="Field.TLabel").grid(row=1, column=0, padx=(0, 10), pady=8, sticky=tk.E)
    combo_action = ttk.Combobox(frame_settings, textvariable=action_var, values=["结算", "存档"], width=16, state="readonly")
    combo_action.grid(row=1, column=1, padx=(0, 24), pady=8, sticky=tk.W)
    combo_action.set(action_var.get() if action_var.get() in ("结算", "存档") else "结算")

    ttk.Label(frame_settings, text="存档确定坐标", style="Field.TLabel").grid(row=1, column=2, padx=(0, 10), pady=8, sticky=tk.E)
    frame_save_confirm = ttk.Frame(frame_settings)
    frame_save_confirm.grid(row=1, column=3, pady=8, sticky=tk.W)
    ttk.Label(frame_save_confirm, text="X").pack(side=tk.LEFT)
    ttk.Entry(frame_save_confirm, textvariable=save_confirm_x_var, width=8).pack(side=tk.LEFT, padx=(4, 12))
    ttk.Label(frame_save_confirm, text="Y").pack(side=tk.LEFT)
    ttk.Entry(frame_save_confirm, textvariable=save_confirm_y_var, width=8).pack(side=tk.LEFT, padx=(4, 0))

    ttk.Label(frame_settings, text="动作选项", style="Field.TLabel").grid(row=2, column=0, padx=(0, 10), pady=(10, 2), sticky=tk.E)
    ttk.Checkbutton(
        frame_settings,
        text="开启操作流程",
        variable=enable_movement_var
    ).grid(row=2, column=1, columnspan=3, pady=(10, 2), sticky=tk.W)

    ttk.Label(frame_settings, text="窗口分辨率", style="Field.TLabel").grid(row=3, column=0, padx=(0, 10), pady=8, sticky=tk.E)
    frame_resolution = ttk.Frame(frame_settings)
    frame_resolution.grid(row=3, column=1, padx=(0, 24), pady=8, sticky=tk.W)
    ttk.Entry(frame_resolution, textvariable=resolution_width_var, width=8).pack(side=tk.LEFT)
    ttk.Label(frame_resolution, text="x").pack(side=tk.LEFT, padx=6)
    ttk.Entry(frame_resolution, textvariable=resolution_height_var, width=8).pack(side=tk.LEFT)

    btn_resolution = ttk.Button(frame_settings, text="修改分辨率", command=modify_resolution)
    btn_resolution.grid(row=3, column=2, padx=(0, 10), pady=8, sticky=tk.W)

    ttk.Checkbutton(
        frame_settings,
        text="修改后锁定窗口，禁止手动调整",
        variable=lock_resolution_after_modify_var
    ).grid(row=3, column=3, pady=8, sticky=tk.W)

    ttk.Label(frame_settings, textvariable=resolution_status_var).grid(
        row=4, column=1, columnspan=3, pady=(0, 4), sticky=tk.W
    )

    frame_actions = ttk.LabelFrame(main_frame, text="操作流程配置", padding=(18, 12), style="Section.TLabelframe")
    frame_actions.grid(row=2, column=0, sticky=tk.EW, pady=(12, 0))
    frame_actions.columnconfigure(1, weight=1)

    ttk.Label(frame_actions, text="步骤", style="Field.TLabel").grid(row=0, column=0, padx=(0, 10), pady=(0, 6), sticky=tk.W)
    ttk.Label(frame_actions, text="按键", style="Field.TLabel").grid(row=0, column=1, padx=(0, 10), pady=(0, 6), sticky=tk.W)
    ttk.Label(frame_actions, text="长按秒数", style="Field.TLabel").grid(row=0, column=2, padx=(0, 10), pady=(0, 6), sticky=tk.W)
    ttk.Label(frame_actions, text="次数", style="Field.TLabel").grid(row=0, column=3, pady=(0, 6), sticky=tk.W)

    for index, (key_var, duration_var, count_var) in enumerate(movement_action_vars, start=1):
        ttk.Label(frame_actions, text=str(index)).grid(row=index, column=0, padx=(0, 10), pady=3, sticky=tk.W)
        ttk.Combobox(
            frame_actions,
            textvariable=key_var,
            values=["D", "A", "F", "1", "2", "3", "4", "SPACE", "ENTER", "TAB", "ESC", "UP", "DOWN", "LEFT", "RIGHT"],
            width=12,
        ).grid(row=index, column=1, padx=(0, 10), pady=3, sticky=tk.W)
        ttk.Entry(frame_actions, textvariable=duration_var, width=10).grid(row=index, column=2, padx=(0, 10), pady=3, sticky=tk.W)
        ttk.Entry(frame_actions, textvariable=count_var, width=8).grid(row=index, column=3, pady=3, sticky=tk.W)

    frame_btns = ttk.Frame(main_frame)
    frame_btns.grid(row=3, column=0, pady=(16, 14))
    btn_start = tk.Button(frame_btns, text="开始运行", bg="lightgreen", width=14, command=start_bot)
    btn_start.pack(side=tk.LEFT, padx=10)
    btn_stop = tk.Button(frame_btns, text="停止", bg="pink", width=14, command=stop_bot, state=tk.DISABLED)
    btn_stop.pack(side=tk.LEFT, padx=10)

    frame_log = ttk.LabelFrame(main_frame, text="运行日志", padding=8, style="Section.TLabelframe")
    frame_log.grid(row=4, column=0, sticky=tk.NSEW)
    main_frame.rowconfigure(4, weight=1)
    text_log = tk.Text(frame_log, height=9, font=("Consolas", 9), relief=tk.FLAT)
    text_log.pack(fill=tk.BOTH, expand=True)
    text_log.insert(tk.END, startup_license_message + "\n")

    def on_close():
        try:
            save_config()
        except Exception:
            pass
        restore_locked_resolution_window()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # 启动界面
    root.mainloop()
