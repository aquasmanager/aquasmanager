<!--
  Licences et avertissement : absence de garantie, limites de responsabilité,
  composants tiers de l'interface (liste générée à la compilation) et du
  serveur (lue dans les paquets installés). Accessible sans compte.
-->
<template>
  <q-layout view="hHh lpr fFf">
    <q-header class="app-header">
      <q-toolbar>
        <q-btn flat round dense icon="arrow_back" :aria-label="t('common.back')" @click="back" />
        <img :src="logoUrl" alt="" width="28" height="28" class="q-mx-sm" />
        <q-toolbar-title class="text-weight-bold">{{ $q.screen.lt.sm ? t('licenses.short') : t('licenses.title') }}</q-toolbar-title>
        <LanguageSelect short />
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="licenses-page q-pa-md">
        <!-- Avertissement -->
        <q-card flat bordered class="q-mb-md">
          <q-card-section>
            <div class="row items-center no-wrap q-mb-sm">
              <q-icon name="gpp_maybe" color="warning" size="26px" class="q-mr-sm" />
              <div class="text-h6 text-weight-bold">{{ t('licenses.warning') }}</div>
            </div>
            <i18n-t keypath="licenses.p1" tag="p" scope="global">
              <template #asIs><b>{{ t('licenses.asIs') }}</b></template>
            </i18n-t>
            <i18n-t keypath="licenses.p2" tag="p" scope="global">
              <template #notReplace><b>{{ t('licenses.notReplace') }}</b></template>
            </i18n-t>
            <i18n-t keypath="licenses.p3" tag="p" scope="global">
              <template #indicative><b>{{ t('licenses.indicative') }}</b></template>
            </i18n-t>
            <p class="q-mb-none">{{ t('licenses.p4') }}</p>
          </q-card-section>
        </q-card>

        <!-- AquasManager -->
        <q-card flat bordered class="q-mb-md">
          <q-card-section>
            <div class="text-h6 text-weight-bold q-mb-xs">AquasManager</div>
            <div class="text-body2">© {{ year }} AquasManager. {{ t('licenses.rights') }}</div>
            <div class="text-caption text-grey-7 app-mono">{{ t('licenses.version', { version: APP_BUILD === 'dev' ? APP_VERSION_LABEL : `${APP_VERSION_LABEL} (${APP_BUILD})` }) }}<template v-if="serverVersion"> · {{ t('licenses.serverVersion', { version: serverVersion }) }}</template><template v-if="APP_BUILT_AT"> · {{ t('licenses.builtAt', { date: formatDateTime(APP_BUILT_AT) }) }}</template></div>
            <div class="text-body2 text-grey-7 q-mt-sm">{{ t('licenses.thanks') }}</div>
          </q-card-section>
        </q-card>

        <!-- Composants tiers -->
        <q-card flat bordered>
          <q-card-section class="q-pb-none">
            <div class="text-h6 text-weight-bold">{{ t('licenses.thirdParty') }}</div>
            <div class="row q-gutter-xs q-mt-xs">
              <span v-for="[name, count] in licenseCounts" :key="name" class="app-tag app-tag--teal">{{ name }} · {{ count }}</span>
            </div>
          </q-card-section>

          <q-tabs v-model="tab" dense align="left" active-color="primary" indicator-color="primary" class="text-grey-7 q-mt-sm" no-caps>
            <q-tab name="front" :label="t('licenses.front', { n: front.length })" />
            <q-tab name="server" :label="server ? t('licenses.serverCount', { n: server.python.length }) : t('licenses.server')" />
            <q-tab name="external" :label="t('licenses.external')" />
          </q-tabs>
          <q-separator />

          <q-card-section>
            <template v-if="tab === 'external'">
              <q-list v-if="server" separator>
                <q-item v-for="c in server.external" :key="c.name">
                  <q-item-section>
                    <q-item-label class="text-weight-bold">
                      <a :href="c.url" target="_blank" rel="noopener">{{ c.name }}</a>
                    </q-item-label>
                    <q-item-label caption>{{ c.usage }}</q-item-label>
                  </q-item-section>
                  <q-item-section side top><span class="app-tag">{{ c.license }}</span></q-item-section>
                </q-item>
              </q-list>
              <div v-else class="text-grey-7">{{ serverMessage }}</div>
            </template>

            <template v-else>
              <q-input v-model="search" dense outlined clearable :placeholder="t('licenses.search')" class="q-mb-sm">
                <template #prepend><q-icon name="search" /></template>
              </q-input>
              <div v-if="tab === 'server' && !server" class="text-grey-7">{{ serverMessage }}</div>
              <q-list v-else dense separator>
                <q-item v-for="p in filtered" :key="`${p.name}@${p.version}`">
                  <q-item-section>
                    <q-item-label>
                      <a v-if="p.url" :href="p.url" target="_blank" rel="noopener">{{ p.name }}</a>
                      <template v-else>{{ p.name }}</template>
                      <span class="text-grey-6 app-mono q-ml-xs">{{ p.version }}</span>
                    </q-item-label>
                    <q-item-label v-if="p.note" caption>{{ p.note }}</q-item-label>
                  </q-item-section>
                  <q-item-section side><span class="app-tag" :class="{ 'app-tag--warn': p.note }">{{ p.license }}</span></q-item-section>
                </q-item>
                <q-item v-if="!filtered.length"><q-item-section class="text-grey-6">{{ t('licenses.noResult') }}</q-item-section></q-item>
              </q-list>
            </template>
          </q-card-section>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { useI18n } from 'vue-i18n';
