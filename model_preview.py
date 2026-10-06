# -*- coding: utf-8 -*-
"""模型预览：提取 MDX → 转 GLB → 在系统浏览器打开 Three.js 3D 预览页。"""
import os, sys, base64, subprocess, tempfile, webbrowser

STORMJS_DIR = os.environ.get('STORMJS_DIR', r'D:\dnd_ref\MPQ工具\mpq-tool')
NODE_BIN = os.environ.get('NODE_BIN', 'node')

_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>模型预览</title>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script>
<style>body{margin:0;overflow:hidden;background:#181d26;color:#c7ccd4;font-family:Segoe UI,sans-serif}
#bar{position:fixed;top:0;left:0;right:0;padding:8px 14px;background:#232a36;z-index:10;font-size:12px}
#err{position:fixed;top:44px;left:14px;color:#ff7a7a;z-index:10;font-size:12px}</style>
</head><body><div id="bar">模型 · 左键旋转 / 滚轮缩放 / 右键平移</div><div id="err"></div>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
const scene=new THREE.Scene();
scene.add(new THREE.AmbientLight(0xffffff,0.75));
const dl=new THREE.DirectionalLight(0xffffff,1.0);dl.position.set(1,1.6,1);scene.add(dl);
const dl2=new THREE.DirectionalLight(0xffffff,0.4);dl2.position.set(-1,-0.8,-1);scene.add(dl2);
const cam=new THREE.PerspectiveCamera(45,innerWidth/innerHeight,0.1,3000);
cam.position.set(0,1.3,2.8);
const renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth,innerHeight);renderer.setClearColor(0x181b23);
document.body.appendChild(renderer.domElement);
const ctrl=new OrbitControls(cam,renderer.domElement);ctrl.enableDamping=true;
let b64=document.getElementById('glb64').textContent;
let bin;
try{bin=atob(b64.trim());}catch(e){document.getElementById('err').textContent='GLB 数据解码失败';throw e;}
const arr=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)arr[i]=bin.charCodeAt(i);
const loader=new GLTFLoader();
loader.parse(arr.buffer,'',(gltf)=>{scene.add(gltf.scene);_fit(gltf.scene);render();},(e)=>{document.getElementById('err').textContent='模型解析失败: '+e;});
function _fit(obj){
  const box=new THREE.Box3().setFromObject(obj);const sph=box.getBoundingSphere(new THREE.Sphere());
  const r=sph.radius||1; cam.position.set(sph.center.x,sph.center.y,sph.center.z).add(new THREE.Vector3(r*1.5,r*0.8,r*1.5));
  ctrl.target.copy(sph.center);
}
function render(){requestAnimationFrame(render);ctrl.update();renderer.render(scene,cam);}render();
addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);});
</script></body></html>"""


def preview_glb(glb_path):
    """把 GLB 内嵌进 HTML，用系统默认浏览器打开 3D 预览。返回 True/错误。"""
    try:
        with open(glb_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        page = ('<div id="glb64" style="display:none">' + b64 + '</div>' + _HTML)
        html_path = os.path.join(tempfile.gettempdir(), 'war3studio_preview.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page)
        webbrowser.open('file://' + html_path.replace('\\', '/'))
        return True
    except Exception as e:
        return str(e)


def mdx_to_glb(mdx_path, mpq_path=None):
    """用 Node + mpq-tool 把 .mdx 转成临时 .glb（带贴图），返回路径或 None。"""
    sd = STORMJS_DIR
    if not os.path.isdir(os.path.join(sd, 'node_modules')):
        return None
    glb = os.path.join(tempfile.gettempdir(), 'ws_preview.glb')
    args = [NODE_BIN, os.path.join(sd, 'mdx_to_glb.mjs'), mdx_path, glb]
    if mpq_path:
        args.append(mpq_path)
    try:
        r = subprocess.run(args, capture_output=True, timeout=90,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000))
        if r.returncode == 0 and os.path.exists(glb):
            return glb
    except Exception:
        return None
    return None


def preview_pywebview(glb_path):
    """用 pywebview 在独立窗口内 3D 查看 GLB（exe 内直接查看，不跳浏览器）。"""
    try:
        import webview
        with open(glb_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        page = ('<div id="glb64" style="display:none">' + b64 + '</div>' + _HTML)
        webview.create_window('模型预览', html=page, width=680, height=560, resizable=True)
        webview.start()
        return True
    except Exception as e:
        return str(e)