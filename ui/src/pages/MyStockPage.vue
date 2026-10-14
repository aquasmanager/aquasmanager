<template>
  <div>
    <PageHeader section :title="t('stock.title')" :subtitle="t('stock.subtitle')">
      <template #actions>
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('stock.add')" @click="openAddItemDialog" />
      </template>
    </PageHeader>

    <div v-if="inventoryStore.items.length > 0" class="row items-center gap-sm q-mb-md">
      <AppInput v-model="search" :placeholder="t('stock.search')" icon="search" clearable class="app-search" style="width: 280px; max-width: 100%" />
      <q-btn
        :outline="!onlyLowStock"
        :unelevated="onlyLowStock"
        color="orange-8"
        icon="filter_alt"
        :label="t('stock.lowFilter', { n: lowStockCount })"
        @click="onlyLowStock = !onlyLowStock"
      />
    </div>

    <div v-if="inventoryStore.loading" class="text-center q-py-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <EmptyState
      v-else-if="sortedItems.length === 0"
      icon="inventory_2"
      :title="t('stock.emptyTitle')"
      :message="t('stock.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('stock.add')" @click="openAddItemDialog" />
    </EmptyState>

    <EmptyState
      v-else-if="filteredItems.length === 0"
      :icon="search ? 'search_off' : 'check_circle'"
      :icon-color="search ? 'grey-5' : 'positive'"
      :title="search ? t('stock.noResult', { search }) : t('stock.noLow')"
    />

    <div v-else class="row q-col-gutter-md">
      <div v-for="item in filteredItems" :key="item.id" class="col-12 col-sm-6 col-md-4">
        <q-card flat bordered class="full-height q-pa-sm">
          <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
            <div class="col text-subtitle1 text-weight-bold ellipsis-2-lines" :title="item.name">{{ item.name }}</div>
            <q-btn v-if="can.edit" flat round dense icon="more_vert" color="grey-7">
              <q-menu auto-close>
                <q-list style="min-width: 140px">
                  <q-item v-if="can.edit" clickable @click="openEditItemDialog(item)">
                    <q-item-section avatar><q-icon name="edit" size="xs" /></q-item-section>
                    <q-item-section>{{ t('actions.edit') }}</q-item-section>
                  </q-item>
                  <q-item v-if="can.edit" clickable @click="markOpenedToday(item)">
                    <q-item-section avatar><q-icon name="lock_open" size="xs" /></q-item-section>
                    <q-item-section>{{ t('stock.openedToday') }}</q-item-section>
                  </q-item>
                  <q-item v-if="can.manage" clickable class="text-negative" @click="removeItem(item)">
                    <q-item-section avatar><q-icon name="delete" size="xs" color="negative" /></q-item-section>
                    <q-item-section>{{ t('actions.delete') }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </q-card-section>

          <q-card-section class="q-pt-none">
            <div class="row items-baseline justify-between">
              <div>
                <span class="text-h4 text-weight-bolder">{{ formatNumber(item.quantity) }}</span>
                <span class="text-body2 text-grey-7 q-ml-xs">{{ item.unit }}</span>
              </div>
              <q-chip v-if="isLowStock(item)" dense color="orange-8" text-color="white" class="text-weight-bold">
                {{ t('stock.low') }}
              </q-chip>
            </div>
            <ScopeChip :entity="item" class="q-mt-xs" />
            <div class="text-caption text-grey-7 q-mt-sm">
              <i18n-t keypath="stock.threshold" scope="global">
                <template #value><b>{{ formatNumber(item.low_stock_threshold) }} {{ item.unit }}</b></template>
              </i18n-t>
            </div>
            <div v-if="item.opened_on" class="text-caption text-grey-7">
              <q-icon name="lock_open" size="14px" class="q-mr-xs" />{{ openedLabel(item.opened_on) }}
            </div>
          </q-card-section>

          <q-card-actions align="between">
            <q-btn flat dense :label="t('stock.history')" icon="history" color="grey-8" class="q-px-sm" @click="openItemHistoryDialog(item)" />
            <q-btn v-if="can.care" unelevated dense :label="t('stock.movement')" icon="swap_vert" color="primary" class="q-px-sm" @click="openMovementDialog(item)" />
          </q-card-actions>
        </q-card>
      </div>
    </div>

    <!-- Ajout / édition d'un article -->
    <FormDialog
      v-model="itemDialog"
      icon="inventory_2"
      :title="isEditingItem ? t('stock.editTitle') : t('stock.add')"
      :subtitle="t('stock.formSubtitle')"
      width="440px"
      :submit-label="isEditingItem ? t('common.save') : t('actions.add')"
      @submit="saveItem"
    >
      <q-input v-model="itemForm.name" :label="t('stock.name')" outlined dense autofocus />
      <q-input v-model="itemForm.unit" :label="t('stock.unit')" outlined dense />
      <q-input
        v-if="!isEditingItem"
        v-model.number="itemForm.quantity"
        type="number"
        step="any"
        :label="t('stock.initialQuantity')"
        outlined
        dense
      />
      <q-input v-model.number="itemForm.low_stock_threshold" type="number" step="any" :label="t('stock.thresholdLabel')" outlined dense clearable />
      <DateInput v-model="itemForm.opened_on" :label="t('stock.openedOn')" clearable />
      <ScopeSelector v-model="itemScope" :current-aquarium-id="aquaId" />
      <div v-if="itemScope.scope !== 'single'" class="text-caption text-grey-7">
        {{ t('stock.sharedHelp') }}
      </div>
    </FormDialog>

    <!-- Mouvement de stock -->
    <FormDialog
      v-model="movementDialog"
      icon="swap_vert"
      :title="t('stock.movementTitle')"
      :subtitle="activeItem?.name"
      width="400px"
      :submit-label="t('stock.validate')"
      @submit="saveMovement"
    >
      <q-btn-toggle
        v-model="movementForm.direction"
        spread
        unelevated
        toggle-color="primary"
        color="grey-2"
        text-color="grey-8"
        :options="[
          { label: t('stock.restock'), value: 'in', icon: 'add' },
          { label: t('stock.consumption'), value: 'out', icon: 'remove' },
        ]"
      />
      <q-input
        v-model.number="movementForm.amount"
        type="number"
        step="any"
        min="0"
        :label="t('stock.quantity', { unit: activeItem?.unit ?? '' })"
        outlined
        dense
        autofocus
      />
      <q-input v-model="movementForm.note" :label="t('stock.note')" outlined dense />
    </FormDialog>

    <!-- Historique des mouvements -->
    <FormDialog
      v-model="itemHistoryDialog"
      icon="history"
      :title="t('stock.history')"
      :subtitle="activeItem?.name"
      width="480px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <q-list v-if="activeItemMovements.length > 0" bordered separator class="rounded-borders">
        <q-item v-for="m in activeItemMovements" :key="m.id">
          <q-item-section>
            <q-item-label :class="m.delta >= 0 ? 'text-positive' : 'text-negative'" class="text-weight-bold">
              {{ m.delta >= 0 ? '+' : '' }}{{ formatNumber(m.delta) }} {{ activeItem?.unit }}
            </q-item-label>
            <q-item-label caption>
              {{ formatDateTime(m.created_at) }}<span v-if="m.note"> — {{ m.note }}</span>
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
      <div v-else class="text-center text-grey-6 q-pa-md">{{ t('stock.noMovement') }}</div>
    </FormDialog>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { usePermissions } from 'src/composables/usePermissions';
