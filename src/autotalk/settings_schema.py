# SPDX-License-Identifier: MIT
"""Presentation metadata for scoped settings; Project alone resolves values.

Rows describe editors, not a second set of defaults. Custom owners supply voice,
sampling, shared presets and imported audio; their fields are placed only once.
"""
from dataclasses import dataclass, replace
from .project import SETTING_DEFAULTS, SETTING_CHOICES

PAGES = ('Talk', 'Voice & language', 'Writing & delivery', 'Timing & playback', 'Audio & recording', 'AI model')
CUSTOM_OWNED = {'voice', 'delivery.sampling'}
CUSTOM_AREAS = ('delivery presets', 'clips', 'background')
ATTRIBUTES = {
    'pitch': ('Low', 'Medium', 'High'), 'texture': ('Clear', 'Warm', 'Breathy', 'Raspy'),
    'energy': ('Low', 'Moderate', 'High'), 'pace': ('Slow', 'Moderate', 'Brisk'),
    'age': ('Young adult', 'Middle-aged adult', 'Older adult'),
    'articulation': ('Natural', 'Precise', 'Relaxed'), 'projection': ('Soft', 'Conversational', 'Confident'),
    'accent': ('Beijing Mandarin', 'Sichuan Mandarin'),
    'expression': ('Restrained laughter', 'Audible sigh', 'Thoughtful hesitation', 'Enthusiastic interjection'),
}
LABELS = {
    'language_policy': ('Separate versions and mixed passages', 'Separate versions; one language per slide', 'Separate single-language versions'),
    'quick_timing': ('Fit, then start (up to three revisions)', 'Generate once, then start', 'Require timing match before start'),
    'realtime_script': ('Write the complete script first', 'Plan the deck; write ahead by slide'),
    'speech_priority': ('Consistency first', 'Earliest playback'),
    'recording_source': ('Slide video + narration', 'Screen + system audio (Linux)'),
    'recording_policy': ('Keep fullscreen pauses; omit time outside fullscreen', 'Keep all elapsed time', 'Skip pauses, buffering and time outside fullscreen'),
    'after': ('Advance automatically', 'Wait for presenter', 'Pause for live demo'),
    'export_rate': ('24 kHz (native)', '44.1 kHz', '48 kHz'),
    'export_bitrate': ('AAC 96 kbit/s', 'AAC 128 kbit/s', 'AAC 192 kbit/s'),
}

@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    page: str
    section: str
    kind: str = 'choice'
    scopes: tuple = ()
    read_only_scopes: tuple = ()
    choices: tuple = ()
    limits: tuple = (0, 100)
    unit: str = ''
    scale: float = 1
    metadata: bool = False
    help: str = ''
    order: int = 0


def setting(key, label, page, section, **kw):
    choices = SETTING_CHOICES.get(key, ())
    return Setting(key, label, page, section, scopes=SETTING_DEFAULTS.get(key, (None, (1,)))[1],
                   choices=tuple(zip(LABELS.get(key, choices), choices)), **kw)

ROWS = [
    *(setting(key, label, 'Talk', 'Talk & conference', kind=kind, metadata=True) for key, label, kind in (
        ('title', 'Talk title', 'text'), ('audience', 'Audience', 'text'), ('objective', 'Talk objective', 'text'),
        ('conference_url', 'Conference website', 'text'), ('scope', 'Conference scope', 'multiline'))),
    setting('language', 'Language', 'Voice & language', 'Language', read_only_scopes=(1,),
            help='Selecting a talk language restores its saved version or starts an empty version. Missing narration is generated from the slides, never translated from another version.'),
    setting('language_policy', 'Language arrangement', 'Voice & language', 'Language'),
    setting('writing_style', 'Writing style', 'Writing & delivery', 'Writing & delivery'),
    setting('delivery.style', 'Spoken delivery', 'Writing & delivery', 'Writing & delivery'),
    setting('delivery.instructions', 'Custom vocal directions', 'Writing & delivery', 'Writing & delivery', kind='text'),
    setting('delivery.attributes.persona', 'Speaker background / persona', 'Writing & delivery', 'Vocal attributes', kind='text'),
    setting('delivery.progression', 'Gradual delivery across slides', 'Writing & delivery', 'Vocal attributes', kind='text'),
    setting('mode', 'Mode', 'Timing & playback', 'Preparation', read_only_scopes=(1,)),
    setting('tolerance_seconds', 'Allowed timing difference', 'Timing & playback', 'Preparation', kind='number', limits=(0,600), unit=' sec'),
    setting('quick_timing', 'Quick timing policy', 'Timing & playback', 'Preparation'),
    setting('realtime_script', 'Realtime narration', 'Timing & playback', 'Preparation'),
    setting('speech_priority', 'Realtime speech priority', 'Timing & playback', 'Preparation'),
    setting('buffer_seconds', 'Realtime startup/refill buffer', 'Timing & playback', 'Preparation', kind='number', limits=(2,30), unit=' seconds'),
    setting('pause_seconds', 'Pause after slide', 'Timing & playback', 'Playback', kind='number', limits=(0,10), unit=' sec'),
    setting('after', 'After slide', 'Timing & playback', 'Playback'),
    setting('record_presentation', 'Record presentation as a video', 'Audio & recording', 'Recording', kind='bool', read_only_scopes=(1,)),
    setting('recording_source', 'Recording source', 'Audio & recording', 'Recording'),
    setting('capture_microphone', 'Include microphone', 'Audio & recording', 'Recording', kind='bool'),
    setting('recording_policy', 'Recording pauses', 'Audio & recording', 'Recording'),
    setting('recording_destination', 'Video destination', 'Audio & recording', 'Recording', kind='text', metadata=True),
    setting('export_rate', 'Export audio sample rate', 'Audio & recording', 'Output quality'),
    setting('export_bitrate', 'MP4 / M4A audio encoding', 'Audio & recording', 'Output quality'),
    setting('background_gain', 'Background volume', 'Audio & recording', 'Background audio', kind='number', limits=(0,100), unit=' %', scale=100),
    setting('background_loop', 'Loop background audio', 'Audio & recording', 'Background audio', kind='bool'),
    setting('codex_model', 'Model', 'AI model', 'Narration AI — Codex', kind='custom'),
    setting('codex_effort', 'Reasoning effort', 'AI model', 'Narration AI — Codex', kind='custom'),
]
index = next(i for i,r in enumerate(ROWS) if r.key == 'delivery.attributes.persona')
ROWS[index:index] = [Setting('delivery.attributes.'+key, key.capitalize(), 'Writing & delivery', 'Vocal attributes',
    scopes=SETTING_DEFAULTS['delivery.attributes.'+key][1], choices=(('Model default',''),)+tuple((v,v) for v in values)) for key,values in ATTRIBUTES.items()]
SCHEMA = {r.key: replace(r, order=i, scopes=(0,1) if r.key in ('after','pause_seconds') else r.scopes) for i,r in enumerate(ROWS)}
del ROWS
