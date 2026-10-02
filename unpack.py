# -*- coding: utf-8 -*-
"""
W3X 一键解包工具 · 核心解包脚本
适用：魔兽争霸3（含重制版）SLK 优化图。把 .w3x 拖到「一键解包.bat」上即自动运行。

流程：
  1. 用本地 mpyq 打开 .w3x 归档
  2. 按 Units\\ 路径读取 ItemStrings.txt / itemdata.slk / abilitydata.slk 等
  3. 解析物品清单（名称/稀有度/槽位/完整属性 Ubertip）
  4. 输出 JSON + Markdown + HTML 阅读报告 到 地图同目录 `_解包输出`
"""
import sys, os, re, json, shutil
try:
    sys.stdout.reconfigure(encoding='gbk', errors='replace')   # 匹配 Windows cmd(GBK) 终端
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mpyq

MPQ_MAGIC = b'MPQ\x1a'
HM3W_OFFSET = 512   # 重制版 HM3W 头占 512 字节，之后才是标准 MPQ 数据

# 内置技能中文名表（官方能力表，随工具分发）；缺失时技能名只取自地图文本
BUILTIN_ABILITY_NAMES = {}
_bpath = os.path.join(HERE, '内置技能名.json')
if os.path.exists(_bpath):
    try:
        with open(_bpath, encoding='utf-8') as _f:
            BUILTIN_ABILITY_NAMES = json.load(_f)
    except Exception:
        BUILTIN_ABILITY_NAMES = {}

def prepare_mpq(w3x_path):
    """检测文件头。若是 HM3W 等非标准头，自动剥离为临时标准 MPQ 副本。
    返回 (可打开的路径, 是否临时文件)。"""
    with open(w3x_path, 'rb') as f:
        head = f.read(4)
    if head == MPQ_MAGIC:
        return w3x_path, None
    # 尝试从 512 偏移找标准 MPQ 头（重制版封装）
    with open(w3x_path, 'rb') as f:
        f.seek(HM3W_OFFSET)
        if f.read(4) != MPQ_MAGIC:
            return w3x_path, None   # 不是已知格式，交给 mpyq 报错
    base = os.path.splitext(os.path.basename(w3x_path))[0]
    tmpdir = os.path.join(HERE, '.tmp')
    os.makedirs(tmpdir, exist_ok=True)
    tmp = os.path.join(tmpdir, base + '_mpq.mpq')
    with open(w3x_path, 'rb') as fin:
        fin.seek(HM3W_OFFSET)
        with open(tmp, 'wb') as fout:
            shutil.copyfileobj(fin, fout, 1024*1024)
    print(f'[重制版头] 已自动剥离 HM3W 头，解包中……')
    return tmp, tmp

# ---------- 1. 路径变体（SLK 优化图硬编码路径；MPQ hash 大小写不敏感） ----------
PATH_ITEMS_STR   = [b'Units\\ItemStrings.txt', b'Units\\Items.txt', b'ItemStrings.txt']
PATH_ITEMS_SLK   = [b'Units\\itemdata.slk', b'Units\\ItemData.slk', b'itemdata.slk']
PATH_ABILITY_STR = [b'Units\\AbilityStrings.txt', b'Units\\Abilities.txt', b'AbilityStrings.txt']
PATH_ABILITY_SLK = [b'Units\\abilitydata.slk', b'Units\\AbilityData.slk', b'abilitydata.slk']
PATH_UNIT_STR    = [b'Units\\UnitStrings.txt', b'Units\\Units.txt', b'UnitStrings.txt']
PATH_UNIT_SLK    = [b'Units\\unitbalance.slk', b'Units\\UnitBalance.slk', b'unitbalance.slk']
PATH_WTS          = [b'war3map.wts', b'Units\\war3map.wts']
PATH_W3A          = [b'war3map.w3a']

# ---------- 2. 读取辅助 ----------
def read_first(archive, candidates):
    """按候选路径依次尝试读取，返回 (bytes, 命中的路径bytes) 或 (None, None)"""
    for p in candidates:
        try:
            return archive.read_file(p), p
        except Exception:
            continue
    return None, None

def decode(data):
    return data.decode('utf-8', 'replace') if data else ''

