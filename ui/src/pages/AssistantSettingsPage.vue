<!--
  Assistant IA : désactivé par défaut. AquasManager n'embarque aucun modèle ;
  l'administrateur branche, s'il le souhaite, un LLM local (Ollama, LM Studio...)
  ou un service externe compatible OpenAI (Mistral, OpenAI, OpenRouter...).
-->
<template>
  <q-page class="app-page assistant-page">
    <PageHeader
      icon="smart_toy"
      :title="t('assistant.title')"
      :subtitle="t('assistant.subtitle')"
    />

    <div v-if="loading" class="flex flex-center q-pa-xl"><q-spinner color="primary" size="2em" /></div>

    <template v-else>
      <q-card flat bordered class="q-mb-md">
        <q-card-section class="row items-center no-wrap gap-md">
          <q-icon name="smart_toy" size="28px" :color="form.enabled ? 'primary' : 'grey-6'" />
          <div class="col">
            <div class="text-subtitle1 text-weight-bold">{{ form.enabled ? t('assistant.enabled') : t('assistant.disabled') }}</div>
            <div class="text-caption text-grey-7">{{ t('assistant.intro') }}</div>
          </div>
          <q-toggle v-model="form.enabled" color="positive" :disable="!form.model" :aria-label="t('assistant.enable')" />
        </q-card-section>
      </q-card>

      <q-card flat bordered class="q-mb-md">
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">{{ t('assistant.service') }}</div>
          <div class="row q-col-gutter-sm">
            <div v-for="p in ASSISTANT_PRESETS" :key="p.label" class="col-6 col-sm-4 col-md">
              <q-card
                flat
                bordered
                class="preset cursor-pointer q-pa-sm"
                :class="{ 'preset--active': form.base_url === p.base_url && form.provider === p.provider }"
                tabindex="0"
                @click="applyPreset(p)"
                @keyup.enter="applyPreset(p)"
              >
                <div class="text-weight-bold">{{ p.label }}</div>
                <div class="text-caption text-grey-7">{{ p.local ? t('assistant.presetLocal') : t('assistant.presetExternal') }}</div>
              </q-card>
            </div>
          </div>
        </q-card-section>

        <q-card-section class="q-gutter-md q-pt-none">
          <q-btn-toggle
            v-model="form.provider"
            unelevated
            no-caps
            toggle-color="primary"
            :options="[
              { label: t('assistant.ollamaApi'), value: 'ollama' },
              { label: t('assistant.openaiApi'), value: 'openai' },
            ]"
          />
          <q-input
            v-model="form.base_url"
            :label="t('assistant.baseUrl')"
            outlined
            dense
            :hint="form.provider === 'ollama' ? t('assistant.ollamaHint') : t('assistant.openaiHint')"
          />
          <q-input
            v-model="form.api_key"
            :label="t('assistant.apiKey')"
            type="password"
            outlined
            dense
            autocomplete="off"
            :placeholder="current?.api_key_set ? t('assistant.keySaved') : t('assistant.keyUseless')"
            :hint="t('assistant.keyHint')"
          >
            <template v-if="current?.api_key_set" #append>
              <q-btn flat dense no-caps size="sm" color="negative" :label="t('assistant.clear')" @click="clearKey" />
            </template>
          </q-input>
          <div class="row items-start no-wrap gap-sm">
            <q-select
              v-model="form.model"
              :options="models"
              :label="t('assistant.model')"
              outlined
              dense
              use-input
              fill-input
              hide-selected
              input-debounce="0"
              new-value-mode="add-unique"
              class="col"
              :hint="t('assistant.modelHint')"
              @input-value="(v: string) => (form.model = v)"
            />
            <q-btn outline color="primary" icon="refresh" :label="t('assistant.list')" :loading="loadingModels" @click="loadModels" />
          </div>
        </q-card-section>

        <q-card-section class="q-pt-none">
          <q-toggle v-model="form.data_access" :label="t('assistant.dataAccess')" />
          <div class="text-caption text-grey-7 q-ml-sm">{{ t('assistant.dataAccessHelp') }}</div>
          <q-input
            v-model.number="form.timeout_seconds"
            type="number"
            min="5"
            max="600"
            :label="t('assistant.timeout')"
            outlined
            dense
            class="q-mt-md timeout"
            :hint="t('assistant.timeoutHint')"
          />
        </q-card-section>

        <div v-if="external" class="app-callout app-callout--warn q-mx-md q-mb-md">
          <q-icon name="public" size="22px" />
          <div>{{ form.data_access ? t('assistant.externalWarningData') : t('assistant.externalWarning') }}</div>
        </div>

        <div v-if="testResult" class="app-callout q-mx-md q-mb-md" :class="testResult.ok ? 'app-callout--ok' : 'app-callout--danger'">
          <q-icon :name="testResult.ok ? 'check_circle' : 'error'" size="22px" />
          <div>{{ testResult.message }}<template v-if="testResult.seconds != null"> ({{ testResult.seconds }} s)</template></div>
        </div>

        <q-card-actions align="right" class="q-pa-md">
          <q-btn flat color="primary" icon="network_check" :label="t('assistant.test')" :loading="testing" @click="test" />
          <q-btn unelevated color="primary" icon="save" :label="t('common.save')" :loading="saving" @click="save" />
        </q-card-actions>
      </q-card>

      <i18n-t keypath="assistant.disclaimer" tag="div" class="text-caption text-grey-7" scope="global">
        <template #link><router-link to="/licences">{{ t('licenses.title') }}</router-link></template>
      </i18n-t>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import PageHeader from 'src/components/PageHeader.vue';
