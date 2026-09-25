# Agreed feature scope and implementation status

The original agreed requirements are retained below. The 0.2 implementation now
exposes these selections and workflows. Linux integration has been exercised;
Windows/macOS adapters and native build definitions are present but need native
qualification. See [current behavior](../README.md) and [verification](VERIFICATION.md).

Remaining acceptance work includes native Windows/macOS GPU and microphone tests,
subjective voice/dialect/expression checks, long talks, and release signing.
These requirements are broader than a claim that every voice property works
reliably for every language.

1. **Presentation modes:** Prepared retains narration review, voice and conference
   configuration, complete audio preparation, duration fitting, and explicit
   presentation start. Quick accepts PDF, language, and duration, uses the default
   voice without conference input, then prepares and presents automatically.
   Realtime plans the whole deck, buffers initial streamed audio, starts presenting,
   and generates subsequent audio in the background. Playback can begin within
   the first slide when the backend supports incremental audio. It supports optional
   conference context and the selected voice. Wait visibly if the buffer empties;
   show that final duration is approximate until generation finishes. Initial
   runtime/model downloads must finish before synthesis can begin.
2. **Slide progress:** Keep the activity indicator and add completed/total slides
   for stages with measurable slide completion. Identify the active stage; do not
   invent slide percentages while waiting for a whole-deck Codex response.
3. **Multiple languages:** Preserve language versions of narration and audio and
   support per-slide languages for mixed-language talks. Organize generated speech
   by language. Keep voice identity reusable across languages, with language-specific
   reference recordings where supplied. Language and all effective synthesis
   settings must participate in determining whether an audio artifact is current.
4. **Presentation recording:** Add a Record presentation checkbox and a video
   destination. Capture the actual presentation's slide/audio timeline, including
   navigation, pauses, and buffering, with synchronized sound.
5. **Voice selection:** Offer a reusable library of predefined, cloned, and designed
   voices with previews. See the Qwen selections below for controls and capabilities.
6. **Speech quality:** Expose only validated quality/performance choices and explain
   their resource tradeoffs. Qwen has no general quality-level switch. Keep native
   synthesis quality separate from export sample rate/encoding; upsampling does not
   improve the generated voice. Do not present sampling randomness as a guaranteed
   quality or speed control.
7. **Speech style:** Offer Professional, Conversational, Energetic, Calm and
   understated, Lightly humorous, Academic, Storytelling, and Inspirational.
   Apply style to narration wording and to vocal delivery only where the selected
   model supports it. Keep the two capabilities clear in the UI.
8. **Continue fullscreen:** Leaving fullscreen pauses playback and preserves the
   current slide and audio position. Offer Continue presentation and Restart from
   beginning. The existing playback controller remains the authority for position.
9. **Codex model and reasoning:** Add separate selectors populated from app-server
   model/list, including each model's supported reasoning efforts and default.
   Respect account availability and slide-image input requirements. Apply the
   selected settings to scope extraction, narration, and duration revisions; save
   them with the project. Quick mode uses defaults without requiring configuration.
10. **Qwen model and synthesis settings:** Use the 1.7B family for the planned
    feature set. Select the appropriate variant for the voice source, as detailed
    below, and download it automatically when needed. Both model sizes need not be
    installed; 0.6B is outside the initial selector and must not be substituted
    silently. Validate 1.7B memory use and speed on the target GPU before promising
    uninterrupted Realtime playback. Qwen has no Codex-style reasoning effort.
11. **Preparation timing:** Measure Codex work, speech-runtime/model loading,
    synthesis, and duration-fitting passes separately. Show elapsed time and an
    estimate based on observed synthesis speed; in Realtime also show buffered
    audio duration. Separate first-use installation/download time from generation.
12. **Optional presentation audio:** Support user-supplied audio excerpts and
    background tracks, as detailed below. Their playback and video recording must
    follow the same presentation timeline as slides and narration.