# ---------- 3. 解析 ItemStrings.txt ----------
def parse_item_strings(txt):
    """解析 [ID] 块，提取名称/去色码/稀有度/槽位/完整 Ubertip"""
    blocks = re.split(r'^\[([0-9A-Za-z]{3,6})\]\r?\n', txt, flags=re.M)
    items = []
    for i in range(1, len(blocks), 2):
        itid = blocks[i]
        content = blocks[i+1]
        m_name = re.search(r'Name=([^\r\n]+)', content)
        m_tip  = re.search(r'Ubertip=([^\r\n]+)', content)
        m_art  = re.search(r'Art=([^\r\n]+)', content)
        name_raw = m_name.group(1).strip() if m_name else ''
        clean = re.sub(r'\|c[0-9A-Fa-f]{8}|\|r', '', name_raw).replace('\r','').replace('\n',' ').strip()
        rarity = '普通'
        if 'FFFF00' in name_raw: rarity = '传奇'
        elif '00CCFF' in name_raw: rarity = '神秘'
        elif '00FF00' in name_raw: rarity = '稀有'
        elif 'FFFFCC' in name_raw or 'FFCC00' in name_raw: rarity = '传说'
        elif 'C0C0C0' in name_raw or '808080' in name_raw: rarity = '精良'
        slot = ''
        m_slot = re.search(r'\[(主手|副手|头部|护甲|手脚|戒指|饰品|护符|项链|头盔|盾|远程|药水|卷轴|材料)[^\]]*\]', clean)
        if m_slot:
            slot = m_slot.group(0)
        tip = (m_tip.group(1).strip() if m_tip else '').replace('\r','').replace('\n',' ')
        items.append({
            'id': itid,
            'name': clean,
            'rarity': rarity,
            'slot': slot,
            'ubertip': tip,
            'art': (m_art.group(1).strip() if m_art else '')
        })
    return items

def parse_skill_strings(txt):
    """解析 AbilityStrings.txt 的技能名/描述文本 -> {code: {name, desc}}"""
    out = {}
    blocks = re.split(r'^\[([^\]]+)\]\r?\n', txt, flags=re.M)
    for i in range(1, len(blocks), 2):
        code = blocks[i]; content = blocks[i+1]
        nm = re.search(r'Name=([^\r\n]+)', content)
        tip = re.search(r'Ubertip=([^\r\n]+)', content) or re.search(r'Tip=([^\r\n]+)', content)
        out[code] = {'name': clean_text(nm.group(1)) if nm else '',
                     'desc': clean_text(tip.group(1)) if tip else ''}
    return out


def parse_wts(txt):
    """解析 war3map.wts 字符串表 -> [{id, text}]"""
    items = []
    for m in re.finditer(r'STRING\s*\{?\s*(\d+)\s*"((?:[^"\\]|\\.)*)"', txt):
        items.append({'id': int(m.group(1)), 'text': m.group(2).replace('\\n', ' ')})
    return items


def extract_w3a_strings(buf, minlen=2):
    """从 war3map.w3a 提取含中文的技能名/描述文本（去色码）"""
    res = []
    cur = bytearray()
    for b in buf:
        if 32 <= b < 127 or b >= 128:
            cur.append(b)
        else:
            if len(cur) >= minlen:
                s = re.sub(r'\|c[0-9A-Fa-f]{8}|\|r', '', cur.decode('utf-8', 'replace'))
                s = s.strip()
                if s and any('\u4e00' <= c <= '\u9fff' for c in s):
                    res.append(s)
            cur = bytearray()
    return res


# ---------- 4. 解析 SLK 表 ----------
def parse_slk(data):
    """把 SLK 文本转成二维网格（list of dict：列名->值），列名取第 1 行。
    SLK 单元格格式：C;X<列>;Y<行>;K"值"  /  K<数字>；同一行后续列可省略 Y（继承上一行）。
    文件可能整行不分行，按 \\r\\n|\\n 切割。"""
    txt = decode(data)
    cells = {}
    maxx = maxy = 0
    last_y = 1   # SLK 行号从 1 开始；省略 Y 时继承
    for line in re.split(r'[\r\n]+', txt):
        line = line.rstrip()
        if not line.startswith('C;'):
            continue
        parts = line.split(';')
        if len(parts) < 3:
            continue
        xp = parts[1]
        if not xp.startswith('X'):
            continue
        try:
            x = int(xp[1:])
        except ValueError:
            continue
        y = last_y
        val_parts = parts[2:]
        if val_parts and val_parts[0].startswith('Y'):
            try:
                y = int(val_parts[0][1:])
            except ValueError:
                continue
            last_y = y
            val_parts = val_parts[1:]
        val = ';'.join(val_parts)
        # 去掉 K 类型前缀与包裹引号
        if val.startswith('K'):
            val = val[1:]
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            val = val[1:-1]
        cells[(x, y)] = val
        maxx = max(maxx, x); maxy = max(maxy, y)
    if not cells:
        return [], {}
    header = [cells.get((i, 1), '') for i in range(1, maxx+1)]
    rows = []
    for y in range(2, maxy+1):
        row = {header[i-1]: cells.get((i, y), '') for i in range(1, maxx+1)}
        rows.append(row)
    return rows, {'maxx': maxx, 'maxy': maxy}

