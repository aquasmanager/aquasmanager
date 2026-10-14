<template>
  <div>
    <PageHeader section :title="t('livestock.fishes.title')" :subtitle="t('livestock.fishes.count', fishCount)">
      <template #actions>
        <AppInput v-if="fishes.length > 0" v-model="search" icon="search" :placeholder="t('livestock.search')" clearable style="width: 220px" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.fishes.add')" @click="showCreateDialog" />
      </template>
    </PageHeader>
    <div v-if="focusId !== null" class="q-mb-sm">
      <q-chip removable color="primary" text-color="white" icon="filter_alt" @remove="clearFocus">
        {{ focusedRows?.[0]?.name ?? t('livestock.focusMissing') }}
      </q-chip>
    </div>

    <EmptyState
      v-if="fishes.length === 0"
      icon="set_meal"
      :title="t('livestock.fishes.emptyTitle')"
      :message="t('livestock.fishes.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.fishes.add')" @click="showCreateDialog" />
    </EmptyState>

    <EmptyState v-else-if="filteredRows.length === 0" icon="search_off" :title="t('livestock.noResult', { search })" />

    <div v-else class="row q-col-gutter-md">
      <div v-for="fish in filteredRows" :key="fish.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
        <PhotoCard
          :photo="mainPhotoUrl(PhotoEntityType.fishes, fish.id, imageTimestamp)"
          :title="withQuantity(fish.name, fish.quantity)"
          :badge="{ label: fish.reef_safe ? t('livestock.reefSafe') : t('livestock.notReefSafe'), color: fish.reef_safe ? 'teal-6' : 'deep-orange-7' }"
          :subtitle="fish.scientific_name"
          :caption="fish.family"
          :meta="{ icon: 'water_drop', text: t('livestock.volumeMeta', { n: fish.min_volume }) }"
          @open="showInfo(fish)"
          @gallery="openGallery(fish)"
          @edit="showEdit(fish)"
          @remove="remove(fish)"
        />
      </div>
    </div>

    <!-- Galerie de photos -->
    <PhotoGalleryDialog
      v-if="galleryFish"
      v-model="galleryOpen"
      :entity-type="PhotoEntityType.fishes"
      :entity-id="galleryFish.id"
      :entity-label="galleryFish.name"
      @main-changed="imageTimestamp = Date.now()"
    />

    <!-- Création / modification -->
    <FormDialog
      v-model="dialog"
      icon="set_meal"
      :title="edited ? t('livestock.fishes.editTitle') : t('livestock.fishes.add')"
      :subtitle="t('livestock.speciesSubtitle')"
      width="640px"
      :loading="saving"
      @submit="onSubmit"
      @hide="closeDialog"
    >
      <SpeciesPicker kind="fishes" :aquarium-id="aquaId" @select="applySpecies" />
      <div class="row q-col-gutter-md">
        <div class="col-8 col-sm-4">
          <q-input v-model="name" :label="t('livestock.commonName')" :placeholder="t('livestock.example', { value: t('livestock.examples.clownfish') })" outlined dense :error="!!errors.name" :error-message="errors.name" />
        </div>
        <div class="col-4 col-sm-2">
          <q-input v-model.number="quantity" type="number" min="1" :label="t('livestock.quantity')" outlined dense :error="!!errors.quantity" :error-message="errors.quantity" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="scientific_name" :label="t('livestock.scientificName')" :placeholder="t('livestock.example', { value: 'Amphiprion ocellaris' })" outlined dense :error="!!errors.scientific_name" :error-message="errors.scientific_name" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="family" :label="t('livestock.family')" :placeholder="t('livestock.example', { value: 'Pomacentridae' })" outlined dense :error="!!errors.family" :error-message="errors.family" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="origin" :label="t('livestock.origin')" :placeholder="t('livestock.example', { value: t('livestock.examples.indoPacific') })" outlined dense :error="!!errors.origin" :error-message="errors.origin" />
        </div>
        <div class="col-6 col-sm-4">
          <q-input v-model.number="max_height" type="number" :label="t('livestock.adultSize')" suffix="cm" outlined dense :error="!!errors.max_height" :error-message="errors.max_height" />
        </div>
        <div class="col-6 col-sm-4">
          <q-input v-model.number="min_volume" type="number" :label="t('livestock.minVolume')" suffix="L" outlined dense :error="!!errors.min_volume" :error-message="errors.min_volume" />
        </div>
        <div class="col-12 col-sm-4">
          <DateInput v-model="date_acquisition" :label="t('livestock.acquiredOn')" :error="!!errors.date_acquisition" :error-message="errors.date_acquisition" />
        </div>
        <div class="col-12 col-sm-6">
          <div class="text-caption text-grey-7 q-mb-xs">{{ t('livestock.reefCompat') }}</div>
          <q-btn-toggle
            v-model="reef_safe"
            spread
            unelevated
            toggle-color="primary"
            color="grey-2"
            text-color="grey-8"
            :options="[
              { label: t('livestock.reefSafe'), value: true },
              { label: t('livestock.notReefSafe'), value: false },
            ]"
          />
        </div>
        <div class="col-12 col-sm-6 self-end">
          <PhotoInput v-model="photoFile" :label="edited ? t('livestock.newMainPhoto') : t('livestock.mainPhoto')" />
        </div>
      </div>
    </FormDialog>

    <!-- Informations -->
    <FishInfoDialog v-model="dialogInfos" :fish="selectedFish" />
  </div>
</template>