13. **System audio destination:** Make AutoTalk's output selectable through Linux/
    Plasma's native Audio Volume controls, independently of the fullscreen display.
    The system audio service owns device routing; avoid a competing application
    device selector or project-specific hardware binding. Provide a System audio
    settings action that opens Plasma's native sound settings and a short preview
    to make the playback stream available for selection. Identify streams clearly
    as AutoTalk and respect system defaults and explicit per-application routing.
    Cover voice previews, prepared playback, Realtime audio, and optional clips.
    Keep routing stable across slide changes, stream recreation, and fullscreen
    exit/continue. Device changes must preserve presentation position; recover
    through system routing or pause with a clear message if no output is available.
    Record video from AutoTalk's own presentation audio mix, independently of the
    physical output device, without capturing unrelated desktop sounds. Verify
    routing and switching with the host's PipeWire/PulseAudio-compatible service;
    documentation of the requirement does not establish that all backends work.

## Qwen voice and delivery selections

These are planned user controls, not additional independent implementations of
voice or style. Organize them into Voice, Delivery, Per-slide directions, and
Optional audio clips, with technical generation parameters under Advanced.

| Selection | Required behavior and limits |
| --- | --- |
| Voice source | Predefined voice uses 1.7B CustomVoice; My voice uses 1.7B Base; Design a voice uses 1.7B VoiceDesign. Show the effective model and its supported controls. |
| Predefined voice / timbre | Offer Ryan, Aiden, Vivian, Serena, Uncle_Fu, Dylan, Eric, Ono_Anna, and Sohee, subject to the loaded model's speaker list. Show native-language profiles and a preview in the chosen talk language. |
| Personal voice | Record/import reference audio, optionally provide its exact transcript, name the voice, and save it for reuse. Explain the difference between audio-plus-transcript conditioning and speaker-identity-only conditioning. |
| Designed voice | Describe a new voice, preview it, and save the accepted identity. Reuse an accepted reference rather than independently redesigning the voice for each slide. |
| Perceived age | An optional VoiceDesign attribute, with descriptive age groups or free text. Do not promise exact age transformation of a cloned or predefined voice. |
| Acoustic attributes | Offer descriptive pitch/register, pace, energy, warmth/texture, articulation, and vocal projection where supported. These are instruction-based guidance, not calibrated pitch, decibel, or words-per-minute controls. Keep output volume separate. |
| Speaker background | An optional persona/role description guiding voice design and delivery. Keep it separate from conference scope and factual narration; it must not become an invented speaker biography in the talk. |
| Single or multiple attributes | Use one delivery editor for individual adjustments and combined settings. Save named presets and provide a custom instruction box. Resolve conflicting preset, field, and free-text directions into one effective instruction. |
| Style and human-likeness | Use the style choices in item 7, with natural rhythm, emphasis, and pauses as the default quality goal. Do not imply a measurable human-likeness percentage or add fillers automatically. |
| Gradual control | Allow section/slide directions such as a calm opening, rising enthusiasm around results, and a measured conclusion. Support within-passage progression as best-effort instructions, without promising exact timed transitions or changing voice identity. |
| Cross-language voice reuse | Keep the chosen identity across language versions and mixed-language passages. Language selection controls synthesis; Codex creates/translates narration. Preview each language, and avoid guarantees of identical accent or pronunciation quality. |
| Accent / dialect | An optional descriptive preference where the model/voice combination has been validated. Do not infer arbitrary dialect-generation support from tokenizer reconstruction demos. |
| Nonverbal expression | Optional, previewed delivery cues such as a chuckle or sigh when the selected model can produce them. Do not assume a universal sound-tag syntax; use imported audio for precisely controlled effects. |
| Advanced synthesis | Expose supported temperature, top-k, top-p, sampling, and repetition-penalty controls with model defaults and Reset. Keep backend-specific/internal sampling controls advanced. Treat maximum generated tokens as an output guard, not a talk-duration or quality selector; detect truncation. |
| Audio export | Preserve native 24 kHz synthesis. Offer output format/encoding and resampling only for export compatibility; do not label a higher export sample rate as higher generated quality. |
| Streaming | Use an incremental-audio backend for Realtime and show buffered duration. Evaluate vLLM-Omni locally; the standard Qwen wrapper's non_streaming_mode flag alone does not enable incremental output. Keep backend setup automatic. |
| Singing / music excerpts | Allow imported clips for musical examples or introductions. Generating new singing from arbitrary lyrics and melody is outside the established Qwen TTS capability and needs separate evaluation. |
| Background sound / ambience | Allow optional imported tracks with volume and placement controls. Keep them separate from narration and voice references so they can be changed independently. Do not expose tokenizer reconstruction as a text-to-sound generator. |

