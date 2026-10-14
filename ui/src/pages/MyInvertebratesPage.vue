<template>
  <div>
    <PageHeader
      section
      :title="t('livestock.invertebrates.title')"
      :subtitle="t('livestock.invertebrates.subtitle')"
    >
      <template #actions>
        <AppInput v-if="invertebrates.length > 0" v-model="search" icon="search" :placeholder="t('livestock.search')" clearable style="width: 220px" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.invertebrates.add')" @click="showCreateDialog" />
      </template>
    </PageHeader>
    <div v-if="focusId !== null" class="q-mb-sm">
      <q-chip removable color="primary" text-color="white" icon="filter_alt" @remove="clearFocus">
        {{ focusedRows?.[0]?.name ?? t('livestock.focusMissing') }}
      </q-chip>
    </div>

    <EmptyState
      v-if="invertebrates.length === 0"
      icon="pets"
      :title="t('livestock.invertebrates.emptyTitle')"
      :message="t('livestock.invertebrates.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.invertebrates.add')" @click="showCreateDialog" />
    </EmptyState>

    <EmptyState v-else-if="filteredRows.length === 0" icon="search_off" :title="t('livestock.noResult', { search })" />

    <div v-else class="row q-col-gutter-md">
      <div v-for="item in filteredRows" :key="item.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
        <PhotoCard
          :photo="mainPhotoUrl(PhotoEntityType.invertebrates, item.id, imageTimestamp)"
          :title="withQuantity(item.name, item.quantity)"
          :subtitle="item.scientific_name"
          :caption="item.family"
          :meta="item.origin ? { icon: 'place', text: item.origin } : undefined"
          @open="showInfo(item)"
          @gallery="openGallery(item)"
          @edit="showEdit(item)"
          @remove="remove(item)"
        />
      </div>
    </div>

    <!-- Galerie de photos -->
    <PhotoGalleryDialog
      v-if="galleryItem"
      v-model="galleryOpen"
      :entity-type="PhotoEntityType.invertebrates"
      :entity-id="galleryItem.id"
      :entity-label="galleryItem.name"
      @main-changed="imageTimestamp = Date.now()"
    />

    <!-- Création / modification -->
    <FormDialog
      v-model="dialog"
      icon="pets"
      :title="edited ? t('livestock.invertebrates.editTitle') : t('livestock.invertebrates.add')"
      :subtitle="t('livestock.speciesSubtitle')"
      width="600px"
      :loading="saving"
      @submit="onSubmit"
      @hide="closeDialog"
    >
      <SpeciesPicker kind="invertebrates" :aquarium-id="aquaId" @select="applySpecies" />
      <div class="row q-col-gutter-md">
        <div class="col-8 col-sm-4">
          <q-input v-model="name" :label="t('livestock.name')" :placeholder="t('livestock.example', { value: t('livestock.examples.hermit') })" outlined dense :error="!!errors.name" :error-message="errors.name" />
        </div>
        <div class="col-4 col-sm-2">
          <q-input v-model.number="quantity" type="number" min="1" :label="t('livestock.quantity')" outlined dense :error="!!errors.quantity" :error-message="errors.quantity" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="scientific_name" :label="t('livestock.scientificName')" :placeholder="t('livestock.example', { value: 'Clibanarius tricolor' })" outlined dense :error="!!errors.scientific_name" :error-message="errors.scientific_name" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="family" :label="t('livestock.family')" :placeholder="t('livestock.example', { value: 'Diogenidae' })" outlined dense :error="!!errors.family" :error-message="errors.family" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="origin" :label="t('livestock.origin')" :placeholder="t('livestock.example', { value: t('livestock.examples.caribbean') })" outlined dense :error="!!errors.origin" :error-message="errors.origin" />
        </div>
        <div class="col-12 col-sm-6">
          <DateInput v-model="date_acquisition" :label="t('livestock.acquiredOn')" :error="!!errors.date_acquisition" :error-message="errors.date_acquisition" />
        </div>
        <div class="col-12 col-sm-6">
          <PhotoInput v-model="photoFile" :label="edited ? t('livestock.newMainPhoto') : t('livestock.mainPhoto')" />
        </div>
      </div>
    </FormDialog>

    <!-- Informations -->
    <InvertebrateInfoDialog v-model="dialogInfos" :invertebrate="selectedItem" />
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
import InvertebrateInfoDialog from 'src/components/InvertebrateInfoDialog.vue';
import SpeciesPicker from 'src/components/SpeciesPicker.vue';
import PhotoGalleryDialog from 'src/components/PhotoGalleryDialog.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import PhotoCard from 'src/components/PhotoCard.vue';
import DateInput from 'src/components/DateInput.vue';
import type { InvertebrateSpecies } from 'src/types/species';
import { useInvertebrateStore } from '../stores/invertebrateStore';
import type { Invertebrate } from '../types/invertebrate';
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

