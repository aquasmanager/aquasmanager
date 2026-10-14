<!--
  Partager les paramètres d'eau d'un aquarium : image (PNG dessinée dans le
  navigateur), texte à coller, ou lien public en lecture seule (durée choisie,
  supprimable à tout moment).
-->
<template>
  <q-dialog :model-value="modelValue" @update:model-value="(v: boolean) => emit('update:modelValue', v)" @show="onShow" @hide="onHide">
    <q-card style="width: 720px; max-width: 95vw">
      <q-card-section class="row items-start no-wrap q-pb-sm">
        <q-avatar size="40px" color="blue-1" text-color="primary" icon="share" class="q-mr-md" />
        <div class="col">
          <div class="text-h6 text-weight-bold">{{ t('params.share.title') }}</div>
          <div class="text-body2 text-grey-7">{{ t('params.share.subtitle') }}</div>
        </div>
        <q-btn flat round dense icon="close" color="grey-7" :aria-label="t('common.close')" v-close-popup />
      </q-card-section>

      <q-card-section class="row items-center q-col-gutter-sm q-pt-none">
        <div class="col-12 col-sm-6">
          <q-select v-model="historyDays" :options="periodOptions" emit-value map-options dense outlined :label="t('params.share.period')" />
        </div>
        <div class="col-12 col-sm-6">
          <q-toggle v-model="pinnedOnly" :disable="!hasPinned" :label="t('params.share.pinnedOnly')" />
        </div>
      </q-card-section>

      <q-tabs v-model="tab" dense align="left" active-color="primary" indicator-color="primary" class="text-grey-7" narrow-indicator>
        <q-tab name="image" icon="image" :label="t('params.share.image')" />
        <q-tab name="text" icon="notes" :label="t('params.share.text')" />
        <q-tab name="link" icon="link" :label="t('params.share.link')" />
      </q-tabs>
      <q-separator />

      <q-card-section v-if="!data.parameters.length" class="text-center text-grey-6 q-py-lg">
        {{ t('params.share.empty') }}
      </q-card-section>

      <q-tab-panels v-else v-model="tab" animated>
        <q-tab-panel name="image" class="q-pa-md">
          <div class="share-preview">
            <q-spinner v-if="!imageUrl" color="primary" size="2em" class="q-ma-lg" />
            <img v-else :src="imageUrl" :alt="t('params.share.imageAlt', { name: data.aquarium.name })" />
          </div>
          <div class="row justify-end q-gutter-sm q-mt-md">
            <q-btn outline color="primary" icon="download" :label="t('params.share.download')" :disable="!imageBlob" @click="downloadImage" />
            <q-btn v-if="canShareFiles" unelevated color="primary" icon="share" :label="t('params.share.shareAction')" :disable="!imageBlob" @click="shareImage" />
          </div>
        </q-tab-panel>

        <q-tab-panel name="text" class="q-pa-md">
          <q-input :model-value="text" type="textarea" outlined readonly autogrow input-class="share-text" />
          <div class="row justify-end q-gutter-sm q-mt-md">
            <q-btn outline color="primary" icon="content_copy" :label="t('params.share.copy')" @click="copy(text, t('params.share.textCopied'))" />
            <q-btn v-if="canShare" unelevated color="primary" icon="share" :label="t('params.share.shareAction')" @click="shareText" />
          </div>
        </q-tab-panel>

        <q-tab-panel name="link" class="q-pa-md">
          <div class="text-body2 text-grey-8 q-mb-md">{{ t('params.share.linkHelp') }}</div>
          <div v-if="can.edit" class="row items-start q-col-gutter-sm q-mb-md">
            <div class="col-12 col-sm-5">
              <q-input v-model="label" dense outlined maxlength="80" :label="t('params.share.label')" :placeholder="t('params.share.labelPlaceholder')" />
            </div>
            <div class="col-12 col-sm-4">
              <q-select v-model="expiresIn" :options="expiryOptions" emit-value map-options dense outlined :label="t('params.share.expires')" />
            </div>
            <div class="col-12 col-sm-3">
              <q-btn unelevated color="primary" icon="add_link" class="full-width" :label="t('params.share.create')" :loading="creating" @click="createLink" />
            </div>
          </div>

          <div v-if="loadingLinks" class="text-center q-py-md"><q-spinner color="primary" size="2em" /></div>
          <div v-else-if="!links.length" class="text-grey-6 text-center q-py-md">{{ t('params.share.noLink') }}</div>
          <q-list v-else bordered separator class="rounded-borders">
            <q-item v-for="link in links" :key="link.id">
              <q-item-section>
                <q-item-label class="text-weight-medium">
                  {{ link.label || t('params.share.untitled') }}
                  <q-badge v-if="link.state === 'expired'" color="grey-6" class="q-ml-xs">{{ t('params.share.expired') }}</q-badge>
                </q-item-label>
                <q-item-label caption>{{ linkDescription(link) }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <div class="row no-wrap items-center">
                  <template v-if="link.state === 'active'">
                    <q-btn flat round dense icon="open_in_new" color="grey-7" :href="parameterShareUrl(link.token)" target="_blank">
                      <q-tooltip>{{ t('params.share.open') }}</q-tooltip>
                    </q-btn>
                    <q-btn flat round dense icon="content_copy" color="primary" @click="copy(parameterShareUrl(link.token), t('params.share.linkCopied'))">
                      <q-tooltip>{{ t('params.share.copyLink') }}</q-tooltip>
                    </q-btn>
                    <q-btn v-if="canShare" flat round dense icon="share" color="primary" @click="shareLink(link)">
                      <q-tooltip>{{ t('params.share.shareAction') }}</q-tooltip>
                    </q-btn>
                  </template>
                  <q-btn v-if="can.edit" flat round dense icon="delete" color="negative" @click="removeLink(link)">
                    <q-tooltip>{{ t('params.share.revoke') }}</q-tooltip>
                  </q-btn>
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </q-tab-panel>
      </q-tab-panels>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { copyToClipboard, exportFile, useQuasar } from 'quasar';
import axios from 'axios';
import type { WaterParameter, WaterParameterReading } from 'src/types/waterParameter';
import { parameterShareUrl, type ParameterShareLink, type SharedParameters, type ShareHistoryDays } from 'src/types/parameterShare';
import { drawParameterCard, parametersText } from 'src/utils/parameterCard';
import { usePermissions } from 'src/composables/usePermissions';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatDateTime, isoDate } from 'src/utils/format';

