import pygame, sys, os, math, random
pygame.init()

W, H = 960, 540
TILE = 48
FPS = 60

WHITE=(245,245,250); GRAY=(180,184,194); DARK=(18,19,23); GROUND=(36,37,46)
ACCENT=(230,70,80); GOLD=(245,200,80); SPIKE=(220,60,60); GREEN=(70,200,120)
def F(size: int):
    return pygame.font.Font(None, size)


screen = pygame.display.set_mode((W,H))
pygame.display.set_caption("Red Runner")
clock = pygame.time.Clock()

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

SOLID = {"X"}
COIN = {"c"}
SPIKES = {"^"}
SPAWN = {"@"}
CHECK = {"!"}
GOAL = {"G"}
PLAT_H = {"="}
PLAT_V = {"|"}

class Input:
    def __init__(self):
        self.prev = pygame.key.get_pressed()
        self.cur = self.prev
    def update(self):
        self.prev = self.cur
        self.cur = pygame.key.get_pressed()
    def down(self,k): return self.cur[k]
    def pressed(self,k): return self.cur[k] and not self.prev[k]
    def released(self,k): return self.prev[k] and not self.cur[k]

class Camera:
    def __init__(self):
        self.x=self.y=0.0
        self.shake_t=0.0; self.shake_mag=0.0
    def update(self,target_rect, level_w, level_h):
        tx = target_rect.centerx - W/2
        ty = target_rect.centery - H*0.55
        tx = max(0,min(tx, level_w - W))
        ty = max(0,min(ty, level_h - H))
        self.x += (tx - self.x)*0.12
        self.y += (ty - self.y)*0.12
        if self.shake_t>0:
            self.shake_t-=1/FPS
    def add_shake(self,mag, dur=0.25):
        self.shake_mag=max(self.shake_mag,mag); self.shake_t=max(self.shake_t,dur)
    def apply(self,rect):
        ox=oy=0
        if self.shake_t>0:
            m=self.shake_mag*(self.shake_t)
            ox=random.uniform(-m,m); oy=random.uniform(-m,m)
        return rect.move(int(-self.x+ox), int(-self.y+oy))

class Particle:
    def __init__(self,pos,vel,life,color,rad):
        self.x,self.y=pos; self.vx,self.vy=vel
        self.life=life; self.t=0; self.color=color; self.rad=rad
    def update(self,dt):
        self.t+=dt; self.x+=self.vx*dt; self.y+=self.vy*dt; self.vy+=500*dt
        return self.t<self.life
    def draw(self,s,camera):
        a=max(0,1-self.t/self.life)
        col=(self.color[0],self.color[1],self.color[2],int(255*a))
        surf=pygame.Surface((self.rad*2,self.rad*2),pygame.SRCALPHA)
        pygame.draw.circle(surf,col,(self.rad,self.rad),self.rad)
        r=surf.get_rect(center=(int(self.x-camera.x),int(self.y-camera.y)))
        s.blit(surf,r.topleft)

class Platform:
    def __init__(self,x,y,w,h,dx,dy,dist,speed):
        self.base=pygame.Vector2(x,y); self.rect=pygame.Rect(x,y,w,h)
        self.dir=pygame.Vector2(dx,dy); self.dist=dist; self.speed=speed
        self.t=0.0; self.prev=self.rect.copy()
    def update(self,dt):
        self.prev=self.rect.copy()
        self.t += dt*self.speed
        p = (math.sin(self.t)+1)/2
        off = self.dir*self.dist*(p*2-1)
        self.rect.topleft = (int(self.base.x+off.x), int(self.base.y+off.y))
    @property
    def delta(self): return pygame.Vector2(self.rect.x-self.prev.x, self.rect.y-self.prev.y)
    def draw(self,s,camera):
        pygame.draw.rect(s,(90,90,110), camera.apply(self.rect), border_radius=6)
        pygame.draw.rect(s,(140,140,170), camera.apply(self.rect), 2, border_radius=6)

class Enemy:
    def __init__(self,x,y):
        self.rect=pygame.Rect(x,y,TILE-8,TILE-8)
        self.vx=120; self.dir=1; self.alive=True
    def update(self,dt,solids):
        self.rect.x += int(self.vx*self.dir*dt)
        if collide_solid(self.rect, solids): self.dir*=-1; self.rect.x += int(self.vx*self.dir*dt)
    def draw(self,s,camera):
        r=camera.apply(self.rect)
        pygame.draw.rect(s,(200,80,120),r,border_radius=8)
        pygame.draw.rect(s,(255,160,200),r,2,border_radius=8)

