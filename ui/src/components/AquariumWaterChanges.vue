<!--
  Changements d'eau d'un aquarium : statistiques (dernier, rythme moyen),
  enregistrement (volume, sel décompté du stock, tâche validée) et historique.
  Chaque changement s'inscrit aussi au journal de bord.
-->
<template>
  <div>
    <PageHeader section :title="t('waterChanges.title')" :subtitle="t('waterChanges.subtitle')">
      <template #actions>
        <q-btn v-if="can.care" unelevated color="primary" icon="water_drop" :label="t('waterChanges.record')" @click="openDialog" />
      </template>
    </PageHeader>

    <div class="row q-col-gutter-md q-mb-md">
      <div v-for="stat in stats" :key="stat.label" class="col-6 col-md-3">
        <q-card flat bordered class="full-height q-pa-md">
          <div class="text-caption text-grey-7">{{ stat.label }}</div>
          <div class="text-h6 text-weight-bold">{{ stat.value }}</div>
          <div v-if="stat.hint" class="text-caption text-grey-6">{{ stat.hint }}</div>
        </q-card>
      </div>
    </div>

    <div v-if="loading" class="text-center q-py-xl"><q-spinner color="primary" size="3em" /></div>
    <EmptyState v-else-if="!changes.length" icon="water_drop" :title="t('waterChanges.emptyTitle')" :message="t('waterChanges.emptyMessage')">
      <q-btn v-if="can.care" unelevated color="primary" icon="water_drop" :label="t('waterChanges.record')" @click="openDialog" />
    </EmptyState>
    <q-card v-else flat bordered>
      <q-list separator>
        <q-item v-for="c in changes" :key="c.id">
          <q-item-section avatar>
            <q-avatar size="36px" color="blue-1" text-color="primary" icon="water_drop" />
          </q-item-section>
          <q-item-section>
            <q-item-label class="text-weight-medium">
              {{ formatNumber(c.volume_l) }} L<span v-if="c.percent != null" class="text-grey-7"> · {{ formatNumber(c.percent) }} %</span>
            </q-item-label>
            <q-item-label caption>
              {{ formatDateTime(c.performed_at) }}
              <span v-if="c.salt_amount && c.salt_item_name"> · {{ formatNumber(c.salt_amount) }} {{ c.salt_unit }} {{ t('waterChanges.of') }} {{ c.salt_item_name }}</span>
              <span v-if="c.note"> · {{ c.note }}</span>
            </q-item-label>
          </q-item-section>
          <q-item-section v-if="can.edit" side>
            <q-btn flat round dense size="sm" icon="delete" color="negative" :aria-label="t('actions.delete')" @click="remove(c)" />
          </q-item-section>
        </q-item>
      </q-list>
    </q-card>

    <FormDialog v-model="dialogOpen" :title="t('waterChanges.record')" icon="water_drop" :loading="saving" :submit-label="t('common.save')" @submit="save">
      <div class="column gap-md">
        <q-input v-model="form.when" outlined dense type="datetime-local" :label="t('waterChanges.when')" />
        <div>
          <q-input v-model.number="form.volume" outlined dense type="number" min="0" step="0.5" :label="t('waterChanges.volume')" suffix="L">
            <template v-if="aquariumVolume" #hint>{{ t('waterChanges.percentHint', { n: formatNumber(percent), total: aquariumVolume }) }}</template>
          </q-input>
          <div v-if="aquariumVolume" class="row q-col-gutter-xs q-mt-md">
            <div v-for="p in [10, 15, 20, 25, 30, 50]" :key="p" class="col-4 col-sm-2">
              <q-btn outline no-caps color="primary" class="full-width" :label="`${p} %`" @click="form.volume = Math.round((aquariumVolume * p) / 100)" />
            </div>
          </div>
        </div>

        <template v-if="isSea">
          <q-select
            v-model="form.saltItemId"
            outlined
            dense
            clearable
            emit-value
            map-options
            :options="saltOptions"
            :label="t('waterChanges.salt')"
            :hint="saltOptions.length ? t('waterChanges.saltHint') : t('waterChanges.noSaltItem')"
          />
          <div v-if="saltItem" class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input v-model.number="form.saltPerLiter" outlined dense type="number" min="0" step="0.5" :label="t('waterChanges.saltPerLiter')" suffix="g/L" @update:model-value="suggestSalt" />
            </div>
            <div class="col-6">
              <q-input v-model.number="form.saltAmount" outlined dense type="number" min="0" step="0.01" :label="t('waterChanges.saltAmount')" :suffix="saltItem.unit" />
            </div>
          </div>
        </template>

        <q-select
          v-model="form.taskId"
          outlined
          dense
          clearable
          emit-value
          map-options
          :options="taskOptions"
          :label="t('waterChanges.completeTask')"
          :hint="t('waterChanges.completeTaskHint')"
        />
        <q-input v-model="form.note" outlined dense maxlength="300" :label="t('waterChanges.note')" />
      </div>
    </FormDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import axios from 'axios';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { WaterType } from 'src/types/Aquarium';
import type { InventoryItem } from 'src/types/inventory';
import type { MaintenanceTask } from 'src/types/maintenanceTask';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatDateTime } from 'src/utils/format';
import { intlLocale } from 'src/i18n/instance';

interface WaterChange {
  id: number;
  aquarium_id: number;
  performed_at: string;
  volume_l: number;
  salt_item_id?: number | null;
  salt_item_name?: string | null;
  salt_unit?: string | null;
  salt_amount?: number | null;
  note?: string | null;
  percent?: number | null;
}

const props = defineProps<{ aquaId: number }>();
const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const aquariumStore = useAquariumStore();

const changes = ref<WaterChange[]>([]);
const items = ref<InventoryItem[]>([]);
const tasks = ref<MaintenanceTask[]>([]);
const loading = ref(true);
const saving = ref(false);