import { ref, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useQuasar } from 'quasar';
import { useInventoryStore } from 'src/stores/inventoryStore';
import type { InventoryItem, InventoryMovement } from 'src/types/inventory';
import AppInput from 'src/components/AppInput.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import ScopeChip from 'src/components/ScopeChip.vue';
import ScopeSelector from 'src/components/ScopeSelector.vue';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { scopeFrom, scopePayload, type ScopeValue } from 'src/utils/sharedScope';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatDateTime, formatNumber, isoDate } from 'src/utils/format';
import DateInput from 'src/components/DateInput.vue';

const { t } = useI18n();

const route = useRoute();

const props = defineProps({
  aquaId: { type: Number, required: true },
});

const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const inventoryStore = useInventoryStore();
const aquariumStore = useAquariumStore();

onMounted(async () => {
  await Promise.all([
    inventoryStore.fetch(props.aquaId),
    aquariumStore.aquariums.length === 0 ? aquariumStore.fetch() : Promise.resolve(),
  ]);
});

// --- Stock ---
const sortedItems = computed(() =>
  [...inventoryStore.items].sort((a, b) => {
    const aLow = isLowStock(a);
    const bLow = isLowStock(b);
    if (aLow !== bLow) return aLow ? -1 : 1;
    return a.name.localeCompare(b.name);
  }),
);

const search = ref<string | null>('');
const onlyLowStock = ref(route.query.filtre === 'stock-bas');
const lowStockCount = computed(() => inventoryStore.items.filter(isLowStock).length);

const filteredItems = computed(() => {
  const base = onlyLowStock.value ? sortedItems.value.filter(isLowStock) : sortedItems.value;
  const s = (search.value ?? '').trim().toLowerCase();
  return s ? base.filter((item) => item.name.toLowerCase().includes(s)) : base;
});

// « Ouvert le 01/09/2026 (depuis 28 jours) »
function openedLabel(openedOn: string): string {
  const days = Math.max(0, Math.round((Date.parse(isoDate()) - Date.parse(openedOn)) / 86_400_000));
  return t('stock.openedSince', { date: formatDate(openedOn), n: days }, days);
}

