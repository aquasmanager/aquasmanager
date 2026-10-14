<template>
  <div>
    <PageHeader section :title="t('params.title')" :subtitle="t('params.subtitle')">
      <template #actions>
        <q-btn v-if="parameters.length > 0" outline color="primary" icon="share" :label="t('params.share.button')" @click="shareDialog = true" />
        <q-btn outline color="primary" icon="compare_arrows" :label="t('params.compareIcp')" @click="icpCompareDialog = true" />
        <q-btn v-if="can.edit" outline color="primary" icon="upload_file" :label="t('params.importIcp')" @click="icpDialog = true" />
        <q-btn v-if="can.edit" outline color="primary" icon="add" :label="t('params.addParam')" @click="openAddParamDialog" />
        <q-btn
          v-if="can.care && parameters.length > 0"
          unelevated
          color="primary"
          icon="playlist_add"
          :label="t('params.batch')"
          @click="batchDialog = true"
        >
          <q-tooltip>{{ t('params.batchHelp') }}</q-tooltip>
        </q-btn>
      </template>
    </PageHeader>

    <div v-if="parameters.length > 0" class="row items-center gap-sm q-mb-md">
      <AppInput v-model="search" :placeholder="t('params.search')" icon="search" clearable class="app-search" style="width: 280px; max-width: 100%" />
      <q-btn
        :outline="!onlyOutOfTarget"
        :unelevated="onlyOutOfTarget"
        color="orange-8"
        icon="filter_alt"
        :label="t('params.outOfTargetFilter', { n: outOfTargetCount })"
        @click="onlyOutOfTarget = !onlyOutOfTarget"
      />
      <q-space />
      <q-btn v-if="can.edit" flat color="grey-8" icon="restart_alt" :label="t('params.defaultTargets')" @click="confirmApplyDefaults">
        <q-tooltip>{{ t('params.defaultTargetsHelp') }}</q-tooltip>
      </q-btn>
    </div>

    <div v-if="store.loading" class="text-center q-py-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <EmptyState
      v-else-if="parameters.length === 0"
      icon="science"
      :title="t('params.emptyTitle')"
      :message="t('params.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('params.addParam')" @click="openAddParamDialog" />
    </EmptyState>

    <EmptyState
      v-else-if="filteredParameters.length === 0"
      :icon="search ? 'search_off' : 'check_circle'"
      :icon-color="search ? 'grey-5' : 'positive'"
      :title="search ? t('params.noResult', { q: search }) : t('params.noOutOfTarget')"
    />

    <div v-else class="row q-col-gutter-md">
      <div v-for="param in filteredParameters" :key="param.id" class="col-12 col-sm-6 col-md-4">
        <q-card flat bordered class="full-height q-pa-sm">
          <q-card-section class="row items-center justify-between q-pb-xs">
            <div class="row items-baseline q-gutter-x-xs">
              <div class="text-subtitle1 text-weight-bold">{{ param.name }}</div>
              <div v-if="param.full_name" class="text-caption text-grey-6">
                {{ param.full_name }}
              </div>
            </div>
            <div class="row items-center">
              <q-btn
                flat
                round
                dense
                :icon="param.pinned ? 'star' : 'star_border'"
                :color="param.pinned ? 'amber-8' : 'grey-5'"
                :disable="!can.edit"
                @click="togglePinned(param)"
              >
                <q-tooltip>
                  {{ param.pinned ? t('params.unpin') : t('params.pin') }}
                </q-tooltip>
              </q-btn>
              <q-btn v-if="can.edit" flat round dense icon="more_vert" color="grey-6">
                <q-menu auto-close>
                  <q-list style="min-width: 120px">
                    <q-item v-if="can.edit" clickable @click="openEditParamDialog(param)">
                      <q-item-section avatar><q-icon name="edit" size="xs" /></q-item-section>
                      <q-item-section>{{ t('actions.edit') }}</q-item-section>
                    </q-item>
                    <q-item v-if="can.manage" clickable class="text-negative" @click="removeParam(param)">
                      <q-item-section avatar><q-icon name="delete" size="xs" color="negative" /></q-item-section>
                      <q-item-section>{{ t('actions.delete') }}</q-item-section>
                    </q-item>
                  </q-list>
                </q-menu>
              </q-btn>
            </div>
          </q-card-section>

          <q-card-section class="q-pt-none">
            <div class="row items-baseline justify-between">
              <div>
                <span class="text-h4 text-weight-bolder text-dark">{{ param.last_value ?? '--' }}</span>
                <span class="text-body2 text-grey-7 q-ml-xs">{{ param.unit }}</span>
              </div>
              <q-chip
                v-if="param.last_value != null && param.in_target != null"
                dense
                :color="param.in_target ? 'positive' : 'warning'"
                text-color="white"
                class="text-weight-bold"
              >
                {{ param.in_target ? t('params.optimal') : t('params.outOfTarget') }}
              </q-chip>
            </div>

            <div
              class="q-mt-sm"
              v-if="(history[param.id]?.length ?? 0) > 1 || ((history[param.id]?.length ?? 0) === 1 && param.in_target != null)"
            >
              <SparklineChart
                :data="(history[param.id] ?? []).map((r) => r.value)"
                :color="parameterColor(param.id, parameters)"
                :height="35"
                :target-min="param.target_min ?? null"
                :target-max="param.target_max ?? null"
              />
            </div>

            <div class="text-caption text-grey-6 q-mt-sm">
              {{ t('params.target') }} <b>{{ param.target_min ?? '--' }} - {{ param.target_max ?? '--' }} {{ param.unit }}</b>
            </div>
            <div class="text-caption text-grey-5">
              {{ t('params.lastReading', { date: formatDate(param.last_reading_at) }) }}
            </div>
            <!-- Tendance des 3 dernières semaines et sortie de cible prévue -->
            <div v-if="trends[param.id]" class="text-caption q-mt-xs row items-center no-wrap" :class="trendClass(trends[param.id]!)">
              <q-icon :name="trendIcon(trends[param.id]!)" size="16px" class="q-mr-xs" />
              <span>{{ trendText(trends[param.id]!, param.unit) }}</span>
            </div>
          </q-card-section>

          <q-card-actions align="between">
            <div class="row no-wrap">
              <q-btn flat dense :label="t('params.history')" icon="history" color="grey-8" class="q-px-sm" @click="openHistoryDialog(param)" />
              <q-btn v-if="can.care && param.last_value != null" flat dense icon="medication_liquid" color="grey-8" class="q-px-xs" @click="openDosing(param)">
                <q-tooltip>{{ t('dosing.button') }}</q-tooltip>
              </q-btn>
            </div>
            <q-btn v-if="can.care" unelevated dense :label="t('params.newReading')" icon="add" color="primary" class="q-px-sm" @click="openAddReadingDialog(param)" />
          </q-card-actions>
        </q-card>
      </div>
    </div>

    <!-- Ajout / édition d'un paramètre -->
    <FormDialog
      v-model="paramDialog"
      icon="science"
      :title="isEditingParam ? t('params.form.editTitle') : t('params.addParam')"
      :subtitle="t('params.form.subtitle')"
      width="440px"
      :submit-label="isEditingParam ? t('common.save') : t('params.form.add')"
      @submit="saveParam"
    >
      <q-input
        v-model="paramForm.name"
        :label="t('params.form.name')"
        outlined
        dense
        autofocus
        @blur="applyPresetIfMatch"
      />
      <div v-if="matchedPreset" class="row items-center justify-between text-caption text-teal">
        <span>
          {{ t('params.form.defaultTarget', { min: matchedPreset.target_min, max: matchedPreset.target_max, unit: matchedPreset.unit }) }}
        </span>
        <q-btn flat dense size="sm" color="teal" :label="t('params.form.apply')" @click="applyPreset" />
      </div>
      <q-input v-model="paramForm.unit" :label="t('params.form.unit')" outlined dense />
      <div class="row q-col-gutter-sm">
        <div class="col-6">
          <q-input v-model.number="paramForm.target_min" type="number" step="any" :label="t('params.form.targetMin')" outlined dense />
        </div>
        <div class="col-6">
          <q-input v-model.number="paramForm.target_max" type="number" step="any" :label="t('params.form.targetMax')" outlined dense />
        </div>
      </div>
    </FormDialog>

    <!-- Relevé -->
    <FormDialog
      v-model="readingDialog"
      icon="edit_note"
      :title="isEditingReading ? t('params.reading.editTitle') : t('params.newReading')"
      :subtitle="activeParam?.full_name ? `${activeParam.name} — ${activeParam.full_name}` : activeParam?.name"
      width="400px"
      @submit="saveReading"
    >
      <q-input
        v-model.number="readingForm.value"
        type="number"
        step="any"
        :label="activeParam?.unit ? t('params.reading.valueUnit', { unit: activeParam.unit }) : t('params.reading.value')"
        outlined
        dense
        autofocus
      />
      <DateInput v-model="readingForm.date" :label="t('params.reading.date')" />
      <q-input v-model="readingForm.note" :label="t('params.reading.note')" outlined dense />
    </FormDialog>

    <!-- Historique d'un paramètre -->
    <FormDialog
      v-model="historyDialog"
      icon="history"
      :title="t('params.history')"
      :subtitle="activeParam?.name"
      width="480px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <q-list v-if="activeHistory.length > 0" bordered separator class="rounded-borders">
        <q-item v-for="r in [...activeHistory].reverse()" :key="r.id">
          <q-item-section>
            <q-item-label class="text-weight-medium">{{ r.value }} {{ activeParam?.unit }}</q-item-label>
            <q-item-label caption>
              {{ formatDate(r.timestamp) }}<span v-if="r.note"> — {{ r.note }}</span>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="row no-wrap">
              <q-btn v-if="can.edit" flat round dense icon="edit" color="grey-7" size="sm" @click="openEditReadingDialog(r)">
                <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
              </q-btn>
              <q-btn v-if="can.manage" flat round dense icon="delete" color="negative" size="sm" @click="deleteReadingEntry(r)">
                <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
              </q-btn>
            </div>
          </q-item-section>
        </q-item>
      </q-list>
      <div v-else class="text-center text-grey-6 q-pa-md">{{ t('params.reading.none') }}</div>
    </FormDialog>

    <!-- Saisie groupée des favoris -->
    <BatchReadingDialog v-model="batchDialog" :aqua-id="aquaId" @saved="onBatchSaved" />

    <!-- Dialog Import ICP -->
    <IcpImportDialog v-model="icpDialog" :aqua-id="aquaId" @imported="onIcpImported" />

    <!-- Dialog Comparaison ICP -->
    <IcpCompareDialog v-model="icpCompareDialog" :aqua-id="aquaId" />
    <DosingCalculatorDialog v-model="dosingDialog" :aqua-id="aquaId" :parameter="dosingParam" />
    <ShareParametersDialog v-model="shareDialog" :aqua-id="aquaId" :parameters="parameters" :history="history" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import { useRoute } from 'vue-router';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useWaterParameterStore } from 'src/stores/waterParameterStore';
