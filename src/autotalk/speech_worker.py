"""Managed speech process. JSON lines in/out; model libraries never enter the GUI."""

import base64
import contextlib
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

PROTOCOL = sys.stdout
RATE = 24000


def emit(value):
    print(json.dumps(value), file=PROTOCOL, flush=True)


def model_snapshot(spec):
    from huggingface_hub import hf_hub_download, snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError
    emit({"type": "status", "message": f"Preparing {spec['repo']}…"})
    try:
        root = Path(snapshot_download(spec["repo"], revision=spec["revision"], local_files_only=True))
    except LocalEntryNotFoundError:
        root = Path(snapshot_download(spec["repo"], revision=spec["revision"]))
    for name, expected in spec["files"].items():
        path = root / name
        for attempt in range(2):
            actual = ""
            if path.is_file():
                with path.open("rb") as stream:
                    if expected["algorithm"] == "sha256":
                        actual = hashlib.file_digest(stream, "sha256").hexdigest()
                    else:
                        data = stream.read()
                        actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
            if actual == expected["digest"]:
                break
            if attempt:
                raise RuntimeError(f"Model integrity check failed: {name}")
            hf_hub_download(spec["repo"], name, revision=spec["revision"], force_download=True)
    return root


def pcm(values):
    import numpy as np
    values = np.asarray(values, dtype=np.float32).reshape(-1)
    if not values.size or not np.isfinite(values).all():
        raise RuntimeError("Speech generation returned empty or invalid audio.")
    return (np.clip(values, -1, 1) * 32767).astype("<i2").tobytes()


class TorchBackend:
    def __init__(self, path, config):
        import torch
        from qwen_tts import Qwen3TTSModel
        if not torch.cuda.is_available():
            raise RuntimeError("A working NVIDIA GPU driver is required for speech generation.")
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        self.model = Qwen3TTSModel.from_pretrained(str(path), device_map="cuda:0", dtype=dtype,
                                                 attn_implementation="sdpa")
        self.config, self.prompts = config, {}

    def generate(self, passage, settings):
        args = dict(text=passage["text"], language=passage["language"], **settings)
        if args.get("temperature") == 0:
            args.pop("temperature")
            args["do_sample"] = False
        source = self.config["source"]
        if source == "Base":
            reference = passage["reference"]
            key = (reference["file"], reference["transcript"])
            if key not in self.prompts:
                self.prompts[key] = self.model.create_voice_clone_prompt(ref_audio=key[0], ref_text=key[1] or None,
                                                                        x_vector_only_mode=not bool(key[1]))
            wavs, rate = self.model.generate_voice_clone(**args, voice_clone_prompt=self.prompts[key])
        elif source == "VoiceDesign":
            wavs, rate = self.model.generate_voice_design(**args, instruct=passage["instructions"])
        else:
            wavs, rate = self.model.generate_custom_voice(**args, speaker=self.config["speaker"],
                                                         instruct=passage["instructions"])
        if rate != RATE:
            raise RuntimeError(f"Unexpected speech sample rate: {rate}.")
        # Qwen's wrapper returns decoded audio rather than an EOS status. Reject
        # output reaching the codec-frame budget instead of accepting a cutoff.
        if len(wavs[0]) / rate * 12.5 >= settings.get("max_new_tokens", 2048) - 2:
            raise RuntimeError("Speech reached the token limit. Shorten the passage or raise the limit.")
        yield pcm(wavs[0])

    def close(self):
        pass


class MLXBackend:
    def __init__(self, path, config):
        import mlx.core as mx
        from mlx_audio.tts.utils import load_model
        if not mx.metal.is_available():
            raise RuntimeError("Speech generation requires an Apple Silicon GPU.")
        mx.set_default_device(mx.gpu)
        self.model = load_model(str(path))
        self.config = config

    def generate(self, passage, settings):
        args = dict(settings)
        args["max_tokens"] = args.pop("max_new_tokens", 2048)
        reference = passage.get("reference", {})
        tokens = 0
        speaker = self.config["speaker"].lower() if self.config["source"] == "CustomVoice" else None
        for result in self.model.generate(text=passage["text"], voice=speaker,
                instruct=passage["instructions"] or None, lang_code=passage["language"].lower(),
                ref_audio=reference.get("file") or None, ref_text=reference.get("transcript") or None,
                stream=True, streaming_interval=0.32, **args):
            if result.sample_rate != RATE:
                raise RuntimeError("Unexpected MLX speech sample rate.")
            tokens += result.token_count
            yield pcm(result.audio)
        if tokens >= args["max_tokens"]:
            raise RuntimeError("Speech reached the token limit. Shorten the passage or raise the limit.")

    def close(self):
        pass


