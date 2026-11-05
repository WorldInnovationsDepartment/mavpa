# Forensics: how to hear a mix with numbers

These techniques took a real track from "a 4/4 song at 103 BPM?" to a 3/4 waltz with a
99%-correct bass line. Use them in roughly this order.

## Grid

1. **Rigid-grid fit.** Modern productions sit on a fixed grid. Fit the BPM to 0.001 and
   the phase to 0.5 ms by maximising onset strength on the beats. `mavpa grid` does this.
   If the residual IQR is wider than about ±10 ms, the song may drift (a live band): say
   so, and pick sections to work in.
2. **Transient vs onset.** The onset-strength peak arrives 10–30 ms after a drum hit
   starts. DAW grid lines sit at the start, so shift the phase by the median residual.
   This is built in.
3. **Meter.** Fold harmonic change, bass change and kick onsets by beat position, mod 2, 3
   and 4. The real meter has one standout phase (the downbeat). Back it up with chroma
   repetition at 4- and 8-bar lags. A 3/4 song shows strong repetition at 12/24 beats and
   weak at 16/32.
4. **Downbeat.** Chords and bass change there. A song often starts with a pickup (a beat
   before bar 1) and ends on a downbeat, and the final hit is a good anchor.

## Map

1. **Bar self-similarity** (`views/structure.png`). Diagonal stripes are repeated loops,
   and their spacing is the loop length. A stripe that jumps sideways means the loop
   restarted.
2. **Loop anchors.** `mavpa analyze` matches every bar against one reference cycle at
   every phase and smooths the result. A change of phase is a restart, so the next section's
   `play` entry needs a new `anchor`.
3. **Stem activity** per bar gives you sections (which stems are on) and one-bar
   drop-outs (drums or bass out). Producers mute bars; they rarely write new parts.

## Notes

1. **Loop-synchronous averaging.** Average the CQT over every repeat of a P-bar loop
   (`mavpa view loop`). Things that repeat stay bright; vocals, noise and variations
   fade. It's the best single picture of a loop.
2. **Consensus transcription.** Keep a note at (loop bar, step, pitch) only if it shows
   up in at least half of the repeats. Use a per-step majority for monophonic parts
   (bass), and onset matching for polyphonic ones.
3. **Bass.** Use pYIN with a long frame (4096) for sub frequencies. Glides show up as
   one-step "blips" between notes, so absorb them. A late entry (resting on beat 1, coming
   in on the "&") is a feature to teach.
4. **Chords.** Match templates against the 'other' stem's chroma, add a bonus when the
   bass is the root, then keep inversions (`F/B`) and colours (maj7, sus2, ♯11) when the
   loop view supports them. Write function numerals relative to the tonic (i, ♭II, ♭VII).
5. **Key and mode.** Find the best 7-note collection, then the tonic inside it. Weigh the
   bass notes, the loop's first bar and the strongest triad. White keys with E as home is
   E Phrygian, not C major. Teach it as "white keys, E is home".
6. **Voicings.** The top and bottom voices are trustworthy; inner voices are a best
   match. Check for staggered entries (upper notes blooming after beat 1); they're a big
   part of the feel.
7. **Hooks hide in 'other'.** Look for fixed-step figures: something on every beat, a
   two-note sigh on the "&-a", a call-and-response every 4th bar. A sustained pitch that
   never changes across chords is a pedal (e.g. an A3 tick over Em, F and G).
8. **Harmonics.** A strong 5th harmonic (+28 semitones) looks like a major 3rd two
   octaves up, and the 3rd harmonic like a 5th an octave up. Before you add a chord tone,
   check whether a lower note explains it. Octave errors in vocals: compare the
   fundamental with the 2nd harmonic.
9. **Vocals.** Singers slide, so write target notes (where the syllable settles), not
   slides. Snap to scale tones. A guide that's 80–90% within a whole tone is a good contour.

## Drums

1. **Band folding.** Onset strength in the kick (30–150 Hz), snare (180–5000 Hz minus
   kick bleed) and hat (7–16 kHz) bands, averaged per (loop bar, step) over all repeats.
   An automatic split separates hits from nothing. Accents: X > x > g.
2. **NMF** (`--components 4`) learns sounds rather than bands, which helps with
   slaps/rims (body plus crack) and shakers.
3. Fills live in the last bar or two of a loop. Ghost notes and 808 movement are often
   left for the ear; say so in the lesson.

## Timbre (for the recipes)

1. **Attack:** how fast the envelope rises. Under 10 ms is a pluck or drum; 50–150 ms is a
   pad or strings.
2. **Decay/release:** how long a note rings after its end.
3. **Brightness:** where the harmonics stop (filter cutoff). A buzzy, hollow sound with
   odd harmonics is square-ish.
4. **Vibrato** about 5–6 Hz on strings or voices; chorus on pads.
5. Give patch recipes for stock instruments (FL: 3xOsc, FLEX, Sytrus; Ableton: Operator,
   Wavetable, Drift, Simpler; GarageBand: Alchemy, Sampler, Drummer/Drum Machine Designer),
   and say plainly that the real presets are unknown.
