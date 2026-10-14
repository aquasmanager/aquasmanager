<!-- Champ date standard : affichage JJ/MM/AAAA, valeur AAAA-MM-JJ, calendrier au clic -->
<template>
  <q-input
    outlined
    dense
    readonly
    class="date-input"
    v-bind="$attrs"
    :model-value="display"
    :clearable="clearable"
    @clear="emit('update:modelValue', null)"
  >
    <template #append>
      <q-icon name="event" class="cursor-pointer" color="grey-7" />
    </template>
    <q-popup-proxy ref="proxy" cover transition-show="scale" transition-hide="scale">
      <q-date :model-value="modelValue" mask="YYYY-MM-DD" minimal first-day-of-week="1" @update:model-value="pick" />
    </q-popup-proxy>
  </q-input>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { QPopupProxy } from 'quasar';

defineOptions({ inheritAttrs: false });

const props = defineProps<{ modelValue: string | null | undefined; clearable?: boolean | undefined }>();
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>();

const proxy = ref<QPopupProxy | null>(null);

const display = computed(() => {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(props.modelValue ?? '');
  return match ? `${match[3]}/${match[2]}/${match[1]}` : '';
});

function pick(value: string | null) {
  emit('update:modelValue', value);
  proxy.value?.hide();
}
</script>

<style scoped>
.date-input :deep(input) {
  cursor: pointer;
}
</style>
