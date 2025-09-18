import pygame, sys, time, random
pygame.init()
w,h=960,540
screen=pygame.display.set_mode((w,h))
clock=pygame.time.Clock()
x,y=120,400; vx=0; vy=0; on_ground=False
while True:
    for e in pygame.event.get():
        if e.type==pygame.QUIT: pygame.quit(); sys.exit()
        if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: pygame.quit(); sys.exit()
    k=pygame.key.get_pressed()
    vx=(-1 if k[pygame.K_LEFT] or k[pygame.K_a] else 1 if k[pygame.K_RIGHT] or k[pygame.K_d] else 0)*6
    if (k[pygame.K_SPACE] or k[pygame.K_RETURN]) and on_ground: vy=-14; on_ground=False
    vy+=0.8; x+=vx; y+=vy
    if y>400: y=400; vy=0; on_ground=True
    screen.fill((14,14,18))
    pygame.draw.rect(screen,(50,180,80),(0,420,w,120))
    pygame.draw.rect(screen,(230,70,80),(int(x),int(y),40,40),border_radius=8)
    pygame.display.flip(); clock.tick(120)
