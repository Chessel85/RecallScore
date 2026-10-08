# RSBV Phase 0 spike findings

Plan: `UserPlans/RSBVProofOfConcept.md`, Phase 0. These are go/no-go checks run
before any Phase 1 work. The spike pages are throwaway code in `web/spikes/`.

## How to run the spikes

From the repo root:

```powershell
.venv\Scripts\python.exe tools\stage_web.py --scores --serve 8000
```

Then open `http://127.0.0.1:8000/spikes/` in the browser under test. Each page
ends with a Copy report button; paste each report into the matching section
below and add what you heard.

* `--scores` copies the local MusicXML corpus into the staged site. It is for
  local testing only and never goes into a public deploy.
* Spike 4 needs a General MIDI SoundFont. Put the candidates (TimGM6mb,
  GeneralUser GS) in `web/sf/` and restage. They then appear in the page's
  SoundFont list. You can also load one with the page's file picker. Note that
  `web/sf/*.sf2` is not yet gitignored or committed; decide that in Phase 1.
* For a true first-visit time, use a private window. Otherwise later loads
  come from the browser cache.

## Automated smoke run (headless Chrome 154, this dev machine)

Claude drove every page in headless Chrome to check that the pages work. These
numbers are a baseline for the plumbing. They are **not** the screen reader
results, which only a real person can produce.

### Spike 1: Pyodide and the shared code. Works.

* Pyodide 314.0.7 from jsDelivr, cold cache: about 10 s from opening the page
  to ready. Loader 2.6 s, `loadPyodide` 6.7 s, shared code zip 0.1 s
  (274 KB, 83 files), importing the MusicXML path 0.7 s.
* All 97 MusicXML files in `files/`, `examples/` and `tests/fixtures/` parse
  with **0 failures** (the whole corpus took about 7 to 9 s).
* The largest scores take 1.2 to 1.6 s to parse (Chopin Op. 25 No. 12,
  1317 positions: 1.26 s; Blue Danube: 1.25 s). That is about 10 times the
  desktop CPython time (Blue Danube: 142 ms).
* **A Right Arrow step** (move, then render Regions 3 and 6, including the
  JS to Python round trip and JSON) took a 1.2 to 2.2 ms median, a 95th
  percentile under 4 ms and a max of 5.5 ms over 200 steps. That is well
  inside Ref 9's 25 ms budget, so Python is not the latency problem.
* music21 was stubbed out (`web/spikes/music21_stub.py`). With the stub,
  `MusicXMLReader.load()` takes its existing ElementTree fallbacks for key,
  time and tempo, and chord symbols return the root name with no pitches.
  The same stub was checked on desktop CPython, where all 93 local files load.
  This confirms the Phase 1 refactor plan: making the two harmony imports
  function-local is enough to cut music21 out.

### Spike 4: audio plumbing. Works; the numbers need real hardware.

* js-synthesizer 1.13.0 with libfluidsynth 2.4.6 in an AudioWorklet. The
  synth was ready in about 0.3 s. `recall_score_sounds.sf2` loads in about
  25 ms. `midiProgramSelect` against an explicit SoundFont id works, so the
  desktop's "app sounds on their own SoundFont" approach carries over.
* The FluidSynth sequencer can be created inside the worklet
  (`createSequencer` and `registerSynthesizer`), and notes scheduled ahead by
  tick were accepted.
* The headless audio device reported a 10 ms base latency and a 40 ms
  output latency (an estimated 53 ms key to sound). That is a fake device:
  **ignore it** and use the real-hardware figures below.

### Spike 5: music21 through micropip. Works, but heavy.

* `micropip.install("music21")` installed music21 10.5.0 and about 20
  dependencies, including numpy and matplotlib. This took **about 10 s**
  (cold).
* `from music21 import harmony` took **about 9 s**. The first `ChordSymbol`
  took 62 ms (Am7 gave the correct MIDI pitches 45, 48, 52, 55). The real
  timeline builder then resolved all 3 chords in `chords_and_lyrics`.
