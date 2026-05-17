import hashlib
import re
import subprocess


PRODUCT_SALT = "zhijianwushuang"
INVALID_ID_VALUES = {
    "",
    "0",
    "none",
    "null",
    "unknown",
    "system serial number",
    "to be filled by o.e.m.",
    "to be filled by oem",
    "default string",
    "not specified",
    "not available",
    "not applicable",
}


def _run_command(args):
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _clean_value(value):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    value = value.strip(".")
    if value.lower() in INVALID_ID_VALUES:
        return ""
    if re.fullmatch(r"0+", value.replace("-", "")):
        return ""
    return value.upper()


def _windows_machine_guid():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return _clean_value(value)
    except Exception:
        return ""


def _wmic_value(alias, field):
    output = _run_command(["wmic", alias, "get", field, "/value"])
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().lower() == field.lower():
            cleaned = _clean_value(value)
            if cleaned:
                return cleaned
    return ""


def get_machine_fingerprint_parts():
    parts = {
        "machine_guid": _windows_machine_guid(),
        "csproduct_uuid": _wmic_value("csproduct", "UUID"),
    }
    return {key: value for key, value in parts.items() if value}


def get_machine_code():
    parts = get_machine_fingerprint_parts()
    stable_text = "\n".join(
        [f"product={PRODUCT_SALT}"] + [f"{key}={parts[key]}" for key in sorted(parts)]
    )
    digest = hashlib.sha256(stable_text.encode("utf-8")).hexdigest().upper()
    return f"{digest[:8]}-{digest[8:16]}"
