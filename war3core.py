# -*- coding: utf-8 -*-
"""
War3Studio 核心模块：
- MPQ 打开/文件枚举/读取（复用本地 mpyq）
- BLP → PNG 解码（BLP1/BLP2/BLP0，支持 JPEG、DXT1/3/5、未压缩、调色板）
- 文件导出
"""
import os, struct, io, shutil
from PIL import Image

import mpyq

MPQ_MAGIC = b'MPQ\x1a'
HM3W_OFFSET = 512


def open_mpq(path):
    """打开 .w3x/.mpq，自动剥离重制版 HM3W 头。返回 (archive, tmpfile)。"""
    tmp = None
    with open(path, 'rb') as f:
        head = f.read(4)
    if head == MPQ_MAGIC:
        mpq_path = path
    else:
        with open(path, 'rb') as f:
            f.seek(HM3W_OFFSET)
            if f.read(4) != MPQ_MAGIC:
                raise ValueError('不是有效的 MPQ/W3X 文件')
        tmp = os.path.join(os.path.dirname(os.path.abspath(path)),
                           '.' + os.path.splitext(os.path.basename(path))[0] + '_tmp.mpq')
        with open(path, 'rb') as fin:
            fin.seek(HM3W_OFFSET)
            with open(tmp, 'wb') as fout:
                shutil.copyfileobj(fin, fout, 1024 * 1024)
        mpq_path = tmp
    arch = mpyq.MPQArchive(mpq_path, listfile=True)
    arch._tmpfile = tmp
    return arch


def close_mpq(arch):
    try:
        arch._file.close()
    except Exception:
        pass
    if getattr(arch, '_tmpfile', None) and os.path.exists(arch._tmpfile):
        try:
            os.remove(arch._tmpfile)
        except Exception:
            pass


def list_files(arch):
    return list(arch.files) if getattr(arch, 'files', None) else []


def read_file(arch, name):
    return arch.read_file(name)


# ---------------------------------------------------------------------------
# BLP 解码
# ---------------------------------------------------------------------------
def _c565888(c):
    return ((c >> 11) & 0x1F) * 255 // 31, ((c >> 5) & 0x3F) * 255 // 63, (c & 0x1F) * 255 // 31