* The JS heap was about 170 MB afterwards.
* **Claude's read:** about 19 s extra the first time a chord-symbol score is
  opened is too slow for the POC. Two options: (a) the plan's fallback, which
  shows the chord name, plays no sound for it, and has Region 3 say so; or
  (b) a later, separate decision to add a small pure-Python table of chord
  kind to intervals so chords sound without music21. Option (b) changes
  desktop parser behaviour, so it needs its own plan and the fingerprint gate.
  This is the user's call.

### Spikes 2 and 3: the pages load and react to keys. No findings yet.

Neither spike means anything without a screen reader. Headless Chrome only
confirmed that a captured key is announced ("reached: Control L") and that the
announcement queue delivers.

## Manual results (NVDA 2026.2, Chrome 154 and Firefox 157; JAWS not yet run)

### Spike 1: first load on the tester's machine

On Chrome on loading Blue Danue.mxl:
Browser: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 | ariaNotify: yes | date: 2026-10-08T14:01:27.696Z
Pyodide 314.0.7
Load: fetch loader 5 ms, loadPyodide 1265 ms, shared code 40 ms (274 KB zip), import MusicXML path 184 ms, music21 stub yes
Page open to ready: 1524 ms
Parsed the-blue-danube-waltz.mxl: 568 positions, 8 parts, Python 605 ms, round trip 609 ms

On Firefox:
Browser: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0 | ariaNotify: yes | date: 2026-10-08T14:08:19.665Z
Pyodide 314.0.7
Load: fetch loader 90 ms, loadPyodide 2102 ms, shared code 31 ms (274 KB zip), import MusicXML path 210 ms, music21 stub yes
Page open to ready: 2445 ms
Parsed the-blue-danube-waltz.mxl: 568 positions, 8 parts, Python 726 ms, round trip 730 ms



### Spike 2: key capture

NVDA + Chrome:

Browser: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 | ariaNotify: yes | date: 2026-10-08T14:20:46.851Z
Key | listbox | tree | application
Space | yes | no | yes
Ctrl+Space | yes | no | yes
Ctrl+Alt+Space | yes | no | yes
Pause | no | no | no
Ctrl+L | yes | no | no
Ctrl+B | yes | no | yes
Ctrl+M | yes | no | yes
Ctrl+G | no | no | no
Ctrl+P | no | no | yes
Ctrl+R | yes | no | yes
Ctrl+H | yes | no | yes
Ctrl+O | yes | no | yes
Ctrl+F | yes | no | yes
Ctrl+A | yes | no | yes
Alt+Left | yes | no | yes
Alt+Right | yes | no | yes
F10 | yes | yes | yes
Alt | yes | yes | yes
Shift+F10 | yes | yes | yes
ContextMenu | no | no | no
F1 | yes | yes | yes
Z | yes | no | yes
X | yes | no | yes
C | yes | no | yes
V | yes | no | yes
B | yes | no | yes
N | no | no | no
Left | yes | yes | yes
Right | yes | yes | yes
Up | yes | yes | yes
Down | yes | yes | yes
Ctrl+Left | yes | yes | yes
Ctrl+Right | yes | yes | yes
Ctrl+Home | yes | yes | yes
Ctrl+End | yes | yes | yes
Tab | yes | yes | yes
Shift+Tab | no | yes | no
Escape | no | no | no
Other keys received: Alt+F10 in listbox, Ctrl+Down in listbox, Ctrl+Up in listbox
Screen reader and version: NVDA 2026.2

NVDA + Firefox:

