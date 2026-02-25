import sys
import os
import math
import random
import pygame

pygame.init()

WINDOW_WIDTH = 960
WINDOW_HEIGHT = 540
TILE_SIZE = 48
FPS = 60

COLOR_WHITE = (245, 245, 250)
COLOR_GRAY = (180, 184, 194)
COLOR_DARK = (18, 19, 23)
COLOR_GROUND = (36, 37, 46)
COLOR_ACCENT = (230, 70, 80)
COLOR_GOLD = (245, 200, 80)
COLOR_SPIKE = (220, 60, 60)
COLOR_GREEN = (70, 200, 120)

screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Red Runner")
clock = pygame.time.Clock()


def get_font(size):
    return pygame.font.Font(None, size)


def draw_rounded_rect(surface, rect, color, radius=0, width=0):
    try:
        pygame.draw.rect(surface, color, rect, width, border_radius=radius)
    except TypeError:
        pygame.draw.rect(surface, color, rect, width)


LEVEL_DATA = [
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

TILE_SOLID = {"X"}
TILE_COIN = {"c"}
TILE_SPIKES = {"^"}
TILE_SPAWN = {"@"}
TILE_CHECKPOINT = {"!"}
TILE_GOAL = {"G"}
TILE_PLATFORM_H = {"="}
TILE_PLATFORM_V = {"|"}


class InputHandler:
    def __init__(self, joy_index=0, deadzone=0.35):
        self.deadzone = deadzone
        pygame.joystick.init()
        self.joy = None
        
        if pygame.joystick.get_count() > joy_index:
            self.joy = pygame.joystick.Joystick(joy_index)
            self.joy.init()
            print("[GAME] Using joystick:", self.joy.get_name(), 
                  "axes:", self.joy.get_numaxes(), 
                  "buttons:", self.joy.get_numbuttons(), 
                  "hats:", self.joy.get_numhats())
        else:
            print("[GAME] No joystick detected.")
            
        self.btn_prev = {}
        self.hat_prev = (0, 0)
        self.ax0_prev = 0.0
        
        self.left_prev = False
        self.right_prev = False
        self.jump_prev = False
        self.back_prev = False
        
        self.left_now = False
        self.right_now = False
        self.jump_now = False
        self.back_now = False

    def _get_button(self, i):
        return self.joy and self.joy.get_numbuttons() > i and self.joy.get_button(i)

    def update(self):
        self.left_prev = self.left_now
        self.right_prev = self.right_now
        self.jump_prev = self.jump_now
        self.back_prev = self.back_now
        
        if not self.joy:
            self.left_now = False
            self.right_now = False
            self.jump_now = False
            self.back_now = False
            return

        num_buttons = self.joy.get_numbuttons()
        for b in range(num_buttons):
            val = bool(self.joy.get_button(b))
            prev_val = self.btn_prev.get(b, False)
            if val != prev_val:
                print("[GAME] BUTTON", b, "DOWN" if val else "UP")
            self.btn_prev[b] = val

        hat = (0, 0)
        if self.joy.get_numhats() > 0:
            hat = self.joy.get_hat(0)
            
        if hat != self.hat_prev:
            print("[GAME] HAT0 ->", hat)
        self.hat_prev = hat

        ax0 = self.joy.get_axis(0) if self.joy.get_numaxes() > 0 else 0.0
        if abs(ax0 - self.ax0_prev) >= 0.1 or ax0 in (-1.0, 0.0, 1.0):
            print("[GAME] AXIS0 %+.2f" % ax0)
        self.ax0_prev = ax0

        x_dir = hat[0]
        if x_dir == 0:
            if ax0 < -self.deadzone:
                x_dir = -1
            elif ax0 > self.deadzone:
                x_dir = 1

        self.left_now = (x_dir < 0)
        self.right_now = (x_dir > 0)
        self.jump_now = bool(self._get_button(0))
        self.back_now = bool(self._get_button(1) or self._get_button(7))

    def left(self):
        return self.left_now

    def right(self):
        return self.right_now

    def jump_pressed(self):
        val = self.jump_now and not self.jump_prev
        if val:
            print("[GAME] ACTION JUMP PRESSED")
        return val

    def jump_released(self):
        val = (not self.jump_now) and self.jump_prev
        if val:
            print("[GAME] ACTION JUMP RELEASED")
        return val

    def back_pressed(self):
        val = self.back_now and not self.back_prev
        if val:
            print("[GAME] ACTION BACK PRESSED")
        return val


class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.shake_time = 0.0
        self.shake_magnitude = 0.0

    def update(self, target_rect, level_w, level_h):
        target_x = target_rect.centerx - WINDOW_WIDTH / 2
        target_y = target_rect.centery - WINDOW_HEIGHT * 0.55
        
        target_x = max(0, min(target_x, level_w - WINDOW_WIDTH))
        target_y = max(0, min(target_y, level_h - WINDOW_HEIGHT))
        
        self.x += (target_x - self.x) * 0.12
        self.y += (target_y - self.y) * 0.12
        
        if self.shake_time > 0:
            self.shake_time -= 1 / FPS

    def add_shake(self, magnitude, duration=0.25):
        self.shake_magnitude = max(self.shake_magnitude, magnitude)
        self.shake_time = max(self.shake_time, duration)

    def apply(self, rect):
        offset_x = 0
        offset_y = 0
        
        if self.shake_time > 0:
            current_mag = self.shake_magnitude * self.shake_time
            offset_x = random.uniform(-current_mag, current_mag)
            offset_y = random.uniform(-current_mag, current_mag)
            
        return rect.move(int(-self.x + offset_x), int(-self.y + offset_y))


class Particle:
    def __init__(self, pos, vel, life, color, radius):
        self.x, self.y = pos
        self.vx, self.vy = vel
        self.life = life
        self.time_alive = 0
        self.color = color
        self.radius = radius

    def update(self, dt):
        self.time_alive += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 500 * dt
        return self.time_alive < self.life

    def draw(self, surface, camera):
        alpha_ratio = max(0, 1 - self.time_alive / self.life)
        color_with_alpha = (self.color[0], self.color[1], self.color[2], int(255 * alpha_ratio))
        
        temp_surface = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(temp_surface, color_with_alpha, (self.radius, self.radius), self.radius)
        
        draw_x = int(self.x - camera.x)
        draw_y = int(self.y - camera.y)
        rect = temp_surface.get_rect(center=(draw_x, draw_y))
        
        surface.blit(temp_surface, rect.topleft)


class Platform:
    def __init__(self, x, y, width, height, dx, dy, distance, speed):
        self.base = pygame.Vector2(x, y)
        self.rect = pygame.Rect(x, y, width, height)
        self.direction = pygame.Vector2(dx, dy)
        self.distance = distance
        self.speed = speed
        self.time = 0.0
        self.prev_rect = self.rect.copy()

    def update(self, dt):
        self.prev_rect = self.rect.copy()
        self.time += dt * self.speed
        
        progress = (math.sin(self.time) + 1) / 2
        offset = self.direction * self.distance * (progress * 2 - 1)
        
        self.rect.topleft = (int(self.base.x + offset.x), int(self.base.y + offset.y))

    @property
    def delta(self):
        return pygame.Vector2(self.rect.x - self.prev_rect.x, self.rect.y - self.prev_rect.y)

    def draw(self, surface, camera):
        render_rect = camera.apply(self.rect)
        draw_rounded_rect(surface, render_rect, (90, 90, 110), 6)
        pygame.draw.rect(surface, (140, 140, 170), render_rect, 2)


class Enemy:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, TILE_SIZE - 8, TILE_SIZE - 8)
        self.vx = 120
        self.direction = 1

    def update(self, dt, solids):
        self.rect.x += int(self.vx * self.direction * dt)
        if get_solid_collision(self.rect, solids):
            self.direction *= -1
            self.rect.x += int(self.vx * self.direction * dt)

    def draw(self, surface, camera):
        render_rect = camera.apply(self.rect)
        draw_rounded_rect(surface, render_rect, (200, 80, 120), 8)
        pygame.draw.rect(surface, (255, 160, 200), render_rect, 2)


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 32, 42)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.coyote_time = 0.0
        self.jump_buffer = 0.0
        self.facing = 1
        self.coins = 0
        self.checkpoint = pygame.Vector2(x, y)

    def touches_any(self, rects):
        return any(self.rect.colliderect(r) for r in rects)

    def update(self, dt, input_handler, solids, platforms, coins, spikes, enemies, goal, checkpoints, camera, particles):
        ax = 0.0
        max_speed = 210
        accel = 1700 if self.on_ground else 1300
        deccel = 2000

        if input_handler.left():
            ax -= accel
            self.facing = -1
            
        if input_handler.right():
            ax += accel
            self.facing = 1

        if ax == 0:
            if self.vx > 0:
                self.vx = max(0, self.vx - deccel * dt)
            elif self.vx < 0:
                self.vx = min(0, self.vx + deccel * dt)
        else:
            self.vx += ax * dt
            self.vx = max(-max_speed, min(max_speed, self.vx))

        if input_handler.jump_pressed():
            self.jump_buffer = 0.15
        else:
            self.jump_buffer = max(0.0, self.jump_buffer - dt)

        if self.on_ground:
            self.coyote_time = 0.12
        else:
            self.coyote_time = max(0.0, self.coyote_time - dt)

        if self.jump_buffer > 0 and self.coyote_time > 0:
            self.vy = -360
            self.on_ground = False
            self.jump_buffer = 0
            
            for _ in range(8):
                angle = random.uniform(-0.4, 0.4)
                speed = random.uniform(80, 160)
                particles.append(Particle(
                    (self.rect.centerx, self.rect.bottom),
                    (speed * math.cos(angle), -abs(speed * math.sin(angle))),
                    0.4, COLOR_WHITE, 3
                ))

        if input_handler.jump_released() and self.vy < -120:
            self.vy = -120

        self.vy += 1000 * dt
        self.vy = max(-1000, min(980, self.vy))

        self.move_x(self.vx * dt, solids)
        self.apply_platform_x(platforms)
        
        self.move_y(self.vy * dt, solids)
        self.on_ground = False
        self.apply_platform_y(platforms)
        
        self.collect_items(coins, particles)

        if self.touches_any(spikes) or any(self.rect.colliderect(e.rect) for e in enemies):
            self.die(camera, particles)

        if any(self.rect.colliderect(r) for r in goal):
            return "win"

        for r in checkpoints:
            if self.rect.colliderect(r):
                self.checkpoint.update(r.x, r.y - self.rect.height - 6)
                
        return None

    def move_x(self, dx, solids):
        self.rect.x += int(dx)
        hit = get_solid_collision(self.rect, solids)
        
        if hit:
            if dx > 0:
                self.rect.right = hit.left
            elif dx < 0:
                self.rect.left = hit.right
            self.vx = 0

    def move_y(self, dy, solids):
        self.rect.y += int(dy)
        hit = get_solid_collision(self.rect, solids)
        
        if hit:
            if dy > 0:
                self.rect.bottom = hit.top
                self.vy = 0
                self.on_ground = True
            elif dy < 0:
                self.rect.top = hit.bottom
                self.vy = 0

    def apply_platform_x(self, platforms):
        for p in platforms:
            if p.delta.x != 0 and self.rect.colliderect(p.rect):
                if p.delta.x > 0:
                    self.rect.right = min(self.rect.right, p.rect.left)
                    self.vx = 0
                else:
                    self.rect.left = max(self.rect.left, p.rect.right)
                    self.vx = 0

    def apply_platform_y(self, platforms):
        carried_by = None
        for p in platforms:
            if p.delta.y != 0 and self.rect.colliderect(p.rect):
                if p.delta.y > 0 and self.rect.bottom <= p.rect.top + 8:
                    self.rect.bottom = p.rect.top
                    self.vy = 0
                    self.on_ground = True
                    carried_by = p
                elif p.delta.y < 0 and self.rect.top >= p.rect.bottom - 8:
                    self.rect.top = p.rect.bottom
                    self.vy = 0
                    
        if carried_by:
            self.rect.x += int(carried_by.delta.x)

    def collect_items(self, coins, particles):
        i = 0
        while i < len(coins):
            if self.rect.colliderect(coins[i]):
                self.coins += 1
                cx, cy = coins[i].center
                
                for _ in range(12):
                    angle = random.uniform(0, math.tau)
                    speed = random.uniform(90, 180)
                    particles.append(Particle(
                        (cx, cy),
                        (speed * math.cos(angle), speed * math.sin(angle) - 120),
                        0.6, COLOR_GOLD, 3
                    ))
                    
                coins.pop(i)
            else:
                i += 1

    def die(self, camera, particles):
        camera.add_shake(8, 0.2)
        cx, cy = self.rect.center
        
        for _ in range(20):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(120, 240)
            particles.append(Particle(
                (cx, cy),
                (speed * math.cos(angle), speed * math.sin(angle) - 120),
                0.7, COLOR_ACCENT, 3
            ))
            
        self.vx = 0
        self.vy = 0
        self.rect.topleft = (int(self.checkpoint.x), int(self.checkpoint.y))


