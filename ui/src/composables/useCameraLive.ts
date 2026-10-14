import { onBeforeUnmount, ref, type Ref } from 'vue';
import { useAuthStore } from 'src/stores/authStore';
import type { CameraQuality } from 'src/types/camera';
import { websocketUrl } from 'src/utils/runtimeConfig';
import { t } from 'src/i18n/instance';

/*
 * Direct d'une caméra en MSE (fMP4 sur websocket), relayé par l'API depuis
 * go2rtc. Logique de lecture adaptée de go2rtc (www/video-rtc.js, licence MIT) :
 * on annonce les codecs lisibles, go2rtc répond le type du flux puis envoie
 * les segments, gardés au plus près du direct (5 s de tampon au maximum).
 */

const CODECS = [
  'avc1.640029', // H.264 high 4.1
  'avc1.64002A', // H.264 high 4.2
  'avc1.640033', // H.264 high 5.1
  'hvc1.1.6.L153.B0', // H.265 main 5.1
  'mp4a.40.2', // AAC LC
  'mp4a.40.5', // AAC HE
  'flac',
  'opus',
];

type LiveStatus = 'idle' | 'connecting' | 'playing' | 'error';

// Codes de fermeture de l'API (voir routes/camera.py)
const CLOSE_MESSAGES: Record<number, string> = {
  4403: 'cameras.player.forbidden',
  4503: 'cameras.player.serviceDown',
};

function friendlyError(raw: string): string {
  const low = raw.toLowerCase();
  if (low.includes('401') || low.includes('unauthorized') || low.includes('user/pass')) {
    return t('cameras.player.credentials');
  }
  if (low.includes('dial tcp') || low.includes('timeout') || low.includes('refused') || low.includes('no route')) {
    return t('cameras.player.unreachable');
  }
  if (low.includes('codecs')) {
    return t('cameras.player.codec');
  }
  return t('cameras.player.noStream');
}

function mediaSourceClass(): { ctor: typeof MediaSource; managed: boolean } | null {
  const managed = (window as unknown as { ManagedMediaSource?: typeof MediaSource }).ManagedMediaSource;
  if (managed) return { ctor: managed, managed: true };
  if ('MediaSource' in window) return { ctor: window.MediaSource, managed: false };
  return null;
}

export function useCameraLive(video: Ref<HTMLVideoElement | null>) {
  const status = ref<LiveStatus>('idle');
  const error = ref('');
  let socket: WebSocket | null = null;
  let stopped = true;
  let retriedAuth = false; // jeton renouvelé une seule fois par lancement

  function fail(message: string) {
    if (stopped) return;
    status.value = 'error';
    error.value = message;
    cleanup();
  }

  function cleanup() {
    const ws = socket;
    socket = null;
    if (ws) {
      ws.onclose = null;
      ws.close();
    }
    const el = video.value;
    if (el) {
      el.removeAttribute('src');
      el.srcObject = null;
      el.load();
    }
  }

  function start(cameraId: number, quality: CameraQuality, authRetry = false) {
    stop();
    stopped = false;
    retriedAuth = authRetry;
    status.value = 'connecting';
    error.value = '';
    const el = video.value;
    const source = mediaSourceClass();
    if (!el || !source) {
      fail(t('cameras.player.unsupported'));
      return;
    }

    const ms = new source.ctor();
    if (source.managed) {
      el.disableRemotePlayback = true;
      el.srcObject = ms;
    } else {
      el.src = URL.createObjectURL(ms);
    }
    el.muted = true;
    el.playsInline = true;
    el.addEventListener('playing', () => (status.value = 'playing'), { once: true });

    const ws = new WebSocket(websocketUrl(`/cameras/${cameraId}/live?quality=${quality}`));
    ws.binaryType = 'arraybuffer';
    socket = ws;

    const sourceOpen = new Promise<void>((resolve) => ms.addEventListener('sourceopen', () => resolve(), { once: true }));
    const socketOpen = new Promise<void>((resolve) => (ws.onopen = () => resolve()));

    void socketOpen.then(() => {
      ws.send(JSON.stringify({ type: 'auth', token: useAuthStore().accessToken }));
      return sourceOpen.then(() => {
        if (!source.managed) URL.revokeObjectURL(el.src);
        const codecs = CODECS.filter((c) => source.ctor.isTypeSupported(`video/mp4; codecs="${c}"`)).join();
        if (socket === ws) ws.send(JSON.stringify({ type: 'mse', value: codecs }));
      });
    });

    let buffer: SourceBuffer | null = null;
    const pending = new Uint8Array(2 * 1024 * 1024);
    let pendingLength = 0;

    function append(data: ArrayBuffer) {
      if (!buffer) return;
      if (buffer.updating || pendingLength > 0) {
        const chunk = new Uint8Array(data);
        if (pendingLength + chunk.byteLength > pending.byteLength) return; // retard trop grand : segment sauté
        pending.set(chunk, pendingLength);
        pendingLength += chunk.byteLength;
        return;
      }
      try {
        buffer.appendBuffer(data);
      } catch {
        /* segment refusé (flux en cours de changement) : on attend le suivant */
      }
    }

    function onUpdateEnd() {
      if (!buffer || !el) return;
      if (!buffer.updating && pendingLength > 0) {
        try {
          buffer.appendBuffer(pending.slice(0, pendingLength));
          pendingLength = 0;
        } catch {
          /* idem */
        }
      }
      if (!buffer.updating && buffer.buffered.length) {
        // Au plus près du direct : 5 s de tampon au maximum, lecture accélérée si retard
        const end = buffer.buffered.end(buffer.buffered.length - 1);
        const start = end - 5;
        if (start > buffer.buffered.start(0)) {
          buffer.remove(buffer.buffered.start(0), start);
          ms.setLiveSeekableRange(start, end);
        }
        if (el.currentTime < start) el.currentTime = start;
        const gap = end - el.currentTime;
        el.playbackRate = gap > 0.1 ? gap : 0.1;
      }
    }

    ws.onmessage = (event: MessageEvent) => {
      if (typeof event.data !== 'string') {
        append(event.data as ArrayBuffer);
        return;
      }
      const msg = JSON.parse(event.data) as { type: string; value: string };
      if (msg.type === 'mse' && !buffer) {
        try {
          buffer = ms.addSourceBuffer(msg.value);
        } catch {
          fail(t('cameras.player.codec'));
          return;
        }
        buffer.mode = 'segments';
        buffer.addEventListener('updateend', onUpdateEnd);
        void el.play().catch(() => undefined);
      } else if (msg.type === 'error') {
        fail(friendlyError(msg.value ?? ''));
      }
    };

    ws.onclose = (event: CloseEvent) => {
      if (stopped || socket !== ws) return;
      if (event.code === 4401 && !retriedAuth) {
        // Jeton expiré : renouvelé puis nouvel essai (une fois)
        retriedAuth = true;
        void useAuthStore()
          .refreshToken({ _skipAuthInterceptor: true })
          .then(() => start(cameraId, quality, true))
          .catch(() => fail(t('cameras.player.sessionExpired')));
        return;
      }
      fail(t(CLOSE_MESSAGES[event.code] ?? 'cameras.player.interrupted'));
    };
  }

  function stop() {
    stopped = true;
    status.value = 'idle';
    cleanup();
  }

  onBeforeUnmount(stop);

  return { status, error, start, stop };
}