Browser: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0 | ariaNotify: yes | date: 2026-10-08T14:23:54.734Z
Key | listbox | tree | application
Space | yes | yes | yes
Ctrl+Space | yes | yes | yes
Ctrl+Alt+Space | yes | yes | yes
Pause | no | no | no
Ctrl+L | yes | yes | yes
Ctrl+B | yes | yes | yes
Ctrl+M | yes | yes | yes
Ctrl+G | yes | yes | yes
Ctrl+P | yes | yes | yes
Ctrl+R | yes | no | yes
Ctrl+H | yes | yes | yes
Ctrl+O | yes | yes | yes
Ctrl+F | no | no | no
Ctrl+A | yes | yes | yes
Alt+Left | yes | yes | yes
Alt+Right | yes | yes | yes
F10 | no | no | yes
Alt | yes | yes | yes
Shift+F10 | yes | yes | yes
ContextMenu | no | no | no
F1 | no | no | no
Z | yes | yes | yes
X | yes | yes | yes
C | yes | yes | yes
V | yes | yes | yes
B | yes | yes | yes
N | no | no | no
Left | yes | yes | yes
Right | yes | yes | yes
Up | yes | yes | yes
Down | yes | yes | yes
Ctrl+Left | yes | yes | yes
Ctrl+Right | yes | yes | yes
Ctrl+Home | yes | yes | yes
Ctrl+End | yes | yes | yes
Tab | yes | yes | yes
Shift+Tab | no | yes | yes
Escape | no | no | no
Screen reader and version: NVDA 2026.2

JAWS + Chrome (JAWS tester):

Keys lost, and the proposed replacements:

Apparent losses in the tables are mostly keys the tester did not press from the
to-do list. Confirmed by the tester: Ctrl+key and bare letters always work;
Tab and Shift+Tab moved focus in every case; Escape leaves NVDA focus mode (so
the page never sees it); the context menu key opened the browser menu in
Firefox but not in Chrome. No replacements needed yet; Escape and Pause must
not be bound.

Menu bar decision (F10/Alt captured, or a Menu button first in the Tab cycle):
DECIDED: a Menu button first in the Tab cycle. F10 and Alt are left to the browser.

### Spike 3: announcements

NVDA + Chrome:
With area notify.
Once. Fine.
Repeat. Fine.
Five quick all at once. Just 1 and 2 heard.
Through the queue. All 5 heard.
Polite assertive. Heard both.

List. hear list including bar line.

Two alternating live regions.
Once. Fine.
Repeat. Fine.
5 quick. Just 5 heard.
Queue. All 5 heard.
Urgent then polite. Heard both.
List. hear the list including bar line.

One live region.
Once. fine.
Repeat. heard only one.
5 quick. just heard '5'.
Queue: heard all 5.
Polite and assertive. Did not hear both.
List. hear list but not bar line.

NVDA and Firefox.
Area notify.
Once. fine.
Twice. fine.
Five quick. just '1' and '2'.
Queue. all 5 heard.
Urgent then polite. heard both.
List. can get into list and hear the contents with up and down. including bar line 

Alternating.
Once. fine.
Repeat. fine.
5 quick. just hear '5'.
Queue. hear all 5.
Urgent and polite. hear both.
list. hear list including bar line.

One live region.
Once. fine.
repeat. fine.
5 quick. hear just '5'.
queue. hear all 5.
urgent then polite. just hear 'playing'.
list. hear list including bar line.



### Spike 4: audio on real hardware

Latency report (Chrome, interactive):

Browser: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 | ariaNotify: yes | date: 2026-10-08T14:55:43.793Z
Synth ready in 52 ms (latency setting: interactive)
Instrument SoundFont TimGM6mb.sf2: 5.7 MB, loaded into the synth in 23 ms (download time not included)
App sounds SoundFont loaded in 12 ms
Background test A (page timer): hidden for 0 ms of the run. 47 notes. Worst lateness: visible 6 ms, hidden 0 ms; 0 notes more than 30 ms late while hidden.
Background test B (FluidSynth sequencer): hidden for 0 ms of the run. 58 notes scheduled. Longest gap between refills: visible 507 ms, hidden 0 ms (a gap over 3000 ms would starve the sequencer); 0 underruns.
AudioContext: 48000 Hz, baseLatency 10.0 ms, outputLatency 40.0 ms, render quantum 2.7 ms
Audition: 68 key presses, key event to note-on sent median 0.5 ms. Estimated key-to-sound: 53.2 ms (handler + one render quantum + base + output latency; excludes the audio driver and speakers).
By ear (fill in): audition feels instant? / SoundFont quality / background playback even?

