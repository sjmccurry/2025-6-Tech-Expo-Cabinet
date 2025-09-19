import pygame, sys, os, math, random
pygame.init()

W, H = 960, 540
TILE = 48
FPS = 60

WHITE=(245,245,250); GRAY=(180,184,194); DARK=(18,19,23); GROUND=(36,37,46)
ACCENT=(230,70,80); GOLD=(245,200,80); SPIKE=(220,60,60); GREEN=(70,200,120)

screen = pygame.display.set_mode((W,H))
pygame.display.set_caption("Red Runner")
clock = pygame.time.Clock()

def F(sz): return pygame.font.Font(None, sz)

def rrect(surf, rect, color, radius=0, width=0):
    try:
        pygame.draw.rect(surf, color, rect, width, border_radius=radius)
    except TypeError:
        pygame.draw.rect(surf, color, rect, width)

LEVEL = [
"................................................................................",
"................................................................................",
".................................................c............E.................",
".................................................XXX............................",
"...................c............................................c...............",
"..............XXX..XXX..............c...............E...........XXX.............",
"@..................................XXXXX...........................c............",
"XXXX.................====....................................XXXXXXX............",
"....XX....c..............................................c...........c..........",
"......XX..............................................XXXXXXX...................",
".........XX..............!.......................c......................G.......",
"............XX.....^^^^^XXXXXX..............XXXXXXX.............^^^^^XXXXXX.....",
"...............XX....................c..........................................",
"..................XX................XXXXXXX.....................................",
".....................XX........................................................",
"........................XXXXXXXXXXXX.............................||||...........",
".................................................................||||...........",
"..................c....................c.........................||||...........",
"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
]

SOLID = {"X"}; COIN = {"c"}; SPIKES = {"^"}; SPAWN = {"@"}; CHECK = {"!"}; GOAL = {"G"}; PLAT_H = {"="}; PLAT_V = {"|"}

# -------- Joystick-only input --------
class Input:
    def __init__(self, joy_index=0, deadzone=0.35):
        self.deadzone=deadzone
        pygame.joystick.init()
        self.joy=None
        if pygame.joystick.get_count()>joy_index:
            self.joy=pygame.joystick.Joystick(joy_index); self.joy.init()
            print(f"[GAME] Using joystick: {self.joy.get_name()} | axes:{self.joy.get_numaxes()} buttons:{self.joy.get_numbuttons()} hats:{self.joy.get_numhats()}")
        else:
            print("[GAME] No joystick detected.")
        self.prev_btn={}; self.prev_hat=(0,0); self.prev_ax0=0.0
        self.left_d=False; self.right_d=False; self.jump_d=False; self.back_d=False
        self.prev_left=False; self.prev_right=False; self.prev_jump=False; self.prev_back=False

    def _btn(self,i): return self.joy and self.joy.get_numbuttons()>i and self.joy.get_button(i)

    def update(self):
        if not self.joy:
            self.left_d=self.right_d=self.jump_d=self.back_d=False
            return
        nb=self.joy.get_numbuttons()
        for b in range(nb):
            v=bool(self.joy.get_button(b)); pv=self.prev_btn.get(b,False)
            if v!=pv: print(f"[GAME] BUTTON {b} {'DOWN' if v else 'UP'}")
            self.prev_btn[b]=v
        hat=(0,0)
        if self.joy.get_numhats()>0: hat=self.joy.get_hat(0)
        if hat!=self.prev_hat: print(f"[GAME] HAT0 -> {hat}")
        self.prev_hat=hat
        ax0=self.joy.get_axis(0) if self.joy.get_numaxes()>0 else 0.0
        if abs(ax0-self.prev_ax0)>=0.1 or ax0 in (-1.0,0.0,1.0): print(f"[GAME] AXIS0 {ax0:+.2f}")
        self.prev_ax0=ax0

        x=hat[0]
        if x==0:
            if ax0<-self.deadzone: x=-1
            elif ax0> self.deadzone: x=+1

        self.left_d  = (x<0)
        self.right_d = (x>0)
        self.jump_d  = bool(self._btn(0))         # A button
        self.back_d  = bool(self._btn(1) or self._btn(7))  # B or Start

    def left(self):  return self.left_d
    def right(self): return self.right_d

    def jump_pressed(self):
        now=self.jump_d; was=self.prev_jump; self.prev_jump=now
        if now and not was: print("[GAME] ACTION JUMP PRESSED")
        return now and not was

    def jump_released(self):
        now=self.jump_d; was=self.prev_jump
        rel = (not now) and was
        if rel: print("[GAME] ACTION JUMP RELEASED")
        return rel

    def back_pressed(self):
        now=self.back_d; was=self.prev_back; self.prev_back=now
        if now and not was: print("[GAME] ACTION BACK PRESSED")
        return now and not was

