# song.json: the answer key

`mavpa build` turns this file into the whole kit. `mavpa draft` writes a first version, and
you (or the agent) refine it. Bars are **song bars**: bar 1 is the first downbeat, and the kit
shows them as DAW bar = song bar + 1. A **step** is a 16th note, so a bar has
`beats_per_bar × 4` steps (12 in 3/4, 16 in 4/4).

```jsonc
{
  "mavpa": 1,
  "title": "Monkey Business",
  "source": "input/track.wav",                  // decoded audio (relative to the workspace)
  "stems": "work/stems/htdemucs_ft",            // drums/bass/other/vocals.wav
  "grid": {"bpm": 100.0, "beats_per_bar": 4, "beat_unit": 4, "downbeat": 0.25, "lead_in_bars": 1},
  "key": {"tonic": "A", "mode": "aeolian", "name": "A minor", "midi_key": "C",
          "summary": "White keys, A is home; the E chords borrow G#.",
          "readme": "A minor = white keys + G# on the E chords, home chord Am"},
  "bars": 40,                                   // last song bar
  "sections": [{"name": "Intro", "from": 1, "to": 4}, {"name": "Main A", "from": 5, "to": 20}],
  "marks": [{"bars": [16], "label": "drop-out (drums + bass out)", "strength": "soft"}],   // soft | hard
  "layers": [ /* see below */ ],
  "harmony": [ /* the loop table, see below */ ],
  "audio": [{"stem": "drums", "name": "01_drums"}, {"stem": "bass", "name": "02_bass_808"},
            {"stem": "other", "name": "03_music"}, {"stem": "vocals", "name": "04_vocals"}],
  "loops": [{"name": "loop8_bass", "layer": "bass", "from": 5, "bars": 8}],   // optional; default = one per pattern
  "guide": { /* lesson text, see lesson.md */ }
}
```

## Layers

A layer is one part. It becomes one MIDI track, one lane on the song map and one card.

```jsonc
{
  "id": "bass", "name": "sub bass",            // name -> MIDI file "02_sub_bass.mid"
  "role": "bass",                               // bass | harmony | pad | keys | lead | hook | pluck | vocal | fx | drums
  "stem": "bass",                               // which stem verify/overlay compare it with
  "program": 38,                                // General MIDI program (0-127), optional
  "color": "bass",                              // bass pad pad2 flick tick top spark vocal drums
  "patterns": {
    "loop":  {"bars": 8, "notes": {"1": [[0, 6, "A1", 100], [6, 2, "A1", 85], [8, 6, "A2", 100]],   // [step, length, note, velocity]
                                   "2": [[0, 16, "G1", 100]]}},
    "outro": {"bars": 4, "notes": {"1": [[0, 16, "A1", 70]]}}
  },
  "play": [                                     // where patterns run
    {"pattern": "loop", "from": 5, "to": 20, "anchor": 1, "except": [16]},
    {"pattern": "loop", "from": 21, "to": 36, "anchor": 21},      // a section that restarts the loop
    {"pattern": "outro", "from": 37, "to": 40, "anchor": 37, "velocity_offset": -20}
  ],
  "notes": {"4": [[14, 2, "E2", 90]]},          // one-off notes in song bars (fills, pickups)
  "card": { /* lesson card, see lesson.md */ }
}
```

`play` entry fields:
1. `pattern`: the pattern name.
2. `from` / `to` (inclusive), or `bars: [..]` for an explicit list of song bars.
3. `anchor`: a song bar where the pattern's bar 1 falls. It defaults to `from`. Pattern bar
   = `(bar − anchor) mod length + 1`.
4. `except: [..]`: bars to skip (drop-outs).
5. `only: [..]`: for drums, the instruments to keep (e.g. the shaker plays through a drop).
6. `velocity` (fixed), `velocity_offset`, `min_velocity`, and `transpose` (semitones, melodic layers).

Notes use scientific names (middle C = C4): `E1`, `F#3`, `Bb4`. Steps can be fractions for
swing or triplets (`2.67`).

### Drum layers

```jsonc
{
  "id": "drums", "name": "drums", "role": "drums", "stem": "drums", "drums": true,
  "kit": {"kick": {"note": 36, "label": "Kick"}, "snare": {"note": 38, "label": "Snare"},
          "hat": {"note": 42, "label": "Closed hat"}},
  "velocity": {"X": 110, "x": 90, "g": 60},     // accent / normal / ghost
  "patterns": {"loop": {"bars": 2, "grid": {
      "kick":  {"1": "X.....x.X.......", "2": "X.....x.X.....x."},
      "snare": {"1": "....X.......X...", "2": "....X.......X.xx"},
      "hat":   {"1": "x.x.x.x.x.x.x.x.", "2": "x.x.x.x.x.x.x.x."}}}},
  "play": [{"pattern": "loop", "from": 5, "to": 36, "anchor": 5}]
}
```

One character per step: `.` for a rest, `X`, `x` or `g` for a hit. GM drum notes: kick 36,
side stick 37, snare 38, clap 39, closed hat 42, pedal hat 44, open hat 46, crash 49,
ride 51, tambourine 54, shaker 70 (or 82). An Ableton Drum Rack starts at C1 = 36.

## Harmony (the loop table)

```jsonc
"harmony": [{
  "title": "The loop: bass + harmony",
  "bass":    {"layer": "bass", "pattern": "loop"},
  "voicing": {"layer": "pad",  "pattern": "loop"},
  "extras":  [{"layer": "lead", "pattern": "loop", "label": "hook"}],
  "chords":    ["Am", "Am/G", "Fmaj7", "E7", "Am", "C", "Dm7", "E"],
  "functions": ["i", "i/♭VII", "♭VImaj7", "V7", "i", "♭III", "iv7", "V"],
  "intro": "This is the skeleton of the song…",
  "rolls": [{"parts": [{"layer": "pad", "pattern": "loop"}, {"layer": "lead", "pattern": "loop"}],
             "lo": "D3", "hi": "F6", "bar_labels": "loop {k}"}],
  "callout": "Why it pulls home: …"
}]
```

The DAW bars for each loop bar are worked out from the voicing layer's `play` entries.

## Rolls (piano-roll pictures in the guide)

A roll is `{"parts": [{"layer", "pattern", "color"?, "label"?, "skip"?: {"1": ["B4"]}}], "lo", "hi", "bars"?, "cell"?, "row"?, "bar_labels": [..] | "loop {k}", "title"?}`.
For notes taken from the song itself rather than a pattern, use
`"from_song": {"from": 1, "to": 4}`.
