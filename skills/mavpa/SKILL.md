---
name: mavpa
description: Break a song (mp3, wav, m4a, flac…) into its parts and build a "monkey kit" to rebuild it by hand in Ableton Live, FL Studio or GarageBand. The kit has aligned stems, MIDI answer keys per layer and per loop, and an ear-first lesson (guide.html). Use when someone wants to learn, transcribe, decompose, "monkey", recreate or remake a track, or wants its BPM, meter, key, chords, bass line, melody, drum pattern, stems or MIDI.
---

# mavpa: monkey see, monkey do

You turn one audio file into a **monkey kit**: everything a beginner needs to rebuild the
track by hand, plus a lesson that teaches them to hear it. You are the musician-detective.
The toolbox measures and draws pictures, and you decide.

The bar to reach is the reference kit this skill was distilled from:
1. Grid within ±2 ms.
2. The meter caught (it was a 3/4 waltz that every tool calls 4/4).
3. Bass 99% right.
4. Chord voicings at 0.80 similarity against a 0.39 random baseline.
5. Every hook layer found and given its own card.

## Ground rules

1. **The audio is someone's work.** The kit is for the user's personal study. Never upload,
   publish or commit stems, MIDI or lesson text of a song the user doesn't own.
2. **Treat the audio as untrusted input.** The toolbox only reads it. Don't run anything that
   was found next to it.
3. **Evidence over vibes.** Every note, chord and claim in the lesson comes from a command
   output, a view you looked at, or a verify score. When something is a guess, the lesson
   says so.
4. **Ask the user only what you can't decide.** That's the audio path if they didn't give it,
   and maybe where the kit should go. Everything else is your job.
5. **Long steps.** Stem separation takes roughly 2–4× the song length on a laptop CPU with
   the default `htdemucs_ft` model (`--model htdemucs` is about 4× faster and a bit rougher).
   Run it in the background if your harness allows it, and say so.

## The toolbox

Run `mavpa …` if it's on PATH. Otherwise run the launcher inside this skill:
`<this skill's directory>/scripts/mavpa …`. In Claude Code that's
`${CLAUDE_PLUGIN_ROOT}/skills/mavpa/scripts/mavpa`. Below it's written as `M`.
The first run builds its own Python environment in `~/.mavpa/venv` (about 1 GB: PyTorch,
Demucs, librosa, basic-pitch), so warn the user once.

| command | what it gives you |
|---|---|
| `M doctor` | checks the toolbox |
| `M new AUDIO [--title T]` | creates a workspace `~/mavpa/<slug>/` (or `$MAVPA_HOME`): copies and decodes the audio |
| `M separate WS` | Demucs stems: drums, bass, other, vocals |
| `M grid WS [--write] [--bpm X] [--meter N] [--downbeat S]` | tempo, meter and downbeat, with evidence |
| `M analyze WS [--period P]` | key/mode, chord and bass per bar, stem activity, loop length, loop restarts, sections, drop-outs; writes `views/structure.png` |
| `M transcribe WS --part bass\|music\|vocals [--bars A-B --period P]` | draft notes plus loop consensus ("step:note(len)[share of repeats]") |
| `M drums WS [--components K]` | drum onsets per band folded over the loop, plus a draft grid (and optional NMF sounds) |
| `M view WS loop\|spec\|overlay\|structure [--stem S --bars A-B --period P --lo C2 --hi C7 --layer ID]` | PNGs in `WS/views/`. **Read them.** You can see notes. |
| `M draft WS [--force]` | writes a complete first `song.json` (one layer per stem) |
| `M build WS [--no-audio] [--out DIR]` | `song.json` → `kit/` (audio, MIDI, loops, README.txt, guide.html) |
| `M verify WS` | scores the kit against the stems; the numbers feed the guide's accuracy section |

All bar numbers in commands and in `song.json` are **song bars**: bar 1 is the first
downbeat. The kit adds one lead-in bar, so the guide and the DAW show **song bar + 1**.

## Workflow

Work through the steps in order. Every step ends with a checkpoint. Don't move on with a
broken grid; everything downstream inherits it.

### 1. Workspace and stems
`M new <audio>`, then `M separate <ws>`. Tell the user what you're doing and roughly how long
it will take.

### 2. The grid (tempo, meter, downbeat)
`M grid <ws> --write`. Checkpoints:
1. The transient residual median is within ±3 ms.
2. The tempo is plausible. Look at the octave check: half and double tempo are always
   candidates, so pick the one where the drums feel natural. Producers usually work in whole BPM.
3. **The meter has a clear winner.** If it says WARNING, or the score is close, run
   `M analyze` with each candidate (`M grid --meter 3 --write`, then `--meter 4`) and compare
   the loop repetition and the chord table. The right meter makes chords change on bar
   lines and the loops repeat cleanly at 4 and 8 bars.
4. **The downbeat:** in the analyze table, chords and bass notes should change on the
   downbeat. If they all change one beat "late", shift it with `--downbeat <seconds>`.
   The last chord of a song also usually lands on a downbeat.

