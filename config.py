# -*- coding: utf-8 -*-
"""配置: 常量 / 指法映射 / 颜色"""
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
SONG_DIR = os.path.join(BASE, 'src', 'SR%02d')
W, H = 1600, 900                    # 逻辑分辨率(布局基准)
RESOLUTIONS = [(1280, 720), (1600, 900)]   # 窗口分辨率档位
FPS = 60
JUDGE_X = 395.0                       # 判定线 x（游戏区位置，微调左移）
NOTE_SPEED = 400.0                    # px/s (滚动 3 秒到判定线)
NOTE_R = 16
LANE_TOP, LANE_BOT = 590, 890     # 轨道区: 自底部往上 1/3 屏(微调上移)
LANES_NORMAL = ['a', 's', 'd', 'f', 'j', 'k', 'l', ';']
LEAD_TIME = 3.0                       # 音符提前出现时间(秒)@1.0x
SPEEDS = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]   # 滚动速度档位
SLOW_SPEEDS = [0.5, 0.75, 0.9, 1.0, 1.1, 1.25]   # 倍速档位(S键循环, 音频+音符同步)
SEEK_SECONDS = 7.0                      # 演奏中 ←/→ 前后跳转时长(秒)

WIN_PERFECT = 0.050
WIN_GREAT = 0.100
WIN_GOOD = 0.150
JUDGE_BOX_W = 80                        # 判定框宽(px, 原120的2/3), 右边界=判定线
HIT_BUFFER = 0.25                     # 输入缓冲窗口(秒)
CHORD_GAP = 0.035                     # 和弦判定: 间隔小于此视为同时
HIT_FX = 0.28                         # 命中特效时长(秒): 圆圈放大渐隐
HIT_SCALE = 0.9                       # 命中放大倍数(1+0.9=放大到1.9倍)
NOTE_MIN_GAP = 34                     # 和弦音符最小间距(px)

# 计分(原版减半, 取 5/10 倍数)
SCORE_PERFECT_BASE = 15      # 完美基础分
SCORE_PERFECT_STEP = 5      # 连续完美递增
SCORE_PERFECT_MAX = 100      # 完美封顶
SCORE_NONPERFECT = 5         # 命中但不完美(Great/Good)
SCORE_MISS_BASE = 75                  # 按错基础扣分
SCORE_MISS_STEP = 50                  # 连续按错递增
SCORE_MISS_MAX = 225                  # 单次扣分上限(第4次封顶)
SCORE_BONUS_FULL = 50        # 大灯小灯全亮 bonus
LIGHTS_BIG_START = 2
LIGHTS_BIG_MAX = 5

# 按键配色: A/; 粉红  D/K 绿  S/L 橘黄  F/J 浅紫
KEY_COLORS = {
    'a': (255, 120, 180), ';': (255, 120, 180),
    'd': (90, 200, 120), 'k': (90, 200, 120),
    's': (255, 165, 70), 'l': (255, 165, 70),
    'f': (170, 140, 255), 'j': (170, 140, 255),
}

# 浅色主题
COL_BG = (238, 242, 250)
COL_PANEL = (255, 255, 255)
COL_LANE_BG = (228, 231, 238)              # 轨道区浅灰背景
COL_LANE_LINE = (205, 215, 235)
COL_JUDGE = (90, 130, 220)
COL_TEXT = (50, 60, 85)
COL_TEXT_SUB = (110, 125, 155)
COL_RAIN = (150, 175, 210)
COL_ACCENT = (255, 210, 90)
COL_LAMP_ON = (255, 205, 90)
COL_LAMP_OFF = (200, 208, 225)

FONT_PATH = os.path.join(BASE, 'src', 'fonts', 'NotoSansCJK-Regular.ttc')
FONT_BOLD = os.path.join(BASE, 'src', 'fonts', 'NotoSansCJK-Bold.ttc')

# 指法映射（原版: hard=全键盘, normal=按指法归 8 组 -> ASDFJKL;）
FINGER = {}
for _k in 'qaz': FINGER[_k] = 'Lp'
for _k in 'wsx': FINGER[_k] = 'Lr'
for _k in 'edc': FINGER[_k] = 'Lm'
for _k in 'rfvtgb': FINGER[_k] = 'Li'
for _k in 'yhnujm': FINGER[_k] = 'Ri'
for _k in 'ik': FINGER[_k] = 'Rm'
for _k in 'ol': FINGER[_k] = 'Rr'
for _k in "p;',./<>": FINGER[_k] = 'Rp'
FINGER_TO_LANE = {'Lp': 0, 'Lr': 1, 'Lm': 2, 'Li': 3, 'Ri': 4, 'Rm': 5, 'Rr': 6, 'Rp': 7}


def key_to_lane(key, lanes):
    """谱面内部键 -> 轨道索引（原版指法映射）"""
    f = FINGER.get(key)
    if f is None:
        return 0
    return FINGER_TO_LANE[f]


def lamp_color_for(n):
    """大灯颜色随点亮数变化: ≤2 浅红 / 3 浅黄 / 4 浅蓝 / 5 浅绿"""
    if n <= 2:
        return (255, 135, 135)
    if n == 3:
        return (255, 215, 110)
    if n == 4:
        return (130, 180, 255)
    return (130, 220, 140)
