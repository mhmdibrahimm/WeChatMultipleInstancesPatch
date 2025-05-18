import os
import sys
import shutil
import subprocess

try:
    import winreg  # For Windows registry access
except ImportError:
    print("This script must be run on Windows (winreg not available).")
    sys.exit(1)

WECHAT_VERSION_TARGET = "3.2.1.156"

# --- Offsets of the two mutex‐check jumps to convert into JMPs ---
#   site #1: original long JZ (0F 84 46 04 00 00) at VA 0x103EFF7E → file-offset 0x003EF37E
#   site #4: original short JZ (74 2C) at VA 0x10A1089E → file-offset 0x00A0FC9E
MUTEX_OFFSETS = [
    0x003EF37E,
    0x00A0FC9E,
]

# --- Offset of the ExitProcess call to NOP out ---
#   CALL [ExitProcess] hex = FF 15 14 E4 5B 11 at VA 0x10A16578 → file-offset 0x00A15978
EXIT_OFFSET  = 0x00A15978
EXIT_OLD     = [0xFF, 0x15, 0x14, 0xE4, 0x5B, 0x11]
EXIT_NEW     = [0x90] * 6  # six NOPs

def get_wechat_install_info():
    reg_path = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\WeChat"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ) as key:
        return {
            "InstallLocation": winreg.QueryValueEx(key, "InstallLocation")[0],
            "DisplayVersion":  winreg.QueryValueEx(key, "DisplayVersion")[0],
        }

def close_wechat():
    print("Attempting to close any running WeChat instances...")
    subprocess.call(["taskkill", "/F", "/IM", "WeChat.exe"], shell=True)

def backup_dll(dll_path):
    bak = dll_path + ".bak"
    if os.path.exists(bak):
        print(f"Backup already exists: {bak}")
    else:
        print("Creating backup of WeChatWin.dll...")
        shutil.copy2(dll_path, bak)
        print(f"Backup created at: {bak}")

def patch_wechat(dll_path):
    print(f"Reading DLL: {dll_path}")
    with open(dll_path, "rb+") as f:
        # 1) Patch the mutex‐check jumps
        for off in MUTEX_OFFSETS:
            f.seek(off)
            orig = f.read(1)[0]
            if orig in (0x74, 0x75):  # JZ or JNZ
                new = 0xEB            # short JMP
                print(f"patch mutex_jump @0x{off:08X}: {hex(orig)} → {hex(new)}")
                f.seek(off)
                f.write(bytes([new]))
            else:
                print(f"skip mutex_jump @0x{off:08X}: found {hex(orig)}")

        # 2) Patch the ExitProcess call
        f.seek(EXIT_OFFSET)
        current = list(f.read(len(EXIT_OLD)))
        if current == EXIT_OLD:
            print(f"patch exit_call @0x{EXIT_OFFSET:08X}: {current} → {[hex(b) for b in EXIT_NEW]}")
            f.seek(EXIT_OFFSET)
            f.write(bytes(EXIT_NEW))
        else:
            print(f"skip exit_call @0x{EXIT_OFFSET:08X}: found {current}")

    return True

def main():
    try:
        info = get_wechat_install_info()
    except FileNotFoundError:
        print("WeChat not found in registry.")
        return
    except PermissionError:
        print("Permission denied. Run as Administrator.")
        return

    path = info["InstallLocation"]
    ver  = info["DisplayVersion"]
    print(f"Found WeChat {ver} at {path}")

    if ver != WECHAT_VERSION_TARGET:
        print(f"Warning: script built for {WECHAT_VERSION_TARGET}, you have {ver}.")
        if input("Continue? (y/N): ").lower() != "y":
            return

    dll = os.path.join(path, "WeChatWin.dll")
    if not os.path.isfile(dll):
        print(f"Cannot find DLL at {dll}")
        return

    close_wechat()
    backup_dll(dll)
    if patch_wechat(dll):
        print("Patch applied. Try launching multiple WeChat instances.")
    else:
        print("Patch did not apply cleanly.")

if __name__ == "__main__":
    main()
