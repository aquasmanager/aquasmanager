<!--
  Paramètres d'eau partagés (sans compte, lecture seule) : /partage/parametres/<jeton>.
  Lien créé depuis l'onglet Paramètres d'un aquarium › Partager.
-->
<template>
  <q-layout view="hHh lpr fFf">
    <q-header class="app-header">
      <q-toolbar>
        <img :src="logoUrl" alt="" width="30" height="30" class="q-mr-sm" />
        <q-toolbar-title class="text-weight-bold">{{ shared?.aquarium.name ?? t('params.title') }}</q-toolbar-title>
        <LanguageSelect short />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="shared-page q-pa-md">
        <div v-if="loading" class="text-center q-py-xl"><q-spinner color="primary" size="3em" /></div>

        <EmptyState v-else-if="!shared" icon="link_off" :title="t('params.share.public.unavailable')" :message="t('params.share.public.expired')" />

        <template v-else>
          <div class="row items-center q-mb-md q-col-gutter-sm">
            <div class="col-12 col-sm">
              <div class="text-h5 text-weight-bold">{{ t('params.title') }}</div>
              <div class="text-body2 text-grey-7">
                {{ subtitle }}
              </div>
            </div>
            <div class="col-12 col-sm-auto">
              <q-btn outline color="primary" icon="download" :label="t('params.share.download')" :loading="downloading" @click="downloadImage" />
            </div>
          </div>

          <EmptyState v-if="!shared.parameters.length" icon="science" :title="t('params.share.public.noParameter')" />

          <div class="row q-col-gutter-md">
            <div v-for="(param, i) in shared.parameters" :key="param.name" class="col-12 col-sm-6 col-md-4">
              <q-card flat bordered class="full-height q-pa-sm">
                <q-card-section class="row items-baseline q-gutter-x-xs q-pb-xs">
                  <div class="text-subtitle1 text-weight-bold">{{ param.name }}</div>
                  <div v-if="param.full_name" class="text-caption text-grey-6">{{ param.full_name }}</div>
                </q-card-section>
                <q-card-section class="q-pt-none">
                  <div class="row items-baseline justify-between">
                    <div>
                      <span class="text-h4 text-weight-bolder">{{ formatValue(param.last_value) }}</span>
                      <span class="text-body2 text-grey-7 q-ml-xs">{{ param.unit }}</span>
                    </div>
                    <q-chip
                      v-if="param.in_target != null"
                      dense
                      :color="param.in_target ? 'positive' : 'warning'"
                      text-color="white"
                      class="text-weight-bold"
                    >
                      {{ param.in_target ? t('params.optimal') : t('params.outOfTarget') }}
                    </q-chip>
                  </div>
                  <div v-if="param.history.length > 1" class="q-mt-sm">
                    <SparklineChart
                      :data="param.history.map((r) => r.value)"
                      :color="PARAMETER_PALETTE[i % PARAMETER_PALETTE.length]!"
                      :height="35"
                      :target-min="param.target_min ?? null"
                      :target-max="param.target_max ?? null"
                    />
                  </div>
                  <div v-if="formatTarget(param)" class="text-caption text-grey-6 q-mt-sm">
                    {{ t('params.target') }} <b>{{ formatTarget(param) }}</b>
                  </div>
                  <div class="text-caption text-grey-5">{{ t('params.lastReading', { date: formatDate(param.last_reading_at) }) }}</div>
                </q-card-section>
              </q-card>
            </div>
          </div>

          <div class="text-center text-caption text-grey-6 q-mt-xl">
            <a href="https://aquasmanager.fr" target="_blank" rel="noopener" class="text-grey-7">{{ t('params.share.footer') }}</a>
          </div>
        </template>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { exportFile, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import LanguageSelect from 'src/components/LanguageSelect.vue';
import EmptyState from 'src/components/EmptyState.vue';
import SparklineChart from 'src/components/SparklineChart.vue';
import logoUrl from 'src/assets/logo.png';
import { useNoIndex } from 'src/composables/useNoIndex';
import type { SharedParameters } from 'src/types/parameterShare';
import { PARAMETER_PALETTE } from 'src/types/waterParameter';
import { drawParameterCard, formatTarget, formatValue } from 'src/utils/parameterCard';
import { formatDate, formatDateTime, isoDate } from 'src/utils/format';

const { t } = useI18n();
const $q = useQuasar();
const route = useRoute();
useNoIndex();

const shared = ref<SharedParameters | null>(null);
const loading = ref(true);
const downloading = ref(false);

const subtitle = computed(() => {
  if (!shared.value) return '';
  const parts = [`${shared.value.aquarium.volume} L`, shared.value.aquarium.biotope];
  if (shared.value.history_days) parts.push(t('params.share.days', { n: shared.value.history_days }));
  if (shared.value.expires_at) parts.push(t('params.share.until', { date: formatDateTime(shared.value.expires_at) }));
  return parts.filter(Boolean).join(' · ');
});

async function downloadImage() {
  if (!shared.value) return;
  downloading.value = true;
  try {
    const blob = await drawParameterCard(shared.value, {
      title: t('params.title'),
      optimal: t('params.optimal'),
      outOfTarget: t('params.outOfTarget'),
      target: t('params.share.target'),
      footer: t('params.share.footer'),
    });
    exportFile(`${t('params.share.fileName')}-${isoDate(new Date())}.png`, blob, { mimeType: 'image/png' });
  } catch {
    $q.notify({ type: 'negative', message: t('params.share.imageFailed') });
  } finally {
    downloading.value = false;
  }
}

onMounted(async () => {
  try {
    shared.value = (await axios.get<SharedParameters>(`/public/parameters/${String(route.params.token)}`)).data;
  } catch {
    shared.value = null;
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.shared-page {
  max-width: 1100px;
  margin: 0 auto;
}
</style>
