# -*- coding: utf-8 -*-
"""演奏场景: 判定/计分/亮灯/音符/背景/歌词/UI"""
import os
import random
import re
import pygame
from config import *
from utils import get_slow_ogg, make_note_surface, parse_anime
class PlayScene:
    def __init__(self, app, song, start_pct=0):
        self.app = app
        self.song = song
        self.start_pct = start_pct
        self.lanes = LANES_NORMAL
        self.player = LANES_NORMAL
        self.auto = set()
        # 谱面事件: (轨道, 时间, 采样, 内部键)
        self.speed = app.speed
        self.slow_factor = app.slow_factor
        self.time_scale = self.slow_factor        # <1 慢放(时间轴拉长), >1 加速
        self.events = [(key_to_lane(k, self.lanes), t, s, k) for t, s, k in song.notes]
        self.events.sort(key=lambda e: e[1])
        self.events = [e for e in self.events if e[1] < song.duration]
        # 和弦分组: 同时刻(±CHORD_GAP)的多音符 -> 组
        self.chord_groups = {}
        cur = [0]
        for i in range(1, len(self.events)):
            if self.events[i][1] - self.events[cur[0]][1] < CHORD_GAP:
                cur.append(i)
            else:
                if len(cur) > 1:
                    for j in cur:
                        self.chord_groups[j] = cur
                cur = [i]
        if len(cur) > 1:
            for j in cur:
                self.chord_groups[j] = cur
        # 慢速模式: 谱面时间轴按比例拉伸(与慢放音频对齐)
        if self.time_scale != 1.0:
            self.events = [(l, t / self.time_scale, s, k) for l, t, s, k in self.events]

        self.notes_active = []
        self.lead_time = (W - JUDGE_X) / (NOTE_SPEED * self.speed)   # 出现到判定时间
        self.duration = song.duration / self.time_scale
        self.start_time = self.duration * self.start_pct / 100.0
        self.idx = 0
        if self.start_time > 0:
            # 跳过起始点之前已过判定窗口的音符(保留窗口内的)
            while self.idx < len(self.events) and self.events[self.idx][1] < self.start_time - WIN_GOOD:
                self.idx += 1
        self.t0 = None
        self.now = 0.0
        self.finished = False

        self.stats = {'perfect': 0, 'great': 0, 'good': 0, 'miss': 0}
        self.score = 0
        self.max_combo = 0
        self.combo = 0
        self.perfect_combo = 0
        self.miss_streak = 0          # 连续按错次数(用于扣分递增)
        self.lights_small = 0
        self.lights_big = LIGHTS_BIG_START
        self.hit_buffer = []
        self.auto_play = False        # AUTO 自动演奏(Tab切换, 不记分)
        self.paused = False           # 暂停(空格切换): 快照冻结, 恢复=从该秒数重进
        self.snapshot = None          # 暂停快照: time/score/combo/lights/stats
        self.last_judge = None        # (文本, 颜色)
        self.last_judge_until = 0.0   # 判定特效绝对过期时间
        self.lyric_now = None      # (ja, cn)
        # 歌词显示: 每时间点聚合 日文(JA)+中文(CN优先,ZH兜底), 显示到下一句(上限10s)
        by_time = {}
        for t, lang, text in song.lyrics:
            if lang not in ('JA', 'CN', 'ZH'):
                continue
            by_time.setdefault(t, {})[lang] = text
        all_ts = sorted(by_time.keys())
        self.lyric_rows = []
        for i, t in enumerate(all_ts):
            nxt = all_ts[i + 1] if i + 1 < len(all_ts) else t + 10.0
            end = min(nxt, t + 10.0)
            d = by_time[t]
            ja = d.get('JA', '')
            cn = d.get('CN') or d.get('ZH') or ''
            if self.time_scale != 1.0:
                t = t / self.time_scale
                end = end / self.time_scale
            self.lyric_rows.append((t, end, ja, cn))
        self.raindrops = [self.new_raindrop(force=True) for _ in range(100)]
        self.sounds = {}
        self.sound_names = sorted({s for _, _, s, _ in self.events})
        # ---- Anime 演出脚本驱动: 背景/口型 ----
        self.bgpic = None                 # 静态背景图(缩放后)
        self.bganims = {}                 # 编号 -> {frames:[surface], active, fade_t0, fade_dur}
        self.anime_events = []            # [(t, cmd, args)] 缩放后
        self.anime_idx = 0
        self.anime_pos = None
        anime_file = None
        for sub in ('Song', 'Event', 'Event2', 'Event3', 'Event4'):
            for name in ('Anime_cn.txt', 'Anime_zh.txt', 'Anime_ja.txt', 'Anime.txt'):
                f = os.path.join(song.dir, sub, name)
                if os.path.exists(f):
                    anime_file = f
                    break
            if anime_file:
                break
        if anime_file:
            anime = parse_anime(anime_file)
            # 静态背景
            for _id, name in anime['bgpic'].items():
                for sub in ('Song', 'Event', 'Event2', 'Event3', 'Event4'):
                    pth = os.path.join(song.dir, sub, name)
                    if os.path.exists(pth):
                        try:
                            img = pygame.image.load(pth).convert_alpha()
                            self.bgpic = pygame.transform.smoothscale(
                                img, (W, int(W * img.get_height() / img.get_width())))
                            break
                        except Exception:
                            pass
            # 背景动画
            for _id, spec in anime['bganim'].items():
                frames = []
                for fn in spec['files']:
                    for sub in ('Song', 'Event', 'Event2', 'Event3', 'Event4'):
                        pth = os.path.join(song.dir, sub, fn)
                        if os.path.exists(pth):
                            try:
                                img = pygame.image.load(pth).convert_alpha()
                                frames.append(pygame.transform.smoothscale(
                                    img, (W, int(W * img.get_height() / img.get_width()))))
                                break
                            except Exception:
                                pass
                if frames:
                    self.bganims[_id] = {'frames': frames, 'active': False,
                                         'fade_t0': 0.0, 'fade_dur': 0.0}
            # 事件 (时间按倍速缩放)
            self.anime_pos = anime['pos']
            self.anime_events = [(t / self.time_scale, cmd, args)
                                 for t, cmd, args in anime['events']]
        # 兜底背景: 无 Anime 时用 bg0x/songbg
        if self.bgpic is None and not self.bganims:
            for sub in ('Song', 'Event', 'Event2', 'Event3', 'Event4'):
                for name in ('songbg_cn.png', 'songbg_zh.png', 'songbg_ja.png', 'bg00.png'):
                    pth = os.path.join(song.dir, sub, name)
                    if os.path.exists(pth):
                        try:
                            img = pygame.image.load(pth).convert_alpha()
                            self.bgpic = pygame.transform.smoothscale(
                                img, (W, int(W * img.get_height() / img.get_width())))
                            break
                        except Exception:
                            pass
                if self.bgpic is not None:
                    break

        self.lead_time = (W - JUDGE_X) / (NOTE_SPEED * self.speed)   # 出现到判定时间
        self.duration = song.duration / self.time_scale
        self.start_time = self.duration * self.start_pct / 100.0
        self.idx = 0
        if self.start_time > 0:
            # 跳过起始点之前已过判定窗口的音符(保留窗口内的)
            while self.idx < len(self.events) and self.events[self.idx][1] < self.start_time - WIN_GOOD:
                self.idx += 1
        self.t0 = None
        self.now = 0.0
        self.finished = False

        self.stats = {'perfect': 0, 'great': 0, 'good': 0, 'miss': 0}
        self.score = 0
        self.max_combo = 0
        self.combo = 0
        self.perfect_combo = 0
        self.miss_streak = 0          # 连续按错次数(用于扣分递增)
        self.lights_small = 0
        self.lights_big = LIGHTS_BIG_START
        self.hit_buffer = []
        self.auto_play = False        # AUTO 自动演奏(Tab切换, 不记分)
        self.paused = False           # 暂停(空格切换): 快照冻结, 恢复=从该秒数重进
        self.snapshot = None          # 暂停快照: time/score/combo/lights/stats
        self.last_judge = None        # (文本, 颜色)
        self.last_judge_until = 0.0   # 判定特效绝对过期时间
        self.lyric_now = None      # (ja, cn)
        # 歌词显示: 每时间点聚合 日文(JA)+中文(CN优先,ZH兜底), 显示到下一句(上限10s)
        by_time = {}
        for t, lang, text in song.lyrics:
            if lang not in ('JA', 'CN', 'ZH'):
                continue
            by_time.setdefault(t, {})[lang] = text
        all_ts = sorted(by_time.keys())
        self.lyric_rows = []
        for i, t in enumerate(all_ts):
            nxt = all_ts[i + 1] if i + 1 < len(all_ts) else t + 10.0
            end = min(nxt, t + 10.0)
            d = by_time[t]
            ja = d.get('JA', '')
            cn = d.get('CN') or d.get('ZH') or ''
            if self.time_scale != 1.0:
                t = t / self.time_scale
                end = end / self.time_scale
            self.lyric_rows.append((t, end, ja, cn))
        self.raindrops = [self.new_raindrop(force=True) for _ in range(100)]
        self.sounds = {}
        self.sound_names = sorted({s for _, _, s, _ in self.events})
        # 背景图集合: Song/Event* 目录下 songbg/bg\d+ (语言后缀算同一张), 自动轮换

    def new_raindrop(self, force=False):
        return {
            'x': random.uniform(0, W),
            'y': random.uniform(-H, 0) if not force else random.uniform(0, H),
            'v': random.uniform(500, 900),
            'len': random.uniform(14, 30),
        }

    def get_sound(self, name):
        if name not in self.sounds:
            try:
                self.sounds[name] = pygame.mixer.Sound(os.path.join(self.song.dir, 'Key', name + '.ogg'))
            except Exception:
                self.sounds[name] = None
        return self.sounds[name]

    def save_snapshot(self):
        """保存当前状态: 时间/得分/连击/亮灯/统计"""
        return {
            'time': self.now,
            'score': self.score,
            'combo': self.combo,
            'max_combo': self.max_combo,
            'perfect_combo': self.perfect_combo,
            'lights_big': self.lights_big,
            'lights_small': self.lights_small,
            'miss_streak': self.miss_streak,
            'stats': dict(self.stats),
            'auto_play': self.auto_play,
        }

    def resume_from(self, sec, snap=None):
        """从指定秒数重新进入游戏(音乐重载+索引重置);
        snap 提供时覆盖得分/连击/亮灯等成绩状态"""
        self.paused = False
        self.start_time = max(0.0, min(float(sec), self.duration))
        # 重置音符索引: 跳过该秒数之前已过判定窗口的
        self.idx = 0
        while self.idx < len(self.events) and self.events[self.idx][1] < self.start_time - WIN_GOOD:
            self.idx += 1
        self.notes_active = []
        self.hit_buffer = []
        self.lyric_now = None
        # 背景事件索引推进到该秒数, 避免重放已触发事件
        while self.anime_idx < len(self.anime_events) and self.anime_events[self.anime_idx][0] <= self.start_time:
            self.anime_idx += 1
        self.start()                            # 重新加载音乐并从该秒数播放
        self.now = self.start_time
        if snap:
            self.score = snap['score']
            self.combo = snap['combo']
            self.max_combo = snap['max_combo']
            self.perfect_combo = snap['perfect_combo']
            self.lights_big = snap['lights_big']
            self.lights_small = snap['lights_small']
            self.miss_streak = snap['miss_streak']
            self.stats = dict(snap['stats'])
            self.auto_play = snap['auto_play']
        self.last_judge = None

    def seek_by(self, delta):
        """前后跳转 delta 秒, 保留当前成绩"""
        self.resume_from(self.now + delta, self.save_snapshot())

    def toggle_pause(self):
        """暂停=快照冻结; 恢复=从该秒数重新进入并覆盖成绩状态"""
        if not self.paused:
            self.snapshot = self.save_snapshot()
            self.paused = True
            pygame.mixer.music.pause()
            return
        snap = self.snapshot
        self.resume_from(snap['time'], snap)

    def start(self):
        # 音乐开局立即启动; 音符延迟 LEAD_TIME 秒出现, 滚动 3 秒到判定区
        if self.slow_factor != 1.0:
            pygame.mixer.music.load(get_slow_ogg(self.song.dir, self.slow_factor))
        else:
            pygame.mixer.music.load(os.path.join(self.song.dir, 'song.ogg'))
        pygame.mixer.music.play(start=self.start_time)
        self.t0 = pygame.time.get_ticks() / 1000.0 - self.start_time

    # ---- 判定 ----
    def judge(self, lane, now):
        best, best_dt = None, 1e9
        for n in self.notes_active:
            if n['lane'] == lane and not n['judged']:
                dt = abs(now - n['time'])
                if dt < best_dt:
                    best, best_dt = n, dt
        if best is not None and best_dt <= WIN_GOOD:
            self.apply_judge(best, self.grade_for(best_dt), now)
            return
        nxt = None
        for n in self.notes_active:
            if n['lane'] == lane and not n['judged']:
                if nxt is None or n['time'] < nxt['time']:
                    nxt = n
        if nxt is not None and 0 <= nxt['time'] - now <= HIT_BUFFER:
            self.hit_buffer.append((lane, now))
            return
        self.punish_miss()

    def grade_for(self, dt):
        if dt <= WIN_PERFECT:
            return 'perfect'
        if dt <= WIN_GREAT:
            return 'great'
        return 'good'

    def punish_miss(self):
        if self.lights_small > 0:
            self.lights_small -= 1
        elif self.lights_big > 0:
            self.lights_big -= 1
        self.perfect_combo = 0
        self.combo = 0
        # 连续按错: 75, 125, 175, 225... 封顶 225; 分数不低于 0
        penalty = min(SCORE_MISS_BASE + SCORE_MISS_STEP * self.miss_streak, SCORE_MISS_MAX)
        self.miss_streak += 1
        self.score = max(0, self.score - penalty)
        self.last_judge = ('MISS', (220, 90, 90))
        self.last_judge_until = self.now + 0.6

    def apply_judge(self, note, grade, press_time=None):
        note['judged'] = True
        note['judged_at'] = self.now
        self.miss_streak = 0          # 命中重置连续按错计数
        self.stats[grade] += 1
        if grade == 'perfect':
            self.perfect_combo += 1
            pts = min(SCORE_PERFECT_BASE + SCORE_PERFECT_STEP * (self.perfect_combo - 1),
                      SCORE_PERFECT_MAX)
            if self.lights_big >= LIGHTS_BIG_MAX and self.lights_small >= 10:
                pts += SCORE_BONUS_FULL
            self.score += pts
            self.lights_small += 1
            if self.lights_small >= 10:
                if self.lights_big < LIGHTS_BIG_MAX:
                    self.lights_small = 0
                    self.lights_big += 1
                else:
                    self.lights_small = 10
        else:
            self.perfect_combo = 0
            self.score += SCORE_NONPERFECT
        self.combo = self.perfect_combo
        self.max_combo = max(self.max_combo, self.combo)
        self.last_judge = (grade.upper(), self.app.color_grade(grade))
        self.last_judge_until = self.now + 0.6
        snd = self.get_sound(note['sample'])
        if snd:
            snd.play()

    # ---- 更新 ----
    def update(self, now):
        # Anime 事件触发: BGPIC/BGANIM/CHAR00
        while self.anime_idx < len(self.anime_events):
            t, cmd, args = self.anime_events[self.anime_idx]
            if t > now:
                break
            self.anime_idx += 1
            if cmd == 'BGPIC':
                pass      # 静态背景已在 Load 确定, 事件多为重复
            elif cmd == 'BGANIM' and args:
                bid = args[0]
                fade = args[1] if len(args) > 1 else 0
                if bid in self.bganims:
                    b = self.bganims[bid]
                    b['active'] = True
                    b['fade_t0'] = now
                    b['fade_dur'] = float(fade)
            elif cmd == 'CHAR00':
                pass      # 口型功能已移除
        # 背景动画帧索引(1.5s/帧交替)
        self.bg_anim_frame = int(now / 1.5)
        for r in self.raindrops:
            r['y'] += r['v'] * (1 / FPS)
            if r['y'] > H:
                self.raindrops.remove(r)
                self.raindrops.append(self.new_raindrop())
        # 生成音符
        while self.idx < len(self.events):
            lane, t, s, k = self.events[self.idx]
            if t - now < self.lead_time:
                self.notes_active.append({
                    'lane': lane, 'time': t, 'sample': s, 'key': k,
                    'judged': False, 'auto': lane in self.auto,
                    'group': self.chord_groups.get(self.idx),
                    'judged_at': None,
                })
                self.idx += 1
            else:
                break
        # AUTO 自动演奏: 到点自动判定(音效+特效), 不记录分数/灯/连击
        if self.auto_play:
            for n in self.notes_active:
                if n['judged']:
                    continue
                if now >= n['time']:
                    n['judged'] = True
                    n['judged_at'] = self.now
                    snd = self.get_sound(n['sample'])
                    if snd:
                        snd.play()
            self.hit_buffer.clear()
        # 输入缓冲匹配
        elif self.hit_buffer:
            for n in self.notes_active:
                if n['judged']:
                    continue
                for hb in list(self.hit_buffer):
                    if hb[0] == n['lane'] and now >= n['time'] - WIN_PERFECT:
                        dt = n['time'] - hb[1]
                        if dt > HIT_BUFFER:
                            continue
                        if dt <= WIN_GREAT:
                            grade = 'perfect' if dt <= WIN_PERFECT else 'great'
                        else:
                            grade = 'good'
                        self.hit_buffer.remove(hb)
                        self.apply_judge(n, grade, hb[1])
                        break
            self.hit_buffer = [hb for hb in self.hit_buffer if now - hb[1] < HIT_BUFFER + 0.3]
        # auto 演奏 & miss
        for n in self.notes_active:
            if n['judged']:
                continue
            if n['auto'] and now >= n['time']:
                self.apply_judge(n, 'perfect', now)
            elif now - n['time'] > WIN_GOOD:
                n['judged'] = True
                self.stats['miss'] += 1
                self.punish_miss()
        self.notes_active = [n for n in self.notes_active
                             if (not n['judged']) or (now - n['time'] < 1.2)]
        # 歌词: 当前句 日文+中文, 过期即清空
        self.lyric_now = None
        for t, end, ja, cn in self.lyric_rows:
            if t <= now < end:
                self.lyric_now = (ja, cn)
                break
        if now > self.duration + 1.5 and not self.finished:
            self.finished = True
            self.app.show_result(self)

    # ---- 绘制 ----
    def draw(self, screen):
        screen.fill(COL_BG)
        if self.bgpic is not None:
            screen.blit(self.bgpic, (0, 0))
        # 背景动画叠放(按编号), 带淡入
        for bid in sorted(self.bganims):
            b = self.bganims[bid]
            if not b['active']:
                continue
            fr = b['frames'][(self.bg_anim_frame // max(len(b['frames']), 1)) % len(b['frames'])]
            if b['fade_dur'] > 0 and self.now - b['fade_t0'] < b['fade_dur']:
                fade = pygame.Surface(fr.get_size(), pygame.SRCALPHA)
                fade.blit(fr, (0, 0))
                fade.set_alpha(int(255 * min((self.now - b['fade_t0']) / b['fade_dur'], 1.0)))
                screen.blit(fade, (0, 0))
            else:
                screen.blit(fr, (0, 0))
        self.draw_rain(screen)
        self.draw_lanes(screen)
        self.draw_notes(screen)
        self.draw_ui(screen)

    def draw_rain(self, screen):
        for r in self.raindrops:
            x = r['x']
            pygame.draw.line(screen, COL_RAIN, (x, r['y']), (x, r['y'] + r['len']), 1)

    def lane_y(self, i):
        n = len(self.lanes)
        lane_h = (LANE_BOT - LANE_TOP) / n
        return LANE_BOT - (i + 1) * lane_h

    def lane_cy(self, i):
        n = len(self.lanes)
        lane_h = (LANE_BOT - LANE_TOP) / n
        return LANE_BOT - (i + 0.5) * lane_h

    def draw_lanes(self, screen):
        n = len(self.lanes)
        lane_h = (LANE_BOT - LANE_TOP) / n
        for i in range(n):
            y = self.lane_y(i)
            rect = pygame.Rect(int(JUDGE_X), int(y), int(W - JUDGE_X), int(lane_h) + 1)
            pygame.draw.rect(screen, COL_LANE_BG, rect)
            pygame.draw.line(screen, COL_LANE_LINE, (JUDGE_X, y), (W, y), 1)
            # 判定矩形框(按键配色, 半透明填充, 右边界=判定线)
            color = KEY_COLORS[self.lanes[i]]
            box = pygame.Rect(int(JUDGE_X - JUDGE_BOX_W), int(y), JUDGE_BOX_W, int(lane_h) + 1)
            fill = pygame.Surface((box.w, box.h), pygame.SRCALPHA)
            fill.fill((*color, 36))
            screen.blit(fill, box.topleft)
            pygame.draw.rect(screen, color, box, 3, border_radius=6)
            # 右边界加粗 = 判定时刻
            pygame.draw.line(screen, color, (int(JUDGE_X), int(y)), (int(JUDGE_X), int(y + lane_h)), 6)

    def draw_notes(self, screen):
        spd = NOTE_SPEED * self.speed
        vis, fx = [], []
        for n in self.notes_active:
            x = JUDGE_X + (n['time'] - self.now) * spd
            if x > W + 60 or x < JUDGE_X - 120:
                continue
            if n['judged']:
                if n.get('judged_at') is not None and self.now - n['judged_at'] < HIT_FX:
                    fx.append((n, x))
                continue
            vis.append((n, x))
        # 和弦连接线(未判定音符)
        drawn_pairs = set()
        for n, x in vis:
            grp = n['group']
            if grp and len(grp) > 1:
                mates = [m for m, mx in vis if m is not n and m['group'] is grp]
                for m in mates:
                    key = (id(n), id(m))
                    if key in drawn_pairs or (id(m), id(n)) in drawn_pairs:
                        continue
                    drawn_pairs.add(key)
                    mx = JUDGE_X + (m['time'] - self.now) * spd
                    y1 = self.note_y(n)
                    y2 = self.note_y(m)
                    pygame.draw.line(screen, (150, 165, 195), (x, y1), (mx, y2), 5)
                    pygame.draw.circle(screen, (150, 165, 195), (int(x), int(y1)), 5)
                    pygame.draw.circle(screen, (150, 165, 195), (int(mx), int(y2)), 5)
        # 命中特效: 音符符号放大 + 渐隐后消失
        for n, x in fx:
            p = (self.now - n['judged_at']) / HIT_FX
            color = KEY_COLORS[self.lanes[n['lane']]]
            y_center = self.note_y(n)
            alpha = int(235 * (1 - p))
            ns, ax, ay = make_note_surface(self.app.fonts['key'], color, 1 + HIT_SCALE * p, alpha,
                                           self.lanes[n['lane']].upper())
            screen.blit(ns, (x - ax, y_center - ay))
        # 未判定音符: 音符符号(符头+符杆+符旗), 键字母白色标注
        for n, x in vis:
            y_center = self.note_y(n)
            color = KEY_COLORS[self.lanes[n['lane']]]
            ns, ax, ay = make_note_surface(self.app.fonts['key'], color, 1.0, 255,
                                           self.lanes[n['lane']].upper())
            screen.blit(ns, (x - ax, y_center - ay))

    def note_y(self, n):
        """音符 y: 和弦组内向中间靠拢, 并保证最小间距"""
        cy = self.lane_cy(n['lane'])
        grp = n['group']
        if grp and len(grp) > 1:
            lanes = [self.events[j][0] for j in grp]
            if len(lanes) == 2:
                y1 = self.lane_cy(lanes[0])
                y2 = self.lane_cy(lanes[1])
                mid = (y1 + y2) / 2
                ny = cy + (mid - cy) * 0.55
                other = y2 if lanes[0] == n['lane'] else y1
                no = other + (mid - other) * 0.55
                if abs(ny - no) < NOTE_MIN_GAP:
                    # 间距不足 -> 围绕中点对称展开, 保持最小间距
                    ny = mid + NOTE_MIN_GAP / 2 if n['lane'] == min(lanes) else mid - NOTE_MIN_GAP / 2
                return ny
            mid = sum(self.lane_cy(l) for l in lanes) / len(lanes)
            return cy + (mid - cy) * 0.55
        return cy

    def draw_ui(self, screen):
        # 左上角时长计时 (mm:ss, 进入即开始)
        t = max(self.now, 0.0)
        tt = int(t // 60), int(t % 60)
        dt = int(self.duration // 60), int(self.duration % 60)
        time_txt = f'{tt[0]:02d}:{tt[1]:02d} / {dt[0]:02d}:{dt[1]:02d}'
        tr = self.app.fonts['ui'].render(time_txt, True, (255, 250, 240))
        bg_t = pygame.Surface((tr.get_width() + 24, tr.get_height() + 12), pygame.SRCALPHA)
        bg_t.fill((30, 40, 70, 150))
        screen.blit(bg_t, (16, 12))
        screen.blit(tr, (28, 18))
        # 歌词(背景图上, 半透明底条, 日文+中文双行)
        if self.lyric_now:
            ja, cn = self.lyric_now
            rows = []
            if ja:
                rows.append((self.app.fonts['lyric_ja'].render(ja, True, (235, 240, 255)), 20))
            if cn:
                rows.append((self.app.fonts['lyric'].render(cn, True, (255, 250, 240)), 26))
            if rows:
                bw = max(r.get_width() for r, _ in rows) + 44
                bh = sum(r.get_height() + 6 for r, _ in rows) + 14
                bg_lr = pygame.Surface((int(bw), int(bh)), pygame.SRCALPHA)
                bg_lr.fill((30, 40, 70, 150))
                screen.blit(bg_lr, (W / 2 - bw / 2, 78))
                cy = 86
                for r, _ in rows:
                    screen.blit(r, (W / 2 - r.get_width() / 2, cy))
                    cy += r.get_height() + 6
        # 左下角信息面板: 亮灯系统 + 得分/连击/歌名/判定特效
        panel = pygame.Rect(16, 590, 290, 300)
        pygame.draw.rect(screen, (225, 232, 245), panel, border_radius=12)
        px = panel.x + 14
        # 歌名 + 难度
        t = self.app.fonts['ui'].render(f"{self.song.sid} {self.song.title}", True, COL_TEXT)
        screen.blit(t, (px, panel.y + 10))
        mode = self.app.fonts['hint'].render('NORMAL', True, COL_TEXT_SUB)
        screen.blit(mode, (px, panel.y + 36))
        # 大灯 5 个
        ly = panel.y + 66
        lc = lamp_color_for(self.lights_big)
        for i in range(LIGHTS_BIG_MAX):
            color = lc if i < self.lights_big else COL_LAMP_OFF
            pygame.draw.rect(screen, color, (px + i * 50, ly, 42, 28), border_radius=6)
        # 小灯 10 个
        for i in range(10):
            color = COL_LAMP_ON if i < self.lights_small else COL_LAMP_OFF
            pygame.draw.circle(screen, color, (px + 13 + i * 13, ly + 44), 5)
        tip = self.app.fonts['hint'].render('4 灯及格 5 灯成功', True, COL_TEXT_SUB)
        screen.blit(tip, (px, ly + 58))
        # 得分 / 连击
        sc = self.app.fonts['ui'].render(f"SCORE  {self.score}", True, (200, 140, 30))
        screen.blit(sc, (px, ly + 92))
        cb = self.app.fonts['ui'].render(f"COMBO  {self.combo}", True, COL_TEXT)
        screen.blit(cb, (px, ly + 122))
        # 判定特效文字
        # 右上角提示: AUTO / 暂停
        if self.auto_play:
            auto = self.app.fonts['auto'].render('AUTO', True, (255, 110, 110))
            screen.blit(auto, (W - auto.get_width() - 100, 84))
        if self.paused:
            ps = self.app.fonts['auto'].render('PAUSED', True, (210, 50, 200))
            screen.blit(ps, (20, 84))
        if self.last_judge and self.now < self.last_judge_until:
            txt, color = self.last_judge
            jr = self.app.fonts['result'].render(txt, True, color)
            screen.blit(jr, (px, ly + 162))
        elif self.last_judge and self.now >= self.last_judge_until:
            self.last_judge = None



# ----------------------------------------------------------------------------
# 应用
# ----------------------------------------------------------------------------
