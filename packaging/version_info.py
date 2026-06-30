# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 版本信息文件(独立, 供 --version-file 使用)。
开发者: 浙江大学环境与资源学院王玮实验室 (Zhejiang University, College of Environmental & Resource Sciences, Wang Wei Lab; 简写 ZJU WW Lab)。
"""
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(0, 1, 0, 0),
        prodvers=(0, 1, 0, 0),
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
                        StringStruct('CompanyName', 'Zhejiang University, College of Environmental & Resource Sciences, Wang Wei Lab (ZJU WW Lab)'),
                        StringStruct('FileDescription', 'Soil Remediation Supervision System (SRS) - Contaminated Site Ecological-Productive Function Reconstruction'),
                        StringStruct('FileVersion', '0.1.0.0'),
                        StringStruct('InternalName', 'SRS'),
                        StringStruct('LegalCopyright', 'Copyright (c) 2026 ZJU WW Lab. Licensed under MIT.'),
                        StringStruct('OriginalFilename', 'SRS.exe'),
                        StringStruct('ProductName', 'SRS - Contaminated Site Supervision System'),
                        StringStruct('ProductVersion', '0.1.0.0'),
                        StringStruct('Comments', 'MVP v0.1.0 - Built 2026-06-30'),
                    ]
                )
            ]
        ),
        VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
    ],
)