class Player:
    def __init__(self,x,y):
        self.rect=pygame.Rect(x,y,32,42)
        self.vx=self.vy=0.0
        self.on_ground=False
        self.coyote=0.0
        self.jump_buffer=0.0
        self.facing=1
        self.spawn=pygame.Vector2(x,y)
        self.coins=0
        self.alive=True
        self.checkpoint=pygame.Vector2(x,y)
    def update(self,dt,inp,solids,plats,coins,spikes,enemies,goal,checks,camera,particles):
        ax=0.0
        speed=210
        accel=1700 if self.on_ground else 1300
        deccel=2000
        if inp.down(pygame.K_LEFT) or inp.down(pygame.K_a):
            ax -= accel; self.facing=-1
        if inp.down(pygame.K_RIGHT) or inp.down(pygame.K_d):
            ax += accel; self.facing=1
        if ax==0:
            if self.vx>0: self.vx=max(0,self.vx-deccel*dt)
            elif self.vx<0: self.vx=min(0,self.vx+deccel*dt)
        else:
            self.vx += ax*dt
            self.vx = max(-speed, min(speed, self.vx))
        if inp.pressed(pygame.K_SPACE) or inp.pressed(pygame.K_RETURN):
            self.jump_buffer = 0.15
        else:
            self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.on_ground: self.coyote = 0.12
        else: self.coyote = max(0.0, self.coyote - dt)
        if self.jump_buffer>0 and self.coyote>0:
            self.vy = -360
            self.on_ground=False
            self.jump_buffer=0
            for i in range(8):
                ang=random.uniform(-0.4,0.4); sp=random.uniform(80,160)
                particles.append(Particle((self.rect.centerx,self.rect.bottom),(sp*math.cos(ang),-abs(sp*math.sin(ang))),0.4,(255,255,255),3))
        if (inp.released(pygame.K_SPACE) or inp.released(pygame.K_RETURN)) and self.vy<-120:
            self.vy = -120
        self.vy += 1000*dt
        self.vy = max(-1000, min(980, self.vy))
        self.move_x(self.vx*dt, solids)
        self.apply_platform_x(plats)
        self.move_y(self.vy*dt, solids)
        self.on_ground=False
        self.apply_platform_y(plats)
        self.collect(coins, particles)
        if self.touch(spikes) or any(self.rect.colliderect(e.rect) for e in enemies):
            self.die(camera, particles)
        if any(self.rect.colliderect(r) for r in goal):
            return "win"
        for r in checks:
            if self.rect.colliderect(r):
                self.checkpoint.update(r.x, r.y - self.rect.h - 6)
        return None
    def move_x(self,dx,solids):
        self.rect.x += int(dx)
        hit = collide_solid(self.rect, solids)
        if hit:
            if dx>0: self.rect.right = hit.left
            elif dx<0: self.rect.left = hit.right
            self.vx=0
    def move_y(self,dy,solids):
        self.rect.y += int(dy)
        hit = collide_solid(self.rect, solids)
        if hit:
            if dy>0:
                self.rect.bottom = hit.top
                self.vy=0; self.on_ground=True
            elif dy<0:
                self.rect.top = hit.bottom; self.vy=0
    def apply_platform_x(self,plats):
        for p in plats:
            if p.delta.x!=0 and self.rect.colliderect(p.rect):
                if p.delta.x>0: self.rect.right=min(self.rect.right, p.rect.left); self.vx=0
                else: self.rect.left=max(self.rect.left, p.rect.right); self.vx=0
    def apply_platform_y(self, plats):
        carried=None
        for p in plats:
            if p.delta.y!=0 and self.rect.colliderect(p.rect):
                if p.delta.y>0 and self.rect.bottom<=p.rect.top+8:
                    self.rect.bottom=p.rect.top; self.vy=0; self.on_ground=True; carried=p
                elif p.delta.y<0 and self.rect.top>=p.rect.bottom-8:
                    self.rect.top=p.rect.bottom; self.vy=0
        if carried:
            self.rect.x += int(carried.delta.x)

    def collect(self,coins,parts):
        i=0
        while i<len(coins):
            if self.rect.colliderect(coins[i]):
                self.coins+=1
                cx,cy=coins[i].center
                for _ in range(12):
                    ang=random.uniform(0,math.tau); sp=random.uniform(90,180)
                    parts.append(Particle((cx,cy),(sp*math.cos(ang),sp*math.sin(ang)-120),0.6,GOLD,3))
                coins.pop(i)
            else: i+=1
    def die(self,camera,parts):
        camera.add_shake(8,0.2)
        cx,cy=self.rect.center
        for _ in range(20):
            ang=random.uniform(0,math.tau); sp=random.uniform(120,240)
            parts.append(Particle((cx,cy),(sp*math.cos(ang),sp*math.sin(ang)-120),0.7,ACCENT,3))
        self.vx=self.vy=0

        self.rect.topleft=(int(self.checkpoint.x), int(self.checkpoint.y))

        # inside class Player:
    def touch(self, rects):
        return any(self.rect.colliderect(r) for r in rects)


def collide_solid(rect, solids):
    for r in solids:
        if rect.colliderect(r): return r
    return None