def get_solid_collision(rect, solids):
    for r in solids:
        if rect.colliderect(r):
            return r
    return None


def parse_level_data(rows):
    solids = []
    coins = []
    spikes = []
    enemies = []
    platforms = []
    goal = []
    checkpoints = []
    spawn_pos = (64, 64)
    
    level_height = len(rows)
    level_width_tiles = max((len(r) for r in rows), default=0)
    
    for y in range(level_height):
        line = rows[y].ljust(level_width_tiles, ".")
        for x, char in enumerate(line):
            rx = x * TILE_SIZE
            ry = y * TILE_SIZE
            
            if char in TILE_SOLID:
                solids.append(pygame.Rect(rx, ry, TILE_SIZE, TILE_SIZE))
            elif char in TILE_COIN:
                coins.append(pygame.Rect(rx + TILE_SIZE // 3, ry + TILE_SIZE // 3, TILE_SIZE // 3, TILE_SIZE // 3))
            elif char in TILE_SPIKES:
                spikes.append(pygame.Rect(rx, ry + TILE_SIZE // 2, TILE_SIZE, TILE_SIZE // 2))
            elif char in TILE_PLATFORM_H:
                platforms.append(Platform(rx, ry, TILE_SIZE, TILE_SIZE // 3, 1, 0, 80, 1.2))
            elif char in TILE_PLATFORM_V:
                platforms.append(Platform(rx + 6, ry, TILE_SIZE - 12, TILE_SIZE // 3, 0, 1, 90, 1.0))
            elif char in TILE_SPAWN:
                spawn_pos = (rx, ry - 12)
            elif char in TILE_GOAL:
                goal.append(pygame.Rect(rx, ry, TILE_SIZE, TILE_SIZE))
            elif char in TILE_CHECKPOINT:
                checkpoints.append(pygame.Rect(rx, ry, TILE_SIZE, TILE_SIZE))
            elif char == "E":
                enemies.append(Enemy(rx + 6, ry + 8))
                
    return solids, coins, spikes, enemies, platforms, goal, checkpoints, (level_width_tiles * TILE_SIZE, level_height * TILE_SIZE), spawn_pos


def draw_game_world(surface, camera, solids, coins, spikes, enemies, platforms, goal, checkpoints):
    for r in solids:
        pygame.draw.rect(surface, COLOR_GROUND, camera.apply(r))
        
    for p in platforms:
        p.draw(surface, camera)
        
    for r in spikes:
        render_rect = camera.apply(r)
        points = [(render_rect.left, render_rect.bottom), (render_rect.centerx, render_rect.top), (render_rect.right, render_rect.bottom)]
        pygame.draw.polygon(surface, COLOR_SPIKE, points)
        pygame.draw.polygon(surface, (255, 200, 200), points, 2)
        
    for r in coins:
        render_rect = camera.apply(r)
        pygame.draw.circle(surface, COLOR_GOLD, render_rect.center, render_rect.width // 2)
        pygame.draw.circle(surface, COLOR_WHITE, render_rect.center, render_rect.width // 2, 2)
        
    for e in enemies:
        e.draw(surface, camera)
        
    for r in goal:
        render_rect = camera.apply(r)
        pygame.draw.rect(surface, COLOR_GREEN, render_rect)
        pygame.draw.rect(surface, COLOR_WHITE, render_rect, 2)
        
    for r in checkpoints:
        render_rect = camera.apply(r)
        pygame.draw.rect(surface, (100, 180, 255), render_rect)
        pygame.draw.rect(surface, COLOR_WHITE, render_rect, 2)


def draw_hud(surface, player):
    text_surface = get_font(28).render("Coins: %d" % player.coins, True, COLOR_WHITE)
    surface.blit(text_surface, (16, 12))


def run_game():
    solids, coins, spikes, enemies, platforms, goal, checkpoints, level_size, spawn_pos = parse_level_data(LEVEL_DATA)
    
    player = Player(spawn_pos[0], spawn_pos[1])
    camera = Camera()
    particles = []
    input_handler = InputHandler(joy_index=0, deadzone=0.35)
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
        input_handler.update()
        
        if input_handler.back_pressed():
            pygame.quit()
            sys.exit()
            
        dt = clock.tick(FPS) / 1000.0
        
        for p in platforms:
            p.update(dt)
            
        platform_rects = [p.rect for p in platforms]
        combined_solids = solids + platform_rects
        
        for en in enemies:
            en.update(dt, combined_solids)
            
        game_state = player.update(dt, input_handler, combined_solids, platforms, coins, spikes, enemies, goal, checkpoints, camera, particles)
        
        camera.update(player.rect, level_size[0], level_size[1])
        
        screen.fill(COLOR_DARK)
        draw_game_world(screen, camera, solids, coins, spikes, enemies, platforms, goal, checkpoints)
        
        player_render_rect = camera.apply(player.rect)
        draw_rounded_rect(screen, player_render_rect, COLOR_ACCENT, 8)
        pygame.draw.rect(screen, COLOR_WHITE, player_render_rect, 2)
        
        i = 0
        while i < len(particles):
            if particles[i].update(dt):
                particles[i].draw(screen, camera)
                i += 1
            else:
                particles.pop(i)
                
        draw_hud(screen, player)
        
        if game_state == "win":
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))
            
            win_text = get_font(64).render("You Win!", True, COLOR_WHITE)
            exit_text = get_font(24).render("Press B/Start to exit", True, COLOR_GRAY)
            
            screen.blit(win_text, (WINDOW_WIDTH // 2 - win_text.get_width() // 2, WINDOW_HEIGHT // 2 - 60))
            screen.blit(exit_text, (WINDOW_WIDTH // 2 - exit_text.get_width() // 2, WINDOW_HEIGHT // 2 + 10))
            
        pygame.display.flip()


if __name__ == "__main__":
    run_game()