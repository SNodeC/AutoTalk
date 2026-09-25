"""Standalone worker: this file runs with AutoTalk's managed speech interpreter."""

import hashlib
import json
import os
import sys
import time
from pathlib import Path


def main():
    import numpy as np
    import soundfile as sf
    import torch
    from huggingface_hub import hf_hub_download, snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError
    from qwen_tts import Qwen3TTSModel

    request = json.loads(Path(sys.argv[1]).read_text())
    if not torch.cuda.is_available():
        raise RuntimeError("No usable NVIDIA GPU was found. This prototype requires a compatible NVIDIA driver.")
    print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)
    specification = request["model"]
    repo, revision = specification["repo"], specification["revision"]
    print(f"Preparing model {repo}…", flush=True)
    try:
        model_path = Path(snapshot_download(repo, revision=revision, local_files_only=True))
    except LocalEntryNotFoundError:
        model_path = Path(snapshot_download(repo, revision=revision))
    # The model snapshot already includes its speech tokenizer. Verify all assets
    # against pinned upstream hashes; no second tokenizer download or cache ref.
    print("Verifying model files…", flush=True)
    for name, expected in specification["files"].items():
        path = model_path / name
        for attempt in range(2):
            actual = ""
            if path.is_file():
                with path.open("rb") as stream:
                    if expected["algorithm"] == "sha256":
                        actual = hashlib.file_digest(stream, "sha256").hexdigest()
                    else:
                        content = stream.read()
                        actual = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            if actual == expected["digest"]:
                break
            if attempt:
                raise RuntimeError(f"Model integrity check failed: {name}")
            hf_hub_download(repo, name, revision=revision, force_download=True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    print("Loading Qwen3-TTS on the GPU…", flush=True)
    model = Qwen3TTSModel.from_pretrained(str(model_path), device_map="cuda:0",
                                        dtype=torch.bfloat16, attn_implementation="sdpa")
    reference = request.get("reference")
    transcript = request.get("transcript", "").strip()
    prompt = model.create_voice_clone_prompt(ref_audio=reference, ref_text=transcript or None,
                                             x_vector_only_mode=not bool(transcript)) if reference else None
    for item in request["items"]:
        started = time.monotonic()
        print(f"Generating {item['label']}…", flush=True)
        # Paragraphs bound generation size without placing timing policy in the model.
        import re
        sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", item["text"].strip())
        chunks, current = [], ""
        for sentence in sentences:
            while len(sentence) > 500:
                cut = sentence.rfind(" ", 0, 500)
                cut = cut if cut > 0 else 500
                sentences_part = sentence[:cut]
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(sentences_part)
                sentence = sentence[cut:].strip()
            if len(current) + len(sentence) > 500 and current:
                chunks.append(current)
                current = ""
            current = (current + " " + sentence).strip()
        if current:
            chunks.append(current)
        segments = []
        rate = 24000
        for chunk in chunks:
            if reference:
                wavs, rate = model.generate_voice_clone(text=chunk, language=request["language"],
                                                       voice_clone_prompt=prompt, max_new_tokens=2048)
            else:
                wavs, rate = model.generate_custom_voice(text=chunk, language=request["language"],
                                                        speaker="Ryan", max_new_tokens=2048)
            data = np.asarray(wavs[0], dtype=np.float32).reshape(-1)
            if not data.size or not np.isfinite(data).all():
                raise RuntimeError("Speech generation returned invalid audio.")
            segments.append(data)
        segments.append(np.zeros(round(item.get("pause", 0) * rate), dtype=np.float32))
        output = Path(item["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp.wav")
        sf.write(temporary, np.concatenate(segments), rate, subtype="PCM_16")
        temporary.replace(output)
        print(json.dumps({"completed": item["label"], "seconds": sum(map(len, segments))/rate,
                          "generation_seconds": round(time.monotonic()-started, 2),
                          "peak_gpu_mib": round(torch.cuda.max_memory_reserved()/2**20)}), flush=True)


if __name__ == "__main__":
    main()
