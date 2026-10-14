<!--
  Documents d'achat liés à un spécimen (fiche corail, invertébré) ou au pied
  mère d'une bouture : les ouvrir d'un geste en cas de contrôle.
-->
<template>
  <div>
    <div class="row items-center q-mb-xs">
      <q-icon name="folder_shared" color="primary" size="20px" class="q-mr-sm" />
      <div class="text-subtitle2 col">{{ title ?? t('documents.specimen.title') }}</div>
      <q-btn
        v-if="can.edit && !readonly"
        flat
        dense
        no-caps
        size="sm"
        color="primary"
        icon="add"
        :label="t('documents.dialog.add')"
        @click="openDialog(null)"
      />
    </div>

    <div v-if="loading" class="q-py-sm"><q-spinner color="primary" size="1.5em" /></div>
    <div v-else-if="!documents.length" class="text-caption text-grey-7">
      {{ t('documents.specimen.empty') }}
    </div>
    <q-list v-else bordered separator dense class="rounded-borders">
      <q-item v-for="doc in documents" :key="doc.id">
        <q-item-section>
          <q-item-label class="text-weight-bold ellipsis">{{ doc.title }}</q-item-label>
          <q-item-label caption>
            {{ [doc.supplier, doc.purchase_date && formatDate(doc.purchase_date), doc.cites_numbers.length && `CITES ${doc.cites_numbers.join(', ')}`]
              .filter(Boolean)
              .join(' · ') || t('documents.specimen.noDetail') }}
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <div class="row no-wrap items-center">
            <q-btn
              v-for="file in doc.files"
              :key="file.id"
              flat
              round
              dense
              color="primary"
              :icon="fileIcon(file)"
              @click="open(doc, file)"
            >
              <q-tooltip>{{ file.original_name }}</q-tooltip>
            </q-btn>
            <span v-if="!doc.files.length" class="text-caption text-grey-6 q-mr-xs">{{ t('documents.specimen.noFile') }}</span>
            <q-btn v-if="can.edit && !readonly" flat round dense icon="edit" color="grey-7" @click="openDialog(doc)">
              <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
            </q-btn>
          </div>
        </q-item-section>
      </q-item>
    </q-list>

    <PurchaseDocumentDialog
      v-model="dialog"
      :document="editing"
      :preset="{ entity_type: entityType, entity_id: entityId }"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import PurchaseDocumentDialog from 'src/components/PurchaseDocumentDialog.vue';
import { usePermissions } from 'src/composables/usePermissions';
import type { DocumentFile, PurchaseDocument, SpecimenType } from 'src/types/purchaseDocument';
import { apiErrorMessage } from 'src/utils/apiError';
import { fileIcon, openDocumentFile } from 'src/utils/documentFiles';
import { formatDate } from 'src/utils/format';

const props = withDefaults(
  defineProps<{ entityType: SpecimenType; entityId: number; title?: string; readonly?: boolean }>(),
  { readonly: false },
);

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const documents = ref<PurchaseDocument[]>([]);
const loading = ref(false);
const dialog = ref(false);
const editing = ref<PurchaseDocument | null>(null);

async function load() {
  loading.value = true;
  try {
    documents.value = (
      await axios.get<PurchaseDocument[]>('/purchase-documents/', {
        params: { entity_type: props.entityType, entity_id: props.entityId },
      })
    ).data;
  } catch {
    documents.value = [];
  } finally {
    loading.value = false;
  }
}

function openDialog(doc: PurchaseDocument | null) {
  editing.value = doc;
  dialog.value = true;
}

function onSaved(doc: PurchaseDocument) {
  // Le dialogue reste sur ce document (ex. fichiers refusés après sa création)
  editing.value = doc;
  void load();
}

async function open(doc: PurchaseDocument, file: DocumentFile) {
  try {
    await openDocumentFile(doc.id, file);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.notify.openFailed')) });
  }
}

watch(() => [props.entityType, props.entityId], load, { immediate: true });
</script>
