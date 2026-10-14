<template>
  <div>
    <PageHeader section :title="t('rules.title')" :subtitle="t('rules.subtitle')">
      <template #actions>
        <AppInput v-if="aquariumRules.length > 0" v-model="search" icon="search" :placeholder="t('equipments.search')" clearable style="width: 220px" />
        <q-btn v-if="can.manage" unelevated color="primary" icon="add" :label="t('rules.add')" @click="openCreate" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="aquariumRules.length === 0"
      icon="rule"
      :title="t('rules.emptyTitle')"
      :message="t('rules.emptyMessage')"
    >
      <q-btn v-if="can.manage" unelevated color="primary" icon="add" :label="t('rules.add')" @click="openCreate" />
    </EmptyState>

    <EmptyState v-else-if="filteredRules.length === 0" icon="search_off" :title="t('rules.noResult', { q: search })" />

    <q-card v-else flat bordered>
      <q-list separator>
      <q-item v-for="rule in filteredRules" :key="rule.id" :class="{ 'rule-off': !rule.is_active }">
        <q-item-section avatar :class="{ 'rule-avatar--xs': $q.screen.lt.sm }">
          <q-avatar :size="$q.screen.lt.sm ? '32px' : '40px'" :color="actionMeta(rule.action).bg" :text-color="actionMeta(rule.action).color" :icon="actionMeta(rule.action).icon" />
        </q-item-section>
        <q-item-section>
          <q-item-label class="text-weight-bold row items-center q-gutter-x-xs">
            <span>{{ rule.name }}</span>
            <q-badge v-if="rule.is_safety_lock" color="deep-orange" :label="t('rules.safety')">
              <q-tooltip>{{ t('rules.safetyHelp') }}</q-tooltip>
            </q-badge>
          </q-item-label>
          <q-item-label caption class="text-body2 text-grey-8">
            <span class="text-grey-6">{{ t('rules.if') }}</span> {{ conditionsSummary(rule) }}
            <span class="text-grey-6">→</span> <b>{{ actionSummary(rule) }}</b>
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <!-- Téléphone : interrupteur au-dessus des boutons, pour laisser la largeur au texte -->
          <div :class="$q.screen.lt.sm ? 'column items-end' : 'row items-center no-wrap q-gutter-xs'">
            <q-toggle :disable="!can.manage" :model-value="rule.is_active" color="positive" @update:model-value="toggleActive(rule)">
              <q-tooltip>{{ rule.is_active ? t('rules.disable') : t('rules.enable') }}</q-tooltip>
            </q-toggle>
            <div class="row no-wrap">
              <q-btn v-if="can.manage" flat round dense icon="edit" color="grey-7" @click="openEdit(rule)">
                <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
              </q-btn>
              <q-btn v-if="can.manage" flat round dense icon="delete" color="negative" @click="removeRule(rule)">
                <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
              </q-btn>
            </div>
          </div>
        </q-item-section>
      </q-item>
      </q-list>
    </q-card>

    <FormDialog
      v-model="dialog"
      icon="rule"
      :title="editingId ? t('rules.form.editTitle') : t('rules.form.newTitle')"
      :subtitle="t('rules.form.subtitle')"
      width="740px"
      :loading="saving"
      @submit="save"
    >
          <q-input v-model="form.name" :label="t('rules.form.name')" outlined dense />

          <!-- Conditions -->
          <div>
            <div class="row items-center justify-between q-mb-sm">
              <div class="text-subtitle2 text-weight-bold">{{ t('rules.form.conditions') }}</div>
              <q-btn-toggle
                v-if="form.conditions.length > 1"
                v-model="form.match_type"
                dense
                unelevated
                toggle-color="primary"
                color="grey-2"
                text-color="grey-8"
                :options="[
                  { label: t('rules.form.all'), value: 'AND' },
                  { label: t('rules.form.any'), value: 'OR' },
                ]"
              />
            </div>

            <template v-for="(cond, index) in form.conditions" :key="index">
              <div v-if="index > 0" class="row justify-center q-my-xs">
                <q-chip dense :color="form.match_type === 'AND' ? 'blue-grey-2' : 'orange-2'" class="text-weight-bold">
                  {{ form.match_type === 'AND' ? t('rules.form.and') : t('rules.form.or') }}
                </q-chip>
              </div>
              <q-card flat bordered class="q-pa-sm bg-grey-1">
                <div class="row q-col-gutter-sm items-center">
                  <div class="col-12 col-sm-auto">
                    <q-btn-toggle
                      :model-value="cond.condition_type === 'TIME_RANGE' ? 'TIME' : 'SENSOR'"
                      dense
                      unelevated
                      toggle-color="primary"
                      color="white"
                      text-color="grey-8"
                      :options="[
                        { value: 'SENSOR', slot: 'sensor' },
                        { value: 'TIME', slot: 'time' },
                      ]"
                      @update:model-value="(v: string) => setConditionKind(cond, v)"
                    >
                      <template #sensor><q-icon name="sensors" /><q-tooltip>{{ t('rules.form.sensor') }}</q-tooltip></template>
                      <template #time><q-icon name="schedule" /><q-tooltip>{{ t('rules.form.timeRange') }}</q-tooltip></template>
                    </q-btn-toggle>
                  </div>

                  <template v-if="cond.condition_type === 'TIME_RANGE'">
                    <div class="col-5 col-sm-4">
                      <q-input v-model="cond.start_time" type="time" :label="t('rules.form.from')" outlined dense bg-color="white" />
                    </div>
                    <div class="col-5 col-sm-4">
                      <q-input v-model="cond.end_time" type="time" :label="t('rules.form.to')" outlined dense bg-color="white" />
                    </div>
                  </template>
                  <div v-else class="col-12 col-sm-4">
                    <q-select
                      :model-value="cond.sensor_id"
                      :options="sensorOptions"
                      emit-value
                      map-options
                      :label="t('rules.form.sensor')"
                      outlined
                      dense
                      bg-color="white"
                      @update:model-value="(id: number) => setConditionSensor(cond, id)"
                    >
                      <template #option="scope">
                        <q-item v-bind="scope.itemProps">
                          <q-item-section avatar><q-icon :name="scope.opt.numeric ? 'thermostat' : 'water'" /></q-item-section>
                          <q-item-section>{{ scope.opt.label }}</q-item-section>
                        </q-item>
                      </template>
                    </q-select>
                  </div>

                  <template v-if="cond.condition_type === 'THRESHOLD'">
                    <div class="col-5 col-sm-2">
                      <q-select v-model="cond.operator" :options="operatorOptions" emit-value map-options :label="t('rules.form.ifLabel')" outlined dense bg-color="white" />
                    </div>
                    <div class="col-5 col-sm-2">
                      <q-input v-model.number="cond.threshold_value" type="number" step="0.1" :label="t('rules.form.value')" suffix="°C" outlined dense bg-color="white" />
                    </div>
                  </template>
                  <div v-else-if="cond.condition_type === 'TIME_RANGE'" class="col-2 col-sm-auto" />
                  <div v-else-if="cond.sensor_id" class="col-10 col-sm-4">
                    <q-select
                      v-model="cond.trigger_state"
                      :options="stateOptions"
                      emit-value
                      map-options
                      :label="t('rules.form.waterLevel')"
                      outlined
                      dense
                      bg-color="white"
                      :hint="t('rules.form.waterLevelHint')"
                    />
                  </div>
                  <div v-else class="col-10 col-sm-4 text-caption text-grey-6">{{ t('rules.form.chooseSensor') }}</div>

                  <div class="col-2 col-sm text-right">
                    <q-btn flat round dense icon="delete" color="negative" :disable="form.conditions.length === 1" @click="form.conditions.splice(index, 1)" />
                  </div>
                </div>
              </q-card>
            </template>
            <q-btn flat dense icon="add" color="primary" :label="t('rules.form.addCondition')" class="q-mt-sm" @click="addCondition" />
            <q-banner v-if="timeWithoutRtc" dense rounded class="bg-orange-1 text-orange-10 q-mt-sm">
              <template #avatar><q-icon name="schedule" color="orange-8" /></template>
              {{ t('rules.form.rtcWarning') }}
            </q-banner>
          </div>

          <!-- Action -->
          <div>
            <div class="text-subtitle2 text-weight-bold q-mb-sm">{{ t('rules.form.then') }}</div>
            <div class="row q-col-gutter-sm">
              <div class="col-12 col-sm-4">
                <q-select v-model="form.action" :options="actionOptions" emit-value map-options :label="t('rules.form.action')" outlined dense />
              </div>
              <template v-if="form.action !== 'NOTIFY'">
                <div class="col-12 col-sm-4">
                  <q-select
                    v-model="form.equipment_id"
                    :options="equipmentOptions"
                    emit-value
                    map-options
                    clearable
                    :label="t('rules.form.equipment')"
                    outlined
                    dense
                    :disable="!!form.group_id"
                  />
                </div>
                <div class="col-12 col-sm-4">
                  <q-select
                    v-model="form.group_id"
                    :options="groupOptions"
                    emit-value
                    map-options
                    clearable
                    :label="t('rules.form.orGroup')"
                    outlined
                    dense
                    :disable="!!form.equipment_id"
                  />
                </div>
              </template>
              <div v-else class="col-12 col-sm-8">
                <q-input v-model="form.notification_message" :label="t('rules.form.notificationMessage')" outlined dense maxlength="200" />
              </div>
            </div>
          </div>

          <div class="column q-gutter-xs">
            <div v-if="form.action === 'ON'" class="row items-center q-gutter-sm">
              <q-input
                v-model.number="form.max_duration_seconds"
                type="number"
                min="1"
                :label="t('rules.form.autoOff')"
                :hint="t('rules.form.autoOffHint')"
                outlined
                dense
                clearable
                style="width: 280px"
              />
            </div>
            <q-toggle
              v-if="form.action !== 'NOTIFY'"
              v-model="form.revert_on_exit"
              :label="revertLabel"
              color="primary"
            />
            <q-toggle
              v-if="form.action !== 'NOTIFY'"
              v-model="form.is_safety_lock"
              :label="t('rules.form.safetyRule')"
              color="deep-orange"
            />
            <q-toggle v-model="form.is_active" :label="t('rules.form.active')" color="positive" />
          </div>
    </FormDialog>
  </div>
