<!--
  Image d'une caméra, rafraîchie toutes les `interval` secondes tant que la
  page est visible (pas de trafic vers la caméra en arrière-plan).
-->
<template>
  <div class="camera-snapshot relative-position" :style="{ aspectRatio: ratio }">
    <img v-if="url" :src="url" :alt="alt ?? t('cameras.snapshotAlt')" class="camera-snapshot__img" />
    <div v-if="!url || error" class="absolute-full flex flex-center column text-center q-pa-md camera-snapshot__overlay">
      <q-spinner v-if="!error" color="white" size="32px" />
      <template v-else>
        <q-icon name="videocam_off" size="32px" color="white" />
        <div class="text-caption text-white q-mt-xs">{{ error }}</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useCameraStore } from 'src/stores/cameraStore';

const props = withDefaults(defineProps<{ cameraId: number; interval?: number; alt?: string; ratio?: string }>(), {
  interval: 10,
  ratio: '16 / 9',
});

const { t } = useI18n();
const store = useCameraStore();
const url = ref<string | null>(null);
const error = ref('');
let timer: ReturnType<typeof setTimeout> | null = null;
let alive = true;

async function refresh() {
  if (timer) clearTimeout(timer);
  timer = null;
  if (!alive) return;
  if (document.visibilityState === 'visible') {
    try {
      const next = await store.snapshotUrl(props.cameraId);
      if (!alive) {
        URL.revokeObjectURL(next);
        return;
      }
      if (url.value) URL.revokeObjectURL(url.value);
      url.value = next;
      error.value = '';
    } catch (err) {
      error.value = err instanceof Error && !('isAxiosError' in err) ? err.message : t('cameras.unavailable');
    }
  }
  if (alive) timer = setTimeout(() => void refresh(), props.interval * 1000);
}

function onVisibility() {
  if (document.visibilityState === 'visible') void refresh();
}

onMounted(() => {
  void refresh();
  document.addEventListener('visibilitychange', onVisibility);
});

watch(() => props.cameraId, () => void refresh());

onBeforeUnmount(() => {
  alive = false;
  if (timer) clearTimeout(timer);
  document.removeEventListener('visibilitychange', onVisibility);
  if (url.value) URL.revokeObjectURL(url.value);
});

defineExpose({ refresh });
</script>

<style scoped>
.camera-snapshot {
  width: 100%;
  background: #0b1220;
  overflow: hidden;
}

.camera-snapshot__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.camera-snapshot__overlay {
  background: rgba(11, 18, 32, 0.55);
}
</style>
