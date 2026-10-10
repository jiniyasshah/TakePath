"""Best-effort, in-memory visual settling after UI-changing actions.

This is not a DOM/network-idle detector. It waits for visible changes to settle,
or falls back after a short unchanged grace period. It never stores screenshots.
Explicit Wait actions remain available when a true condition must be observed.
"""
from __future__ import annotations

import time
from typing import Callable


class VisualSettlingInterrupted(RuntimeError):
    pass


def average_difference(first: bytes, second: bytes) -> float:
    if not first or len(first) != len(second):
        return float("inf")
    return sum(abs(a-b) for a,b in zip(first,second)) / len(first)


def wait_for_visual_settle(
    sample: Callable[[], bytes | None],
    *,
    cancel: Callable[[], bool] = lambda: False,
    guard: Callable[[], None] = lambda: None,
    paused: Callable[[], bool] = lambda: False,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    max_seconds: float = 2.5,
    quiet_seconds: float = 0.40,
    unchanged_grace: float = 0.75,
    threshold: float = 2.4,
    poll: float = 0.15,
) -> bool:
    """Wait for a visible change to settle. True if settled, False on fallback.

    An unchanged page is considered ready after `unchanged_grace`, since many
    clicks do not change pixels. An unchanging animation can hit max_seconds,
    resulting in False without a false claim that the page is actually ready.
    Every sample is guarded against unintended focus changes.
    """
    if not (0 < quiet_seconds < max_seconds <= 10):
        raise ValueError("Invalid visual wait duration")
    if not (0 < unchanged_grace <= max_seconds and poll > 0):
        raise ValueError("Invalid visual wait polling")
    guard()
    previous = sample()
    if previous is None:
        return False
    start = clock()
    previous_time = start
    saw_change = False
    while True:
        if cancel():
            raise VisualSettlingInterrupted("Playback stopped during UI readiness wait")
        if paused():
            before = clock()
            sleep(min(poll,0.05))
            paused_time=max(0.0,clock()-before)
            start += paused_time
            previous_time += paused_time
            continue
        guard()
        now=clock()
        if now-start >= max_seconds:
            return False
        sleep(min(poll, max_seconds-(now-start)))
        guard()
        current = sample()
        if current is None:
            return False
        now=clock()
        if average_difference(previous,current) > threshold:
            saw_change = True
            previous_time = now
        previous=current
        if saw_change and now-previous_time >= quiet_seconds:
            return True
        if not saw_change and now-start >= unchanged_grace:
            return True


def sample_window_thumbnail(bounds) -> bytes | None:
    """Grab a downscaled greyscale sample; no image is persisted or logged."""
    try:
        import mss
        from PIL import Image
        if not isinstance(bounds,(tuple,list)) or len(bounds)!=4:
            return None
        x,y,w,h=[int(v) for v in bounds]
        if w < 30 or h < 30:
            return None
        with mss.mss() as shot:
            screen=shot.monitors[0]
            left=max(x,screen['left'])
            top=max(y,screen['top'])
            right=min(x+w,screen['left']+screen['width'])
            bottom=min(y+h,screen['top']+screen['height'])
            if right-left < 30 or bottom-top < 30:
                return None
            img=shot.grab({'left':left,'top':top,
                          'width':right-left,'height':bottom-top})
            image=Image.frombytes("RGB",img.size,img.rgb)
            return image.resize((64,36),Image.Resampling.BILINEAR).convert("L").tobytes()
    except Exception:
        return None
