# WeChat Multi-Instance Patch (v3.2.1.156)

Enable running multiple instances of the Windows WeChat client by patching its mutex check and early-exit call.

NOTE: This patch apply only to WeChat [v3.2.1.156](https://webcdn.m.qq.com/spcmgr/download/WeChat_for_XP_SP3_To_Vista.exe). I mentioned the way to patch for version [v3.9.10.19](https://github.com/tom-snow/wechat-windows-versions/releases/tag/v3.9.10.19) in this document too. For other versions, kindly check the adaptation section.

---

## Quick Start
If you do not care about details, just run the Python script, it will patch WeChat, and you will be able to run multiple instances. Enjoy!

## Overview

By default, WeChat prevents more than one copy of itself from running at the same time. Under the hood it:

1. Calls `CreateMutexW(...)` to register a named mutex.
2. Tests the return value and, if the mutex already exists, jumps into “abort” logic.
3. Calls `ExitProcess()` to terminate the second instance.

This patch bypasses both of those safeguards:

- We turn the conditional “already-running” jump into an **unconditional** jump.
- We `NOP` out the `ExitProcess` call so the process never immediately exits.

All of this is done by binary-patching two small regions in **WeChatWin.dll**.

---

## Prerequisites

- WeChat for Windows **v3.2.1.156**, installed under `C:\Program Files (x86)\Tencent\WeChat`.
- **Administrator** privileges to overwrite `WeChatWin.dll`.
- [Ghidra](https://ghidra-sre.org/) (or another PE-aware disassembler) for locating offsets.
- Python 3+ on Windows.

---

## How It Works

### 1. Finding the Mutex-Check Offset

1. Load **WeChatWin.dll** into Ghidra’s CodeBrowser.
2. In the **Imports** tree, locate `CreateMutexW` under **KERNEL32.dll**.
3. Use “Direct References Search” to find each `CALL CreateMutexW` site.
4. In the listing, scroll to the **TEST …; JZ/JNZ** right after the call.  
5. Note the instruction’s **virtual address** (e.g. `0x103EFF7E`) and translate it to a **raw file-offset**:
   ```text
   file_offset = section_file_offset + (instruction_va − section_va_start)
    ```

6. For each mutex-check you replace the first byte of the jump:

   * `0x75` (JNZ) → `0xEB` (JMP), or
   * `0x74` (JZ)  → `0xEB` (JMP)

### 2. Disabling ExitProcess

1. In the Imports tree, find `ExitProcess`.
2. “Direct References Search” yields a `CALL [ExitProcess]` (6 bytes: `FF 15 14 E4 5B 11`).
3. Compute its file-offset same as above.
4. Overwrite all six bytes with `0x90` (NOP ×6).

---

## Disclaimer

* **Backup first!** Always keep a copy of the original `WeChatWin.dll`.
* Use this patch at your own risk. Future WeChat updates will likely change offsets.
* This is provided for educational purposes only.

---

## Patch for Version 3.9.10.19
For WeChat v3.9.10.19, only a single byte-patch is required—no ExitProcess fix is needed. You can edit the constants and the `patch_wechat` function accordingly:
```python
WECHAT_VERSION_TARGET = "3.9.10.19"
OFFSET = 0x031AE5A2  # file-offset of the mutex check in WeChatWin.dll
OLD_VALUE = 0x85     # original byte
NEW_VALUE = 0x31     # patched byte

# Keep same code from the script, only edit the constants and the following function

def patch_wechat(path):
    with open(path, "rb+") as f:
        f.seek(OFFSET)
        b = f.read(1)[0]
        if b == OLD_VALUE:
            f.seek(OFFSET)
            f.write(bytes([NEW_VALUE]))
            return True
    return False
```

---

## How to Adapt for [Other WeChat Versions](https://github.com/tom-snow/wechat-windows-versions/)

If you need to apply this multi‐instance patch to a different WeChat release—whether newer or older—the process is the same in principle, but you’ll need to discover the correct byte-offsets in that build. It might be the case that this method would not work for newer versions. Here is the general concept on how to do it:

1. **Install and Prepare**  
   - Copy the target `WeChatWin.dll` to a safe working folder.  
   - Back it up (e.g. `WeChatWin.dll.bak`).  
   - Open it in Ghidra (or your favorite PE disassembler) and let the basic analysis run.

2. **Locate the Mutex-Check Sites**  
   - In the **Symbol Tree → Imports → KERNEL32.dll**, find **CreateMutexW**.  
   - Right-click → **Direct References Search** to list all call sites.  
   - For each call:
     1. Double-click to jump to the `CALL …CreateMutexW`.  
     2. Scroll down to the **TEST RAX,RAX** (or **TEST EAX,EAX**) immediately after.  
     3. Identify the conditional jump (`JZ` or `JNZ`) that follows.

3. **Compute the Raw File Offset**  
   - Note the jump’s **virtual address** (VA), for example `0x10F0ABCD`.  
   - Open **Window → Memory Map**, find the `.text` section row:
     ```
     VAstart = <section VA start>
     FOstart = <file offset start>
     ```
   - Compute:
     ```
     file_offset = FOstart + (JUMP_VA − VAstart)
     ```
   - Alternatively, in the **Bytes** pane click **Go To → file(<offset>)** to verify.

4. **Patch the Jump**  
   - If it’s **short** (`74 xx` or `75 xx`):
     ```python
     # Overwrite the first byte only:
     f.seek(file_offset)
     f.write(b'\xEB')  # EB = short JMP
     ```
   - If it’s **long** (`0F 84 xx xx xx xx`):
     ```python
     f.seek(file_offset)
     f.write(b'\xE9')  # E9 = long JMP, leave displacement intact
     ```

5. **Locate & Patch the ExitProcess Call**  
   - In **Imports → ExitProcess**, use **Direct References Search** to find its `CALL`.  
   - Note its VA and compute its file-offset the same way.  
   - Overwrite all six bytes (`FF 15 xx xx xx xx`) with `0x90` × 6.

6. **Update Your Script**  
   - Replace the hard-coded offsets in `MUTEX_OFFSETS` and `EXIT_OFFSET` with your new values.  
   - Re-run the patch script as Administrator.


