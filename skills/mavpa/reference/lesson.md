# Writing the lesson (guide.html)

The learner opens a DAW and freezes at the blank page. The lesson removes that fear one
layer at a time: **hear it, try it, check it, then make it sound right.**

Text goes into `song.json`. Anything you leave out is generated from the data. Markup:
`**bold**`, `*italic*`, `` `mono` ``, and note tokens `{{E4}}` or `{{E4 G4 B4}}` (or
`{{64}}`, a MIDI number). Note tokens follow the page's naming toggle (C4 scientific, C5 in
FL, C3 in Ableton/GarageBand), so **always** write notes as tokens. A pitch class without an
octave (`{{E}}`) is printed as is.

## `guide` block

```jsonc
"guide": {
  "title": "Song — how it is built, and how to rebuild it",
  "eyebrow": "Monkey kit · melodic decomposition · rebuild by hand",
  "lede": "One paragraph promise.",
  "chips": ["3/4 time", "103 BPM", "E Phrygian, white keys only", "8-bar loop", "145 bars · 4:14"],
  "lead_in": "count-in with the one-beat pickup on beat 3",     // README: what DAW bar 1 holds
  "dna": ["**It is a waltz: 3/4, not 4/4.** Count …", "…"],      // 4–6 facts, most surprising first
  "lanes": [{"layer": "pad", "patterns": ["loop"], "name": "Pad (loop)", "color": "pad"}],   // song map lanes (optional)
  "map_note": "The loop restarts at bar 70 …",                  // the copy-paste trap, if any
  "cards": [ … ],             // ordered cards; omit to get one per layer (layer.card)
  "cards_intro": "…", "method": ["…"], "plan": ["…"], "accuracy": ["…"], "footer": "…"
}
```

## A card

```jsonc
{
  "layer": "bass",                       // omit for free cards (FX notes, outro cadence)
  "title": "808 sub bass",
  "where": "stem 02 · bars 2–145 · out on 35, 44",
  "about": "What it is, its register ({{E1}}–{{F2}}), rhythm, and character (slides, late entries).",
  "monkey": [                            // ear-first, 3–6 steps, hints not answers
    "Solo `02_bass` and loop bars 10–17.",
    "Load a plain sine. For loop bar 1 try white keys in the lowest octave until one stops beating against the stem. Hint: it's the home note.",
    "Now the rhythm: does it start on beat 1? Bars 4 and 7 don't."
  ],
  "answer": {
    "summary": "Show the answer",
    "tables": [{"type": "notes", "pattern": "loop", "notes": {"4": "rest on beat 1"}},
               {"type": "voicing", "layer": "pad", "pattern": "loop", "chords": ["Em", "…"],
                "extra": {"layer": "flick", "pattern": "loop", "label": "+ flick"}}],
    "rolls": [{"parts": [{"layer": "bass", "pattern": "loop"}], "bar_labels": "loop {k}"}],
    "drums": {"layer": "drums", "pattern": "loop"},
    "text": "…", "note": "Reliability caveat in one sentence."
  },
  "recipes": {"fl": ["…"], "ableton": ["…"], "garageband": ["…"]},
  "sound": "One paragraph when a full recipe is overkill.",
  "list": ["for free cards: a plain numbered list"]
}
```

## Style

1. **Hints, not answers, in "Monkey it."** Give the learner a bar range, what to listen
   for, the register, and a constraint ("white keys only", "it never changes", "a
   half-step apart"). The answer goes in the `answer` block, which stays collapsed.
2. **Name the feel.** "Late entry on the &", "blooms after beat 1", "a sigh between E and
   F", "slides ~120 ms". Learners copy feel when it has a name.
3. **Use DAW bar numbers** in the text (song bar + 1). The guide's tables convert by
   themselves.
4. **Recipes use stock instruments,** with envelope numbers (attack, decay, release),
   filter cutoffs, mono/glide and effects in order. Cover FL Studio, Ableton Live and
   GarageBand (Alchemy, Sampler, Drum Machine Designer).
5. **Accuracy is honest.** Write it from `mavpa verify`. Tiers work well: **Exact /
   Very high / High / Good but simplified / Approximate**. Say what was left for the ear.
6. **The practice plan** is 4–6 sessions, each with a checkpoint ("your sine locks with
   the stem in every bar").
7. Keep a beginner in mind: one idea per sentence, no theory without a sound to attach
   it to, numbered lists everywhere.
