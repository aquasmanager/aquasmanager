<!--
  Documents d'achat : factures, certificats de cession reçus, permis CITES,
  liés aux spécimens. Tout se retrouve (et se télécharge) en cas de contrôle.
-->
<template>
  <q-page class="app-page">
    <PageHeader
      icon="folder_shared"
      :title="t('documents.title')"
      :subtitle="t('documents.subtitle')"
    >
      <template #actions>
        <q-btn outline color="primary" icon="folder_zip" :label="t('documents.downloadAll')" :disable="!documents.length" @click="downloadAll" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('documents.new')" @click="openDialog(null)" />
      </template>
    </PageHeader>

    <q-input v-model="search" dense outlined clearable debounce="250" :placeholder="t('documents.search')" class="q-mb-md">
      <template #prepend><q-icon name="search" /></template>
    </q-input>

    <div v-if="loading" class="flex flex-center q-pa-xl"><q-spinner color="primary" size="2em" /></div>

    <EmptyState
      v-else-if="!filtered.length"
      icon="folder_shared"
      :title="documents.length ? t('documents.noMatch') : t('documents.emptyTitle')"
      :message="documents.length ? t('documents.noMatchMessage') : t('documents.emptyMessage')"
    >
      <q-btn v-if="!documents.length && can.edit" unelevated color="primary" icon="add" :label="t('documents.addDocument')" @click="openDialog(null)" />
    </EmptyState>

    <div v-else class="row q-col-gutter-md">
      <div v-for="doc in filtered" :key="doc.id" class="col-12 col-md-6">
        <q-card flat bordered class="full-height column">
          <q-card-section class="col">
            <div class="row items-start no-wrap">
              <div class="col">
                <div class="text-subtitle1 text-weight-bold">{{ doc.title }}</div>
                <div class="text-caption text-grey-7">
                  {{ [doc.supplier, doc.purchase_date && formatDate(doc.purchase_date)].filter(Boolean).join(' · ') || t('documents.noSupplier') }}
                </div>
              </div>
              <q-btn v-if="can.edit" flat round dense icon="more_vert" color="grey-7">
                <q-menu anchor="bottom right" self="top right">
                  <q-list dense style="min-width: 180px">
                    <q-item v-close-popup clickable @click="openDialog(doc)">
                      <q-item-section avatar><q-icon name="edit" size="xs" /></q-item-section>
                      <q-item-section>{{ t('actions.edit') }}</q-item-section>
                    </q-item>
                    <q-item v-close-popup clickable class="text-negative" @click="remove(doc)">
                      <q-item-section avatar><q-icon name="delete" size="xs" color="negative" /></q-item-section>
                      <q-item-section>{{ t('actions.delete') }}</q-item-section>
                    </q-item>
                  </q-list>
                </q-menu>
              </q-btn>
            </div>

            <div v-if="doc.reference || doc.cites_numbers.length" class="row q-gutter-xs q-mt-sm">
              <span v-if="doc.reference" class="app-tag">{{ t('documents.number', { n: doc.reference }) }}</span>
              <span v-for="n in doc.cites_numbers" :key="n" class="app-tag app-tag--teal">CITES {{ n }}</span>
            </div>

            <div v-if="doc.links.length" class="q-mt-sm">
              <q-chip
                v-for="link in doc.links"
                :key="`${link.entity_type}-${link.entity_id}`"
                dense
                outline
                color="primary"
                :icon="SPECIMEN_ICONS[link.entity_type]"
                :clickable="link.aquarium_id != null"
                @click="goToSpecimen(link)"
              >
                {{ link.label ?? t('documents.deletedSpecimen', { type: specimenLabel(link.entity_type) }) }}
              </q-chip>
            </div>
            <div v-else class="text-caption text-grey-6 q-mt-sm">{{ t('documents.noSpecimen') }}</div>

            <div v-if="doc.notes" class="text-body2 text-grey-8 q-mt-sm" style="white-space: pre-line">{{ doc.notes }}</div>
          </q-card-section>

          <q-separator />
          <q-card-section class="q-py-sm">
            <div v-if="!doc.files.length" class="text-caption text-grey-6">{{ t('documents.noFile') }}</div>
            <div v-for="file in doc.files" :key="file.id" class="row items-center no-wrap">
              <q-icon :name="fileIcon(file)" color="primary" size="20px" class="q-mr-sm" />
              <a href="#" class="col ellipsis file-link" @click.prevent="open(doc, file)">{{ file.original_name }}</a>
              <span class="text-caption text-grey-6 q-mx-sm">{{ formatSize(file.size) }}</span>
              <q-btn flat round dense size="sm" icon="download" @click="open(doc, file, true)"><q-tooltip>{{ t('documents.download') }}</q-tooltip></q-btn>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <PurchaseDocumentDialog v-model="dialog" :document="editing" @saved="onSaved" />
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import EmptyState from 'src/components/EmptyState.vue';
import PageHeader from 'src/components/PageHeader.vue';
import PurchaseDocumentDialog from 'src/components/PurchaseDocumentDialog.vue';
import { usePermissions } from 'src/composables/usePermissions';
import {
  specimenLabel,
  type DocumentFile,
  type DocumentLink,
  type PurchaseDocument,
  type SpecimenType,
} from 'src/types/purchaseDocument';
import { apiErrorMessage } from 'src/utils/apiError';
import { fileIcon, formatSize, openDocumentFile } from 'src/utils/documentFiles';
import { formatDate } from 'src/utils/format';