The general user sfz sounded nicer than the tim sfz but that is nothing to do with the browser.
All tests were fine.  What latency there was, was barely noticeable on both sound fonts.
And tabbing away caused no problems.

Firefox.
Browser: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0 | ariaNotify: yes | date: 2026-10-08T14:59:14.322Z
Synth ready in 169 ms (latency setting: interactive)
Instrument SoundFont GeneralUser-GS.sf2: 30.8 MB, loaded into the synth in 126 ms (download time not included)
App sounds SoundFont loaded in 12 ms
Background test A (page timer): hidden for 0 ms of the run. 47 notes. Worst lateness: visible 30 ms, hidden 0 ms; 0 notes more than 30 ms late while hidden.
Background test B (FluidSynth sequencer): hidden for 0 ms of the run. 44 notes scheduled. Longest gap between refills: visible 523 ms, hidden 0 ms (a gap over 3000 ms would starve the sequencer); 0 underruns.
AudioContext: 48000 Hz, baseLatency 0.0 ms, outputLatency 39.5 ms, render quantum 2.7 ms
Audition: 13 key presses, key event to note-on sent median 11.0 ms. Estimated key-to-sound: 53.1 ms (handler + one render quantum + base + output latency; excludes the audio driver and speakers).
By ear (fill in): audition feels instant? / SoundFont quality / background playback even?
Again, same as Chrome. No problems.



### Spike 5: decision on chord symbols

Chrome.
Browser: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 | ariaNotify: yes | date: 2026-10-08T15:00:41.948Z
Pyodide 314.0.7 loaded in 1264 ms
micropip.install("music21"): 5056 ms (download plus install)
Import music21.harmony: 2893 ms
First ChordSymbol: Am7: [45, 48, 52, 55], 28 ms
chords_and_lyrics fixture via the real timeline builder: 353 ms, 3 chord notes, 3 with pitches
Memory: 171 MB JS heap

Firefox.
Browser: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0 | ariaNotify: yes | date: 2026-10-08T15:01:15.322Z
Pyodide 314.0.7 loaded in 1454 ms
micropip.install("music21"): 4816 ms (download plus install)
Import music21.harmony: 4376 ms
First ChordSymbol: Am7: [45, 48, 52, 55], 17 ms
chords_and_lyrics fixture via the real timeline builder: 324 ms, 3 chord notes, 3 with pitches
Memory: heap size not reported by this browser

## Go / no-go

Decision (2026-10-08, user): GO.

* Latency: about 53 ms estimated key-to-sound is acceptable for the web version.
* Chord symbols: do not ship music21 in the browser for chords alone (about 5 s
  install plus 3 to 4 s import). Extract the chord data from music21 ahead of
  time, or source it elsewhere.
* Announcements: use the queue, never rapid direct announcements.
* Menu bar: a Menu button first in the Tab cycle (decided).
* Tab-away audio: verified by ear by the tester (no issues); the report counter showed 0 ms hidden, so it is not machine-confirmed.
* Open: JAWS run.

### Conclusions for the Phase 1 design

Everything below is drawn from the manual results above plus the tester's notes.
Where it differs from `UserPlans/RSBVProofOfConcept.md`, this file wins.

Key capture (spike 2):
* The tables have gaps because the tester did not press every key on the to-do
  list. A "no" means "not received", not "swallowed". Do not treat any "no" as a
  proven loss without re-pressing it.