# -------- Camera/Entities/World --------
class Camera:
    def __init__(self): self.x=self.y=0.0; self.shake_t=0.0; self.shake_mag=0.0
    def update(self,target_rect, level_w, level_h):
        tx=target_rect.centerx - W/2; ty=target_rect.centery - H*0.55
        tx=max(0,min(tx, level_w - W)); ty=max(0,min(ty, level_h - H))
        self.x += (tx - self.x)*0.12; self.y += (ty - self.y)*0.12
        if self.shake_t>0: self.shake_t-=1/FPS
    def add_shake(self,mag,dur=0.25): self.shake_mag=max(self.shake_mag,mag); self.shake_t=max(self.shake_t,dur)
    def apply(self,rect):
        ox=oy=0
        if self.shake_t>0:
            m=self.shake_mag*(self.shake_t)
            ox=random.uniform(-m,m); oy=random.uniform(-m,m)
        return rect.move(int(-self.x+ox), int(-self.y+oy))

class Particle:
    def __init__(self,pos,vel,life,color,rad):
        self.x,self.y=pos; self.vx,self.vy=vel; self.life=life; self.t=0; self.color=color; self.rad=rad
    def update(self,dt):
        self.t+=dt; self.x+=self.vx*dt; self.y+=self.vy*dt; self.vy+=500*dt
        return self.t<self.life
    def draw(self,s,camera):
        a=max(0,1-self.t/self.life); col=(self.color[0],self.color[1],self.color[2],int(255*a))
        surf=pygame.Surface((self.rad*2,self.rad*2),pygame.SRCALPHA)
        pygame.draw.circle(surf,col,(self.rad,self.rad),self.rad)
        r=surf.get_rect(center=(int(self.x-camera.x),int(self.y-camera.y))); s.blit(surf,r.topleft)

class Platform:
    def __init__(self,x,y,w,h,dx,dy,dist,speed):
        self.base=pygame.Vector2(x,y); self.rect=pygame.Rect(x,y,w,h)
        self.dir=pygame.Vector2(dx,dy); self.dist=dist; self.speed=speed; self.t=0.0; self.prev=self.rect.copy()
    def update(self,dt):
        self.prev=self.rect.copy(); self.t += dt*self.speed
        p = (math.sin(self.t)+1)/2; off = self.dir*self.dist*(p*2-1)
        self.rect.topleft = (int(self.base.x+off.x), int(self.base.y+off.y))
    @property
    def delta(self): return pygame.Vector2(self.rect.x-self.prev.x, self.rect.y-self.prev.y)
    def draw(self,s,camera):
        rr=camera.apply(self.rect); rrect(s,(90,90,110),rr); pygame.draw.rect(s,(140,140,170),rr,2)

class Enemy:
    def __init__(self,x,y):
        self.rect=pygame.Rect(x,y,TILE-8,TILE-8); self.vx=120; self.dir=1
    def update(self,dt,solids):
        self.rect.x += int(self.vx*self.dir*dt)
        if collide_solid(self.rect, solids): self.dir*=-1; self.rect.x += int(self.vx*self.dir*dt)
    def draw(self,s,camera):
        rr=camera.apply(self.rect); rrect(s,rr,(200,80,120),8); pygame.draw.rect(s,(255,160,200),rr,2)

