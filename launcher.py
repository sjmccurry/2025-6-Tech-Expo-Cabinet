import os, sys, json, math, time, subprocess, pygame
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum, auto

pygame.init()

# ---------- Drawing helpers (safe on pygame 1.9.x) ----------
def rrect(surf, rect, color, radius=0, width=0):
    try:
        pygame.draw.rect(surf, color, rect, width, border_radius=radius)
    except TypeError:
        pygame.draw.rect(surf, color, rect, width)

def scale_to_cover(surface, size):
    iw, ih = surface.get_size(); rw, rh = size
    sc = max(float(rw)/iw, float(rh)/ih)
    return pygame.transform.smoothscale(surface, (int(iw*sc), int(ih*sc)))

def blit_rounded_image(dst, img, rect, radius):
    if not img:
        rrect(dst, rect, (40,42,50), radius)
        return
    scaled = scale_to_cover(img, (rect.w, rect.h))
    layer = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    x = (rect.w - scaled.get_width())//2
    y = (rect.h - scaled.get_height())//2
    layer.blit(scaled, (x, y))
    mask = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    rrect(mask, mask.get_rect(), (255,255,255,255), radius)
    layer.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
    dst.blit(layer, rect.topleft)

def F(sz): return pygame.font.Font(None, sz)

# ---------- Joystick-only input ----------
class Action(Enum):
    LEFT=auto(); RIGHT=auto(); LAUNCH=auto(); BACK=auto()

class JoyInput:
    def __init__(self, joy_index=0, deadzone=0.35):
        self.deadzone = deadzone
        pygame.joystick.init()
        self.joy = None
        if pygame.joystick.get_count() > joy_index:
            self.joy = pygame.joystick.Joystick(joy_index); self.joy.init()
        if self.joy:
            print(f"[LAUNCHER] Using joystick: {self.joy.get_name()} | axes:{self.joy.get_numaxes()} buttons:{self.joy.get_numbuttons()} hats:{self.joy.get_numhats()}")
        else:
            print("[LAUNCHER] No joystick detected.")
        self.prev_btn = {}
        self.prev_hat = (0,0)
        self.prev_axis0 = 0.0
        self.prev_act = {a:False for a in Action}
        self.cur_act  = {a:False for a in Action}

    def _btn(self, i):
        return self.joy and self.joy.get_numbuttons() > i and self.joy.get_button(i)

    def update(self):
        # log button edges
        if self.joy:
            nb = self.joy.get_numbuttons()
            for b in range(nb):
                v = bool(self.joy.get_button(b))
                pv = self.prev_btn.get(b, False)
                if v != pv:
                    print(f"[LAUNCHER] BUTTON {b} {'DOWN' if v else 'UP'}")
                self.prev_btn[b] = v

            hat = (0,0)
            if self.joy.get_numhats() > 0:
                hat = self.joy.get_hat(0)
            if hat != self.prev_hat:
                print(f"[LAUNCHER] HAT0 -> {hat}")
            self.prev_hat = hat

            ax0 = self.joy.get_axis(0) if self.joy.get_numaxes() > 0 else 0.0
            # print only when crossing notable steps
            if abs(ax0 - self.prev_axis0) >= 0.1 or ax0 in (-1.0, 0.0, 1.0):
                print(f"[LAUNCHER] AXIS0 {ax0:+.2f}")
            self.prev_axis0 = ax0

            x = hat[0]
            if x == 0:
                if ax0 < -self.deadzone: x = -1
                elif ax0 > self.deadzone: x = +1

            self.cur_act[Action.LEFT]  = (x < 0)
            self.cur_act[Action.RIGHT] = (x > 0)
            self.cur_act[Action.LAUNCH]= bool(self._btn(0))
            self.cur_act[Action.BACK]  = bool(self._btn(1) or self._btn(7))
        else:
            for a in self.cur_act: self.cur_act[a] = False

    def pressed(self, act):
        was = self.prev_act[act]
        now = self.cur_act[act]
        self.prev_act[act] = now
        if now and not was:
            print(f"[LAUNCHER] ACTION {act.name} PRESSED")
        return now and not was

# ---------- Data ----------
@dataclass
class GameEntry:
    slug: str
    title: str
    subtitle: str
    path: str
    cover: Optional[pygame.Surface]
    accent: Tuple[int, int, int]


def load_cover(p):
    try: return pygame.image.load(p).convert_alpha()
    except Exception: return None

def discover_games(root):
    out=[]
    if not os.path.isdir(root): return out
    for slug in sorted(os.listdir(root)):
        p=os.path.join(root,slug)
        if not (os.path.isdir(p) and os.path.isfile(os.path.join(p,"main.py"))): continue
        title=slug.replace("_"," ").title(); subtitle=""; accent=(64,140,255)
        meta=os.path.join(p,"meta.json")
        if os.path.isfile(meta):
            try:
                j=json.load(open(meta,"r",encoding="utf-8"))
                title=j.get("title",title); subtitle=j.get("subtitle","")
                if isinstance(j.get("accent"),list) and len(j["accent"])==3: accent=tuple(int(x) for x in j["accent"])
            except Exception: pass
        cv=None
        for n in ("cover.png","cover.jpg","cover.jpeg","cover.webp"):
            cp=os.path.join(p,n)
            if os.path.isfile(cp): cv=load_cover(cp); break
        out.append(GameEntry(slug,title,subtitle,p,cv,accent))
    return out

# ---------- Launcher visuals (minimal, clean) ----------
BG=(15,16,20); CARD_BG=(28,29,36); INK=(238,239,244); INK2=(188,190,198)

