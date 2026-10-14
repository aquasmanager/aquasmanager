<template>
  <div>
    <PageHeader section :title="t('livestock.plants.title')" :subtitle="t('livestock.plants.count', plantCount)">
      <template #actions>
        <AppInput v-if="plants.length > 0" v-model="search" icon="search" :placeholder="t('livestock.search')" clearable style="width: 220px" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.plants.add')" @click="showCreateDialog" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="plants.length === 0"
      icon="local_florist"
      :title="t('livestock.plants.emptyTitle')"
      :message="t('livestock.plants.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.plants.add')" @click="showCreateDialog" />
    </EmptyState>

    <EmptyState v-else-if="filteredRows.length === 0" icon="search_off" :title="t('livestock.noResult', { search })" />

    <div v-else class="row q-col-gutter-md">
      <div v-for="plant in filteredRows" :key="plant.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
        <PhotoCard
          :photo="mainPhotoUrl(PhotoEntityType.plants, plant.id, imageTimestamp)"
          :title="withQuantity(plant.name, plant.quantity)"
          :badge="{ label: t(`livestock.growingSpeed.${plant.growing}`), color: 'green-7' }"
          :subtitle="plant.scientific_name"
          :caption="t('livestock.heightMeta', { location: t(`livestock.plantLocation.${plant.location}`), n: plant.max_height })"
          :meta="{ icon: 'thermostat', color: 'red-6', text: `${plant.temperature_range.min}-${plant.temperature_range.max} °C` }"
          @open="showInfo(plant)"
          @gallery="openGallery(plant)"
          @edit="showEdit(plant)"
          @remove="remove(plant)"
        />
      </div>
    </div>

    <!-- Galerie de photos -->
    <PhotoGalleryDialog
      v-if="galleryPlant"
      v-model="galleryOpen"
      :entity-type="PhotoEntityType.plants"
      :entity-id="galleryPlant.id"
      :entity-label="galleryPlant.name"
      @main-changed="imageTimestamp = Date.now()"
    />

    <!-- Création / modification -->
    <FormDialog
      v-model="dialog"
      icon="local_florist"
      :title="edited ? t('livestock.plants.editTitle') : t('livestock.plants.add')"
      :subtitle="t('livestock.plants.subtitle')"
      width="680px"
      :loading="saving"
      @submit="onSubmit"
      @hide="closeDialog"
    >
      <SpeciesPicker kind="plants" :aquarium-id="aquaId" @select="applySpecies" />
      <div class="row q-col-gutter-md">
        <div class="col-8 col-sm-4">
          <q-input v-model="name" :label="t('livestock.name')" :placeholder="t('livestock.example', { value: 'Anubias nana' })" outlined dense :error="!!errors.name" :error-message="errors.name" />
        </div>
        <div class="col-4 col-sm-2">
          <q-input v-model.number="quantity" type="number" min="1" :label="t('livestock.quantity')" outlined dense :error="!!errors.quantity" :error-message="errors.quantity" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="scientific_name" :label="t('livestock.scientificName')" outlined dense :error="!!errors.scientific_name" :error-message="errors.scientific_name" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="family" :label="t('livestock.family')" :placeholder="t('livestock.example', { value: 'Araceae' })" outlined dense :error="!!errors.family" :error-message="errors.family" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="origin" :label="t('livestock.origin')" :placeholder="t('livestock.example', { value: t('livestock.examples.westAfrica') })" outlined dense :error="!!errors.origin" :error-message="errors.origin" />
        </div>
        <div class="col-12 col-sm-4">
          <AppSelect v-model="growing" :options="growingOptions" :label="t('livestock.growing')" :error="!!errors.growing" :error-message="errors.growing" />
        </div>
        <div class="col-12 col-sm-4">
          <AppSelect v-model="location" :options="locationOptions" :label="t('livestock.location')" :error="!!errors.location" :error-message="errors.location" />
        </div>
        <div class="col-12 col-sm-4">
          <q-input v-model.number="max_height" type="number" :label="t('livestock.maxHeight')" suffix="cm" outlined dense :error="!!errors.max_height" :error-message="errors.max_height" />
        </div>

        <div class="col-12 col-sm-6">
          <div class="text-caption text-grey-7">{{ t('livestock.lightRange') }}</div>
          <q-range v-model="light_range" :min="1" :max="10" label markers snap color="primary" />
        </div>
        <div class="col-12 col-sm-6">
          <div class="text-caption text-grey-7">{{ t('livestock.temperatureRange') }}</div>
          <q-range v-model="temperature_range" :min="10" :max="35" label snap color="primary" />
        </div>
        <div class="col-12 col-sm-6">
          <div class="text-caption text-grey-7">{{ t('livestock.resistance') }}</div>
          <q-slider v-model="resistance_level" :min="1" :max="10" label markers snap color="primary" />
        </div>
        <div class="col-12 col-sm-6">
          <DateInput v-model="date_acquisition" :label="t('livestock.acquiredOnF')" :error="!!errors.date_acquisition" :error-message="errors.date_acquisition" />
        </div>
        <div class="col-12">
          <PhotoInput v-model="photoFile" :label="edited ? t('livestock.newMainPhoto') : t('livestock.mainPhoto')" />
        </div>
      </div>
    </FormDialog>

    <!-- Informations -->
    <PlantInfoDialog v-model="dialogInfos" :plant="selectedPlant" />
  </div>
