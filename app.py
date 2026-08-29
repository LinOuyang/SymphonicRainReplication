# -*- coding: utf-8 -*-
"""应用: 菜单/结果/主循环"""
import os
import random
import pygame
from config import *
from song import Song
from play_scene import PlayScene

class App:
    def __init__(self, unpack=None):
        self.unpack = unpack           # main 注入的按需解压回调: unpack(sid)
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        pygame.mixer.set_num_channels(64)
        self.screen = pygame.Surface((W, H))          # 逻辑画布(1600x900), 布局基准
        self.window = pygame.display.set_mode((W, H))  # 实际窗口
        pygame.display.set_caption('交响乐之雨 — 复刻 (Symphonic Rain)')
        self.clock = pygame.time.Clock()
        self.fonts = self.load_fonts()
        self.songs = []
        for i in range(1, 19):
            sid = f'SR{i:02d}'
            if os.path.isdir(SONG_DIR % i) or os.path.exists(SONG_DIR % i + '.zip'):
                try:
                    self.songs.append(Song(sid))
                except Exception as e:
                    print(f'{sid} 加载失败: {e}')
        self.state = 'menu'
        self.menu_idx = 0
        self.speed_idx = 6            # 默认 1.0x
        self.speed = SPEEDS[self.speed_idx]
        self.slow_idx = 3             # 倍速档位, 默认 1.0x (正常)
        self.slow_factor = SLOW_SPEEDS[self.slow_idx]
        self.start_pct = 0            # 从曲目 XX% 开始 (P 键 +10%)
        self.filter_digit = None      # 数字过滤: 只显示编号含该数字的曲目 (None=全部)
        self.mode_idx = 1             # 窗口分辨率档位 (0:1280x720 1:1600x900)
        self.fullscreen = False       # 全屏/窗口
        self.menu_buttons = self.build_menu_buttons()
        self.scene = None
        self.result = None
        self.result_t0 = 0
        self.now = 0.0
        self.running = True
        self.bgm_playing = False

    def load_fonts(self):
        def f(path, size):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                return pygame.font.SysFont('simsun,arial', size)
        return {
            'key': f(FONT_BOLD, 22),
            'key_small': f(FONT_BOLD, 18),
            'title': f(FONT_BOLD, 38),
            'title_small': f(FONT_BOLD, 22),
            'ui': f(FONT_PATH, 18),
            'lyric': f(FONT_BOLD, 27),
            'lyric_ja': f(FONT_PATH, 21),
            'judge': f(FONT_BOLD, 38),
            'auto': f(FONT_BOLD, 56),
            'result': f(FONT_BOLD, 28),
            'hint': f(FONT_PATH, 16),
        }

    def color_grade(self, grade):
        return {
            'perfect': (240, 190, 60),
            'great': (90, 190, 110),
            'good': (90, 150, 240),
            'miss': (220, 90, 90),
        }[grade]

    def show_result(self, scene):
        self.result = scene
        self.result_t0 = self.now
        self.state = 'result'
        pygame.mixer.music.stop()

    def filtered_songs(self):
        """按数字过滤后的歌曲列表"""
        if self.filter_digit is None:
            return self.songs
        d = str(self.filter_digit)
        return [s for s in self.songs if d in s.sid]

    def build_menu_buttons(self):
        """主界面左侧竖排三个显示模式按钮"""
        btns = []
        labels = [('窗口 1280x720', 0), ('窗口 1600x900', 1), ('全屏', None)]
        for i, (label, mode) in enumerate(labels):
            r = pygame.Rect(100, 200 + i * 66, 190, 54)
            if mode is None:
                action = self.toggle_fullscreen
            else:
                action = (lambda m=mode: self.set_window_mode(m))
            btns.append((r, action, label))
        return btns

    def apply_display(self):
        if self.fullscreen:
            info = pygame.display.Info()
            self.window = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(RESOLUTIONS[self.mode_idx])

    def set_window_mode(self, m):
        self.mode_idx = m
        self.fullscreen = False
        self.apply_display()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.apply_display()

    def on_click(self, x, y):
        if self.state != 'menu':
            return
        for rect, action, _ in self.menu_buttons:
            if rect.collidepoint(x, y):
                action()

    def start_play(self):
        # 先停主界面 BGM, 避免与歌曲音乐冲突
        if self.bgm_playing:
            pygame.mixer.music.stop()
            self.bgm_playing = False
        fl = self.filtered_songs()
        if not fl:
            return
        song = fl[self.menu_idx % len(fl)]
        if self.unpack:
            self.unpack(song.sid)    # 按需解压: src/SRXX.zip -> src/SRXX/ 并删 zip
        self.scene = PlayScene(self, song, self.start_pct)
        self.state = 'play'
        self.scene.start()

    def run(self):
        while self.running:
            self.clock.tick(FPS)
            self.now = pygame.time.get_ticks() / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN:
                    self.on_key(ev.key)
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    sw, sh = self.window.get_size()
                    self.on_click(int(ev.pos[0] * W / sw), int(ev.pos[1] * H / sh))
            self.update()
            self.draw()
            pygame.transform.scale(self.screen, self.window.get_size(), self.window)
            pygame.display.flip()
        pygame.quit()

    def on_key(self, key):
        if self.state == 'menu':
            if pygame.K_0 <= key <= pygame.K_9:
                d = key - pygame.K_0
                self.filter_digit = None if self.filter_digit == d else d
                self.menu_idx = 0
            elif key in (pygame.K_UP, pygame.K_k):        # vim: k = 上
                self.menu_idx = (self.menu_idx - 1) % len(self.songs)
            elif key in (pygame.K_DOWN, pygame.K_j):      # vim: j = 下
                self.menu_idx = (self.menu_idx + 1) % len(self.songs)
            elif key in (pygame.K_LEFT, pygame.K_h):      # vim: h = 左
                self.speed_idx = (self.speed_idx - 1) % len(SPEEDS)
                self.speed = SPEEDS[self.speed_idx]
            elif key in (pygame.K_RIGHT, pygame.K_l):     # vim: l = 右
                self.speed_idx = (self.speed_idx + 1) % len(SPEEDS)
                self.speed = SPEEDS[self.speed_idx]
            elif key == pygame.K_s:
                self.slow_idx = (self.slow_idx + 1) % len(SLOW_SPEEDS)
                self.slow_factor = SLOW_SPEEDS[self.slow_idx]
            elif key == pygame.K_p:
                self.start_pct = (self.start_pct + 10) % 100
            elif key == pygame.K_f:
                self.toggle_fullscreen()
            elif key == pygame.K_RETURN:
                self.start_play()
            elif key == pygame.K_ESCAPE:
                self.running = False
        elif self.state == 'play':
            if key == pygame.K_ESCAPE:
                pygame.mixer.music.stop()
                self.state = 'menu'
                return
            if key == pygame.K_LEFT:
                self.scene.seek_by(-SEEK_SECONDS)
                return
            if key == pygame.K_RIGHT:
                self.scene.seek_by(SEEK_SECONDS)
                return
            if key == pygame.K_TAB:
                self.scene.auto_play = not self.scene.auto_play
                return
            if key == pygame.K_SPACE:
                self.scene.toggle_pause()
                return
            if self.scene.paused:
                return      # 暂停期间按键无效
            if self.scene.auto_play:
                return      # AUTO 期间玩家按键无效
            ch = pygame.key.name(key).lower()
            if ch in self.scene.player:
                self.scene.judge(self.scene.lanes.index(ch), self.now - self.scene.t0)
        elif self.state == 'result':
            if key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                self.state = 'menu'

    def update_bgm(self):
        """主界面循环播放 BGM, 演奏/结果时停止"""
        if self.state == 'menu':
            if not self.bgm_playing:
                try:
                    pygame.mixer.music.load(os.path.join(BASE, 'src', 'track', 'main_title.ogg'))
                    pygame.mixer.music.play(-1)
                    self.bgm_playing = True
                except Exception:
                    pass
        elif self.bgm_playing:
            pygame.mixer.music.stop()
            self.bgm_playing = False

    def update(self):
        self.update_bgm()
        if self.state == 'play':
            if self.scene.paused:
                return      # 暂停: 时间/音符/判定全部冻结
            now = self.now - self.scene.t0
            self.scene.now = now
            if now >= 0:
                self.scene.update(now)

    def draw(self):
        if self.state == 'menu':
            self.draw_menu()
        elif self.state == 'play':
            self.draw_play()
        elif self.state == 'result':
            self.draw_result()

    def draw_menu(self):
        self.screen.fill(COL_BG)
        self.raindrops_menu()
        title = self.fonts['title'].render('交响乐之雨  —  演奏模式', True, COL_TEXT)
        self.screen.blit(title, (W / 2 - title.get_width() / 2, 30))
        sub = self.fonts['hint'].render('↑/↓(jk) 选歌  ←/→(hl) 滚动  数字过滤  S 倍速  P 起始  F 全屏', True, COL_TEXT_SUB)
        self.screen.blit(sub, (W / 2 - sub.get_width() / 2, 84))
        # 左侧显示模式按钮
        cur_mode = 2 if self.fullscreen else self.mode_idx
        for i, (rect, _, label) in enumerate(self.menu_buttons):
            active = (i == cur_mode)
            pygame.draw.rect(self.screen, (255, 228, 160) if active else (215, 224, 240),
                             rect, border_radius=10)
            pygame.draw.rect(self.screen, (180, 150, 80) if active else (160, 175, 200),
                             rect, 2, border_radius=10)
            lbl = self.fonts['ui'].render(label, True, (120, 80, 20) if active else COL_TEXT)
            self.screen.blit(lbl, (rect.x + 12, rect.y + rect.h / 2 - lbl.get_height() / 2))
        fl = self.filtered_songs()
        y0 = 140
        for i, s in enumerate(fl):
            y = y0 + i * 34
            if i == self.menu_idx % len(fl):
                pygame.draw.rect(self.screen, (255, 228, 160), (W / 2 - 260, y - 4, 520, 32))
                color = (170, 110, 20)
            else:
                color = COL_TEXT_SUB
            line = self.fonts['ui'].render(f"{s.sid}  {s.title}", True, color)
            self.screen.blit(line, (W / 2 - 240, y))
        filt_txt = f'  数字过滤: {self.filter_digit}' if self.filter_digit is not None else ''
        sf = self.slow_factor
        slow_txt = '正常' if sf == 1.0 else ('慢速' if sf < 1.0 else '加速')
        info = self.fonts['ui'].render(f'NORMAL  ASDFJKL;    滚动 {self.speed:.1f}x  {slow_txt} {sf:g}x  起始 {self.start_pct}%{filt_txt}', True, (60, 110, 180))
        self.screen.blit(info, (W / 2 - info.get_width() / 2, H - 60))

    def raindrops_menu(self):
        if not hasattr(self, '_menu_rain'):
            self._menu_rain = [{'x': random.uniform(0, W), 'y': random.uniform(0, H),
                                'v': random.uniform(400, 800), 'l': random.uniform(12, 26)} for _ in range(70)]
        for r in self._menu_rain:
            r['y'] += r['v'] / FPS
            if r['y'] > H:
                r['y'] = -20
            pygame.draw.line(self.screen, COL_RAIN, (r['x'], r['y']), (r['x'], r['y'] + r['l']), 1)
        return self._menu_rain

    def draw_play(self):
        self.scene.draw(self.screen)

    def draw_result(self):
        s = self.result
        self.screen.fill(COL_BG)
        perfect, great, good, miss = s.stats['perfect'], s.stats['great'], s.stats['good'], s.stats['miss']
        lights = s.lights_big
        grade = '成功 ★' if lights >= 5 else '及格' if lights >= 4 else '未及格'
        t = self.fonts['title'].render(f"{s.song.sid}  {s.song.title}", True, COL_TEXT)
        self.screen.blit(t, (W / 2 - t.get_width() / 2, 50))
        lx = W / 2 - (5 * 52 - 8) / 2
        lc = lamp_color_for(lights)
        for i in range(LIGHTS_BIG_MAX):
            color = lc if i < lights else COL_LAMP_OFF
            pygame.draw.rect(self.screen, color, (lx + i * 52, 120, 44, 28), border_radius=6)
        g = self.fonts['title'].render(f"{grade}   ({lights}/5 大灯)", True, (200, 140, 30))
        self.screen.blit(g, (W / 2 - g.get_width() / 2, 175))
        lines = [
            f"分数  {s.score}",
            f"最大连击  {s.max_combo}",
            f"Perfect  {perfect}    Great  {great}    Good  {good}    Miss  {miss}",
        ]
        for i, ln in enumerate(lines):
            r = self.fonts['result'].render(ln, True, COL_TEXT)
            self.screen.blit(r, (W / 2 - r.get_width() / 2, 260 + i * 50))
        h = self.fonts['hint'].render('Enter / ESC 返回选歌', True, COL_TEXT_SUB)
        self.screen.blit(h, (W / 2 - h.get_width() / 2, H - 60))


if __name__ == '__main__':
    App().run()