const aquarium = computed(() => aquariumStore.getById(props.aquaId));
const aquariumVolume = computed(() => aquarium.value?.volume ?? 0);
const isSea = computed(() => aquarium.value?.water_type === WaterType.sea);

function formatNumber(value: number): string {
  return value.toLocaleString(intlLocale(), { maximumFractionDigits: 1 });
}

// --- Statistiques ---
const stats = computed(() => {
  const list = changes.value;
  const last = list[0];
  const eightWeeksAgo = Date.now() - 56 * 86400000;
  const recent = list.filter((c) => new Date(c.performed_at).getTime() >= eightWeeksAgo);
  const perWeek = recent.reduce((sum, c) => sum + c.volume_l, 0) / 8;
  const monthStart = new Date();
  monthStart.setDate(1);
  monthStart.setHours(0, 0, 0, 0);
  const thisMonth = list.filter((c) => new Date(c.performed_at) >= monthStart);
  const daysSince = last ? Math.floor((Date.now() - new Date(last.performed_at).getTime()) / 86400000) : null;
  return [
    {
      label: t('waterChanges.stats.last'),
      value: last ? formatDate(last.performed_at) : '—',
      hint: daysSince == null ? '' : t('waterChanges.stats.daysAgo', { n: daysSince }, daysSince),
    },
    {
      label: t('waterChanges.stats.perWeek'),
      value: recent.length ? `${formatNumber(perWeek)} L` : '—',
      hint: recent.length && aquariumVolume.value ? t('waterChanges.stats.percentOfVolume', { n: formatNumber((perWeek / aquariumVolume.value) * 100) }) : t('waterChanges.stats.over8Weeks'),
    },
    {
      label: t('waterChanges.stats.thisMonth'),
      value: `${formatNumber(thisMonth.reduce((s, c) => s + c.volume_l, 0))} L`,
      hint: t('waterChanges.stats.count', { n: thisMonth.length }, thisMonth.length),
    },
    {
      label: t('waterChanges.stats.total'),
      value: String(list.length),
      hint: t('waterChanges.stats.recorded'),
    },
  ];
});

// --- Saisie ---
function localInput(value: Date = new Date()): string {
  const d = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return d.toISOString().slice(0, 16);
}

const dialogOpen = ref(false);
const form = ref({
  when: localInput(),
  volume: 0,
  saltItemId: null as number | null,
  saltPerLiter: 36,
  saltAmount: null as number | null,
  taskId: null as number | null,
  note: '',
});

const percent = computed(() => (aquariumVolume.value ? (form.value.volume / aquariumVolume.value) * 100 : 0));
const saltOptions = computed(() => items.value.map((i) => ({ value: i.id, label: `${i.name} (${formatNumber(i.quantity)} ${i.unit})` })));
const saltItem = computed(() => items.value.find((i) => i.id === form.value.saltItemId) ?? null);
const taskOptions = computed(() => tasks.value.map((task) => ({ value: task.id, label: task.title })));

// Quantité de sel proposée : g/L × volume, convertie dans l'unité de l'article
function suggestSalt() {
  const item = saltItem.value;
  if (!item || !form.value.volume || !form.value.saltPerLiter) return;
  const grams = form.value.volume * form.value.saltPerLiter;
  const unit = item.unit.trim().toLowerCase();
  if (unit === 'kg') form.value.saltAmount = Math.round(grams / 10) / 100;
  else if (unit === 'g') form.value.saltAmount = Math.round(grams);
}

watch(() => [form.value.volume, form.value.saltItemId], suggestSalt);

function openDialog() {
  const salt = items.value.find((i) => /sel|salt/i.test(i.name));
  const waterTask = tasks.value.find((task) => /eau|water/i.test(task.title));
  form.value = {
    when: localInput(),
    volume: changes.value[0]?.volume_l ?? Math.round(aquariumVolume.value * 0.1),
    saltItemId: isSea.value ? (salt?.id ?? null) : null,
    saltPerLiter: 36,
    saltAmount: null,
    taskId: waterTask?.id ?? null,
    note: '',
  };
  suggestSalt();
  dialogOpen.value = true;
}

async function load() {
  try {
    const [c, i, tk] = await Promise.all([
      axios.get<WaterChange[]>('/water-changes/', { params: { aquarium_id: props.aquaId } }),
      axios.get<InventoryItem[]>('/inventory-items/', { params: { aquarium_id: props.aquaId } }),
      axios.get<MaintenanceTask[]>('/maintenance-tasks/', { params: { aquarium_id: props.aquaId } }),
    ]);
    changes.value = c.data;
    items.value = i.data;
    tasks.value = tk.data;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('waterChanges.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!form.value.volume || form.value.volume <= 0) {
    $q.notify({ type: 'warning', message: t('waterChanges.volumeRequired') });
    return;
  }
  saving.value = true;
  try {
    await axios.post('/water-changes/', {
      aquarium_id: props.aquaId,
      performed_at: new Date(form.value.when).toISOString(),
      volume_l: form.value.volume,
      salt_item_id: saltItem.value ? saltItem.value.id : null,
      salt_amount: saltItem.value ? form.value.saltAmount : null,
      complete_task_id: form.value.taskId,
      note: form.value.note.trim() || null,
    });
    dialogOpen.value = false;
    $q.notify({ type: 'positive', message: t('waterChanges.saved') });
    await load();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('waterChanges.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

function remove(change: WaterChange) {
  confirmRemove(t('waterChanges.item', { date: formatDate(change.performed_at) }), async () => {
    await axios.delete(`/water-changes/${change.id}`);
    await load();
  }, { message: t('waterChanges.deleteMessage') });
}

onMounted(load);
</script>
