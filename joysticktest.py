import os, sys, time, pygame

if "DISPLAY" not in os.environ:
    os.environ["SDL_VIDEODRIVER"] = "dummy"

pygame.init()
pygame.joystick.init()

def print_device(js):
    try:
        iid = js.get_instance_id()
    except AttributeError:
        iid = js.get_id()
    print(f"[{iid}] {js.get_name()} | axes:{js.get_numaxes()} buttons:{js.get_numbuttons()} hats:{js.get_numhats()}")

def scan():
    pygame.joystick.quit()
    pygame.joystick.init()
    out = []
    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        js.init()
        out.append(js)
    return out

def open_window():
    try:
        win = pygame.display.set_mode((680, 400))
        pygame.display.set_caption("Joystick Test")
        return win
    except pygame.error:
        return None

screen = open_window()
font = pygame.font.Font(None, 24)
clock = pygame.time.Clock()

joysticks = scan()
print(f"Detected {len(joysticks)} device(s).")
for js in joysticks:
    print_device(js)

axis_last = {}
axis_print_threshold = 0.05
running = True

while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False
        elif e.type == pygame.JOYDEVICEADDED or e.type == pygame.JOYDEVICEREMOVED:
            joysticks = scan()
            print(f"Rescanned: {len(joysticks)} device(s).")
            for js in joysticks:
                print_device(js)
        elif e.type == pygame.JOYBUTTONDOWN:
            print(f"joy{e.joy} BUTTON {e.button} DOWN")
        elif e.type == pygame.JOYBUTTONUP:
            print(f"joy{e.joy} BUTTON {e.button} UP")
        elif e.type == pygame.JOYAXISMOTION:
            val = round(e.value, 2)
            key = (e.joy, e.axis)
            last = axis_last.get(key)
            if last is None or abs(val - last) >= axis_print_threshold or val in (-1.0, 0.0, 1.0):
                axis_last[key] = val
                print(f"joy{e.joy} AXIS {e.axis}: {val:+.2f}")
        elif e.type == pygame.JOYHATMOTION:
            print(f"joy{e.joy} HAT {e.hat}: {e.value}")
        elif e.type == pygame.KEYDOWN:
            print(f"KEY DOWN: {e.key}")
        elif e.type == pygame.KEYUP:
            print(f"KEY UP  : {e.key}")

    if screen:
        screen.fill((12, 12, 14))
        y = 10
        if not joysticks:
            msg = "No joysticks detected. If your board is keyboard-type, press buttons."
            img = font.render(msg, True, (230, 230, 235))
            screen.blit(img, (10, y))
        for js in joysticks:
            name = js.get_name()
            hdr = f"{name}  axes:{js.get_numaxes()} buttons:{js.get_numbuttons()} hats:{js.get_numhats()}"
            img = font.render(hdr, True, (230, 230, 235))
            screen.blit(img, (10, y))
            y += img.get_height() + 4

            for a in range(js.get_numaxes()):
                v = js.get_axis(a)
                pygame.draw.rect(screen, (60, 60, 70), pygame.Rect(10, y, 220, 12), border_radius=4)
                fill = int((v + 1) / 2 * 220)
                pygame.draw.rect(screen, (120, 200, 255), pygame.Rect(10, y, fill, 12), border_radius=4)
                img = font.render(f"axis {a}: {v:+.2f}", True, (180, 180, 190))
                screen.blit(img, (240, y - 2))
                y += 16

            for h in range(js.get_numhats()):
                hat = js.get_hat(h)
                img = font.render(f"hat {h}: {hat}", True, (180, 180, 190))
                screen.blit(img, (10, y))
                y += 16

            downs = [str(b) for b in range(js.get_numbuttons()) if js.get_button(b)]
            img = font.render("buttons down: " + (", ".join(downs) if downs else "none"), True, (180, 180, 190))
            screen.blit(img, (10, y))
            y += 26

            y += 6

        pygame.display.flip()

    clock.tick(120)

pygame.quit()
sys.exit(0)