</template>

<script setup lang="ts">
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import AppInput from 'src/components/AppInput.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import { useRuleStore } from 'src/stores/ruleStore';
import { useEquipmentStore } from 'src/stores/equipmentStore';
import { useEquipmentGroupStore } from 'src/stores/equipmentGroupStore';
import { useSensorStore } from 'src/stores/sensorStore';
import { useControllerStore } from 'src/stores/controllerStore';
import type { Rule, RuleAction, RuleCondition, RuleCreate, ThresholdOperator } from 'src/types/rule';
import type { Sensor } from 'src/types/sensor';
import type { Controller } from 'src/types/controller';

const props = defineProps<{ aquaId: number }>();
const { t } = useI18n();

const operatorOptions = computed<{ label: string; value: ThresholdOperator }[]>(() => [
  { label: t('rules.operators.gt'), value: '>' },
  { label: t('rules.operators.gte'), value: '>=' },
  { label: t('rules.operators.lt'), value: '<' },
  { label: t('rules.operators.lte'), value: '<=' },
]);
const OPERATOR_SYMBOLS: Record<ThresholdOperator, string> = { '>': '>', '>=': '≥', '<': '<', '<=': '≤' };
// État logique, tel qu'affiché dans Capteurs : l'inversion du flotteur est
// appliquée par l'API et convertie dans le firmware
const stateOptions = computed(() => [
  { label: t('rules.states.high'), value: 'HIGH' },
  { label: t('rules.states.low'), value: 'LOW' },
]);
const actionOptions = computed<{ label: string; value: RuleAction }[]>(() => [
  { label: t('rules.actions.on'), value: 'ON' },
  { label: t('rules.actions.off'), value: 'OFF' },
  { label: t('rules.actions.notify'), value: 'NOTIFY' },
]);

