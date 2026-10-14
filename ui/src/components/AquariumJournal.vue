<!--
  Journal de bord d'un aquarium : notes datées (changement d'eau, dosage,
  observation...). Les ajouts de vivants et les maintenances s'y inscrivent
  d'eux-mêmes. Les notes apparaissent aussi sur le graphique d'évolution des
  paramètres (tableau de bord), pour relier causes et effets.
-->
<template>
  <div>
    <PageHeader section :title="t('journal.title')" :subtitle="t('journal.subtitle')" />

    <q-card v-if="can.care" flat bordered class="q-mb-md">
      <q-card-section class="column gap-sm">
        <div class="row q-gutter-xs">
          <q-btn
            v-for="c in JOURNAL_CATEGORIES"
            :key="c.key"
            dense
            no-caps
            unelevated
            :outline="form.category !== c.key"
            :style="form.category === c.key ? { background: c.color, color: 'white' } : { color: c.color }"
            :icon="c.icon"
            :label="t(`journal.categories.${c.key}`)"
            class="category-btn"
            @click="form.category = c.key"
          />
        </div>
        <div class="row q-col-gutter-sm items-start">
          <div class="col-12 col-md">
            <q-input
              v-model="form.text"
              outlined
              dense
              autogrow
              maxlength="500"
              :placeholder="t(`journal.placeholders.${form.category}`)"
              @keydown.enter.exact.prevent="add"
            />
          </div>
          <!-- Téléphone : date et bouton chacun sur sa ligne (sinon le bouton recouvre la date) -->
          <div class="col-12 col-sm col-md-auto">
            <q-input v-model="form.when" outlined dense type="datetime-local" :label="t('journal.when')" class="journal-when" />
          </div>
          <div class="col-12 col-sm-auto">
            <q-btn unelevated color="primary" icon="add" class="full-width" :label="t('journal.add')" :loading="saving" :disable="!form.text.trim()" @click="add" />
          </div>
        </div>
      </q-card-section>
    </q-card>

    <div class="row items-center q-gutter-xs q-mb-md">
      <q-chip
        v-for="c in JOURNAL_CATEGORIES"
        :key="c.key"
        clickable
        dense
        :outline="!filters.has(c.key)"
        :style="filters.has(c.key) ? { background: c.color, color: 'white' } : { color: c.color }"
        :icon="c.icon"
        @click="toggleFilter(c.key)"
      >
        {{ t(`journal.categories.${c.key}`) }} · {{ counts[c.key] ?? 0 }}
      </q-chip>
      <q-btn v-if="filters.size" flat dense no-caps size="sm" color="grey-7" :label="t('journal.allCategories')" @click="filters = new Set()" />
    </div>

    <div v-if="loading" class="text-center q-py-xl"><q-spinner color="primary" size="3em" /></div>
    <EmptyState v-else-if="!entries.length" icon="edit_note" :title="t('journal.emptyTitle')" :message="t('journal.emptyMessage')" />
    <EmptyState v-else-if="!filtered.length" icon="filter_alt_off" :title="t('journal.noMatch')" />

    <template v-else>
      <div v-for="group in groups" :key="group.month" class="q-mb-lg">
        <div class="text-subtitle2 text-weight-bold text-grey-8 q-mb-sm month">{{ group.month }}</div>
        <q-card flat bordered>
        <q-list separator>
          <q-item v-for="entry in group.entries" :key="entry.id">
            <q-item-section avatar>
              <q-avatar size="36px" :style="{ background: journalCategory(entry.category).color + '1f', color: journalCategory(entry.category).color }" :icon="journalCategory(entry.category).icon" />
            </q-item-section>
            <q-item-section>
              <q-item-label class="entry-text">{{ entry.text }}</q-item-label>
              <q-item-label caption>
                {{ formatDateTime(entry.occurred_at) }} · {{ t(`journal.categories.${entry.category}`) }}
                <span v-if="entry.auto"> · {{ t('journal.auto') }}</span>
              </q-item-label>
            </q-item-section>
            <q-item-section v-if="can.edit" side>
              <div class="row no-wrap">
                <q-btn flat round dense size="sm" icon="edit" color="grey-7" :aria-label="t('actions.edit')" @click="openEdit(entry)" />
                <q-btn flat round dense size="sm" icon="delete" color="negative" :aria-label="t('actions.delete')" @click="remove(entry)" />
              </div>
            </q-item-section>
          </q-item>
        </q-list>
        </q-card>
      </div>
    </template>

    <FormDialog v-model="editOpen" :title="t('journal.editTitle')" icon="edit_note" :loading="saving" @submit="saveEdit">
      <div v-if="editing" class="column gap-md">
        <q-select
          v-model="editing.category"
          outlined
          dense
          emit-value
          map-options
          :options="JOURNAL_CATEGORIES.map((c) => ({ value: c.key, label: t(`journal.categories.${c.key}`) }))"
          :label="t('journal.category')"
        />
        <q-input v-model="editing.text" outlined autogrow maxlength="500" :label="t('journal.text')" />
        <q-input v-model="editing.when" outlined dense type="datetime-local" :label="t('journal.when')" />
      </div>
    </FormDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import axios from 'axios';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import { JOURNAL_CATEGORIES, journalCategory, type JournalCategory, type JournalEntry } from 'src/types/journal';