class Player:
    def __init__(self,x,y):
        self.rect=pygame.Rect(x,y,32,42); self.vx=self.vy=0.0; self.on_ground=False
        self.coyote=0.0; self.jump_buffer=0.0; self.facing=1; self.coins=0
        self.checkpoint=pygame.Vector2(x,y)
    def touch(self,rects): return any(self.rect.colliderect(r) for r in rects)
    def update(self,dt,inp,solids,plats,coins,spikes,enemies,goal,checks,camera,particles):
        ax=0.0; speed=210; accel=1700 if self.on_ground else 1300; deccel=2000
        if inp.left(): ax -= accel; self.facing=-1
        if inp.right(): ax += accel; self.facing=1
        if ax==0:
            if self.vx>0: self.vx=max(0,self.vx-deccel*dt)
            elif self.vx<0: self.vx=min(0,self.vx+deccel*dt)
        else:
            self.vx += ax*dt; self.vx = max(-speed, min(speed, self.vx))

        if inp.jump_pressed(): self.jump_buffer=0.15
        else: self.jump_buffer=max(0.0,self.jump_buffer-dt)
        if self.on_ground: self.coyote=0.12
        else: self.coyote=max(0.0,self.coyote-dt)
        if self.jump_buffer>0 and self.coyote>0:
            self.vy=-360; self.on_ground=False; self.jump_buffer=0
            for i in range(8):
                ang=random.uniform(-0.4,0.4); sp=random.uniform(80,160)
                particles.append(Particle((self.rect.centerx,self.rect.bottom),(sp*math.cos(ang),-abs(sp*math.sin(ang))),0.4,(255,255,255),3))
        if inp.jump_released() and self.vy<-120: self.vy=-120

        self.vy += 1000*dt; self.vy = max(-1000, min(980, self.vy))
        self.move_x(self.vx*dt, solids); self.apply_platform_x(plats)
        self.move_y(self.vy*dt, solids); self.on_ground=False; self.apply_platform_y(plats)

        self.collect(coins, particles)
        if self.touch(spikes) or any(self.rect.colliderect(e.rect) for e in enemies):
            self.die(camera, particles)
        if any(self.rect.colliderect(r) for r in goal): return "win"
        for r in checks:
            if self.rect.colliderect(r): self.checkpoint.update(r.x, r.y - self.rect.h - 6)
        return None
    def move_x(self,dx,solids):
        self.rect.x += int(dx); hit = collide_solid(self.rect, solids)
        if hit:
            if dx>0: self.rect.right = hit.left
            elif dx<0: self.rect.left = hit.right
            self.vx=0
    def move_y(self,dy,solids):
        self.rect.y += int(dy); hit = collide_solid(self.rect, solids)
        if hit:
            if dy>0: self.rect.bottom = hit.top; self.vy=0; self.on_ground=True
            elif dy<0: self.rect.top = hit.bottom; self.vy=0
    def apply_platform_x(self,plats):
        for p in plats:
            if p.delta.x!=0 and self.rect.colliderect(p.rect):
                if p.delta.x>0: self.rect.right=min(self.rect.right,p.rect.left); self.vx=0
                else: self.rect.left=max(self.rect.left,p.rect.right); self.vx=0
    def apply_platform_y(self,plats):
        carried=None
        for p in plats:
            if p.delta.y!=0 and self.rect.colliderect(p.rect):
                if p.delta.y>0 and self.rect.bottom<=p.rect.top+8:
                    self.rect.bottom=p.rect.top; self.vy=0; self.on_ground=True; carried=p
                elif p.delta.y<0 and self.rect.top>=p.rect.bottom-8:
                    self.rect.top=p.rect.bottom; self.vy=0
        if carried: self.rect.x += int(carried.delta.x)
    def collect(self,coins,parts):
        i=0
        while i<len(coins):
            if self.rect.colliderect(coins[i]):
                self.coins+=1; cx,cy=coins[i].center
                for _ in range(12):
                    ang=random.uniform(0,math.tau); sp=random.uniform(90,180)
                    parts.append(Particle((cx,cy),(sp*math.cos(ang),sp*math.sin(ang)-120),0.6,GOLD,3))
                coins.pop(i)
            else: i+=1
    def die(self,camera,parts):
        camera.add_shake(8,0.2); cx,cy=self.rect.center
        for _ in range(20):
            ang=random.uniform(0,math.tau); sp=random.uniform(120,240)
            parts.append(Particle((cx,cy),(sp*math.cos(ang),sp*math.sin(ang)-120),0.7,ACCENT,3))
        self.vx=self.vy=0; self.rect.topleft=(int(self.checkpoint.x), int(self.checkpoint.y))

def collide_solid(rect, solids):
    for r in solids:
        if rect.colliderect(r): return r
    return None