const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const ruleStore = useRuleStore();
const equipmentStore = useEquipmentStore();
const groupStore = useEquipmentGroupStore();
const sensorStore = useSensorStore();
const controllerStore = useControllerStore();

const search = ref<string | null>('');
const dialog = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);

function isNumericSensor(sensor: Sensor | undefined): boolean {
  const unit = (sensor?.unit ?? '').toLowerCase();
  return unit === '°c' || unit === 'temperature';
}

const aquariumSensors = computed(() => sensorStore.sensors.filter((s) => s.aquarium_id === props.aquaId));
const aquariumEquipments = computed(() => equipmentStore.equipments.filter((e) => e.aquarium_id === props.aquaId));

const sensorOptions = computed(() =>
  aquariumSensors.value.map((s) => ({ label: s.name, value: s.id, numeric: isNumericSensor(s) })),
);
const equipmentOptions = computed(() => aquariumEquipments.value.map((e) => ({ label: e.name, value: e.id })));
const groupOptions = computed(() =>
  groupStore.groups
    .filter((g) => g.equipments.some((ge) => aquariumEquipments.value.some((e) => e.id === ge.id)))
    .map((g) => ({ label: g.name, value: g.id })),
);

// Une règle appartient à l'aquarium de son équipement cible ou de ses capteurs
const aquariumRules = computed(() => {
  const sensorIds = new Set(aquariumSensors.value.map((s) => s.id));
  const equipmentIds = new Set(aquariumEquipments.value.map((e) => e.id));
  const groupIds = new Set(groupOptions.value.map((g) => g.value));
  return ruleStore.rules.filter(
    (r) =>
      (r.equipment_id != null && equipmentIds.has(r.equipment_id)) ||
      (r.group_id != null && groupIds.has(r.group_id)) ||
      r.conditions.some((c) => c.sensor_id != null && sensorIds.has(c.sensor_id)),
  );
});