const props = defineProps<{
  modelValue: boolean;
  aquaId: number;
  parameters: WaterParameter[];
  history: Record<number, WaterParameterReading[]>;
}>();
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const aquariumStore = useAquariumStore();

const tab = ref<'image' | 'text' | 'link'>('image');
const historyDays = ref<ShareHistoryDays>(30);
const pinnedOnly = ref(false);
const hasPinned = computed(() => props.parameters.some((p) => p.pinned));

const periodOptions = computed(() => [
  { value: 0, label: t('params.share.latestOnly') },
  { value: 7, label: t('params.share.days', { n: 7 }) },
  { value: 30, label: t('params.share.days', { n: 30 }) },
  { value: 90, label: t('params.share.days', { n: 90 }) },
]);
const expiryOptions = computed(() => [
  { value: 1, label: t('params.share.expiresDays', { n: 1 }, 1) },
  { value: 7, label: t('params.share.expiresDays', { n: 7 }, 7) },
  { value: 30, label: t('params.share.expiresDays', { n: 30 }, 30) },
  { value: null, label: t('params.share.never') },
]);

// Mêmes données que la page publique, construites ici sans appel au serveur
const data = computed<SharedParameters>(() => {
  const aquarium = aquariumStore.getById(props.aquaId);
  const now = new Date();
  const since = now.getTime() - historyDays.value * 86400000;
  const params = [...props.parameters]
    .filter((p) => p.last_value != null && (p.pinned || !pinnedOnly.value))
    .sort((a, b) => (a.pinned !== b.pinned ? (a.pinned ? -1 : 1) : a.name.localeCompare(b.name)));
  return {
    aquarium: {
      name: aquarium?.name ?? '',
      volume: aquarium?.volume ?? 0,
      water_type: aquarium?.water_type ?? '',
      biotope: aquarium?.biotope ?? '',
    },
    history_days: historyDays.value,
    generated_at: now.toISOString(),
    parameters: params.map((p) => ({
      name: p.name,
      full_name: p.full_name ?? null,
      unit: p.unit ?? null,
      target_min: p.target_min ?? null,
      target_max: p.target_max ?? null,
      last_value: p.last_value ?? null,
      last_reading_at: p.last_reading_at ?? null,
      in_target: p.in_target ?? null,
      history: historyDays.value
        ? (props.history[p.id] ?? [])
            .filter((r) => new Date(r.timestamp).getTime() >= since)
            .map((r) => ({ timestamp: r.timestamp, value: r.value }))
        : [],
    })),
  };
});

// --- Image ---
const imageBlob = ref<Blob | null>(null);
const imageUrl = ref<string | null>(null);
const canShare = typeof navigator !== 'undefined' && !!navigator.share;
const canShareFiles = computed(() => {
  if (!canShare || !navigator.canShare) return false;
  try {
    return navigator.canShare({ files: [new File([new Blob()], 'test.png', { type: 'image/png' })] });
  } catch {
    return false;
  }
});