const store = useInvertebrateStore();
const photoStore = usePhotoStore();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();

const search = ref<string | null>('');
const dialog = ref(false);
const dialogInfos = ref(false);
const selectedItem = ref<Invertebrate | null>(null);
const edited = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const photoFile = ref<File | null>(null);

const imageTimestamp = ref(Date.now());
const galleryOpen = ref(false);
const galleryItem = ref<Invertebrate | null>(null);

const FIELDS = ['name', 'quantity', 'scientific_name', 'family', 'origin', 'date_acquisition'] as const;

const buildSchema = () => z.object({
  quantity: positiveInt(t('livestock.quantityField')),
  name: nameField(),
  scientific_name: nameField(),
  family: nameField(),
  origin: nameField(),
  date_acquisition: isoDateField(),
});
type FormValues = z.infer<ReturnType<typeof buildSchema>>;

const { handleSubmit, errors, setValues, resetForm } = useForm({ validationSchema: computed(() => toTypedSchema(buildSchema())) });

const { value: name } = useField<string>('name');
const { value: quantity } = useField<number>('quantity');
const { value: scientific_name } = useField<string>('scientific_name');
const { value: family } = useField<string>('family');
const { value: origin } = useField<string>('origin');
const { value: date_acquisition } = useField<string>('date_acquisition');


function applySpecies(species: InvertebrateSpecies) {
  setValues({
    name: species.common_name,
    scientific_name: species.scientific_name,
    family: species.family ?? '',
    origin: species.origin ?? '',
  });
}

const invertebrates = computed(() => store.getByAquariumId(props.aquaId));

// Spécimen ouvert depuis un document d'achat : lui seul
const { focusId, clearFocus, focused } = useSpecimenFocus();
const focusedRows = computed(() => focused(invertebrates.value));

const filteredRows = computed(() => {
  if (focusedRows.value) return focusedRows.value;
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return invertebrates.value;
  return invertebrates.value.filter((item) =>
    [item.name, item.scientific_name, item.family, item.origin].some((val) => (val ?? '').toLowerCase().includes(s)),
  );
});

function openGallery(item: Invertebrate) {
  galleryItem.value = item;
  galleryOpen.value = true;
}

function showCreateDialog() {
  edited.value = false;
  editingId.value = null;
  photoFile.value = null;
  resetForm({ values: { name: '', quantity: 1, scientific_name: '', family: '', origin: '', date_acquisition: isoDate() } });
  dialog.value = true;
}

function showEdit(item: Invertebrate) {
  edited.value = true;
  editingId.value = item.id;
  photoFile.value = null;
  resetForm({ values: pickKeys<FormValues>(item, FIELDS) });
  dialog.value = true;
}

function showInfo(item: Invertebrate) {
  selectedItem.value = item;
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
      await store.update({ ...(formValues as unknown as Invertebrate), id: editingId.value, aquarium_id: props.aquaId });
      if (photoFile.value) await photoStore.uploadMainPhoto(PhotoEntityType.invertebrates, editingId.value, photoFile.value);
    } else {
      await store.add({ ...formValues, aquarium_id: props.aquaId }, photoFile.value ?? undefined);
    }
    imageTimestamp.value = Date.now();
    $q.notify({ type: 'positive', message: edited.value ? t('livestock.invertebrates.updated') : t('livestock.invertebrates.added') });
    closeDialog();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('livestock.invertebrates.saveFailed')) });
  } finally {
    saving.value = false;
  }
});

function onSubmit() {
  void submitForm();
}

function remove(item: Invertebrate) {
  confirmRemove(t('livestock.invertebrates.item', { name: item.name }), () => store.remove(item.id));
}

onMounted(() => {
  void store.fetch(props.aquaId);
});
</script>
