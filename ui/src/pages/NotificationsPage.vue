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

        <div class="col-12">
          <q-card flat bordered :class="{ 'channel-off': !form.email_enabled }">
            <q-card-section class="row items-center justify-between">
              <div class="text-subtitle1 text-weight-bold row items-center">
                <q-icon name="mail" color="primary" class="q-mr-sm" />{{ t('notifSettings.email.title') }}
              </div>
              <q-badge :color="form.email_enabled ? 'positive' : 'grey-5'" :label="form.email_enabled ? t('notifSettings.active') : t('notifSettings.inactive')" />
            </q-card-section>
            <q-card-section class="q-pt-none">
              <q-toggle v-model="form.email_enabled" :label="t('notifSettings.email.enable')" />
              <div class="text-caption text-grey-7 q-mb-md">{{ t('notifSettings.email.intro') }}</div>
              <div class="row q-col-gutter-md">
                <div class="col-12 col-sm-6">
                  <q-input v-model="form.smtp_host" :label="t('notifSettings.email.host')" :placeholder="SMTP_EXAMPLES.host" outlined dense />
                </div>
                <div class="col-6 col-sm-3">
                  <q-select v-model="form.smtp_security" :options="securityOptions" emit-value map-options :label="t('notifSettings.email.security')" outlined dense @update:model-value="onSecurity" />
                </div>
                <div class="col-6 col-sm-3">
                  <q-input v-model.number="form.smtp_port" type="number" min="1" max="65535" :label="t('notifSettings.email.port')" outlined dense />
                </div>
                <div class="col-12 col-sm-6">
                  <q-input v-model="form.smtp_user" :label="t('notifSettings.email.user')" autocomplete="off" outlined dense />
                </div>
                <div class="col-12 col-sm-6">
                  <q-input
                    v-model="form.smtp_password"
                    :label="t('notifSettings.email.password')"
                    type="password"
                    autocomplete="new-password"
                    outlined
                    dense
                    :placeholder="current?.smtp_password_set ? t('notifSettings.saved') : ''"
                    :hint="t('notifSettings.email.passwordHint')"
                  />
                </div>
                <div class="col-12 col-sm-6">
                  <q-input v-model="form.email_from" type="email" :label="t('notifSettings.email.from')" :hint="t('notifSettings.email.fromHint')" outlined dense />
                </div>
                <div class="col-12 col-sm-6">
                  <q-input v-model="form.email_to" :label="t('notifSettings.email.to')" :placeholder="SMTP_EXAMPLES.to" :hint="t('notifSettings.email.toHint')" outlined dense />
                </div>
              </div>
            </q-card-section>
            <q-card-actions align="right">
              <q-btn flat color="primary" icon="notifications" :label="t('notifSettings.test', { channel: t('notifSettings.email.title') })" :loading="testing === 'email'" @click="test('email')" />
            </q-card-actions>
          </q-card>
        </div>
      </div>

      <div class="row items-center justify-between q-mt-md">
        <div class="text-caption text-grey-7">{{ t('notifSettings.testSaves') }}</div>
        <div class="q-gutter-sm">
          <q-btn v-if="current?.telegram_bot_token_set" flat color="negative" :label="t('notifSettings.clearToken', { channel: 'Telegram' })" @click="clearSecret('telegram_bot_token')" />
          <q-btn v-if="current?.ntfy_token_set" flat color="negative" :label="t('notifSettings.clearToken', { channel: 'ntfy' })" @click="clearSecret('ntfy_token')" />
          <q-btn v-if="current?.smtp_password_set" flat color="negative" :label="t('notifSettings.email.clearPassword')" @click="clearSecret('smtp_password')" />
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
type Channel = 'telegram' | 'ntfy' | 'email';
type SmtpSecurity = 'starttls' | 'ssl' | 'none';

interface NotificationSettings {
  provider: Provider;
  telegram_chat_id: string | null;
  telegram_bot_token_set: boolean;
  ntfy_url: string;
  ntfy_topic: string | null;
  ntfy_token_set: boolean;
  email_enabled: boolean;
  smtp_host: string | null;
  smtp_port: number;
  smtp_security: SmtpSecurity;
  smtp_user: string | null;
  smtp_password_set: boolean;
  email_from: string | null;
  email_to: string | null;
}

// Exemples de format de jeton (non traduits)
const TOKEN_EXAMPLES = { telegram: '123456:ABC...', ntfy: 'tk_...' }; // i18n-ignore
const SMTP_EXAMPLES = { host: 'smtp.gmail.com', to: 'moi@example.org' }; // i18n-ignore
const SMTP_PORTS: Record<SmtpSecurity, number> = { starttls: 587, ssl: 465, none: 25 };
const securityOptions = computed(() =>
  (['starttls', 'ssl', 'none'] as const).map((value) => ({ label: t(`notifSettings.email.${value}`), value })),
);

// Port par défaut de la sécurité choisie, si le port saisi était celui d'une autre
function onSecurity(security: SmtpSecurity) {
  if (Object.values(SMTP_PORTS).includes(Number(form.value.smtp_port))) form.value.smtp_port = SMTP_PORTS[security];
}

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
  email_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_security: SmtpSecurity;
  smtp_user: string;
  smtp_password: string;
  email_from: string;
  email_to: string;
}>({
  provider: 'none',
  telegram_bot_token: '',
  telegram_chat_id: '',
  ntfy_url: 'https://ntfy.sh',
  ntfy_topic: '',
  ntfy_token: '',
  email_enabled: false,
  smtp_host: '',
  smtp_port: 587,
  smtp_security: 'starttls',
  smtp_user: '',
  smtp_password: '',
  email_from: '',
  email_to: '',
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
    email_enabled: data.email_enabled,
    smtp_host: data.smtp_host ?? '',
    smtp_port: data.smtp_port,
    smtp_security: data.smtp_security,
    smtp_user: data.smtp_user ?? '',
    smtp_password: '',
    email_from: data.email_from ?? '',
    email_to: data.email_to ?? '',
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
      email_enabled: f.email_enabled,
      smtp_host: f.smtp_host,
      smtp_port: Number(f.smtp_port) || SMTP_PORTS[f.smtp_security],
      smtp_security: f.smtp_security,
      smtp_user: f.smtp_user,
      email_from: f.email_from,
      email_to: f.email_to,
      ...(f.smtp_password ? { smtp_password: f.smtp_password } : {}),
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

async function clearSecret(field: 'telegram_bot_token' | 'ntfy_token' | 'smtp_password') {
  try {
    const { data } = await axios.put<NotificationSettings>('/notification-settings/', { [field]: '' });
    applyServer(data);
    $q.notify({ type: 'positive', message: t(field === 'smtp_password' ? 'notifSettings.email.passwordCleared' : 'notifSettings.tokenCleared') });
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
    const name = channel === 'email' ? t('notifSettings.email.title') : channel;
    $q.notify(
      error
        ? { type: 'negative', message: t('notifSettings.testFailedOn', { channel: name, error }), timeout: 8000 }
        : { type: 'positive', message: t('notifSettings.testSent', { channel: name }) },
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
