'use client';

import { useCallback, useRef, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// 'quy' = quechua Ayacucho-Chanka, 'quz' = quechua Cusco-Collao.
// Confirma con tu equipo cuál habla su compañero.
const QUECHUA_LANG = 'quy';

export function useQuechuaSpeech(onText: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [processing, setProcessing] = useState(false);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const supported =
    typeof window !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined';

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunks.current = [];
      rec.ondataavailable = (e) => chunks.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setListening(false);
        setProcessing(true);
        try {
          const blob = new Blob(chunks.current, { type: rec.mimeType });
          const form = new FormData();
          form.append('audio', blob, 'voz.webm');
          form.append('lang', QUECHUA_LANG);
          const res = await fetch(`${API_URL}/transcribe`, {
            method: 'POST',
            body: form,
          });
          if (!res.ok) throw new Error('Error de transcripción');
          const data = await res.json();
          if (data.text) onText(data.text);
        } catch (e) {
          console.error(e);
          alert('No se pudo transcribir. Intenta de nuevo o escribe tu consulta.');
        } finally {
          setProcessing(false);
        }
      };
      rec.start();
      recRef.current = rec;
      setListening(true);
    } catch {
      alert('Permite el micrófono en el navegador.');
    }
  }, [onText]);

  const stop = useCallback(() => recRef.current?.stop(), []);

  return { supported, listening, processing, start, stop };
}