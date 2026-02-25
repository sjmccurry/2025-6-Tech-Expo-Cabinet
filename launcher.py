import os
import sys
import json
import math
import time
import subprocess
import pygame
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum, auto

pygame.init()

BACKGROUND_COLOR = (15, 16, 20)
CARD_BACKGROUND_COLOR = (28, 29, 36)
TEXT_COLOR_PRIMARY = (238, 239, 244)
TEXT_COLOR_SECONDARY = (188, 190, 198)

def draw_rounded_rect(surface, rect, color, radius=0, width=0):
    try:
        pygame.draw.rect(surface, color, rect, width, border_radius=radius)
    except TypeError:
        pygame.draw.rect(surface, color, rect, width)

def scale_to_cover(surface, target_size):
    image_width, image_height = surface.get_size()
    target_width, target_height = target_size
    
    scale_factor = max(float(target_width) / image_width, float(target_height) / image_height)
    new_width = int(image_width * scale_factor)
    new_height = int(image_height * scale_factor)
    
    return pygame.transform.smoothscale(surface, (new_width, new_height))

def blit_rounded_image(destination_surface, image, rect, radius):
    if not image:
        draw_rounded_rect(destination_surface, rect, (40, 42, 50), radius)
        return
        
    scaled_image = scale_to_cover(image, (rect.width, rect.height))
    layer = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    
    x_offset = (rect.width - scaled_image.get_width()) // 2
    y_offset = (rect.height - scaled_image.get_height()) // 2
    layer.blit(scaled_image, (x_offset, y_offset))
    
    mask = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    draw_rounded_rect(mask, mask.get_rect(), (255, 255, 255, 255), radius)
    
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    destination_surface.blit(layer, rect.topleft)

def get_font(size): 
    return pygame.font.Font(None, size)

class Action(Enum):
    LEFT = auto()
    RIGHT = auto()
    LAUNCH = auto()
    BACK = auto()

class JoyInput:
    def __init__(self, joy_index=0, deadzone=0.35):
        self.deadzone = deadzone
        pygame.joystick.init()
        self.joystick = None
        
        if pygame.joystick.get_count() > joy_index:
            self.joystick = pygame.joystick.Joystick(joy_index)
            self.joystick.init()
            
        if self.joystick:
            name = self.joystick.get_name()
            axes = self.joystick.get_numaxes()
            buttons = self.joystick.get_numbuttons()
            hats = self.joystick.get_numhats()
            print(f"[LAUNCHER] Using joystick: {name} | axes:{axes} buttons:{buttons} hats:{hats}")
        else:
            print("[LAUNCHER] No joystick detected.")
            
        self.previous_buttons = {}
        self.previous_hat = (0, 0)
        self.previous_axis_x = 0.0
        self.previous_actions = {action: False for action in Action}
        self.current_actions = {action: False for action in Action}

    def _is_button_pressed(self, button_index):
        if self.joystick and self.joystick.get_numbuttons() > button_index:
            return self.joystick.get_button(button_index)
        return False

    def update(self):
        if self.joystick:
            total_buttons = self.joystick.get_numbuttons()
            for button_index in range(total_buttons):
                is_pressed = bool(self.joystick.get_button(button_index))
                was_pressed = self.previous_buttons.get(button_index, False)
                
                if is_pressed != was_pressed:
                    state = 'DOWN' if is_pressed else 'UP'
                    print(f"[LAUNCHER] BUTTON {button_index} {state}")
                self.previous_buttons[button_index] = is_pressed

            current_hat = (0, 0)
            if self.joystick.get_numhats() > 0:
                current_hat = self.joystick.get_hat(0)
                
            if current_hat != self.previous_hat:
                print(f"[LAUNCHER] HAT0 -> {current_hat}")
            self.previous_hat = current_hat

            axis_x = self.joystick.get_axis(0) if self.joystick.get_numaxes() > 0 else 0.0
            
            if abs(axis_x - self.previous_axis_x) >= 0.1 or axis_x in (-1.0, 0.0, 1.0):
                print(f"[LAUNCHER] AXIS0 {axis_x:+.2f}")
            self.previous_axis_x = axis_x

            direction_x = current_hat[0]
            if direction_x == 0:
                if axis_x < -self.deadzone: 
                    direction_x = -1
                elif axis_x > self.deadzone: 
                    direction_x = 1

            self.current_actions[Action.LEFT] = (direction_x < 0)
            self.current_actions[Action.RIGHT] = (direction_x > 0)
            self.current_actions[Action.LAUNCH] = bool(self._is_button_pressed(0))
            self.current_actions[Action.BACK] = bool(self._is_button_pressed(1) or self._is_button_pressed(7))
        else:
            for action in self.current_actions: 
                self.current_actions[action] = False

    def is_action_just_pressed(self, action):
        was_pressed = self.previous_actions[action]
        is_pressed_now = self.current_actions[action]
        self.previous_actions[action] = is_pressed_now
        
        if is_pressed_now and not was_pressed:
            print(f"[LAUNCHER] ACTION {action.name} PRESSED")
            
        return is_pressed_now and not was_pressed

