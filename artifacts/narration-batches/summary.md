# Incremental narration: Phase A and approved implementation

Prepared/Quick Start and Create talk text now share one plan-and-batch path, with
`NARRATION_BATCH_PAGES = 10`. The opening is saved first; later turns send text only
and use the plan's images already in the same thread. Each validated batch is saved
before its narration event. At most one next batch is prefetched. Resume uses the
existing text-ready state. Single-slide, Realtime-ahead and fit paths are preserved.

## Shortened Phase A

Same German project settings: gpt-6.1-sol, medium effort. Each planning call sent 93
images / 12,827,571 bytes. N25 was interrupted after planning at the owner's request;
the additional stream-parsing trace was omitted. No further size trials were run.

| N | Planning s | Three batch times s | First saved s | Estimated total 93 / 150 slides s |
|---|---:|---|---:|---:|
| 10 | 119.57 | 50.02 / 60.08 / 70.54 | 120.79 | 675 / 1,092 |
| 15 | 118.22 | 94.90 / 104.02 / 133.56 | 118.96 | 799 / 1,292 |

Estimates prorated batch time per page; the 150 estimate also scaled planning by
150/93. They were not full runs and assumed similar output per page. Phase A replies
validated and each completed batch retained planned budgets. Border spot checks
were coherent. N10's plan omitted pause allowance; N15's included it. N10 was chosen
for shorter durable checkpoints and the lower sample projection, not proven optimality.
Stream parsing could avoid extra turns, but still needs framing/validation/durable
publication and keeps the full-deck input risk. Its latency was not measured.

## Exactly one final real run

Fresh copied 93-slide German project, Prepared mode, production services.narrate()
(the Create talk text path). No speech, fit requests or other model runs.

- Planning: **125.28 s**, 93 images, **157,247 input tokens**, 475,000-token context.
- First saved narration: **125.94 s**, including client setup and save.
- Saved counts: **1, 11, 21, 31, 41, 51, 61, 71, 81, 91, 93**, read back from the manifest.
- Total: **743.69 s**, versus historical German **580.73 s** (+28.1%) and English
  **478.14 s** (+55.5%). This improves durable availability, not total generation speed.
- All 10 batch turns used **zero images**, in the planning thread. All batch budgets
  matched the plan. Last turn input was 212,890 tokens.

| Pages | Wall s | Images | Input tokens | Output tokens |
|---|---:|---:|---:|---:|
| 2–11 | 52.34 | 0 | 168,554 | 1,536 |
| 12–21 | 60.39 | 0 | 173,064 | 1,965 |
| 22–31 | 69.76 | 0 | 178,142 | 2,200 |
| 32–41 | 71.44 | 0 | 183,329 | 2,231 |
| 42–51 | 78.29 | 0 | 188,524 | 2,404 |
| 52–61 | 68.63 | 0 | 194,151 | 2,394 |
| 62–71 | 79.02 | 0 | 199,757 | 2,620 |
| 72–81 | 64.91 | 0 | 205,197 | 2,039 |
| 82–91 | 61.33 | 0 | 209,910 | 2,046 |
| 92–93 | 11.45 | 0 | 212,890 | 349 |

Latency was not flat: full batches rose from 52 to 79 s, then fell to 65 and 61 s.
Output length changed with the content; wall time per 1,000 output tokens stayed
roughly 29–34 s. This single run does not isolate a causal context slowdown. Omitting
images reduced input/history growth; it did not establish an overall speedup.

Two reviewed borders:

- **11→12:** “Als Nächstes ordnen wir diese Zahlen in einer Tabelle.” → “So stehen
  unsere Messwerte in einer Tabelle.” Coherent handoff from measurements to rows.
- **81→82:** “welche Fälle fehlen möglicherweise in unserer Bewertung?” → “welche
  relevanten Fälle unsere Daten überhaupt abdecken.” Coherent move into coverage/bias,
  with a short recap. These are bounded transition checks, not a full factual audit.

## Verification and limits

Ruff F checks passed for src and the changed test file. Host pytest: **584 passed,
15 audio-device tests deselected, 114.61 s**. Ten focused added cases cover the two
entry points, UI saved readiness, pipeline overlap, failure/invalid-batch/cancellation
recovery, missing-only resume, and unchanged small/fit calls.

Production: **+78 / −54 = +24 net lines**; tests: **+124 / −1 = +123 net lines**.
The shared generator replaces the old workflow loop; no second resume state was added.

Follow-ups: fit remains whole-deck; 150-page planning/context size is unmeasured.
The final plan allocated 5,400 s plus 55.2 s of pauses, exceeding the talk target;
aggregate-duration enforcement is an existing limitation, not added by batching.
The original app/project were not controlled or written by these runs; source audio
metadata changed independently during Phase A. The project copy was deleted after
verification and is not committed. Raw local traces remain under this directory;
only summary.md and results.json are committed. The packaged executable was not rebuilt.