async function markOpenedToday(item: InventoryItem) {
  try {
    await inventoryStore.update(item.id, { opened_on: isoDate() });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('stock.notify.saveFailed')) });
  }
}

function isLowStock(item: InventoryItem): boolean {
  return item.low_stock_threshold != null && item.quantity <= item.low_stock_threshold;
}

const itemDialog = ref(false);
const isEditingItem = ref(false);
const editingItemId = ref<number | null>(null);
const itemForm = ref<{ name: string; unit: string; quantity: number; low_stock_threshold?: number | null; opened_on?: string | null }>({
  name: '',
  unit: '',
  quantity: 0,
});
const itemScope = ref<ScopeValue>(scopeFrom(null, props.aquaId));

function openAddItemDialog() {
  isEditingItem.value = false;
  editingItemId.value = null;
  itemForm.value = { name: '', unit: '', quantity: 0 };
  itemScope.value = scopeFrom(null, props.aquaId);
  itemDialog.value = true;
}

function openEditItemDialog(item: InventoryItem) {
  isEditingItem.value = true;
  editingItemId.value = item.id;
  itemForm.value = {
    name: item.name,
    unit: item.unit,
    quantity: item.quantity,
    low_stock_threshold: item.low_stock_threshold ?? null,
    opened_on: item.opened_on ?? null,
  };
  itemScope.value = scopeFrom(item, props.aquaId);
  itemDialog.value = true;
}

async function saveItem() {
  if (!itemForm.value.name.trim() || !itemForm.value.unit.trim()) {
    $q.notify({ type: 'warning', message: t('stock.notify.nameUnitRequired') });
    return;
  }
  if (itemScope.value.scope === 'multiple' && itemScope.value.aquarium_ids.length === 0) {
    $q.notify({ type: 'warning', message: t('stock.notify.aquariumRequired') });
    return;
  }
  const scope = scopePayload(itemScope.value, props.aquaId);
  try {
    if (isEditingItem.value && editingItemId.value !== null) {
      await inventoryStore.update(editingItemId.value, {
        name: itemForm.value.name.trim(),
        unit: itemForm.value.unit.trim(),
        low_stock_threshold: itemForm.value.low_stock_threshold ?? null,
        opened_on: itemForm.value.opened_on || null,
        ...scope,
      });
    } else {
      await inventoryStore.create({
        aquarium_id: props.aquaId,
        name: itemForm.value.name.trim(),
        unit: itemForm.value.unit.trim(),
        quantity: itemForm.value.quantity,
        low_stock_threshold: itemForm.value.low_stock_threshold ?? null,
        opened_on: itemForm.value.opened_on || null,
        ...scope,
      });
    }
    itemDialog.value = false;
    // L'article peut ne plus concerner ce bac après changement de portée
    if (scope.scope === 'multiple' && !scope.aquarium_ids.includes(props.aquaId)) await inventoryStore.fetch(props.aquaId);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('stock.notify.saveFailed')) });
  }
}

function removeItem(item: InventoryItem) {
  const shared = item.scope !== 'single' ? t('stock.deleteShared') : '';
  confirmRemove(t('stock.item', { name: item.name }), () => inventoryStore.remove(item.id), {
    message: t('stock.deleteMessage', { name: item.name }) + shared,
  });
}

// --- Mouvement de stock ---
const movementDialog = ref(false);
const activeItem = ref<InventoryItem | null>(null);
const movementForm = ref<{ direction: 'in' | 'out'; amount: number | undefined; note: string }>({
  direction: 'in',
  amount: undefined,
  note: '',
});

function openMovementDialog(item: InventoryItem) {
  activeItem.value = item;
  movementForm.value = { direction: 'in', amount: undefined, note: '' };
  movementDialog.value = true;
}

async function saveMovement() {
  if (!activeItem.value) return;
  if (!movementForm.value.amount || movementForm.value.amount <= 0) {
    $q.notify({ type: 'warning', message: t('stock.notify.positive') });
    return;
  }
  const delta = movementForm.value.direction === 'in' ? movementForm.value.amount : -movementForm.value.amount;
  try {
    await inventoryStore.addMovement(activeItem.value.id, { delta, note: movementForm.value.note || null });
    movementDialog.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('stock.notify.movementFailed')) });
  }
}

// --- Historique stock ---
const itemHistoryDialog = ref(false);
const activeItemMovements = ref<InventoryMovement[]>([]);

async function openItemHistoryDialog(item: InventoryItem) {
  activeItem.value = item;
  activeItemMovements.value = await inventoryStore.fetchMovements(item.id);
  itemHistoryDialog.value = true;
}
</script>