<script setup lang="ts">
import PhotoInput from 'src/components/PhotoInput.vue';
import { useI18n } from 'vue-i18n';
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref } from 'vue';
import { useSpecimenFocus } from 'src/composables/useSpecimenFocus';
import { useQuasar } from 'quasar';
import { z } from 'zod';
import { toTypedSchema } from '@vee-validate/zod';
import { useField, useForm } from 'vee-validate';
import AppInput from 'src/components/AppInput.vue';
import FormDialog from 'src/components/FormDialog.vue';
import FishInfoDialog from 'src/components/FishInfoDialog.vue';
import SpeciesPicker from 'src/components/SpeciesPicker.vue';
import PhotoGalleryDialog from 'src/components/PhotoGalleryDialog.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import PhotoCard from 'src/components/PhotoCard.vue';
import DateInput from 'src/components/DateInput.vue';
import type { FishSpecies } from 'src/types/species';
import { useFishStore } from '../stores/fishStore';
import type { Fish } from '../types/fish';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { pickKeys } from 'src/utils/pick';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl, usePhotoStore } from 'src/stores/photoStore';
import { apiErrorMessage } from 'src/utils/apiError';
import { isoDate, withQuantity } from 'src/utils/format';
import { isoDateField, nameField, positiveInt } from 'src/utils/validation';

const { t } = useI18n();

const props = defineProps({
  aquaId: { type: Number, required: true },
});

const store = useFishStore();
const photoStore = usePhotoStore();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();

const search = ref<string | null>('');
const dialog = ref(false);
const dialogInfos = ref(false);
const selectedFish = ref<Fish | null>(null);
const edited = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const photoFile = ref<File | null>(null);

const imageTimestamp = ref(Date.now());
const galleryOpen = ref(false);
const galleryFish = ref<Fish | null>(null);

const FIELDS = ['name', 'quantity', 'scientific_name', 'family', 'origin', 'max_height', 'min_volume', 'reef_safe', 'date_acquisition'] as const;

const buildSchema = () => z.object({
  quantity: positiveInt(t('livestock.quantityField')),
  name: nameField(),
  scientific_name: nameField(),
  family: nameField(),
  origin: nameField(),
  max_height: positiveInt(t('livestock.fishes.sizeField')),
  min_volume: positiveInt(t('livestock.fishes.volumeField')),
  reef_safe: z.boolean(),
  date_acquisition: isoDateField(),
});
type FormValues = z.infer<ReturnType<typeof buildSchema>>;

const { handleSubmit, errors, setValues, resetForm } = useForm({ validationSchema: computed(() => toTypedSchema(buildSchema())) });

const { value: name } = useField<string>('name');
const { value: quantity } = useField<number>('quantity');
const { value: scientific_name } = useField<string>('scientific_name');
const { value: family } = useField<string>('family');
const { value: origin } = useField<string>('origin');
const { value: max_height } = useField<number>('max_height');
const { value: min_volume } = useField<number>('min_volume');
const { value: reef_safe } = useField<boolean>('reef_safe');
const { value: date_acquisition } = useField<string>('date_acquisition');


function applySpecies(species: FishSpecies) {
  setValues({
    name: species.common_name,
    scientific_name: species.scientific_name,
    family: species.family ?? '',
    origin: species.origin ?? '',
    max_height: species.max_height,
    min_volume: species.min_volume,
    reef_safe: species.reef_safe,
  });
}

const fishes = computed(() => store.getByAquariumId(props.aquaId));
// Individus (quantités), pas seulement les fiches
const fishCount = computed(() => fishes.value.reduce((n, x) => n + (x.quantity ?? 1), 0));

// Spécimen ouvert depuis un document d'achat : lui seul
const { focusId, clearFocus, focused } = useSpecimenFocus();
const focusedRows = computed(() => focused(fishes.value));

const filteredRows = computed(() => {
  if (focusedRows.value) return focusedRows.value;
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return fishes.value;
  return fishes.value.filter((fish) =>
    [fish.name, fish.scientific_name, fish.family, fish.origin].some((val) => (val ?? '').toLowerCase().includes(s)),
  );
});

function openGallery(fish: Fish) {
  galleryFish.value = fish;
  galleryOpen.value = true;
}

function showCreateDialog() {
  edited.value = false;
  editingId.value = null;
  photoFile.value = null;
  resetForm({
    values: {
      name: '',
      quantity: 1,
      scientific_name: '',
      family: '',
      origin: '',
      max_height: 10,
      min_volume: 100,
      reef_safe: true,
      date_acquisition: isoDate(),
    },
  });
  dialog.value = true;
}

function showEdit(fish: Fish) {
  edited.value = true;
  editingId.value = fish.id;
  photoFile.value = null;
  resetForm({ values: pickKeys<FormValues>(fish, FIELDS) });
  dialog.value = true;
}

function showInfo(fish: Fish) {
  selectedFish.value = fish;
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
      await store.update({ ...(formValues as unknown as Fish), id: editingId.value, aquarium_id: props.aquaId });
      if (photoFile.value) await photoStore.uploadMainPhoto(PhotoEntityType.fishes, editingId.value, photoFile.value);
    } else {
      await store.add({ ...formValues, aquarium_id: props.aquaId }, photoFile.value ?? undefined);
    }
    imageTimestamp.value = Date.now();
    $q.notify({ type: 'positive', message: edited.value ? t('livestock.fishes.updated') : t('livestock.fishes.added') });
    closeDialog();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('livestock.fishes.saveFailed')) });
  } finally {
    saving.value = false;
  }
});

function onSubmit() {
  void submitForm();
}

function remove(fish: Fish) {
  confirmRemove(t('livestock.fishes.item', { name: fish.name }), () => store.remove(fish.id));
}

onMounted(() => {
  void store.fetch(props.aquaId);
});
</script>