const filteredRules = computed(() => {
  const s = (search.value ?? '').trim().toLowerCase();
  const rules = [...aquariumRules.value].sort((a, b) => a.name.localeCompare(b.name));
  return s ? rules.filter((r) => r.name.toLowerCase().includes(s) || conditionsSummary(r).toLowerCase().includes(s)) : rules;
});

function sensorName(id: number | null | undefined): string {
  return sensorStore.sensors.find((s) => s.id === id)?.name ?? t('rules.summary.sensorN', { id });
}

function hhmm(value: string | null | undefined): string {
  return (value ?? '').slice(0, 5);
}

// « Quand la condition n'est plus remplie : rallumer Osmolateur » (action inverse)
const revertLabel = computed(() => {
  const f = form.value;
  const target =
    equipmentStore.equipments.find((e) => e.id === f.equipment_id)?.name ??
    groupStore.groups.find((g) => g.id === f.group_id)?.name ??
    t('rules.form.theEquipment');
  const action = f.action === 'ON' ? t('rules.form.revertTurnOff') : t('rules.form.revertTurnOn');
  return t('rules.form.revert', { action, target });
});

function conditionText(c: RuleCondition): string {
  if (c.condition_type === 'TIME_RANGE') return t('rules.summary.between', { start: hhmm(c.start_time), end: hhmm(c.end_time) });
  if (c.condition_type === 'THRESHOLD') {
    return `${sensorName(c.sensor_id)} ${OPERATOR_SYMBOLS[c.operator ?? '>']} ${c.threshold_value} °C`;
  }
  return `${sensorName(c.sensor_id)} ${c.trigger_state === 'HIGH' ? t('rules.summary.levelHigh') : t('rules.summary.levelLow')}`;
}

function conditionsSummary(rule: Rule): string {
  return rule.conditions.map(conditionText).join(rule.match_type === 'OR' ? t('rules.summary.or') : t('rules.summary.and'));
}

function actionSummary(rule: Rule): string {
  if (rule.action === 'NOTIFY') {
    return rule.notification_message
      ? t('rules.summary.notifyMessage', { message: rule.notification_message })
      : t('rules.summary.notify');
  }
  const target =
    equipmentStore.equipments.find((e) => e.id === rule.equipment_id)?.name ??
    groupStore.groups.find((g) => g.id === rule.group_id)?.name ??
    '?';
  const duration =
    rule.action === 'ON' && rule.max_duration_seconds ? t('rules.summary.maxDuration', { n: rule.max_duration_seconds }) : '';
  const revert = rule.revert_on_exit
    ? rule.action === 'ON'
      ? t('rules.summary.revertOff')
      : t('rules.summary.revertOn')
    : '';
  return `${t(rule.action === 'ON' ? 'rules.summary.turnOn' : 'rules.summary.turnOff', { target })}${duration}${revert}`;
}

