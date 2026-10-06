# War3Studio · 魔兽争霸3 全功能资源工作台

一键打开 .w3x / .mpq 地图，浏览并导出资源、预览贴图与音频、解包 SLK 数据（物品/技能/装备）。

- 打开地图（含重制版 HM3W 头）
- **资源树浏览**：按目录分组列出全部资源（模型/贴图/音频/脚本/数据）
- **预览**：BLP 贴图 → PNG 即时预览、音频播放、文本查看
- **导出**：选中或全部资源批量导出（模型/贴图/音频/任意文件）
- **SLK 解包**：物品清单、技能表、装备数据 → JSON / Markdown

## 界面

- `打开`：选择 .w3x 或 .mpq
- 左侧资源树：分组浏览所有文件
- 选中文件即右侧预览（贴图 / 文本 / 音频自动播放）
- `导出选中` / `全部导出`：把资源写到指定目录
- `SLK 解包`：输出 `_解包输出`（物品数据.json、物品清单.md、技能表.json、slk 表）

## 使用

```
War3Studio.exe            # 打开后点「打开地图」
War3Studio.exe map.w3x    # 或直接拖 .w3x 到 exe 上启动
```

## 对 SLK 优化图（无 listfile）的支持

KK / SLK 优化图会删除 `(listfile)`，普通方式无法列出文件名。本工具优先用内置 MPQ 读取；
若检测到系统装有 **Node.js 及 `@wowserhq/stormjs`**，会自动用 StormLib 枚举全部资源（含隐藏/加密图中的文件），并提供完整资源树与导出。无 Node 时，普通地图仍可完整使用，SLK优化图可正常「SLK 解包」与按已知路径读取。

## 运行/打包

```powershell
# 运行
python war3_studio.py

# 打包（需 PyInstaller）
pip install pyinstaller pillow
python -m PyInstaller --noconfirm --onefile --windowed --name War3Studio \
  --add-data "unpack.py;." --add-data "mpyq.py;." --add-data "内置技能名.json;." \
  war3_studio.py
```

## 文件

| 文件 | 说明 |
|---|---|
| `war3_studio.py` | 主程序（tkinter GUI） |
| `war3core.py` | MPQ 打开 / 文件读取 / BLP→PNG 解码 |
| `unpack.py` | SLK 数据解包逻辑 |
| `mpyq.py` | MPQ 读取模块 |
| `内置技能名.json` | 官方技能中文名表 |
| `War3Studio.exe` | Windows 打包版（Release 下载） |

## 依赖

- Python 3.9+，`pillow`
- （可选）Node.js + `@wowserhq/stormjs` 以完整枚举 SLK优化图

> AI生成
