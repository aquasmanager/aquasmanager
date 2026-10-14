<!--
  Calculateur de dosage d'un paramètre : valeur mesurée, objectif, volume
  d'eau et produit → quantité totale, répartie sur plusieurs jours pour ne
  pas dépasser la hausse maximale conseillée par jour. Appliquer crée une
  tâche par jour, décompte le stock et note le dosage au journal.
-->
<template>
  <FormDialog
    :model-value="modelValue"
    :title="t('dosing.title', { name: parameter?.name ?? '' })"
    :subtitle="t('dosing.subtitle')"
    icon="medication_liquid"
    width="620px"
    :loading="saving"
    :submit-label="t('dosing.apply')"
    submit-icon="playlist_add_check"
    :submit-disabled="!result || !product"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="onShow"
    @submit="apply"
  >
    <div v-if="parameter" class="column gap-md">
      <div class="row q-col-gutter-sm">
        <div class="col-6 col-sm-3">
          <q-input v-model.number="current" outlined dense type="number" step="any" :label="t('dosing.current')" :suffix="unit" />
        </div>
        <div class="col-6 col-sm-3">
          <q-input v-model.number="target" outlined dense type="number" step="any" :label="t('dosing.target')" :suffix="unit" />
        </div>
        <div class="col-6 col-sm-3">
          <q-input v-model.number="volume" outlined dense type="number" min="1" :label="t('dosing.volume')" suffix="L" :hint="t('dosing.volumeHint')" />
        </div>
        <div class="col-6 col-sm-3">
          <q-input v-model.number="maxPerDay" outlined dense type="number" min="0" step="any" :label="t('dosing.maxPerDay')" :suffix="unit" />
        </div>
      </div>

      <div class="row q-col-gutter-sm items-start">
        <div class="col">
          <q-select
            v-model="productId"
            outlined
            dense
            emit-value
            map-options
            :options="productOptions"
            :label="t('dosing.product')"
            :hint="productOptions.length ? productEffect : t('dosing.noProduct')"
          />
        </div>
        <div class="col-auto">
          <q-btn flat dense no-caps color="primary" icon="add" :label="t('dosing.newProduct')" @click="productFormOpen = !productFormOpen" />
        </div>
      </div>

      <!-- Nouveau produit : générique ou personnalisé -->
      <q-card v-if="productFormOpen" flat bordered class="q-pa-sm">
        <div class="column gap-sm">
          <q-select v-model="presetIndex" outlined dense emit-value map-options clearable :options="presetOptions" :label="t('dosing.fromPreset')" @update:model-value="applyPreset" />
          <div class="row q-col-gutter-sm">
            <div class="col-12 col-sm-7"><q-input v-model="newProduct.name" outlined dense maxlength="80" :label="t('dosing.productName')" /></div>
            <div class="col-12 col-sm-5"><q-input v-model="newProduct.brand" outlined dense maxlength="60" :label="t('dosing.brand')" /></div>
          </div>
          <q-btn-toggle
            v-model="describeBy"
            dense
            no-caps
            unelevated
            spread
            toggle-color="primary"
            color="grey-2"
            text-color="grey-9"
            :options="[
              { value: 'effect', label: t('dosing.byEffect') },
              { value: 'concentration', label: t('dosing.byConcentration'), disable: !massUnit },
            ]"
          />
          <div v-if="describeBy === 'concentration'" class="row q-col-gutter-sm">
            <div class="col-6 col-sm-4"><q-input v-model.number="concentration" outlined dense type="number" step="any" :label="t('dosing.concentration')" /></div>
            <div class="col-6 col-sm-4">
              <q-select v-model="concentrationUnit" outlined dense :options="['mg/mL', 'g/L', 'mg/L', '%']" :label="t('dosing.concentrationUnit')" />
            </div>
            <div class="col-12 col-sm-4">
              <q-select v-model="newProduct.dose_unit" outlined dense :options="['mL', 'g']" :label="t('dosing.doseUnit')" />
            </div>
            <div class="col-12 text-caption text-grey-7">{{ t('dosing.concentrationHint') }}</div>
          </div>
          <div v-else class="row q-col-gutter-sm">
            <div class="col-6 col-sm-3"><q-input v-model.number="newProduct.dose_amount" outlined dense type="number" step="any" :label="t('dosing.doseAmount')" /></div>
            <div class="col-6 col-sm-3"><q-input v-model="newProduct.dose_unit" outlined dense maxlength="20" :label="t('dosing.doseUnit')" /></div>
            <div class="col-6 col-sm-3"><q-input v-model.number="newProduct.raises" outlined dense type="number" step="any" :label="t('dosing.raises')" :suffix="unit" /></div>
            <div class="col-6 col-sm-3"><q-input v-model.number="newProduct.per_volume_l" outlined dense type="number" step="any" :label="t('dosing.perVolume')" suffix="L" /></div>
          </div>
          <div class="text-caption text-grey-7">{{ t('dosing.effectExample', { amount: formatNumber(formEffect.amount || 0), unit: newProduct.dose_unit, volume: formatNumber(formEffect.volume || 0), raises: formEffect.raises ? formatNumber(formEffect.raises) : '?', param: parameter.name, punit: unit }) }}</div>
          <q-select v-model="newProduct.inventory_item_id" outlined dense clearable emit-value map-options :options="stockOptions" :label="t('dosing.stockItem')" />
          <div class="row justify-end">
            <q-btn unelevated no-caps color="primary" icon="save" :label="t('dosing.saveProduct')" :loading="savingProduct" @click="saveProduct" />
          </div>
        </div>
      </q-card>

      <!-- Résultat -->
      <q-banner v-if="!needed" rounded class="bg-green-1 text-green-10">
        <template #avatar><q-icon name="check_circle" color="positive" /></template>
        {{ t('dosing.nothingToDo') }}
      </q-banner>
      <q-banner v-else-if="result" rounded class="bg-blue-1 text-blue-10">
        <template #avatar><q-icon name="calculate" color="primary" /></template>
        <div class="text-h6 text-weight-bold">{{ formatQuantity(result.total, product?.dose_unit) }}</div>
        <div v-if="result.days > 1">{{ t('dosing.spread', { perDay: formatQuantity(result.perDay, product?.dose_unit), days: result.days }) }}</div>
        <div class="text-caption">{{ t('dosing.raiseBy', { delta: formatNumber(target - current), unit }) }}</div>
      </q-banner>

      <div v-if="result" class="column">
        <q-checkbox v-model="createTasks" dense :label="t('dosing.createTasks', { n: result.days }, result.days)" />
        <q-checkbox v-model="consumeStock" dense :disable="!product?.inventory_item_id" :label="t('dosing.consumeStock')" />
        <q-checkbox v-model="addJournal" dense :label="t('dosing.addJournal')" />
      </div>
      <div class="text-caption text-grey-7">{{ t('dosing.disclaimer') }}</div>
    </div>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import axios from 'axios';