import { useAssistantStore } from 'src/stores/assistantStore';
import {
  ASSISTANT_PRESETS,
  isExternalUrl,
  type AssistantSettings,
  type AssistantTestResult,
} from 'src/types/assistant';
import { apiErrorMessage } from 'src/utils/apiError';

const $q = useQuasar();
const { t } = useI18n();
const assistantStore = useAssistantStore();

const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const loadingModels = ref(false);
const current = ref<AssistantSettings | null>(null);
const models = ref<string[]>([]);
const testResult = ref<AssistantTestResult | null>(null);
interface AssistantForm extends Omit<AssistantSettings, 'api_key_set'> {
  api_key: string;
}

const form = ref<AssistantForm>({
  enabled: false,
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model: '',
  api_key: '',
  timeout_seconds: 120,
  data_access: true,
});

const external = computed(() => isExternalUrl(form.value.base_url));

// Réglages du formulaire pour tester ou lister les modèles avant d'enregistrer
function probe() {
  return {
    provider: form.value.provider,
    base_url: form.value.base_url.trim(),
    model: form.value.model.trim(),
    ...(form.value.api_key ? { api_key: form.value.api_key } : {}),
  };
}

function applyPreset(p: (typeof ASSISTANT_PRESETS)[number]) {
  if (form.value.base_url !== p.base_url) {
    form.value.model = '';
    models.value = [];
  }
  form.value.provider = p.provider;
  form.value.base_url = p.base_url;
  testResult.value = null;
}

async function load() {
  try {
    const { data } = await axios.get<AssistantSettings>('/assistant/settings');
    current.value = data;
    form.value = { ...form.value, ...data, api_key: '' };
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('assistant.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

async function loadModels() {
  loadingModels.value = true;
  try {
    models.value = (await axios.post<{ models: string[] }>('/assistant/models', probe())).data.models;
    if (!models.value.length) $q.notify({ type: 'info', message: t('assistant.noModels') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('assistant.modelsFailed')) });
  } finally {
    loadingModels.value = false;
  }
}

async function test() {
  testing.value = true;
  testResult.value = null;
  try {
    testResult.value = (await axios.post<AssistantTestResult>('/assistant/test', probe())).data;
  } catch (err) {
    testResult.value = { ok: false, message: apiErrorMessage(err, t('assistant.testFailed')), seconds: null };
  } finally {
    testing.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const { api_key, ...rest } = form.value;
    const { data } = await axios.put<AssistantSettings>('/assistant/settings', {
      ...rest,
      base_url: rest.base_url.trim(),
      model: rest.model.trim(),
      ...(api_key ? { api_key } : {}),
    });
    current.value = data;
    form.value.api_key = '';
    await assistantStore.fetchStatus();
    $q.notify({ type: 'positive', message: data.enabled ? t('assistant.activated') : t('assistant.savedDisabled') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('assistant.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

async function clearKey() {
  try {
    current.value = (await axios.put<AssistantSettings>('/assistant/settings', { api_key: '' })).data;
    form.value.api_key = '';
    $q.notify({ type: 'positive', message: t('assistant.keyCleared') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('assistant.failed')) });
  }
}

onMounted(load);
</script>

<style scoped>
.assistant-page {
  max-width: 960px;
}

.preset {
  height: 100%;
  transition: border-color 0.15s;
}

.preset--active {
  border-color: var(--q-primary);
  box-shadow: 0 0 0 1px var(--q-primary);
}

.timeout {
  max-width: 320px;
}
</style>
