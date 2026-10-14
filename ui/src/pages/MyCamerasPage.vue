<!--
  Caméras d'un aquarium (optionnel) : images rafraîchies, direct en plein
  écran, capture vers les photos. Configuration réservée aux gestionnaires.
-->
<template>
  <div>
    <PageHeader section :title="t('cameras.title')" :subtitle="t('cameras.subtitle')">
      <template #actions>
        <q-btn v-if="can.manage" unelevated color="primary" icon="add" :label="t('cameras.add')" @click="openForm(null)" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="!store.loading && cameras.length === 0"
      icon="videocam"
      :title="t('cameras.emptyTitle')"
      :message="t('cameras.emptyMessage')"
    >
      <q-btn v-if="can.manage" unelevated color="primary" icon="add" :label="t('cameras.add')" @click="openForm(null)" />
    </EmptyState>

    <div class="row q-col-gutter-md">
      <div v-for="cam in cameras" :key="cam.id" class="col-12 col-sm-6 col-lg-4">
        <q-card flat bordered class="overflow-hidden">
          <div class="cursor-pointer relative-position" role="button" :aria-label="t('cameras.liveOf', { name: cam.name })" @click="openLive(cam)">
            <CameraSnapshot :ref="(el) => setSnapshotRef(cam.id, el)" :camera-id="cam.id" :alt="cam.name" />
            <div class="absolute-bottom-right q-ma-sm">
              <q-btn round unelevated size="sm" color="dark" icon="play_arrow" :aria-label="t('cameras.live')" @click.stop="openLive(cam)" />
            </div>
          </div>
          <q-card-section class="row items-center no-wrap q-py-sm">
            <div class="col ellipsis">
              <div class="text-subtitle2 text-weight-bold ellipsis">{{ cam.name }}</div>
              <div class="text-caption text-grey-7">{{ brandLabel(cam) }} · {{ cam.host }}</div>
            </div>
            <q-btn v-if="can.edit" flat round dense icon="photo_camera" color="grey-8" :aria-label="t('cameras.capture')" :loading="capturing === cam.id" @click="capture(cam)">
              <q-tooltip>{{ t('cameras.captureHelp') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.manage" flat round dense icon="edit" color="grey-8" :aria-label="t('actions.edit')" @click="openForm(cam)">
              <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.manage" flat round dense icon="delete" color="grey-8" :aria-label="t('actions.delete')" @click="askDelete(cam)">
              <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
            </q-btn>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <CameraFormDialog v-model="formOpen" :aquarium-id="aquaId" :camera="editing" @saved="onSaved" />
    <CameraLiveDialog v-model="liveOpen" :camera="liveCamera" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, type ComponentPublicInstance } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import CameraFormDialog from 'src/components/CameraFormDialog.vue';
import CameraLiveDialog from 'src/components/CameraLiveDialog.vue';
import CameraSnapshot from 'src/components/CameraSnapshot.vue';
import EmptyState from 'src/components/EmptyState.vue';
import PageHeader from 'src/components/PageHeader.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { useCameraStore } from 'src/stores/cameraStore';
import { cameraBrandLabel, type Camera } from 'src/types/camera';
import { apiErrorMessage } from 'src/utils/apiError';

const props = defineProps<{ aquaId: number }>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const store = useCameraStore();
const cameras = computed(() => store.cameras.filter((c) => c.aquarium_id === props.aquaId));

const formOpen = ref(false);
const editing = ref<Camera | null>(null);
const liveOpen = ref(false);
const liveCamera = ref<Camera | null>(null);
const capturing = ref<number | null>(null);
const snapshots = new Map<number, { refresh: () => Promise<void> }>();

function setSnapshotRef(id: number, el: Element | ComponentPublicInstance | null) {
  if (el) snapshots.set(id, el as unknown as { refresh: () => Promise<void> });
  else snapshots.delete(id);
}

function brandLabel(cam: Camera) {
  return cameraBrandLabel(cam.brand);
}

async function load() {
  try {
    await Promise.all([store.fetchStatus(), store.fetchCameras(props.aquaId)]);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('cameras.loadFailed')) });
  }
}

function openForm(cam: Camera | null) {
  editing.value = cam;
  formOpen.value = true;
}

function onSaved(cam: Camera) {
  void snapshots.get(cam.id)?.refresh();
}

function openLive(cam: Camera) {
  liveCamera.value = cam;
  liveOpen.value = true;
}

async function capture(cam: Camera) {
  capturing.value = cam.id;
  try {
    await store.capture(cam.id);
    $q.notify({ type: 'positive', icon: 'photo_camera', message: t('cameras.captured') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('cameras.captureFailed')) });
  } finally {
    capturing.value = null;
  }
}

function askDelete(cam: Camera) {
  $q.dialog({
    title: t('cameras.deleteTitle'),
    message: t('cameras.deleteMessage', { name: cam.name }),
    cancel: true,
    ok: { label: t('actions.delete'), color: 'negative', flat: true },
  }).onOk(() => {
    void store.deleteCamera(cam.id).catch((err) => {
      $q.notify({ type: 'negative', message: apiErrorMessage(err, t('cameras.deleteFailed')) });
    });
  });
}

onMounted(load);
watch(() => props.aquaId, load);
</script>
