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

def default_bindings():
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
        title=slug.replace("_"," ").title(); subtitle=""; accent=(140,120,255)
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

def F(sz): return pygame.font.Font(None, sz)
def draw_text(surf,s,size,color,pos,align="topleft"):
    r=F(size).render(s,True,color); rect=r.get_rect(); setattr(rect,align,pos); surf.blit(r,rect); return rect
def rrect(surf,rect,color,r=24,w=0): pygame.draw.rect(surf,color,rect,w,border_radius=r)

def fit_image(surface, rect):
    if not surface: return None,None
    iw,ih=surface.get_size(); rw,rh=rect.w,rect.h
    sc=max(rw/iw, rh/ih); nw,nh=int(iw*sc),int(ih*sc)
    im=pygame.transform.smoothscale(surface,(nw,nh))
    return im,(rect.x+(rw-nw)//2, rect.y+(rh-nh)//2)

def make_bg(w,h):
    bg=pygame.Surface((w,h)); bg.fill((14,14,18))
    g=pygame.Surface((w,h),pygame.SRCALPHA)
    pygame.draw.circle(g,(150,120,255,36),(int(w*0.2),int(h*0.25)),int(min(w,h)*0.45))
    pygame.draw.circle(g,(255,110,120,28),(int(w*0.8),int(h*0.2)),int(min(w,h)*0.5))
    pygame.draw.circle(g,(70,200,170,26),(int(w*0.55),int(h*0.85)),int(min(w,h)*0.55))
    bg.blit(g,(0,0)); return bg

def glass(s, rect, a=80, border=(255,255,255,30)):
    pane=pygame.Surface((rect.w,rect.h),pygame.SRCALPHA)
    rrect(pane,pane.get_rect(),(255,255,255,a),24)
    pygame.draw.rect(pane,border,pane.get_rect(),1,border_radius=24)
    s.blit(pane,rect)

def glow(s, rect, color, alpha=85):
    g=pygame.Surface((int(rect.w*1.6),int(rect.h*1.2)),pygame.SRCALPHA)
    pygame.draw.ellipse(g,(*color,alpha),g.get_rect())
    s.blit(g,(rect.centerx-g.get_width()//2, rect.bottom-g.get_height()//2))

def draw_card_base(surface, entry, rect, scale, dim_alpha):
    body=rect.inflate(-18,-18)
    footer_h=max(68,int(72*scale))
    img_rect=pygame.Rect(body.x,body.y,body.w,body.h-footer_h-8)
    footer=pygame.Rect(body.x,img_rect.bottom+8,body.w,footer_h)
    glass(surface,rect,a=60+int(10*scale))
    if entry.cover:
        im,pos=fit_image(entry.cover,img_rect)
        if im:
            if dim_alpha>0:
                temp=im.copy(); temp.fill((255,255,255,dim_alpha),special_flags=pygame.BLEND_RGBA_MULT); surface.blit(temp,pos)
            else:
                surface.blit(im,pos)
    else:
        rrect(surface,img_rect,(34,34,40),18)
    footer_shade=pygame.Surface(footer.size,pygame.SRCALPHA)
    rrect(footer_shade,footer_shade.get_rect(),(14,14,18,175),18); surface.blit(footer_shade,footer)
    pygame.draw.rect(surface,(*entry.accent,40),rect,1,border_radius=24)
    return footer

def draw_focus_overlay(surface, entry, footer, scale, t):
    draw_text(surface,entry.title,int(40*scale),(242,242,248),(footer.x+16,footer.y+12),"topleft")
    if entry.subtitle:
        draw_text(surface,entry.subtitle,int(22*scale),(200,200,208),(footer.x+16,footer.bottom-28),"topleft")
    pulse=(math.sin(t*2.2)+1)*0.5
    pill_w=min(footer.w-32,int(380*scale)); pill_h=int(44*scale)
    pill=pygame.Rect(0,0,pill_w,pill_h); pill.center=(footer.centerx,footer.bottom+int(26*scale))
    glass(surface,pill,a=130,border=(*entry.accent,130))
    draw_text(surface,"Press Enter to Play",int(26*scale),(255,255,255,200+int(55*pulse)),pill.center,"center")
    return pill.bottom

def run():
    ww,hh=1280,720
    screen=pygame.display.set_mode((ww,hh))
    pygame.display.set_caption("Arcade Launcher")
    clock=pygame.time.Clock()
    bg=make_bg(ww,hh)
    inp=Input(default_bindings())
    root=os.path.join(os.path.dirname(os.path.abspath(__file__)),"games")
    games=discover_games(root)
    n=len(games)
    idx=0
    scroll=float(idx)
    t=0.0

    while True:
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()

        inp.update()
        if inp.pressed(Action.BACK): pygame.quit(); sys.exit()
        if n:
            if inp.pressed(Action.RIGHT): idx=(idx+1)%n
            if inp.pressed(Action.LEFT): idx=(idx-1)%n
        dt=clock.tick(60)/1000.0
        k=min(1.0, dt*10.0); scroll+= (idx - scroll) * k

        screen.blit(bg,(0,0))
        title=draw_text(screen,"ARCADE",72,(245,245,250),(48,36),"topleft")
        draw_text(screen,"Select a game",24,(185,185,195),(title.left,title.bottom+6),"topleft")

        if n:
            center=pygame.Rect(0,0,int(min(ww*0.46,720)),int(min(ww*0.46,720)*0.62))
            center.center=(ww//2,int(hh*0.55))
            spacing=center.w*0.72
            visible=6
            items=[]
            for i in range(n):
                delta=((i - scroll + n/2) % n) - n/2
                if abs(delta) > visible/2: continue
                scale=0.62 + 0.38*max(0.0, 1.0 - abs(delta)*0.55)
                x_off=int(delta*spacing); y_off=int(abs(delta)*center.h*0.10)
                rect=center.move(x_off,y_off)
                items.append((scale, abs(delta), i, rect, delta))
            items.sort(key=lambda it: it[0])  # small to large

            focus_footer=None; focus_entry=None; focus_rect=None; focus_scale=None
            for scale,dist,i,rect,delta in items:
                dim=int(140*min(1.0, dist))  # side cards dimmed
                if i==idx:
                    glow(screen,rect,games[i].accent,alpha=95)
                glass_rect=rect
                footer=draw_card_base(screen,games[i],glass_rect,scale,dim)
                if i==idx:
                    focus_footer=footer; focus_entry=games[i]; focus_rect=rect; focus_scale=scale

            bottom_ui_y=hh-20
            if focus_entry:
                last_y = draw_focus_overlay(screen, focus_entry, focus_footer, focus_scale, t)
                bottom_ui_y = max(bottom_ui_y, last_y+12)

            help_line="Enter: Play   Esc: Quit   ←/→: Navigate"
            draw_text(screen,help_line,22,(170,170,178),(ww-24,bottom_ui_y),"bottomright")

            if inp.pressed(Action.LAUNCH):
                chosen=games[idx]
                pygame.display.quit()
                try: subprocess.call([sys.executable, os.path.join(chosen.path,"main.py")])
                except Exception: pass
                pygame.display.init(); screen=pygame.display.set_mode((ww,hh))
                bg=make_bg(ww,hh)
                inp=Input(default_bindings())
                games=discover_games(root); n=len(games); idx=min(idx,n-1) if n else 0
                scroll=float(idx)

        pygame.display.flip()
        t+=dt

if __name__=="__main__":
    run()