import { usePermissions } from 'src/composables/usePermissions';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDateTime } from 'src/utils/format';
import { intlLocale } from 'src/i18n/instance';

const props = defineProps<{ aquaId: number }>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();

const entries = ref<JournalEntry[]>([]);
const loading = ref(true);
const saving = ref(false);
const filters = ref<Set<JournalCategory>>(new Set());

// Date et heure locales au format du champ datetime-local
function localInput(value: Date = new Date()): string {
  const d = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return d.toISOString().slice(0, 16);
}

const form = ref<{ category: JournalCategory; text: string; when: string }>({ category: 'note', text: '', when: localInput() });

const counts = computed(() => {
  const result: Partial<Record<JournalCategory, number>> = {};
  for (const e of entries.value) result[e.category] = (result[e.category] ?? 0) + 1;
  return result;
});

const filtered = computed(() => (filters.value.size ? entries.value.filter((e) => filters.value.has(e.category)) : entries.value));

const groups = computed(() => {
  const result: { month: string; entries: JournalEntry[] }[] = [];
  for (const entry of filtered.value) {
    const month = new Date(entry.occurred_at).toLocaleDateString(intlLocale(), { month: 'long', year: 'numeric' });
    const last = result[result.length - 1];
    if (last && last.month === month) last.entries.push(entry);
    else result.push({ month, entries: [entry] });
  }
  return result;
});

function toggleFilter(key: JournalCategory) {
  const next = new Set(filters.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  filters.value = next;
}

async function load() {
  try {
    entries.value = (await axios.get<JournalEntry[]>('/journal/', { params: { aquarium_id: props.aquaId } })).data;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('journal.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

async function add() {
  const text = form.value.text.trim();
  if (!text) return;
  saving.value = true;
  try {
    const { data } = await axios.post<JournalEntry>('/journal/', {
      aquarium_id: props.aquaId,
      category: form.value.category,
      text,
      occurred_at: new Date(form.value.when).toISOString(),
    });
    entries.value = [data, ...entries.value].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
    form.value = { category: form.value.category, text: '', when: localInput() };
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('journal.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

const editOpen = ref(false);
const editing = ref<{ id: number; category: JournalCategory; text: string; when: string } | null>(null);

function openEdit(entry: JournalEntry) {
  editing.value = { id: entry.id, category: entry.category, text: entry.text, when: localInput(new Date(entry.occurred_at)) };
  editOpen.value = true;
}

async function saveEdit() {
  const e = editing.value;
  if (!e || !e.text.trim()) return;
  saving.value = true;
  try {
    const { data } = await axios.patch<JournalEntry>(`/journal/${e.id}`, {
      category: e.category,
      text: e.text.trim(),
      occurred_at: new Date(e.when).toISOString(),
    });
    entries.value = entries.value.map((x) => (x.id === data.id ? data : x)).sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
    editOpen.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('journal.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

function remove(entry: JournalEntry) {
  confirmRemove(t('journal.item'), async () => {
    await axios.delete(`/journal/${entry.id}`);
    entries.value = entries.value.filter((x) => x.id !== entry.id);
  });
}

onMounted(load);
watch(() => props.aquaId, () => {
  loading.value = true;
  void load();
});
</script>

<style scoped>
.month::first-letter {
  text-transform: uppercase;
}

.entry-text {
  white-space: pre-line;
}

@media (min-width: 1024px) {
  .journal-when {
    min-width: 210px;
  }
}

.category-btn {
  border-radius: 999px;
}
</style>
