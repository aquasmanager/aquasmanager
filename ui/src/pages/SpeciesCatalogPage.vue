<template>
  <q-page class="app-page">
    <PageHeader icon="menu_book" :title="t('livestock.catalog.title')" :subtitle="t('livestock.catalog.subtitle')">
      <template #actions>
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('livestock.catalog.add')" @click="openCreate" />
      </template>
    </PageHeader>

    <q-card flat bordered class="q-mb-md">
      <q-tabs v-model="kind" dense align="left" active-color="primary" indicator-color="primary" class="text-grey-7">
        <q-tab name="fishes" icon="set_meal" :label="t('livestock.fishes.title')" />
        <q-tab name="corals" icon="grass" :label="t('livestock.corals.title')" />
        <q-tab name="plants" icon="local_florist" :label="t('livestock.plants.title')" />
        <q-tab name="invertebrates" icon="pets" :label="t('livestock.invertebrates.title')" />
      </q-tabs>
    </q-card>

    <!-- Catalogue commun : synchronisé depuis le hub de l'éditeur -->
    <div v-if="sync?.enabled" class="row items-center gap-sm q-mb-sm text-caption text-grey-7">
      <q-icon :name="sync.error ? 'cloud_off' : 'cloud_done'" :color="sync.error ? 'warning' : 'positive'" size="16px" />
      <span v-if="sync.applied_at">{{ t('livestock.catalog.sync.updated', { date: formatDateTime(sync.applied_at) }) }}</span>
      <span v-else>{{ t('livestock.catalog.sync.never') }}</span>
      <span v-if="sync.error" class="text-warning">· {{ t('livestock.catalog.sync.failed') }}<q-tooltip>{{ sync.error }}</q-tooltip></span>
      <q-btn v-if="can.manage" flat dense no-caps size="sm" color="primary" icon="sync" :label="t('livestock.catalog.sync.now')" :loading="syncing" @click="syncNow" />
    </div>

    <div class="row items-center gap-sm q-mb-md">
      <AppInput v-model="search" :placeholder="t('livestock.catalog.search')" icon="search" clearable style="width: 320px; max-width: 100%" />
      <q-btn-toggle
        v-if="hasWaterType"
        v-model="waterFilter"
        unelevated
        toggle-color="primary"
        color="grey-2"
        text-color="grey-8"
        :options="[
          { label: t('livestock.catalog.all'), value: 'all' },
          { label: t('livestock.catalog.sea'), value: 'sea' },
          { label: t('livestock.catalog.fresh'), value: 'pure' },
        ]"
      />
    </div>

    <q-card flat bordered>
    <AppTable
      :rows="filteredRows"
      :columns="columns"
      row-key="id"
      :loading="loading"
      :pagination="{ rowsPerPage: 25, sortBy: 'common_name' }"
      :no-data-label="t('livestock.catalog.empty')"
    >
      <template #body-cell-common_name="props">
        <q-td :props="props">
          <div class="text-weight-medium">{{ props.row.common_name }}</div>
          <div class="text-caption text-italic text-grey-7">
            {{ props.row.scientific_name }}
            <q-badge v-if="props.row.customized" outline color="grey-7" class="q-ml-xs" :label="t('livestock.catalog.sync.customized')">
              <q-tooltip max-width="260px">{{ t('livestock.catalog.sync.customizedHint') }}</q-tooltip>
            </q-badge>
          </div>
          <div v-if="props.row.notes" class="text-caption text-grey-8 species-notes">
            {{ props.row.notes }}
            <q-tooltip max-width="320px">{{ props.row.notes }}</q-tooltip>
          </div>
        </q-td>
      </template>
      <template #body-cell-water_type="props">
        <q-td :props="props">
          <q-chip dense :color="props.value === 'sea' ? 'blue-1' : 'green-1'" :text-color="props.value === 'sea' ? 'blue-9' : 'green-9'">
            {{ props.value === 'sea' ? t('livestock.catalog.seaShort') : t('livestock.catalog.freshShort') }}
          </q-chip>
        </q-td>
      </template>
      <template #body-cell-reef_safe="props">
        <q-td :props="props">
          <q-icon
            v-if="props.row.water_type === 'sea'"
            :name="props.value ? 'check_circle' : 'cancel'"
            :color="props.value ? 'positive' : 'negative'"
          />
          <span v-else class="text-grey-5">—</span>
        </q-td>
      </template>
      <template #body-cell-actions="props">
        <q-td :props="props" class="q-gutter-xs text-no-wrap">
          <q-btn v-if="props.row.link" flat round dense icon="open_in_new" :href="props.row.link" target="_blank">
            <q-tooltip>{{ t('livestock.picker.reference') }}</q-tooltip>
          </q-btn>
          <q-btn v-if="can.edit" flat round dense icon="edit" color="grey-7" @click="openEdit(props.row)">
            <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
          </q-btn>
          <q-btn v-if="can.manage" flat round dense icon="delete" color="negative" @click="removeSpecies(props.row)">
            <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
          </q-btn>
          <!-- Espèce ajoutée ici : proposable au catalogue commun (hub de l'éditeur) -->
          <q-btn
            v-if="canPropose && !props.row.builtin"
            flat
            round
            dense
            icon="volunteer_activism"
            color="primary"
            :aria-label="t('livestock.propose.action')"
            @click="openPropose(props.row)"
          >
            <q-tooltip>{{ t('livestock.propose.action') }}</q-tooltip>
          </q-btn>
        </q-td>
      </template>
    </AppTable>
    </q-card>

    <ProposeSpeciesDialog v-model="proposeOpen" :kind="kind" :species="proposed" />
    <ProposeCorrectionDialog
      v-if="editingRow"
      v-model="correctionOpen"
      :kind="kind"
      :common-name="editingRow.common_name"
      :scientific-name="editingRow.scientific_name"
      :changes="correctionChanges"
    />

    <FormDialog
      v-model="dialog"
      icon="menu_book"
      :title="editingId ? t('livestock.catalog.editTitle') : t('livestock.catalog.addTitle', { kind: t(`livestock.catalog.kinds.${kind}`) })"
      :subtitle="t('livestock.catalog.formSubtitle')"
      width="600px"
      :submit-label="editingId ? t('common.save') : t('actions.add')"
      :loading="saving"
      @submit="save"
    >
        <template v-if="canCorrect" #footer-left>
          <q-btn flat no-caps color="primary" icon="rate_review" :label="t('livestock.correct.action')" @click="openCorrection" />
        </template>
        <div class="row q-col-gutter-sm">
          <div class="col-12 col-sm-6">
            <q-input v-model="form.common_name" :label="t('livestock.catalog.commonName')" outlined dense maxlength="30" />
          </div>
          <div class="col-12 col-sm-6">
            <q-input v-model="form.scientific_name" :label="t('livestock.scientificName')" outlined dense maxlength="30" />
          </div>
          <div class="col-12 col-sm-6">
            <q-input v-model="form.family" :label="t('livestock.familyLabel')" outlined dense maxlength="30" />
          </div>
          <div class="col-12 col-sm-6">
            <q-input v-model="form.origin" :label="t('livestock.originLabel')" outlined dense maxlength="30" />
          </div>

          <div v-if="hasWaterType" class="col-12 col-sm-6">
            <q-select v-model="form.water_type" :options="waterOptions" emit-value map-options :label="t('livestock.catalog.waterType')" outlined dense />
          </div>
          <div v-if="kind === 'invertebrates'" class="col-12 col-sm-6">
            <q-select v-model="form.category" :options="categoryOptions" emit-value map-options :label="t('livestock.catalog.category')" outlined dense />
          </div>

          <template v-if="kind === 'fishes'">
            <div class="col-6 col-sm-4">
              <q-input v-model.number="form.max_height" type="number" :label="t('livestock.catalog.maxSizeCm')" outlined dense />
            </div>
          </template>
          <template v-if="kind === 'fishes' || kind === 'invertebrates'">
            <div class="col-6 col-sm-4">
              <q-input v-model.number="form.min_volume" type="number" :label="t('livestock.catalog.minVolumeL')" outlined dense />
            </div>
            <div v-if="form.water_type === 'sea'" class="col-12 col-sm-4 flex items-center">
              <q-toggle v-model="form.reef_safe" :label="t('livestock.catalog.reefCompatible')" />
            </div>
          </template>

          <template v-if="kind === 'corals'">
            <div class="col-12 col-sm-4">
              <q-select v-model="form.type" :options="['SPS', 'LPS', 'MOU']" :label="t('livestock.type')" outlined dense />
            </div>
            <div class="col-12 col-sm-8">
              <div class="text-caption text-grey-7">{{ t('livestock.catalog.lightPar', { min: form.light.min, max: form.light.max, parMin: toPar(form.light.min), parMax: toPar(form.light.max) }) }}
                <q-icon name="help_outline" size="14px"><q-tooltip>{{ t('livestock.parScale') }}</q-tooltip></q-icon>
              </div>
              <q-range v-model="form.light" :min="1" :max="CORAL_LIGHT_MAX" :step="1" markers snap color="amber-8" />
            </div>
            <div class="col-12 col-sm-6">
              <div class="text-caption text-grey-7">{{ t('livestock.catalog.brewingValue', { min: form.brewing.min, max: form.brewing.max }) }}</div>
              <q-range v-model="form.brewing" :min="1" :max="10" :step="1" markers snap color="blue-6" />
            </div>
            <div class="col-12 col-sm-6">
              <div class="text-caption text-grey-7">{{ t('livestock.catalog.aggressivenessValue', { n: form.aggressiveness_level }) }}</div>
              <q-slider v-model="form.aggressiveness_level" :min="1" :max="10" markers snap color="negative" />
            </div>
            <div class="col-12 col-sm-6">
              <div class="text-caption text-grey-7">{{ t('livestock.catalog.placementValue', { n: form.location_level }) }}</div>
              <q-slider v-model="form.location_level" :min="1" :max="10" markers snap color="teal" />
            </div>
          </template>

          <template v-if="kind === 'plants'">
            <div class="col-12 col-sm-6">
              <div class="text-caption text-grey-7">{{ t('livestock.catalog.lightValue', { min: form.light.min, max: form.light.max }) }}</div>
              <q-range v-model="form.light" :min="1" :max="10" :step="1" markers snap color="amber-8" />
            </div>
            <div class="col-12 col-sm-6">
              <div class="text-caption text-grey-7">{{ t('livestock.catalog.temperatureValue', { min: form.temperature.min, max: form.temperature.max }) }}</div>
              <q-range v-model="form.temperature" :min="10" :max="35" :step="1" color="red-6" />
            </div>
            <div class="col-6 col-sm-4">
              <q-select v-model="form.growing" :options="growingOptions" emit-value map-options :label="t('livestock.growing')" outlined dense />
            </div>
            <div class="col-6 col-sm-4">
              <q-select v-model="form.location" :options="locationOptions" emit-value map-options :label="t('livestock.location')" outlined dense />
            </div>
            <div class="col-12 col-sm-4">
              <q-input v-model.number="form.max_height" type="number" :label="t('livestock.catalog.maxHeightCm')" outlined dense />
            </div>
          </template>

          <div v-if="kind === 'corals' || kind === 'plants'" class="col-12 col-sm-6">
            <div class="text-caption text-grey-7">{{ t('livestock.catalog.resistanceValue', { n: form.resistance_level }) }}</div>
            <q-slider v-model="form.resistance_level" :min="1" :max="10" markers snap color="positive" />
          </div>

          <div class="col-12">
            <q-input v-model="form.notes" :label="t('livestock.catalog.notes')" :hint="t('livestock.catalog.notesHint')" type="textarea" autogrow outlined dense maxlength="1000" />
          </div>
          <div class="col-12">
            <q-input v-model="form.link" :label="t('livestock.catalog.link')" outlined dense maxlength="300" />
          </div>
        </div>
    </FormDialog>
  </q-page>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { CORAL_LIGHT_MAX, formatDateTime, toPar } from 'src/utils/format';
import axios from 'axios';
import AppTable from 'src/components/AppTable.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref, watch } from 'vue';
import { useQuasar, type QTableColumn } from 'quasar';
import PageHeader from 'src/components/PageHeader.vue';
import FormDialog from 'src/components/FormDialog.vue';
import ProposeSpeciesDialog from 'src/components/ProposeSpeciesDialog.vue';
import ProposeCorrectionDialog from 'src/components/ProposeCorrectionDialog.vue';
import { useHubStatus, type SpeciesChanges, type SpeciesProposal } from 'src/utils/hub';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import AppInput from 'src/components/AppInput.vue';
import { useSpeciesStore } from 'src/stores/speciesStore';
import { CoralType } from 'src/types/coral';
import { PlantGrowing, PlantLocation } from 'src/types/plant';
import {
  INVERTEBRATE_CATEGORIES,
  type InvertebrateCategory,
  type SpeciesByKind,
  type SpeciesKind,
  type SpeciesWaterType,
} from 'src/types/species';

const { t } = useI18n();

type AnySpecies = SpeciesByKind[SpeciesKind];

const $q = useQuasar();
const waterOptions = computed(() => [
  { label: t('livestock.catalog.sea'), value: 'sea' },
  { label: t('livestock.catalog.fresh'), value: 'pure' },
]);
const categoryOptions = computed(() => INVERTEBRATE_CATEGORIES.map((value) => ({ value, label: t(`livestock.categories.${value}`) })));
const growingOptions = computed(() => Object.values(PlantGrowing).map((value) => ({ value, label: t(`livestock.growingSpeed.${value}`) })));
const locationOptions = computed(() => Object.values(PlantLocation).map((value) => ({ value, label: t(`livestock.plantLocation.${value}`) })));
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const store = useSpeciesStore();

// Proposition au catalogue commun : bouton affiché si le hub répond
const hub = useHubStatus();
const canPropose = computed(() => !!(hub.value?.suggestions || hub.value?.issues_form_url));
const proposeOpen = ref(false);
const proposed = ref<SpeciesProposal | null>(null);
function openPropose(row: AnySpecies) {
  // Fiche envoyée sans les champs propres à cette installation
  const species: Record<string, unknown> = { ...row };
  for (const key of ['id', 'builtin', 'warnings']) delete species[key];
  proposed.value = species as SpeciesProposal;
  proposeOpen.value = true;
}

const kind = ref<SpeciesKind>('fishes');
const search = ref<string | null>('');
const waterFilter = ref<'all' | SpeciesWaterType>('all');
const rowsByKind = ref<{ [K in SpeciesKind]: SpeciesByKind[K][] }>({ fishes: [], corals: [], plants: [], invertebrates: [] });
const loading = ref(false);
const saving = ref(false);

const hasWaterType = computed(() => kind.value === 'fishes' || kind.value === 'invertebrates');

// Colonnes recalculées au changement de langue
const columns = computed<QTableColumn[]>(() => {
  const nameColumn: QTableColumn = { name: 'common_name', label: t('livestock.catalog.columns.species'), field: 'common_name', align: 'left', sortable: true };
  const familyColumn: QTableColumn = { name: 'family', label: t('livestock.familyLabel'), field: 'family', align: 'left', sortable: true };
  const waterColumn: QTableColumn = { name: 'water_type', label: t('livestock.catalog.columns.water'), field: 'water_type', align: 'left', sortable: true };
  const volumeColumn: QTableColumn = {
    name: 'min_volume',
    label: t('livestock.catalog.columns.volumeMin'),
    field: 'min_volume',
    format: (v: number) => `${v} L`,
    sortable: true,
  };
  const reefColumn: QTableColumn = { name: 'reef_safe', label: t('livestock.catalog.columns.reef'), field: 'reef_safe', align: 'center' };
  const actionsColumn: QTableColumn = { name: 'actions', label: '', field: 'id', align: 'right' };

  const COLUMNS: Record<SpeciesKind, QTableColumn[]> = {
    fishes: [
      nameColumn,
      waterColumn,
      familyColumn,
      { name: 'max_height', label: t('livestock.catalog.columns.sizeMax'), field: 'max_height', format: (v: number) => `${v} cm`, sortable: true },
      volumeColumn,
      reefColumn,
      actionsColumn,
    ],
    corals: [
      nameColumn,
      { name: 'type', label: t('livestock.catalog.columns.type'), field: 'type', align: 'left', sortable: true },
      familyColumn,
      { name: 'light', label: t('livestock.light'), field: (r: SpeciesByKind['corals']) => `${r.light_min}–${r.light_max} (${toPar(r.light_min)}–${toPar(r.light_max)} PAR)`, align: 'center' },
      { name: 'brewing', label: t('livestock.brewing'), field: (r: SpeciesByKind['corals']) => `${r.brewing_min}–${r.brewing_max}`, align: 'center' },
      { name: 'aggressiveness_level', label: t('livestock.aggressiveness'), field: 'aggressiveness_level', align: 'center', sortable: true },
      { name: 'resistance_level', label: t('livestock.resistance'), field: 'resistance_level', align: 'center', sortable: true },
      actionsColumn,
    ],
    plants: [
      nameColumn,
      familyColumn,
      { name: 'light', label: t('livestock.light'), field: (r: SpeciesByKind['plants']) => `${r.light_min}–${r.light_max}`, align: 'center' },
      {
        name: 'temperature',
        label: t('livestock.temperature'),
        field: (r: SpeciesByKind['plants']) => `${r.temperature_min}–${r.temperature_max} °C`,
        align: 'center',
      },
      { name: 'growing', label: t('livestock.catalog.columns.growing'), field: 'growing', format: (v: PlantGrowing) => t(`livestock.growingSpeed.${v}`), sortable: true },
      { name: 'location', label: t('livestock.catalog.columns.location'), field: 'location', format: (v: PlantLocation) => t(`livestock.plantLocation.${v}`), sortable: true },
      { name: 'max_height', label: t('livestock.catalog.columns.heightMax'), field: 'max_height', format: (v: number) => `${v} cm`, sortable: true },
      actionsColumn,
    ],
    invertebrates: [
      nameColumn,
      waterColumn,
      {
        name: 'category',
        label: t('livestock.catalog.columns.category'),
        field: 'category',
        format: (v: InvertebrateCategory) => t(`livestock.categories.${v}`),
        sortable: true,
      },
      familyColumn,
      volumeColumn,
      reefColumn,
      actionsColumn,
    ],
  };
  return COLUMNS[kind.value];
});

const filteredRows = computed<AnySpecies[]>(() => {
  let rows: AnySpecies[] = rowsByKind.value[kind.value];
  if (hasWaterType.value && waterFilter.value !== 'all') {
    rows = rows.filter((r) => 'water_type' in r && r.water_type === waterFilter.value);
  }
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return rows;
  return rows.filter((r) => r.common_name.toLowerCase().includes(s) || r.scientific_name.toLowerCase().includes(s));
});

async function load() {
  loading.value = true;
  try {
    const [fishes, corals, plants, invertebrates] = await Promise.all([
      store.search('fishes'),
      store.search('corals'),
      store.search('plants'),
      store.search('invertebrates'),
    ]);
    rowsByKind.value = { fishes, corals, plants, invertebrates };
  } catch {
    $q.notify({ type: 'negative', message: t('livestock.catalog.loadFailed') });
  } finally {
    loading.value = false;
  }
}

// --- Formulaire : champs de tous les types, seuls ceux du type courant sont envoyés ---
function emptyForm() {
  return {
    common_name: '',
    scientific_name: '',
    family: '',
    origin: '',
    notes: '',
    link: '',
    water_type: waterFilter.value === 'pure' ? 'pure' : 'sea',
    max_height: null as number | null,
    min_volume: null as number | null,
    reef_safe: true,
    category: 'shrimp' as InvertebrateCategory,
    type: CoralType.LPS as CoralType,
    light: { min: 2, max: 4 },
    brewing: { min: 3, max: 5 },
    temperature: { min: 22, max: 28 },
    growing: PlantGrowing.average as PlantGrowing,
    location: PlantLocation.middle as PlantLocation,
    aggressiveness_level: 3,
    resistance_level: 6,
    location_level: 5,
  };
}

const dialog = ref(false);
const editingId = ref<number | null>(null);
const form = ref(emptyForm());

function openCreate() {
  editingId.value = null;
  editingRow.value = null;
  form.value = emptyForm();
  dialog.value = true;
}

// Espèce du catalogue commun en cours d'édition : base des propositions de correction
const editingRow = ref<AnySpecies | null>(null);
const correctionOpen = ref(false);
const correctionChanges = ref<SpeciesChanges>({});
const canCorrect = computed(() => !!editingRow.value?.builtin && !!hub.value?.corrections);

function openCorrection() {
  const original = editingRow.value as unknown as Record<string, string | number | boolean | null> | null;
  if (!original) return;
  let payload: Record<string, string | number | boolean | null>;
  try {
    payload = buildPayload();
  } catch (err) {
    $q.notify({ type: 'warning', message: (err as Error).message });
    return;
  }
  const norm = (v: unknown) => (v === undefined || v === '' ? null : v) as string | number | boolean | null;
  const changes: SpeciesChanges = {};
  for (const [field, after] of Object.entries(payload)) {
    const before = norm(original[field]);
    if (before !== norm(after)) changes[field] = { before, after: norm(after) };
  }
  correctionChanges.value = changes;
  correctionOpen.value = true;
}

function openEdit(row: AnySpecies) {
  editingId.value = row.id;
  editingRow.value = row;
  const f = {
    ...emptyForm(),
    common_name: row.common_name,
    scientific_name: row.scientific_name,
    family: row.family ?? '',
    origin: row.origin ?? '',
    notes: row.notes ?? '',
    link: row.link ?? '',
  };
  if ('water_type' in row) f.water_type = row.water_type;
  if ('min_volume' in row) {
    f.min_volume = row.min_volume;
    f.reef_safe = row.reef_safe;
  }
  if ('category' in row) f.category = row.category;
  if ('max_height' in row) f.max_height = row.max_height;
  if ('light_min' in row) f.light = { min: row.light_min, max: row.light_max };
  if ('resistance_level' in row) f.resistance_level = row.resistance_level;
  if ('brewing_min' in row) {
    f.type = row.type;
    f.brewing = { min: row.brewing_min, max: row.brewing_max };
    f.aggressiveness_level = row.aggressiveness_level;
    f.location_level = row.location_level;
  }
  if ('temperature_min' in row) {
    f.temperature = { min: row.temperature_min, max: row.temperature_max };
    f.growing = row.growing;
    f.location = row.location;
  }
  form.value = f;
  dialog.value = true;
}

function requirePositive(value: number | null, label: string): number {
  if (!value || value <= 0) throw new Error(t('livestock.catalog.required', { label }));
  return value;
}

function buildPayload() {
  const f = form.value;
  const common = {
    common_name: f.common_name.trim(),
    scientific_name: f.scientific_name.trim(),
    family: f.family.trim() || null,
    origin: f.origin.trim() || null,
    notes: f.notes.trim() || null,
    link: f.link.trim() || null,
  };
  switch (kind.value) {
    case 'fishes':
      return {
        ...common,
        water_type: f.water_type,
        max_height: requirePositive(f.max_height, t('livestock.catalog.sizeMaxField')),
        min_volume: requirePositive(f.min_volume, t('livestock.catalog.volumeMinField')),
        reef_safe: f.water_type === 'sea' ? f.reef_safe : true,
      };
    case 'invertebrates':
      return {
        ...common,
        water_type: f.water_type,
        category: f.category,
        min_volume: requirePositive(f.min_volume, t('livestock.catalog.volumeMinField')),
        reef_safe: f.water_type === 'sea' ? f.reef_safe : true,
      };
    case 'corals':
      return {
        ...common,
        type: f.type,
        light_min: f.light.min,
        light_max: f.light.max,
        brewing_min: f.brewing.min,
        brewing_max: f.brewing.max,
        aggressiveness_level: f.aggressiveness_level,
        resistance_level: f.resistance_level,
        location_level: f.location_level,
      };
    case 'plants':
      return {
        ...common,
        light_min: f.light.min,
        light_max: f.light.max,
        temperature_min: f.temperature.min,
        temperature_max: f.temperature.max,
        growing: f.growing,
        location: f.location,
        resistance_level: f.resistance_level,
        max_height: requirePositive(f.max_height, t('livestock.catalog.heightMaxField')),
      };
  }
}

async function save() {
  if (!form.value.common_name.trim() || !form.value.scientific_name.trim()) {
    $q.notify({ type: 'warning', message: t('livestock.catalog.namesRequired') });
    return;
  }
  let payload;
  try {
    payload = buildPayload();
  } catch (err) {
    $q.notify({ type: 'warning', message: (err as Error).message });
    return;
  }
  saving.value = true;
  try {
    // Le payload correspond au type courant (construit par buildPayload selon kind)
    const typed = payload as never;
    if (editingId.value) await store.update(kind.value, editingId.value, typed);
    else await store.create(kind.value, typed);
    dialog.value = false;
    await load();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('livestock.catalog.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

function removeSpecies(row: AnySpecies) {
  confirmRemove(
    t('livestock.catalog.item', { name: row.common_name }),
    async () => {
      await store.remove(kind.value, row.id);
      await load();
    },
    { message: t('livestock.catalog.deleteMessage', { name: row.common_name }) },
  );
}

watch(kind, () => {
  search.value = '';
  waterFilter.value = 'all';
});

// Synchronisation du catalogue commun (hub de l'éditeur)
interface CatalogSync {
  enabled: boolean;
  applied_at: string | null;
  checked_at: string | null;
  result: string | null;
  error: string | null;
}
const sync = ref<CatalogSync | null>(null);
const syncing = ref(false);
async function loadSync() {
  try {
    sync.value = (await axios.get<CatalogSync>('/species/catalog/status')).data;
  } catch {
    sync.value = null;
  }
}
async function syncNow() {
  syncing.value = true;
  try {
    sync.value = (await axios.post<CatalogSync>('/species/catalog/sync')).data;
    if (sync.value.error) $q.notify({ type: 'warning', message: t('livestock.catalog.sync.failed') });
    else $q.notify({ type: 'positive', message: t('livestock.catalog.sync.done') });
    await load();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('livestock.catalog.sync.failed')) });
  } finally {
    syncing.value = false;
  }
}

onMounted(() => {
  void load();
  void loadSync();
});
</script>

<style scoped>
/* Description du catalogue : visible sous le nom, sur deux lignes au plus */
.species-notes {
  max-width: 320px;
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