def parse_level(rows):
    solids=[]; coins=[]; spikes=[]; enemies=[]; plats=[]; goal=[]; checks=[]; spawn=(64,64)
    H=len(rows); Wd=max((len(r) for r in rows), default=0)
    for y in range(H):
        line=rows[y].ljust(Wd,".")
        for x,c in enumerate(line):
            rx,ry=x*TILE, y*TILE
            if c in SOLID: solids.append(pygame.Rect(rx,ry,TILE,TILE))
            elif c in COIN: coins.append(pygame.Rect(rx+TILE//3, ry+TILE//3, TILE//3, TILE//3))
            elif c in SPIKES: spikes.append(pygame.Rect(rx,ry+TILE//2,TILE,TILE//2))
            elif c in PLAT_H: plats.append(Platform(rx,ry,TILE,TILE//3,1,0,80,1.2))
            elif c in PLAT_V: plats.append(Platform(rx+6,ry,TILE-12,TILE//3,0,1,90,1.0))
            elif c in SPAWN: spawn=(rx, ry-12)
            elif c in GOAL: goal.append(pygame.Rect(rx,ry,TILE,TILE))
            elif c in CHECK: checks.append(pygame.Rect(rx,ry,TILE,TILE))
            elif c=="E": enemies.append(Enemy(rx+6, ry+8))
    return solids, coins, spikes, enemies, plats, goal, checks, (Wd*TILE, H*TILE), spawn

def draw_world(s, camera, solids, coins, spikes, enemies, plats, goal, checks):
    for r in solids: pygame.draw.rect(s,GROUND, camera.apply(r))
    for p in plats: p.draw(s,camera)
    for r in spikes:
        rr=camera.apply(r); pygame.draw.polygon(s,SPIKE,[(rr.left,rr.bottom),(rr.centerx,rr.top),(rr.right,rr.bottom)])
        pygame.draw.polygon(s,(255,200,200),[(rr.left,rr.bottom),(rr.centerx,rr.top),(rr.right,rr.bottom)],2)
    for r in coins: rr=camera.apply(r); pygame.draw.circle(s,GOLD,rr.center, rr.w//2); pygame.draw.circle(s,WHITE,rr.center, rr.w//2,2)
    for e in enemies: e.draw(s,camera)
    for r in goal: rr=camera.apply(r); pygame.draw.rect(s,GREEN,rr); pygame.draw.rect(s,WHITE,rr,2)
    for r in checks: rr=camera.apply(r); pygame.draw.rect(s,(100,180,255),rr); pygame.draw.rect(s,WHITE,rr,2)

def hud(s, player):
    t=F(28).render(f"Coins: {player.coins}", True, WHITE); s.blit(t,(16,12))

def run():
    solids, coins, spikes, enemies, plats, goal, checks, size, spawn = parse_level(LEVEL)
    ply = Player(spawn[0], spawn[1]); cam = Camera(); parts=[]
    inp = Input(joy_index=0, deadzone=0.35)
    paused=False
    while True:
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
        inp.update()
        if inp.back_pressed(): pygame.quit(); sys.exit()
        if paused:
            screen.fill(DARK); t=F(48).render("Paused", True, WHITE); screen.blit(t,(W//2-t.get_width()//2,H//2-t.get_height()//2)); pygame.display.flip(); clock.tick(FPS); continue
        dt = clock.tick(FPS)/1000.0
        for p in plats: p.update(dt)
        for en in enemies: en.update(dt, solids+[p.rect for p in plats])
        state = ply.update(dt, inp, solids+[p.rect for p in plats], plats, coins, spikes, enemies, goal, checks, cam, parts)
        cam.update(ply.rect, size[0], size[1])
        screen.fill(DARK); draw_world(screen, cam, solids, coins, spikes, enemies, plats, goal, checks)
        pr = cam.apply(ply.rect); rrect(screen, pr, ACCENT, 8); pygame.draw.rect(screen, WHITE, pr, 2)
        i=0
        while i<len(parts):
            if parts[i].update(dt): parts[i].draw(screen,cam); i+=1
            else: parts.pop(i)
        hud(screen, ply)
        if state=="win":
            overlay=pygame.Surface((W,H),pygame.SRCALPHA); overlay.fill((0,0,0,160)); screen.blit(overlay,(0,0))
            t1=F(64).render("You Win!", True, WHITE); t2=F(24).render("Press B/Start to exit", True, GRAY)
            screen.blit(t1,(W//2-t1.get_width()//2,H//2-60)); screen.blit(t2,(W//2-t2.get_width()//2,H//2+10))
        pygame.display.flip()

if __name__=="__main__":
    run()
