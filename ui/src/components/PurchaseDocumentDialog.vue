<!--
  Document d'achat (facture, certificat de cession reçu, permis CITES) :
  informations, fichiers (PDF, photos) et spécimens concernés.
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="folder_shared"
    :title="document ? t('documents.dialog.editTitle') : t('documents.dialog.newTitle')"
    :subtitle="t('documents.dialog.subtitle')"
    width="640px"
    :submit-label="document ? t('common.save') : t('documents.dialog.add')"
    :loading="saving"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="init"
    @submit="save"
  >
    <q-input v-model="form.title" :label="t('documents.dialog.docTitle')" outlined dense maxlength="120" :hint="t('documents.dialog.titleHint')" autofocus />
    <div class="row q-col-gutter-md">
      <div class="col-12 col-sm-7"><q-input v-model="form.supplier" :label="t('documents.dialog.supplier')" outlined dense maxlength="120" /></div>
      <div class="col-12 col-sm-5">
        <q-input v-model="form.purchase_date" type="date" :label="t('documents.dialog.date')" stack-label outlined dense clearable />
      </div>
      <div class="col-12 col-sm-6"><q-input v-model="form.reference" :label="t('documents.dialog.reference')" outlined dense maxlength="80" /></div>
      <div class="col-12 col-sm-6">
        <q-select
          v-model="form.cites_numbers"
          :label="t('documents.dialog.cites')"
          :hint="t('documents.dialog.citesHint')"
          multiple
          use-chips
          use-input
          hide-dropdown-icon
          input-debounce="0"
          new-value-mode="add-unique"
          outlined
          dense
          @new-value="addCites"
        />
      </div>
      <!-- Espèce de chaque numéro : proposé à l'ajout d'un corail de cette espèce -->
      <div v-if="form.cites_numbers.length" class="col-12">
        <div class="text-caption text-grey-7 q-mb-xs">{{ t('documents.dialog.citesSpeciesHint') }}</div>
        <div v-for="number in form.cites_numbers" :key="number" class="row items-center q-col-gutter-sm q-mb-xs">
          <div class="col-12 col-sm-4"><span class="app-tag app-tag--teal">CITES {{ number }}</span></div>
          <div class="col-12 col-sm-8">
            <q-select
              :model-value="citesSpecies[citesKey(number)] ?? null"
              :options="filteredCoralSpecies"
              :label="t('documents.dialog.citesSpecies')"
              emit-value
              map-options
              use-input
              clearable
              input-debounce="0"
              outlined
              dense
              @filter="filterCoralSpecies"
              @update:model-value="(id: number | null) => setCitesSpecies(number, id)"
            />
          </div>
        </div>
      </div>
    </div>

    <q-select
      v-model="form.links"
      :options="filteredSpecimens"
      :label="t('documents.dialog.specimens')"
      outlined
      dense
      multiple
      use-chips
      use-input
      emit-value
      map-options
      input-debounce="0"
      :hint="t('documents.dialog.specimensHint')"
      @filter="filterSpecimens"
    >
      <template #prepend><q-icon name="link" /></template>
      <template #option="scope">
        <q-item v-bind="scope.itemProps">
          <q-item-section>
            <q-item-label>{{ scope.opt.label }}</q-item-label>
            <q-item-label caption>{{ scope.opt.caption }}</q-item-label>
          </q-item-section>
        </q-item>
      </template>
    </q-select>

    <q-input v-model="form.notes" :label="t('documents.dialog.notes')" type="textarea" outlined dense autogrow maxlength="2000" />

    <!-- Fichiers -->
    <div>
      <div class="text-subtitle2 q-mb-xs">{{ t('documents.dialog.files') }}</div>
      <q-list v-if="document?.files.length" bordered separator dense class="rounded-borders q-mb-sm">
        <q-item v-for="file in document.files" :key="file.id">
          <q-item-section avatar><q-icon :name="fileIcon(file)" color="primary" /></q-item-section>
          <q-item-section>
            <q-item-label class="ellipsis">{{ file.original_name }}</q-item-label>
            <q-item-label caption>{{ formatSize(file.size) }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="row no-wrap">
              <q-btn flat round dense icon="open_in_new" @click="open(file)"><q-tooltip>{{ t('documents.dialog.open') }}</q-tooltip></q-btn>
              <q-btn flat round dense color="negative" icon="delete" @click="removeFile(file)"><q-tooltip>{{ t('actions.delete') }}</q-tooltip></q-btn>
            </div>
          </q-item-section>
        </q-item>
      </q-list>
      <q-file
        v-model="newFiles"
        :accept="DOCUMENT_ACCEPT"
        multiple
        append
        outlined
        dense
        counter
        max-file-size="20971520"
        :label="t('documents.dialog.addFiles')"
        :hint="t('documents.dialog.filesHint')"
        @rejected="onRejected"
      >
        <template #prepend><q-icon name="attach_file" /></template>
      </q-file>
      <!-- Pages photographiées, réunies en un PDF à l'enregistrement -->
      <div class="text-caption text-grey-7 q-mt-sm">{{ t('documents.scan.title') }}</div>
      <ScanPages v-model="scanPages" v-model:name="scanName" />
    </div>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import ScanPages, { type ScanPage } from 'src/components/ScanPages.vue';
import { preparePage } from 'src/utils/imageCompress';
import {
  DOCUMENT_ACCEPT,
  specimenLabel,
  specimenKey,
  type DocumentFile,
  type LinkableSpecimen,
  type PurchaseDocument,
  type SpecimenType,
} from 'src/types/purchaseDocument';
import { apiErrorMessage } from 'src/utils/apiError';
import { useSpeciesStore } from 'src/stores/speciesStore';
import { fileIcon, formatSize, openDocumentFile } from 'src/utils/documentFiles';

const props = defineProps<{
  modelValue: boolean;
  document?: PurchaseDocument | null;
  // Nouveau document : spécimen lié d'office (ouvert depuis sa fiche)
  preset?: { entity_type: SpecimenType; entity_id: number } | null;
}>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [document: PurchaseDocument] }>();