@dataclass
class GameEntry:
    slug: str
    title: str
    subtitle: str
    path: str
    cover: Optional[pygame.Surface]
    accent: Tuple[int, int, int]


def load_cover_image(filepath):
    try: 
        return pygame.image.load(filepath).convert_alpha()
    except Exception: 
        return None

def discover_games(root_directory):
    discovered_games = []
    
    if not os.path.isdir(root_directory): 
        return discovered_games
        
    for slug in sorted(os.listdir(root_directory)):
        game_path = os.path.join(root_directory, slug)
        main_script_path = os.path.join(game_path, "main.py")
        
        if not (os.path.isdir(game_path) and os.path.isfile(main_script_path)): 
            continue
            
        title = slug.replace("_", " ").title()
        subtitle = ""
        accent_color = (64, 140, 255)
        meta_filepath = os.path.join(game_path, "meta.json")
        
        if os.path.isfile(meta_filepath):
            try:
                with open(meta_filepath, "r", encoding="utf-8") as meta_file:
                    metadata = json.load(meta_file)
                    title = metadata.get("title", title)
                    subtitle = metadata.get("subtitle", "")
                    
                    if isinstance(metadata.get("accent"), list) and len(metadata["accent"]) == 3: 
                        accent_color = tuple(int(color_value) for color_value in metadata["accent"])
            except Exception: 
                pass
                
        cover_image = None
        valid_cover_filenames = ("cover.png", "cover.jpg", "cover.jpeg", "cover.webp")
        
        for filename in valid_cover_filenames:
            cover_filepath = os.path.join(game_path, filename)
            if os.path.isfile(cover_filepath): 
                cover_image = load_cover_image(cover_filepath)
                break
                
        discovered_games.append(GameEntry(slug, title, subtitle, game_path, cover_image, accent_color))
        
    return discovered_games

def paint_background(surface):
    surface.fill(BACKGROUND_COLOR)
    width, height = surface.get_size()
    band_surface = pygame.Surface((width, int(height * 0.45)), pygame.SRCALPHA)
    draw_rounded_rect(band_surface, band_surface.get_rect(), (255, 255, 255, 12), 0)
    
    try: 
        surface.blit(band_surface, (0, int(height * 0.06)), special_flags=pygame.BLEND_RGBA_SUB)
    except Exception: 
        surface.blit(band_surface, (0, int(height * 0.06)))

def draw_side_card(surface, entry, rect, fade_amount):
    draw_rounded_rect(surface, rect, CARD_BACKGROUND_COLOR, 20)
    inner_rect = rect.inflate(-14, -14)
    blit_rounded_image(surface, entry.cover, inner_rect, 16)
    
    dim_overlay = pygame.Surface(inner_rect.size, pygame.SRCALPHA)
    dim_overlay.fill((0, 0, 0, int(200 * (1 - fade_amount))))
    surface.blit(dim_overlay, inner_rect.topleft)
    
    pygame.draw.rect(surface, (*entry.accent, 50), rect, 2)

def draw_focus_card_base(surface, entry, rect):
    draw_rounded_rect(surface, rect, CARD_BACKGROUND_COLOR, 20)
    padding = 16
    
    image_rect = pygame.Rect(rect.x + padding, rect.y + padding, rect.width - 2 * padding, int(rect.height * 0.68))
    footer_rect = pygame.Rect(rect.x + padding, image_rect.bottom + 8, rect.width - 2 * padding, rect.bottom - (image_rect.bottom + 8) - padding)
    
    blit_rounded_image(surface, entry.cover, image_rect, 14)
    draw_rounded_rect(surface, footer_rect, (22, 23, 28), 12)
    pygame.draw.rect(surface, (*entry.accent, 80), rect, 2)
    
    return footer_rect

