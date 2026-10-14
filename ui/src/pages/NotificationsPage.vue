<template>
  <q-page class="app-page notifications-page">
    <PageHeader
      icon="notifications_active"
      :title="t('notifSettings.title')"
      :subtitle="t('notifSettings.subtitle')"
    />

    <div v-if="loading" class="flex flex-center q-pa-xl"><q-spinner color="primary" size="2em" /></div>

    <template v-else>
      <q-card flat bordered class="q-mb-md">
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">{{ t('notifSettings.channel') }}</div>
          <q-btn-toggle
            v-model="form.provider"
           
            unelevated
            toggle-color="primary"
            color="grey-2"
            text-color="grey-8"
            :options="providerOptions"
          />
        </q-card-section>
      </q-card>

      <div class="row q-col-gutter-md">
        <div class="col-12 col-md-6">
          <q-card flat bordered class="full-height" :class="{ 'channel-off': !isActive('telegram') }">
            <q-card-section class="row items-center justify-between">
              <div class="text-subtitle1 text-weight-bold row items-center">
                <!-- i18n-ignore : nom propre du service -->
                <q-icon name="send" color="light-blue-7" class="q-mr-sm" />Telegram
              </div>
              <q-badge :color="isActive('telegram') ? 'positive' : 'grey-5'" :label="isActive('telegram') ? t('notifSettings.active') : t('notifSettings.inactive')" />
            </q-card-section>
            <q-card-section class="q-gutter-md q-pt-none">
              <q-input
                v-model="form.telegram_bot_token"
                :label="t('notifSettings.botToken')"
                type="password"
                outlined
                dense
                :placeholder="current?.telegram_bot_token_set ? t('notifSettings.saved') : TOKEN_EXAMPLES.telegram"
                :hint="t('notifSettings.botHint')"
              />
              <!-- i18n-ignore : nom propre du service -->
              <q-input v-model="form.telegram_chat_id" label="Chat ID" outlined dense :hint="t('notifSettings.chatHint')" />
            </q-card-section>
            <q-card-actions align="right">
              <q-btn flat color="primary" icon="notifications" :label="t('notifSettings.test', { channel: 'Telegram' })" :loading="testing === 'telegram'" @click="test('telegram')" />
            </q-card-actions>
          </q-card>
        </div>

        <div class="col-12 col-md-6">
          <q-card flat bordered class="full-height" :class="{ 'channel-off': !isActive('ntfy') }">
            <q-card-section class="row items-center justify-between">
              <div class="text-subtitle1 text-weight-bold row items-center">
                <!-- i18n-ignore : nom propre du service -->
                <q-icon name="campaign" color="teal" class="q-mr-sm" />ntfy
              </div>
              <q-badge :color="isActive('ntfy') ? 'positive' : 'grey-5'" :label="isActive('ntfy') ? t('notifSettings.active') : t('notifSettings.inactive')" />
            </q-card-section>
            <q-card-section class="q-gutter-md q-pt-none">
              <q-input v-model="form.ntfy_url" :label="t('notifSettings.server')" outlined dense :hint="t('notifSettings.serverHint')" />
              <q-input
                v-model="form.ntfy_topic"
                :label="t('notifSettings.topic')"
                outlined
                dense
                :hint="t('notifSettings.topicHint')"
              >
                <template #append>
                  <q-btn flat dense round icon="casino" size="sm" :aria-label="t('notifSettings.randomTopic')" @click="generateTopic">
                    <q-tooltip>{{ t('notifSettings.randomTopic') }}</q-tooltip>
                  </q-btn>
                </template>
              </q-input>
              <q-input
                v-model="form.ntfy_token"
                :label="t('notifSettings.accessToken')"
                type="password"
                outlined
                dense
                :placeholder="current?.ntfy_token_set ? t('notifSettings.saved') : TOKEN_EXAMPLES.ntfy"
                :hint="t('notifSettings.tokenHint')"
              />
            </q-card-section>
            <q-card-actions align="right">
              <q-btn flat color="primary" icon="notifications" :label="t('notifSettings.test', { channel: 'ntfy' })" :loading="testing === 'ntfy'" @click="test('ntfy')" />
            </q-card-actions>
          </q-card>
        </div>
      </div>

      <div class="row items-center justify-between q-mt-md">
        <div class="text-caption text-grey-7">{{ t('notifSettings.testSaves') }}</div>
        <div class="q-gutter-sm">
          <q-btn v-if="current?.telegram_bot_token_set" flat color="negative" :label="t('notifSettings.clearToken', { channel: 'Telegram' })" @click="clearSecret('telegram_bot_token')" />
          <q-btn v-if="current?.ntfy_token_set" flat color="negative" :label="t('notifSettings.clearToken', { channel: 'ntfy' })" @click="clearSecret('ntfy_token')" />
          <q-btn unelevated color="primary" icon="save" :label="t('common.save')" :loading="saving" @click="save()" />
        </div>
      </div>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import axios, { type AxiosError } from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import PageHeader from 'src/components/PageHeader.vue';

