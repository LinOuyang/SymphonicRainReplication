# -*- coding: utf-8 -*-
"""素材打包: 把 src/ 下每个文件夹打包为同名 zip 并删除原文件夹
运行: python pack_src.py
说明: 游戏运行时演奏哪首才解压哪首 (main.py 的 ensure_song), 解压完删 zip
      重新打包前请先解压所有 zip (或从原解包备份恢复)"""
import os
import shutil
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, 'src')


def main():
    total_in = total_out = 0
    for name in sorted(os.listdir(SRC)):
        p = os.path.join(SRC, name)
        if not os.path.isdir(p) or name.startswith('.'):
            continue
        zp = p + '.zip'
        if os.path.exists(zp):
            print(f'{name}: 跳过 (zip 已存在)')
            continue
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, dirs, fs in os.walk(p):
                for fn in fs:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, SRC)      # 顶层条目 = 文件夹名
                    z.write(full, rel)
        size = os.path.getsize(zp) / 1e6
        total_in += sum(os.path.getsize(os.path.join(r, f))
                        for r, _, fs in os.walk(p) for f in fs) / 1e6
        total_out += size
        shutil.rmtree(p)
        print(f'{name}: 打包完成 {size:.1f}MB')
    print(f'合计: 原 {total_in:.0f}MB -> zip {total_out:.0f}MB (省 {total_in - total_out:.0f}MB)')


if __name__ == '__main__':
    main()