import LanguageSelect from 'src/components/LanguageSelect.vue';
import logoUrl from 'src/assets/logo.png';
import frontLicenses from 'src/assets/licenses-front.json';
import { useAuthStore } from 'src/stores/authStore';
import { APP_BUILD, APP_BUILT_AT, APP_VERSION_LABEL } from 'src/composables/useAppUpdate';
import { formatDateTime } from 'src/utils/format';

interface PackageLicense {
  name: string;
  version: string;
  license: string;
  url: string | null;
  note?: string | null;
}

interface ServerLicenses {
  external: { name: string; license: string; url: string; usage: string }[];
  python: PackageLicense[];
}

const { t } = useI18n();
const router = useRouter();
const auth = useAuthStore();
const year = new Date().getFullYear();
const tab = ref<'front' | 'server' | 'external'>('front');
const search = ref('');
const front = frontLicenses as PackageLicense[];
const server = ref<ServerLicenses | null>(null);
const serverFailed = ref(false);
const serverMessage = computed(() => (serverFailed.value ? t('licenses.serverUnavailable') : t('licenses.signIn')));

const current = computed<PackageLicense[]>(() => (tab.value === 'server' ? server.value?.python ?? [] : front));
const filtered = computed(() => {
  const q = (search.value ?? '').trim().toLowerCase();
  return q ? current.value.filter((p) => `${p.name} ${p.license}`.toLowerCase().includes(q)) : current.value;
});
const licenseCounts = computed(() => {
  const counts = new Map<string, number>();
  for (const p of [...front, ...(server.value?.python ?? [])]) counts.set(p.license, (counts.get(p.license) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
});

function back() {
  if (window.history.length > 1) router.back();
  else void router.push(auth.accessToken ? '/home' : '/login');
}

// Version du serveur (API), même numérotation que l'interface
const serverVersion = ref<string | null>(null);

onMounted(async () => {
  if (!auth.accessToken) return;
  axios
    .get<{ version: string; build: string }>('/about/version')
    .then(({ data }) => (serverVersion.value = data.build === 'dev' ? data.version : `${data.version} (${data.build})`))
    .catch(() => undefined);
  try {
    server.value = (await axios.get<ServerLicenses>('/about/licenses')).data;
  } catch {
    serverFailed.value = true;
  }
});
</script>

<style scoped>
.licenses-page {
  max-width: 900px;
  margin: 0 auto;
}

.licenses-page p {
  line-height: 1.6;
}

.licenses-page a {
  color: inherit;
  text-decoration-color: color-mix(in srgb, currentColor 35%, transparent);
}
</style>
