"""通过后端API导入三份真实场地数据(事务由FastAPI管理)。
流程: 上传文件 → 自动检测mapping → 确认mapping → 导入
"""
import json
import os
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8011/api/v1"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def req(method, path, token, body=None, files=None):
    url = BASE + path
    if files:
        # multipart upload
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        lines = []
        for key, (filename, filepath) in files.items():
            with open(filepath, "rb") as f:
                content = f.read()
            lines.append(f"--{boundary}".encode())
            lines.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'.encode())
            lines.append(b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            lines.append(b"")
            lines.append(content)
        lines.append(f"--{boundary}--".encode())
        body_data = b"\r\n".join(lines)
        headers = {"Authorization": f"Bearer {token}",
                   "Content-Type": f"multipart/form-data; boundary={boundary}"}
        r = urllib.request.Request(url, data=body_data, headers=headers, method=method)
    else:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        data = json.dumps(body).encode() if body else None
        r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500] if e.fp else ""
        return e.code, {"error": body}
    except Exception as e:
        return -1, {"error": str(e)}


def main():
    # 登录
    code, data = req("POST", "/auth/login", None, {"username": "admin", "password": "Demo@2026"})
    token = data["access_token"]
    print("✅ 登录成功")

    files = [
        ("data/raw/3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx", "01.云南-个旧-HM"),
        ("data/raw/2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx", "02.江苏-栖霞-OP"),
        ("data/raw/1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx", "03.农村-HMOP"),
    ]

    for relpath, site_code in files:
        fpath = os.path.join(ROOT, relpath.replace("/", os.sep))
        fname = os.path.basename(fpath)
        print(f"\n{'='*60}")
        print(f"导入: {fname} → site_code={site_code}")

        # 步骤1: 上传文件检测mapping
        code, data = req("POST", "/data/upload", token, files={"file": (fname, fpath)})
        if code != 200:
            print(f"  ❌ 上传失败: HTTP {code} {str(data)[:200]}")
            continue
        print(f"  ✅ 上传成功: {data.get('mapping_id','?')}")
        mapping_id = data.get("mapping_id")
        dest = data.get("dest")

        # 步骤2: 确认mapping并导入
        code, data = req("POST", f"/data/resolve-mapping", token,
                         {"mapping_id": mapping_id, "dest": dest,
                          "site_code": site_code, "on_conflict": "new_version"})
        if code != 200:
            print(f"  ❌ 导入失败: HTTP {code} {str(data)[:200]}")
            continue
        print(f"  ✅ 导入成功: site_id={data.get('site_id')}, "
              f"points={data.get('n_points')}, measurements={data.get('n_measurements')}")


if __name__ == "__main__":
    main()
