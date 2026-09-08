# Voice control: the SAPI 5.4 spike (abandoned 2026-08-24)

A full hands-free implementation (Ref 19) against Windows SAPI 5.4's classic
in-process recognizer (`SAPI.SpInprocRecognizer`, driven via `pywin32`'s
`win32com.client` automation bindings) was built and live-tested on the user's
machine (Windows 11, build 26200), then abandoned in favour of a Vosk-based
rewrite (tasks.txt L1).

**Why it was abandoned:** not for lack of effort. Once every plumbing bug below
was fixed, the engine's own accuracy was still inconsistent for this app's
small, closed command vocabulary — "stop"/"pause"/"back" recognized reliably
(~90%+ confidence), "play"/"preview"/others frequently not recognized at all.

The code is preserved, uncommitted-to-`main`, on branch `feature/voice-control`
(see that branch's own preservation commit) purely for reference. **None of it
should be revived as-is.** The findings below are real and would resurface for
anyone attempting classic SAPI again.

## Engine and device findings

- **SAPI's `AudioInput` device-token registry category does not exist on this
  Windows build.** `HKLM\SOFTWARE\Microsoft\Speech\AudioInput\Tokens` — the
  MSDN-documented way to enumerate/select microphones for automation — is
  absent; `SpObjectTokenCategory.SetId` fails with `SPERR_NOT_FOUND`
  (0x8004503A). The legacy "Windows Speech Recognition" microphone-setup wizard
  that used to populate it has been removed, replaced by the architecturally
  separate "Voice Access" feature, and running that replacement doesn't
  repopulate the old hive. Real per-device names ARE obtainable regardless, via
  the classic `winmm` `waveInGetNumDevs`/`waveInGetDevCapsW` API (`ctypes`,
  stdlib only) — confirmed working, surfaced the real hardware (a Realtek
  onboard mic, a Behringer USB interface) SAPI's own token category couldn't
  see.

- **`SpInprocRecognizer` has NO audio input wired by default** — unlike what most
  SAPI automation examples (which target `SpSharedRecognizer`, tied into the OS's
  own shared recognition service) imply. It constructs fine, loads a grammar
  fine, and reports its own `.State` as Active, but delivers zero
  `OnSoundStart`/`OnHypothesis`/`OnRecognition`/`OnFalseRecognition` events until
  `recognizer.AudioInputStream` is explicitly assigned a `SAPI.SpMMAudioIn`
  object, **before** `CreateRecoContext()` is called. Confirmed by adding
  sound/hypothesis event instrumentation during debugging.

- **`SpMMAudioIn.DeviceId` cannot be set to anything other than its own default**
  (-1, the classic MME `WAVE_MAPPER` convention) on this machine — assigning ANY
  other value throws `SPERR_ALREADY_INITIALIZED` (0x80045002), reproduced in
  complete isolation (a bare `Dispatch("SAPI.SpMMAudioIn"); .DeviceId = 0` in a
  fresh script/process, no Qt, no other app code, fails identically). Per-device
  selection from within an app is therefore unreliable via classic SAPI; the only
  reliable lever is changing the OS-level default recording device.

## `win32com` marshaling findings (not SAPI-specific)

- **`ISpeechRecoGrammar.CmdLoadFromMemory(GrammarData, LoadOption)` reliably fails
  with `E_INVALIDARG`** (0x80070057) through `win32com`'s dynamic dispatch,
  regardless of grammar content, `LANGID`, engine token, or whether the XML is
  passed as `str` or `bytes` — even though MSDN documents `GrammarData` as
  accepting the grammar XML directly as a string. `CmdLoadFromFile` against the
  identical XML written to a real temp file succeeds immediately. Looks like a
  `win32com` VARIANT-marshaling quirk specific to that one method's
  dynamically-generated wrapper.

- **Event-callback parameters arrive as a generic late-bound `IDispatch`**, not
  the specific typed interface — accessing `OnRecognition`'s `Result.PhraseInfo`
  directly raises `AttributeError: 'PyIDispatch' object has no attribute
  'PhraseInfo'`, even though the identical property works fine on an object
  returned directly from a `Dispatch()`'d method call.
  `win32com.client.CastTo(result, "ISpeechRecoResult")` resolves it. A general
  `win32com` event-dispatch characteristic, worth remembering for any future COM
  event-sink work in this codebase.

## Debugging methodology worth keeping

- A `pywin32` COM exception's real Win32/HRESULT code is buried in the exception
  args tuple and prints as a large negative int — `hex(value & 0xFFFFFFFF)`
  recovers the actual documented HRESULT to look up.
- Small, disposable standalone scripts that `Dispatch()` the same COM objects
  directly (run via `python scratch_script.py`, never `python -c`) were far faster
  at isolating which single call was failing than reasoning about the app's own
  multi-layer wrapping. The pytest harness can't touch real COM/audio at all by
  design, so live throwaway scripting is the only way to verify COM behaviour
  empirically.

## Not attempted

`Windows.Media.SpeechRecognition` (the WinRT API, the other originally-considered
option — see the Product Definition Document) was ruled out ahead of time in
favour of Vosk: its async-only (`IAsyncOperation`) API shape needs a materially
different threading model than the COM-message-pump approach above, the `winrt`
Python projection is less mature than `pywin32`, microphone-permission behaviour
for an unpackaged desktop Python app under Windows' privacy model was
unconfirmed, and it shares underlying plumbing with the same "Voice Access" stack
that already showed real gaps on this machine.
