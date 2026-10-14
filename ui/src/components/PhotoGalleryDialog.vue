<template>
  <FormDialog
    :model-value="modelValue"
    icon="photo_library"
    :title="t('photos.title')"
    :subtitle="entityLabel"
    width="640px"
    :cancel-label="t('common.close')"
    hide-submit
    @update:model-value="(value: boolean) => emit('update:modelValue', value)"
  >
    <div v-if="canWrite" class="row q-gutter-sm">
      <q-btn v-if="hasCamera" unelevated color="primary" icon="photo_camera" :label="t('photos.takePhoto')" :loading="uploading" @click="camera?.click()" />
      <q-btn outline color="primary" icon="add_photo_alternate" :label="t('photos.addFromGallery')" :loading="uploading" @click="filePicker?.click()" />
      <input ref="filePicker" type="file" accept="image/*" multiple class="hidden" @change="handleFileSelected" />
      <input ref="camera" type="file" accept="image/*" capture="environment" class="hidden" @change="handleCapture" />
      <q-btn v-if="store.photos.length >= 2" flat color="primary" icon="compare" :label="t('photos.compare.button')" @click="compareOpen = true" />
    </div>
    <div v-else-if="store.photos.length >= 2" class="row">
      <q-btn flat color="primary" icon="compare" :label="t('photos.compare.button')" @click="compareOpen = true" />
    </div>

    <div v-if="store.loading" class="text-center q-py-lg">
      <q-spinner color="primary" size="2em" />
    </div>

    <div v-else-if="store.photos.length === 0" class="text-center text-grey-6 q-py-lg">
      <q-icon name="no_photography" size="40px" color="grey-5" />
      <div class="q-mt-sm">{{ t('photos.empty') }}</div>
    </div>

    <div v-else class="row q-col-gutter-sm">
      <div v-for="(photo, index) in store.photos" :key="photo.id" class="col-6 col-sm-4">
        <q-card flat bordered class="overflow-hidden">
          <q-img :src="photoFileUrl(entityType, entityId, photo.id)" :ratio="1" class="cursor-pointer" @click="openLightbox(index)">
            <q-badge v-if="photo.is_main" color="positive" class="absolute-top-left q-ma-xs">
              <q-icon name="star" size="12px" class="q-mr-xs" />{{ t('photos.main') }}
            </q-badge>
            <div class="absolute-bottom text-caption text-center q-pa-xs photo-date">{{ formatDate(photo.created_at) }}</div>
          </q-img>
          <div v-if="canWrite" class="row justify-center q-pa-xs">
            <q-btn
              flat
              dense
              round
              size="sm"
              :icon="photo.is_main ? 'star' : 'star_border'"
              :color="photo.is_main ? 'amber-8' : 'grey-7'"
              :disable="photo.is_main"
              @click="handleSetMain(photo.id)"
            >
              <q-tooltip>{{ t('photos.setMain') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="canDelete" flat dense round size="sm" icon="delete" color="negative" @click="handleDelete(photo.id)">
              <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
            </q-btn>
          </div>
        </q-card>
      </div>
    </div>
  </FormDialog>

  <PhotoCompareDialog v-model="compareOpen" :photos="store.photos" :entity-type="entityType" :entity-id="entityId" :entity-label="entityLabel" />

  <!-- Visionneuse plein écran -->
  <q-dialog v-model="lightboxOpen" maximized transition-show="fade" transition-hide="fade">
    <q-card class="bg-black column no-wrap">
      <q-bar class="bg-black text-white">
        <div v-if="currentLightboxPhoto">{{ lightboxIndex + 1 }} / {{ store.photos.length }}</div>
        <q-space />
        <q-btn
          v-if="canWrite && currentLightboxPhoto && !currentLightboxPhoto.is_main"
          flat
          dense
          icon="star_border"
          :label="t('photos.setMainShort')"
          @click="handleSetMain(currentLightboxPhoto.id)"
        />
        <q-btn
          v-if="canDelete && currentLightboxPhoto"
          flat
          dense
          icon="delete"
          @click="handleDelete(currentLightboxPhoto.id)"
        />
        <q-btn flat dense round icon="close" v-close-popup />
      </q-bar>

      <div class="col row items-center justify-center relative-position">
        <q-btn
          v-if="store.photos.length > 1"
          flat
          round
          icon="chevron_left"
          color="white"
          class="absolute-left q-ml-md"
          style="z-index: 1"
          @click="stepLightbox(-1)"
        />

        <q-img
          v-if="currentLightboxPhoto"
          :src="photoFileUrl(entityType, entityId, currentLightboxPhoto.id)"
          fit="contain"
          style="max-height: 90vh; max-width: 90vw"
        />

        <q-btn
          v-if="store.photos.length > 1"
          flat
          round
          icon="chevron_right"
          color="white"
          class="absolute-right q-mr-md"
          style="z-index: 1"
          @click="stepLightbox(1)"
        />
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import { usePhotoStore, photoFileUrl } from 'src/stores/photoStore';
import { PhotoEntityType } from 'src/types/photo';
import PhotoCompareDialog from 'src/components/PhotoCompareDialog.vue';
import { formatDate } from 'src/utils/format';

const props = defineProps<{
  modelValue: boolean;
  entityType: PhotoEntityType;
  entityId: number;
  entityLabel?: string;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'main-changed'): void;
}>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
// Photos des boutures : aussi gérables par le compte « bourse »
const isFrag = computed(() => props.entityType === PhotoEntityType.frags);
const canWrite = computed(() => (isFrag.value ? can.frags : can.edit));
const canDelete = computed(() => (isFrag.value ? can.frags : can.manage));
const { confirmRemove } = useConfirmRemove();
const uploading = ref(false);
const store = usePhotoStore();
const filePicker = ref<HTMLInputElement | null>(null);

const lightboxOpen = ref(false);
const compareOpen = ref(false);
const lightboxIndex = ref(0);
const currentLightboxPhoto = computed(() => store.photos[lightboxIndex.value] ?? null);

function openLightbox(index: number) {
  lightboxIndex.value = index;
  lightboxOpen.value = true;
}

function stepLightbox(delta: number) {
  const total = store.photos.length;
  lightboxIndex.value = (lightboxIndex.value + delta + total) % total;
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      void store.fetchPhotos(props.entityType, props.entityId);
    }
  },
  // Sur les pages en liste (fish/coral/plant/invertebrate), le composant
  // n'est monté qu'au moment même de l'ouverture (v-if="galleryX" posé en
  // même temps que modelValue=true) : sans immediate, ce watch ne voit
  // jamais de transition false->true et ne charge donc jamais les photos
  // au premier clic (seulement en rouvrant après une première fermeture).
  { immediate: true },
);