import {
  parameterColor,
  type WaterParameter,
  type WaterParameterReading,
} from 'src/types/waterParameter';
import SparklineChart from 'src/components/SparklineChart.vue';
import IcpImportDialog from 'src/components/IcpImportDialog.vue';
import BatchReadingDialog from 'src/components/BatchReadingDialog.vue';
import { usePermissions } from 'src/composables/usePermissions';
import IcpCompareDialog from 'src/components/IcpCompareDialog.vue';
import ShareParametersDialog from 'src/components/ShareParametersDialog.vue';
import DosingCalculatorDialog from 'src/components/DosingCalculatorDialog.vue';
import AppInput from 'src/components/AppInput.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import DateInput from 'src/components/DateInput.vue';
import { useConfirm, useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, isoDate } from 'src/utils/format';
import { intlLocale } from 'src/i18n/instance';

const route = useRoute();

const props = defineProps({
  aquaId: { type: Number, required: true },
});

const { t } = useI18n();
const $q = useQuasar();
const { confirmRemove } = useConfirmRemove();
const { confirmAction } = useConfirm();
const store = useWaterParameterStore();
const can = usePermissions();
const parameters = computed(() => store.parameters);

// Favoris (étoile sur chaque carte) en tête de grille, le reste par ordre alphabétique.
const sortedParameters = computed(() =>
  [...parameters.value].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return a.name.localeCompare(b.name);
  }),
);