</template>

<script setup lang="ts">
import PhotoInput from 'src/components/PhotoInput.vue';
import { useI18n } from 'vue-i18n';
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { z } from 'zod';
import { toTypedSchema } from '@vee-validate/zod';
import { useField, useForm } from 'vee-validate';
import AppInput from 'src/components/AppInput.vue';
import AppSelect from 'src/components/AppSelect.vue';
import FormDialog from 'src/components/FormDialog.vue';
import PlantInfoDialog from 'src/components/PlantInfoDialog.vue';
import SpeciesPicker from 'src/components/SpeciesPicker.vue';
import PhotoGalleryDialog from 'src/components/PhotoGalleryDialog.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import PhotoCard from 'src/components/PhotoCard.vue';
import DateInput from 'src/components/DateInput.vue';
import type { PlantSpecies } from 'src/types/species';
import { usePlantStore } from '../stores/plantStore';
import { PlantGrowing, PlantLocation, type Plant } from '../types/plant';
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

const store = usePlantStore();
const photoStore = usePhotoStore();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();

const growingOptions = computed(() =>
  Object.values(PlantGrowing).map((value) => ({ value, label: t(`livestock.growingSpeed.${value}`) })),
);
const locationOptions = computed(() =>
  Object.values(PlantLocation).map((value) => ({ value, label: t(`livestock.plantLocation.${value}`) })),
);

const search = ref<string | null>('');
const dialog = ref(false);
const dialogInfos = ref(false);
const selectedPlant = ref<Plant | null>(null);
const edited = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const photoFile = ref<File | null>(null);

const imageTimestamp = ref(Date.now());
const galleryOpen = ref(false);
const galleryPlant = ref<Plant | null>(null);

const FIELDS = [
  'name',
  'quantity',
  'scientific_name',
  'family',
  'origin',
  'light_range',
  'temperature_range',
  'growing',
  'resistance_level',
  'max_height',
  'location',
  'date_acquisition',
] as const;