function releaseImage() {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value);
  imageUrl.value = null;
  imageBlob.value = null;
}

async function renderImage() {
  if (!props.modelValue || !data.value.parameters.length) return;
  try {
    const blob = await drawParameterCard(data.value, {
      title: t('params.title'),
      optimal: t('params.optimal'),
      outOfTarget: t('params.outOfTarget'),
      target: t('params.share.target'),
      footer: t('params.share.footer'),
    });
    releaseImage();
    imageBlob.value = blob;
    imageUrl.value = URL.createObjectURL(blob);
  } catch {
    $q.notify({ type: 'negative', message: t('params.share.imageFailed') });
  }
}

watch([historyDays, pinnedOnly], () => void renderImage());

function imageName(): string {
  const slug = data.value.aquarium.name.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-');
  return `${t('params.share.fileName')}-${slug || 'aquarium'}-${isoDate(new Date())}.png`;
}

function downloadImage() {
  if (imageBlob.value) exportFile(imageName(), imageBlob.value, { mimeType: 'image/png' });
}

async function shareImage() {
  if (!imageBlob.value) return;
  const file = new File([imageBlob.value], imageName(), { type: 'image/png' });
  try {
    await navigator.share({ files: [file], title: data.value.aquarium.name });
  } catch {
    // partage annulé
  }
}

// --- Texte ---
const text = computed(() =>
  parametersText(data.value, {
    title: t('params.share.textTitle', { name: data.value.aquarium.name, date: formatDate(data.value.generated_at) }),
    outOfTarget: t('params.outOfTarget').toLowerCase(),
    target: t('params.share.target').toLowerCase(),
    footer: t('params.share.footer'),
  }),
);

async function shareText() {
  try {
    await navigator.share({ text: text.value });
  } catch {
    // partage annulé
  }
}

async function copy(value: string, message: string) {
  try {
    await copyToClipboard(value);
    $q.notify({ type: 'positive', message });
  } catch {
    $q.notify({ type: 'info', message: value, timeout: 8000 });
  }
}

// --- Lien public ---
const links = ref<ParameterShareLink[]>([]);
const loadingLinks = ref(false);
const creating = ref(false);
const label = ref('');
const expiresIn = ref<number | null>(7);

async function loadLinks() {
  loadingLinks.value = true;
  try {
    links.value = (await axios.get<ParameterShareLink[]>('/parameter-shares/', { params: { aquarium_id: props.aquaId } })).data;
  } catch {
    links.value = [];
  } finally {
    loadingLinks.value = false;
  }
}

function linkDescription(link: ParameterShareLink): string {
  const parts = [
    link.history_days ? t('params.share.days', { n: link.history_days }) : t('params.share.latestOnly'),
  ];
  if (link.pinned_only) parts.push(t('params.share.pinnedShort'));
  parts.push(link.expires_at ? t('params.share.until', { date: formatDateTime(link.expires_at) }) : t('params.share.noExpiry'));
  parts.push(t('params.share.views', { n: link.view_count }, link.view_count));
  return parts.join(' · ');
}

async function createLink() {
  creating.value = true;
  try {
    const { data: link } = await axios.post<ParameterShareLink>('/parameter-shares/', {
      aquarium_id: props.aquaId,
      label: label.value.trim() || null,
      history_days: historyDays.value,
      pinned_only: pinnedOnly.value,
      expires_in_days: expiresIn.value,
    });
    links.value = [link, ...links.value];
    label.value = '';
    await copy(parameterShareUrl(link.token), t('params.share.linkCreated'));
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('params.share.createFailed')) });
  } finally {
    creating.value = false;
  }
}

async function shareLink(link: ParameterShareLink) {
  try {
    await navigator.share({ title: data.value.aquarium.name, url: parameterShareUrl(link.token) });
  } catch {
    // partage annulé
  }
}

function removeLink(link: ParameterShareLink) {
  confirmRemove(link.label || t('params.share.untitled'), async () => {
    await axios.delete(`/parameter-shares/${link.id}`);
    links.value = links.value.filter((l) => l.id !== link.id);
  }, { message: t('params.share.revokeMessage') });
}

async function onShow() {
  if (!aquariumStore.getById(props.aquaId)) await aquariumStore.fetch().catch(() => undefined);
  void renderImage();
  void loadLinks();
}

function onHide() {
  releaseImage();
}

onBeforeUnmount(releaseImage);
</script>

<style scoped>
.share-preview {
  display: flex;
  justify-content: center;
  background: var(--q-grey-2, #f1f5f9);
  border-radius: 12px;
  max-height: 55vh;
  overflow: auto;
}

.share-preview img {
  width: 100%;
  height: auto;
  display: block;
}

:deep(.share-text) {
  font-family: var(--app-font-mono);
  font-size: 13px;
}
</style>
