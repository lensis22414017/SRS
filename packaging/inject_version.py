"""打包后用 pefile 注入 VS_VERSION_INFO 资源到 SRS.exe(PyInstaller version_file 在 onedir 下失效的兜底)。
开发者: 生态环境部土壤与农业农村生态环境监管技术中心。
用 pefile + 手工构造 RT_VERSION 资源二进制写入。
用法: python packaging/inject_version.py dist/SRS/SRS.exe
"""
import os
import sys
import struct

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pefile


def build_version_info():
    """构造 VS_VERSION_INFO 资源二进制(UTF-16, 标准格式)。"""
    # StringTable
    strings = [
        ("CompanyName", "生态环境部土壤与农业农村生态环境监管技术中心"),
        ("FileDescription", "Soil Remediation Supervision System (SRS) - Contaminated Site Ecological-Productive Function Reconstruction"),
        ("FileVersion", "1.0.1.0"),
        ("InternalName", "SRS"),
        ("LegalCopyright", "Copyright (c) 2026 生态环境部土壤与农业农村生态环境监管技术中心"),
        ("OriginalFilename", "SRS.exe"),
        ("ProductName", "SRS - Contaminated Site Supervision System"),
        ("ProductVersion", "1.0.1.0"),
        ("Comments", "v1.0.1 - Built 2026-07-18"),
    ]
    # StringTable block
    lang = b"\x09\x04\xb0\x04"  # 0x0409, 1200(0x04B0) little-endian
    string_entries = b""
    for key, val in strings:
        k = key.encode("utf-16-le") + b"\x00\x00"
        if len(k) % 4:
            k += b"\x00" * (4 - len(k) % 4)
        v = val.encode("utf-16-le") + b"\x00\x00"
        if len(v) % 4:
            v += b"\x00" * (4 - len(v) % 4)
        # wLength of value, wValueLength(chars), wType(1=text), szKey, padding, value
        entry = struct.pack("<HHH", 6 + len(k) + len(v), len(val), 1) + k + v
        while len(entry) % 4:
            entry += b"\x00"
        string_entries += entry
    # StringTable: wLength, wValueLength(0), wType(1), szKey="040904B0", padding, children
    st_key = b"0\x000\x004\x000\x009\x000\x004\x00B\x000\x00\x00\x00"  # "040904B0" UTF-16 + null
    st_header = struct.pack("<HHH", 6 + len(st_key) + len(string_entries), 0, 1) + st_key
    if len(st_header) % 4:
        st_header += b"\x00" * (4 - len(st_header) % 4)
    string_table = st_header + string_entries
    while len(string_table) % 4:
        string_table += b"\x00"

    # StringFileInfo: wLength, wValueLength(0), wType(1), szKey="StringFileInfo", padding, children
    sfi_key = "StringFileInfo".encode("utf-16-le") + b"\x00\x00"
    if len(sfi_key) % 4:
        sfi_key += b"\x00" * (4 - len(sfi_key) % 4)
    sfi = struct.pack("<HHH", 6 + len(sfi_key) + len(string_table), 0, 1) + sfi_key + string_table
    while len(sfi) % 4:
        sfi += b"\x00"

    # VarFileInfo: wLength, wValueLength(0), wType(1), szKey="VarFileInfo", padding, child Var
    var_key = b"T\x00r\x00a\x00n\x00s\x00l\x00a\x00t\x00i\x00o\x00n\x00\x00\x00"  # "Translation"
    if len(var_key) % 4:
        var_key += b"\x00" * (4 - len(var_key) % 4)
    var_value = b"\x09\x04\xb0\x04"  # 0x0409, 1200
    var = struct.pack("<HHH", 6 + len(var_key) + len(var_value), len(var_value) // 2, 0) + var_key + var_value
    while len(var) % 4:
        var += b"\x00"
    vfi_key = "VarFileInfo".encode("utf-16-le") + b"\x00\x00"
    if len(vfi_key) % 4:
        vfi_key += b"\x00" * (4 - len(vfi_key) % 4)
    vfi = struct.pack("<HHH", 6 + len(vfi_key) + len(var), 0, 1) + vfi_key + var
    while len(vfi) % 4:
        vfi += b"\x00"

    # VS_VERSION_INFO: wLength, wValueLength(sizeof VS_FIXEDFILEINFO=52), wType(0=binary), szKey="VS_VERSION_INFO", padding, FFI, children
    vvk = "VS_VERSION_INFO".encode("utf-16-le") + b"\x00\x00"
    if len(vvk) % 4:
        vvk += b"\x00" * (4 - len(vvk) % 4)
    ffi = struct.pack("<7IHH6I",
        0xFEEF04BD, 0x10000, 0x10000, 0x3F, 0, 0x40004, 1,  # signature, filever, prodver, mask, flags, OS, filetype
        0,  # subtype
        0, 0, 0, 0, 0, 0)  # date
    children = sfi + vfi
    total_len = 6 + len(vvk) + len(ffi) + len(children)
    vs = struct.pack("<HHH", total_len, 52, 0) + vvk + ffi + children
    while len(vs) % 4:
        vs += b"\x00"
    return vs


def main():
    exe_path = sys.argv[1] if len(sys.argv) > 1 else "dist/SRS/SRS.exe"
    print(f"注入版本信息到: {exe_path}")
    data = build_version_info()
    print(f"  资源大小: {len(data)} bytes")
    pe = pefile.PE(exe_path)
    # RT_VERSION = 16, 名称=1
    pe.DIRECTORY_ENTRY_RESOURCE.entries
    # 用 pefile 的 set_resource 注入
    new_rva = None
    # 删旧 RT_VERSION
    for entry in list(pe.DIRECTORY_ENTRY_RESOURCE.entries):
        if entry.id == pefile.RESOURCE_TYPE["RT_VERSION"]:
            pe.DIRECTORY_ENTRY_RESOURCE.entries.remove(entry)
    # pefile 没有 set_resource 直接API, 用 add; 改用写文件后 reparse
    # 简化: 用 pefile 写入新资源
    from pefile import RESOURCE_TYPE
    try:
        pe.add_resource(data, rt=RESOURCE_TYPE["RT_VERSION"], name=1, lang=0x0409)
        pe.write(exe_path)
        print("✅ 注入成功")
    except Exception as e:
        print(f"⚠ add_resource 失败({e}), 尝试备用写法")
        # 备用: 直接用 ResourceSectionData
        raise
    # 验证
    pe2 = pefile.PE(exe_path)
    found = any(e.id == RESOURCE_TYPE["RT_VERSION"] for e in pe2.DIRECTORY_ENTRY_RESOURCE.entries)
    print(f"  验证 RT_VERSION 存在: {found}")


if __name__ == "__main__":
    main()
