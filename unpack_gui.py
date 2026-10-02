# -*- coding: utf-8 -*-
"""
W3X 一键解包工具 · GUI 版（带拖拽界面）
打包入口：PyInstaller --onefile --windowed
复用 unpack.py 的解包/解析函数，本文件实现图形界面与日志回调。
"""
import sys, os, re, json, threading, shutil

# 定位 unpack.py 所在目录（源码/打包后均在同目录）
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import unpack as U          # 复用 parse/decode/build 等纯函数
import mpyq                 # 本地 MPQ 模块

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# 拖拽支持（打包时隐藏到后台；失败则退化按钮）
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_OK = True
except Exception:
    DND_OK = False

APP_NAME = 'W3X 一键解包工具'
BG      = '#12161c'
PANEL   = '#1a212b'
PANEL2  = '#202a36'
FG      = '#e6e6e6'
DIM     = '#9aa7b5'
ACCENT  = '#C77B3F'
GREEN   = '#5CD99B'
LINE    = '#2a3540'


def prepare_file_local(path):
    """检测并剥离重制版 HM3W 头，返回 (可打开路径, 是否临时文件)。"""
    with open(path, 'rb') as f:
        head = f.read(4)
    if head == b'MPQ\x1a':
        return path, None
    with open(path, 'rb') as f:
        f.seek(512)
        if f.read(4) != b'MPQ\x1a':
            return path, None
    base = os.path.splitext(os.path.basename(path))[0]
    tmpdir = os.path.join(HERE, '.tmp')
    os.makedirs(tmpdir, exist_ok=True)
    tmp = os.path.join(tmpdir, base + '_mpq.mpq')
    with open(path, 'rb') as fin:
        fin.seek(512)
        with open(tmp, 'wb') as fout:
            shutil.copyfileobj(fin, fout, 1024 * 1024)
    return tmp, tmp


