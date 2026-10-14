<!--
  Saisie groupée des relevés : une date, une note et une valeur par
  paramètre. Les favoris sont proposés d'office, les autres paramètres
  s'ajoutent au besoin ; les champs laissés vides sont ignorés.
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="playlist_add"
    :title="t('params.batch')"
    :subtitle="t('params.batchDialog.subtitle')"
    width="560px"
    :submit-label="t('params.batchDialog.submit')"
    :submit-disabled="filledCount === 0"
    :loading="saving"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset"
    @submit="save"
  >
    <div class="row q-col-gutter-sm">
      <div class="col-12 col-sm-6">
        <DateInput v-model="date" :label="t('params.batchDialog.date')" />
      </div>
      <div class="col-12 col-sm-6">
        <q-input v-model="note" :label="t('params.batchDialog.note')" outlined dense />
      </div>
    </div>

    <div v-if="rows.length === 0" class="text-body2 text-grey-7">{{ t('params.batchDialog.noFavorite') }}</div>

    <div v-else class="column gap-sm">
      <div v-for="param in rows" :key="param.id" class="row items-center no-wrap gap-sm">
        <q-input
          v-model.number="values[param.id]"
          type="number"
          step="any"
          outlined
          dense
          class="col"
          :label="param.name + (param.full_name ? ` — ${param.full_name}` : '')"
          :suffix="param.unit ?? undefined"
          :hint="hintFor(param)"
          :autofocus="param.id === rows[0]?.id"
        />
        <q-btn flat round dense icon="close" color="grey-6" @click="removeRow(param.id)">
          <q-tooltip>{{ t('params.batchDialog.remove') }}</q-tooltip>
        </q-btn>
      </div>
    </div>

    <AppSelect
      v-if="addableOptions.length > 0"
      :model-value="null"
      :options="addableOptions"
      :label="t('params.batchDialog.addParam')"
      clearable
      @update:model-value="addRow"
    >
      <template #prepend><q-icon name="add" /></template>
    </AppSelect>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import DateInput from 'src/components/DateInput.vue';
import AppSelect from 'src/components/AppSelect.vue';
import { useWaterParameterStore } from 'src/stores/waterParameterStore';
import type { WaterParameter, WaterParameterReading } from 'src/types/waterParameter';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, isoDate } from 'src/utils/format';

const props = defineProps<{ modelValue: boolean; aquaId: number }>();
const { t } = useI18n();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [readings: WaterParameterReading[]] }>();

const $q = useQuasar();
const store = useWaterParameterStore();

const date = ref<string | null>(isoDate());
const note = ref('');
const selectedIds = ref<number[]>([]);
const values = ref<Record<number, number | null | undefined>>({});
const saving = ref(false);

const sortedParameters = computed(() => [...store.parameters].sort((a, b) => a.name.localeCompare(b.name)));
const rows = computed(() => sortedParameters.value.filter((p) => selectedIds.value.includes(p.id)));
const addableOptions = computed(() =>
  sortedParameters.value
    .filter((p) => !selectedIds.value.includes(p.id))
    .map((p) => ({ label: p.unit ? `${p.name} (${p.unit})` : p.name, value: p.id })),
);
const filledCount = computed(() => rows.value.filter((p) => isFilled(values.value[p.id])).length);

function isFilled(value: number | null | undefined): value is number {
  return typeof value === 'number' && !Number.isNaN(value);
}

function hintFor(param: WaterParameter): string {
  const parts: string[] = [];
  if (param.target_min != null || param.target_max != null) {
    parts.push(t('params.batchDialog.hintTarget', { min: param.target_min ?? '…', max: param.target_max ?? '…' }));
  }
  if (param.last_value != null) {
    parts.push(t('params.batchDialog.hintLast', { value: param.last_value, date: formatDate(param.last_reading_at) }));
  }
  return parts.join(' · ');
}

function reset() {
  date.value = isoDate();
  note.value = '';
  values.value = {};
  selectedIds.value = store.parameters.filter((p) => p.pinned).map((p) => p.id);
}

function addRow(id: number | null) {
  if (id != null && !selectedIds.value.includes(id)) selectedIds.value = [...selectedIds.value, id];
}

function removeRow(id: number) {
  selectedIds.value = selectedIds.value.filter((selected) => selected !== id);
  delete values.value[id];
}

async function save() {
  if (!date.value) {
    $q.notify({ type: 'warning', message: t('params.batchDialog.dateRequired') });
    return;
  }
  const filled = rows.value.filter((p) => isFilled(values.value[p.id]));
  if (filled.length === 0) {
    $q.notify({ type: 'warning', message: t('params.batchDialog.valueRequired') });
    return;
  }
  saving.value = true;
  try {
    const readings = await store.addReadingsBatch({
      aquarium_id: props.aquaId,
      // Midi : la date choisie ne bascule pas au jour voisin avec le fuseau horaire
      timestamp: `${date.value}T12:00:00`,
      note: note.value.trim() || null,
      values: filled.map((p) => ({ water_parameter_id: p.id, value: values.value[p.id] as number })),
    });
    $q.notify({ type: 'positive', message: t('params.batchDialog.saved', readings.length) });
    emit('saved', readings);
    emit('update:modelValue', false);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('params.batchDialog.saveFailed')) });
  } finally {
    saving.value = false;
  }
}
</script>
