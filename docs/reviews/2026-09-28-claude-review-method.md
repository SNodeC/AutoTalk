# Claude re-review: provenance and verification

The owner requested committing/pushing the current work, then repeating the deep
Claude review across all dimensions. Preflight found a clean working tree: the
implementation was already committed as
[`88351b828d694e68ac48816b16e3e22e67d4e047`](https://github.com/SNodeC/AutoTalk/commit/88351b828d694e68ac48816b16e3e22e67d4e047).
`git push origin HEAD` reported Everything up-to-date; the remote branch hash was
also checked. No empty snapshot commit was created.

Branch: [review/claude-ui-ux-2026-09-27](https://github.com/SNodeC/AutoTalk/tree/review/claude-ui-ux-2026-09-27).
The review documents and synthetic screenshots were added afterward; production
source remained at the reviewed commit throughout.

## Reviewer and instructions

Installed authenticated **Claude Code 2.1.276**, using its configured default
**claude-sonnet-5**, authored the [verdict](2026-09-28-claude-verdict.md).
Session: `297fbf94-3935-47f0-b96b-ce934f924a9a`.
Codex supplied the brief, checked evidence attribution and recorded the output.
This is an informed code/usability review, not a blinded study or a test with
recruited ordinary users.

The repository records the exact prompts:

- [Initial brief](2026-09-28-claude-review-brief.md): all product requirements,
  full review dimensions, recent changes, evidence, known limits and isolation.
- [Coverage/evidence follow-up](2026-09-28-claude-review-followup.md): corrected
  overclaimed test/screenshot evidence; requested the complete placement table,
  deeper source review and deterministic cancellation/Realtime probes.
- [Final factual check](2026-09-28-claude-review-final-check.md): requested tracing
  staging symlinks through package collection, correcting probe-attempt attribution
  and distinguishing atomic save replacement from power-loss durability.

The follow-ups are coordinator requests, not additional product requirements.
Claude's final response is preserved verbatim. Recommendations remain review
findings; no fixes were performed during this review.

CLI invocation (follow-ups use the same flags plus `--resume`):

```sh
claude --safe-mode -p --permission-mode dontAsk \
  --tools 'Read,Glob,Grep,Bash' --allowedTools 'Read,Glob,Grep,Bash' \
  --output-format stream-json --verbose \
  < docs/reviews/2026-09-28-claude-review-brief.md
```

Safe mode disables custom hooks/plugins/MCP and project customizations. The brief
forbids production changes, Git mutations, credential inspection, user-project or
preference changes, live GPU/Codex requests, downloads, portal prompts, and changes
to running user processes or shared binaries. Synthetic probes used isolated
absolute XDG paths and throwaway projects. Raw transcripts, initial drafts and
probe logs remain in ignored `artifacts/claude-review-2026-09-28/`; diagnostic
scripts are under `/tmp/autotalk-claude-review-2026-09-28/`.

## Executed verification

These commands were executed by Claude, rather than merely cited from earlier
implementation reports:

```sh
QT_QPA_PLATFORM=xcb xvfb-run -a .venv/bin/python -m pytest -q -o faulthandler_timeout=30

PYTHONPATH="$PWD/artifacts/open-tasks/package-source/build/system-qt:$PWD/src" \
LD_LIBRARY_PATH="$PWD/artifacts/open-tasks/package-source/build/system-qt/PySide6/Qt/lib" \
QT_QPA_PLATFORM=xcb xvfb-run -a artifacts/open-tasks/venv-qt610/bin/python \
  -m pytest -q -o faulthandler_timeout=30
```

| Check | Result / evidence scope |
|---|---|
| Full standard Qt 6.11.2 suite | 349 passed in 76.32 seconds, no skips |
| Full native Qt 6.10.2/Breeze suite | 349 passed in 93.95 seconds, no skips |
| Native verdict tests with fresh screenshot capture | 13 passed, 2 deselected in 8.32 seconds; the two deselected tests had already run in both full suites |
| Newly authored Prepared stop/restart probe | Cached synthetic audio; Escape, End, controls restored, second Start enters presentation |
| Newly authored Quick and Realtime primary-button probes | One visible primary button in each mode |
| Newly authored preparation-cancellation probe | Synthetic narration client polls actual cancellation; mode, Start and text controls usable afterward; does not actually click a second Start |
| Newly authored Realtime stop/restart probe | Real workflow/PCM handling with deterministic external substitutes; later-slide work held open while opening audio plays; End restores editing; second Start accepted as a job or presentation |
| Final consolidated run of those five probes | 5 passed in 2.10 seconds |

The Realtime probe required test-setup corrections before it reached the intended
state. Failed attempts are retained in raw transcripts and discussed in the final
verdict. Passing the corrected probe does not establish live service cancellation
latency or completed second playback. The synthetic narration gate is explicitly
released by the test after End. The existing suite's SIGINT test ran; Claude did
not author an additional SIGINT test.

The native command depends on matching local build artifacts/interpreter versions;
it is not a portable fresh-install command. Root `.venv` uses Qt/Shiboken 6.11.2;
`venv-qt610` matches the staged native bindings. Mixing these environments is invalid.

## Visual evidence

The existing acceptance-test capture mechanism produced **46 synthetic PNGs**,
covering three modes, all seven menus and settings pages at minimum/normal sizes.
Claude individually opened **six** of those new images, **five** previously
committed images and **three** derived crops: 11 originals plus 3 crops. It did
not individually inspect all 46 generated images. The preserved directory contains
those 46 originals and the one crop remaining after Claude's cleanup.

[Archived evidence](evidence/2026-09-28-rereview/) contains only synthetic slide
content. Selected directly inspected images:

- [Minimum-size editor](evidence/2026-09-28-rereview/940-Prepared.png)
- [File menu](evidence/2026-09-28-rereview/940-menu-File.png)
- [Talk menu](evidence/2026-09-28-rereview/940-menu-Talk.png)
- [Settings menu](evidence/2026-09-28-rereview/940-menu-Settings.png)
- [Talk settings](evidence/2026-09-28-rereview/940-scope-1-page-1.png)
- [Expanded disclosure](evidence/2026-09-28-rereview/disclosure-expanded.png)
- [After-slide clipping crop](evidence/2026-09-28-rereview/crop_afterslide2.png)

Paths in Claude's verbatim verdict refer to the original local probe directory;
the same screenshot basenames are archived above. Widget grabs do not capture
window-manager title bars. Titles were checked from source and executed tests,
not visually read from those grabs. Dark/150%-scale inspection used historical
screenshots; no new full dark/scale matrix was run by this reviewer.

## Interpretation and limits

The complete placement table is a reviewer assessment from source and sampled
visual/interaction evidence, not a measured ordinary-user study. Click counts
are estimates and depend on dialog page memory, menus, tab selection and the
precise control being reached; grouped rows are not exhaustive event traces.
The owner still controls product decisions and any implementation approval.

No new live GPU/Codex startup benchmark, GPU-retention measurement or Wayland
portal recording was performed. The 93.91-to-61.68-second timing comparison is
historical evidence from the implementation report; the 15–20-second Realtime
target remains unmet in those measured runs. The latest portal recording recheck
remains unverified. Windows/macOS execution and QEMU remain deferred.

Review activity changed **0 production lines and 0 application test lines**.
Only review documentation and synthetic visual evidence are committed. Temporary
review probes are separate diagnostic artifacts, not changes to the regression suite.

The final factual check retracted F15: staging symlinks are consumed by package
collection; shipped Qt plugins/translations are regular bundled files. That draft
claim must not be treated as an outstanding defect. F14 remains explicitly a
design observation, not a reproduced file-descriptor leak.

Final verdict SHA-256: `4dcbc64c6a8c4dbe9a5c99b28604af89ac04b9c60d034be603ca6e826f95e068`.
