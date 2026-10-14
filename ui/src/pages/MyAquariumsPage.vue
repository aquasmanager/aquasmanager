<template>
  <q-page class="app-page">
    <PageHeader icon="water" :title="t('aquariums.title')" :subtitle="t('aquariums.subtitle')">
      <template #actions>
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('aquariums.add')" @click="showCreateDialog" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="store.aquariums.length === 0"
      icon="water"
      :title="t('aquariums.emptyTitle')"
      :message="t('aquariums.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('aquariums.add')" @click="showCreateDialog" />
    </EmptyState>

    <div v-else class="row q-col-gutter-md">
      <div v-for="aquarium in store.aquariums" :key="aquarium.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
        <PhotoCard
          :photo="mainPhotoUrl(PhotoEntityType.aquariums, aquarium.id, imageTimestamp)"
          :title="aquarium.name"
          :badge="
            inMaintenance(aquarium)
              ? { label: t('aquariums.maintenance.badge'), color: 'orange-9' }
              : { label: aquarium.water_type === WaterType.sea ? t('aquariumInfo.sea') : t('aquariumInfo.fresh'), color: 'teal-6' }
          "
          :subtitle="aquarium.biotope"
          :caption="t('aquariums.since', { date: formatDate(aquarium.date_creation) })"
          :meta="{ icon: 'water_drop', text: `${aquarium.volume} L` }"
          :open-label="t('aquariums.open')"
          @open="goToAquarium(aquarium.id)"
          @gallery="openGallery(aquarium)"
          @edit="showEdit(aquarium)"
          @remove="remove(aquarium)"
        >
          <template #actions>
            <q-btn flat round dense size="sm" color="grey-7" icon="info" @click="showInfo(aquarium)">
              <q-tooltip>{{ t('aquariums.information') }}</q-tooltip>
            </q-btn>
          </template>
        </PhotoCard>
      </div>
    </div>

    <!-- Galerie de photos -->
    <PhotoGalleryDialog
      v-if="galleryAquarium"
      v-model="galleryOpen"
      :entity-type="PhotoEntityType.aquariums"
      :entity-id="galleryAquarium.id"
      :entity-label="galleryAquarium.name"
      @main-changed="imageTimestamp = Date.now()"
    />

    <!-- Création / modification -->
    <FormDialog
      v-model="dialog"
      icon="water"
      :title="edited ? t('aquariums.editTitle') : t('aquariums.add')"
      :subtitle="t('aquariums.formSubtitle')"
      :loading="saving"
      @submit="onSubmit"
      @hide="closeDialog"
    >
      <div class="row q-col-gutter-md">
        <div class="col-12 col-sm-6">
          <q-input v-model="name" :label="t('aquariums.name')" outlined dense :error="!!errors.name" :error-message="errors.name" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="biotope" :label="t('aquariums.biotope')" :placeholder="t('aquariums.biotopePlaceholder')" outlined dense :error="!!errors.biotope" :error-message="errors.biotope" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model.number="volume" type="number" :label="t('aquariums.volume')" suffix="L" outlined dense :error="!!errors.volume" :error-message="errors.volume" />
        </div>
        <div class="col-12 col-sm-6">
          <DateInput v-model="date_creation" :label="t('aquariums.filledOn')" :error="!!errors.date_creation" :error-message="errors.date_creation" />
        </div>
        <div class="col-12">
          <div class="text-caption text-grey-7 q-mb-xs">{{ t('aquariums.waterType') }}</div>
          <q-btn-toggle
            v-model="water_type"
            spread
            unelevated
            toggle-color="primary"
            color="grey-2"
            text-color="grey-8"
            :options="[
              { label: t('aquariumInfo.sea'), value: WaterType.sea, icon: 'waves' },
              { label: t('aquariumInfo.fresh'), value: WaterType.pure, icon: 'water_drop' },
            ]"
          />
        </div>
        <div class="col-12">
          <PhotoInput v-model="photoFile" :label="edited ? t('aquariums.newMainPhoto') : t('aquariums.mainPhoto')" />
        </div>
      </div>
    </FormDialog>

    <!-- Informations -->
    <AquariumInfoDialog v-model="dialogInfos" :aquarium="selectedAquarium" />
  </q-page>
</template>