def paint_bg(surf):
    surf.fill(BG)
    w,h = surf.get_size()
    band = pygame.Surface((w, int(h*0.45)), pygame.SRCALPHA)
    rrect(band, band.get_rect(), (255,255,255,12), 0)
    try: surf.blit(band, (0, int(h*0.06)), special_flags=pygame.BLEND_RGBA_SUB)
    except: surf.blit(band, (0, int(h*0.06)))

def draw_side_card(surf, entry, rect, fade):
    rrect(surf, rect, CARD_BG, 20)
    inner = rect.inflate(-14,-14)
    blit_rounded_image(surf, entry.cover, inner, 16)
    dim = pygame.Surface(inner.size, pygame.SRCALPHA)
    dim.fill((0,0,0,int(200*(1-fade))))
    surf.blit(dim, inner.topleft)
    pygame.draw.rect(surf, (*entry.accent,50), rect, 2)

def draw_focus_card_base(surf, entry, rect):
    rrect(surf, rect, CARD_BG, 20)
    pad=16
    img_rect = pygame.Rect(rect.x+pad, rect.y+pad, rect.w-2*pad, int(rect.h*0.68))
    footer   = pygame.Rect(rect.x+pad, img_rect.bottom+8, rect.w-2*pad, rect.bottom-(img_rect.bottom+8)-pad)
    blit_rounded_image(surf, entry.cover, img_rect, 14)
    rrect(surf, footer, (22,23,28), 12)
    pygame.draw.rect(surf, (*entry.accent,80), rect, 2)
    return footer

# ---------- Main ----------
def run():
    W,H = 720,600
    screen = pygame.display.set_mode((W,H))
    pygame.display.set_caption("Arcade Launcher")
    clock = pygame.time.Clock()

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "games")
    games = discover_games(root); n=len(games)
    inp = JoyInput(joy_index=0, deadzone=0.35)

    idx=0; scroll=float(idx); t=0.0

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()

        inp.update()

        if n:
            if inp.pressed(Action.RIGHT): idx=(idx+1)%n
            if inp.pressed(Action.LEFT):  idx=(idx-1)%n

        dt = clock.tick(60)/1000.0
        scroll += (idx - scroll) * min(1.0, dt*10.0)

        paint_bg(screen)

        if n:
            hero_w=int(min(W*0.50,760)); hero_h=int(hero_w*0.60)
            center=pygame.Rect(0,0,hero_w,hero_h); center.center=(W//2,int(H*0.56))
            spacing=int(hero_w*0.72)
            items=[]
            for i in range(n):
                delta=((i - scroll + n/2) % n) - n/2
                if abs(delta)>3: continue
                scale=0.62+0.38*max(0.0,1.0-abs(delta)*0.55)
                rect=center.move(int(delta*spacing), int(abs(delta)*hero_h*0.10))
                rect=pygame.Rect(rect.x,rect.y,int(center.w*scale),int(center.h*scale))
                items.append((i,delta,scale,rect))
            for i,delta,scale,rect in sorted(items,key=lambda x:x[2]):
                if i==idx: continue
                draw_side_card(screen,games[i],rect,0.85 if abs(delta)<0.5 else 0.65)
            focus_footer=None; focus_entry=None; focus_scale=None
            for i,delta,scale,rect in items:
                if i==idx:
                    focus_footer=draw_focus_card_base(screen,games[i],rect); focus_entry=games[i]; focus_scale=scale; break

        title = F(66).render("ARCADE", True, INK); screen.blit(title,(48,40))
        sub = F(22).render("D-pad/Stick: browse  •  A: play  •  B/Start: back", True, INK2); screen.blit(sub,(48,40+title.get_height()+6))

        if n and focus_entry:
            t1=F(int(38*focus_scale)).render(focus_entry.title, True, INK); screen.blit(t1,(focus_footer.x+14, focus_footer.y+10))
            if focus_entry.subtitle:
                t2=F(int(22*focus_scale)).render(focus_entry.subtitle, True, INK2); screen.blit(t2,(focus_footer.x+14, focus_footer.bottom-28))
            pulse=0.5*(1+math.sin(t*2.2))
            pill_w=min(focus_footer.w-20, int(360*focus_scale)); pill_h=int(40*focus_scale)
            pill=pygame.Rect(0,0,pill_w,pill_h); pill.center=(focus_footer.centerx, focus_footer.bottom+int(24*focus_scale))
            rrect(screen, pill, (*focus_entry.accent, int(190+40*pulse)), 999)
            txt=F(int(24*focus_scale)).render("Press A to Play", True, (255,255,255))
            screen.blit(txt, txt.get_rect(center=pill.center))

        if n and inp.pressed(Action.LAUNCH):
            chosen = games[idx]
            print(f"[LAUNCHER] Launching {chosen.slug}")
            pygame.display.quit()
            try: subprocess.call([sys.executable, os.path.join(chosen.path, "main.py")])
            except Exception as e: print("[LAUNCHER] Game error:", e)
            pygame.display.init(); screen = pygame.display.set_mode((W,H)); clock = pygame.time.Clock()
            games = discover_games(root); n=len(games); idx=min(idx,n-1) if n else 0; scroll=float(idx)
            inp = JoyInput(joy_index=0, deadzone=0.35)

        if inp.pressed(Action.BACK):
            print("[LAUNCHER] Back/Exit pressed"); pygame.quit(); sys.exit()

        pygame.display.flip(); t += dt

if __name__=="__main__":
    run()
