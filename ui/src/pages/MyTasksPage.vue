<template>
  <div>
    <PageHeader section :title="t('tasks.title')" :subtitle="t('tasks.subtitle')">
      <template #actions>
        <q-btn outline color="primary" icon="event" :label="t('tasks.calendar')" to="/calendar" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('tasks.add')" @click="openAddTaskDialog" />
      </template>
    </PageHeader>

    <div v-if="taskStore.loading" class="text-center q-py-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <EmptyState
      v-else-if="sortedTasks.length === 0"
      icon="task_alt"
      :title="t('tasks.emptyTitle')"
      :message="t('tasks.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('tasks.add')" @click="openAddTaskDialog" />
    </EmptyState>

    <div v-else class="row q-col-gutter-md">
      <div v-for="task in sortedTasks" :key="task.id" class="col-12 col-sm-6 col-md-4">
        <q-card flat bordered class="full-height q-pa-sm column">
          <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
            <div class="col text-subtitle1 text-weight-bold ellipsis-2-lines" :title="task.title">{{ task.title }}</div>
            <q-btn v-if="can.edit" flat round dense icon="more_vert" color="grey-7">
              <q-menu auto-close>
                <q-list style="min-width: 140px">
                  <q-item v-if="can.edit" clickable @click="openEditTaskDialog(task)">
                    <q-item-section avatar><q-icon name="edit" size="xs" /></q-item-section>
                    <q-item-section>{{ t('actions.edit') }}</q-item-section>
                  </q-item>
                  <q-item v-if="can.manage" clickable class="text-negative" @click="removeTask(task)">
                    <q-item-section avatar><q-icon name="delete" size="xs" color="negative" /></q-item-section>
                    <q-item-section>{{ t('actions.delete') }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </q-card-section>

          <q-card-section class="q-pt-none col">
            <div v-if="task.description" class="text-body2 text-grey-8 q-mb-sm">{{ task.description }}</div>

            <div class="row items-center q-mb-sm">
              <q-chip dense color="grey-3" text-color="grey-9" icon="repeat" class="q-ml-none">
                {{ t(`tasks.recurrences.${task.recurrence}`) }}{{ task.recurrence === 'custom_days' ? t('tasks.customDays', { n: task.recurrence_days }) : '' }}
              </q-chip>
              <ScopeChip :entity="task" />
            </div>

            <div class="text-caption" :class="isOverdue(task) ? 'text-negative text-weight-bold' : 'text-grey-8'">
              <q-icon :name="isOverdue(task) ? 'event_busy' : 'event'" size="xs" class="q-mr-xs" />
              {{ t('tasks.due', { date: task.next_due_at ? formatDate(task.next_due_at) : t('tasks.none') }) }}
            </div>
            <div class="text-caption text-grey-7 q-mt-xs">
              {{ t('tasks.lastDone', { date: formatDate(task.last_completed_at) }) }}
            </div>
          </q-card-section>

          <q-card-actions align="between">
            <q-btn flat dense :label="t('tasks.history')" icon="history" color="grey-8" class="q-px-sm" @click="openTaskHistoryDialog(task)" />
            <q-btn v-if="can.care" unelevated dense :label="t('tasks.markDone')" icon="check" color="positive" class="q-px-sm" @click="openCompleteTaskDialog(task)" />
          </q-card-actions>
        </q-card>
      </div>
    </div>

    <!-- Ajout / édition d'une tâche -->
    <FormDialog
      v-model="taskDialog"
      icon="task_alt"
      :title="isEditingTask ? t('tasks.editTitle') : t('tasks.add')"
      :subtitle="t('tasks.formSubtitle')"
      width="480px"
      :submit-label="isEditingTask ? t('common.save') : t('actions.add')"
      @submit="saveTask"
    >
      <q-input v-model="taskForm.title" :label="t('tasks.titleField')" outlined dense autofocus />
      <q-input v-model="taskForm.description" :label="t('tasks.description')" type="textarea" outlined dense autogrow />
      <AppSelect v-model="taskForm.recurrence" :options="recurrenceOptions" :label="t('tasks.recurrence')" />
      <q-input
        v-if="taskForm.recurrence === 'custom_days'"
        v-model.number="taskForm.recurrence_days"
        type="number"
        min="1"
        :label="t('tasks.everyHowManyDays')"
        :suffix="t('tasks.days')"
        outlined
        dense
      />
      <DateInput v-model="taskForm.next_due_date" :label="t('tasks.nextDue')" clearable />
      <ScopeSelector v-model="taskScope" :current-aquarium-id="aquaId" />
      <div v-if="taskScope.scope !== 'single'" class="text-caption text-grey-7">
        {{ t('tasks.sharedHelp') }}
      </div>
    </FormDialog>

    <!-- Marquer fait -->
    <FormDialog
      v-model="completeDialog"
      icon="check_circle"
      icon-bg="green-1"
      icon-color="positive"
      :title="t('tasks.completeTitle')"
      :subtitle="activeTask?.title"
      width="420px"
      :submit-label="t('tasks.validate')"
      submit-color="positive"
      @submit="saveCompletion"
    >
      <DateInput v-model="completeForm.date" :label="t('tasks.doneDate')" />
      <q-input v-model="completeForm.note" :label="t('tasks.note')" outlined dense />
    </FormDialog>

    <!-- Historique des réalisations -->
    <FormDialog
      v-model="taskHistoryDialog"
      icon="history"
      :title="t('tasks.history')"
      :subtitle="activeTask?.title"
      width="480px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <q-list v-if="activeTaskCompletions.length > 0" bordered separator class="rounded-borders">
        <q-item v-for="c in activeTaskCompletions" :key="c.id">
          <q-item-section avatar><q-icon name="check_circle" color="positive" /></q-item-section>
          <q-item-section>
            <q-item-label>{{ formatDate(c.completed_at) }}</q-item-label>
            <q-item-label v-if="c.note" caption>{{ c.note }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-btn v-if="can.manage" flat round dense icon="delete" color="negative" size="sm" :aria-label="t('actions.delete')" @click="deleteTaskCompletion(c)">
              <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
            </q-btn>
          </q-item-section>
        </q-item>
      </q-list>
      <div v-else class="text-center text-grey-6 q-pa-md">{{ t('tasks.noHistory') }}</div>
    </FormDialog>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { usePermissions } from 'src/composables/usePermissions';
import { ref, computed, onMounted } from 'vue';
import { useQuasar } from 'quasar';
import { useMaintenanceTaskStore } from 'src/stores/maintenanceTaskStore';
import type { MaintenanceTask, MaintenanceTaskCompletion, TaskRecurrence } from 'src/types/maintenanceTask';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import ScopeChip from 'src/components/ScopeChip.vue';
import ScopeSelector from 'src/components/ScopeSelector.vue';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { scopeFrom, scopePayload, type ScopeValue } from 'src/utils/sharedScope';
import DateInput from 'src/components/DateInput.vue';
import AppSelect from 'src/components/AppSelect.vue';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, isoDate } from 'src/utils/format';

const { t } = useI18n();

const props = defineProps({
  aquaId: { type: Number, required: true },
});

const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const taskStore = useMaintenanceTaskStore();
const aquariumStore = useAquariumStore();

const todayDateStr = () => isoDate();
const dateStrFrom = isoDate;

onMounted(async () => {
  await Promise.all([
    taskStore.fetch(props.aquaId),
    aquariumStore.aquariums.length === 0 ? aquariumStore.fetch() : Promise.resolve(),
  ]);
});

// --- Tâches ---
const RECURRENCES: TaskRecurrence[] = ['none', 'daily', 'weekly', 'monthly', 'custom_days'];
const recurrenceOptions = computed(() => RECURRENCES.map((value) => ({ label: t(`tasks.recurrenceOptions.${value}`), value })));

const sortedTasks = computed(() =>
  [...taskStore.tasks].sort((a, b) => {
    const aOverdue = isOverdue(a);
    const bOverdue = isOverdue(b);
    if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;
    if (!a.next_due_at && !b.next_due_at) return a.title.localeCompare(b.title);
    if (!a.next_due_at) return 1;
    if (!b.next_due_at) return -1;
    return a.next_due_at.localeCompare(b.next_due_at);
  }),
);

// En retard à partir du lendemain de l'échéance (les échéances n'ont pas d'heure)
function isOverdue(task: MaintenanceTask): boolean {
  return !!task.next_due_at && isoDate(new Date(task.next_due_at)) < todayDateStr();
}

const taskDialog = ref(false);
const isEditingTask = ref(false);
const editingTaskId = ref<number | null>(null);
const taskForm = ref<{
  title: string;
  description: string;
  recurrence: TaskRecurrence;
  recurrence_days?: number | null;
  next_due_date: string;
}>({ title: '', description: '', recurrence: 'none', next_due_date: '' });
const taskScope = ref<ScopeValue>(scopeFrom(null, props.aquaId));

function openAddTaskDialog() {
  isEditingTask.value = false;
  editingTaskId.value = null;
  taskForm.value = { title: '', description: '', recurrence: 'none', next_due_date: '' };
  taskScope.value = scopeFrom(null, props.aquaId);
  taskDialog.value = true;
}

function openEditTaskDialog(task: MaintenanceTask) {
  isEditingTask.value = true;
  editingTaskId.value = task.id;
  taskForm.value = {
    title: task.title,
    description: task.description ?? '',
    recurrence: task.recurrence,
    recurrence_days: task.recurrence_days ?? null,
    next_due_date: task.next_due_at ? dateStrFrom(new Date(task.next_due_at)) : '',
  };
  taskScope.value = scopeFrom(task, props.aquaId);
  taskDialog.value = true;
}

async function saveTask() {
  if (!taskForm.value.title.trim()) {
    $q.notify({ type: 'warning', message: t('tasks.notify.titleRequired') });
    return;
  }
  if (taskForm.value.recurrence === 'custom_days' && !taskForm.value.recurrence_days) {
    $q.notify({ type: 'warning', message: t('tasks.notify.daysRequired') });
    return;
  }
  if (taskScope.value.scope === 'multiple' && taskScope.value.aquarium_ids.length === 0) {
    $q.notify({ type: 'warning', message: t('tasks.notify.aquariumRequired') });
    return;
  }

  const scope = scopePayload(taskScope.value, props.aquaId);
  const payload = {
    title: taskForm.value.title.trim(),
    description: taskForm.value.description || null,
    recurrence: taskForm.value.recurrence,
    recurrence_days: taskForm.value.recurrence === 'custom_days' ? (taskForm.value.recurrence_days ?? null) : null,
    next_due_at: taskForm.value.next_due_date ? `${taskForm.value.next_due_date}T12:00:00` : null,
    ...scope,
  };
  try {
    if (isEditingTask.value && editingTaskId.value !== null) {
      await taskStore.update(editingTaskId.value, payload);
    } else {
      await taskStore.create({ aquarium_id: props.aquaId, ...payload });
    }
    taskDialog.value = false;
    // La tâche peut ne plus concerner ce bac après changement de portée
    if (scope.scope === 'multiple' && !scope.aquarium_ids.includes(props.aquaId)) await taskStore.fetch(props.aquaId);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('tasks.notify.saveFailed')) });
  }
}

