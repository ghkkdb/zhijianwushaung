import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from machine_code import get_machine_code


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return BASE_DIR


def resource_path(filename):
    bundled_dir = getattr(sys, "_MEIPASS", "")
    if bundled_dir:
        bundled_path = os.path.join(bundled_dir, filename)
        if os.path.exists(bundled_path):
            return bundled_path
    return os.path.join(app_dir(), filename)


DEFAULT_PRIVATE_KEY = resource_path("private_key.pem")
DEFAULT_PUBLIC_KEY = os.path.join(app_dir(), "public_key.pem")
DEFAULT_LICENSE_FILE = os.path.join(app_dir(), "license.lic")


def safe_filename_part(value, fallback="client"):
    value = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(value or "").strip())
    value = value.strip("_")
    return value or fallback


def default_license_filename(machine_code="", licensed_to=""):
    owner = safe_filename_part(licensed_to, "client")
    code = safe_filename_part(machine_code, "machine")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"license_{owner}_{code}_{timestamp}.lic"


def default_license_path(machine_code="", licensed_to=""):
    return os.path.join(app_dir(), default_license_filename(machine_code, licensed_to))


def init_key(private_key_path, public_key_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(private_key_path, "wb") as f:
        f.write(private_pem)
    with open(public_key_path, "wb") as f:
        f.write(public_pem)
    print(f"已生成私钥：{private_key_path}")
    print(f"已生成公钥：{public_key_path}")
    print("如需更换密钥，请把公钥内容同步替换到 main.py 的 LICENSE_PUBLIC_KEY_PEM。")


def issue_license(private_key_path, machine_code, output_path, licensed_to="", expires_at=""):
    machine_code = machine_code.strip().upper()
    if expires_at:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        expires_at = expires.isoformat()

    payload = {
        "product": "zhijianwushuang",
        "machine_code": machine_code,
        "licensed_to": licensed_to,
        "expires_at": expires_at,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    with open(private_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)

    signature = private_key.sign(
        payload_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    license_data = {
        "payload": base64.b64encode(payload_bytes).decode("ascii"),
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(license_data, f, ensure_ascii=False, indent=2)
    print(f"已生成授权文件：{output_path}")


def prompt_text(label, default=""):
    suffix = f"（默认：{default}）" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def interactive_issue_license():
    print("=== 指尖无双授权文件生成 ===")
    print("请把客户软件弹窗中的机器码复制到这里。")
    print("")

    machine_code = ""
    while not machine_code:
        machine_code = prompt_text("请输入客户机器码").strip().upper()
        if not machine_code:
            print("机器码不能为空。")

    licensed_to = prompt_text("请输入客户名，可留空")
    expires_at = prompt_text("请输入到期时间，可留空，例如 2026-12-31T23:59:59+08:00")
    output_path = prompt_text("请输入授权文件输出路径", default_license_path(machine_code, licensed_to))

    if not os.path.exists(DEFAULT_PRIVATE_KEY):
        print(f"未找到私钥文件：{DEFAULT_PRIVATE_KEY}")
        return 1

    try:
        issue_license(DEFAULT_PRIVATE_KEY, machine_code, output_path, licensed_to, expires_at)
    except Exception as exc:
        print(f"授权文件生成失败：{exc}")
        return 1

    print("")
    print("生成完成。把 license.lic 放到客户的 zhijianwushuang.exe 同级目录即可。")
    return 0


def launch_license_ui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("指尖无双授权文件生成工具")
    root.geometry("560x330")
    root.minsize(540, 320)
    root.resizable(False, False)

    machine_code_var = tk.StringVar()
    licensed_to_var = tk.StringVar()
    expires_at_var = tk.StringVar()
    output_var = tk.StringVar(value=default_license_path())
    status_var = tk.StringVar(value="到期时间留空表示永久授权。")

    frame = ttk.Frame(root, padding=(20, 18, 20, 18))
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="授权文件生成", font=("Microsoft YaHei UI", 15, "bold")).grid(
        row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 16)
    )

    ttk.Label(frame, text="客户机器码").grid(row=1, column=0, sticky=tk.E, padx=(0, 10), pady=8)
    machine_entry = ttk.Entry(frame, textvariable=machine_code_var)
    machine_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=8)

    ttk.Label(frame, text="客户名").grid(row=2, column=0, sticky=tk.E, padx=(0, 10), pady=8)
    ttk.Entry(frame, textvariable=licensed_to_var).grid(row=2, column=1, columnspan=2, sticky=tk.EW, pady=8)

    ttk.Label(frame, text="到期时间").grid(row=3, column=0, sticky=tk.E, padx=(0, 10), pady=8)
    ttk.Entry(frame, textvariable=expires_at_var).grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=8)

    ttk.Label(frame, text="输出文件").grid(row=4, column=0, sticky=tk.E, padx=(0, 10), pady=8)
    ttk.Entry(frame, textvariable=output_var).grid(row=4, column=1, sticky=tk.EW, pady=8)

    def choose_output():
        path = filedialog.asksaveasfilename(
            title="选择授权文件保存位置",
            initialdir=app_dir(),
            initialfile="license.lic",
            defaultextension=".lic",
            filetypes=[("License file", "*.lic"), ("All files", "*.*")],
        )
        if path:
            output_var.set(path)

    ttk.Button(frame, text="浏览", command=choose_output).grid(row=4, column=2, sticky=tk.E, padx=(8, 0), pady=8)

    ttk.Label(
        frame,
        text="到期时间示例：2026-12-31T23:59:59+08:00；留空为永久授权。客户使用时文件名需改为 license.lic。",
        foreground="#555555",
    ).grid(row=5, column=1, columnspan=2, sticky=tk.W, pady=(0, 8))

    def refresh_output_path(*_):
        output_var.set(default_license_path(machine_code_var.get().strip().upper(), licensed_to_var.get().strip()))

    machine_code_var.trace_add("write", refresh_output_path)
    licensed_to_var.trace_add("write", refresh_output_path)

    def generate_license():
        machine_code = machine_code_var.get().strip().upper()
        licensed_to = licensed_to_var.get().strip()
        expires_at = expires_at_var.get().strip()
        output_path = output_var.get().strip() or default_license_path(machine_code, licensed_to)

        if not machine_code:
            messagebox.showwarning("缺少机器码", "请先输入客户机器码。")
            machine_entry.focus_set()
            return

        if not os.path.exists(DEFAULT_PRIVATE_KEY):
            messagebox.showerror("缺少私钥", f"未找到私钥文件：{DEFAULT_PRIVATE_KEY}")
            return

        try:
            issue_license(DEFAULT_PRIVATE_KEY, machine_code, output_path, licensed_to, expires_at)
        except Exception as exc:
            messagebox.showerror("生成失败", f"授权文件生成失败：{exc}")
            return

        status_var.set(f"已生成：{output_path}")
        messagebox.showinfo("生成成功", "授权文件已生成。")

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=6, column=1, columnspan=2, sticky=tk.E, pady=(12, 6))
    ttk.Button(button_frame, text="生成授权文件", command=generate_license).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(button_frame, text="退出", command=root.destroy).pack(side=tk.LEFT)

    ttk.Label(frame, textvariable=status_var, foreground="#2563eb").grid(
        row=7, column=0, columnspan=3, sticky=tk.W, pady=(8, 0)
    )

    machine_entry.focus_set()
    root.mainloop()