def parse_level(rows):
    solids=[]; coins=[]; spikes=[]; enemies=[]; plats=[]
    goal=[]; checks=[]; spawn=(64,64)

    H = len(rows)
    Wd = max((len(r) for r in rows), default=0)

    for y in range(H):
        line = rows[y].ljust(Wd, ".")
        for x, c in enumerate(line):
            rx, ry = x*TILE, y*TILE
            if c in SOLID:
                solids.append(pygame.Rect(rx, ry, TILE, TILE))
            elif c in COIN:
                s = TILE//3
                coins.append(pygame.Rect(rx + (TILE - s)//2, ry + (TILE - s)//2, s, s))
            elif c in SPIKES:
                spikes.append(pygame.Rect(rx, ry + TILE//2, TILE, TILE//2))
            elif c in PLAT_H:
                plats.append(Platform(rx, ry, TILE, TILE//3, 1, 0, 80, 1.2))
            elif c in PLAT_V:
                plats.append(Platform(rx + 6, ry, TILE - 12, TILE//3, 0, 1, 90, 1.0))
            elif c in SPAWN:
                spawn = (rx, ry - 12)
            elif c in GOAL:
                goal.append(pygame.Rect(rx, ry, TILE, TILE))
            elif c in CHECK:
                checks.append(pygame.Rect(rx, ry, TILE, TILE))
            elif c == "E":
                enemies.append(Enemy(rx + 6, ry + 8))

    return solids, coins, spikes, enemies, plats, goal, checks, (Wd*TILE, H*TILE), spawn


def draw_world(s, camera, solids, coins, spikes, enemies, plats, goal, checks):
    for r in solids:
        pygame.draw.rect(s,GROUND, camera.apply(r))
    for p in plats:
        p.draw(s,camera)
    for r in spikes:
        rr=camera.apply(r); pygame.draw.polygon(s,SPIKE,[(rr.left,rr.bottom),(rr.centerx,rr.top),(rr.right,rr.bottom)])
        pygame.draw.polygon(s,(255,200,200),[(rr.left,rr.bottom),(rr.centerx,rr.top),(rr.right,rr.bottom)],2)
    for r in coins:
        rr=camera.apply(r); pygame.draw.circle(s,GOLD,rr.center, rr.w//2)
        pygame.draw.circle(s,WHITE,rr.center, rr.w//2,2)
    for e in enemies: e.draw(s,camera)
    for r in goal:
        rr=camera.apply(r); pygame.draw.rect(s,GREEN,rr); pygame.draw.rect(s,WHITE,rr,2)
    for r in checks:
        rr=camera.apply(r); pygame.draw.rect(s,(100,180,255),rr); pygame.draw.rect(s,WHITE,rr,2)

def hud(s, player):
    t=F(28).render(f"Coins: {player.coins}", True, WHITE)
    s.blit(t,(16,12))

def run():
    solids, coins, spikes, enemies, plats, goal, checks, size, spawn = parse_level(LEVEL)
    ply = Player(spawn[0], spawn[1])
    ply.checkpoint.update(spawn[0], spawn[1])
    cam = Camera()
    parts=[]
    paused=False
    while True:
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and e.key==pygame.K_p: paused=not paused
        if paused:
            screen.fill(DARK)
            t=F(48).render("Paused", True, WHITE)
            screen.blit(t, (W//2 - t.get_width()//2, H//2 - t.get_height()//2))
            pygame.display.flip(); clock.tick(FPS); continue

        inp.update()
        dt = clock.tick(FPS)/1000.0

        for p in plats: p.update(dt)
        for e in enemies: e.update(dt, solids+ [p.rect for p in plats])

        state = ply.update(dt, inp, solids+ [p.rect for p in plats], plats, coins, spikes, enemies, goal, checks, cam, parts)
        cam.update(ply.rect, size[0], size[1])

        screen.fill(DARK)
        draw_world(screen, cam, solids, coins, spikes, enemies, plats, goal, checks)

        pr = cam.apply(ply.rect)
        pygame.draw.rect(screen,ACCENT,pr,border_radius=8)
        pygame.draw.rect(screen,WHITE,pr,2,border_radius=8)

        i=0
        while i<len(parts):
            if parts[i].update(dt): parts[i].draw(screen,cam); i+=1
            else: parts.pop(i)

        hud(screen, ply)

        if state=="win":
            overlay=pygame.Surface((W,H),pygame.SRCALPHA)
            overlay.fill((0,0,0,160)); screen.blit(overlay,(0,0))
            t1=F(64).render("You Win!", True, WHITE)
            t2=F(24).render("Press ESC to quit", True, GRAY)
            screen.blit(t1,(W//2-t1.get_width()//2,H//2-60))
            screen.blit(t2,(W//2-t2.get_width()//2,H//2+10))

        pygame.display.flip()

inp = Input()

if __name__=="__main__":
    run()