function actionMeta(action: RuleAction) {
  if (action === 'ON') return { icon: 'power', color: 'positive', bg: 'green-1' };
  if (action === 'OFF') return { icon: 'power_off', color: 'negative', bg: 'red-1' };
  return { icon: 'notifications', color: 'primary', bg: 'blue-1' };
}

// --- Formulaire ---
function emptyForm(): RuleCreate {
  return {
    name: '',
    action: 'OFF',
    match_type: 'AND',
    is_active: true,
    is_safety_lock: false,
    equipment_id: null,
    group_id: null,
    max_duration_seconds: null,
    revert_on_exit: false,
    notification_message: '',
    conditions: [{ sensor_id: null, condition_type: 'SENSOR_STATE', trigger_state: 'LOW' }],
  };
}

const form = ref<RuleCreate>(emptyForm());

function setConditionSensor(cond: RuleCondition, sensorId: number) {
  cond.sensor_id = sensorId;
  const numeric = isNumericSensor(sensorStore.sensors.find((s) => s.id === sensorId));
  cond.condition_type = numeric ? 'THRESHOLD' : 'SENSOR_STATE';
  if (numeric) {
    cond.operator = cond.operator ?? '>';
    cond.trigger_state = null;
  } else {
    cond.trigger_state = cond.trigger_state ?? 'LOW';
    cond.operator = null;
    cond.threshold_value = null;
  }
}

function setConditionKind(cond: RuleCondition, kind: string) {
  if (kind === 'TIME') {
    Object.assign(cond, {
      condition_type: 'TIME_RANGE',
      sensor_id: null,
      trigger_state: null,
      operator: null,
      threshold_value: null,
      start_time: cond.start_time ?? '12:00',
      end_time: cond.end_time ?? '13:00',
    });
  } else if (cond.condition_type === 'TIME_RANGE') {
    Object.assign(cond, { condition_type: 'SENSOR_STATE', trigger_state: 'LOW', start_time: null, end_time: null });
  }
}

// Contrôleur(s) qui exécuteront la règle : ceux des équipements pilotés, sinon ceux des capteurs
function ruleControllers(rule: Partial<RuleCreate>): Controller[] {
  const ids = new Set<number>();
  const group = groupStore.groups.find((g) => g.id === rule.group_id);
  const equipmentIds = rule.equipment_id ? [rule.equipment_id] : group ? group.equipments.map((e) => e.id) : [];
  equipmentIds.forEach((id) => {
    const eq = equipmentStore.equipments.find((e) => e.id === id);
    if (eq) ids.add(eq.controller_id);
  });
  if (ids.size === 0) {
    for (const c of rule.conditions ?? []) {
      const sensor = sensorStore.sensors.find((s) => s.id === c.sensor_id);
      if (sensor) ids.add(sensor.controller_id);
    }
  }
  return controllerStore.controllers.filter((c) => ids.has(c.id));
}

const timeWithoutRtc = computed(() => {
  if (!form.value.conditions.some((c) => c.condition_type === 'TIME_RANGE')) return false;
  const controllers = ruleControllers(form.value);
  return controllers.length === 0 || controllers.some((c) => !c.rtc_model);
});

function addCondition() {
  form.value.conditions.push({ sensor_id: null, condition_type: 'SENSOR_STATE', trigger_state: 'LOW' });
}

function openCreate() {
  editingId.value = null;
  form.value = emptyForm();
  dialog.value = true;
}

function openEdit(rule: Rule) {
  editingId.value = rule.id;
  form.value = {
    ...emptyForm(),
    ...rule,
    notification_message: rule.notification_message ?? '',
    revert_on_exit: rule.revert_on_exit ?? false,
    conditions: rule.conditions.map((c) => ({ ...c, start_time: hhmm(c.start_time) || null, end_time: hhmm(c.end_time) || null })),
  };
  dialog.value = true;
}