import FormDialog from 'src/components/FormDialog.vue';
import type { WaterParameter } from 'src/types/waterParameter';
import type { InventoryItem } from 'src/types/inventory';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { apiErrorMessage } from 'src/utils/apiError';
import { intlLocale } from 'src/i18n/instance';

interface DosingProduct {
  id: number;
  name: string;
  brand?: string | null;
  parameter: string;
  dose_amount: number;
  dose_unit: string;
  raises: number;
  per_volume_l: number;
  inventory_item_id?: number | null;
  concentration?: number | null;
  concentration_unit?: string | null;
}
type ProductInput = Omit<DosingProduct, 'id'>;
type Preset = ProductInput & { unit: string };

// Concentrations massiques : facteur vers mg/L (paramètres en mg/l ou µg/l, ICP compris)
function massFactor(u: string | null | undefined): number | null {
  const v = (u ?? '').trim().toLowerCase().replace('μ', 'µ').replace(/\s+/g, '');
  if (['mg/l', 'ppm'].includes(v)) return 1;
  if (['µg/l', 'ug/l', 'ppb'].includes(v)) return 0.001;
  if (v === 'g/l') return 1000;
  return null;
}

function convert(value: number, from: string, to: string): number | null {
  const a = massFactor(from);
  const b = massFactor(to);
  return a != null && b != null ? (value * a) / b : null;
}

const props = defineProps<{ modelValue: boolean; aquaId: number; parameter: WaterParameter | null }>();
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

const { t } = useI18n();
const $q = useQuasar();
const aquariumStore = useAquariumStore();

// Hausse maximale conseillée par jour (valeurs prudentes, modifiables)
const MAX_PER_DAY: Record<string, number> = { KH: 1, CA: 20, MG: 100, NO3: 5, PO4: 0.03, GH: 1 };