// Mêmes bornes que l'API : lumière 1-10, température 10-35 °C, hauteur 1-50 cm
const buildSchema = () => z.object({
  quantity: positiveInt(t('livestock.quantityField')),
  name: nameField(),
  scientific_name: nameField(),
  family: nameField(),
  origin: nameField(),
  light_range: z.object({ min: z.number().int().min(1).max(10), max: z.number().int().min(1).max(10) }),
  temperature_range: z.object({ min: z.number().int().min(10).max(35), max: z.number().int().min(10).max(35) }),
  growing: z.nativeEnum(PlantGrowing, { required_error: t('livestock.errors.growingRequired') }),
  resistance_level: z.number().int().min(1).max(10),
  max_height: z
    .number({ invalid_type_error: t('livestock.errors.heightRequired') })
    .int(t('livestock.errors.integer'))
    .min(1, t('livestock.errors.min1cm'))
    .max(50, t('livestock.errors.max50cm')),
  location: z.nativeEnum(PlantLocation, { required_error: t('livestock.errors.locationRequired') }),
  date_acquisition: isoDateField(),
});
type FormValues = z.infer<ReturnType<typeof buildSchema>>;

const { handleSubmit, errors, setValues, resetForm } = useForm({ validationSchema: computed(() => toTypedSchema(buildSchema())) });

const { value: name } = useField<string>('name');
const { value: quantity } = useField<number>('quantity');
const { value: scientific_name } = useField<string>('scientific_name');
const { value: family } = useField<string>('family');
const { value: origin } = useField<string>('origin');
const { value: light_range } = useField<{ min: number; max: number }>('light_range');
const { value: temperature_range } = useField<{ min: number; max: number }>('temperature_range');
const { value: growing } = useField<PlantGrowing>('growing');
const { value: resistance_level } = useField<number>('resistance_level');
const { value: max_height } = useField<number>('max_height');
const { value: location } = useField<PlantLocation>('location');
const { value: date_acquisition } = useField<string>('date_acquisition');


function applySpecies(species: PlantSpecies) {
  setValues({
    name: species.common_name,
    scientific_name: species.scientific_name,
    family: species.family ?? '',
    origin: species.origin ?? '',
    light_range: { min: species.light_min, max: species.light_max },
    temperature_range: { min: species.temperature_min, max: species.temperature_max },
    growing: species.growing,
    resistance_level: species.resistance_level,
    max_height: species.max_height,
    location: species.location,
  });
}

const plants = computed(() => store.getByAquariumId(props.aquaId));
// Individus (quantités), pas seulement les fiches
const plantCount = computed(() => plants.value.reduce((n, x) => n + (x.quantity ?? 1), 0));

const filteredRows = computed(() => {
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return plants.value;
  return plants.value.filter((plant) =>
    [plant.name, plant.scientific_name, plant.family, plant.origin].some((val) => (val ?? '').toLowerCase().includes(s)),
  );
});

function openGallery(plant: Plant) {
  galleryPlant.value = plant;
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
      light_range: { min: 3, max: 7 },
      temperature_range: { min: 22, max: 28 },
      growing: PlantGrowing.average,
      resistance_level: 5,
      max_height: 20,
      location: PlantLocation.middle,
      date_acquisition: isoDate(),
    },
  });
  dialog.value = true;
}

function showEdit(plant: Plant) {
  edited.value = true;
  editingId.value = plant.id;
  photoFile.value = null;
  resetForm({ values: pickKeys<FormValues>(plant, FIELDS) });
  dialog.value = true;
}

function showInfo(plant: Plant) {
  selectedPlant.value = plant;
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
      await store.update({ ...(formValues as unknown as Plant), id: editingId.value, aquarium_id: props.aquaId });
      if (photoFile.value) await photoStore.uploadMainPhoto(PhotoEntityType.plants, editingId.value, photoFile.value);
    } else {
      await store.add({ ...formValues, aquarium_id: props.aquaId }, photoFile.value ?? undefined);
    }
    imageTimestamp.value = Date.now();
    $q.notify({ type: 'positive', message: edited.value ? t('livestock.plants.updated') : t('livestock.plants.added') });
    closeDialog();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('livestock.plants.saveFailed')) });
  } finally {
    saving.value = false;
  }
});

function onSubmit() {
  void submitForm();
}

function remove(plant: Plant) {
  confirmRemove(t('livestock.plants.item', { name: plant.name }), () => store.remove(plant.id));
}

onMounted(() => {
  void store.fetch(props.aquaId);
});
</script>
