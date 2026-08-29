#!/usr/softwares/miniconda3/envs/py310/bin/python
# -*- coding: utf-8 -*-
"""入口: python main.py
按需解压逻辑: 素材打包成 zip 存放, 用到时才解压, 解压完删除原 zip
(参考 ffmpeg: runtime/ffmpeg.zip -> runtime/ffmpeg.exe)"""
import os
import sys
import zipfile
from config import BASE


def unpack_if_needed(base, name):
    """若目标不存在且存在同名 zip, 解压到 base 并删除原 zip; 返回目标路径
    base = 解压目标目录 (zip 内顶层条目解压到 base 下), name = 目标目录/文件名"""
    target = os.path.join(base, name)
    if os.path.exists(target):
        return target
    zf = target + '.zip'
    if os.path.exists(zf):
        with zipfile.ZipFile(zf, 'r') as z:
            z.extractall(base)
        os.remove(zf)
        print(f'解压 {os.path.basename(zf)} -> {name}')
    return target


def ensure_song(sid):
    """演奏前解压曲目: src/SRXX.zip -> src/SRXX/, 解压完删 zip"""
    unpack_if_needed(os.path.join(BASE, 'src'), sid)


if __name__ == "__main__":
    # 主界面 BGM: src/track.zip -> src/track/ (启动即需)
    unpack_if_needed(os.path.join(BASE, 'src'), 'track')
    unpack_if_needed(os.path.join(BASE, 'src'), 'fonts')
    # Windows ffmpeg: runtime/ffmpeg.zip -> runtime/ffmpeg.exe
    if sys.platform.startswith('win'):
        exe_file = os.path.join(BASE, 'runtime', 'ffmpeg.exe')
        if not os.path.exists(exe_file):
            zip_file = os.path.join(BASE, 'runtime', 'ffmpeg.zip')
            if os.path.exists(zip_file):
                with zipfile.ZipFile(zip_file, 'r') as z:
                    z.extractall(os.path.join(BASE, 'runtime'))
                os.remove(zip_file)
                print('解压 runtime/ffmpeg.zip -> runtime/ffmpeg.exe')
    from app import App
    App(unpack=ensure_song).run()
