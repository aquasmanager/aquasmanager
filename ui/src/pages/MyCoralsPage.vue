<template>
  <div>
    <PageHeader section :title="t('livestock.corals.title')" :subtitle="t('livestock.corals.count', coralCount)">
      <template #actions>
        <AppInput v-if="corals.length > 0" v-model="search" icon="search" :placeholder="t('livestock.search')" clearable style="width: 220px" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.corals.add')" @click="showCreateDialog" />
      </template>
    </PageHeader>
    <div v-if="focusId !== null" class="q-mb-sm">
      <q-chip removable color="primary" text-color="white" icon="filter_alt" @remove="clearFocus">
        {{ focusedRows?.[0]?.name ?? t('livestock.focusMissing') }}
      </q-chip>
    </div>

    <EmptyState
      v-if="corals.length === 0"
      icon="grass"
      :title="t('livestock.corals.emptyTitle')"
      :message="t('livestock.corals.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.corals.add')" @click="showCreateDialog" />
    </EmptyState>

    <EmptyState v-else-if="filteredRows.length === 0" icon="search_off" :title="t('livestock.noResult', { search })" />

    <div v-else class="row q-col-gutter-md">
      <div v-for="coral in filteredRows" :key="coral.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
        <PhotoCard
          :photo="mainPhotoUrl(PhotoEntityType.corals, coral.id, imageTimestamp)"
          :title="withQuantity(coral.name, coral.quantity)"
          :badge="{ label: coral.type, color: 'primary' }"
          :subtitle="coral.scientific_name"
          :caption="coral.family"
          :meta="{ icon: 'wb_sunny', color: 'orange-8', text: t('livestock.lightMetaPar', { min: coral.light_range.min, max: coral.light_range.max, parMin: toPar(coral.light_range.min), parMax: toPar(coral.light_range.max) }) }"
          @open="showInfo(coral)"
          @gallery="openGallery(coral)"
          @edit="showEdit(coral)"
          @remove="remove(coral)"
        >
          <template #actions>
            <q-btn v-if="can.frags" flat round dense size="sm" color="grey-7" icon="content_cut" :to="`/frags?coral=${coral.id}`">
              <q-tooltip>{{ t('livestock.corals.frag') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="canPropose && !inSharedCatalog(coral)" flat round dense size="sm" color="grey-7" icon="volunteer_activism" :aria-label="t('livestock.propose.action')" @click.stop="openPropose(coral)">
              <q-tooltip>{{ t('livestock.propose.action') }}</q-tooltip>
            </q-btn>
          </template>
        </PhotoCard>
      </div>
    </div>

    <!-- Galerie de photos -->
    <PhotoGalleryDialog
      v-if="galleryCoral"
      v-model="galleryOpen"
      :entity-type="PhotoEntityType.corals"
      :entity-id="galleryCoral.id"
      :entity-label="galleryCoral.name"
      @main-changed="imageTimestamp = Date.now()"
    />

    <!-- Création / modification -->
    <FormDialog
      v-model="dialog"
      icon="grass"
      :title="edited ? t('livestock.corals.editTitle') : t('livestock.corals.add')"
      :subtitle="t('livestock.corals.subtitle')"
      width="680px"
      :loading="saving"
      @submit="onSubmit"
      @hide="closeDialog"
    >
      <SpeciesPicker kind="corals" :aquarium-id="aquaId" @select="applySpecies" />
      <div class="row q-col-gutter-md">
        <div class="col-8 col-sm-4">
          <q-input v-model="name" :label="t('livestock.name')" :placeholder="t('livestock.example', { value: 'Euphyllia' })" outlined dense :error="!!errors.name" :error-message="errors.name" />
        </div>
        <div class="col-4 col-sm-2">
          <q-input v-model.number="quantity" type="number" min="1" :label="t('livestock.quantity')" outlined dense :error="!!errors.quantity" :error-message="errors.quantity" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="scientific_name" :label="t('livestock.scientificName')" :placeholder="t('livestock.example', { value: 'Euphyllia ancora' })" outlined dense :error="!!errors.scientific_name" :error-message="errors.scientific_name" />
        </div>
        <div class="col-12 col-sm-4">
          <AppSelect v-model="type" :options="coralTypes" :label="t('livestock.type')" :error="!!errors.type" :error-message="errors.type" />
        </div>
        <div class="col-12 col-sm-4">
          <q-input v-model="family" :label="t('livestock.family')" :placeholder="t('livestock.example', { value: 'Euphylliidae' })" outlined dense :error="!!errors.family" :error-message="errors.family" />
        </div>
        <div class="col-12 col-sm-4">
          <q-input v-model="origin" :label="t('livestock.origin')" :placeholder="t('livestock.example', { value: t('livestock.examples.indonesia') })" outlined dense :error="!!errors.origin" :error-message="errors.origin" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="acquired_from" :label="t('livestock.provenance')" :placeholder="t('livestock.provenancePlaceholder')" outlined dense :hint="t('livestock.provenanceHint')" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="cites" :label="t('livestock.cites')" :placeholder="t('livestock.optional')" outlined dense :error="!!errors.cites" :error-message="errors.cites" />
          <!-- Numéros CITES des factures pour cette espèce -->
          <div v-if="citesSuggestions.length" class="q-mt-xs">
            <div class="text-caption text-grey-7">{{ t('livestock.citesSuggested') }}</div>
            <q-chip
              v-for="s in citesSuggestions"
              :key="`${s.document_id}-${s.number}`"
              dense
              clickable
              :outline="cites !== s.number"
              :color="s.used_by.length ? 'grey-6' : 'teal'"
              :text-color="cites === s.number ? 'white' : undefined"
              icon="receipt_long"
              @click="cites = s.number"
            >
              {{ s.number }}
              <q-tooltip>
                {{ s.document_title }}<span v-if="s.purchase_date"> · {{ formatDate(s.purchase_date) }}</span>
                <template v-if="s.used_by.length"><br />{{ t('livestock.citesUsedBy', { names: s.used_by.join(', ') }) }}</template>
              </q-tooltip>
            </q-chip>
          </div>
        </div>
        <div class="col-12 col-sm-6">
          <DateInput v-model="date_acquisition" :label="t('livestock.acquiredOn')" :error="!!errors.date_acquisition" :error-message="errors.date_acquisition" />
        </div>

        <div class="col-12 col-sm-6">
          <div class="text-caption text-grey-7">
            {{ t('livestock.lightRangePar', { min: light_range.min, max: light_range.max, parMin: toPar(light_range.min), parMax: toPar(light_range.max) }) }}
            <q-icon name="help_outline" size="14px"><q-tooltip>{{ t('livestock.parScale') }}</q-tooltip></q-icon>
          </div>
          <q-range v-model="light_range" :min="1" :max="CORAL_LIGHT_MAX" label markers snap color="primary" />
        </div>
        <div class="col-12 col-sm-6">
          <div class="text-caption text-grey-7">{{ t('livestock.brewingRange') }}</div>
          <q-range v-model="brewing_range" :min="1" :max="10" label markers snap color="primary" />
        </div>
        <div class="col-12 col-sm-4">
          <div class="text-caption text-grey-7">{{ t('livestock.aggressiveness') }}</div>
          <q-slider v-model="aggressiveness_level" :min="1" :max="10" label markers snap color="primary" />
        </div>
        <div class="col-12 col-sm-4">
          <div class="text-caption text-grey-7">{{ t('livestock.resistance') }}</div>
          <q-slider v-model="resistance_level" :min="1" :max="10" label markers snap color="primary" />
        </div>
        <div class="col-12 col-sm-4">
          <div class="text-caption text-grey-7">{{ t('livestock.heightInTank') }}</div>
          <q-slider v-model="location_level" :min="1" :max="10" label markers snap color="primary" />
        </div>

        <div class="col-12">
          <PhotoInput v-model="photoFile" :label="edited ? t('livestock.newMainPhoto') : t('livestock.mainPhoto')" />
        </div>
      </div>
    </FormDialog>

    <!-- Informations -->
    <CoralInfoDialog v-model="dialogInfos" :coral="selectedCoral" />

    <!-- Proposition de l'espèce au catalogue commun -->
    <ProposeSpeciesDialog v-model="proposeOpen" kind="corals" :species="proposed" />
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
import AppSelect from 'src/components/AppSelect.vue';
import FormDialog from 'src/components/FormDialog.vue';
import CoralInfoDialog from 'src/components/CoralInfoDialog.vue';
import SpeciesPicker from 'src/components/SpeciesPicker.vue';
import PhotoGalleryDialog from 'src/components/PhotoGalleryDialog.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import PhotoCard from 'src/components/PhotoCard.vue';
import ProposeSpeciesDialog from 'src/components/ProposeSpeciesDialog.vue';
import { useHubStatus, type SpeciesProposal } from 'src/utils/hub';
import DateInput from 'src/components/DateInput.vue';
import type { CoralSpecies } from 'src/types/species';
import { useCoralStore } from '../stores/coralStore';
import { useSpeciesStore } from 'src/stores/speciesStore';
import { CoralType, type Coral } from '../types/coral';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { pickKeys } from 'src/utils/pick';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl, usePhotoStore } from 'src/stores/photoStore';
import { apiErrorMessage } from 'src/utils/apiError';
import { CORAL_LIGHT_MAX, formatDate, isoDate, toPar, withQuantity } from 'src/utils/format';
import axios from 'axios';
import type { CitesSuggestion } from 'src/types/purchaseDocument';
import { isoDateField, nameField, optionalText, positiveInt } from 'src/utils/validation';

const { t } = useI18n();

const props = defineProps({
  aquaId: { type: Number, required: true },
});

const store = useCoralStore();
const photoStore = usePhotoStore();
const $q = useQuasar();
const can = usePermissions();
const speciesStore = useSpeciesStore();

// Proposer l'espèce de ce corail au catalogue commun (si le hub de l'éditeur répond)
const hub = useHubStatus();
const canPropose = computed(() => !!(hub.value?.suggestions || hub.value?.issues_form_url));
// Noms communs du catalogue commun (espèces intégrées) : rien à proposer pour
// un corail qui y figure déjà. Tant que la liste n'est pas chargée, bouton masqué.
const sharedNames = ref<Set<string> | null>(null);
const normalizeName = (name: string) =>
  name.normalize('NFD').replace(/\p{Diacritic}/gu, '').replace(/\s+/g, ' ').trim().toLowerCase();
const inSharedCatalog = (coral: Coral) => !sharedNames.value || sharedNames.value.has(normalizeName(coral.name));
async function loadSharedNames() {
  try {
    const species = await speciesStore.search('corals');
    sharedNames.value = new Set(species.filter((s) => s.builtin).map((s) => normalizeName(s.common_name)));
  } catch {
    sharedNames.value = null;
  }
}
const proposeOpen = ref(false);
const proposed = ref<SpeciesProposal | null>(null);
function openPropose(coral: Coral) {
  proposed.value = {
    common_name: coral.name,
    scientific_name: coral.scientific_name,
    family: coral.family || null,
    origin: coral.origin || null,
    type: coral.type,
    light_min: coral.light_range.min,
    light_max: coral.light_range.max,
    brewing_min: coral.brewing_range.min,
    brewing_max: coral.brewing_range.max,
    aggressiveness_level: coral.aggressiveness_level,
    resistance_level: coral.resistance_level,
    location_level: coral.location_level,
  };
  proposeOpen.value = true;
}
const { confirmRemove } = useConfirmRemove();

const coralTypes = computed(() =>
  [CoralType.LPS, CoralType.SPS, CoralType.MOU].map((value) => ({ label: t(`livestock.coralTypes.${value}`), value })),
);

const search = ref<string | null>('');
const dialog = ref(false);
const dialogInfos = ref(false);
const selectedCoral = ref<Coral | null>(null);
const edited = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const photoFile = ref<File | null>(null);

const imageTimestamp = ref(Date.now());
const galleryOpen = ref(false);
const galleryCoral = ref<Coral | null>(null);

const level = z.number().int().min(1).max(10);
const range = z.object({ min: level, max: level });
const lightLevel = z.number().int().min(1).max(CORAL_LIGHT_MAX);

const FIELDS = [
  'name',
  'quantity',
  'cites',
  'type',
  'scientific_name',
  'family',
  'origin',
  'acquired_from',
  'light_range',
  'brewing_range',
  'aggressiveness_level',
  'resistance_level',
  'location_level',
  'date_acquisition',
] as const;

const buildSchema = () => z.object({
  quantity: positiveInt(t('livestock.quantityField')),
  name: nameField(),
  cites: optionalText(),
  type: z.nativeEnum(CoralType),
  scientific_name: nameField(),
  family: nameField(),
  origin: nameField(),
  acquired_from: z.string().trim().max(120, t('livestock.errors.max120')).nullable().optional(),
  light_range: z.object({ min: lightLevel, max: lightLevel }),
  brewing_range: range,
  aggressiveness_level: level,
  resistance_level: level,
  location_level: level,
  date_acquisition: isoDateField(),
});
type FormValues = z.infer<ReturnType<typeof buildSchema>>;

const { handleSubmit, errors, setValues, resetForm } = useForm({ validationSchema: computed(() => toTypedSchema(buildSchema())) });

const { value: name } = useField<string>('name');
const { value: quantity } = useField<number>('quantity');
const { value: cites } = useField<string>('cites');
const { value: type } = useField<CoralType>('type');
const { value: scientific_name } = useField<string>('scientific_name');
const { value: family } = useField<string>('family');
const { value: origin } = useField<string>('origin');
const { value: acquired_from } = useField<string | null>('acquired_from');
const { value: light_range } = useField<{ min: number; max: number }>('light_range');
const { value: brewing_range } = useField<{ min: number; max: number }>('brewing_range');
const { value: aggressiveness_level } = useField<number>('aggressiveness_level');
const { value: resistance_level } = useField<number>('resistance_level');
const { value: location_level } = useField<number>('location_level');
const { value: date_acquisition } = useField<string>('date_acquisition');


// Numéros CITES des documents d'achat associés à l'espèce choisie : un seul libre → repris
const citesSuggestions = ref<CitesSuggestion[]>([]);
async function suggestCites(speciesId: number) {
  try {
    citesSuggestions.value = (
      await axios.get<CitesSuggestion[]>('/purchase-documents/cites-suggestions', { params: { coral_species_id: speciesId } })
    ).data;
  } catch {
    citesSuggestions.value = [];
    return;
  }
  const free = citesSuggestions.value.filter((s) => !s.used_by.length);
  if (!edited.value && !cites.value && free.length === 1) {
    cites.value = free[0]!.number;
    $q.notify({ type: 'info', icon: 'receipt_long', message: t('livestock.citesFilled', { number: free[0]!.number, document: free[0]!.document_title }) });
  }
}

function applySpecies(species: CoralSpecies) {
  void suggestCites(species.id);
  setValues({
    name: species.common_name,
    type: species.type,
    scientific_name: species.scientific_name,
    family: species.family ?? '',
    origin: species.origin ?? '',
    light_range: { min: species.light_min, max: species.light_max },
    brewing_range: { min: species.brewing_min, max: species.brewing_max },
    aggressiveness_level: species.aggressiveness_level,
    resistance_level: species.resistance_level,
    location_level: species.location_level,
  });
}

const corals = computed(() => store.getByAquariumId(props.aquaId));
// Individus (quantités), pas seulement les fiches
const coralCount = computed(() => corals.value.reduce((n, x) => n + (x.quantity ?? 1), 0));

// Spécimen ouvert depuis un document d'achat : lui seul
const { focusId, clearFocus, focused } = useSpecimenFocus();
const focusedRows = computed(() => focused(corals.value));

const filteredRows = computed(() => {
  if (focusedRows.value) return focusedRows.value;
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return corals.value;
  return corals.value.filter((coral) =>
    [coral.name, coral.scientific_name, coral.family, coral.origin, coral.type].some((val) =>
      (val ?? '').toLowerCase().includes(s),
    ),
  );
});

function openGallery(coral: Coral) {
  galleryCoral.value = coral;
  galleryOpen.value = true;
}

function showCreateDialog() {
  edited.value = false;
  editingId.value = null;
  citesSuggestions.value = [];
  photoFile.value = null;
  resetForm({
    values: {
      name: '',
      acquired_from: '',
      quantity: 1,
      cites: '',
      type: CoralType.LPS,
      scientific_name: '',
      family: '',
      origin: '',
      light_range: { min: 4, max: 8 },
      brewing_range: { min: 3, max: 7 },
      aggressiveness_level: 5,
      resistance_level: 5,
      location_level: 5,
      date_acquisition: isoDate(),
    },
  });
  dialog.value = true;
}

function showEdit(coral: Coral) {
  edited.value = true;
  editingId.value = coral.id;
  citesSuggestions.value = [];
  photoFile.value = null;
  resetForm({ values: pickKeys<FormValues>(coral, FIELDS) });
  dialog.value = true;
}

function showInfo(coral: Coral) {
  selectedCoral.value = coral;
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
      await store.update({ ...(formValues as unknown as Coral), id: editingId.value, aquarium_id: props.aquaId });
      if (photoFile.value) await photoStore.uploadMainPhoto(PhotoEntityType.corals, editingId.value, photoFile.value);
    } else {
      await store.add({ ...formValues, aquarium_id: props.aquaId }, photoFile.value ?? undefined);
    }
    imageTimestamp.value = Date.now();
    $q.notify({ type: 'positive', message: edited.value ? t('livestock.corals.updated') : t('livestock.corals.added') });
    closeDialog();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('livestock.corals.saveFailed')) });
  } finally {
    saving.value = false;
  }
});

function onSubmit() {
  void submitForm();
}

function remove(coral: Coral) {
  confirmRemove(t('livestock.corals.item', { name: coral.name }), () => store.remove(coral.id));
}

onMounted(() => {
  void store.fetch(props.aquaId);
  void loadSharedNames();
});
</script>
