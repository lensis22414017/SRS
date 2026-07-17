# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 版本信息文件(独立, 供 --version-file 使用)。
开发者: 生态环境部土壤与农业农村生态环境监管技术中心。
"""
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 0, 2, 0),
        prodvers=(1, 0, 2, 0),
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    '040904B0',
                    [
                        StringStruct('CompanyName', '生态环境部土壤与农业农村生态环境监管技术中心'),
                        StringStruct('FileDescription', 'Soil Remediation Supervision System (SRS) - Contaminated Site Ecological-Productive Function Reconstruction'),
                        StringStruct('FileVersion', '1.0.2.0'),
                        StringStruct('InternalName', 'SRS'),
                        StringStruct('LegalCopyright', 'Copyright (c) 2026 生态环境部土壤与农业农村生态环境监管技术中心'),
                        StringStruct('OriginalFilename', 'SRS.exe'),
                        StringStruct('ProductName', 'SRS - Contaminated Site Supervision System'),
                        StringStruct('ProductVersion', '1.0.2.0'),
                        StringStruct('Comments', 'v1.0.2 - Built 2026-07-17'),
                    ]
                )
            ]
        ),
        VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
    ],
)