* Confirmed working in focus mode: every Ctrl+key tested, every bare letter
  (Z/X/C/V/B and the other letters), arrows, Ctrl+arrows, Ctrl+Home/End, Tab and
  Shift+Tab (both moved focus in every case), Alt+Left/Right.
* Escape leaves NVDA focus mode, so the page never receives it in browse
  transitions. Do not bind Escape for anything essential. Pause was never
  received in either browser; treat it as unavailable until retested.
* The ContextMenu key opened the browser context menu in Firefox but not in
  Chrome. Shift+F10 reached the page in both. Use Shift+F10 as the documented
  key for the Region 4 scope menu, and handle ContextMenu where it arrives.
* F10 and Alt: unreliable across browsers (Firefox F10 reached only the
  application widget). Hence the Menu button.
* The `application` role widget received the most keys in Chrome and the tree
  the fewest, but those tree gaps are mostly untested keys. Region 2 as a
  `role="tree"` should be re-verified in the real app, not rejected on this data.
* Screen reader tested: NVDA 2026.2 with Chrome 154 and Firefox 157. JAWS not
  yet run.

Announcements (spike 3), same result in Chrome and Firefox:
* `ariaNotify` is available in both Chrome 154 and Firefox 157 (the reports say
  `ariaNotify: yes`), so the plan's statement that Firefox must use live regions
  is out of date. Still build the live-region path fully, for Safari and others.
* A single live region is the weakest: a repeated message is dropped, five rapid
  messages leave only the last, and an urgent-then-polite pair is not both heard
  (Firefox: only "playing" heard). Do not use one region.
* Direct `ariaNotify` and the two alternating regions both handle once, repeat,
  and urgent-then-polite. Rapid-fire direct calls lose messages (`ariaNotify`
  keeps the first two, alternating regions keep the last).
* Feeding messages through a queue delivered all five every time, in every mode.
  The announcer must always go through a queue.
* The bar line indicator was heard in the list case with `ariaNotify` and with
  alternating regions, but not with a single live region.

Audio (spike 4), real hardware, NVDA user:
* Estimated key-to-sound is about 53 ms in both browsers, mostly the 40 ms
  output latency of the device. The handler cost is 0.5 ms (Chrome) and 11 ms
  (Firefox). The tester judged this acceptable, which supersedes the 25 ms
  figure of Ref 9 for the web version; record it as a known deviation.
* Both candidate SoundFonts work. The tester preferred GeneralUser GS (30.8 MB,
  loaded in 126 ms) by ear over TimGM6mb (5.7 MB). Choosing between download
  size and quality is a Phase 1 decision.
* Playback was even and nothing went wrong when tabbing away, judged by ear. The
  report counters read 0 ms hidden, so the page did not register the hidden
  state; the ear test is the only evidence.

Load and chords (spikes 1 and 5):
* Real-machine first load: ready in 1.5 s (Chrome) and 2.4 s (Firefox) with a
  warm CDN. Largest-score parse: Blue Danube, 568 positions, 8 parts, 0.6 to
  0.7 s. Smoke-run figures above are slower because they were cold-cache.
* music21 from micropip works but costs about 8 to 9 s on real machines (5 s
  install plus 3 to 4 s import), and a 170 MB heap. The user decided against
  shipping it for chords. Chosen direction: obtain the chord kind-to-intervals
  data another way (extract it from music21 into a small pure-Python table, or
  source it elsewhere). That changes desktop parser behaviour, so it needs its
  own plan and the fingerprint gate. Until then the fallback applies: show the
  chord name, play no sound for it, and say so in Region 3.

Decisions already made: Menu button first in the Tab cycle; queue for all
announcements; go ahead with the build.

Open items: JAWS run (spikes 2 and 3); `web/sf/*.sf2` is neither gitignored nor
committed (decide in Phase 1; the files are 5.7 MB and 30.8 MB, under GitHub's
limit); the final SoundFont choice.
