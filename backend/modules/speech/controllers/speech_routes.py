import io
import threading

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from config.settings import settings
from security import limiter

router = APIRouter(tags=["speech"])

MODEL_ID = "facebook/mms-1b-all"
ALLOWED_LANGS = {"quy", "quz"}  # Ayacucho-Chanka y Cusco-Collao
MAX_BYTES = 10 * 1024 * 1024  # 10 MB

_lock = threading.Lock()
_state: dict = {}


def _load():
    # Se carga la primera vez que se usa, no al arrancar el backend.
    if "model" not in _state:
        from transformers import AutoProcessor, Wav2Vec2ForCTC

        _state["processor"] = AutoProcessor.from_pretrained(MODEL_ID)
        _state["model"] = Wav2Vec2ForCTC.from_pretrained(MODEL_ID)
        _state["model"].eval()
    return _state["processor"], _state["model"]


def _transcribe_sync(data: bytes, lang: str) -> str:
    import librosa
    import torch

    wav, _ = librosa.load(io.BytesIO(data), sr=16000, mono=True)
    with _lock:  # el modelo cambia de adaptador: no es seguro en paralelo
        processor, model = _load()
        processor.tokenizer.set_target_lang(lang)
        model.load_adapter(lang)
        inputs = processor(wav, sampling_rate=16000, return_tensors="pt")
        with torch.no_grad():
            logits = model(**inputs).logits
        ids = torch.argmax(logits, dim=-1)[0]
        return processor.decode(ids)


@router.post("/transcribe")
@limiter.limit(settings.LLM_RATE_LIMIT)
async def transcribe(
    request: Request,
    audio: UploadFile = File(...),
    lang: str = Form("quy"),
):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail="Idioma no soportado")

    data = await audio.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Audio demasiado grande")

    import asyncio

    try:
        text = await asyncio.to_thread(_transcribe_sync, data, lang)
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo transcribir el audio")

    return {"text": text, "lang": lang}