def unpack_one(w3x_path, log):
    """对单个地图解包并输出，log 为回调(msg)。返回 (code, outdir)"""
    w3x_path = os.path.abspath(w3x_path)
    if not os.path.exists(w3x_path):
        log('[错误] 找不到文件：' + w3x_path)
        return 1, None
    base = os.path.splitext(os.path.basename(w3x_path))[0]
    outdir = os.path.join(os.path.dirname(w3x_path), base + '_解包输出')
    rawdir = os.path.join(outdir, 'raw')
    os.makedirs(rawdir, exist_ok=True)

    log('== 正在解包：' + base)
    mpq_path, tmp_file = prepare_file_local(w3x_path)
    try:
        a = mpyq.MPQArchive(mpq_path, listfile=False)
    except Exception as e:
        log('[错误] 无法打开 MPQ 归档：' + str(e))
        if tmp_file and os.path.exists(tmp_file):
            try: os.remove(tmp_file)
            except Exception: pass
        return 1, None

    pulls = [
        ('ItemStrings.txt', U.PATH_ITEMS_STR),
        ('itemdata.slk', U.PATH_ITEMS_SLK),
        ('AbilityStrings.txt', U.PATH_ABILITY_STR),
        ('abilitydata.slk', U.PATH_ABILITY_SLK),
        ('UnitStrings.txt', U.PATH_UNIT_STR),
        ('unitbalance.slk', U.PATH_UNIT_SLK),
    ]
    items, raw_hint, slk_sum = [], [], []
    for label, variants in pulls:
        data, used = U.read_first(a, variants)
        if data is None:
            continue
        with open(os.path.join(rawdir, label), 'wb') as f:
            f.write(data)
        raw_hint.append((label, len(data)))
        if label == 'ItemStrings.txt':
            items = U.parse_item_strings(U.decode(data))
        elif label.endswith('.slk'):
            rows, _ = U.parse_slk(data)
            slk_sum.append((label, len(rows)))
            with open(os.path.join(outdir, label + '.json'), 'w', encoding='utf-8') as f:
                json.dump(rows, f, ensure_ascii=False, indent=1)

    try: a._file.close()
    except Exception: pass

    if not items:
        log('[提示] 未解出物品（非 SLK 优化图）。')
        if tmp_file and os.path.exists(tmp_file):
            try: os.remove(tmp_file)
            except Exception: pass
        return 2, outdir

    # 去重
    seen = set(); uniq = []
    for it in items:
        if it['id'] in seen:
            continue
        seen.add(it['id']); uniq.append(it)
    items = uniq

    with open(os.path.join(outdir, '物品数据.json'), 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    with open(os.path.join(outdir, '物品清单.md'), 'w', encoding='utf-8') as f:
        f.write(f'# {base} · 解包物品清单\n\n> 共 {len(items)} 件物品\n\n')
        f.write('| ID | 名称 | 稀有度 | 槽位 | 装备属性 / 描述 |\n|---|---|---|---|---|\n')
        for it in items:
            tip = U.clean_text(it['ubertip']).replace('|', '\\|')
            f.write(f"| {it['id']} | {it['name']} | {it['rarity']} | {it['slot']} | {tip} |\n")
    with open(os.path.join(outdir, '解包报告.html'), 'w', encoding='utf-8') as f:
        f.write(U.build_html(base, items, raw_hint, slk_sum))

    if tmp_file and os.path.exists(tmp_file):
        try: os.remove(tmp_file)
        except Exception: pass

    log(f'[完成] 共提取物品 {len(items)} 件 → ' + outdir)
    return 0, outdir


class GuiApp:
    def __init__(self, root):
        self.root = root
        self.files = []
        self.busy = False
        self._build()
        if DND_OK:
            self._enable_dnd()

    def _build(self):
        r = self.root
        r.configure(bg=BG)
        r.title(APP_NAME)
        r.geometry('760x560')
        r.minsize(680, 480)

        head = tk.Frame(r, bg=BG)
        head.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(head, text='W3X 一键解包工具', font=('Microsoft YaHei UI', 18, 'bold'),
                 bg=BG, fg=ACCENT).pack(anchor='w')
        tk.Label(head, text='把 .w3x 地图拖进来，或点“添加文件”，然后一键解包。自动识别重制版(HM3W)头。',
                 font=('Microsoft YaHei UI', 10), bg=BG, fg=DIM).pack(anchor='w', pady=(2, 0))

        box = tk.LabelFrame(r, text=' 待解包地图 ', font=('Microsoft YaHei UI', 10, 'bold'),
                            bg=PANEL, fg=GREEN, bd=0, highlightthickness=1,
                            highlightbackground=LINE, highlightcolor=LINE)
        box.pack(fill='both', expand=True, padx=16, pady=8)
        self.tree = ttk.Treeview(box, columns=('name', 'size'), show='headings',
                                 height=8, selectmode='extended')
        self.tree.heading('name', text='地图文件')
        self.tree.heading('size', text='大小')
        self.tree.column('name', width=560, anchor='w')
        self.tree.column('size', width=120, anchor='e')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=FG,
                        borderwidth=0, rowheight=26, font=('Microsoft YaHei UI', 10))
        style.configure('Treeview.Heading', background=PANEL2, foreground=GREEN,
                        borderwidth=0, font=('Microsoft YaHei UI', 10, 'bold'))
        style.map('Treeview', background=[('selected', '#2a4a52')])
        vsb = ttk.Scrollbar(box, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        bar = tk.Frame(r, bg=BG)
        bar.pack(fill='x', padx=16, pady=6)
        self.btn_add = tk.Button(bar, text='添加文件', command=self.add_files,
                                 bg=PANEL2, fg=FG, activebackground=ACCENT, activeforeground=BG,
                                 relief='flat', padx=14, pady=6, font=('Microsoft YaHei UI', 10))
        self.btn_add.pack(side='left', padx=(0, 6))
        self.btn_clear = tk.Button(bar, text='清空', command=self._clear,
                                   bg=PANEL2, fg=FG, activebackground=ACCENT, relief='flat',
                                   padx=14, pady=6, font=('Microsoft YaHei UI', 10))
        self.btn_clear.pack(side='left', padx=6)
        self.btn_run = tk.Button(bar, text='一 键 解 包', command=self._run,
                                 bg=ACCENT, fg=BG, activebackground=GREEN,
                                 relief='flat', padx=22, pady=7, font=('Microsoft YaHei UI', 11, 'bold'))
        self.btn_run.pack(side='left', padx=14)
        self.btn_open = tk.Button(bar, text='打开输出', command=self._open,
                                  bg=PANEL2, fg=FG, activebackground=ACCENT, relief='flat',
                                  padx=14, pady=6, font=('Microsoft YaHei UI', 10))
        self.btn_open.pack(side='left', padx=6)
        self.lbl_state = tk.Label(bar, text='就绪', bg=BG, fg=DIM, font=('Microsoft YaHei UI', 10))
        self.lbl_state.pack(side='right')

        lg = tk.LabelFrame(r, text=' 解包日志 ', font=('Microsoft YaHei UI', 10, 'bold'),
                           bg=PANEL, fg=GREEN, bd=0, highlightthickness=1,
                           highlightbackground=LINE, highlightcolor=LINE)
        lg.pack(fill='both', expand=True, padx=16, pady=8)
        self.log_text = scrolledtext.ScrolledText(lg, bg=BG, fg=FG, font=('Consolas', 10),
                                                  wrap='none', insertbackground=FG, relief='flat', state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=4, pady=4)

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _enable_dnd(self):
        for w in (self.tree, self.root):
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind('<<Drop>>', self._on_drop)
            except Exception:
                pass

    def _on_drop(self, event):
        if self.busy:
            return
        raw = event.data
        paths = [p for p in raw.split('} {') if p.strip()]
        cleaned = []
        for p in paths:
            p = p.strip().strip('{}').strip('"')
            if p.lower().endswith('.w3x') and os.path.isfile(p):
                cleaned.append(p)
        self._add(cleaned)

    def _add(self, paths):
        added = 0
        for p in paths:
            p = os.path.abspath(p)
            if p.lower().endswith('.w3x') and os.path.isfile(p) and p not in self.files:
                self.files.append(p)
                size = os.path.getsize(p)
                self.tree.insert('', 'end', values=(os.path.basename(p), f'{size/1024/1024:.1f} MB'))
                added += 1
        if added == 0:
            self.log('[提示] 未添加任何地图（请选择 .w3x 文件）')
        self.lbl_state.config(text=f'{len(self.files)} 个地图')

    def add_files(self):
        if self.busy:
            return
        sel = filedialog.askopenfilenames(
            title='选择魔兽地图', filetypes=[('魔兽地图', '*.w3x'), ('所有文件', '*.*')])
        self._add(list(sel))

    def _clear(self):
        if self.busy:
            return
        self.files.clear()
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.log('[已清空]')

    def _open(self):
        for f in self.files:
            out = os.path.join(os.path.dirname(f),
                               os.path.splitext(os.path.basename(f))[0] + '_解包输出')
            if os.path.isdir(out):
                os.startfile(out)
                return
        messagebox.showinfo('提示', '还没有输出，请先解包。', parent=self.root)

    def _run(self):
        if self.busy or not self.files:
            return
        files = list(self.files)
        self.busy = True
        self.btn_run.config(state='disabled')
        self.lbl_state.config(text='解包中…', fg=GREEN)
        self._append_log('')
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')
        threading.Thread(target=self._worker, args=(files,), daemon=True).start()

    def _worker(self, files):
        ok = 0; fail = 0
        for i, f in enumerate(files):
            self._ui_log(f'---- [{i+1}/{len(files)}] ----')
            code, out = unpack_one(f, self._ui_log)
            if code == 0:
                ok += 1
            else:
                fail += 1
        self.root.after(0, lambda: self._done(ok, fail))

    def _done(self, ok, fail):
        self.busy = False
        self.btn_run.config(state='normal')
        msg = f'完成：成功 {ok}，失败 {fail}'
        self.lbl_state.config(text=msg, fg=GREEN if fail == 0 else ACCENT)
        if ok:
            messagebox.showinfo('完成', '解包完成！\n输出已放在每个地图同目录的 _解包输出 文件夹。', parent=self.root)

    def log(self, msg):
        self.root.after(0, self._append_log, msg)

    def _ui_log(self, msg):
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')

    def _on_close(self):
        if self.busy:
            if not messagebox.askokcancel('退出', '解包还在进行，确定退出？', parent=self.root):
                return
        self.root.destroy()


def main():
    if DND_OK:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = GuiApp(root)
    # 支持把 .w3x 直接拖到 exe 图标上打开
    for a in sys.argv[1:]:
        a = os.path.abspath(a)
        if a.lower().endswith('.w3x') and os.path.isfile(a):
            app._add([a])
    root.mainloop()


if __name__ == '__main__':
    main()