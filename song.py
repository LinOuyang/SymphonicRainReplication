# -*- coding: utf-8 -*-
"""谱面/歌曲: 读取 song.txt 与 Song.ID
支持两种形态: 已解压目录 (src/SRXX/) 或 打包 zip (src/SRXX.zip, 运行时按需解压)"""
import os
import zipfile
from config import SONG_DIR


class Song:
    def __init__(self, sid):
        self.sid = sid
        self.dir = SONG_DIR % int(sid[2:])
        self.zip = None                     # 若素材仍为 zip 形态则记录路径
        if not os.path.isdir(self.dir):
            z = self.dir + '.zip'
            if os.path.exists(z):
                self.zip = z
        self.title = self.read_title()
        self.notes = []
        self.lyrics = []
        self.load_chart()

    def _read_text(self, name):
        """目录形态直接读文件, zip 形态从 zip 内读取 (zip 顶层 = 曲目文件夹)"""
        p = os.path.join(self.dir, name)
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                return f.read()
        if self.zip:
            with zipfile.ZipFile(self.zip) as z:
                return z.read(f'{self.sid}/{name}').decode('utf-8')
        raise FileNotFoundError(p)

    def read_title(self):
        try:
            lines = self._read_text('Song.ID').splitlines()
        except Exception:
            return self.sid
        title = self.sid
        for i, l in enumerate(lines):
            if l.strip() in ('[ZH]', '[CN]', '[JA]') and i + 1 < len(lines):
                title = lines[i + 1].strip()
                break
        return title

    def load_chart(self):
        for line in self._read_text('song.txt').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            p = line.split(',')
            if len(p) >= 4 and p[0].isdigit():
                t = int(p[0]) / 88200.0
                snd = p[2]
                if snd.startswith('@'):
                    text = ','.join(p[3:]).strip().rstrip(',').rstrip()
                    self.lyrics.append((t, snd[1:], text))
                else:
                    self.notes.append((t, snd, p[3]))
        self.notes.sort(key=lambda x: x[0])
        self.lyrics.sort(key=lambda x: x[0])

    @property
    def duration(self):
        return self.notes[-1][0] + 3.0 if self.notes else 0.0

    @property
    def first_note_time(self):
        return self.notes[0][0] if self.notes else 0.0