def main():
    if len(sys.argv) == 1:
        launch_license_ui()
        return

    parser = argparse.ArgumentParser(description="指尖无双授权工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("machine-code", help="打印当前电脑的机器码")

    init_parser = subparsers.add_parser("init-key", help="生成新的 RSA 私钥和公钥")
    init_parser.add_argument("--private-key", default=DEFAULT_PRIVATE_KEY)
    init_parser.add_argument("--public-key", default=DEFAULT_PUBLIC_KEY)

    issue_parser = subparsers.add_parser("issue", help="用私钥签发授权文件")
    issue_parser.add_argument("--machine-code", required=True)
    issue_parser.add_argument("--private-key", default=DEFAULT_PRIVATE_KEY)
    issue_parser.add_argument("--out", default="")
    issue_parser.add_argument("--licensed-to", default="")
    issue_parser.add_argument("--expires-at", default="", help="可选，例如 2026-12-31T23:59:59+08:00")

    args = parser.parse_args()
    if args.command == "machine-code":
        print(get_machine_code())
    elif args.command == "init-key":
        init_key(args.private_key, args.public_key)
    elif args.command == "issue":
        output_path = args.out or default_license_path(args.machine_code, args.licensed_to)
        issue_license(args.private_key, args.machine_code, output_path, args.licensed_to, args.expires_at)


if __name__ == "__main__":
    main()
