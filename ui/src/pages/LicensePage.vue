<!--
  Licence de l'installation : fonctionnalités réservées (ouvertes ou non),
  clé collée par un administrateur, identifiant d'installation à
  communiquer pour obtenir une clé réservée à celle-ci.
-->
<template>
  <q-page class="app-page license-page">
    <PageHeader icon="verified" :title="t('licensePage.title')" :subtitle="t('licensePage.subtitle')" />

    <div v-if="!status" class="flex flex-center q-pa-xl"><q-spinner color="primary" size="2em" /></div>

    <template v-else>
      <q-card flat bordered class="q-mb-md">
        <q-card-section class="row items-center no-wrap gap-md">
          <q-icon :name="status.valid ? 'verified' : status.error ? 'gpp_bad' : 'gpp_maybe'" size="32px" :color="status.valid ? 'positive' : status.error ? 'negative' : 'grey-6'" />
          <div class="col">
            <div class="text-subtitle1 text-weight-bold">
              {{ status.valid ? t('licensePage.active') : status.error ? t('licensePage.refused') : t('licensePage.none') }}
            </div>
            <div v-if="status.error" class="text-caption text-negative">{{ status.error }}</div>
            <div v-else-if="status.valid" class="text-caption text-grey-7">
              {{ status.client }} ·
              {{ status.expires ? t('licensePage.expires', { date: formatDate(status.expires) }) : t('licensePage.noExpiry') }} ·
              {{ status.source === 'env' ? t('licensePage.sourceEnv') : t('licensePage.sourceApp') }}
            </div>
            <div v-else class="text-caption text-grey-7">{{ t('licensePage.noneHelp') }}</div>
          </div>
        </q-card-section>
        <q-separator />
        <q-list separator>
          <q-item v-for="(description, feature) in status.paid_features" :key="feature">
            <q-item-section avatar>
              <q-icon :name="FEATURE_ICONS[feature] ?? 'extension'" :color="has(feature) ? 'primary' : 'grey-5'" />
            </q-item-section>
            <q-item-section>
              <q-item-label class="text-weight-medium">{{ featureLabel(feature, description) }}</q-item-label>
            </q-item-section>
            <q-item-section side>
              <span class="app-tag" :class="has(feature) ? 'app-tag--ok' : ''">
                {{ has(feature) ? t('licensePage.open') : t('licensePage.closed') }}
              </span>
            </q-item-section>
          </q-item>
        </q-list>
      </q-card>

      <q-card flat bordered class="q-mb-md">
        <q-card-section class="column gap-sm">
          <div class="text-subtitle2">{{ t('licensePage.instance') }}</div>
          <div class="row items-center no-wrap gap-sm">
            <code class="app-mono instance-id">{{ status.instance_id }}</code>
            <q-btn flat round dense icon="content_copy" :aria-label="t('licensePage.copy')" @click="copyInstance">
              <q-tooltip>{{ t('licensePage.copy') }}</q-tooltip>
            </q-btn>
          </div>
          <div class="text-caption text-grey-7">{{ t('licensePage.instanceHelp') }}</div>
        </q-card-section>
      </q-card>

      <q-card flat bordered>
        <q-card-section class="column gap-sm">
          <div class="text-subtitle2">{{ t('licensePage.key') }}</div>
          <q-input v-model="key" type="textarea" outlined dense autogrow :placeholder="t('licensePage.keyPlaceholder')" input-class="app-mono" />
        </q-card-section>
        <q-card-actions align="right" class="q-px-md q-pb-md">
          <q-btn v-if="status.source === 'app'" flat color="negative" icon="delete" :label="t('licensePage.remove')" @click="askRemove" />
          <q-btn unelevated color="primary" icon="key" :label="t('licensePage.save')" :disable="key.trim().length < 10" :loading="saving" @click="save" />
        </q-card-actions>
      </q-card>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { copyToClipboard, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import PageHeader from 'src/components/PageHeader.vue';
import { useLicenseStore, type Feature } from 'src/stores/licenseStore';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate } from 'src/utils/format';

const FEATURE_ICONS: Record<string, string> = { bourse: 'storefront', assistant: 'smart_toy' };

const i18n = useI18n();
const { t } = i18n;
const $q = useQuasar();
const license = useLicenseStore();
const status = computed(() => license.status);
const key = ref('');
const saving = ref(false);

function has(feature: string): boolean {
  return license.has(feature as Feature);
}

// Libellé traduit si connu, sinon la description donnée par l'API
function featureLabel(feature: string, description: string): string {
  const path = `licensePage.features.${feature}`;
  return i18n.te(path) ? t(path) : description;
}

async function copyInstance() {
  if (!status.value) return;
  await copyToClipboard(status.value.instance_id);
  $q.notify({ type: 'positive', message: t('licensePage.copied'), timeout: 1500 });
}

async function save() {
  saving.value = true;
  try {
    await license.save(key.value.trim());
    key.value = '';
    $q.notify({ type: 'positive', message: t('licensePage.saved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('licensePage.saveFailed')), timeout: 6000 });
  } finally {
    saving.value = false;
  }
}

function askRemove() {
  $q.dialog({
    title: t('licensePage.removeTitle'),
    message: t('licensePage.removeMessage'),
    cancel: { label: t('common.cancel'), flat: true, color: 'grey-8' },
    ok: { label: t('licensePage.remove'), color: 'negative', unelevated: true },
  }).onOk(() => {
    license.remove().catch((err: unknown) => $q.notify({ type: 'negative', message: apiErrorMessage(err, t('licensePage.saveFailed')) }));
  });
}

onMounted(() => {
  license.refresh().catch((err: unknown) => $q.notify({ type: 'negative', message: apiErrorMessage(err, t('licensePage.loadFailed')) }));
});
</script>

<style scoped>
.license-page {
  max-width: 820px;
}

.instance-id {
  word-break: break-all;
}
</style>
