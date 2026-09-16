"""Deterministic click scheduler. Contains no OS calls or sleeping."""
LEFT_DOWN = 0x0002
LEFT_UP = 0x0004


class RapidFire:
    def __init__(self):
        self.active = False
        self.down = False
        self.next_down = 0.0
        self.release_at = 0.0

    def step(self, now, cps):
        period = 1.0 / cps
        if not self.active:
            # The physical press has already reached the target application.
            # Release that first press; schedule repeated presses from now on.
            self.active = True
            self.next_down = now + period
            return (LEFT_UP,)
        if self.down:
            if now >= self.release_at:
                self.down = False
                return (LEFT_UP,)
            return ()
        if now >= self.next_down:
            self.down = True
            self.release_at = now + min(0.020, period / 2)
            # No catch-up burst after a late scheduler tick.
            self.next_down = now + period
            return (LEFT_DOWN,)
        return ()

    def stop(self):
        release = self.active
        self.active = self.down = False
        self.next_down = self.release_at = 0.0
        return (LEFT_UP,) if release else ()