const search = ref('');
const onlyOutOfTarget = ref(route.query.filtre === 'hors-cible');
const outOfTargetCount = computed(() => parameters.value.filter((p) => p.in_target === false).length);

const filteredParameters = computed(() => {
  const base = onlyOutOfTarget.value
    ? sortedParameters.value.filter((p) => p.in_target === false)
    : sortedParameters.value;
  // clearable remet la valeur à null
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return base;
  return base.filter((p) => {
    if (p.name.toLowerCase().includes(s)) return true;
    return !!p.full_name && p.full_name.toLowerCase().includes(s);
  });
});

const history = ref<Record<number, WaterParameterReading[]>>({});

async function loadHistory() {
  await Promise.all([
    ...parameters.value.map(async (p) => {
      history.value[p.id] = await store.fetchReadings(p.id);
    }),
    loadTrends(),
  ]);
}

// --- Tendances ---
interface Trend {
  parameter_id: number;
  slope_per_day: number;
  span_days: number;
  reliable: boolean;
  direction: 'stable' | 'rising' | 'falling';
  limit: 'min' | 'max' | null;
  days_to_limit: number | null;
  predicted_date: string | null;
}

const trends = ref<Record<number, Trend>>({});

async function loadTrends() {
  try {
    const { data } = await axios.get<Trend[]>('/water-parameters/trends', { params: { aquarium_id: props.aquaId } });
    trends.value = Object.fromEntries(data.map((trend) => [trend.parameter_id, trend]));
  } catch {
    trends.value = {};
  }
}