function validationError(): string | null {
  const f = form.value;
  if (!f.name.trim()) return t('rules.errors.name');
  if (f.conditions.some((c) => c.condition_type !== 'TIME_RANGE' && c.sensor_id == null)) {
    return t('rules.errors.sensor');
  }
  if (f.conditions.some((c) => c.condition_type === 'TIME_RANGE' && (!c.start_time || !c.end_time))) {
    return t('rules.errors.timeRange');
  }
  if (f.conditions.some((c) => c.condition_type === 'TIME_RANGE' && hhmm(c.start_time) === hhmm(c.end_time))) {
    return t('rules.errors.sameTime');
  }
  if (f.conditions.some((c) => c.condition_type === 'THRESHOLD' && (c.threshold_value == null || Number.isNaN(c.threshold_value)))) {
    return t('rules.errors.threshold');
  }
  if (f.action !== 'NOTIFY' && !f.equipment_id && !f.group_id) return t('rules.errors.target');
  return null;
}

function affectedControllerIds(rule: Partial<RuleCreate> | undefined): number[] {
  if (!rule) return [];
  const ids = new Set<number>();
  for (const c of rule.conditions ?? []) {
    const sensor = sensorStore.sensors.find((s) => s.id === c.sensor_id);
    if (sensor) ids.add(sensor.controller_id);
  }
  ruleControllers(rule).forEach((c) => ids.add(c.id));
  return [...ids];
}

async function save() {
  const error = validationError();
  if (error) {
    $q.notify({ type: 'warning', message: error });
    return;
  }
  const f = form.value;
  const payload: RuleCreate = {
    name: f.name.trim(),
    action: f.action,
    match_type: f.conditions.length > 1 ? f.match_type : 'AND',
    is_active: f.is_active,
    is_safety_lock: f.action === 'NOTIFY' ? false : f.is_safety_lock,
    equipment_id: f.action === 'NOTIFY' ? null : f.equipment_id ?? null,
    group_id: f.action === 'NOTIFY' ? null : f.group_id ?? null,
    max_duration_seconds: f.action === 'ON' && f.max_duration_seconds ? f.max_duration_seconds : null,
    revert_on_exit: f.action === 'NOTIFY' ? false : !!f.revert_on_exit,
    notification_message: f.action === 'NOTIFY' ? f.notification_message?.trim() || null : null,
    conditions: f.conditions.map((c): RuleCondition => {
      if (c.condition_type === 'TIME_RANGE') {
        return { sensor_id: null, condition_type: 'TIME_RANGE', start_time: hhmm(c.start_time), end_time: hhmm(c.end_time) };
      }
      return {
        sensor_id: c.sensor_id,
        condition_type: c.condition_type,
        ...(c.condition_type === 'THRESHOLD'
          ? { operator: c.operator ?? '>', threshold_value: Number(c.threshold_value) }
          : { trigger_state: c.trigger_state ?? 'LOW' }),
      };
    }),
  };
  saving.value = true;
  try {
    const previous = editingId.value ? ruleStore.rules.find((r) => r.id === editingId.value) : undefined;
    if (editingId.value) await ruleStore.update(editingId.value, payload);
    else await ruleStore.add(payload);
    new Set([...affectedControllerIds(previous), ...affectedControllerIds(payload)]).forEach((id) =>
      controllerStore.markControllerAsDirty(id),
    );
    dialog.value = false;
    $q.notify({ type: 'positive', message: t('rules.notify.saved') });
    await ruleStore.fetch();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('rules.notify.saveFailed')), timeout: 7000 });
  } finally {
    saving.value = false;
  }
}

async function toggleActive(rule: Rule) {
  try {
    await ruleStore.update(rule.id, { is_active: !rule.is_active });
    affectedControllerIds(rule).forEach((id) => controllerStore.markControllerAsDirty(id));
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('rules.notify.updateFailed')) });
  }
}

function removeRule(rule: Rule) {
  confirmRemove(t('rules.item', { name: rule.name }), async () => {
    await ruleStore.remove(rule.id);
    affectedControllerIds(rule).forEach((id) => controllerStore.markControllerAsDirty(id));
  });
}

onMounted(() => {
  void Promise.all([ruleStore.fetch(), equipmentStore.fetch(), groupStore.fetch(), sensorStore.fetch()]).catch(() =>
    $q.notify({ type: 'negative', message: t('rules.notify.loadFailed') }),
  );
});
</script>

<style scoped>
.rule-off {
  opacity: 0.55;
}

.rule-avatar--xs {
  min-width: 40px;
  padding-right: 8px;
}
</style>