type Provider = 'none' | 'telegram' | 'ntfy' | 'both';
type Channel = 'telegram' | 'ntfy';

interface NotificationSettings {
  provider: Provider;
  telegram_chat_id: string | null;
  telegram_bot_token_set: boolean;
  ntfy_url: string;
  ntfy_topic: string | null;
  ntfy_token_set: boolean;
}

// Exemples de format de jeton (non traduits)
const TOKEN_EXAMPLES = { telegram: '123456:ABC...', ntfy: 'tk_...' }; // i18n-ignore

const $q = useQuasar();
const { t } = useI18n();
const providerOptions = computed(() => [
  { label: t('notifSettings.none'), value: 'none' },
  { label: 'Telegram', value: 'telegram' },
  { label: 'ntfy', value: 'ntfy' },
  { label: t('notifSettings.both'), value: 'both' },
]);
const loading = ref(true);
const saving = ref(false);
const testing = ref<Channel | null>(null);
const current = ref<NotificationSettings | null>(null);
const form = ref<{
  provider: Provider;
  telegram_bot_token: string;
  telegram_chat_id: string;
  ntfy_url: string;
  ntfy_topic: string;
  ntfy_token: string;
}>({
  provider: 'none',
  telegram_bot_token: '',
  telegram_chat_id: '',
  ntfy_url: 'https://ntfy.sh',
  ntfy_topic: '',
  ntfy_token: '',
});

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as AxiosError<{ detail?: unknown }>).response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, '');
  return fallback;
}

function applyServer(data: NotificationSettings) {
  current.value = data;
  form.value = {
    provider: data.provider,
    telegram_bot_token: '',
    telegram_chat_id: data.telegram_chat_id ?? '',
    ntfy_url: data.ntfy_url,
    ntfy_topic: data.ntfy_topic ?? '',
    ntfy_token: '',
  };
}

function isActive(channel: Channel): boolean {
  return form.value.provider === channel || form.value.provider === 'both';
}

function generateTopic() {
  const random = Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, '0')).join('');
  form.value.ntfy_topic = `aquasmanager-${random}`;
}

async function load() {
  loading.value = true;
  try {
    const { data } = await axios.get<NotificationSettings>('/notification-settings/');
    applyServer(data);
  } catch (err) {
    $q.notify({ type: 'negative', message: errorDetail(err, t('notifSettings.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

async function save(notifySuccess = true): Promise<boolean> {
  saving.value = true;
  const f = form.value;
  try {
    const { data } = await axios.put<NotificationSettings>('/notification-settings/', {
      provider: f.provider,
      telegram_chat_id: f.telegram_chat_id,
      ntfy_url: f.ntfy_url,
      ntfy_topic: f.ntfy_topic,
      // Jeton vide = inchangé (jamais renvoyé par l'API)
      ...(f.telegram_bot_token ? { telegram_bot_token: f.telegram_bot_token } : {}),
      ...(f.ntfy_token ? { ntfy_token: f.ntfy_token } : {}),
    });
    applyServer(data);
    if (notifySuccess) $q.notify({ type: 'positive', message: t('notifSettings.configSaved') });
    return true;
  } catch (err) {
    $q.notify({ type: 'negative', message: errorDetail(err, t('notifSettings.saveFailed')) });
    return false;
  } finally {
    saving.value = false;
  }
}

async function clearSecret(field: 'telegram_bot_token' | 'ntfy_token') {
  try {
    const { data } = await axios.put<NotificationSettings>('/notification-settings/', { [field]: '' });
    applyServer(data);
    $q.notify({ type: 'positive', message: t('notifSettings.tokenCleared') });
  } catch (err) {
    $q.notify({ type: 'negative', message: errorDetail(err, t('notifSettings.failed')) });
  }
}

async function test(channel: Channel) {
  testing.value = channel;
  try {
    // Le test utilise la configuration enregistrée : on enregistre d'abord ce qui est saisi
    if (!(await save(false))) return;
    const { data } = await axios.post<{ results: Record<string, string | null> }>('/notification-settings/test', { channel });
    const error = data.results[channel];
    $q.notify(
      error
        ? { type: 'negative', message: t('notifSettings.testFailedOn', { channel, error }), timeout: 8000 }
        : { type: 'positive', message: t('notifSettings.testSent', { channel }) },
    );
  } catch (err) {
    $q.notify({ type: 'negative', message: errorDetail(err, t('notifSettings.testFailed')) });
  } finally {
    testing.value = null;
  }
}

onMounted(load);
</script>

<style scoped>
.notifications-page {
  max-width: 1100px;
  margin: 0 auto;
}

.channel-off {
  opacity: 0.7;
}
</style>