function removeTask(task: MaintenanceTask) {
  const shared = task.scope !== 'single' ? t('tasks.deleteShared') : '';
  confirmRemove(t('tasks.item', { title: task.title }), () => taskStore.remove(task.id), {
    message: t('tasks.deleteMessage', { title: task.title }) + shared,
  });
}

// --- Marquer fait ---
const completeDialog = ref(false);
const activeTask = ref<MaintenanceTask | null>(null);
const completeForm = ref<{ date: string; note: string }>({ date: todayDateStr(), note: '' });

function openCompleteTaskDialog(task: MaintenanceTask) {
  activeTask.value = task;
  completeForm.value = { date: todayDateStr(), note: '' };
  completeDialog.value = true;
}

async function saveCompletion() {
  if (!activeTask.value) return;
  if (!completeForm.value.date) {
    $q.notify({ type: 'warning', message: t('tasks.notify.dateRequired') });
    return;
  }
  try {
    await taskStore.complete(activeTask.value.id, {
      completed_at: `${completeForm.value.date}T12:00:00`,
      note: completeForm.value.note || null,
    });
    completeDialog.value = false;
    $q.notify({ type: 'positive', message: t('tasks.notify.done') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('tasks.notify.failed')) });
  }
}

// --- Historique tâche ---
const taskHistoryDialog = ref(false);
const activeTaskCompletions = ref<MaintenanceTaskCompletion[]>([]);

async function openTaskHistoryDialog(task: MaintenanceTask) {
  activeTask.value = task;
  activeTaskCompletions.value = await taskStore.fetchCompletions(task.id);
  taskHistoryDialog.value = true;
}

function deleteTaskCompletion(completion: MaintenanceTaskCompletion) {
  const task = activeTask.value;
  if (!task) return;
  confirmRemove(
    t('tasks.completionItem', { date: formatDate(completion.completed_at) }),
    async () => {
      await taskStore.deleteCompletion(task.id, completion.id);
      activeTaskCompletions.value = activeTaskCompletions.value.filter((c) => c.id !== completion.id);
    },
    { message: t('tasks.completionDelete', { date: formatDate(completion.completed_at) }) },
  );
}
</script>
