<!--
  Lecture d'un QR code avec la caméra (API BarcodeDetector : Chrome /
  Android). Sur les autres navigateurs, l'appareil photo du téléphone ouvre
  directement le lien de l'étiquette.
-->
<template>
  <q-dialog :model-value="modelValue" maximized transition-show="slide-up" transition-hide="slide-down" @show="start" @hide="stop" @update:model-value="(v: boolean) => emit('update:modelValue', v)">
    <q-card class="bg-black text-white column no-wrap">
      <q-bar class="bg-black">
        <q-icon name="qr_code_scanner" />
        <div>{{ t('frags.scanner.title') }}</div>
        <q-space />
        <q-btn v-close-popup dense flat round icon="close" :aria-label="t('common.close')" />
      </q-bar>
      <div class="col relative-position">
        <video ref="video" class="scanner-video" playsinline muted />
        <div class="scanner-frame" />
        <div class="absolute-bottom text-center q-pa-md text-body2">
          {{ error ?? t('frags.scanner.aim') }}
        </div>
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { scannerAvailable } from 'src/utils/qrScanner';

defineProps<{ modelValue: boolean }>();
const { t } = useI18n();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; detected: [value: string] }>();

const video = ref<HTMLVideoElement | null>(null);
const error = ref<string | null>(null);
let stream: MediaStream | null = null;
let timer: ReturnType<typeof setTimeout> | null = null;

async function start() {
  error.value = null;
  if (!scannerAvailable()) {
    error.value = t('frags.scanner.unavailable');
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    if (!video.value) return;
    video.value.srcObject = stream;
    await video.value.play();
    const detector = new window.BarcodeDetector!({ formats: ['qr_code'] });
    const scan = async () => {
      if (!video.value || !stream) return;
      try {
        const codes = await detector.detect(video.value);
        if (codes[0]?.rawValue) {
          emit('detected', codes[0].rawValue);
          emit('update:modelValue', false);
          return;
        }
      } catch {
        // image pas encore prête : on réessaie
      }
      timer = setTimeout(() => void scan(), 250);
    };
    void scan();
  } catch {
    error.value = t('frags.scanner.denied');
  }
}

function stop() {
  if (timer) clearTimeout(timer);
  timer = null;
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
}
</script>

<style scoped>
.scanner-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.scanner-frame {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 64vmin;
  height: 64vmin;
  transform: translate(-50%, -50%);
  border: 3px solid rgba(255, 255, 255, 0.85);
  border-radius: 16px;
  box-shadow: 0 0 0 100vmax rgba(0, 0, 0, 0.35);
}
</style>