// Appareil photo arrière : seulement sur un appareil tactile (ailleurs, capture est ignoré)
const hasCamera = $q.platform.has.touch;
const camera = ref<HTMLInputElement | null>(null);

async function upload(files: File[]): Promise<number> {
  uploading.value = true;
  let added = 0;
  try {
    // Une à la fois : la première ajoutée devient la photo principale côté serveur
    for (const file of files) {
      await store.uploadPhoto(props.entityType, props.entityId, file);
      added++;
      if (store.photos.length === 1) emit('main-changed');
    }
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('photos.addFailed')) });
  } finally {
    uploading.value = false;
  }
  return added;
}

function handleFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = '';
  if (!files.length) return;
  void upload(files).then((added) => {
    if (added) $q.notify({ type: 'positive', message: t('photos.addedCount', added) });
  });
}

// Prise de vue : proposer d'enchaîner (série de photos d'un même spécimen)
function handleCapture(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  void upload([file]).then((added) => {
    if (!added) return;
    $q.notify({
      type: 'positive',
      message: t('photos.added'),
      timeout: 5000,
      actions: [{ label: t('photos.another'), color: 'white', icon: 'photo_camera', handler: () => camera.value?.click() }],
    });
  });
}

function handleSetMain(photoId: number) {
  store.setMainPhoto(props.entityType, props.entityId, photoId).then(
    () => {
      $q.notify({ type: 'positive', message: t('photos.mainUpdated') });
      emit('main-changed');
    },
    (err: unknown) => {
      $q.notify({ type: 'negative', message: apiErrorMessage(err, t('photos.updateFailed')) });
    },
  );
}

function handleDelete(photoId: number) {
  confirmRemove(t('photos.item'), async () => {
    await store.deletePhoto(props.entityType, props.entityId, photoId);
    // L'API promeut une autre photo principale si besoin : on recharge les indicateurs
    await store.fetchPhotos(props.entityType, props.entityId);
    emit('main-changed');
    if (store.photos.length === 0) {
      lightboxOpen.value = false;
    } else if (lightboxIndex.value >= store.photos.length) {
      lightboxIndex.value = store.photos.length - 1;
    }
  }, { message: t('photos.deleteMessage') });
}
</script>

<style scoped>
.photo-date {
  background: rgba(0, 0, 0, 0.45);
  color: white;
  padding: 2px 4px;
}

.hidden {
  display: none;
}
</style>
