<!--
  Direct d'une caméra en plein écran : qualité standard (flux secondaire,
  léger) ou HD (flux principal), capture vers les photos de l'aquarium.
-->
<template>
  <q-dialog v-model="open" maximized transition-show="fade" transition-hide="fade" @show="play" @hide="live.stop()">
    <q-card class="live-card column no-wrap">
      <q-bar class="live-bar text-white">
        <q-icon name="videocam" />
        <div class="text-weight-bold ellipsis">{{ camera?.name }}</div>
        <q-badge v-if="live.status.value === 'playing'" color="red-6" :label="t('cameras.player.live')" class="q-ml-sm" />
        <q-space />
        <q-btn-toggle
          v-model="quality"
          dense
          no-caps
          unelevated
          toggle-color="primary"
          color="grey-9"
          text-color="white"
          :options="[
            { label: t('cameras.player.standard'), value: 'sub' },
            { label: t('cameras.player.hd'), value: 'main' },
          ]"
          @update:model-value="play"
        />
        <q-btn v-if="can.edit" dense flat icon="photo_camera" :aria-label="t('cameras.capture')" :loading="capturing" class="q-ml-sm" @click="capture">
          <q-tooltip>{{ t('cameras.captureHelp') }}</q-tooltip>
        </q-btn>
        <q-btn v-close-popup dense flat icon="close" :aria-label="t('common.close')" />
      </q-bar>

      <div class="col relative-position flex flex-center">
        <video ref="videoEl" class="live-video" muted playsinline />
        <div v-if="live.status.value === 'connecting'" class="absolute-full flex flex-center column text-white">
          <q-spinner size="42px" />
          <div class="text-caption q-mt-sm">{{ t('cameras.player.connecting') }}</div>
        </div>
        <div v-else-if="live.status.value === 'error'" class="absolute-full flex flex-center column text-white q-pa-lg text-center">
          <q-icon name="videocam_off" size="42px" />
          <div class="q-mt-sm">{{ live.error.value }}</div>
          <q-btn outline color="white" icon="refresh" :label="t('common.retry')" class="q-mt-md" @click="play" />
        </div>
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useCameraLive } from 'src/composables/useCameraLive';
import { usePermissions } from 'src/composables/usePermissions';
import { useCameraStore } from 'src/stores/cameraStore';
import type { Camera, CameraQuality } from 'src/types/camera';
import { apiErrorMessage } from 'src/utils/apiError';

const props = defineProps<{ modelValue: boolean; camera: Camera | null }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; captured: [] }>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const store = useCameraStore();
const videoEl = ref<HTMLVideoElement | null>(null);
const live = useCameraLive(videoEl);
const quality = ref<CameraQuality>('sub');
const capturing = ref(false);

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
});

function play() {
  if (props.camera) live.start(props.camera.id, quality.value);
}

async function capture() {
  if (!props.camera) return;
  capturing.value = true;
  try {
    await store.capture(props.camera.id);
    $q.notify({ type: 'positive', icon: 'photo_camera', message: t('cameras.captured') });
    emit('captured');
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('cameras.captureFailed')) });
  } finally {
    capturing.value = false;
  }
}
</script>

<style scoped>
.live-card {
  background: #000;
}

.live-bar {
  background: #0b1220;
  height: auto;
  min-height: 44px;
  padding-top: env(safe-area-inset-top);
  gap: 6px;
}

.live-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}
</style>
