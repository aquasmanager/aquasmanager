<!--
  Aquariums concernés par une tâche ou un article de stock :
  cet aquarium, une sélection de bacs, ou tous (y compris les futurs).
-->
<template>
  <div class="column gap-sm">
    <div class="text-caption text-grey-7">{{ t('scope.label') }}</div>
    <q-btn-toggle
      :model-value="modelValue.scope"
      spread
      unelevated
      no-caps
      toggle-color="primary"
      color="grey-2"
      text-color="grey-8"
      :options="[
        { label: singleLabel ?? t('scope.single'), value: 'single', icon: 'water' },
        { label: t('scope.multiple'), value: 'multiple', icon: 'join_inner' },
        { label: t('scope.all'), value: 'all', icon: 'select_all' },
      ]"
      @update:model-value="changeScope"
    />
    <AppSelect
      v-if="modelValue.scope === 'multiple'"
      :model-value="modelValue.aquarium_ids"
      :options="aquariumOptions"
      :label="t('scope.aquariums')"
      multiple
      use-chips
      @update:model-value="(ids: number[]) => emit('update:modelValue', { scope: 'multiple', aquarium_ids: ids })"
    />
    <div v-else-if="modelValue.scope === 'all'" class="text-caption text-grey-7">
      <q-icon name="info" size="xs" class="q-mr-xs" />{{ t('scope.allHelp') }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import AppSelect from 'src/components/AppSelect.vue';
import { useAquariumStore } from 'src/stores/aquariumStore';
import type { ScopeValue, SharedScope } from 'src/utils/sharedScope';

const props = defineProps<{ modelValue: ScopeValue; currentAquariumId: number; singleLabel?: string }>();
const emit = defineEmits<{ 'update:modelValue': [value: ScopeValue] }>();

const { t } = useI18n();
const aquariumStore = useAquariumStore();
const aquariumOptions = computed(() => aquariumStore.aquariums.map((a) => ({ label: a.name, value: a.id })));

onMounted(async () => {
  if (aquariumStore.aquariums.length === 0) await aquariumStore.fetch();
});

function changeScope(scope: SharedScope) {
  // « Plusieurs » part de l'aquarium courant, à compléter
  const current = props.currentAquariumId ? [props.currentAquariumId] : [];
  const ids = scope === 'multiple' && props.modelValue.aquarium_ids.length === 0 ? current : props.modelValue.aquarium_ids;
  emit('update:modelValue', { scope, aquarium_ids: scope === 'multiple' ? ids : current });
}
</script>