function trendIcon(trend: Trend): string {
  return trend.direction === 'stable' ? 'trending_flat' : trend.direction === 'rising' ? 'trending_up' : 'trending_down';
}

function trendClass(trend: Trend): string {
  if (trend.days_to_limit !== null && trend.days_to_limit <= 3) return 'text-negative text-weight-bold';
  if (trend.days_to_limit !== null && trend.days_to_limit <= 7) return 'text-orange-9 text-weight-medium';
  return 'text-grey-7';
}

function trendText(trend: Trend, unit?: string | null): string {
  const days = Math.round(trend.span_days);
  if (trend.direction === 'stable') return t('params.trend.stable', { n: days });
  const slope = trend.slope_per_day.toLocaleString(intlLocale(), { maximumSignificantDigits: 2, signDisplay: 'always' });
  let text = t('params.trend.perDay', { slope: `${slope}${unit ? ` ${unit}` : ''}`, n: days });
  if (trend.days_to_limit !== null && trend.predicted_date) {
    const when = new Date(trend.predicted_date).toLocaleDateString(intlLocale(), { day: '2-digit', month: '2-digit' });
    const way = trend.limit === 'min' ? t('params.trend.below') : t('params.trend.above');
    text += ` · ${t('params.trend.exit', { way, n: Math.max(1, Math.round(trend.days_to_limit)), date: when })}`;
  } else if (!trend.reliable) {
    text += ` · ${t('params.trend.irregular')}`;
  }
  return text;
}

onMounted(async () => {
  await Promise.all([store.fetch(props.aquaId), store.fetchTargetDefaults()]);
  await loadHistory();
});

// --- Saisie groupée ---
const batchDialog = ref(false);