# ---------- 5. 生成 HTML 报告 ----------
def clean_text(s):
    """去掉魔兽颜色码 |cRRGGBBAA / |r，并把 |n 换行转空格"""
    s = re.sub(r'\|c[0-9A-Fa-f]{8}|\|r', '', s)
    s = s.replace('|n', ' ').replace('\r', ' ').replace('\n', ' ')
    return re.sub(r'\s+', ' ', s).strip()

def color_of(rarity):
    return {
        '传奇':'#C77B3F','神秘':'#B06AB3','稀有':'#5CD99B','传说':'#E0C35C',
        '精良':'#9AA7B5','普通':'#cfd6dd'
    }.get(rarity, '#cfd6dd')

def build_html(w3x_name, items, raw_hint, slk_summary, skills=None):
    rows = ''.join(
        f'<tr><td class="id">{it["id"]}</td><td class="nm" style="color:{color_of(it["rarity"])}">{it["name"]}</td>'
        f'<td><span class="b" style="background:{color_of(it["rarity"])}">{it["rarity"]}</span></td>'
        f'<td>{it["slot"]}</td><td class="tip">{clean_text(it["ubertip"]) or "—"}</td></tr>'
        for it in items
    )
    file_cells = ''.join(
        f'<tr><td>{n}</td><td>{sz:,} 字节</td></tr>' for n, sz in raw_hint
    )
    slk_cells = ''.join(
        f'<tr><td>{n}</td><td>{cnt} 行</td></tr>' for n, cnt in slk_summary
    ) if slk_summary else '<tr><td colspan="2">无</td></tr>'
    if skills:
        named = sum(1 for x in skills if x.get('name'))
        skill_rows = ''.join(
            f'<tr><td class="id">{x.get("code","")}</td><td>{x.get("name") or "无"}</td>'
            f'<td class="tip">{(x.get("desc") or "—")[:30]}</td>'
            f'<td>{x.get("cool1","")}</td><td>{x.get("cost1","")}</td>'
            f'<td>{x.get("area1","")}</td><td>{x.get("rng1","")}</td><td>{x.get("dataA1","")}</td></tr>'
            for x in skills
        )
        skill_html = (f'<h2>技能表（{len(skills)} 条 · 含名称 {named}）</h2>'
                      '<table><tr><th>代码</th><th>名称</th><th>描述</th><th>冷却</th><th>消耗</th><th>范围</th><th>射程</th><th>数值A</th></tr>'
                      f'{skill_rows}</table>')
    else:
        skill_html = '<h2>技能表</h2><p class="dim">本图未解析到技能表。</p>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>W3X 解包报告 · {w3x_name}</title>
