# -*- coding: utf-8 -*-
"""
War3Studio · 魔兽争霸3 全功能资源工作台
- 打开 .w3x/.mpq（含重制版 HM3W 头）
- 资源树浏览（模型/贴图/音频/脚本/数据），无清单图经 StormJS 枚举
- 贴图预览（BLP→PNG）、音频播放、文本查看
- 资源导出（模型/贴图/音频/任意文件）
- SLK 数据解包（物品/技能/装备 → JSON/MD）
- 打包：PyInstaller --onefile --windowed（需 Node 运行时，见 README）
"""
import os, sys, json, subprocess, threading, tempfile, shutil, glob, io
from PIL import Image, ImageTk

# 隐藏子进程控制台（Windows）
_CSW = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
try:
    import model_preview as MP
except Exception:
    MP = None

# ---------- 运行环境定位 ----------
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import war3core as W
import unpack as U

STORMJS_DIR = os.environ.get('STORMJS_DIR', r'D:\dnd_ref\MPQ工具\mpq-tool')
NODE_BIN = os.environ.get('NODE_BIN', 'node')


def find_stormjs():
    """定位 stormjs 枚举/读取脚本目录（含 node_modules）。"""
    for d in (STORMJS_DIR, os.path.join(HERE, 'stormjs'), os.path.join(HERE, 'node_modules')):
        if os.path.isdir(os.path.join(d, 'node_modules')):
            return d
    return None