const current = ref(0);
const target = ref(0);
const volume = ref(0);
const maxPerDay = ref<number | null>(null);
const products = ref<DosingProduct[]>([]);
const presets = ref<Preset[]>([]);
const stock = ref<InventoryItem[]>([]);
const productId = ref<number | null>(null);
const createTasks = ref(true);
const consumeStock = ref(true);
const addJournal = ref(true);
const saving = ref(false);

const unit = computed(() => props.parameter?.unit ?? '');
const key = computed(() => (props.parameter?.name ?? '').trim().toUpperCase());
const product = computed(() => products.value.find((p) => p.id === productId.value) ?? null);
const productOptions = computed(() =>
  products.value
    .filter((p) => p.parameter.trim().toUpperCase() === key.value)
    .map((p) => ({ value: p.id, label: productLabel(p) })),
);
const productEffect = computed(() =>
  product.value
    ? (product.value.concentration ? `${formatNumber(product.value.concentration)} ${product.value.concentration_unit} · ` : '') +
      t('dosing.effectExample', {
        amount: formatNumber(product.value.dose_amount),
        unit: product.value.dose_unit,
        volume: formatNumber(product.value.per_volume_l),
        raises: formatNumber(product.value.raises),
        param: props.parameter?.name ?? '',
        punit: unit.value,
      })
    : '',
);
const stockOptions = computed(() => stock.value.map((i) => ({ value: i.id, label: `${i.name} (${i.unit})` })));

const needed = computed(() => target.value > current.value);

const result = computed(() => {
  const p = product.value;
  if (!p || !needed.value || !volume.value || p.raises <= 0) return null;
  const delta = target.value - current.value;
  const total = (delta / p.raises) * p.dose_amount * (volume.value / p.per_volume_l);
  const days = maxPerDay.value && maxPerDay.value > 0 ? Math.min(14, Math.max(1, Math.ceil(delta / maxPerDay.value))) : 1;
  return { total: round(total), perDay: round(total / days), days };
});

function productLabel(p: Pick<DosingProduct, 'name' | 'brand'>): string {
  return p.brand ? `${p.name} (${p.brand})` : p.name;
}

// Hausse d'une dose : 4 chiffres significatifs (0,000052 mg/l reste exact, pas arrondi à 0,0001)
function roundSignificant(value: number): number {
  return value ? Number(value.toPrecision(4)) : 0;
}

// Grandes quantités dans l'unité supérieure : 62 778 mL -> 62,78 L ; 2 500 g -> 2,5 kg
function formatQuantity(value: number, doseUnit: string | undefined): string {
  const bigger = ({ ml: 'L', g: 'kg' } as Record<string, string>)[(doseUnit ?? '').trim().toLowerCase()];
  if (bigger && value >= 1000) return `${formatNumber(round(value / 1000))} ${bigger}`;
  return `${formatNumber(value)} ${doseUnit ?? ''}`.trim();
}

function round(value: number): number {
  if (value >= 10) return Math.round(value * 10) / 10;
  if (value >= 0.1) return Math.round(value * 100) / 100;
  return Math.round(value * 10000) / 10000;
}

function formatNumber(value: number): string {
  return value.toLocaleString(intlLocale(), { maximumFractionDigits: Math.abs(value) < 0.1 && value !== 0 ? 4 : 2 });
}

async function onShow() {
  const p = props.parameter;
  if (!p) return;
  current.value = p.last_value ?? 0;
  target.value =
    p.target_min != null && p.target_max != null
      ? round((p.target_min + p.target_max) / 2)
      : (p.target_min ?? p.target_max ?? p.last_value ?? 0);
  volume.value = aquariumStore.getById(props.aquaId)?.volume ?? 100;
  maxPerDay.value = MAX_PER_DAY[key.value] ?? null;
  productFormOpen.value = false;
  try {
    const [prod, pre, items] = await Promise.all([
      axios.get<DosingProduct[]>('/dosing/products'),
      axios.get<Preset[]>('/dosing/presets'),
      axios.get<InventoryItem[]>('/inventory-items/', { params: { aquarium_id: props.aquaId } }),
    ]);
    products.value = prod.data;
    presets.value = pre.data;
    stock.value = items.data;
    productId.value = productOptions.value[0]?.value ?? null;
    if (!productOptions.value.length) productFormOpen.value = true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('dosing.loadFailed')) });
  }
}

