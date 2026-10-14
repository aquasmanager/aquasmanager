<!--
  Proposer une espèce au catalogue commun d'AquasManager : envoi direct au hub
  de l'éditeur (qui ouvre une issue publique), ou formulaire d'issue prérempli
  pour les personnes ayant un compte. Montre ce qui sera envoyé.
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="volunteer_activism"
    :title="t('livestock.propose.title')"
    :subtitle="species ? `${species.common_name} · ${species.scientific_name}` : undefined"
    width="520px"
    :submit-label="t('livestock.propose.send')"
    submit-icon="send"
    :hide-submit="!hub?.suggestions || !!sent"
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
    <template v-else-if="species">
      <div class="text-body2 text-grey-8">{{ t('livestock.propose.intro') }}</div>
      <q-list dense bordered separator class="rounded-borders">
        <q-item v-for="row in rows" :key="row.label">
          <q-item-section class="text-grey-7">{{ row.label }}</q-item-section>
          <q-item-section side class="text-grey-9">{{ row.value }}</q-item-section>
        </q-item>
      </q-list>
      <q-input v-model="description" :label="t('livestock.catalog.notes')" :hint="t('livestock.catalog.notesHint')" type="textarea" autogrow outlined dense maxlength="1000" />
      <q-input v-model="author" :label="t('livestock.propose.author')" outlined dense maxlength="40" />
      <q-input v-model="note" :label="t('livestock.propose.note')" type="textarea" autogrow outlined dense maxlength="1000" />
      <div class="text-caption text-grey-7">
        <q-icon name="public" size="14px" class="q-mr-xs" />{{ t('livestock.propose.public') }}
      </div>
      <div v-if="!hub?.suggestions && !hub?.issues_form_url" class="text-caption text-negative">{{ t('livestock.propose.unavailable') }}</div>
    </template>

    <template #footer-left>
      <q-btn v-if="hub?.issues_form_url && !sent && species" flat no-caps color="primary" icon="open_in_new" :label="t('livestock.propose.github')" :href="formUrl" target="_blank" rel="noopener">
        <q-tooltip>{{ t('livestock.propose.githubHint') }}</q-tooltip>
      </q-btn>
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
import { toPar } from 'src/utils/format';
import { hubErrorKey, proposeSpecies, useHubStatus, type SpeciesKind, type SpeciesProposal } from 'src/utils/hub';

const props = defineProps<{ modelValue: boolean; kind: SpeciesKind; species: SpeciesProposal | null }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const { t } = useI18n();
const $q = useQuasar();
const hub = useHubStatus();
const author = ref('');
const note = ref('');
const description = ref('');
const sending = ref(false);
const sent = ref<{ number: number; url: string } | null>(null);

function reset() {
  author.value = '';
  note.value = '';
  description.value = typeof props.species?.notes === 'string' ? props.species.notes : '';
  sent.value = null;
}

type Value = string | number | boolean | null | undefined;
const range = (min: Value, max: Value, unit = '') => (min == null && max == null ? null : `${min ?? '?'} – ${max ?? '?'}${unit}`);

// Ce qui part avec la proposition, lisible (libellés du catalogue)
const rows = computed(() => {
  const s = props.species;
  if (!s) return [];
  const yesNo = (v: Value) => (v == null ? null : v ? t('actions.yes') : t('actions.no'));
  const all: [string, Value][] = [
    [t('livestock.familyLabel'), s.family],
    [t('livestock.originLabel'), s.origin],
    [t('livestock.catalog.columns.type'), s.type],
    [t('livestock.catalog.columns.water'), s.water_type ? (s.water_type === 'sea' ? t('livestock.catalog.sea') : t('livestock.catalog.fresh')) : null],
    [t('livestock.catalog.columns.category'), s.category ? t(`livestock.categories.${String(s.category)}`) : null],
    [
      t('livestock.light'),
      props.kind === 'corals' && typeof s.light_min === 'number' && typeof s.light_max === 'number'
        ? `${s.light_min} – ${s.light_max} (${toPar(s.light_min)} – ${toPar(s.light_max)} PAR)`
        : range(s.light_min, s.light_max),
    ],
    [t('livestock.brewing'), range(s.brewing_min, s.brewing_max)],
    [t('livestock.temperature'), range(s.temperature_min, s.temperature_max, ' °C')],
    [t('livestock.catalog.columns.sizeMax'), s.max_height != null ? `${s.max_height} cm` : null],
    [t('livestock.catalog.columns.volumeMin'), s.min_volume != null ? `${s.min_volume} L` : null],
    [t('livestock.catalog.columns.reef'), yesNo(s.reef_safe)],
    [t('livestock.catalog.columns.growing'), s.growing ? t(`livestock.growingSpeed.${String(s.growing)}`) : null],
    [t('livestock.catalog.columns.location'), s.location ? t(`livestock.plantLocation.${String(s.location)}`) : null],
    [t('livestock.aggressiveness'), s.aggressiveness_level],
    [t('livestock.resistance'), s.resistance_level],
    [t('livestock.heightInTank'), s.location_level],
  ];
  return all.filter(([, value]) => value != null && value !== '').map(([label, value]) => ({ label, value: String(value) }));
});

// Formulaire d'issue prérempli : les paramètres reprennent les « id » du formulaire
const formUrl = computed(() => {
  const base = hub.value?.issues_form_url;
  const s = props.species;
  if (!base || !s) return undefined;
  const url = new URL(base);
  url.searchParams.set('title', `[${t(`livestock.propose.kinds.${props.kind}`)}] ${s.common_name} (${s.scientific_name})`);
  url.searchParams.set('kind', t(`livestock.propose.kinds.${props.kind}`));
  url.searchParams.set('common_name', s.common_name);
  url.searchParams.set('scientific_name', s.scientific_name);
  const details = rows.value.map((r) => `${r.label} : ${r.value}`);
  if (description.value.trim()) details.push(`${t('livestock.catalog.notes')} : ${description.value.trim()}`);
  url.searchParams.set('details', details.join('\n'));
  if (note.value.trim()) url.searchParams.set('note', note.value.trim());
  return url.toString();
});

async function send() {
  if (!props.species) return;
  sending.value = true;
  try {
    sent.value = await proposeSpecies({
      kind: props.kind,
      species: { ...props.species, notes: description.value.trim() || null },
      author: author.value.trim() || null,
      note: note.value.trim() || null,
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