const { t } = useI18n();
const $q = useQuasar();
const saving = ref(false);
const specimens = ref<LinkableSpecimen[]>([]);
const needle = ref('');
const newFiles = ref<File[] | null>(null);
const scanPages = ref<ScanPage[]>([]);
const scanName = ref('');
interface DocumentForm {
  title: string;
  supplier: string;
  purchase_date: string | null;
  reference: string;
  cites_numbers: string[];
  notes: string;
  // « corals:12 », « invertebrates:3 »...
  links: string[];
}

const speciesStore = useSpeciesStore();
const form = ref<DocumentForm>({
  title: '',
  supplier: '',
  purchase_date: null,
  reference: '',
  cites_numbers: [],
  notes: '',
  links: [],
});

const specimenOptions = computed(() =>
  specimens.value.map((s) => ({
    value: specimenKey(s.entity_type, s.entity_id),
    label: s.name,
    caption: [specimenLabel(s.entity_type), s.aquarium_name, s.scientific_name, s.cites && `CITES ${s.cites}`]
      .filter(Boolean)
      .join(' · '),
  })),
);
const filteredSpecimens = computed(() => {
  const q = needle.value.toLowerCase();
  return q ? specimenOptions.value.filter((o) => `${o.label} ${o.caption}`.toLowerCase().includes(q)) : specimenOptions.value;
});

function filterSpecimens(value: string, update: (fn: () => void) => void) {
  update(() => (needle.value = value));
}

// Espèce du catalogue de coraux associée à chaque numéro CITES
const citesKey = (number: string) => number.replace(/[\s\-_/.]/g, '').toUpperCase();
const citesSpecies = ref<Record<string, number>>({});
const coralSpecies = ref<{ value: number; label: string; caption: string }[]>([]);
const speciesNeedle = ref('');
const filteredCoralSpecies = computed(() => {
  const q = speciesNeedle.value.toLowerCase();
  return q ? coralSpecies.value.filter((o) => `${o.label} ${o.caption}`.toLowerCase().includes(q)) : coralSpecies.value;
});
function filterCoralSpecies(value: string, update: (fn: () => void) => void) {
  update(() => (speciesNeedle.value = value));
}
function setCitesSpecies(number: string, id: number | null) {
  const next = { ...citesSpecies.value };
  if (id) next[citesKey(number)] = id;
  else delete next[citesKey(number)];
  citesSpecies.value = next;
}

async function init() {
  newFiles.value = null;
  scanPages.value = [];
  scanName.value = '';
  const d = props.document;
  citesSpecies.value = Object.fromEntries(
    (d?.cites_entries ?? []).filter((e) => e.coral_species_id).map((e) => [citesKey(e.number), e.coral_species_id as number]),
  );
  void speciesStore
    .search('corals')
    .then((list) => {
      coralSpecies.value = list.map((s) => ({ value: s.id, label: s.common_name, caption: s.scientific_name }));
    })
    .catch(() => undefined);
  form.value = {
    title: d?.title ?? '',
    supplier: d?.supplier ?? '',
    purchase_date: d?.purchase_date ?? null,
    reference: d?.reference ?? '',
    cites_numbers: [...(d?.cites_numbers ?? [])],
    notes: d?.notes ?? '',
    links: d
      ? d.links.map((l) => specimenKey(l.entity_type, l.entity_id))
      : props.preset
        ? [specimenKey(props.preset.entity_type, props.preset.entity_id)]
        : [],
  };
  try {
    specimens.value = (await axios.get<LinkableSpecimen[]>('/purchase-documents/specimens')).data;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.dialog.specimensFailed')) });
  }
}