<script setup lang="ts">
import PhotoInput from 'src/components/PhotoInput.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { z } from 'zod';
import { toTypedSchema } from '@vee-validate/zod';
import { useField, useForm } from 'vee-validate';
import FormDialog from 'src/components/FormDialog.vue';
import AquariumInfoDialog from 'src/components/AquariumInfoDialog.vue';
import PhotoGalleryDialog from 'src/components/PhotoGalleryDialog.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import PhotoCard from 'src/components/PhotoCard.vue';
import DateInput from 'src/components/DateInput.vue';
import { useAquariumStore } from '../stores/aquariumStore';
import { WaterType, type Aquarium } from 'src/types/Aquarium';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { pickKeys } from 'src/utils/pick';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl, usePhotoStore } from 'src/stores/photoStore';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, isoDate } from 'src/utils/format';

const { t } = useI18n();
const router = useRouter();
const store = useAquariumStore();
const photoStore = usePhotoStore();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();

const dialog = ref(false);
const dialogInfos = ref(false);
const selectedAquarium = ref<Aquarium | null>(null);
const edited = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const photoFile = ref<File | null>(null);

const imageTimestamp = ref(Date.now());
const galleryOpen = ref(false);
const galleryAquarium = ref<Aquarium | null>(null);

const FIELDS = ['name', 'volume', 'water_type', 'biotope', 'date_creation'] as const;

const v = (key: string) => t(`aquariums.validation.${key}`);
const buildSchema = () =>
  z.object({
    name: z.string().trim().min(4, v('min4')).max(30, v('max30')),
    volume: z.number({ invalid_type_error: v('volumeRequired') }).int(v('integer')).positive(v('positive')),
    water_type: z.nativeEnum(WaterType),
    biotope: z.string().trim().min(4, v('min4')).max(30, v('max30')),
    date_creation: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, v('dateRequired')),
  });
type FormValues = z.infer<ReturnType<typeof buildSchema>>;

// Messages de validation dans la langue courante
const { handleSubmit, errors, resetForm } = useForm({ validationSchema: computed(() => toTypedSchema(buildSchema())) });

const { value: name } = useField<string>('name');
const { value: volume } = useField<number>('volume');
const { value: water_type } = useField<WaterType>('water_type');
const { value: biotope } = useField<string>('biotope');
const { value: date_creation } = useField<string>('date_creation');


function openGallery(aquarium: Aquarium) {
  galleryAquarium.value = aquarium;
  galleryOpen.value = true;
}

// Mode maintenance en cours (changement d'eau) : badge à la place du type d'eau
function inMaintenance(aquarium: Aquarium): boolean {
  return !!aquarium.maintenance_until && new Date(aquarium.maintenance_until).getTime() > Date.now();
}

function goToAquarium(id: number) {
  void router.push(`/aquariums/${id}`);
}

function showCreateDialog() {
  edited.value = false;
  editingId.value = null;
  photoFile.value = null;
  resetForm({
    values: { name: '', volume: 300, water_type: WaterType.sea, biotope: t('aquariums.defaultBiotope'), date_creation: isoDate() },
  });
  dialog.value = true;
}

function showEdit(aquarium: Aquarium) {
  edited.value = true;
  editingId.value = aquarium.id;
  photoFile.value = null;
  resetForm({ values: pickKeys<FormValues>(aquarium, FIELDS) });
  dialog.value = true;
}

function showInfo(aquarium: Aquarium) {
  selectedAquarium.value = aquarium;
  dialogInfos.value = true;
}

function closeDialog() {
  dialog.value = false;
  photoFile.value = null;
}

const submitForm = handleSubmit(async (formValues) => {
  saving.value = true;
  try {
    if (edited.value && editingId.value !== null) {
      await store.update({ ...formValues, id: editingId.value });
      if (photoFile.value) await photoStore.uploadMainPhoto(PhotoEntityType.aquariums, editingId.value, photoFile.value);
    } else {
      await store.add(formValues, photoFile.value ?? undefined);
    }
    imageTimestamp.value = Date.now();
    $q.notify({ type: 'positive', message: edited.value ? t('aquariums.updated') : t('aquariums.added') });
    closeDialog();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('aquariums.saveFailed')) });
  } finally {
    saving.value = false;
  }
});

function onSubmit() {
  void submitForm();
}

function remove(aquarium: Aquarium) {
  confirmRemove(t('aquariums.item', { name: aquarium.name }), () => store.remove(aquarium.id), {
    message: t('aquariums.deleteMessage', { name: aquarium.name }),
  });
}

onMounted(() => {
  void store.fetch();
});
</script>
