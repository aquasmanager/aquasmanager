import { t } from 'src/i18n/instance';
import { computed, ref } from 'vue';
import axios from 'axios';

// Notifications push de l'appareil courant (service worker + PushManager)

const subscribed = ref(false);
const busy = ref(false);

export function pushSupported(): boolean {
  return typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

/** iPhone / iPad : les notifications ne marchent qu'avec l'appli installée sur l'écran d'accueil */
export function needsInstallForPush(): boolean {
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const standalone = window.matchMedia('(display-mode: standalone)').matches;
  return ios && !standalone;
}

function keyToBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob((base64url + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function registration() {
  return navigator.serviceWorker.ready;
}

export function usePushNotifications() {
  const permission = ref(pushSupported() ? Notification.permission : 'denied');
  const blocked = computed(() => permission.value === 'denied');

  async function refresh() {
    if (!pushSupported()) return;
    const sub = await (await registration()).pushManager.getSubscription();
    subscribed.value = !!sub;
    permission.value = Notification.permission;
  }

  async function enable() {
    busy.value = true;
    try {
      permission.value = await Notification.requestPermission();
      if (permission.value !== 'granted') throw new Error(t('notices.pushDenied'));
      const { data } = await axios.get<{ public_key: string }>('/push/public-key');
      const reg = await registration();
      const sub =
        (await reg.pushManager.getSubscription()) ??
        (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyToBytes(data.public_key) }));
      await axios.post('/push/subscriptions', sub.toJSON());
      subscribed.value = true;
    } finally {
      busy.value = false;
    }
  }

  async function disable() {
    busy.value = true;
    try {
      const sub = await (await registration()).pushManager.getSubscription();
      if (sub) {
        await axios.post('/push/unsubscribe', { endpoint: sub.endpoint }).catch(() => undefined);
        await sub.unsubscribe();
      }
      subscribed.value = false;
    } finally {
      busy.value = false;
    }
  }

  async function test(): Promise<number> {
    const { data } = await axios.post<{ devices: number }>('/push/test');
    return data.devices;
  }

  return { subscribed, busy, permission, blocked, refresh, enable, disable, test };
}
