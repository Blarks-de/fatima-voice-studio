"""Settings (data/config.json), the engine builds, and the models the app can download."""
import ctypes
import json
import os
import secrets
from pathlib import Path

from . import APP_NAME

ROOT = Path(__file__).resolve().parent.parent  # the code
# The installer drops an "installed" marker next to the code. An installed copy keeps models, engine, voices
# and settings in %LOCALAPPDATA% and audio in Music, so updating or uninstalling the app never touches them.
# Run from source, everything stays inside this folder.
INSTALLED = (ROOT / "installed").exists()


def _music() -> Path:
    """The user's Music folder, wherever it really is (it may be moved or synced by OneDrive)."""
    import uuid
    folder_id = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("4BD8D571-6D19-48D3-BE97-422220080E43").bytes_le)
    buf = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(buf)) == 0:
            path = Path(buf.value)
            ctypes.windll.ole32.CoTaskMemFree(buf)
            return path
    except (AttributeError, OSError):
        pass
    return Path.home() / "Music"


HOME = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME if INSTALLED else ROOT
MUSIC = _music() / APP_NAME if INSTALLED else ROOT
DATA = HOME / "data"
CONFIG_FILE = DATA / "config.json"
VOICES = HOME / "voices"

DEFAULTS = {
    "host": "127.0.0.1",
    "port": 9830,
    "api_key": None,  # generated on first run
    "batches_dir": str(MUSIC / ("Batches" if INSTALLED else "batches")),
    "exports_dir": str(MUSIC / ("Exports" if INSTALLED else "exports")),  # where agents (MCP) save audio and exports
    # folders agents may read voice clips and scripts from (plus batches and exports, always)
    "agent_read_dirs": [str(Path.home() / d) for d in ("Music", "Downloads", "Desktop", "Documents")],
    "agents_noncommercial": False,  # may agents use non-commercial models?
    "engine": "cuda",  # which engine build runs the models (ENGINES); picked on the Setup page
    "models_dir": str(HOME / "models"),
    "default_model": "qwen3-tts-q8",
    "default_language": "en",
    "default_voice": "",
    # Output: what every finished script is turned into
    "loudness": -16.0,       # LUFS; YouTube plays at about -14, voiceovers usually sit at -16
    "formats": ["wav", "mp3"],
    "mp3_bitrate": 192,
    "subtitles": True,       # SRT next to each finished script (needs the subtitles model)
    "pause_segment": 0.25,   # seconds of silence where a long paragraph was split
    "pause_paragraph": 0.7,  # seconds between paragraphs
    "max_chars": 600,        # longest piece of text sent to the engine at once (about 40 seconds of speech)
    "notify": True,
    "check_updates": True,
    "hf_token": "",
    "timeout_s": 900,        # one segment
}

# llama.cpp builds, from one pinned release so every engine behaves the same. (url, size, sha256)
ENGINE_RELEASE = "b11476"
_GH = f"https://github.com/ggml-org/llama.cpp/releases/download/{ENGINE_RELEASE}/"
ENGINES = {
    "cuda": {"label": "NVIDIA · CUDA", "about": "The fastest option for NVIDIA cards (GeForce RTX 20 series and newer). Needs a 2025 or newer driver.",
             "zips": [(_GH + "llama-b11476-bin-win-cuda-13.4-x64.zip", 153139193, "0f947f51ece3b807a7f556dbdf45dc1a7f31aa6ea265657639007a33ef1ce5e0"),
                      (_GH + "cudart-llama-bin-win-cuda-13.4-x64.zip", 423535356, "738f8c251ac22b70c3ae6f83a10cf222725df0395246a2cf58f32bdb85fbe668")],
             "gpu": True},
    "cuda12": {"label": "NVIDIA · CUDA (older driver)", "about": "For NVIDIA cards whose driver can't be updated to a 2025 one, and GTX 10/16 cards.",
               "zips": [(_GH + "llama-b11476-bin-win-cuda-12.4-x64.zip", 264521953, "b30289b92274bb7e89200832f4bcfd9e731b716a4056d00b61440f623d4cc8e8"),
                        (_GH + "cudart-llama-bin-win-cuda-12.4-x64.zip", 391443627, "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6")],
               "gpu": True},
    "vulkan": {"label": "AMD / Intel · Vulkan", "about": "For AMD Radeon and Intel Arc cards. Also works on NVIDIA, a little slower than CUDA.",
               "zips": [(_GH + "llama-b11476-bin-win-vulkan-x64.zip", 33380424, "5c71e7b749697da4a8d46e9ee55486845cbba27c9dfbecb4007f31ba6610d523")],
               "gpu": True},
    "cpu": {"label": "CPU only", "about": "No graphics card needed. Speech comes out a bit slower than real time.",
            "zips": [(_GH + "llama-b11476-bin-win-cpu-x64.zip", 19441535, "a23e548c6b3525c38bcfeceaff919786ae06741857043cb670279b70100e5483")],
            "gpu": False},
}
ENGINE_EXE = "llama-tts.exe"

# whisper.cpp (CPU build: fast enough for subtitles and works on every PC, no GPU memory used)
WHISPER_RELEASE = "b5454"
WHISPER_ZIP = (f"https://github.com/ggml-org/whisper.cpp/releases/download/{WHISPER_RELEASE}/whisper-bin-x64.zip",
               8928640, "6ba69e3482d7826214f90a6a9c84ca07782aec1e1d0c6a7c30c994fd5d816ccb")
