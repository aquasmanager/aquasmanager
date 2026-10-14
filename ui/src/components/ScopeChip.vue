<!-- Indique qu'une tâche ou un article est partagé avec d'autres aquariums -->
<template>
  <q-chip v-if="entity.scope !== 'single'" dense color="indigo-1" text-color="indigo-9" :icon="entity.scope === 'all' ? 'select_all' : 'join_inner'" class="q-ml-none">
    {{ entity.scope === 'all' ? t('scope.allTanks') : t('scope.sharedCount', entity.aquarium_ids.length) }}
    <q-tooltip>{{ label }}</q-tooltip>
  </q-chip>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { scopeLabel, type ScopedEntity } from 'src/utils/sharedScope';

const props = defineProps<{ entity: ScopedEntity }>();
const { t } = useI18n();
const aquariumStore = useAquariumStore();

const label = computed(() => scopeLabel(props.entity, (id) => aquariumStore.getById(id)?.name));
</script>