function onBatchSaved(readings: WaterParameterReading[]) {
  for (const reading of readings) {
    const list = history.value[reading.water_parameter_id] ?? [];
    history.value[reading.water_parameter_id] = sortByTimestamp([...list, reading]);
  }
  void loadTrends();
}

// --- Calculateur de dosage ---
const dosingDialog = ref(false);
const dosingParam = ref<WaterParameter | null>(null);

function openDosing(param: WaterParameter) {
  dosingParam.value = param;
  dosingDialog.value = true;
}

// --- Partage (image, texte, lien public) ---
const shareDialog = ref(false);

// --- Import ICP ---
const icpDialog = ref(false);
const icpCompareDialog = ref(false);

async function onIcpImported() {
  await store.fetch(props.aquaId);
  await loadHistory();
}

// --- Définition du paramètre ---
const paramDialog = ref(false);
const isEditingParam = ref(false);
const editingParamId = ref<number | null>(null);
const paramForm = ref<{ name: string; unit: string; target_min?: number | null; target_max?: number | null }>({
  name: '',
  unit: '',
});

// Plages typiques en eau de mer récifale, juste un point de départ éditable
// (elles ne remplacent jamais une valeur déjà saisie par l'utilisateur).
const matchedPreset = computed(() => store.defaultTargetFor(paramForm.value.name));

function applyPresetIfMatch() {
  if (isEditingParam.value) return;
  const preset = matchedPreset.value;
  if (!preset) return;
  if (!paramForm.value.unit) paramForm.value.unit = preset.unit;
  if (paramForm.value.target_min == null) paramForm.value.target_min = preset.target_min;
  if (paramForm.value.target_max == null) paramForm.value.target_max = preset.target_max;
}

function applyPreset() {
  const preset = matchedPreset.value;
  if (!preset) return;
  if (!paramForm.value.unit) paramForm.value.unit = preset.unit;
  paramForm.value.target_min = preset.target_min;
  paramForm.value.target_max = preset.target_max;
}

function confirmApplyDefaults() {
  const changes = parameters.value.filter((p) => {
    const preset = store.defaultTargetFor(p.name, p.unit);
    return !!preset && (p.target_min !== preset.target_min || p.target_max !== preset.target_max);
  });
  if (changes.length === 0) {
    $q.notify({ type: 'info', message: t('params.notify.alreadyDefault') });
    return;
  }
  confirmAction({
    title: t('params.notify.defaultsTitle'),
    message: t('params.notify.defaultsMessage', { n: changes.length, names: changes.map((p) => p.name).join(', ') }),
    okLabel: t('params.form.apply'),
    onOk: async () => {
      try {
        const updated = await store.applyDefaultTargets(props.aquaId);
        $q.notify({ type: 'positive', message: t('params.notify.targetsUpdated', { n: updated.length }) });
      } catch (err) {
        $q.notify({ type: 'negative', message: apiErrorMessage(err, t('params.notify.targetsFailed')) });
      }
    },
  });
}

function openAddParamDialog() {
  isEditingParam.value = false;
  editingParamId.value = null;
  paramForm.value = { name: '', unit: '' };
  paramDialog.value = true;
}

function openEditParamDialog(param: WaterParameter) {
  isEditingParam.value = true;
  editingParamId.value = param.id;
  paramForm.value = {
    name: param.name,
    unit: param.unit ?? '',
    target_min: param.target_min ?? null,
    target_max: param.target_max ?? null,
  };
  paramDialog.value = true;
}

async function saveParam() {
  if (!paramForm.value.name.trim()) {
    $q.notify({ type: 'warning', message: t('params.notify.nameRequired') });
    return;
  }
  const payload = {
    name: paramForm.value.name.trim(),
    unit: paramForm.value.unit || null,
    target_min: paramForm.value.target_min ?? null,
    target_max: paramForm.value.target_max ?? null,
  };
  try {
    if (isEditingParam.value && editingParamId.value !== null) {
      await store.update(editingParamId.value, payload);
    } else {
      const created = await store.create({ aquarium_id: props.aquaId, ...payload });
      history.value[created.id] = [];
    }
    paramDialog.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('params.notify.saveFailed')) });
  }
}