### Model boundaries and acceptance criteria

- CustomVoice and VoiceDesign support natural-language delivery instructions.
  Base voice cloning does not expose the same direct instruction interface.
  Disable unsupported controls with an explanation rather than silently ignoring
  them. A designed reference reused through Base inherits this limitation.
- Download only the selected variants and manage their lifetime automatically;
  do not require the user to run servers or keep all three models in GPU memory.
- Keep one saved voice profile and one effective delivery configuration, with
  explicit section/slide overrides. Save model, language, reference, style, and
  synthesis settings with generated artifacts so changes invalidate affected audio.
- Provide previews using the selected voice, language, and effective delivery.
  Review consistency, pronunciation, and prompt adherence on the target machine;
  model demonstrations are not acceptance tests for AutoTalk.
- Include delivered audio, optional clips, and track timing in duration accounting,
  synchronized slide changes, pause/resume, and recorded video. Style changes can
  change duration. Changed settings must invalidate affected prepared or queued
  audio before it can be played.
- Prepared exposes full authoring. Quick uses the default voice and automatic
  delivery settings without conference input. Realtime uses supported selected settings with
  visible buffering and no promised first-audio latency until measured locally.
- The article's Dialect, Singing, Paralanguage, and Background Sound Reconstruction
  examples demonstrate encoding/decoding of existing audio. Do not implement them
  as four unrestricted generation switches or add a redundant reconstruction pass
  to ordinary imported-clip playback.

## Performance evidence and capability sources

The [recorded local measurements](VERIFICATION.md#observed-synthesis-times) show
7.50 seconds of generation for 9.96 seconds of German audio (including a 0.6-second
pause), and 10.29 seconds for 13.92 seconds. These exclude loading and downloads.
Speech synthesis is therefore a likely sustained bottleneck for long talks on
the tested machine, but no controlled Codex-versus-Qwen timing has been recorded.
Duration fitting can add repeated narration and synthesis passes.

- [Codex model discovery and supported reasoning efforts](https://learn.chatgpt.com/docs/app-server#models)
  provide the selectable capabilities; do not hard-code account/model availability.
- [Official Qwen3-TTS model capabilities](https://github.com/QwenLM/Qwen3-TTS#released-models-description-and-download)
  distinguish model sizes, predefined voices, cloning, and instruction control.
- [Qwen's capability article](https://qwen.ai/blog?id=qwen3tts-0115) demonstrates
  voice design, expressive delivery, cross-language voices, and tokenizer audio
  reconstruction; the selections above distinguish these capabilities.
- [Voice design and reuse](https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone)
  documents the designed-reference-to-Base workflow.
- [Qwen inference interface](https://github.com/QwenLM/Qwen3-TTS/blob/main/qwen_tts/inference/qwen3_tts_model.py)
  documents generation controls and the standard wrapper's streaming limitation.
- [vLLM-Omni speech interface](https://docs.vllm.ai/projects/vllm-omni/en/stable/serving/speech_api/)
  documents a candidate local streaming backend and its output controls.
- [Plasma Audio Volume](https://docs.kde.org/trunk_kf6/en/plasma-pa/kcontrol/plasma-pa/index.html)
  documents system and application audio controls.
- [Qt audio output](https://doc.qt.io/qt-6/qaudiooutput.html)
  documents device selection and the system-default output.