def has_node():
    try:
        subprocess.run([NODE_BIN, '-v'], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


# ---------- 后端 ----------
class MapSource:
    """封装一个地图文件：枚举 + 读取 + 导出。"""
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.files = []
        self._use_node = False
        self._open()

    def _open(self):
        # 1) 尝试 mpyq
        try:
            a = W.open_mpq(self.path)
            fs = W.list_files(a)
            W.close_mpq(a)
            if fs:
                self.files = [{'name': n, 'size': 0} for n in fs]
                return
        except Exception:
            pass
        # 2) 用 StormJS 枚举（KK/SLK 优化图无 listfile）
        if has_node():
            sd = find_stormjs()
            if sd:
                outjson = os.path.join(tempfile.gettempdir(), 'war3studio_enum.json')
                r = subprocess.run([NODE_BIN, os.path.join(sd, 'stormjs_enum.mjs'),
                                    self.path, outjson], capture_output=True, timeout=120,
                                   creationflags=_CSW)
                if os.path.exists(outjson):
                    try:
                        self.files = json.load(open(outjson, encoding='utf-8'))
                        self._use_node = True
                    except Exception:
                        pass

    def read_to(self, name, dest):
        """读取资源到本地 dest，返回 dest 或 None。顺序：先 mpyq(按路径)，再 Node。"""
        # 1) 先尝试 mpyq（按路径直接读；KK/SLK 优化图的 .slk/.w3a 等标准路径可读）
        try:
            a = W.open_mpq(self.path)
            try:
                nb = name.encode('utf-8') if isinstance(name, str) else name
                data = W.read_file(a, nb)
            finally:
                W.close_mpq(a)
            if data:
                os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
                with open(dest, 'wb') as f:
                    f.write(data)
                return dest
        except Exception:
            pass
        # 2) 再尝试 Node+StormJS（KK 图占位名文件）
        if has_node():
            sd = find_stormjs()
            if sd:
                r = subprocess.run([NODE_BIN, os.path.join(sd, 'stormjs_read.mjs'),
                                    self.path, name, dest], capture_output=True, timeout=60,
                                   creationflags=_CSW)
                if r.returncode == 0 and os.path.exists(dest):
                    return dest
        return None


# ---------- 预览 ----------
def preview_image(bytes_, size=(360, 360)):
    try:
        pil = Image.open(os.path.join(tempfile.gettempdir(), 'dummy'))  # placeholder
    except Exception:
        pass


# ---------- GUI ----------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext


class StudioApp:
    def __init__(self, root):
        self.root = root
        self.src = None
        self._build()

    def _build(self):
        r = self.root
        r.title('War3Studio · 魔兽争霸3 资源工作台')
        r.geometry('980x640')
        r.minsize(860, 560)

        # 顶部工具栏
        bar = tk.Frame(r)
        bar.pack(fill='x', padx=8, pady=6)
        self.btn_open = tk.Button(bar, text='打开 .w3x/.mpq', command=self.open_map)
        self.btn_open.pack(side='left')
        self.btn_export = tk.Button(bar, text='导出选中', command=self.export_selected)
        self.btn_export.pack(side='left', padx=4)
        self.btn_export_all = tk.Button(bar, text='全部导出', command=self.export_all)
        self.btn_export_all.pack(side='left', padx=4)
        self.btn_unpack = tk.Button(bar, text='SLK 解包', command=self.unpack_slk)
        self.btn_unpack.pack(side='left', padx=4)
        self.lbl_map = tk.Label(bar, text='未打开', fg='#666')
        self.lbl_map.pack(side='right')

        paned = ttk.Panedwindow(r, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=8, pady=4)

        # 左：资源树
        left = tk.Frame(paned)
        self.tree = ttk.Treeview(left, columns=('type', 'size'), show='tree headings')
        self.tree.heading('#0', text='资源')
        self.tree.heading('type', text='类型')
        self.tree.heading('size', text='大小')
        self.tree.column('type', width=90)
        self.tree.column('size', width=90)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.pack(fill='both', expand=True)
        paned.add(left, weight=3)

        # 右：预览
        right = tk.Frame(paned)
        self.preview = tk.Canvas(right, width=560, height=300, bg='#f4f4f4',
                                 highlightthickness=0)
        self.preview.bind('<MouseWheel>', self._on_wheel)
        self.preview.bind('<ButtonPress-1>', self._on_pan_start)
        self.preview.bind('<B1-Motion>', self._on_pan)
        self.preview.pack(fill='both', expand=True)
        self.info = tk.Label(right, text='', justify='left', anchor='nw', font=('Consolas', 9))
        self.info.pack(fill='x', pady=(4, 0))
        paned.add(right, weight=2)

        # 底部日志
        self.logbox = scrolledtext.ScrolledText(r, height=7, font=('Consolas', 9))
        self.logbox.pack(fill='x', padx=8, pady=(0, 8))

        self._log('就绪。打开一个 .w3x/.mpq 开始。')

    def _log(self, m):
        self.logbox.insert('end', m + '\n')
        self.logbox.see('end')

    # ---------- 打开 ----------
    def open_map(self):
        path = filedialog.askopenfilename(
            title='选择魔兽地图', filetypes=[('魔兽地图', '*.w3x'), ('MPQ', '*.mpq'), ('所有文件', '*.*')])
        if not path:
            return
        self.root.config(cursor='watch')
        self.root.update()
        try:
            self.src = MapSource(path)
            self.lbl_map.config(text=os.path.basename(path) +
                                (f'（{len(self.src.files)} 个文件）'))
            self._log(f'打开 {path}: {len(self.src.files)} 个文件')
            self._fill_tree()
            threading.Thread(target=self._auto_unpack, daemon=True).start()
        except Exception as e:
            messagebox.showerror('错误', f'无法打开: {e}')
        finally:
            self.root.config(cursor='')

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        # 精细化分类：扩展名 → 分组标签（保持定义顺序）
        EXT_LABEL = [
            ('.mdx', '模型·MDX'), ('.mdl', '模型·MDL'),
            ('.blp', '贴图·BLP'), ('.tga', '贴图·TGA'), ('.dds', '贴图·DDS'),
            ('.png', '贴图·PNG'), ('.jpg', '贴图·JPG'), ('.jpeg', '贴图·JPG'),
            ('.wav', '音频·WAV'), ('.mp3', '音频·MP3'), ('.ogg', '音频·OGG'),
            ('.flac', '音频·FLAC'), ('.mid', '音频·MID'),
            ('.j', '脚本·JASS'), ('.ai', '脚本·JASS'), ('.jass', '脚本·JASS'),
            ('.txt', '文本·TXT'), ('.wts', '文本·WTS'),
            ('.slk', '数据·SLK'), ('.json', '数据·JSON'),
            ('.w3a', '数据·W3A'), ('.w3u', '数据·W3U'), ('.w3t', '数据·W3T'),
        ]
        groups = {}
        for f in self.src.files:
            name = f['name']
            if not name:
                continue
            ext = '.' + name.rsplit('.', 1)[-1].lower() if '.' in name else ''
            label = next((l for e, l in EXT_LABEL if ext == e), '其他')
            groups.setdefault(label, []).append(f)
        for label in sorted(groups.keys(), key=lambda x: (x != '其他', x)):
            items = groups[label]
            node = self.tree.insert('', 'end', text=f'{label}（{len(items)}）', open=False)
            for it in sorted(items, key=lambda x: x['name'].lower()):
                size = it.get('size', 0)
                self.tree.insert(node, 'end', text=it['name'],
                                 values=('', size if size else ''), iid=None)

    # ---------- 选择/预览 ----------
    def on_select(self, ev):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        # 类型分组节点（带子节点）不预览
        if self.tree.get_children(item):
            return
        name = self.tree.item(item, 'text')
        if not name:
            return
        self._preview(name)

    def _preview(self, name):
        if not self.src:
            return
        self.root.config(cursor='watch')
        self.root.update()
        ext = name.rsplit('.', 1)[-1].lower()
        tmp = os.path.join(tempfile.gettempdir(), 'ws_' + os.path.basename(name))
        try:
            dest = self.src.read_to(name, tmp)
            if not dest:
                self.info.config(text=f'{name}\n[读取失败]')
                return
            size = os.path.getsize(dest)
            self._clear_img()
            if ext in ('blp',):
                try:
                    png = W.blp_to_png(open(dest, 'rb').read())
                    pil = Image.open(io.BytesIO(png)).convert('RGBA')
                except Exception:
                    pil = None
                if pil:
                    self._show_img(pil, name)
                else:
                    self.info.config(text=f'{name}\n{size} 字节 · BLP 贴图(解码失败)')
                self.info.config(text=f'{name}\n{size} 字节 · BLP 贴图' if not pil else self.info.cget('text'))
            elif ext in ('png', 'jpg', 'jpeg', 'tga'):
                try:
                    pil = Image.open(dest).convert('RGBA')
                    self._show_img(pil, name)
                except Exception as e:
                    self.info.config(text=f'{name}\n图片预览失败: {e}')
            elif ext in ('wav', 'mp3', 'ogg', 'flac'):
                self._show_audio(dest, name)
            elif ext in ('txt', 'slk', 'wts', 'j', 'ai'):
                try:
                    txt = open(dest, 'r', encoding='utf-8', errors='replace').read(2000)
                    self.info.config(text=f'{name}\n{size} 字节\n\n{txt}')
                except Exception:
                    self.info.config(text=f'{name}\n{size} 字节')
            elif ext in ('mdx', 'mdl'):
                info = f'{name}\n{size} 字节 · 模型'
                if MP:
                    glb = MP.mdx_to_glb(dest, self.src.path)
                    if glb:
                        try:
                            subprocess.Popen([sys.executable, '--preview', glb],
                                             creationflags=_CSW)
                            info += '\n已启动 3D 预览窗口'
                        except Exception:
                            MP.preview_glb(glb)
                            info += '\n已用浏览器打开预览'
                    else:
                        info += '\n（未检测到 Node，无法预览）'
                self.info.config(text=info)
            else:
                self.info.config(text=f'{name}\n{size} 字节')
        finally:
            self.root.config(cursor='')

    def _show_img(self, pil, name):
        try:
            self._pil = pil.copy()
            self._zoom = 1.0
            self._offx = 0; self._offy = 0
            self._draw_img()
            self.info.config(text=f'{name}（滚轮缩放 / 左键拖拽平移）')
        except Exception as e:
            self.info.config(text=f'{name}\n预览失败 {e}')

    def _draw_img(self):
        c = self.preview
        w = c.winfo_width() or 380; h = c.winfo_height() or 300
        img = self._pil.copy()
        img.thumbnail((int(w * self._zoom), int(h * self._zoom)))
        self._tkimg = ImageTk.PhotoImage(img)
        c.delete('all')
        c.create_image(w // 2 + self._offx, h // 2 + self._offy, image=self._tkimg)

    def _on_wheel(self, e):
        self._zoom *= 1.2 if e.delta > 0 else 1 / 1.2
        self._zoom = max(0.2, min(12, self._zoom))
        self._draw_img()

    def _on_pan_start(self, e):
        self._drag = (e.x, e.y)

    def _on_pan(self, e):
        if not hasattr(self, '_drag'):
            return
        dx = e.x - self._drag[0]; dy = e.y - self._drag[1]
        self._drag = (e.x, e.y)
        self._offx += dx; self._offy += dy
        self._draw_img()

    def _clear_img(self):
        self.preview.delete('all')

    def _show_audio(self, dest, name):
        try:
            os.startfile(dest)  # 用系统播放器播放
            self.info.config(text=f'{name}\n已用系统播放器打开播放')
        except Exception as e:
            self.info.config(text=f'{name}\n播放失败 {e}')

    # ---------- 导出 ----------
    def _selected_names(self):
        sel = self.tree.selection()
        out = []
        for item in sel:
            name = self.tree.item(item, 'text')
            if name and '/' not in name.replace('\\', '/'):
                out.append(name)
            else:
                # 分组节点：导出其下所有
                for child in self.tree.get_children(item):
                    out.append(self.tree.item(child, 'text'))
        return out

    def export_selected(self):
        if not self.src:
            messagebox.showinfo('提示', '先打开地图')
            return
        names = self._selected_names()
        if not names:
            messagebox.showinfo('提示', '请先在树中选中要导出的文件/文件夹')
            return
        outdir = filedialog.askdirectory(title='选择导出目录')
        if not outdir:
            return
        self.root.config(cursor='watch')
        self.root.update()
        try:
            ok = 0
            for n in names:
                dest = os.path.join(outdir, n.replace('\\', '_').replace('/', '_'))
                if self.src.read_to(n, dest):
                    ok += 1
            self._log(f'导出 {ok}/{len(names)} 个 → {outdir}')
        finally:
            self.root.config(cursor='')

    def export_all(self):
        if not self.src:
            return
        outdir = filedialog.askdirectory(title='选择导出目录')
        if not outdir:
            return
        self.root.config(cursor='watch')
        self.root.update()
        try:
            ok = 0
            for f in self.src.files:
                n = f['name']
                dest = os.path.join(outdir, n.replace('\\', '_').replace('/', '_'))
                if self.src.read_to(n, dest):
                    ok += 1
            self._log(f'全部导出 {ok} 个 → {outdir}')
        finally:
            self.root.config(cursor='')

    # ---------- SLK 解包 ----------
    def unpack_slk(self):
        if not self.src:
            messagebox.showinfo('提示', '先打开地图')
            return
        outdir = filedialog.askdirectory(title='选择解包输出目录') or os.path.dirname(self.src.path)
        threading.Thread(target=self._run_unpack, args=(outdir,), daemon=True).start()

    def _auto_unpack(self):
        """打开地图后自动解包到地图同目录（后台）。"""
        try:
            outdir = os.path.dirname(self.src.path)
            self._run_unpack(outdir)
        except Exception as e:
            self._log('[自动解包失败] ' + str(e))

    def _run_unpack(self, outdir):
        if not self.src:
            return
        base = os.path.splitext(os.path.basename(self.src.path))[0]
        dest = os.path.join(outdir, base + '_解包输出')
        try:
            os.makedirs(dest, exist_ok=True)
            pulls = [
                ('ItemStrings.txt', U.PATH_ITEMS_STR), ('itemdata.slk', U.PATH_ITEMS_SLK),
                ('AbilityStrings.txt', U.PATH_ABILITY_STR), ('abilitydata.slk', U.PATH_ABILITY_SLK),
                ('UnitStrings.txt', U.PATH_UNIT_STR), ('unitbalance.slk', U.PATH_UNIT_SLK),
                ('war3map.wts', U.PATH_WTS), ('war3map.w3a', U.PATH_W3A),
            ]
            items, slk_rows = [], []
            ability_rows = []
            ability_names = {}
            for label, variants in pulls:
                data = None
                for v in variants:
                    tmp = os.path.join(tempfile.gettempdir(), 'ws_' + label)
                    if self.src.read_to(v.decode() if isinstance(v, bytes) else v, tmp):
                        data = open(tmp, 'rb').read()
                        break
                if data is None:
                    continue
                if label == 'ItemStrings.txt':
                    items = U.parse_item_strings(U.decode(data))
                elif label == 'AbilityStrings.txt':
                    ability_names = U.parse_skill_strings(U.decode(data))
                elif label == 'abilitydata.slk':
                    rows, _ = U.parse_slk(data)
                    ability_rows = rows
                elif label.endswith('.slk'):
                    rows, _ = U.parse_slk(data)
                    slk_rows.append((label, rows))
            self._write_slk_outputs(dest, items, slk_rows, ability_names, ability_rows)
            n = len(items)
            self.root.after(0, lambda: self._log(f'SLK 解包完成 → {dest}（物品 {n}）'))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.root.after(0, lambda tb=tb: self._log('解包错误:\n' + tb))

    def _write_slk_outputs(self, dest, items, slk_rows, ability_names, ability_rows):
        # 去重物品
        seen = set(); uniq = []
        for it in items:
            if it['id'] not in seen:
                seen.add(it['id']); uniq.append(it)
        with open(os.path.join(dest, '物品数据.json'), 'w', encoding='utf-8') as f:
            json.dump(uniq, f, ensure_ascii=False, indent=1)
        md = ['# 解包物品清单\n', f'> 共 {len(uniq)} 件\n', '\n| ID | 名称 | 稀有度 | 槽位 | 描述 |\n|---|---|---|---|---|\n']
        for it in uniq:
            md.append(f"| {it['id']} | {it['name']} | {it['rarity']} | {it['slot']} | {U.clean_text(it['ubertip'])} |\n")
        with open(os.path.join(dest, '物品清单.md'), 'w', encoding='utf-8') as f:
            f.write(''.join(md))
        # 技能表
        if ability_rows:
            full = []
            for row in ability_rows:
                code = row.get('alias') or row.get('code') or ''
                nm = ability_names.get(code) or {}
                full.append({'code': code, 'name': nm.get('name', ''), 'desc': nm.get('desc', ''),
                             'cool': row.get('Cool1', ''), 'cost': row.get('Cost1', ''), 'area': row.get('Area1', ''),
                             'rng': row.get('Rng1', '')})
            with open(os.path.join(dest, '技能表.json'), 'w', encoding='utf-8') as f:
                json.dump(full, f, ensure_ascii=False, indent=1)
        # slk 原始
        for label, rows in slk_rows:
            with open(os.path.join(dest, label + '.json'), 'w', encoding='utf-8') as f:
                json.dump(rows, f, ensure_ascii=False, indent=1)


def main():
    # 独立模型预览模式：War3Studio.exe --preview <glb>
    if '--preview' in sys.argv:
        try:
            i = sys.argv.index('--preview')
            glb = sys.argv[i + 1]
            import model_preview as MP
            MP.preview_pywebview(glb)
        except Exception as e:
            try:
                import tkinter as tk
                from tkinter import messagebox
                r = tk.Tk(); r.withdraw()
                messagebox.showerror('预览错误', str(e)); r.destroy()
            except Exception:
                pass
        return
    import tkinter as tk
    root = tk.Tk()
    app = StudioApp(root)
    for a in sys.argv[1:]:
        a = os.path.abspath(a)
        if os.path.isfile(a):
            app.src = MapSource(a)
            app.lbl_map.config(text=os.path.basename(a) + f' ({len(app.src.files)})')
            app._fill_tree()
    root.mainloop()


if __name__ == '__main__':
    main()