// --- Nouveau produit ---
const productFormOpen = ref(false);
const savingProduct = ref(false);
const presetIndex = ref<number | null>(null);
const describeBy = ref<'effect' | 'concentration'>('effect');
const concentration = ref<number | null>(null);
const concentrationUnit = ref<'mg/mL' | 'g/L' | 'mg/L' | '%'>('mg/mL');
// Le mode « concentration » n'a de sens que pour un paramètre en masse par litre (mg/l, µg/l...)
const massUnit = computed(() => massFactor(unit.value) != null);

// Élément apporté par unité de produit (mg par mL ou par g)
function mgPerUnit(value: number, cUnit: string): number {
  if (cUnit === 'mg/L') return value / 1000;
  if (cUnit === '%') return value * 10; // % m/m (g de produit) ou m/v (mL) : 1 % = 10 mg
  return value; // mg/mL et g/L
}

// Effet d'une dose de référence (1 mL ou 1 g dans 100 L) dans l'unité du paramètre
const formEffect = computed(() => {
  const p = newProduct.value;
  if (describeBy.value === 'concentration') {
    if (!concentration.value || !massUnit.value) return { amount: 1, volume: 100, raises: 0 };
    const mgPerL = (mgPerUnit(concentration.value, concentrationUnit.value) * 1) / 100;
    return { amount: 1, volume: 100, raises: roundSignificant(convert(mgPerL, 'mg/l', unit.value) ?? 0) };
  }
  return { amount: p.dose_amount, volume: p.per_volume_l, raises: p.raises };
});
const newProduct = ref<ProductInput>({ name: '', brand: null, parameter: '', dose_amount: 1, dose_unit: 'mL', raises: 0, per_volume_l: 100, inventory_item_id: null });
const presetOptions = computed(() =>
  presets.value
    .map((p, index) => ({ value: index, label: p.name, parameter: p.parameter }))
    .filter((p) => p.parameter.toUpperCase() === key.value),
);

function applyPreset(index: number | null) {
  const p = index != null ? presets.value[index] : null;
  if (!p) return;
  // Hausse du produit générique exprimée dans l'unité du paramètre (µg/l pour la plupart des ICP)
  const raises = convert(p.raises, p.unit, unit.value) ?? p.raises;
  describeBy.value = 'effect';
  newProduct.value = { ...newProduct.value, name: p.name, dose_amount: p.dose_amount, dose_unit: p.dose_unit, raises: roundSignificant(raises), per_volume_l: p.per_volume_l, concentration: p.concentration ?? null, concentration_unit: p.concentration_unit ?? null };
}

async function saveProduct() {
  const effect = formEffect.value;
  const p: ProductInput = {
    ...newProduct.value,
    dose_amount: effect.amount,
    per_volume_l: effect.volume,
    raises: effect.raises,
    ...(describeBy.value === 'concentration' ? { concentration: concentration.value, concentration_unit: concentrationUnit.value } : {}),
  };
  if (!p.name.trim() || !(p.dose_amount > 0) || !(p.raises > 0) || !(p.per_volume_l > 0)) {
    $q.notify({ type: 'warning', message: t('dosing.productRequired') });
    return;
  }
  savingProduct.value = true;
  try {
    const { data } = await axios.post<DosingProduct>('/dosing/products', { ...p, name: p.name.trim(), brand: p.brand?.trim() || null, parameter: props.parameter?.name ?? '' });
    products.value = [...products.value, data];
    productId.value = data.id;
    productFormOpen.value = false;
    presetIndex.value = null;
    newProduct.value = { name: '', brand: null, parameter: '', dose_amount: 1, dose_unit: 'mL', raises: 0, per_volume_l: 100, inventory_item_id: null };
    concentration.value = null;
    describeBy.value = 'effect';
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('dosing.productFailed')) });
  } finally {
    savingProduct.value = false;
  }
}

async function apply() {
  const r = result.value;
  if (!r || !product.value) return;
  saving.value = true;
  try {
    await axios.post('/dosing/apply', {
      aquarium_id: props.aquaId,
      product_id: product.value.id,
      total: r.total,
      days: r.days,
      current: current.value,
      target: target.value,
      create_tasks: createTasks.value,
      consume_stock: consumeStock.value && !!product.value.inventory_item_id,
      add_journal: addJournal.value,
    });
    emit('update:modelValue', false);
    $q.notify({ type: 'positive', message: t('dosing.applied') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('dosing.applyFailed')) });
  } finally {
    saving.value = false;
  }
}
</script>
