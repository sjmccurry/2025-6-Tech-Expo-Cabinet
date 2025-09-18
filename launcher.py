import os, sys, json, math, time, subprocess, pygame
from dataclasses import dataclass, field
from enum import Enum, auto

pygame.init()

class Action(Enum):
    LEFT=auto(); RIGHT=auto(); LAUNCH=auto(); BACK=auto()

@dataclass
class InputState: down: bool=False; pressed: bool=False
@dataclass
class Bindings: keys: dict = field(default_factory=dict)

class Input:
    def __init__(self, b:Bindings):
        self.b=b; self.s={a:InputState() for a in Action}; self.prev={a:False for a in Action}
        pygame.key.set_repeat(0,0)
    def _set(self,a,v):
        st=self.s[a]; was=self.prev[a]; st.down=v; st.pressed=(not was) and v; self.prev[a]=v
    def update(self):
        k=pygame.key.get_pressed(); held={a:False for a in Action}
        for a,ks in self.b.keys.items(): held[a]|=any(k[x] for x in (ks if isinstance(ks,(list,tuple,set)) else [ks]))
        for a in Action: self._set(a,held[a])
    def pressed(self,a): return self.s[a].pressed

def bindings():
    return Bindings(keys={
        Action.LEFT:[pygame.K_LEFT,pygame.K_a],
        Action.RIGHT:[pygame.K_RIGHT,pygame.K_d],
        Action.LAUNCH:[pygame.K_RETURN,pygame.K_SPACE],
        Action.BACK:[pygame.K_ESCAPE]
    })

@dataclass
class GameEntry:
    slug:str; title:str; subtitle:str; path:str
    cover:pygame.Surface|None; accent:tuple[int,int,int]

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

BG=(15,16,20)
CARD_BG=(28,29,36)
INK=(238,239,244)
INK_2=(188,190,198)

def F(sz): return pygame.font.Font(None, sz)

def draw_text(surf, s, size, color, pos, align="topleft"):
    r=F(size).render(s, True, color); rect=r.get_rect(); setattr(rect, align, pos); surf.blit(r, rect); return rect

def rrect(surf, rect, color, radius=18, width=0):
    pygame.draw.rect(surf, color, rect, width=width, border_radius=radius)

