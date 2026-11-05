"""The musical grid of a song: tempo, meter and where bar 1 starts.

Conventions used everywhere in mavpa:
  * "song bars" are counted from 1 at the first downbeat of the track;
  * the kit puts ``lead_in_bars`` (default 1) in front, so song bar 1 = DAW bar 2,
    and any pickup before the first downbeat lands inside DAW bar 1;
  * a "step" is a 16th note (4 steps per beat), so a 3/4 bar has 12 steps.
"""
from dataclasses import dataclass, asdict


@dataclass
class Grid:
    bpm: float
    beats_per_bar: int = 4
    downbeat: float = 0.0          # seconds into the source file where song bar 1 starts
    beat_unit: int = 4
    steps_per_beat: int = 4
    lead_in_bars: int = 1

    @property
    def beat(self):
        return 60.0 / self.bpm

    @property
    def bar(self):
        return self.beats_per_bar * self.beat

    @property
    def step(self):
        return self.beat / self.steps_per_beat

    @property
    def steps_per_bar(self):
        return self.beats_per_bar * self.steps_per_beat

    @property
    def pad_s(self):
        """Silence prepended to the source so song bar 1 lands on DAW bar lead_in_bars + 1."""
        return self.lead_in_bars * self.bar - self.downbeat

    def t(self, bar, step=0.0):
        """Song bar (1-based) + step -> seconds in the source file."""
        return self.downbeat + (bar - 1) * self.bar + step * self.step

    def daw_t(self, bar, step=0.0):
        """Song bar + step -> seconds in the aligned kit (and in every kit MIDI file)."""
        return (bar - 1 + self.lead_in_bars) * self.bar + step * self.step

    def daw_bar(self, bar):
        return bar + self.lead_in_bars

    def bar_at(self, t):
        """Source seconds -> (song bar, step float)."""
        q = (t - self.downbeat) / self.step
        return int(q // self.steps_per_bar) + 1, q % self.steps_per_bar

    def n_bars(self, duration):
        """Number of song bars that start before the end of a source of this duration."""
        import math
        return max(1, int(math.ceil((duration - self.downbeat) / self.bar)))

    def step_names(self):
        return [f"{b}{s}" for b in range(1, self.beats_per_bar + 1) for s in ("", "e", "&", "a")][: self.steps_per_bar]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        keys = {"bpm", "beats_per_bar", "downbeat", "beat_unit", "steps_per_beat", "lead_in_bars"}
        g = cls(**{k: v for k, v in d.items() if k in keys})
        if g.pad_s < -1e-9:
            raise ValueError(
                f"grid.downbeat ({g.downbeat:.3f}s) is more than lead_in_bars={g.lead_in_bars} bar(s) "
                f"({g.lead_in_bars * g.bar:.3f}s) into the file: move song bar 1 earlier by whole bars "
                "or raise lead_in_bars")
        return g
