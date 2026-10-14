<!--
  Proposer une modification d'une espèce du catalogue commun : envoie au hub de
  l'éditeur les champs modifiés (avant → après), qui ouvre une issue publique.
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="rate_review"
    :title="t('livestock.correct.title')"
    :subtitle="`${commonName} · ${scientificName}`"
    width="560px"
    :submit-label="t('livestock.propose.send')"
    submit-icon="send"
    :hide-submit="!!sent"
    :cancel-label="sent ? t('common.close') : t('common.cancel')"
    :loading="sending"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset"
    @submit="send"
  >
    <template v-if="sent">
      <div class="app-callout app-callout--ok">
        <q-icon name="check_circle" size="22px" />
        <div>
          {{ t('livestock.propose.sent') }}
          <div><a :href="sent.url" target="_blank" rel="noopener">{{ t('livestock.propose.sentLink', { n: sent.number }) }}</a></div>
        </div>
      </div>
    </template>
    <template v-else>
      <div class="text-body2 text-grey-8">{{ t('livestock.correct.intro') }}</div>
      <q-markup-table v-if="rows.length" dense flat bordered separator="horizontal">
        <thead>
          <tr>
            <th class="text-left">{{ t('livestock.correct.field') }}</th>
            <th class="text-left">{{ t('livestock.correct.current') }}</th>
            <th class="text-left">{{ t('livestock.correct.proposed') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.field">
            <td class="text-grey-8">{{ row.label }}</td>
            <td class="text-grey-7 correction-value">{{ row.before }}</td>
            <td class="text-weight-medium correction-value">{{ row.after }}</td>
          </tr>
        </tbody>
      </q-markup-table>
      <div v-else class="text-caption text-grey-7">{{ t('livestock.correct.noChange') }}</div>
      <q-input v-model="author" :label="t('livestock.propose.author')" outlined dense maxlength="40" />
      <q-input v-model="note" :label="t('livestock.correct.note')" type="textarea" autogrow outlined dense maxlength="1000" />
      <div class="text-caption text-grey-7">
        <q-icon name="public" size="14px" class="q-mr-xs" />{{ t('livestock.propose.public') }}
      </div>
    </template>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import { APP_VERSION } from 'src/composables/useAppUpdate';
import { currentLocale } from 'src/i18n/instance';
import { hubErrorKey, proposeCorrection, type SpeciesChanges, type SpeciesKind } from 'src/utils/hub';
import { speciesFieldLabel, speciesFieldValue } from 'src/utils/speciesFields';

const props = defineProps<{
  modelValue: boolean;
  kind: SpeciesKind;
  commonName: string;
  scientificName: string;
  changes: SpeciesChanges;
}>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const { t } = useI18n();
const $q = useQuasar();
const author = ref('');
const note = ref('');
const sending = ref(false);
const sent = ref<{ number: number; url: string } | null>(null);

function reset() {
  author.value = '';
  note.value = '';
  sent.value = null;
}

const rows = computed(() =>
  Object.entries(props.changes).map(([field, change]) => ({
    field,
    label: speciesFieldLabel(t, field),
    before: speciesFieldValue(t, props.kind, field, change.before),
    after: speciesFieldValue(t, props.kind, field, change.after),
  })),
);

async function send() {
  if (!rows.value.length && !note.value.trim()) {
    $q.notify({ type: 'warning', message: t('livestock.correct.empty') });
    return;
  }
  sending.value = true;
  try {
    sent.value = await proposeCorrection({
      kind: props.kind,
      common_name: props.commonName,
      scientific_name: props.scientificName,
      changes: props.changes,
      note: note.value.trim() || null,
      author: author.value.trim() || null,
      app_version: APP_VERSION,
      locale: currentLocale(),
    });
  } catch (err) {
    $q.notify({ type: 'negative', message: t(`livestock.propose.errors.${hubErrorKey(err)}`), timeout: 6000 });
  } finally {
    sending.value = false;
  }
}
</script>

<style scoped>
.correction-value {
  white-space: normal;
  word-break: break-word;
}
</style>