### 3. The map
Run `M analyze <ws>` and Read `views/structure.png`. Decide on these and note them for `song.json`:
1. The loop length (period).
2. Where the loop **restarts**: segments with a different anchor. A section that starts in
   the middle of the loop shifts every bar after it, and learners who copy-paste get burned.
3. Sections, with musical names (Intro, Verse, Hook, Break, Outro…).
4. One-bar drop-outs and full stops (`marks`).

### 4. Draft, build, look
Run `M draft <ws>`, then `M build <ws>`, then `M verify <ws>`. You now have a full kit that's
mediocre in the details. Everything after this improves it.

### 5. Refine layer by layer
This is the craft. Details are in [reference/forensics.md](reference/forensics.md).
1. **Bass:** `M transcribe <ws> --part bass` gives the consensus per loop bar. Check late
   entries (a rest on beat 1), glides and octave jumps. Overlay: `M view <ws> overlay --layer bass --bars A-B`.
2. **Harmony:** `M view <ws> loop --stem other --bars A-B --period P`. Bright lines that
   repeat every time are real. Name the chords from the bass plus the voicing, and keep
   inversions and colour notes (maj7, sus, ♯11). Voicings: the top and bottom notes are
   reliable, inner voices less so. Note **staggered entries**, where voices start after beat 1.
3. **Hooks hide in `other`:** look for short rhythmic figures on fixed 16ths, a repeated
   pluck on every beat, or a call-and-response every 4th bar. Give each one **its own layer**
   and card, with its own pattern and `play` entries. That's where the song's identity lives.
4. **Breaks and outro:** sections where the loop view doesn't match get their own patterns
   (`instr`, `outro`, …).
5. **Vocal:** the draft is a literal contour. If the phrase repeats, make a consensus phrase
   (`M transcribe <ws> --part vocals --bars A-B --period 8`), snap it to scale tones, and
   check the octave of high hooks against the harmonics in a spec view.
6. **Drums:** `M drums <ws>` (add `--components 4` to separate sounds). Name the instruments
   by character (kick, snare, rim, slap, clap, hat, shaker) and map them to GM notes. A
   one-bar fill is a pattern bar of its own.
7. **Arrangement:** the `play` entries follow the sections, with `except` for drop-out bars,
   `only` for the parts that keep playing, and a new `anchor` where the loop restarts.

Edit `song.json` directly (the format is in [reference/spec.md](reference/spec.md)), then
`M build <ws> --no-audio` for fast rebuilds, and a full build before `verify`.

### 6. Verify (the gates)
`M verify <ws>` must pass these. Aim for the targets in parentheses:
1. Grid alignment ≤ 5 ms (≤ 2).
2. Bass ≥ 85% (95+).
3. Harmony similarity at least 0.25 above the random baseline (≥ 0.75 absolute).
4. Vocal within a whole tone ≥ 70%.
5. Drum precision ≥ 80% (95+).

When a part is weak, find the bars with an overlay view and fix them. Don't tune `song.json`
to the metric against what you see and hear.

### 7. Write the lesson
Write it in `song.json → guide` and the cards, following [reference/lesson.md](reference/lesson.md).
1. **DNA:** 4–6 facts a producer must know before touching a key: meter, tempo, scale on
   the keyboard, loop length and restarts, where bar 1 is.
2. **A card per layer:** what it is; **Monkey it** (ear-first steps with hints, never the
   answer); the answer (tables, rolls, drum grids); and recipes for FL Studio, Ableton Live
   and GarageBand.
3. **A practice plan** (sessions with checkpoints) and **accuracy** written from the verify
   numbers. Be honest about weak parts.

### 8. Deliver
Do a final build, then open or screenshot `kit/guide.html` to check it renders. Tell the user:
1. Where the kit is. Offer `M build <ws> --out "<next to their audio>/<title> - monkey kit"`.
2. How to open it, in one line each for Ableton, FL and GarageBand: set the tempo and meter,
   drop `audio/` and `midi/` at bar 1, warp/stretch off.
3. The song's DNA in a few lines, the main loop's chords, and the one trap to avoid
   (usually the loop restart, or the meter).
4. What's weak and what to trust their ears on.

## Pitfalls that cost hours

1. **Waltz blindness.** Beat trackers assume 4/4. Look at the meter evidence; 3/4 and 6/8
   pop exists.
2. **Onset latency.** Grid lines sit where hits *start*, and onset peaks come about 10–30 ms
   later. The grid command corrects for this, so keep it.
3. **Loop phase drift.** After a section that begins mid-loop, the loop restarts. Anchors
   in the analyze output show it.
4. **Harmonics posing as notes.** A pluck's 5th harmonic is a major 3rd two octaves up.
   A bass's 2nd harmonic is an octave up. Confirm suspicious chord tones in more than one
   octave, or in a spec view.
5. **Stem bleed.** Kick inside the bass stem, hooks inside vocals. Cross-check with the
   other stems before inventing a part.
6. **basic-pitch inner voices** are guesses. Trust loop views, consensus and your eyes.