def run():
    screen_width, screen_height = 1180, 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("Arcade Launcher")
    clock = pygame.time.Clock()

    games_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "games")
    games = discover_games(games_directory)
    total_games = len(games)
    
    joystick_input = JoyInput(joy_index=0, deadzone=0.35)

    current_index = 0
    scroll_position = float(current_index)
    time_elapsed = 0.0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: 
                pygame.quit()
                sys.exit()

        joystick_input.update()

        if total_games > 0:
            if joystick_input.is_action_just_pressed(Action.RIGHT): 
                current_index = (current_index + 1) % total_games
            if joystick_input.is_action_just_pressed(Action.LEFT):  
                current_index = (current_index - 1) % total_games

        delta_time = clock.tick(60) / 1000.0
        scroll_position += (current_index - scroll_position) * min(1.0, delta_time * 10.0)

        paint_background(screen)

        if total_games > 0:
            hero_width = int(min(screen_width * 0.50, 760))
            hero_height = int(hero_width * 0.60)
            center_rect = pygame.Rect(0, 0, hero_width, hero_height)
            center_rect.center = (screen_width // 2, int(screen_height * 0.56))
            card_spacing = int(hero_width * 0.72)
            
            render_items = []
            
            for index in range(total_games):
                distance_from_center = ((index - scroll_position + total_games / 2) % total_games) - total_games / 2
                
                if abs(distance_from_center) > 3: 
                    continue
                    
                scale_factor = 0.62 + 0.38 * max(0.0, 1.0 - abs(distance_from_center) * 0.55)
                x_offset = int(distance_from_center * card_spacing)
                y_offset = int(abs(distance_from_center) * hero_height * 0.10)
                
                translated_rect = center_rect.move(x_offset, y_offset)
                final_rect = pygame.Rect(translated_rect.x, translated_rect.y, int(center_rect.width * scale_factor), int(center_rect.height * scale_factor))
                
                render_items.append((index, distance_from_center, scale_factor, final_rect))
                
            for index, distance, scale, rect in sorted(render_items, key=lambda item: item[2]):
                if index == current_index: 
                    continue
                fade = 0.85 if abs(distance) < 0.5 else 0.65
                draw_side_card(screen, games[index], rect, fade)
                
            focused_footer = None
            focused_entry = None
            focused_scale = None
            
            for index, distance, scale, rect in render_items:
                if index == current_index:
                    focused_footer = draw_focus_card_base(screen, games[index], rect)
                    focused_entry = games[index]
                    focused_scale = scale
                    break

        title_text = get_font(66).render("ARCADE", True, TEXT_COLOR_PRIMARY)
        screen.blit(title_text, (48, 40))
        
        subtitle_text = get_font(22).render("D-pad/Stick: browse  •  A: play  •  B/Start: back", True, TEXT_COLOR_SECONDARY)
        screen.blit(subtitle_text, (48, 40 + title_text.get_height() + 6))

        if total_games > 0 and focused_entry:
            game_title_text = get_font(int(38 * focused_scale)).render(focused_entry.title, True, TEXT_COLOR_PRIMARY)
            screen.blit(game_title_text, (focused_footer.x + 14, focused_footer.y + 10))
            
            if focused_entry.subtitle:
                game_subtitle_text = get_font(int(22 * focused_scale)).render(focused_entry.subtitle, True, TEXT_COLOR_SECONDARY)
                screen.blit(game_subtitle_text, (focused_footer.x + 14, focused_footer.bottom - 28))
                
            pulse_effect = 0.5 * (1 + math.sin(time_elapsed * 2.2))
            pill_width = min(focused_footer.width - 20, int(360 * focused_scale))
            pill_height = int(40 * focused_scale)
            
            pill_rect = pygame.Rect(0, 0, pill_width, pill_height)
            pill_rect.center = (focused_footer.centerx, focused_footer.bottom + int(24 * focused_scale))
            
            draw_rounded_rect(screen, pill_rect, (*focused_entry.accent, int(190 + 40 * pulse_effect)), 999)
            
            play_text = get_font(int(24 * focused_scale)).render("Press A to Play", True, (255, 255, 255))
            screen.blit(play_text, play_text.get_rect(center=pill_rect.center))

        if total_games > 0 and joystick_input.is_action_just_pressed(Action.LAUNCH):
            chosen_game = games[current_index]
            print(f"[LAUNCHER] Launching {chosen_game.slug}")
            
            pygame.display.quit()
            try: 
                subprocess.call([sys.executable, os.path.join(chosen_game.path, "main.py")])
            except Exception as error: 
                print("[LAUNCHER] Game error:", error)
                
            pygame.display.init()
            screen = pygame.display.set_mode((screen_width, screen_height))
            clock = pygame.time.Clock()
            
            games = discover_games(games_directory)
            total_games = len(games)
            current_index = min(current_index, total_games - 1) if total_games > 0 else 0
            scroll_position = float(current_index)
            joystick_input = JoyInput(joy_index=0, deadzone=0.35)

        if joystick_input.is_action_just_pressed(Action.BACK):
            print("[LAUNCHER] Back/Exit pressed")
            pygame.quit()
            sys.exit()

        pygame.display.flip()
        time_elapsed += delta_time

if __name__ == "__main__":
    run()