function onRejected() {
  $q.notify({ type: 'warning', message: t('documents.dialog.rejected') });
}

async function open(file: DocumentFile) {
  if (!props.document) return;
  try {
    await openDocumentFile(props.document.id, file);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.notify.openFailed')) });
  }
}

function removeFile(file: DocumentFile) {
  const d = props.document;
  if (!d) return;
  $q.dialog({
    title: t('documents.dialog.deleteFileTitle'),
    message: t('documents.dialog.deleteFileMessage', { name: file.original_name }),
    cancel: true,
    ok: { label: t('actions.delete'), color: 'negative', flat: true },
  }).onOk(() => {
    void (async () => {
      try {
        await axios.delete(`/purchase-documents/${d.id}/files/${file.id}`);
        emit('saved', { ...d, files: d.files.filter((f) => f.id !== file.id) });
      } catch (err) {
        $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.notify.deleteFailed')) });
      }
    })();
  });
}

// Plusieurs numéros CITES : Entrée après chacun, ou plusieurs collés d'un coup (virgule, point-virgule)
function addCites(value: string, done: (item?: string, mode?: 'add' | 'add-unique' | 'toggle') => void) {
  const parts = value.split(/[,;\n]+/).map((v) => v.trim()).filter(Boolean);
  const known = new Set(form.value.cites_numbers.map((n) => n.toUpperCase()));
  for (const part of parts.slice(0, -1)) {
    if (!known.has(part.toUpperCase())) form.value.cites_numbers.push(part);
  }
  done(parts.at(-1), 'add-unique');
}

async function save() {
  if (!form.value.title.trim()) {
    $q.notify({ type: 'warning', message: t('documents.dialog.titleRequired') });
    return;
  }
  saving.value = true;
  const payload = {
    title: form.value.title.trim(),
    supplier: form.value.supplier.trim(),
    purchase_date: form.value.purchase_date || null,
    reference: form.value.reference.trim(),
    cites_entries: form.value.cites_numbers.map((number) => ({
      number,
      coral_species_id: citesSpecies.value[citesKey(number)] ?? null,
    })),
    notes: form.value.notes.trim() || null,
    links: form.value.links.map((key) => {
      const [entity_type, id] = key.split(':');
      return { entity_type, entity_id: Number(id) };
    }),
  };
  try {
    let { data } = props.document
      ? await axios.patch<PurchaseDocument>(`/purchase-documents/${props.document.id}`, payload)
      : await axios.post<PurchaseDocument>('/purchase-documents/', payload);
    if (scanPages.value.length) {
      try {
        const body = new FormData();
        for (const page of scanPages.value) body.append('pages', await preparePage(page.file, page.rotation), 'page.jpg');
        if (scanName.value.trim()) body.append('name', scanName.value.trim());
        await axios.post(`/purchase-documents/${data.id}/scan`, body);
        scanPages.value.forEach((p) => URL.revokeObjectURL(p.url));
        scanPages.value = [];
        scanName.value = '';
        data = (await axios.get<PurchaseDocument>(`/purchase-documents/${data.id}`)).data;
      } catch (err) {
        emit('saved', data);
        $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.scan.failed')) });
        return;
      }
    }
    if (newFiles.value?.length) {
      const body = new FormData();
      newFiles.value.forEach((f) => body.append('files', f));
      try {
        await axios.post(`/purchase-documents/${data.id}/files`, body);
        data = (await axios.get<PurchaseDocument>(`/purchase-documents/${data.id}`)).data;
      } catch (err) {
        // Document enregistré, fichiers refusés : on le garde et on prévient
        emit('saved', data);
        $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.dialog.uploadFailed')) });
        return;
      }
    }
    emit('saved', data);
    emit('update:modelValue', false);
    $q.notify({ type: 'positive', message: props.document ? t('documents.dialog.saved') : t('documents.dialog.added') });
    if (data.auto_linked) $q.notify({ type: 'info', icon: 'link', message: t('documents.dialog.autoLinked', data.auto_linked) });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('documents.dialog.saveFailed')) });
  } finally {
    saving.value = false;
  }
}
</script>