class VllmBackend:
    def __init__(self, path, config):
        import yaml
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("Speech generation requires a working NVIDIA GPU driver.")
        self.directory = tempfile.TemporaryDirectory(prefix="autotalk-server-")
        self.config = config
        self.process = None
        self.token = os.urandom(24).hex()
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        deployment = yaml.safe_load(Path(__file__).with_name("speech-linux.yaml").read_text())
        sampling = config.get("sampling", {})
        talker = deployment["stages"][0]
        talker["default_sampling_params"].update({k: v for k, v in sampling.items() if k != "max_new_tokens"})
        if "max_new_tokens" in sampling:
            talker["default_sampling_params"]["max_tokens"] = sampling["max_new_tokens"]
        config_path = Path(self.directory.name) / "deployment.yaml"
        config_path.write_text(yaml.safe_dump(deployment))
        env = os.environ.copy()
        env.update(VLLM_NO_USAGE_STATS="1", DO_NOT_TRACK="1", VLLM_USE_FLASHINFER_SAMPLER="0")
        try:
            self.process = subprocess.Popen([
                sys.executable, "-m", "vllm.entrypoints.cli.main", "serve", str(path),
                "--served-model-name", "autotalk", "--deploy-config", str(config_path), "--omni",
                "--host", "127.0.0.1", "--port", str(port), "--api-key", self.token, "--enforce-eager"],
                stdout=sys.stderr, stderr=sys.stderr, env=env)
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError("The local streaming backend could not start. See preparation details.")
                try:
                    with urllib.request.urlopen(self.url + "/health", timeout=1) as response:
                        if response.status == 200:
                            return
                except (OSError, urllib.error.URLError):
                    time.sleep(0.2)
            raise TimeoutError("The local speech backend did not become ready within five minutes.")
        except BaseException:
            self.close()
            raise

    def generate(self, passage, settings):
        body = {"model": "autotalk", "input": passage["text"], "voice": self.config["speaker"].lower(),
                "language": passage["language"], "instructions": passage["instructions"],
                "task_type": self.config["source"], "response_format": "pcm", "stream": True,
                "stream_format": "sse", "max_new_tokens": settings.get("max_new_tokens", 2048)}
        if self.config["source"] == "Base":
            reference = passage["reference"]
            body.update(ref_audio="data:audio/wav;base64," + base64.b64encode(Path(reference["file"]).read_bytes()).decode(),
                        ref_text=reference["transcript"] or None,
                        x_vector_only_mode=not bool(reference["transcript"]))
        request = urllib.request.Request(self.url + "/v1/audio/speech", data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.token})
        done = False
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                for line in response:
                    if not line.startswith(b"data: "):
                        continue
                    event = json.loads(line[6:])
                    if event.get("type") == "speech.audio.delta":
                        raw = base64.b64decode(event["audio"], validate=True)
                        if len(raw) % 2:
                            raise ValueError("The backend returned malformed PCM audio.")
                        yield raw
                    elif event.get("type") == "speech.audio.done":
                        if event.get("usage", {}).get("output_tokens", 0) >= body["max_new_tokens"]:
                            raise RuntimeError("Speech reached the token limit; increase it or shorten the passage.")
                        done = True
                    elif event.get("type") == "speech.audio.error":
                        raise RuntimeError(str(event.get("error", event)))
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read(4000).decode(errors="replace")) from error
        if not done:
            raise RuntimeError("Speech streaming ended without a completion event.")

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.directory.cleanup()


def generate_items(backend, request, config):
    for item in request["items"]:
        started = time.monotonic()
        output = Path(item["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        frames = 0
        with output.open("wb") as stream, wave.open(stream, "wb") as audio:
            audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            for passage in item["passages"]:
                for raw in backend.generate(passage, config.get("sampling", {})):
                    if not raw:
                        continue
                    audio.writeframes(raw)
                    stream.flush()
                    frames += len(raw) // 2
                    emit({"type": "audio", "page": item.get("page", 0), "key": item["key"],
                          "path": str(output), "frames": frames, "offset": 44})
            if not frames:
                raise RuntimeError("The speech backend produced no audio.")
            pause = round(item.get("pause", 0) * RATE)
            if pause:
                audio.writeframes(b"\0\0" * pause)
                frames += pause
        emit({"type": "complete", "page": item.get("page", 0), "key": item["key"],
              "path": str(output), "frames": frames, "seconds": frames / RATE,
              "generation_seconds": time.monotonic() - started,
              "provenance": {"backend": config["backend"], "model": config["model"]["repo"],
                             "revision": config["model"]["revision"], "sampling": config.get("sampling", {})}})
    emit({"type": "batch_complete"})


def main():
    backend = None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            config = json.loads(sys.stdin.readline())
            started = time.monotonic()
            path = model_snapshot(config["model"])
            emit({"type": "measurement", "stage": "Model files", "seconds": time.monotonic()-started})
            started = time.monotonic()
            emit({"type": "status", "message": "Loading the local speech model…"})
            backend_type = {"vllm": VllmBackend, "torch": TorchBackend, "mlx": MLXBackend}[config["backend"]]
            backend = backend_type(path, config)
            emit({"type": "measurement", "stage": "Model load", "seconds": time.monotonic()-started})
            emit({"type": "ready"})
            for line in sys.stdin:
                generate_items(backend, json.loads(line), config)
    except Exception as error:
        import traceback
        traceback.print_exc(file=sys.stderr)
        emit({"type": "error", "message": str(error)})
        raise SystemExit(1)
    finally:
        if backend:
            backend.close()


if __name__ == "__main__":
    main()
