# -*- coding: utf-8 -*-
"""发布 War3Studio v2.0 到 GitHub keyminori/w3xunpack
用法: python github_release.py <token> [--tag v2.0.0] [--no-release]
"""
import sys, os, base64, json, argparse, urllib.request, urllib.error
from urllib.parse import quote

API = 'https://api.github.com'


def api(method, path, token, payload=None, accept='application/vnd.github+json'):
    req = urllib.request.Request(path, method=method)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', accept)
    req.add_header('User-Agent', 'war3studio')
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, data, timeout=300) as r:
            body = r.read().decode('utf-8')
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        return e.code, {'err': e.read().decode('utf-8', 'replace')}


def put_file(token, owner, repo, path, content, msg):
    url = '{}/repos/{}/{}/contents/{}'.format(API, owner, repo, quote(path, safe='/.'))
    payload = {'message': msg, 'content': base64.b64encode(content).decode('ascii')}
    st, ex = api('GET', url, token)
    if st == 200 and isinstance(ex, dict) and ex.get('sha'):
        payload['sha'] = ex['sha']
    return api('PUT', url, token, payload)


def upload_asset(token, upload_url, name, content, content_type='application/octet-stream'):
    # upload_url 形如 https://uploads.github.com/repos/.../releases/{id}/assets{?name,label}
    base = upload_url.split('{')[0]
    url = base + '?name=' + quote(name)
    req = urllib.request.Request(url, method='POST', data=content)
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'war3studio')
    req.add_header('Content-Type', content_type)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            body = r.read().decode('utf-8')
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        return e.code, {'err': e.read().decode('utf-8', 'replace')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('token', nargs='?', default=os.environ.get('GITHUB_TOKEN', ''))
    ap.add_argument('--tag', default='v2.0.0')
    ap.add_argument('--name', default='War3Studio v2.0.0')
    ap.add_argument('--notes', default='War3Studio 全功能资源工作台 v2.0.0\n\n- 资源树精细化分类（模型/贴图/音频/脚本/数据/图标，带计数）\n- 打开地图自动后台 SLK 解包\n- 模型预览（MDX→GLB，加载贴图）、贴图滚轮缩放+拖拽平移\n- 音频播放、BLP→PNG 即时预览、批量导出\n- 隐藏子进程黑框、应用图标与窗口图标')
    ap.add_argument('--no-release', action='store_true', help='只更新仓库文件，不创建 Release')
    args = ap.parse_args()

    token = args.token
    if not token:
        print('用法: python github_release.py <token> [--tag v2.0.0]'); return 1
    owner, repo = 'keyminori', 'w3xunpack'
    st, me = api('GET', API + '/user', token)
    if st != 200:
        print('认证失败:', me.get('err', st)); return 1
    print('已认证: @%s' % me.get('login', '?'))

    base = os.path.dirname(os.path.abspath(__file__))
    files = {
        'war3_studio.py': 'update: v2.0.0 全功能资源工作台 GUI',
        'war3core.py': 'update: MPQ/BLP 核心模块',
        'model_preview.py': 'add: 模型预览（MDX→GLB 3D 渲染）',
        'war3.ico': 'add: 应用图标（魔兽英雄，版权归暴雪）',
        'unpack.py': 'update: SLK 解包逻辑',
        'mpyq.py': 'update: MPQ 模块',
        '内置技能名.json': 'update: 技能名表',
        'README.md': 'docs: War3Studio v2.0.0 说明',
        'github_release.py': 'add: v2.0.0 发布脚本',
    }
    for name, msg in files.items():
        p = os.path.join(base, name)
        if not os.path.isfile(p):
            print('跳过缺失:', name); continue
        st, r = put_file(token, owner, repo, name, open(p, 'rb').read(), msg)
        print('[%s] %s %s' % ('OK' if st in (200, 201) else '失败', name,
                              '' if st in (200, 201) else r.get('err', st)))

    exe_path = os.path.join(base, 'dist', 'War3Studio.exe')
    if not os.path.isfile(exe_path):
        print('!! 未找到 dist/War3Studio.exe，跳过 exe 上传')
    elif args.no_release:
        st, r = put_file(token, owner, repo, 'War3Studio.exe',
                         open(exe_path, 'rb').read(), 'update: War3Studio.exe v2.0.0')
        print('[%s] War3Studio.exe(仓库)' % ('OK' if st in (200, 201) else '失败'))
    else:
        # 创建 Release
        st, r = api('POST', '{}/repos/{}/{}/releases'.format(API, owner, repo), token,
                    {'tag_name': args.tag, 'name': args.name, 'body': args.notes,
                     'draft': False, 'prerelease': False})
        if st == 201:
            print('[OK] Release 创建: %s' % r.get('html_url'))
            upload_url = r.get('upload_url', '')
            # 同时把 exe 也作为仓库根文件（保持目录一致）
            put_file(token, owner, repo, 'War3Studio.exe',
                     open(exe_path, 'rb').read(), 'update: War3Studio.exe v2.0.0')
            ast, ar = upload_asset(token, upload_url, 'War3Studio.exe',
                                   open(exe_path, 'rb').read())
            print('[%s] 上传 Release 资产 War3Studio.exe (%d 字节) %s' %
                  ('OK' if ast == 201 else '失败', os.path.getsize(exe_path),
                   '' if ast == 201 else ar.get('err', ast)))
        else:
            print('[失败] 创建 Release:', r.get('err', st))
            if 'already_exists' in str(r.get('err', '')):
                print('提示: 标签 %s 已存在，请换 tag 或删除旧标签' % args.tag)

    print('\n完成 → https://github.com/%s/%s/releases' % (owner, repo))
    return 0


if __name__ == '__main__':
    sys.exit(main())