WHISPER_EXE = "whisper-cli.exe"


def engine_dir(cfg: dict, key: str | None = None) -> Path:
    return HOME / "engine" / (key or cfg["engine"])


def whisper_dir() -> Path:
    return HOME / "engine" / "whisper"


def installed_engines(cfg: dict) -> list[str]:
    return [k for k in ENGINES if (engine_dir(cfg, k) / ENGINE_EXE).exists()]


HF = "https://huggingface.co/"
_QWEN = HF + "ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF/resolve/main/"
_WHISPER = HF + "ggerganov/whisper.cpp/resolve/main/"
# Every file a model can need (url, size, sha256); shared files are downloaded once.
FILES = {
    "Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf": (_QWEN + "Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf", 1847874400,
                                           "ac7931aeb2e7aad1a6ed6602d353a5679c9d096b18ce8204ac730a8408d572e1"),
    "Qwen3-TTS-12Hz-1.7B-Base-Q4_K_M.gguf": (_QWEN + "Qwen3-TTS-12Hz-1.7B-Base-Q4_K_M.gguf", 1035965280,
                                             "8d18c94acb2addd042f97da63c98be144eafa76d0d9495177eab65130cf85129"),
    "mmproj-Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf": (_QWEN + "mmproj-Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf", 446422912,
                                                  "6fd65188839bcd6ecc91b277ad471e22a0edfada4699a0fe82f1165c18cfcce2"),
    "ggml-small-q5_1.bin": (_WHISPER + "ggml-small-q5_1.bin", 190085487,
                            "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb"),
    "ggml-large-v3-turbo-q5_0.bin": (_WHISPER + "ggml-large-v3-turbo-q5_0.bin", 574041195,
                                     "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"),
}

# Language codes the voice models take; the label is shown in the app.
LANGUAGES = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian",
             "pt": "Portuguese", "ru": "Russian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese"}

# kind "voice": speaks text (runs on the engine). kind "subtitles": whisper.cpp for SRT timings and transcripts.
MODELS = {
    "qwen3-tts-q8": {
        "kind": "voice", "label": "Qwen3-TTS 1.7B · Q8", "short": "Qwen3-TTS · best quality", "api_id": "qwen3-tts",
        "files": ["Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf", "mmproj-Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf"],
        "license": "Apache 2.0 — commercial use OK", "page": HF + "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "languages": list(LANGUAGES), "vram_gb": 4.2,
        "about": "The default. Natural voices in 10 languages, clones a voice from a few seconds of audio. "
                 "About 2× faster than real time on an RTX 5060 laptop GPU."},
    "qwen3-tts-q4": {
        "kind": "voice", "label": "Qwen3-TTS 1.7B · Q4", "short": "Qwen3-TTS · smaller", "api_id": "qwen3-tts-q4",
        "files": ["Qwen3-TTS-12Hz-1.7B-Base-Q4_K_M.gguf", "mmproj-Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf"],
        "license": "Apache 2.0 — commercial use OK", "page": HF + "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "languages": list(LANGUAGES), "vram_gb": 3.2,
        "about": "Same model, compressed further: for graphics cards with 4 GB or less, or CPU-only PCs. "
                 "Slightly less polished."},
    "whisper-small": {
        "kind": "subtitles", "label": "Whisper small", "short": "Subtitles · fast", "api_id": "whisper-small",
        "files": ["ggml-small-q5_1.bin"], "license": "MIT — commercial use OK", "page": HF + "openai/whisper-small",
        "about": "Times the subtitles (SRT) of every finished script. Runs on the CPU, about 10× faster than real time."},
    "whisper-turbo": {
        "kind": "subtitles", "label": "Whisper large-v3 turbo", "short": "Transcripts · accurate", "api_id": "whisper-large-v3-turbo",
        "files": ["ggml-large-v3-turbo-q5_0.bin"], "license": "MIT — commercial use OK", "page": HF + "openai/whisper-large-v3-turbo",
        "about": "More accurate transcripts, for the transcription API and for timing subtitles in harder audio. "
                 "About 3× slower than Whisper small."},
}


def model_files(key: str) -> list[str]:
    return list(MODELS[key]["files"])


def model_page(key: str) -> str:
    return MODELS[key]["page"]


def voice_models() -> list[str]:
    return [k for k, m in MODELS.items() if m["kind"] == "voice"]


EDITABLE = {"batches_dir", "exports_dir", "default_model", "default_language", "default_voice", "port", "api_key",
            "notify", "agent_read_dirs", "agents_noncommercial", "check_updates", "loudness", "formats", "mp3_bitrate",
            "subtitles", "pause_segment", "pause_paragraph", "max_chars", "hf_token", "timeout_s"}


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    if not cfg["api_key"]:
        cfg["api_key"] = "sk-local-" + secrets.token_urlsafe(24)
        save(cfg)
    return cfg


def save(cfg: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)


def installed_models(cfg: dict) -> list[str]:
    models_dir = Path(cfg["models_dir"])
    return [key for key in MODELS if all((models_dir / f).exists() for f in model_files(key))]


def subtitles_model(cfg: dict) -> str | None:
    """The installed subtitles model to use (the fast one if both are there)."""
    installed = installed_models(cfg)
    return next((k for k in ("whisper-small", "whisper-turbo") if k in installed), None)
