# -*- coding: utf-8 -*-
"""工具: 慢速音频生成 / 音符图形"""
import os
import subprocess
import sys
import pygame


def get_slow_ogg(song_dir, factor):
    """获取倍速音频, 缓存于项目根目录 tmp/ (与 src 并列)
    文件名 = 曲目ID_倍速.mp3 (如 SR03_0.5.mp3); 已存在则直接复用, 无需重新生成
    优先使用 runtime/ffmpeg.exe (Windows 免配置), 否则用系统 ffmpeg"""
    src = os.path.join(song_dir, 'song.ogg')
    project_root = os.path.dirname(os.path.abspath(__file__))
    cache = os.path.join(project_root, 'tmp')
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, f'{os.path.basename(song_dir)}_{factor}.mp3')
    if not os.path.exists(out):
        ffmpeg = 'ffmpeg'
        win_ff = os.path.join(project_root, 'runtime', 'ffmpeg.exe')
        if os.path.exists(win_ff) and sys.platform.startswith('win'):
            ffmpeg = win_ff
        subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', src,
                        '-filter:a', f'atempo={factor}', '-c:a', 'libmp3lame', '-q:a', '4', out], check=True)
    return out


def make_note_surface(font, color, scale=1.0, alpha=255, label=None):
    """绘制音符符号(圆头+符杆+符旗), 返回 (surface, 锚点x, 锚点y) 锚点=符头圆心"""
    w = int(44 * scale) + 8
    h = int(60 * scale) + 8
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w / 2
    # 符头: 圆
    r = 13 * scale
    head_cy = h - 15 * scale
    pygame.draw.circle(surf, color, (int(cx), int(head_cy)), int(r))
    # 符杆(stem): 从圆右侧向上
    stem_x = cx + r * 0.6
    stem_top = head_cy - r * 0.7 - 32 * scale
    pygame.draw.line(surf, color, (stem_x, head_cy - r * 0.3), (stem_x, stem_top), max(3, int(3.5 * scale)))
    # 符旗(flag): 从杆顶向右下弯曲
    pts = []
    for i in range(7):
        t = i / 6
        pts.append((stem_x + 3 + 16 * scale * t, stem_top + 25 * scale * t * t))
    pygame.draw.lines(surf, color, False, pts, max(3, int(3 * scale)))
    # 键字母: 白色, 居中于符头圆心
    if label:
        lbl = font.render(label, True, (255, 255, 255))
        surf.blit(lbl, (cx - lbl.get_width() / 2, head_cy - lbl.get_height() / 2))
    if alpha < 255:
        surf.set_alpha(alpha)
    return surf, cx, head_cy

def parse_anime(path):
    """解析 Anime_*.txt -> dict(bgpic, bganim, kuchi, pos, events)
    BGANIM: bg0[0-1].png -> ['bg00.png','bg01.png']; events: [(t, cmd, args)]"""
    import re
    bgpic, bganim, kuchi, pos = {}, {}, {}, None
    events = []
    section = None
    for raw in open(path, encoding='utf-8'):
        line = raw.split('//')[0].strip()
        if not line:
            continue
        if line.startswith('['):
            section = line.strip('[]')
            continue
        parts = [x.strip() for x in line.split(',')]
        if section == 'Load':
            cmd = parts[0]
            if cmd == 'BGPIC' and len(parts) >= 3:
                bgpic[int(parts[1])] = parts[2]
            elif cmd == 'BGANIM' and len(parts) >= 3:
                m = re.match(r'(.+?)\[(\d+)-(\d+)\]\.(\w+)$', parts[2])
                if m:
                    base, a, b, ext = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
                    files = [f'{base}{i}.{ext}' for i in range(a, b + 1)]
                else:
                    files = [parts[2]]
                speed = None
                if len(parts) > 3 and parts[3].lstrip('-').isdigit():
                    try:
                        speed = (int(parts[3]), int(parts[4]))
                    except Exception:
                        speed = (int(parts[3]), 0)
                bganim[int(parts[1])] = {'files': files, 'speed': speed}
            elif cmd == 'ECHAR00' and len(parts) >= 3:
                kuchi[int(parts[1])] = parts[2]
        elif section in ('Init', 'Perform') and parts[0].startswith('T'):
            try:
                t = float(parts[0][1:])
            except ValueError:
                continue
            args = []
            for x in parts[2:]:
                if not x:
                    continue
                args.append(int(x) if x.lstrip('-').isdigit() else x)
            events.append((t, parts[1], args))
            if parts[1] == 'POS00' and len(args) >= 2:
                pos = (args[0], args[1])
    events.sort(key=lambda e: e[0])
    return {'bgpic': bgpic, 'bganim': bganim, 'kuchi': kuchi, 'pos': pos, 'events': events}
