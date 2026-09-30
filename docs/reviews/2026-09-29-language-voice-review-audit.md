# Final factual and architectural audit request

Return a concise final corrective addendum, at most 1500 words, explicitly
superseding the affected recommendations/claims in Revision 2. Do not repeat the
full verdict or implement changes. Original execution boundaries still apply.
No additional broad test campaign is needed. Inspect the relevant source as
needed, and distinguish recommendations from proved behavior.

The coordinator checked your verdict against the code and CLI trace:

1. Trace shows twelve screenshots generated but ONLY six Read calls: 03, 04,
   06, 08, 09, 11. Correct the repeated “all twelve opened” claim. The first
   pass's 21 tests were not rerun by you in the second pass. The coordinator
   separately ran 69 passing, 2 deselected under native Qt/Xvfb (versions,
   scoped_settings, settings_dialog, start_interaction); label them as mine.
   test_refinement.py::test_writing_next_slide_preserves_current_stream_buffer
   was READ by you, not run in either of your stated suites. Do not call it an
   executed passing test unless you actually execute it. “Only three untracked
   files” is also inaccurate; documentation was added during the review.
2. LV12 Option B knowingly leaves inherited text stale on mixed slides. The
   owner requires complete cause-level fixes, no workarounds, and never ranked
   override preservation above correctness. Withdraw that as a recommended fix.
   Consider retaining whole-slide pending translation while structurally
   preserving explicit portions during transformation, without a second
   readiness authority. If this requires additional code, say so honestly; do
   not force the existing line estimate to fit.
3. LV11's proposed untagged-only predicate still flags the EXACT reproduced
   French slide: it has untagged text plus an explicit slide override. The fix
   must compare resolved source/destination languages, not merely passage tags.
4. LV13's output.is_file shortcut does not prove a completed valid WAV; streaming
   and interrupted generations can leave partial files. It also does not restore
   the slide's duration/hash/provenance pointers. Withdraw the 2–4-line shortcut
   and state the actual completion/identity requirements, or defer optimization.
5. Pin-on-first-content changes inheritance semantics and does not fix existing
   populated inherited talks or “Use app” after content exists. Also consider a
   talk CLOSED when defaults change: I reproduced saving an inherited Chinese
   talk, loading it, then applying German defaults. Text stays Chinese and ready,
   audio becomes stale, missing text pages=[], with no dialog transition involved.
   Result: artifacts/claude-language-review-2026-09-29/coordinator-closed-talk.json.
   Defaults are excluded from JSON, version.language is empty. Distinguish the
   language of authored content from the current effective target and deliberate
   overrides. The invariant must survive Save/Cancel/reopen. Do not claim the
   current proposed plan solves every path; give the smallest coherent options
   and identify any product decision or persistent provenance truly required.
6. LV15 describes user edits during generation, but the UI disables those
   settings while busy. Verify reachability before presenting silent stale-event
   rejection as a user-facing problem. Keep defensive stale rejection a positive
   finding unless a real supported path to the confusion is shown.

The strong executed findings stand. The addendum should make the final review
accurate and useful without pretending an unimplemented remedy is verified.
