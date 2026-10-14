<!--
  Lieu de vente d'une cession : choisir un lieu existant ou en taper un
  nouveau (créé à l'enregistrement du certificat). v-model : id du lieu,
  nom d'un nouveau lieu, ou null.
-->
<template>
  <q-select
    :model-value="modelValue"
    :options="filteredOptions"
    :label="t('frags.location.label')"
    outlined
    dense
    emit-value
    map-options
    use-input
    clearable
    input-debounce="0"
    new-value-mode="add-unique"
    :hint="t('frags.location.hint')"
    @filter="filter"
    @new-value="addNew"
    @update:model-value="(value: LocationChoice) => emit('update:modelValue', value ?? null)"
  >
    <template #prepend><q-icon name="place" /></template>
    <template #option="scope">
      <q-item v-bind="scope.itemProps">
        <q-item-section>
          <q-item-label>{{ scope.opt.label }}</q-item-label>
          <q-item-label v-if="scope.opt.caption" caption>{{ scope.opt.caption }}</q-item-label>
        </q-item-section>
      </q-item>
    </template>
  </q-select>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import axios from 'axios';
import { useI18n } from 'vue-i18n';
import type { LocationChoice, SaleLocation } from 'src/types/frag';

defineProps<{ modelValue: LocationChoice }>();
const { t } = useI18n();
const emit = defineEmits<{ 'update:modelValue': [value: LocationChoice]; loaded: [locations: SaleLocation[]] }>();

interface Option {
  label: string;
  value: number | string;
  caption?: string | undefined;
}

const locations = ref<SaleLocation[]>([]);
const added = ref<Option[]>([]);
const needle = ref('');

const options = computed<Option[]>(() => [
  ...locations.value.map((l) => ({
    label: l.name,
    value: l.id,
    caption: l.certificate_count ? t('frags.location.certificates', l.certificate_count) : undefined,
  })),
  ...added.value,
]);
const filteredOptions = computed(() =>
  needle.value ? options.value.filter((o) => o.label.toLowerCase().includes(needle.value)) : options.value,
);

function filter(value: string, update: (fn: () => void) => void) {
  update(() => (needle.value = value.toLowerCase()));
}

function addNew(value: string, done: (item?: Option, mode?: 'add' | 'add-unique' | 'toggle') => void) {
  const name = value.trim().replace(/\s+/g, ' ');
  if (!name) return done();
  const existing = options.value.find((o) => o.label.toLowerCase() === name.toLowerCase());
  if (existing) return done(existing, 'add-unique');
  const option = { label: name, value: name, caption: t('frags.location.new') };
  added.value.push(option);
  done(option, 'add-unique');
}

onMounted(async () => {
  try {
    locations.value = (await axios.get<SaleLocation[]>('/sale-locations/')).data;
    emit('loaded', locations.value);
  } catch {
    locations.value = [];
  }
});
</script>