const SPECIMEN_ICONS: Record<SpecimenType, string> = { corals: 'grass', invertebrates: 'pets', fish: 'set_meal' };
const SPECIMEN_TABS: Record<SpecimenType, string> = { corals: 'coraux', invertebrates: 'invertebrates', fish: 'fishes' };

const { t } = useI18n();
const $q = useQuasar();
const router = useRouter();
const can = usePermissions();
const documents = ref<PurchaseDocument[]>([]);
const loading = ref(true);
const search = ref<string | null>('');
const dialog = ref(false);
const editing = ref<PurchaseDocument | null>(null);

const filtered = computed(() => {
  const q = (search.value ?? '').trim().toLowerCase();
  if (!q) return documents.value;
  return documents.value.filter((d) =>
    [d.title, d.supplier, d.reference, ...d.cites_numbers, d.notes ?? '', ...d.links.map((l) => l.label ?? '')]
      .join(' ')
      .toLowerCase()
      .includes(q),
  );
});

async function load() {
  try {
    documents.value = (await axios.get<PurchaseDocument[]>('/purchase-documents/')).data;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.notify.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

function openDialog(doc: PurchaseDocument | null) {
  editing.value = doc;
  dialog.value = true;
}

function onSaved(doc: PurchaseDocument) {
  editing.value = doc;
  const index = documents.value.findIndex((d) => d.id === doc.id);
  if (index >= 0) documents.value.splice(index, 1, doc);
  else documents.value.unshift(doc);
}

function remove(doc: PurchaseDocument) {
  $q.dialog({
    title: t('documents.deleteTitle'),
    message: t('documents.deleteMessage', { title: doc.title, n: doc.files.length }),
    cancel: true,
    ok: { label: t('actions.delete'), color: 'negative', flat: true },
  }).onOk(() => {
    void (async () => {
      try {
        await axios.delete(`/purchase-documents/${doc.id}`);
        documents.value = documents.value.filter((d) => d.id !== doc.id);
      } catch (err) {
        $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.notify.deleteFailed')) });
      }
    })();
  });
}

async function open(doc: PurchaseDocument, file: DocumentFile, download = false) {
  try {
    await openDocumentFile(doc.id, file, download);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.notify.openFailed')) });
  }
}

function goToSpecimen(link: DocumentLink) {
  if (link.aquarium_id == null) return;
  void router.push({ path: `/aquariums/${link.aquarium_id}`, query: { tab: SPECIMEN_TABS[link.entity_type], specimen: String(link.entity_id) } });
}

async function downloadAll() {
  try {
    const { data } = await axios.get<Blob>('/purchase-documents/export.zip', { responseType: 'blob' });
    const url = URL.createObjectURL(data);
    const a = document.createElement('a');
    a.href = url;
    a.download = t('documents.zipName');
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.notify.downloadFailed')) });
  }
}

onMounted(load);
</script>

<style scoped>
.file-link {
  color: inherit;
  text-decoration: none;
}

.file-link:hover {
  text-decoration: underline;
}
</style>
