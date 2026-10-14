<!-- src/components/BaseInfoDialog.vue -->
<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="width: 640px; max-width: 95vw">
      <q-card-section class="row items-start no-wrap q-pb-sm">
        <q-avatar size="40px" color="blue-1" text-color="primary" icon="info" class="q-mr-md" />
        <div class="col">
          <div class="text-h6 text-weight-bold">{{ title ?? t('actions.details') }}</div>
          <div class="text-body2 text-grey-7">{{ subtitle ?? t('info.subtitle') }}</div>
        </div>
        <q-btn icon="close" flat round dense color="grey-7" :aria-label="t('common.close')" v-close-popup />
      </q-card-section>

      <q-separator />

      <q-card-section class="scroll" style="max-height: 72vh">
        <div v-if="filteredData.length > 0" class="row q-col-gutter-md">
          <div v-for="{ key, label, value } in filteredData" :key="key" class="col-12 col-sm-6">
            <div class="text-caption text-grey-7">{{ label }}</div>
            <div class="text-body1 text-weight-medium ellipsis">{{ value }}</div>
          </div>
        </div>

        <slot />
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { intlLocale } from 'src/i18n/instance';

const i18n = useI18n();
const { t } = i18n;

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  title: { type: String, default: undefined },
  subtitle: { type: String, default: undefined },
  data: {
    type: Object as PropType<object | undefined | null>,
    default: null
  },
  excludeKeys: {
    type: Array as PropType<string[]>,
    default: () => ['yaml_config']
  }
});

defineEmits(['update:modelValue']);

// Libellés lisibles des champs techniques les plus courants (info.fields.*)
function fieldLabel(key: string): string {
  return i18n.te(`info.fields.${key}`) ? t(`info.fields.${key}`) : key;
}
const HIDDEN_KEYS = ['actions', 'photo', 'last_config'];

function display(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? t('actions.yes') : t('actions.no');
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) return new Date(value).toLocaleString(intlLocale());
  if (typeof value === 'object') return JSON.stringify(value);
  return typeof value === 'number' || typeof value === 'string' ? String(value) : '—';
}

const filteredData = computed(() => {
  if (!props.data) return [];
  return Object.entries(props.data as Record<string, unknown>)
    .filter(([key]) => !props.excludeKeys.includes(key) && !HIDDEN_KEYS.includes(key))
    .map(([key, value]) => ({ key, label: fieldLabel(key), value: display(value) }));
});


</script>