def _decode_dxt_block(data, off, fmt):
    """解码一个 4x4 DXT 块，返回 16 个 (r,g,b,a)。fmt: dxt1/dxt3/dxt5"""
    if fmt == 'dxt1':
        c0, c1 = struct.unpack_from('<HH', data, off)
        bits = struct.unpack_from('<Q', data, off + 4)[0]
        a0, a1 = _c565888(c0), _c565888(c1)
        if c0 > c1:
            tab = [a0, a1,
                   ((2 * a0[0] + a1[0]) // 3, (2 * a0[1] + a1[1]) // 3, (2 * a0[2] + a1[2]) // 3, 255),
                   ((a0[0] + 2 * a1[0]) // 3, (a0[1] + 2 * a1[1]) // 3, (a0[2] + 2 * a1[2]) // 3, 255)]
        else:
            tab = [a0, a1,
                   ((a0[0] + a1[0]) // 2, (a0[1] + a1[1]) // 2, (a0[2] + a1[2]) // 2, 255),
                   (0, 0, 0, 0)]
        out = []
        for y in range(4):
            for x in range(4):
                out.append(tab[(bits >> (2 * (y * 4 + x))) & 3])
        return out
    if fmt == 'dxt3':
        alphas = struct.unpack_from('<Q', data, off)[0]
        c0, c1 = struct.unpack_from('<HH', data, off + 8)
        bits = struct.unpack_from('<Q', data, off + 12)[0]
        col0, col1 = _c565888(c0), _c565888(c1)
        tab = [col0, col1,
               ((2 * col0[0] + col1[0]) // 3, (2 * col0[1] + col1[1]) // 3, (2 * col0[2] + col1[2]) // 3, 255),
               ((col0[0] + 2 * col1[0]) // 3, (col0[1] + 2 * col1[1]) // 3, (col0[2] + 2 * col1[2]) // 3, 255)]
        out = []
        for y in range(4):
            for x in range(4):
                n = y * 4 + x
                col = tab[(bits >> (2 * n)) & 3]
                a = ((alphas >> (4 * n)) & 0xF) * 255 // 15
                out.append((col[0], col[1], col[2], a))
        return out
    # dxt5
    a0, a1 = data[off], data[off + 1]
    a_bits = struct.unpack_from('<Q', data, off + 2)[0]
    c0, c1 = struct.unpack_from('<HH', data, off + 8)
    bits = struct.unpack_from('<Q', data, off + 12)[0]
    cc0, cc1 = _c565888(c0), _c565888(c1)
    tab = [cc0, cc1,
           ((2 * cc0[0] + cc1[0]) // 3, (2 * cc0[1] + cc1[1]) // 3, (2 * cc0[2] + cc1[2]) // 3, 255),
           ((cc0[0] + 2 * cc1[0]) // 3, (cc0[1] + 2 * cc1[1]) // 3, (cc0[2] + 2 * cc1[2]) // 3, 255)]
    if a0 > a1:
        atab = [a0, a1, (6 * a0 + a1) // 7, (5 * a0 + 2 * a1) // 7, (4 * a0 + 3 * a1) // 7,
                (3 * a0 + 4 * a1) // 7, (2 * a0 + 5 * a1) // 7, (a0 + 6 * a1) // 7]
    else:
        atab = [a0, a1, (4 * a0 + a1) // 5, (3 * a0 + 2 * a1) // 5, (2 * a0 + 3 * a1) // 5,
                (a0 + 4 * a1) // 5, 0, 255]
    out = []
    for y in range(4):
        for x in range(4):
            n = y * 4 + x
            col = tab[(bits >> (2 * n)) & 3]
            ai = (a_bits >> (3 * n)) & 7
            out.append((col[0], col[1], col[2], atab[ai]))
    return out


def _img_to_png(img):
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


def _blp_common(data, version):
    if version == 1:
        comp = data[4]
        width, height = struct.unpack_from('<II', data, 8)
        offset = struct.unpack_from('<7I', data, 16)
        size = struct.unpack_from('<7I', data, 44)
        palette_off = 72
        data_off = 72 + 1024
        mipfmt = 'dxt1'
    elif version == 2:
        comp = data[4]
        width, height = struct.unpack_from('<II', data, 8)
        offset = struct.unpack_from('<16I', data, 16)
        size = struct.unpack_from('<16I', data, 80)
        palette_off = 144
        data_off = 144 + 1024
        mipfmt = {1: 'raw', 2: 'dxt1', 3: 'dxt3', 4: 'dxt5'}.get(comp, 'raw')
    else:  # blp0
        comp = data[4]
        width, height = struct.unpack_from('<II', data, 8)
        offset = struct.unpack_from('<1I', data, 16)
        size = struct.unpack_from('<1I', data, 20)
        palette_off = 24
        data_off = 24 + 1024
        mipfmt = 'raw'
        return _blp0_decode(data, comp, width, height)

    # JPEG (BLP1 comp=0)
    if version == 'blp1' and comp == 0:
        idx = data.find(b'\xff\xd8', 36)
        if idx < 0:
            raise ValueError('JPEG BLP 无 SOI')
        end = data.find(b'\xff\xd9', idx)
        if end < 0:
            end = len(data)
        else:
            end += 2
        return _img_to_png(Image.open(io.BytesIO(data[idx:end])).convert('RGBA'))

    for m in range(7 if version == 'blp1' else 16):
        off = offset[m] if m < len(offset) else 0
        if off <= 0:
            continue
        w = max(1, width >> m)
        h = max(1, height >> m)
        if w < 4 or h < 4:
            continue
        return _decode_blp_mip(data, off, w, h, mipfmt)
    raise ValueError('BLP 无可用 mipmap')


def _blp0_decode(data, comp, width, height):
    pal_off = 24
    pal = struct.unpack_from('<256I', data, pal_off)
    pix = data[pal_off + 1024:]
    img = Image.new('RGB', (width, height))
    if comp == 1:  # 未压缩 BGR
        for i in range(min(len(pix) // 3, width * height)):
            img.putpixel((i % width, i // width), (pix[i * 3 + 2], pix[i * 3 + 1], pix[i * 3]))
    else:
        for i in range(min(len(pix), width * height)):
            c = pal[pix[i]]
            img.putpixel((i % width, i // width), ((c >> 16) & 255, (c >> 8) & 255, c & 255))
    return _img_to_png(img)


def _decode_blp_mip(data, off, w, h, fmt):
    img = Image.new('RGBA', (w, h))
    if fmt == 'raw':
        n = min(len(data) - off, w * h * 4)
        for i in range(0, n - 3, 4):
            b, g, r, a = data[off + i], data[off + i + 1], data[off + i + 2], data[off + i + 3]
            img.putpixel(((i // 4) % w, (i // 4) // w), (r, g, b, a))
    else:
        bx = (w + 3) // 4
        by = (h + 3) // 4
        bsz = {'dxt1': 8, 'dxt3': 16, 'dxt5': 16}[fmt]
        cur = off
        for y in range(by):
            for x in range(bx):
                blk = _decode_dxt_block(data, cur, fmt)
                cur += bsz
                for yy in range(4):
                    for xx in range(4):
                        px = blk[yy * 4 + xx]
                        ix, iy = x * 4 + xx, y * 4 + yy
                        if ix < w and iy < h:
                            img.putpixel((ix, iy), px)
    return _img_to_png(img)


def blp_to_png(data):
    if data[:4] == b'BLP0':
        return _blp_common(data, 'blp0')
    if data[:4] == b'BLP1':
        return _blp_common(data, 'blp1')
    if data[:4] == b'BLP2':
        return _blp_common(data, 'blp2')
    raise ValueError('不是 BLP 文件')


def blp_to_pil(data):
    """返回可复用 PIL Image（预览用）。"""
    return Image.open(io.BytesIO(blp_to_png(data)))


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------
def guess_ext(name):
    """按文件名或内容推断扩展名。"""
    base = name.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
    if '.' in base:
        return base.rsplit('.', 1)[-1].lower()
    return ''


def export_asset(arch, name, out_dir, convert_images=True):
    """导出单个资源。贴图(.blp/.tga)转 PNG；其余原样。返回写出路径。"""
    data = arch.read_file(name)
    os.makedirs(out_dir, exist_ok=True)
    base = name.replace('\\', '_').replace('/', '_')
    ext = guess_ext(name).lower()
    if convert_images and ext in ('blp',):
        try:
            png = blp_to_png(data)
            dest = os.path.join(out_dir, os.path.splitext(base)[0] + '.png')
            with open(dest, 'wb') as f:
                f.write(png)
            return dest
        except Exception:
            pass
    if convert_images and ext in ('tga',):
        try:
            img = Image.open(io.BytesIO(data)).convert('RGBA')
            dest = os.path.join(out_dir, os.path.splitext(base)[0] + '.png')
            img.save(dest, 'PNG')
            return dest
        except Exception:
            pass
    dest = os.path.join(out_dir, base)
    with open(dest, 'wb') as f:
        f.write(data)
    return dest