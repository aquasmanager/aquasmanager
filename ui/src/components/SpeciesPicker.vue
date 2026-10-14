<template>
  <div class="species-picker">
    <q-select
      :model-value="selected"
      :options="options"
      option-label="common_name"
      use-input
      input-debounce="250"
      outlined
      dense
      clearable
      :loading="loading"
      :label="t(`livestock.picker.${kind}`)"
      @filter="onFilter"
      @update:model-value="onSelect"
    >
      <template #prepend><q-icon name="menu_book" /></template>
      <template #option="scope">
        <q-item v-bind="scope.itemProps">
          <q-item-section>
            <q-item-label>{{ scope.opt.common_name }}</q-item-label>
            <q-item-label caption class="text-italic">{{ scope.opt.scientific_name }}</q-item-label>
          </q-item-section>
          <q-item-section v-if="scope.opt.warnings.length" side>
            <q-icon name="warning" color="warning" size="xs">
              <q-tooltip>{{ scope.opt.warnings.join(' ') }}</q-tooltip>
            </q-icon>
          </q-item-section>
        </q-item>
      </template>
      <template #no-option>
        <q-item>
          <q-item-section class="text-grey-6">{{ t('livestock.picker.none') }}</q-item-section>
        </q-item>
      </template>
    </q-select>

    <div v-if="selected && (selected.warnings.length || selected.notes || selected.link)" class="q-mt-xs">
      <div v-for="w in selected.warnings" :key="w" class="text-caption text-orange-9 row items-center no-wrap">
        <q-icon name="warning" size="xs" class="q-mr-xs" />{{ w }}
      </div>
      <div v-if="selected.notes" class="text-caption text-grey-7">{{ selected.notes }}</div>
      <a v-if="selected.link" :href="selected.link" target="_blank" rel="noopener" class="text-caption">{{ t('livestock.picker.reference') }}</a>
    </div>
  </div>
</template>

<script setup lang="ts" generic="K extends SpeciesKind">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useSpeciesStore } from 'src/stores/speciesStore';
import type { SpeciesByKind, SpeciesKind } from 'src/types/species';

const { t } = useI18n();

type Species = SpeciesByKind[K];

const props = defineProps<{ kind: K; aquariumId?: number | null }>();
const emit = defineEmits<{ select: [species: Species] }>();

const store = useSpeciesStore();
const options = ref<Species[]>([]);
const selected = ref<Species | null>(null);
const loading = ref(false);

function onFilter(value: string, update: (fn: () => void) => void) {
  loading.value = true;
  store
    .search(props.kind, value, props.aquariumId, true)
    .then((results) => update(() => (options.value = results as Species[])))
    .catch(() => update(() => (options.value = [])))
    .finally(() => (loading.value = false));
}

function onSelect(species: Species | null) {
  selected.value = species;
  if (species) emit('select', species);
}
</script>