<style>
  :root{{--p:#2A5A6A;--ps:#35586b;--a:#C77B3A;--n:#0D1117;--pe:#5CD99B;--b:#E4E0D8;--dim:#9aa7b5;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:radial-gradient(circle at 50% -10%,#1a2530 0%,var(--n) 55%);color:var(--b);font-family:"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.7;font-size:15px;padding-bottom:80px}}
  .wrap{{max-width:1100px;margin:0 auto;padding:0 24px}}
  header{{padding:52px 0 24px;text-align:center;border-bottom:1px solid var(--p)}}
  .k{{color:var(--pe);letter-spacing:.3em;font-size:12px;margin-bottom:10px}}
  h1{{font-size:30px}} h1 span{{color:var(--a)}}
  .sub{{color:#9aa0b5;font-size:14px;margin-top:8px}}
  h2{{color:var(--pe);font-size:20px;margin:32px 0 10px;border-bottom:1px solid var(--p);padding-bottom:6px}}
  table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}}
  th{{background:rgba(42,90,106,.25);color:var(--pe);text-align:left;padding:8px 10px;border-bottom:2px solid var(--p)}}
  td{{padding:7px 10px;border-bottom:1px solid rgba(122,143,163,.15);vertical-align:top;word-break:break-word}}
  tr:hover td{{background:rgba(42,90,106,.08)}}
  .nm{{font-weight:600;white-space:nowrap}}
  .tip{{color:#9aa0b5;font-size:12px}}
  .b{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;color:#0D1117;font-weight:600}}
  .dim{{color:#9aa0b5;font-size:12px}}
  .cnt{{color:var(--a);font-weight:700}}
</style></head><body>
<header><div class="wrap">
  <div class="k">W3X UNPACKER · ONE-CLICK</div>
  <h1>W3X 解包报告 · <span>{w3x_name}</span></h1>
  <div class="sub">共提取 <b class="cnt">{len(items)}</b> 件物品 · 含名称 / 稀有度 / 槽位 / 装备属性</div>
</div></header>
<div class="wrap">
  <h2>解包文件</h2>
  <table><tr><th>文件</th><th>大小</th></tr>{file_cells}</table>
  <h2>物品清单（{len(items)} 件）</h2>
  <table>
    <tr><th>ID</th><th>名称</th><th>稀有度</th><th>槽位</th><th>装备属性 / 描述</th></tr>
    {rows}
  </table>
  <h2>数值表（SLK 原始网格）</h2>
  <table><tr><th>表</th><th>记录数</th></tr>{slk_cells}</table>
  {skill_html}
  <div class="dim">完整明细见同目录 <b>物品数据.json</b> 与 <b>raw/</b> 原始文件。</div>
</div>
</body></html>"""

# ---------- 6. 主流程 ----------
def run(w3x_path):
    w3x_path = os.path.abspath(w3x_path)
    if not os.path.exists(w3x_path):
        print(f'[错误] 找不到地图文件：{w3x_path}')
        return 1
    base = os.path.splitext(os.path.basename(w3x_path))[0]
    outdir = os.path.join(os.path.dirname(w3x_path), f'{base}_解包输出')
    rawdir = os.path.join(outdir, 'raw')
    os.makedirs(rawdir, exist_ok=True)

    print(f'== 正在解包：{w3x_path}')
    mpq_path, tmp_file = prepare_mpq(w3x_path)
    try:
        a = mpyq.MPQArchive(mpq_path, listfile=False)
    except Exception as e:
        print(f'[错误] 无法打开 MPQ 归档：{e}')
        if tmp_file and os.path.exists(tmp_file):
            try: os.remove(tmp_file)
            except Exception: pass
        return 1

    pulls = [
        ('ItemStrings.txt',  PATH_ITEMS_STR),
        ('itemdata.slk',     PATH_ITEMS_SLK),
        ('AbilityStrings.txt', PATH_ABILITY_STR),
        ('abilitydata.slk',  PATH_ABILITY_SLK),
        ('UnitStrings.txt',  PATH_UNIT_STR),
        ('unitbalance.slk',  PATH_UNIT_SLK),
        ('war3map.wts',      PATH_WTS),
        ('war3map.w3a',      PATH_W3A),
    ]
    raw_hint = []
    items = []
    slk_summary = []
    ability_names = {}
    ability_rows = []
    wts_items = []
    w3a_strings = []
    for label, variants in pulls:
        data, used = read_first(a, variants)
        if data is None:
            continue
        with open(os.path.join(rawdir, label), 'wb') as f:
            f.write(data)
        raw_hint.append((label, len(data)))
        if label == 'ItemStrings.txt':
            items = parse_item_strings(decode(data))
        elif label == 'AbilityStrings.txt':
            ability_names = parse_skill_strings(decode(data))
        elif label == 'war3map.wts':
            wts_items = parse_wts(decode(data))
            with open(os.path.join(outdir, 'wts文本.json'), 'w', encoding='utf-8') as f:
                json.dump(wts_items, f, ensure_ascii=False, indent=1)
        elif label == 'war3map.w3a':
            w3a_strings = extract_w3a_strings(data)
            with open(os.path.join(outdir, '技能名.json'), 'w', encoding='utf-8') as f:
                json.dump(w3a_strings, f, ensure_ascii=False, indent=1)
        elif label.endswith('.slk'):
            rows, _ = parse_slk(data)
            slk_summary.append((label, len(rows)))
            if label == 'abilitydata.slk':
                ability_rows = rows
            with open(os.path.join(outdir, label + '.json'), 'w', encoding='utf-8') as f:
                json.dump(rows, f, ensure_ascii=False, indent=1)

    if not items:
        print('[提示] 未解出物品（ItemStrings.txt 未找到或为空）。')
        print('      这可能是非 SLK 优化的普通地图，数据在 war3map.j 等脚本内，本工具当前只支持 SLK 优化图。')
        try: a._file.close()
        except Exception: pass
        if tmp_file and os.path.exists(tmp_file):
            try: os.remove(tmp_file)
            except Exception: pass
        return 2

    # 去重（同 ID 可能重复块）
    seen = set(); uniq = []
    for it in items:
        if it['id'] in seen:
            continue
        seen.add(it['id']); uniq.append(it)
    items = uniq

    json_path = os.path.join(outdir, '物品数据.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=1)

    md_path = os.path.join(outdir, '物品清单.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f'# {base} · 解包物品清单\n\n')
        f.write(f'> 共 {len(items)} 件物品\n\n')
        f.write('| ID | 名称 | 稀有度 | 槽位 | 装备属性 / 描述 |\n|---|---|---|---|---|\n')
        for it in items:
            tip = clean_text(it['ubertip']).replace('|', '\\|')
            f.write(f"| {it['id']} | {it['name']} | {it['rarity']} | {it['slot']} | {tip} |\n")

    html_path = os.path.join(outdir, '解包报告.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(build_html(base, items, raw_hint, slk_summary))

    # ---- 技能表/文本提取（若有文本或 wts）----
    skill_msg = ''
    full = []
    if ability_rows:
        full = []
        for row in ability_rows:
            code = row.get('alias') or row.get('code') or ''
            nm = ability_names.get(row.get('alias')) or ability_names.get(row.get('code')) or {}
            full.append({
                'code': code,
                'name': nm.get('name', '') or BUILTIN_ABILITY_NAMES.get(code, ''),
                'desc': nm.get('desc', ''),
                'levels': row.get('levels', ''), 'cool1': row.get('Cool1', ''),
                'cost1': row.get('Cost1', ''), 'area1': row.get('Area1', ''),
                'rng1': row.get('Rng1', ''), 'dataA1': row.get('DataA1', ''),
            })
        with open(os.path.join(outdir, '技能表.json'), 'w', encoding='utf-8') as f:
            json.dump(full, f, ensure_ascii=False, indent=1)
        named = sum(1 for x in full if x['name'])
        with open(os.path.join(outdir, '技能表.md'), 'w', encoding='utf-8') as f:
            f.write(f'# {base} · 技能表\n\n> 共 {len(full)} 条 · 有名称 {named} 条\n\n')
            f.write('| 代码 | 名称 | 描述 | 冷却 | 消耗 | 范围 | 射程 | 数值A |\n|---|---|---|---|---|---|---|---|\n')
            for x in full:
                desc = (x['desc'] or '—').replace('|', '\\|')[:40]
                f.write(f"| {x['code']} | {x['name'] or '无'} | {desc} | {x['cool1']} | {x['cost1']} | {x['area1']} | {x['rng1']} | {x['dataA1']} |\n")
        skill_msg = f'；技能表 {len(full)} 条' + (f'（含名称 {named}）' if named else '（本图无技能名文本，仅数值）')
        if wts_items:
            skill_msg += f'；wts 文本 {len(wts_items)} 条'

    if w3a_strings:
        with open(os.path.join(outdir, '技能名.md'), 'w', encoding='utf-8') as f:
            f.write(f'# {base} · 技能名（war3map.w3a 内嵌）\n\n')
            f.write(f'> 共 {len(w3a_strings)} 个中文技能名/描述\n\n')
            for s in w3a_strings:
                f.write('- ' + s.replace('|', '\\|') + '\n')
        skill_msg += f'；技能名 {len(w3a_strings)} 条'

    # HTML 报告（含技能表）
    html_path = os.path.join(outdir, '解包报告.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(build_html(base, items, raw_hint, slk_summary, skills=full))

    print(f'\n[完成] 共提取物品 {len(items)} 件。{skill_msg}')
    print(f'  输出目录：{outdir}')
    print(f'  - 物品数据.json （完整明细）')
    print(f'  - 物品清单.md   （Markdown 汇总）')
    print(f'  - 解包报告.html （阅读报告）')
    print(f'  - raw/          （原始 SLK/文本）')
    try: a._file.close()
    except Exception: pass
    if tmp_file and os.path.exists(tmp_file):
        try: os.remove(tmp_file)
        except Exception: pass
    return 0

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print('用法：解包.py <地图.w3x> [地图2.w3x ...]')
        sys.exit(1)
    code = 0
    for w in args:
        code = max(code, run(w))
    sys.exit(code)