def shadow(surf, rect, alpha=90, spread=28):
    sh=pygame.Surface((rect.w+spread, rect.h+spread), pygame.SRCALPHA)
    pygame.draw.rect(sh,(0,0,0,alpha),sh.get_rect(),border_radius=22)
    sh=pygame.transform.smoothscale(sh,(rect.w+spread, rect.h+spread))
    surf.blit(sh,(rect.x-spread//2, rect.y-spread//2))

def scale_to_cover(surface, size):
    iw,ih=surface.get_size(); rw,rh=size
    sc=max(rw/iw, rh/ih)
    return pygame.transform.smoothscale(surface,(int(iw*sc),int(ih*sc)))

def blit_rounded_image(dst, img, rect, radius):
    if not img:
        rrect(dst, rect, (40,42,50), radius)
        return
    scaled=scale_to_cover(img,(rect.w,rect.h))
    layer=pygame.Surface((rect.w,rect.h),pygame.SRCALPHA)
    x=(rect.w - scaled.get_width())//2
    y=(rect.h - scaled.get_height())//2
    layer.blit(scaled,(x,y))
    mask=pygame.Surface((rect.w,rect.h),pygame.SRCALPHA)
    rrect(mask, mask.get_rect(), (255,255,255,255), radius)
    layer.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
    dst.blit(layer, rect.topleft)

def paint_bg(surf):
    surf.fill(BG)
    w,h=surf.get_size()
    band=pygame.Surface((w,int(h*0.5)), pygame.SRCALPHA)
    rrect(band, band.get_rect(), (255,255,255,12), radius=0)
    surf.blit(band, (0,int(h*0.06)), special_flags=pygame.BLEND_RGBA_SUB)

def draw_side_card(surf, entry, rect, alpha_mul):
    shadow(surf, rect, alpha=70)
    rrect(surf, rect, CARD_BG, radius=22)
    inner=rect.inflate(-14,-14)
    if entry.cover:
        temp=entry.cover.copy()
        blit_rounded_image(surf, temp, inner, 18)
        if alpha_mul<1.0:
            dim=pygame.Surface(inner.size,pygame.SRCALPHA)
            dim.fill((0,0,0,int(255*(1-alpha_mul))))
            surf.blit(dim, inner.topleft)
    else:
        rrect(surf, inner, (40,42,50), radius=18)
    pygame.draw.rect(surf, (*entry.accent,50), rect, 2, border_radius=22)

def draw_focus_card_base(surf, entry, rect):
    shadow(surf, rect, alpha=110)
    rrect(surf, rect, CARD_BG, radius=22)
    pad=16
    img_rect=pygame.Rect(rect.x+pad, rect.y+pad, rect.w-2*pad, int(rect.h*0.68))
    footer=pygame.Rect(rect.x+pad, img_rect.bottom+8, rect.w-2*pad, rect.bottom-(img_rect.bottom+8)-pad)
    blit_rounded_image(surf, entry.cover, img_rect, 16)
    rrect(surf, footer, (22,23,28), radius=14)
    pygame.draw.rect(surf, (*entry.accent,80), rect, 2, border_radius=22)
    return footer

def run():
    ww,hh=1280,720
    screen=pygame.display.set_mode((ww,hh))
    pygame.display.set_caption("Arcade Launcher")
    clock=pygame.time.Clock()
    inp=Input(bindings())
    root=os.path.join(os.path.dirname(os.path.abspath(__file__)),"games")
    games=discover_games(root); n=len(games)
    idx=0; scroll=float(idx); t=0.0
    while True:
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
        inp.update()
        if inp.pressed(Action.BACK): pygame.quit(); sys.exit()
        if n:
            if inp.pressed(Action.RIGHT): idx=(idx+1)%n
            if inp.pressed(Action.LEFT): idx=(idx-1)%n
        dt=clock.tick(60)/1000.0
        scroll += (idx - scroll) * min(1.0, dt*10.0)
        paint_bg(screen)
        if n:
            hero_w=int(min(ww*0.50,760))
            hero_h=int(hero_w*0.60)
            center=pygame.Rect(0,0,hero_w,hero_h)
            center.center=(ww//2,int(hh*0.56))
            spacing=int(hero_w*0.72)
            visible_span=6
            item_data=[]
            for i in range(n):
                delta=((i - scroll + n/2) % n) - n/2
                if abs(delta)>visible_span/2: continue
                scale=0.62 + 0.38*max(0.0,1.0-abs(delta)*0.55)
                rect=center.move(int(delta*spacing), int(abs(delta)*hero_h*0.10))
                rect=pygame.Rect(rect.x,rect.y,int(center.w*scale),int(center.h*scale))
                item_data.append((i,delta,scale,rect))
            for i,delta,scale,rect in sorted(item_data,key=lambda x:x[2]):
                if i==idx: continue
                draw_side_card(screen,games[i],rect,0.85 if abs(delta)<0.5 else 0.65)
            focus_footer=None; focus_entry=None; focus_scale=None
            for i,delta,scale,rect in item_data:
                if i==idx:
                    focus_footer=draw_focus_card_base(screen,games[i],rect)
                    focus_entry=games[i]; focus_scale=scale
                    break
        title=draw_text(screen,"ARCADE",66,INK,(48,40),"topleft")
        draw_text(screen,"Use ←/→ to browse, Enter to play",22,INK_2,(title.left,title.bottom+6),"topleft")
        if n and focus_entry:
            draw_text(screen,focus_entry.title,int(38*focus_scale),INK,(focus_footer.x+14,focus_footer.y+10),"topleft")
            if focus_entry.subtitle:
                draw_text(screen,focus_entry.subtitle,int(22*focus_scale),INK_2,(focus_footer.x+14,focus_footer.bottom-28),"topleft")
            pulse=0.5*(1+math.sin(t*2.2))
            pill_w=min(focus_footer.w-20,int(360*focus_scale)); pill_h=int(40*focus_scale)
            pill=pygame.Rect(0,0,pill_w,pill_h); pill.center=(focus_footer.centerx,focus_footer.bottom+int(24*focus_scale))
            shadow(screen,pill.inflate(12,12),alpha=70)
            rrect(screen,pill,(*focus_entry.accent,int(190+40*pulse)),radius=999)
            draw_text(screen,"Press Enter to Play",int(24*focus_scale),(255,255,255),pill.center,"center")
        if n and inp.pressed(Action.LAUNCH):
            chosen=games[idx]
            pygame.display.quit()
            try: subprocess.call([sys.executable, os.path.join(chosen.path,"main.py")])
            except Exception: pass
            pygame.display.init(); screen=pygame.display.set_mode((ww,hh))
            inp=Input(bindings())
            games=discover_games(root); n=len(games); idx=min(idx,n-1) if n else 0; scroll=float(idx)
        pygame.display.flip(); t+=dt

if __name__=="__main__":
    run()
