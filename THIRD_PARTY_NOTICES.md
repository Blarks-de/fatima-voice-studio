# Third-party notices

Fatima Voice Studio's own code is MIT licensed (see `LICENSE`). It ships with, or downloads on request,
the following third-party software and models, each under its own licence.

## Shipped in the installer

| Component | Licence | Source |
|---|---|---|
| Python 3.13 (embeddable distribution) | PSF License 2.0 | https://www.python.org |
| NumPy | BSD-3-Clause | https://github.com/numpy/numpy |
| python-soundfile | BSD-3-Clause | https://github.com/bastibe/python-soundfile |
| libsndfile (bundled in python-soundfile) | LGPL-2.1 | https://github.com/libsndfile/libsndfile |
| lameenc, with the LAME MP3 encoder | LGPL-3.0 (LAME: LGPL-2.0) | https://github.com/chrisstaite/lameenc |
| FastAPI | MIT | https://github.com/fastapi/fastapi |
| Starlette | BSD-3-Clause | https://github.com/encode/starlette |
| Uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn |
| Pydantic, pydantic-core, pydantic-settings | MIT | https://github.com/pydantic |
| HTTPX, HTTPCore | BSD-3-Clause | https://github.com/encode/httpx |
| AnyIO | MIT | https://github.com/agronholm/anyio |
| Pillow | MIT-CMU (HPND) | https://github.com/python-pillow/Pillow |
| pystray | LGPL-3.0 | https://github.com/moses-palmer/pystray |
| MCP Python SDK | MIT | https://github.com/modelcontextprotocol/python-sdk |
| pywin32 | PSF | https://github.com/mhammond/pywin32 |
| python-multipart | Apache-2.0 | https://github.com/Kludex/python-multipart |
| sse-starlette | BSD-3-Clause | https://github.com/sysid/sse-starlette |
| jsonschema, jsonschema-specifications, referencing, rpds-py | MIT | https://github.com/python-jsonschema |
| cryptography | Apache-2.0 or BSD-3-Clause | https://github.com/pyca/cryptography |
| cffi | MIT | https://github.com/python-cffi/cffi |
| pycparser | BSD-3-Clause | https://github.com/eliben/pycparser |
| OpenTelemetry API | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python |
| attrs | MIT | https://github.com/python-attrs/attrs |
| certifi | MPL-2.0 | https://github.com/certifi/python-certifi |
| click | BSD-3-Clause | https://github.com/pallets/click |
| h11 | MIT | https://github.com/python-hyper/h11 |
| idna | BSD-3-Clause | https://github.com/kjd/idna |
| PyJWT | MIT | https://github.com/jpadilla/pyjwt |
| python-dotenv | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| six | MIT | https://github.com/benjaminp/six |
| typing_extensions | PSF-2.0 | https://github.com/python/typing_extensions |
| typing-inspection, annotated-types, annotated-doc | MIT | https://github.com/pydantic |
| httpx-sse | MIT | https://github.com/florimondmanca/httpx-sse |
| Geist, Geist Mono fonts | SIL Open Font License 1.1 | https://github.com/vercel/geist-font |

Exact versions are in `packaging/requirements-lock.txt`; each package's licence text is in its
`*.dist-info` folder inside the installed `python\Lib\site-packages`.

pystray, lameenc (with LAME) and libsndfile are LGPL. They are shipped unmodified as separate files (Python
source and DLLs/extension modules), which you may replace with your own builds.

## Downloaded by the app when you choose to

These are not part of the installer. The app downloads them from their publishers when you click Download,
and checks each file against its published SHA-256.

| Component | Licence | Source |
|---|---|---|
| llama.cpp engine (`llama-tts`), incl. ggml | MIT | https://github.com/ggml-org/llama.cpp |
| NVIDIA CUDA runtime (in the CUDA engine downloads) | NVIDIA CUDA EULA | redistributed by llama.cpp |
| whisper.cpp (`whisper-cli`), incl. ggml | MIT | https://github.com/ggml-org/whisper.cpp |
| Qwen3-TTS 12Hz 1.7B Base (GGUF, Q8 and Q4) | Apache 2.0 | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base, GGUF by ggml-org |
| Whisper small, Whisper large-v3 turbo (ggml) | MIT | https://huggingface.co/openai, ggml by ggerganov |

## Audio you make

The voice models above allow commercial use of their output. Cloning a voice still needs the permission of the
person it belongs to: only add voices that are yours or that you have the right to use.