async function togglePinned(param: WaterParameter) {
  try {
    await store.update(param.id, { pinned: !param.pinned });
  } catch {
    $q.notify({ type: 'negative', message: t('params.notify.pinFailed') });
  }
}

function removeParam(param: WaterParameter) {
  confirmRemove(
    t('params.item', { name: param.name }),
    async () => {
      await store.remove(param.id);
      delete history.value[param.id];
    },
    { message: t('params.deleteMessage', { name: param.name }) },
  );
}

// --- Relevé ---
const dateStrFrom = isoDate;
const todayDateStr = () => isoDate();

const readingDialog = ref(false);
const activeParam = ref<WaterParameter | null>(null);
const isEditingReading = ref(false);
const editingReadingId = ref<number | null>(null);
const readingForm = ref<{ value: number | undefined; note: string; date: string }>({
  value: undefined,
  note: '',
  date: todayDateStr(),
});

function openAddReadingDialog(param: WaterParameter) {
  activeParam.value = param;
  isEditingReading.value = false;
  editingReadingId.value = null;
  readingForm.value = { value: undefined, note: '', date: todayDateStr() };
  readingDialog.value = true;
}

function sortByTimestamp(readings: WaterParameterReading[]): WaterParameterReading[] {
  return [...readings].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

async function saveReading() {
  if (!activeParam.value) return;
  if (readingForm.value.value === undefined || readingForm.value.value === null || Number.isNaN(readingForm.value.value)) {
    $q.notify({ type: 'warning', message: t('params.notify.valueRequired') });
    return;
  }
  if (!readingForm.value.date) {
    $q.notify({ type: 'warning', message: t('params.notify.dateRequired') });
    return;
  }

  const paramId = activeParam.value.id;
  const payload = {
    value: readingForm.value.value,
    note: readingForm.value.note || null,
    // Midi pile pour éviter tout souci de fuseau horaire qui ferait
    // basculer la date choisie sur le jour précédent/suivant.
    timestamp: `${readingForm.value.date}T12:00:00`,
  };

  try {
    if (isEditingReading.value && editingReadingId.value !== null) {
      const reading = await store.updateReading(paramId, editingReadingId.value, payload);
      const list = history.value[paramId] ?? [];
      history.value[paramId] = sortByTimestamp(list.map((r) => (r.id === reading.id ? reading : r)));
    } else {
      const reading = await store.addReading(paramId, payload);
      const list = history.value[paramId] ?? [];
      history.value[paramId] = sortByTimestamp([...list, reading]);
    }
    readingDialog.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('params.notify.readingFailed')) });
  }
}

// --- Historique ---
const historyDialog = ref(false);
const activeHistory = computed(() => (activeParam.value ? history.value[activeParam.value.id] ?? [] : []));

function openHistoryDialog(param: WaterParameter) {
  activeParam.value = param;
  historyDialog.value = true;
}

function openEditReadingDialog(reading: WaterParameterReading) {
  if (!activeParam.value) return;
  isEditingReading.value = true;
  editingReadingId.value = reading.id;
  readingForm.value = {
    value: reading.value,
    note: reading.note ?? '',
    date: dateStrFrom(new Date(reading.timestamp)),
  };
  readingDialog.value = true;
}

function deleteReadingEntry(reading: WaterParameterReading) {
  if (!activeParam.value) return;
  const paramId = activeParam.value.id;
  confirmRemove(
    t('params.readingItem', { date: formatDate(reading.timestamp) }),
    async () => {
      await store.deleteReading(paramId, reading.id);
      history.value[paramId] = (history.value[paramId] ?? []).filter((r) => r.id !== reading.id);
    },
    {
      message: t('params.readingDeleteMessage', {
        date: formatDate(reading.timestamp),
        value: `${reading.value} ${activeParam.value.unit ?? ''}`.trim(),
      }),
    },
  );
}
</script>
