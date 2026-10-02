# W3X 一键解包工具（W3X Unpacker）

一款**傻瓜式**的魔兽争霸3（含重制版）自制地图解包工具。把 `.w3x` 拖进来，一键解出地图里藏着的**装备 / 技能 / 数值**数据。

针对「SLK 优化图」设计——这类地图的装备/技能数据存在 `Units\ItemStrings.txt`、`itemdata.slk`、`abilitydata.slk` 里，普通工具（如 `xdep`）解不开。本工具用 `mpyq` 按正确路径直接读取，全量提取，并自动补全技能中文名。

## ✨ 功能特性

- **自动识别重制版头**：自动剥离 `HM3W` 重制版封装头，原始 `.w3x` 直接拖入即可
- **全量提取**：`ItemStrings.txt` / `itemdata.slk` / `abilitydata.slk` / `unitbalance.slk` / `war3map.w3a`
- **装备提取**：名称 / 稀有度 / 槽位 / 属性（Ubertip）一条不漏，去除魔兽颜色码
- **技能数值提取**：技能表含 冷却 / 消耗 / 范围 / 射程 / 数值 字段
- **技能名补全**：三路技能名——
  1. `war3map.w3a` 内嵌自定义技能名
  2. 官方内置技能中文名库（`内置技能名.json`，921 条）
  3. 地图文本 `AbilityStrings.txt` / `war3map.wts`（若存在）
- **解包报告含技能表**：`解包报告.html` 列出技能名称与数值
- **三种输出**：`解包报告.html` · `物品清单.md` · `物品数据.json`，另附原始 SLK 与数值表 JSON
- **图形界面**：拖拽即用、多地图队列、实时日志、一键打开输出
- **绿色免安装**：单文件 exe，无需 Python

## 🚀 快速使用

### 图形界面（推荐，无需 Python）
从 **GitHub Releases** 下载最新版 `W3X一键解包.exe`（exe 由 Release 自动构建，仓库不含二进制）。双击 exe，把 `.w3x` 拖进窗口（或拖到 exe 图标上），点「一键解包」。

> 也可在仓库 **Actions → Build W3X EXE → Run workflow** 手动构建，产物在 Artifact 中。

### 命令行（需 Python 3）
把 `.w3x` 拖到 `一键解包.bat` 图标上松开，或：
```bash
python unpack.py "你的地图.w3x"          # 单图
python unpack.py a.w3x b.w3x             # 多图批量
```

## 📂 输出结构

地图同目录生成 `<地图名>_解包输出` 文件夹：

| 文件 | 说明 |
|---|---|
| 解包报告.html | 阅读版报告（含**技能表**） |
| 物品清单.md / 物品数据.json | 物品明细 |
| 技能表.json / 技能表.md | 技能数值 + 名称 |
| 技能名.json | w3a 自定义技能名 |
| wts文本.json | war3map.wts 字符串（若存在） |
| *.slk.json | 数值表（itemdata/abilitydata/unitdata 等） |
| raw/ | 原始 SLK / 文本 |

## ⚙️ 支持说明

- 核心依赖 `mpyq`（本地内嵌）+ `内置技能名.json`（官方中文名库）。
- 支持「SLK 优化图」；普通地图脚本（war3map.j）若被加密则无法提取脚本。
- 只读地图、只写输出、不联网、不覆盖原图。

## 📜 许可

仅供学习研究使用。地图版权归原作者所有，本工具仅作数据提取，不参与地图内容的再分发。