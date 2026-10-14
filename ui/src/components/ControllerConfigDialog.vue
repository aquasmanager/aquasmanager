<!--
  Configuration ESPHome d'un contrôleur : celle déployée au dernier flash,
  celle qui sera envoyée au prochain flash, et leurs différences.
  Les mots de passe et clés sont masqués par l'API.
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="code"
    :title="t('controllers.config.title')"
    :subtitle="controller ? `${controller.name} (${controller.ip ?? t('controllers.config.noIp')})` : undefined"
    width="1000px"
    :cancel-label="t('common.close')"
    :submit-label="t('controllers.config.flashNow')"
    submit-icon="system_update"
    :hide-submit="!can.manage || !config || config.identical"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="load"
    @submit="emit('flash')"
  >
    <div v-if="loading" class="text-center q-py-xl">
      <q-spinner color="primary" size="40px" />
      <div class="text-grey-7 q-mt-sm">{{ t('controllers.config.generating') }}</div>
    </div>

    <template v-else-if="config">
      <q-banner v-if="config.deployed === null" dense rounded class="bg-blue-1 text-blue-10">
        <template #avatar><q-icon name="info" color="primary" /></template>
        {{ t('controllers.config.unknown') }}
      </q-banner>
      <q-banner v-else-if="config.identical" dense rounded class="bg-green-1 text-green-9">
        <template #avatar><q-icon name="check_circle" color="positive" /></template>
        {{ t('controllers.config.identical') }}
      </q-banner>
      <q-banner v-else dense rounded class="bg-amber-1 text-amber-10">
        <template #avatar><q-icon name="difference" color="amber-9" /></template>
        {{ t('controllers.config.pending') }}
        <template v-if="config.last_sync"> {{ t('controllers.config.lastFlash', { date: formatDateTime(config.last_sync) }) }}</template>
      </q-banner>

      <q-tabs v-model="tab" dense align="left" active-color="primary" indicator-color="primary" class="text-grey-7">
        <q-tab v-if="config.deployed !== null" name="diff" icon="difference" :label="t('controllers.config.diff')" />
        <q-tab name="desired" icon="upcoming" :label="t('controllers.config.desired')" />
        <q-tab v-if="config.deployed !== null" name="deployed" icon="memory" :label="t('controllers.config.deployed')" />
      </q-tabs>

      <div v-if="tab === 'diff'">
        <div v-if="config.identical || !config.diff" class="text-center text-grey-6 q-py-lg">{{ t('controllers.config.noDiff') }}</div>
        <pre v-else class="diff-view font-mono text-caption q-ma-none q-pa-sm rounded-borders"><span
          v-for="(line, index) in diffLines"
          :key="index"
          :class="diffLineClass(line)"
        >{{ line }}
</span></pre>
      </div>
      <YamlCodeEditor
        v-else-if="tab === 'desired'"
        :model-value="config.desired"
        readonly
        :filename="`${controller?.technical_name ?? t('controllers.config.controller')}-${t('controllers.config.desiredFile')}.yaml`"
        height="55vh"
      />
      <YamlCodeEditor
        v-else
        :model-value="config.deployed ?? ''"
        readonly
        :filename="`${controller?.technical_name ?? t('controllers.config.controller')}-${t('controllers.config.deployedFile')}.yaml`"
        height="55vh"
      />
    </template>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import YamlCodeEditor from 'src/components/YamlCodeEditor.vue';
import { usePermissions } from 'src/composables/usePermissions';
import type { Controller } from 'src/types/controller';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDateTime } from 'src/utils/format';

interface ControllerConfig {
  deployed: string | null;
  desired: string;
  diff: string | null;
  identical: boolean;
  last_sync: string | null;
  is_dirty: boolean;
}

const props = defineProps<{ modelValue: boolean; controller: Controller | null }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; flash: [] }>();

const $q = useQuasar();
const { t } = useI18n();
const can = usePermissions();
const config = ref<ControllerConfig | null>(null);
const loading = ref(false);
const tab = ref<'diff' | 'desired' | 'deployed'>('diff');

const diffLines = computed(() => (config.value?.diff ?? '').split('\n'));

function diffLineClass(line: string): string {
  if (line.startsWith('+++') || line.startsWith('---')) return 'text-grey-7';
  if (line.startsWith('+')) return 'diff-add';
  if (line.startsWith('-')) return 'diff-del';
  if (line.startsWith('@@')) return 'text-primary';
  return '';
}

async function load() {
  if (!props.controller) return;
  loading.value = true;
  config.value = null;
  try {
    const { data } = await axios.get<ControllerConfig>(`/controllers/${props.controller.id}/config`);
    config.value = data;
    tab.value = data.deployed === null || data.identical ? 'desired' : 'diff';
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.config.failed')) });
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.diff-view {
  background: var(--app-code-bg);
  border: 1px solid var(--app-border-color);
  max-height: 55vh;
  overflow: auto;
  white-space: pre;
}

.diff-add {
  background: rgba(46, 160, 67, 0.15);
  color: #2ea043;
}

.diff-del {
  background: rgba(248, 81, 73, 0.15);
  color: #f85149;
}
</style>
