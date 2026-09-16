import ctypes
import math
import queue
import sys
import threading
import time

from macro.profiles import Profile
from macro.rapid_fire import RapidFire


class FractionalMotion:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = self.y = 0.0

    def step(self, lateral, vertical):
        self.x += lateral * 0.3
        self.y += vertical
        # Small horizontal adjustments accumulate instead of being lost.
        x, y = math.trunc(self.x + math.copysign(1e-9, self.x)), math.trunc(self.y + 1e-9)
        self.x -= x
        self.y -= y
        return x, y


class Engine:
    def __init__(self):
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.events = queue.SimpleQueue()
        self.profile = Profile("default", "Manual", "Manual")
        self.session = None
        self.enabled = False
        self.left = self.right = False
        self.available = False
        self.error = ""
        self.keyboard_listener = self.mouse_listener = self.worker = None
        self.motion = FractionalMotion()
        self.held_keys = set()
        self.rapid = RapidFire()
        self.next_motion = 0.0

    def start(self):
        if sys.platform != "win32":
            self.error = "Movimento e atalhos disponíveis somente no Windows."
            return
        try:
            from pynput import keyboard, mouse
            self.keyboard = keyboard
            self.mouse = mouse
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            self.user32.mouse_event.argtypes = [
                ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_uint32, ctypes.c_size_t]
            self.user32.mouse_event.restype = None
            self.keyboard_listener = keyboard.Listener(on_press=self._key_down, on_release=self._key_up)
            self.mouse_listener = mouse.Listener(
                on_click=self._click, win32_event_filter=self._physical_events_only)
            self.keyboard_listener.start()
            self.mouse_listener.start()
            self.worker = threading.Thread(target=self._loop, daemon=True)
            self.available = True
            self.worker.start()
        except Exception as error:
            self.error = "Falha ao iniciar entrada: " + str(error)
            self.close()

    def _key_down(self, key):
        with self.lock:
            if key in self.held_keys:
                return
            self.held_keys.add(key)
        if key == self.keyboard.Key.f9:
            self.events.put("toggle")
        elif key == self.keyboard.Key.insert:
            self.pause()  # Immediate stop, even if the GUI is busy.
            self.events.put("stop")

    def _key_up(self, key):
        with self.lock:
            self.held_keys.discard(key)

    @staticmethod
    def _physical_events_only(msg, data):
        # Ignore injected clicks in OUR callbacks to prevent feedback loops.
        # Events remain visible to Windows; this does not suppress OS input.
        return not bool(data.flags & 0x00000001)

    def _emit_buttons(self, flags):
        for flag in flags:
            self.user32.mouse_event(flag, 0, 0, 0, 0)

    def _stop_firing(self):
        self._emit_buttons(self.rapid.stop())

    def _click(self, x, y, button, pressed):
        with self.lock:
            if button == self.mouse.Button.left:
                self.left = pressed
            elif button == self.mouse.Button.right:
                self.right = pressed
            if not (self.left and self.right):
                self._stop_firing()
                self.next_motion = 0.0

    def set_profile(self, profile):
        profile.validate()
        with self.lock:
            self.pause()
            self.profile = profile

    def set_session(self, session):
        with self.lock:
            self.pause()
            self.session = session

    def pause(self):
        with self.lock:
            self.enabled = False
            self.left = self.right = False
            self.motion.reset()
            self.next_motion = 0.0
            self._stop_firing()

    def toggle(self):
        with self.lock:
            if self.enabled:
                self.pause()
                return
            if not self.available:
                raise ValueError(self.error or "Motor indisponível.")
            if not self.session or not self.session.valid():
                raise ValueError("Ative uma licença válida na aba Licença.")
            self.left = self.right = False
            self.motion.reset()
            self.enabled = True

    def _loop(self):
        try:
            while not self.stop_event.is_set():
                with self.lock:
                    if self.enabled and (not self.session or not self.session.valid()):
                        self.pause()
                        self.events.put("expired")
                    interval = self._tick(time.monotonic())
                self.stop_event.wait(interval)
        except Exception as error:
            self.pause()
            self.available = False
            self.error = str(error)
            self.events.put("error")

    def _tick(self, now):
        if not (self.enabled and self.left and self.right):
            self._stop_firing()
            self.motion.reset()
            self.next_motion = 0.0
            return 0.005
        if self.profile.rapid_fire:
            self._emit_buttons(self.rapid.step(now, self.profile.fire_cps))
        else:
            self._stop_firing()
        if now >= self.next_motion:
            x, y = self.motion.step(self.profile.lateral, self.profile.vertical)
            if x or y:
                self.user32.mouse_event(0x0001, x & 0xffffffff, y & 0xffffffff, 0, 0)
            self.next_motion = now + self.profile.interval_ms / 1000
        return max(0.001, min(0.005, self.next_motion - now))

    def close(self):
        self.pause()
        self.available = False
        self.stop_event.set()
        for listener in (self.keyboard_listener, self.mouse_listener):
            if listener:
                listener.stop()
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=1)
