<template>
  <div>
    <PageHeader section :title="t('dashboard.title')" :subtitle="t('dashboard.subtitle')">
      <template #actions>
        <q-btn
          v-if="can.edit && cards.length > 1"
          :outline="!arranging"
          :unelevated="arranging"
          color="primary"
          :icon="arranging ? 'check' : 'drag_indicator'"
          :label="arranging ? t('dashboard.arrangeDone') : t('dashboard.arrange')"
          @click="arranging = !arranging"
        />
        <q-btn v-if="can.edit && !arranging" unelevated color="primary" icon="add" :label="t('dashboard.addCard')" @click="openAddCardDialog" />
      </template>
    </PageHeader>

    <div v-if="cardStore.loading" class="text-center q-py-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <EmptyState
      v-else-if="cards.length === 0"
      icon="dashboard_customize"
      :title="t('dashboard.emptyTitle')"
      :message="t('dashboard.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('dashboard.addCard')" @click="openAddCardDialog" />
    </EmptyState>

    <!-- Grille des cartes (réorganisable par glisser-déposer) -->
    <div v-if="arranging && cards.length" class="app-callout text-caption q-mb-md">
      <q-icon name="drag_indicator" size="18px" />
      <div>{{ t('dashboard.arrangeHelp') }}</div>
    </div>
    <div v-if="!cardStore.loading && cards.length" ref="gridEl" class="row q-col-gutter-md">
      <div
        v-for="card in cards"
        :key="card.id"
        :class="cardColClass(card)"
      >
        <!-- Clic : vue agrandie (période, zoom) ; les commandes de la carte ne l'ouvrent pas -->
        <q-card
          flat
          bordered
          class="full-height column q-pa-sm dash-card"
          :class="{
            'dash-card--clickable': !arranging && hasDetail(card),
            'dash-card--arranging': arranging,
            // Liste d'équipements, évolution : contenu en haut plutôt qu'en bas de la carte
            'justify-between': card.type !== MetricType.WATER_TREND && cardEquipmentIds(card).length <= 1,
          }"
          @click="!arranging && openDetail(card)"
        >
          <!-- En-tête de la carte -->
          <!-- Titre long (téléphone) : il passe à la ligne, les boutons restent à droite -->
          <q-card-section class="row items-center justify-between no-wrap q-pb-xs">
            <div class="col row items-center no-wrap" style="min-width: 0">
              <q-icon v-if="arranging" name="drag_indicator" size="24px" color="grey-7" class="card-drag q-mr-xs" />
              <q-avatar size="md" :color="getCardTheme(card).bg" :text-color="getCardTheme(card).color" class="q-mr-sm">
                <q-icon :name="card.icon" size="xs" />
              </q-avatar>
              <div class="text-subtitle1 text-weight-bold card-title">{{ cardTitle(card) }}</div>
              <span v-if="isCardLive(card)" class="app-live q-ml-sm">
                {{ t('dashboard.live') }}
                <q-tooltip>{{ t('dashboard.liveHelp') }}</q-tooltip>
              </span>
            </div>
            <div v-if="!arranging" class="col-auto row no-wrap">
            <q-btn
              v-if="card.type === MetricType.WATER_TREND"
              flat
              round
              dense
              :icon="isCollapsed(card) ? 'expand_more' : 'expand_less'"
              color="grey-7"
              :aria-label="isCollapsed(card) ? t('dashboard.trend.expand') : t('dashboard.trend.collapse')"
              @click.stop="toggleCollapsed(card)"
            >
              <q-tooltip>{{ isCollapsed(card) ? t('dashboard.trend.expand') : t('dashboard.trend.collapse') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="hasDetail(card)" flat round dense icon="open_in_full" color="grey-7" :aria-label="t('dashboard.openDetail')" @click.stop="openDetail(card)">
              <q-tooltip>{{ t('dashboard.openDetail') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.edit" flat round dense icon="more_vert" color="grey-6" @click.stop>
              <q-menu auto-close>
                <q-list style="min-width: 120px">
                  <q-item clickable @click="editCard(card)">
                    <q-item-section avatar><q-icon name="edit" size="xs" /></q-item-section>
                    <q-item-section>{{ t('actions.edit') }}</q-item-section>
                  </q-item>
                  <q-item clickable class="text-negative" @click="removeCard(card)">
                    <q-item-section avatar><q-icon name="delete" size="xs" color="negative" /></q-item-section>
                    <q-item-section>{{ t('actions.delete') }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
            </div>
          </q-card-section>

          <!-- Corps de la carte : Rendus selon le type -->
          <q-card-section class="q-pt-xs">

            <!-- Évolution combinée des paramètres d'eau (repliable) -->
            <div v-if="card.type === MetricType.WATER_TREND" v-show="!isCollapsed(card)" @click.stop>
              <div v-if="waterParameterStore.parameters.length === 0" class="text-center text-grey-6 q-py-md">{{ t('dashboard.trend.empty') }}</div>
              <template v-else>
                <div class="row items-center justify-between gap-sm q-mb-md">
                  <div class="text-caption text-grey-6 col-12 col-md gt-xs">{{ t('dashboard.trend.help') }}</div>
                  <q-space class="gt-sm" />
                  <q-btn
                    :outline="!showJournal"
                    :unelevated="showJournal"
                    dense
                    no-caps
                    size="sm"
                    color="blue-grey-7"
                    icon="edit_note"
                    :label="t('journal.chart.show')"
                    class="q-px-sm"
                    @click="showJournal = !showJournal"
                  >
                    <q-tooltip>{{ t('journal.chart.tooltip') }}</q-tooltip>
                  </q-btn>
                  <q-btn-toggle
                    v-model="trendPeriod"
                    dense
                    unelevated
                    toggle-color="primary"
                    color="grey-2"
                    text-color="grey-8"
                    :options="[
                      { label: t('dashboard.trend.period3m'), value: '3m' },
                      { label: t('dashboard.trend.period6m'), value: '6m' },
                      { label: t('dashboard.trend.period1y'), value: '1y' },
                      { label: t('dashboard.trend.periodAll'), value: 'all' },
                    ]"
                  />
                </div>

                <div class="row items-center justify-between q-mb-sm">
                  <div class="text-caption text-weight-medium text-grey-7">
                    {{ t('dashboard.trend.shown', { n: selectedParamIds.size, total: waterParameterStore.parameters.length }) }}
                  </div>
                  <div class="row gap-xs">
                    <q-btn flat dense size="sm" color="amber-9" icon="star" :label="t('dashboard.trend.favorites')" @click="selectTrendParams('favorites')" />
                    <q-btn flat dense size="sm" color="primary" :label="t('dashboard.trend.all')" @click="selectTrendParams('all')" />
                    <q-btn flat dense size="sm" color="grey-7" :label="t('dashboard.trend.none')" @click="selectTrendParams('none')" />
                  </div>
                </div>
                <div class="row q-gutter-sm q-mb-lg">
                  <q-chip
                    v-for="p in sortedTrendParams"
                    :key="p.id"
                    clickable
                    :outline="!selectedParamIds.has(p.id)"
                    :style="selectedParamIds.has(p.id) ? `background-color:${paramColor(p.id)}` : ''"
                    :text-color="selectedParamIds.has(p.id) ? 'white' : 'grey-8'"
                    @click="toggleTrendParam(p.id)"
                  >
                    <q-icon v-if="p.pinned" name="star" size="14px" class="q-mr-xs" />{{ p.name }}
                    <q-tooltip>{{ paramRangeLabel(p.id) }}</q-tooltip>
                  </q-chip>
                </div>

                <v-chart v-if="hasTrendData" :option="trendChartOption" :style="{ height: $q.screen.lt.sm ? '260px' : '340px' }" autoresize />
                <div v-else class="text-center text-grey-6 q-py-md">{{ t('dashboard.trend.empty') }}</div>
              </template>
            </div>

            <!-- TYPE 1 & 2 : Température et Paramètres d'Eau (KH, NO3, PO4...) -->
            <template v-else-if="card.type === MetricType.TEMPERATURE || card.type === MetricType.WATER_PARAM">
              <div class="row items-baseline justify-between">
                <div>
                  <span class="app-value">
                    {{ formatValue(getCardValue(card)) }}
                  </span>
                  <span class="app-value-unit">{{ card.unit }}</span>
                </div>
                <span
                  v-if="isParamInTarget(card) !== null"
                  class="app-tag"
                  :class="isParamInTarget(card) ? 'app-tag--ok' : 'app-tag--warn'"
                >
                  {{ isParamInTarget(card) ? t('dashboard.inTarget') : t('dashboard.outOfTarget') }}
                </span>
              </div>

              <!-- Courbe d'évolution (Sparkline) -->
              <div class="q-mt-sm row items-center justify-between">
                <div class="col-7">
                  <div class="text-caption text-grey-6 q-mb-xs">
                    {{ t('dashboard.periodHelp', { period: t(`dashboard.period.${cardPeriod(card)}`) }) }}
                  </div>
                  <SparklineChart
                    v-if="getCardHistory(card).length > 1"
                    :data="getCardHistory(card)"
                    :color="card.water_parameter_id ? paramColor(card.water_parameter_id) : getCardTheme(card).hexColor"
                    :height="35"
                    :target-min="card.target_min ?? null"
                    :target-max="card.target_max ?? null"
                  />
                </div>
                <div v-if="card.target_min != null || card.target_max != null" class="col-5 text-right text-caption text-grey-6">
                  {{ t('dashboard.target') }}<br>
                  <b class="app-mono">{{ targetLabel(card) }}</b>
                </div>
              </div>
            </template>

            <!-- TYPE 3 : Niveau Binaire Simple -->
            <template v-else-if="card.type === MetricType.BINARY_LEVEL">
              <div class="row items-center justify-between q-py-xs">
                <div class="text-body1 text-weight-medium text-grey-8">{{ t('dashboard.currentState') }}</div>
                <q-chip
                  dense
                  :color="getBinaryStatus(card).color"
                  text-color="white"
                  :icon="getBinaryStatus(card).icon"
                  class="q-px-sm"
                >
                  {{ getBinaryStatus(card).label }}
                </q-chip>
              </div>
              <div class="text-caption text-grey-6 q-mt-xs">
                {{ t('dashboard.lastChange', { when: getSensorLastChange(card.sensor_id) }) }}
              </div>
            </template>

            <!-- Équipement : marche / arrêt et mode, comme sur la page Équipements -->
            <template v-else-if="card.type === MetricType.EQUIPMENT">
              <!-- Plusieurs équipements : une ligne chacun (état, nom, mode, interrupteur) -->
              <q-list v-if="cardEquipmentIds(card).length > 1" dense class="equip-list" @click.stop>
                <q-item v-for="id in cardEquipmentIds(card)" :key="id" class="q-px-none">
                  <template v-if="equipmentStore.getById(id)">
                    <q-item-section avatar class="equip-dot-section">
                      <span class="equip-dot" :class="`bg-${equipmentState(equipmentStore.getById(id)!).color}`">
                        <q-tooltip>{{ equipmentState(equipmentStore.getById(id)!).label }}</q-tooltip>
                      </span>
                    </q-item-section>
                    <q-item-section>
                      <q-item-label class="ellipsis cursor-pointer equip-name" @click="openEquipmentHistory(id)">
                        {{ equipmentStore.getById(id)!.name }}
                        <q-tooltip>{{ t('dashboard.equipment.history') }}</q-tooltip>
                      </q-item-label>
                      <q-item-label v-if="!isEquipmentOnline(equipmentStore.getById(id)!)" caption class="text-grey-6">
                        <q-icon name="cloud_off" size="12px" /> {{ t('dashboard.equipment.offlineHelp') }}
                      </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <div class="row no-wrap items-center gap-xs">
                        <q-btn
                          v-if="isAutomated(id)"
                          outline
                          dense
                          no-caps
                          size="sm"
                          class="q-px-xs"
                          :icon="isEquipmentAuto(equipmentStore.getById(id)!) ? 'autorenew' : 'pan_tool'"
                          :color="isEquipmentAuto(equipmentStore.getById(id)!) ? 'primary' : 'orange-9'"
                          :label="isEquipmentAuto(equipmentStore.getById(id)!) ? t('dashboard.equipment.auto') : t('dashboard.equipment.manual')"
                          :disable="!can.edit || !isEquipmentOnline(equipmentStore.getById(id)!)"
                          @click="toggleEquipmentMode(equipmentStore.getById(id)!)"
                        >
                          <q-tooltip>{{ t('dashboard.equipment.mode', { mode: isEquipmentAuto(equipmentStore.getById(id)!) ? t('dashboard.equipment.auto') : t('dashboard.equipment.manual') }) }}</q-tooltip>
                        </q-btn>
                        <q-toggle
                          :model-value="isEquipmentOn(id)"
                          color="positive"
                          dense
                          :aria-label="equipmentStore.getById(id)!.name"
                          :disable="!can.edit || !isEquipmentOnline(equipmentStore.getById(id)!) || isRuleDriven(equipmentStore.getById(id)!)"
                          @update:model-value="(on: boolean) => setEquipmentStatus(equipmentStore.getById(id)!, on)"
                        >
                          <q-tooltip v-if="!isEquipmentOnline(equipmentStore.getById(id)!)">{{ t('dashboard.equipment.offlineHelp') }}</q-tooltip>
                          <q-tooltip v-else-if="isRuleDriven(equipmentStore.getById(id)!)">{{ t('dashboard.equipment.forceHelp') }}</q-tooltip>
                        </q-toggle>
                      </div>
                    </q-item-section>
                  </template>
                  <q-item-section v-else class="text-grey-6">{{ t('dashboard.equipment.missing') }}</q-item-section>
                </q-item>
              </q-list>
              <!-- Commandes : ne pas ouvrir la vue agrandie en les touchant -->
              <div v-else-if="cardEquipment(card)" @click.stop>
                <div class="row items-center justify-between q-py-xs">
                  <q-chip dense :color="equipmentState(cardEquipment(card)!).color" text-color="white" :icon="equipmentState(cardEquipment(card)!).icon">
                    {{ equipmentState(cardEquipment(card)!).label }}
                  </q-chip>
                  <q-toggle
                    :model-value="isEquipmentOn(cardEquipment(card)!.id)"
                    color="positive"
                    size="lg"
                    :aria-label="card.title"
                    :disable="!can.edit || !isEquipmentOnline(cardEquipment(card)!) || isRuleDriven(cardEquipment(card)!)"
                    @update:model-value="(on: boolean) => setEquipmentStatus(cardEquipment(card)!, on)"
                  >
                    <q-tooltip v-if="!isEquipmentOnline(cardEquipment(card)!)">{{ t('dashboard.equipment.offlineHelp') }}</q-tooltip>
                    <q-tooltip v-else-if="isRuleDriven(cardEquipment(card)!)">{{ t('dashboard.equipment.forceHelp') }}</q-tooltip>
                  </q-toggle>
                </div>
                <!-- Mode : seulement si des règles pilotent l'équipement (sinon sans effet) -->
                <q-btn-toggle
                  v-if="isAutomated(cardEquipment(card)!.id)"
                  :model-value="isEquipmentAuto(cardEquipment(card)!) ? EquipmentMode.AUTO : EquipmentMode.MANUAL"
                  spread
                  dense
                  unelevated
                  toggle-color="primary"
                  color="grey-2"
                  text-color="grey-8"
                  class="q-mt-xs"
                  :disable="!can.edit || !isEquipmentOnline(cardEquipment(card)!)"
                  :options="[
                    { label: t('dashboard.equipment.auto'), value: EquipmentMode.AUTO },
                    { label: t('dashboard.equipment.manual'), value: EquipmentMode.MANUAL },
                  ]"
                  @update:model-value="(mode: EquipmentMode) => setEquipmentMode(cardEquipment(card)!, mode)"
                />
              </div>
              <div v-else class="text-grey-6 q-py-sm">{{ t('dashboard.equipment.missing') }}</div>
            </template>

            <!-- TYPE 4 : Réserve Osmosée (Double Flotteur + Remplissage Osmoseur) -->
            <template v-else-if="card.type === MetricType.RO_RESERVE">
              <div v-if="isEquipmentOn(card.equipment_id)" class="q-pa-sm rounded-borders bg-blue-1 text-blue-9 row items-center justify-between q-mb-sm">
                <div class="row items-center">
                  <q-spinner-dots color="blue" size="1.5em" class="q-mr-sm" />
                  <span class="text-weight-bold">{{ t('dashboard.refilling') }}</span>
                </div>
                <q-chip dense color="blue" text-color="white">{{ t('dashboard.roOn') }}</q-chip>
              </div>

              <div class="row items-center justify-between q-mt-xs">
                <div class="text-body2 text-grey-7">{{ t('dashboard.highLevel') }}</div>
                <q-badge :color="isSensorActive(card.sensor_high_id) ? 'positive' : 'grey-5'">
                  {{ isSensorActive(card.sensor_high_id) ? t('dashboard.reached') : t('dashboard.incomplete') }}
                </q-badge>
              </div>

              <div class="row items-center justify-between q-mt-xs">
                <div class="text-body2 text-grey-7">{{ t('dashboard.lowLevel') }}</div>
                <!-- Flotteur de sécurité : l'eau doit l'atteindre (1) ; à sec (0), la réserve est presque vide -->
                <q-badge v-if="getSensorValue(card.sensor_low_id) === null" color="grey-5">{{ t('sensors.state.waiting') }}</q-badge>
                <q-badge v-else :color="isSensorActive(card.sensor_low_id) ? 'positive' : 'negative'">
                  {{ isSensorActive(card.sensor_low_id) ? t('dashboard.ok') : t('dashboard.lowAlert') }}
                </q-badge>
              </div>
            </template>

            <!-- TYPE 5 : Suivi Osmolateur (Déclenchements & Durée avec Horodatage) -->
            <template v-else-if="card.type === MetricType.OSMOLATOR_EVENTS">
              <div class="row q-col-gutter-xs q-mb-md text-center">
                <div class="col-4">
                  <div class="bg-blue-1 rounded-borders q-pa-xs">
                    <div class="text-caption text-grey-7">{{ t('dashboard.activations') }}</div>
                    <div class="text-subtitle1 text-weight-bolder text-primary">
                      {{ getOsmolateurStats(card.equipment_id).count }}x
                    </div>
                  </div>
                </div>
                <div class="col-4">
                  <div class="bg-blue-1 rounded-borders q-pa-xs">
                    <div class="text-caption text-grey-7">{{ t('dashboard.totalDuration') }}</div>
                    <div class="text-subtitle1 text-weight-bolder text-primary">
                      {{ getOsmolateurStats(card.equipment_id).formattedTotal }}
                    </div>
                  </div>
                </div>
                <div class="col-4">
                  <div class="bg-blue-1 rounded-borders q-pa-xs">
                    <div class="text-caption text-grey-7">{{ t('dashboard.average') }}</div>
                    <div class="text-subtitle1 text-weight-bolder text-primary">
                      {{ getOsmolateurStats(card.equipment_id).avgDuration }}s
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="equipmentActivations(card.equipment_id).length > 0" class="q-mt-xs">
                <div class="text-caption text-grey-6 q-mb-xs row justify-between">
                  <span>{{ t('dashboard.topUpHistory') }}</span>
                  <span>{{ t('dashboard.durationSec') }}</span>
                </div>

                <svg viewBox="0 0 300 80" class="full-width" style="overflow: visible;">
                  <line x1="0" y1="10" x2="300" y2="10" stroke="#eeeeee" stroke-dasharray="2" />
                  <line x1="0" y1="40" x2="300" y2="40" stroke="#eeeeee" stroke-dasharray="2" />
                  <line x1="0" y1="75" x2="300" y2="75" stroke="#bdbdbd" stroke-width="1" />

                  <g v-for="(log, idx) in equipmentActivations(card.equipment_id)" :key="log.id">
                    <rect
                      :x="getBarX(idx, equipmentActivations(card.equipment_id).length)"
                      :y="getBarY(log.duration_seconds || 0, getBarMax(equipmentActivations(card.equipment_id)))"
                      :width="getBarWidth(equipmentActivations(card.equipment_id).length)"
                      :height="getBarHeight(log.duration_seconds || 0, getBarMax(equipmentActivations(card.equipment_id)))"
                      fill="#027BE3"
                      rx="2"
                      class="bar-item"
                    >
                      <q-tooltip anchor="top middle" self="bottom middle" class="bg-dark text-white text-caption">
                        <div class="text-weight-bold">{{ formatDate(log.started_at) }}</div>
                        <div>{{ t('dashboard.injection', { n: log.duration_seconds }) }}</div>
                      </q-tooltip>
                    </rect>
                  </g>
                </svg>

                <div class="row justify-between text-caption text-grey-6 q-mt-xs">
                  <span>{{ formatShortDate(equipmentActivations(card.equipment_id)[0]?.started_at) }}</span>
                  <span>{{ formatShortDate(equipmentActivations(card.equipment_id).at(-1)?.started_at) }}</span>
                </div>
              </div>

              <div v-else class="text-center text-grey-6 q-pa-md">
                {{ t('dashboard.noActivation') }}
              </div>
            </template>

          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Historique d'un capteur -->
    <SensorHistoryDialog
      v-model="sensorHistoryOpen"
      :sensor="sensorHistorySensor"
      :parameter="detailParameter"
      :initial-period="sensorHistoryCard ? cardPeriod(sensorHistoryCard) : null"
      :target-min="sensorHistoryCard?.target_min"
      :target-max="sensorHistoryCard?.target_max"
    />

    <!-- Mises en marche d'un équipement sur une période -->
    <ActivationHistoryDialog
      v-model="activationOpen"
      :equipment-id="activationEquipmentId"
      :title="activationTitle"
      :initial-period="activationPeriod"
    />

    <!-- Ajout / édition d'une carte -->
    <FormDialog
      v-model="addCardDialog"
      icon="dashboard_customize"
      :title="isEditing ? t('dashboard.form.editTitle') : t('dashboard.addCard')"
      :subtitle="t('dashboard.form.subtitle')"
      :submit-label="isEditing ? t('common.save') : t('dashboard.form.add')"
      :loading="savingCard"
      @submit="saveCard"
    >

      <q-input v-if="newCard.type !== MetricType.WATER_TREND" v-model="newCard.title" :label="t('dashboard.form.cardTitle')" outlined dense />

      <q-select
        v-model="newCard.type"
        :options="typeOptions"
        :label="t('dashboard.form.type')"
        outlined
        dense
        emit-value
        map-options
      />

      <!-- Champs spécifiques Temp/Paramètres -->
      <template v-if="newCard.type === MetricType.TEMPERATURE || newCard.type === MetricType.WATER_PARAM">
        <q-btn-toggle
          v-if="newCard.type === MetricType.WATER_PARAM"
          v-model="paramSource"
          spread
          unelevated
          toggle-color="primary"
          color="grey-2"
          text-color="grey-8"
          :options="[
            { label: t('dashboard.form.physicalSensor'), value: 'sensor' },
            { label: t('dashboard.form.manualEntry'), value: 'manual' },
          ]"
          @update:model-value="onParamSourceChange"
        />

        <q-select
          v-if="newCard.type === MetricType.TEMPERATURE || paramSource === 'sensor'"
          v-model="newCard.sensor_id"
          :options="availableSensors"
          :label="t('dashboard.form.sensor')"
          outlined
          dense
          emit-value
          map-options
        />
        <template v-else>
          <q-select
            v-model="newCard.water_parameter_id"
            :options="availableWaterParameters"
            :label="t('dashboard.form.manualParam')"
            outlined
            dense
            emit-value
            map-options
            @update:model-value="onWaterParameterPicked"
          />
          <div v-if="availableWaterParameters.length === 0" class="text-caption text-warning">
            {{ t('dashboard.form.noManualParam') }}
          </div>
        </template>
        <div class="row q-col-gutter-sm">
          <div class="col-6">
            <q-input v-model.number="newCard.target_min" type="number" step="0.1" :label="t('dashboard.form.targetMin')" outlined dense />
          </div>
          <div class="col-6">
            <q-input v-model.number="newCard.target_max" type="number" step="0.1" :label="t('dashboard.form.targetMax')" outlined dense />
          </div>
        </div>
        <q-input v-model="newCard.unit" :label="t('dashboard.form.unit')" outlined dense />
        <q-select
          :model-value="newCard.period ?? defaultPeriod(newCard)"
          :options="periodOptions"
          :label="t('dashboard.form.period')"
          outlined
          dense
          emit-value
          map-options
          @update:model-value="(p: CardPeriod) => (newCard.period = p)"
        />
      </template>

      <!-- Champs spécifiques Réserve Osmosée -->
      <template v-else-if="newCard.type === MetricType.RO_RESERVE">
        <q-select
          v-model="newCard.sensor_high_id"
          :options="availableSensors"
          :label="t('dashboard.form.highSensor')"
          outlined
          dense
          emit-value
          map-options
        />
        <q-select
          v-model="newCard.sensor_low_id"
          :options="availableSensors"
          :label="t('dashboard.form.lowSensor')"
          outlined
          dense
          emit-value
          map-options
        />
        <q-select
          v-model="newCard.equipment_id"
          :options="availableActuators"
          :label="t('dashboard.form.roRelay')"
          outlined
          dense
          emit-value
          map-options
        />
      </template>

      <!-- Champ spécifique Capteur Binaire -->
      <template v-else-if="newCard.type === MetricType.BINARY_LEVEL">
        <q-select
          v-model="newCard.sensor_id"
          :options="availableSensors"
          :label="t('dashboard.form.binarySensor')"
          outlined
          dense
          emit-value
          map-options
        />
        <q-select
          :model-value="newCard.normal_state ?? 'HIGH'"
          :options="[
            { label: t('dashboard.form.normalHigh'), value: 'HIGH' },
            { label: t('dashboard.form.normalLow'), value: 'LOW' },
          ]"
          :label="t('dashboard.form.normalState')"
          :hint="t('dashboard.form.normalStateHint')"
          outlined
          dense
          emit-value
          map-options
          @update:model-value="(s: LevelState) => (newCard.normal_state = s)"
        />
      </template>

      <!-- Champ spécifique Équipement -->
      <template v-else-if="newCard.type === MetricType.EQUIPMENT">
        <q-select
          v-model="newCard.equipment_ids"
          :options="availableActuators"
          :label="t('dashboard.form.equipments')"
          :hint="t('dashboard.form.equipmentsHint')"
          outlined
          dense
          multiple
          use-chips
          emit-value
          map-options
          @update:model-value="onEquipmentsPicked"
        />
      </template>

      <!-- Champ spécifique Osmolateur -->
      <template v-else-if="newCard.type === MetricType.OSMOLATOR_EVENTS">
        <q-select
          v-model="newCard.equipment_id"
          :options="availableOsmolators"
          :label="t('dashboard.form.osmolatorPump')"
          outlined
          dense
          emit-value
          map-options
        />
        <div v-if="availableOsmolators.length === 0" class="text-caption text-warning">
          {{ t('dashboard.form.noOsmolator') }}
        </div>
      </template>

      <q-input v-model="newCard.icon" :label="t('dashboard.form.icon')" outlined dense />

      <!-- Largeur dans la grille (sur grand écran ; toujours pleine largeur sur téléphone) -->
      <q-select
        v-model="newCard.col_span"
        :options="widthOptions"
        :label="t('dashboard.form.width')"
        outlined
        dense
        emit-value
        map-options
      />
    </FormDialog>
  </div>
</template>

<script setup lang="ts">
import { usePermissions } from 'src/composables/usePermissions';
import { ref, computed, onBeforeUnmount, onMounted, watch } from 'vue';
import { date as qdate, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { formatDate as formatDay } from 'src/utils/format';
import { intlLocale } from 'src/i18n/instance';
import {
  MetricType,
  type CardPeriod,
  type DashboardCardConfig,
  type DashboardCardCreate,
  type EquipmentActivation,
  type LevelState,
} from 'src/types/dashboard';
import { EquipmentCategory, EquipmentMode, EquipmentStatus, type Equipment } from 'src/types/equipment';
import { useControllerStore } from 'src/stores/controllerStore';
import { useFaultStore } from 'src/stores/faultStore';
import { useWebSocketStore } from 'src/stores/websocket';
import { useDashboardCardStore } from 'src/stores/dashboardCardStore';
import { useSensorStore } from 'src/stores/sensorStore';
import { useEquipmentStore } from 'src/stores/equipmentStore';
import { useMetricsStore } from 'src/stores/metricsStore';
import { useWaterParameterStore } from 'src/stores/waterParameterStore';
import { parameterColor, type WaterParameterReading } from 'src/types/waterParameter';
import SparklineChart from 'src/components/SparklineChart.vue';
import SensorHistoryDialog from 'src/components/SensorHistoryDialog.vue';
import ActivationHistoryDialog from 'src/components/ActivationHistoryDialog.vue';
import { useEquipmentAutomation } from 'src/composables/useEquipmentAutomation';
import Sortable from 'sortablejs';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import type { EChartsOption, LineSeriesOption } from 'echarts';
import { axisStyle, chartBase, chartColors, dot, escapeHtml } from 'src/utils/chart';
import { journalCategory, type JournalEntry } from 'src/types/journal';
import axios from 'axios';

const props = defineProps({
  aquaId: { type: Number, required: true },
  aquariumName: { type: String, default: '' },
});

const { t } = useI18n();
const { isAutomated } = useEquipmentAutomation();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const wsStore = useWebSocketStore();
const cardStore = useDashboardCardStore();
const sensorStore = useSensorStore();
const equipmentStore = useEquipmentStore();
const metricsStore = useMetricsStore();
const waterParameterStore = useWaterParameterStore();
const controllerStore = useControllerStore();
const faultStore = useFaultStore();

const cards = computed(() => cardStore.cards);

const addCardDialog = ref(false);
const savingCard = ref(false);
const isEditing = ref(false);
const editingCardId = ref<number | null>(null);

// --- Courbes (par carte, sur sa période) et activations (par équipement) ---
const cardHistory = ref<Record<number, number[]>>({});
const lastChangeMap = ref<Record<number, number>>({});
const activationsMap = ref<Record<number, EquipmentActivation[]>>({});

const CARD_PERIOD_DAYS: Record<CardPeriod, number> = { '24h': 1, '7d': 7, '30d': 30, '90d': 90 };
const periodOptions = computed(() =>
  (Object.keys(CARD_PERIOD_DAYS) as CardPeriod[]).map((p) => ({ label: t(`dashboard.period.${p}`), value: p })),
);

// Sans période choisie : 24 h pour un capteur, 90 jours pour un paramètre saisi à la main
function defaultPeriod(card: Partial<DashboardCardConfig>): CardPeriod {
  return card.water_parameter_id ? '90d' : '24h';
}

function cardPeriod(card: DashboardCardConfig): CardPeriod {
  return card.period ?? defaultPeriod(card);
}

async function loadCardHistory(card: DashboardCardConfig) {
  const period = cardPeriod(card);
  if (card.water_parameter_id) {
    const since = Date.now() - CARD_PERIOD_DAYS[period] * 86400_000;
    const readings = await waterParameterStore.fetchReadings(card.water_parameter_id);
    cardHistory.value[card.id] = readings.filter((r) => new Date(r.timestamp).getTime() >= since).map((r) => r.value);
  } else if (card.sensor_id && (card.type === MetricType.TEMPERATURE || card.type === MetricType.WATER_PARAM)) {
    const history = await metricsStore.fetchSensorPeriodHistory(card.sensor_id, period);
    cardHistory.value[card.id] = history.points.map((p) => p.avg);
  }
}

async function loadCardData() {
  const equipmentIds = new Set<number>();
  for (const card of cards.value) {
    if (card.type === MetricType.OSMOLATOR_EVENTS && card.equipment_id) equipmentIds.add(card.equipment_id);
  }
  await Promise.all([
    ...cards.value.map((card) => loadCardHistory(card).catch(() => undefined)),
    ...[...equipmentIds].map(async (id) => {
      activationsMap.value[id] = await metricsStore.fetchEquipmentActivations(id, 20);
    }),
  ]);
}

// --- Graphe combiné : évolution de tous les paramètres d'eau (indépendant
// des cartes configurées), avec sélection de ceux à afficher. Chaque série
// est normalisée sur 0-100% (min/max de son propre historique) pour pouvoir
// comparer des paramètres d'échelles différentes (KH ~ 6-12, NO3 ~ 0-20,
// Ca ~ 380-450...) sur un même axe. La vraie valeur (+ unité) reste
// accessible via le tooltip personnalisé.
const trendHistoryMap = ref<Record<number, WaterParameterReading[]>>({});
const selectedParamIds = ref<Set<number>>(new Set());
const trendPeriod = ref<'3m' | '6m' | '1y' | 'all'>('1y');

// Journal de bord : notes reportées sur la courbe (repères verticaux)
const journalEntries = ref<JournalEntry[]>([]);
const showJournal = ref(true);

async function loadJournal() {
  try {
    journalEntries.value = (await axios.get<JournalEntry[]>('/journal/', { params: { aquarium_id: props.aquaId } })).data;
  } catch {
    journalEntries.value = [];
  }
}

async function loadTrendHistory() {
  await Promise.all([
    ...waterParameterStore.parameters.map(async (p) => {
      trendHistoryMap.value[p.id] = await waterParameterStore.fetchReadings(p.id);
    }),
    loadJournal(),
  ]);
  selectedParamIds.value = new Set(savedTrendSelection() ?? defaultTrendSelection());
}

// Par défaut : les favoris (étoile sur la page Paramètres). Sans favori, les
// 5 paramètres mesurés le plus récemment, pour ne pas afficher 40 courbes.
function defaultTrendSelection(): number[] {
  const favorites = waterParameterStore.parameters.filter((p) => p.pinned).map((p) => p.id);
  if (favorites.length > 0) return favorites;
  return [...waterParameterStore.parameters]
    .filter((p) => p.last_reading_at)
    .sort((a, b) => (b.last_reading_at ?? '').localeCompare(a.last_reading_at ?? ''))
    .slice(0, 5)
    .map((p) => p.id);
}

// Sélection mémorisée par aquarium dans ce navigateur (simple confort d'affichage)
const trendStorageKey = computed(() => `aquasmanager.trend-selection.${props.aquaId}`);

function savedTrendSelection(): number[] | null {
  try {
    const raw = localStorage.getItem(trendStorageKey.value);
    if (!raw) return null;
    const known = new Set(waterParameterStore.parameters.map((p) => p.id));
    const ids = (JSON.parse(raw) as number[]).filter((id) => known.has(id));
    return ids.length > 0 ? ids : null;
  } catch {
    return null;
  }
}

function setTrendSelection(ids: Iterable<number>) {
  selectedParamIds.value = new Set(ids);
  try {
    localStorage.setItem(trendStorageKey.value, JSON.stringify([...selectedParamIds.value]));
  } catch {
    // Stockage indisponible (navigation privée) : la sélection n'est simplement pas retenue
  }
}

function toggleTrendParam(paramId: number) {
  const next = new Set(selectedParamIds.value);
  if (next.has(paramId)) next.delete(paramId);
  else next.add(paramId);
  setTrendSelection(next);
}

function selectTrendParams(mode: 'favorites' | 'all' | 'none') {
  if (mode === 'none') {
    setTrendSelection([]);
  } else if (mode === 'all') {
    setTrendSelection(waterParameterStore.parameters.map((p) => p.id));
  } else {
    // Les favoris redeviennent la sélection par défaut
    setTrendSelection(defaultTrendSelection());
    try {
      localStorage.removeItem(trendStorageKey.value);
    } catch {
      // ignoré
    }
  }
}

// Favoris en premier dans la liste des pastilles
const sortedTrendParams = computed(() =>
  [...waterParameterStore.parameters].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return a.name.localeCompare(b.name);
  }),
);

function paramColor(paramId: number): string {
  return parameterColor(paramId, waterParameterStore.parameters);
}

const MAX_TARGET_BANDS = 2;

const PERIOD_DAYS: Record<'3m' | '6m' | '1y', number> = { '3m': 90, '6m': 182, '1y': 365 };

function periodStartMs(): number {
  if (trendPeriod.value === 'all') return -Infinity;
  return Date.now() - PERIOD_DAYS[trendPeriod.value] * 86400_000;
}

// Sur le graphe combiné, un paramètre dont les relevés sont resserrés sur
// quelques jours s'affiche comme un trait quasi vertical à côté d'un
// paramètre étalé sur plusieurs semaines (chaque série est normalisée
// indépendamment) : ce n'est pas un bug, mais ça surprend. Ce tooltip
// explique en un coup d'œil ce qui est affiché.
function paramRangeLabel(paramId: number): string {
  const param = waterParameterStore.parameters.find((p) => p.id === paramId);
  const fullName = param?.full_name ?? null;
  const prefix = fullName ? `${fullName} — ` : '';

  const startMs = periodStartMs();
  const readings = (trendHistoryMap.value[paramId] ?? []).filter((r) => new Date(r.timestamp).getTime() >= startMs);
  if (readings.length === 0) return `${prefix}${t('dashboard.trend.noReading')}`;
  if (readings.length === 1) {
    return `${prefix}${t('dashboard.trend.oneReading', { date: formatDay(readings[0]!.timestamp) })}`;
  }
  const first = formatDay(readings[0]!.timestamp);
  const last = formatDay(readings[readings.length - 1]!.timestamp);
  return `${prefix}${t('dashboard.trend.readings', { n: readings.length, from: first, to: last })}`;
}

interface TrendPoint {
  x: number;
  y: number;
  raw: number;
  unit: string;
  synthetic?: boolean;
}

interface TargetBand {
  min: number;
  max: number;
}

const trendChartSeries = computed(() => {
  const startMs = periodStartMs();
  const nowMs = Date.now();

  return waterParameterStore.parameters
    .filter((p) => selectedParamIds.value.has(p.id))
    .map((p) => {
      const readings = (trendHistoryMap.value[p.id] ?? []).filter(
        (r) => new Date(r.timestamp).getTime() >= startMs,
      );
      if (readings.length === 0) {
        return { paramId: p.id, name: p.name, data: [] as TrendPoint[], targetBand: null as TargetBand | null };
      }

      const values = readings.map((r) => r.value);
      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = max - min || 1;
      const data: TrendPoint[] = readings.map((r) => ({
        x: new Date(r.timestamp).getTime(),
        y: Number((((r.value - min) / range) * 100).toFixed(1)),
        raw: r.value,
        unit: p.unit ?? '',
      }));

      // Prolonge la dernière valeur connue jusqu'à aujourd'hui : sans ça la
      // ligne s'arrête net à la date du dernier relevé (flagrant pour un
      // paramètre testé rarement, ex: ICP tous les quelques mois).
      const last = data[data.length - 1];
      if (last && nowMs - last.x > 86400_000) {
        data.push({ ...last, x: nowMs, synthetic: true });
      }

      // Cible reportée sur la même échelle normalisée que la série, pour
      // pouvoir l'afficher comme bande repère sur le graphe.
      let targetBand: TargetBand | null = null;
      if (p.target_min != null || p.target_max != null) {
        const bandMin = (((p.target_min ?? min) - min) / range) * 100;
        const bandMax = (((p.target_max ?? max) - min) / range) * 100;
        targetBand = { min: Math.max(0, Math.min(bandMin, bandMax)), max: Math.min(100, Math.max(bandMin, bandMax)) };
      }

      return { paramId: p.id, name: p.name, data, targetBand };
    })
    .filter((s) => s.data.length > 0);
});

const hasTrendData = computed(() => trendChartSeries.value.length > 0);

const trendChartOption = computed<EChartsOption>(() => {
  const dark = $q.dark.isActive;
  const c = chartColors(dark);
  const axis = axisStyle(dark);
  // Au-delà de deux paramètres, les bandes de cible se superposent en un
  // aplat illisible : on ne les trace que pour une lecture ciblée.
  const withBands = trendChartSeries.value.length <= MAX_TARGET_BANDS;
  const startMs = periodStartMs();
  const notes = showJournal.value
    ? journalEntries.value.filter((e) => new Date(e.occurred_at).getTime() >= startMs)
    : [];
  const series: LineSeriesOption[] = trendChartSeries.value.map((s, index) => {
    const color = paramColor(s.paramId);
    return {
      type: 'line',
      name: s.name,
      color,
      // Lignes droites plutôt que lissées : avec peu de relevés espacés
      // irrégulièrement, une courbe lissée inventerait des rebonds.
      lineStyle: { width: 2.5, cap: 'round' },
      symbol: 'circle',
      symbolSize: 7,
      itemStyle: { borderColor: c.markerBorder, borderWidth: 2 },
      emphasis: { scale: 1.4 },
      data: s.data.map((pt) => ({ value: [pt.x, pt.y], raw: pt.raw, unit: pt.unit, synthetic: pt.synthetic ?? false })),
      // Notes du journal : un repère vertical par note (sur la première courbe seulement)
      ...(index === 0 && notes.length
        ? {
            markLine: {
              symbol: ['none', 'none'],
              animation: false,
              label: { show: false },
              emphasis: { label: { show: false }, lineStyle: { width: 3 } },
              data: notes.map((e) => ({
                xAxis: new Date(e.occurred_at).getTime(),
                name: e.text,
                category: e.category,
                lineStyle: { color: journalCategory(e.category).color, type: 'dashed', width: 1.5, opacity: 0.8 },
              })),
            },
          }
        : {}),
      ...(withBands && s.targetBand
        ? {
            markArea: {
              silent: true,
              itemStyle: { color, opacity: 0.1 },
              data: [[{ yAxis: s.targetBand.min }, { yAxis: s.targetBand.max }]],
            },
          }
        : {}),
    };
  });
  return {
    ...chartBase(dark),
    grid: { left: 16, right: 24, top: 36, bottom: 8, containLabel: true },
    // Zoom : molette / pincement, ou sélection avec l'outil loupe ; bouton pour revenir
    toolbox: { right: 8, top: 0, iconStyle: { borderColor: c.text }, feature: { dataZoom: { yAxisIndex: 'none', title: { zoom: t('chart.zoom'), back: t('chart.zoomBack') } }, restore: { title: t('chart.reset') } } },
    dataZoom: [{ type: 'inside', xAxisIndex: 0 }],
    xAxis: {
      type: 'time',
      ...axis,
      splitLine: { show: false },
      axisLabel: { ...axis.axisLabel, hideOverlap: true, formatter: (v: number) => qdate.formatDate(v, 'DD/MM') },
    },
    yAxis: { type: 'value', show: false, min: 0, max: 100 },
    legend: { show: false },
    tooltip: {
      ...chartBase(dark).tooltip,
      trigger: 'item',
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params;
        if (p?.componentType === 'markLine') {
          const note = p.data as { xAxis: number; name: string; category: string };
          const meta = journalCategory(note.category);
          return `${qdate.formatDate(note.xAxis, 'DD/MM/YYYY HH:mm')}<br>${dot(meta.color)}<b>${escapeHtml(t(`journal.categories.${meta.key}`))}</b><br>${escapeHtml(note.name)}`;
        }
        const data = p?.data as { value: [number, number]; raw: number; unit: string; synthetic: boolean } | undefined;
        if (!p || !data) return '';
        const note = data.synthetic ? ` <span style="opacity:.6">${escapeHtml(t('dashboard.trend.lastKnown'))}</span>` : '';
        return `${qdate.formatDate(data.value[0], 'DD/MM/YYYY')}<br>${dot(p.color)}<b>${escapeHtml(p.seriesName)}</b> : ${escapeHtml(data.raw)} ${escapeHtml(data.unit)}${note}`;
      },
    },
    series,
  };
});

onMounted(async () => {
  await Promise.all([
    cardStore.fetchCards(props.aquaId),
    sensorStore.fetch(),
    equipmentStore.fetch(),
    waterParameterStore.fetch(props.aquaId),
  ]);
  await Promise.all([loadCardData(), loadTrendHistory()]);
});

// Ajoute la nouvelle valeur temps réel à l'historique local (sparkline) et
// note l'instant du changement, sans attendre un nouveau fetch.
watch(
  () => ({ ...wsStore.sensorsState }),
  (state, oldState) => {
    for (const [key, value] of Object.entries(state)) {
      const id = Number(key);
      if (oldState?.[id] === value) continue;
      lastChangeMap.value[id] = Date.now();
      // Pas de mesure (sonde muette) : rien à ajouter aux courbes
      if (value === null) continue;
      // Nouvelle valeur ajoutée au bout des courbes des cartes de ce capteur
      for (const card of cards.value) {
        if (card.sensor_id !== id || card.water_parameter_id || !(card.id in cardHistory.value)) continue;
        cardHistory.value[card.id] = [...(cardHistory.value[card.id] ?? []), value];
      }
    }
  },
  { deep: true },
);

// Fin d'un complément d'osmolateur (passage à OFF) : l'activation vient d'être
// refermée côté serveur, on recharge son historique pour la carte.
watch(
  () => ({ ...wsStore.equipmentsState }),
  (state, oldState) => {
    for (const [key, value] of Object.entries(state)) {
      const id = Number(key);
      if (!(id in activationsMap.value) || oldState?.[id] === value) continue;
      if (String(value).toUpperCase() !== 'OFF') continue;
      void metricsStore.fetchEquipmentActivations(id, 20).then((logs) => {
        activationsMap.value[id] = logs;
      });
    }
  },
);

// --- Sélecteurs pour la modale d'ajout/édition ---
const availableSensors = computed(() =>
  sensorStore.getByAquariumId(props.aquaId).map((s) => ({ label: `${s.name} (${s.type})`, value: s.id })),
);

const availableActuators = computed(() =>
  equipmentStore.getByAquariumId(props.aquaId).map((e) => ({ label: e.name, value: e.id })),
);

const availableOsmolators = computed(() =>
  equipmentStore
    .getByAquariumId(props.aquaId)
    .filter((e) => e.category === EquipmentCategory.OSMOLATOR)
    .map((e) => ({ label: e.name, value: e.id })),
);

const availableWaterParameters = computed(() =>
  waterParameterStore.parameters.map((p) => ({ label: `${p.name}${p.unit ? ` (${p.unit})` : ''}`, value: p.id })),
);

// Source des données pour une carte water_param : capteur physique ou
// paramètre saisi manuellement (pas de sensor_id possible dans ce cas).
const paramSource = ref<'sensor' | 'manual'>('sensor');

function onParamSourceChange(mode: 'sensor' | 'manual') {
  if (mode === 'sensor') {
    newCard.value.water_parameter_id = null;
  } else {
    newCard.value.sensor_id = null;
  }
}

function onWaterParameterPicked(paramId: number) {
  const param = waterParameterStore.parameters.find((p) => p.id === paramId);
  if (!param) return;
  if (!newCard.value.title) newCard.value.title = param.name;
  if (!newCard.value.unit) newCard.value.unit = param.unit ?? null;
  if (newCard.value.target_min == null) newCard.value.target_min = param.target_min ?? null;
  if (newCard.value.target_max == null) newCard.value.target_max = param.target_max ?? null;
}

const newCard = ref<Partial<DashboardCardConfig>>({
  title: '',
  type: MetricType.TEMPERATURE,
  icon: 'sensors',
});

// Icône proposée selon le type de carte (tant que l'utilisateur ne l'a pas changée)
const TYPE_ICONS: Record<MetricType, string> = {
  [MetricType.TEMPERATURE]: 'thermostat',
  [MetricType.WATER_PARAM]: 'science',
  [MetricType.RO_RESERVE]: 'water',
  [MetricType.BINARY_LEVEL]: 'water',
  [MetricType.OSMOLATOR_EVENTS]: 'water_drop',
  [MetricType.EQUIPMENT]: 'power',
  [MetricType.WATER_TREND]: 'show_chart',
};
watch(
  () => newCard.value.type,
  (type, previous) => {
    if (!type || isEditing.value) return;
    const icon = newCard.value.icon;
    if (!icon || icon === 'sensors' || (previous && icon === TYPE_ICONS[previous])) newCard.value.icon = TYPE_ICONS[type];
    if (!previous || newCard.value.col_span === defaultColSpan(previous)) newCard.value.col_span = defaultColSpan(type);
  },
);

// Titre proposé : le nom de l'équipement, ou « Équipements » s'il y en a plusieurs
function onEquipmentsPicked(ids: number[]) {
  const names = ids.map((id) => equipmentStore.getById(id)?.name).filter((n): n is string => !!n);
  const title = newCard.value.title ?? '';
  const auto = !title || title === t('dashboard.equipment.multiTitle') || names.includes(title) || equipmentNames.value.includes(title);
  if (auto) newCard.value.title = ids.length > 1 ? t('dashboard.equipment.multiTitle') : (names[0] ?? '');
}
const equipmentNames = computed(() => equipmentStore.equipments.map((e) => e.name));

const typeOptions = computed(() => [
  { label: t('dashboard.types.temperature'), value: MetricType.TEMPERATURE },
  { label: t('dashboard.types.waterParam'), value: MetricType.WATER_PARAM },
  { label: t('dashboard.types.roReserve'), value: MetricType.RO_RESERVE },
  { label: t('dashboard.types.binaryLevel'), value: MetricType.BINARY_LEVEL },
  { label: t('dashboard.types.osmolatorEvents'), value: MetricType.OSMOLATOR_EVENTS },
  { label: t('dashboard.types.equipment'), value: MetricType.EQUIPMENT },
  // Une seule par aquarium : proposée seulement si elle a été supprimée (ou en modification)
  ...(isEditing.value && newCard.value.type === MetricType.WATER_TREND) || !cards.value.some((c) => c.type === MetricType.WATER_TREND)
    ? [{ label: t('dashboard.types.waterTrend'), value: MetricType.WATER_TREND }]
    : [],
]);

// --- Helpers Temps Réel ---
function getSensorValue(sensorId?: number | null): number | null {
  if (!sensorId) return null;
  const live = wsStore.sensorsState[sensorId];
  if (live !== undefined) return live; // null : la sonde ne répond plus
  const sensor = sensorStore.getById(sensorId);
  return sensor?.last_value != null ? Number(sensor.last_value) : null;
}

function formatValue(value: number | null): string {
  // Au plus 2 décimales (un calcul ou une conversion peut en laisser 15)
  return value === null ? '--' : String(Math.round(value * 100) / 100);
}

// Carte water_param : valeur/historique viennent soit d'un capteur physique
// (sensor_id), soit d'un paramètre saisi manuellement (water_parameter_id).
function getCardValue(card: DashboardCardConfig): number | null {
  if (card.water_parameter_id) {
    return waterParameterStore.parameters.find((p) => p.id === card.water_parameter_id)?.last_value ?? null;
  }
  return getSensorValue(card.sensor_id);
}

function getCardHistory(card: DashboardCardConfig): number[] {
  return cardHistory.value[card.id] ?? [];
}

// "En direct" = la carte est branchée sur un capteur physique et on a reçu
// au moins une mise à jour websocket pour lui cette session (donc le flux
// MQTT arrive bien), par opposition à un paramètre saisi manuellement ou
// une dernière valeur simplement relue en base au chargement.
function isCardLive(card: DashboardCardConfig): boolean {
  if (!card.sensor_id) return false;
  return wsStore.sensorsState[card.sensor_id] !== undefined;
}

function equipmentActivations(equipmentId?: number | null): EquipmentActivation[] {
  if (!equipmentId) return [];
  return activationsMap.value[equipmentId] ?? [];
}

function isSensorActive(sensorId?: number | null): boolean {
  const val = getSensorValue(sensorId);
  return val !== null && val >= 1;
}

function getEquipmentStatus(equipmentId?: number | null): string {
  if (!equipmentId) return 'OFF';
  const live = wsStore.equipmentsState[equipmentId];
  if (live !== undefined) return String(live).toUpperCase();
  return equipmentStore.getById(equipmentId)?.status ?? 'OFF';
}

function isEquipmentOn(equipmentId?: number | null): boolean {
  return getEquipmentStatus(equipmentId) === 'ON';
}

// null = pas de valeur ou pas de cible configurée : on ne peut pas se
// prononcer (ne pas afficher "Optimal" par défaut, ce serait mensonger).
function isParamInTarget(card: DashboardCardConfig): boolean | null {
  const val = getCardValue(card);
  if (val === null) return null;
  if (card.target_min == null && card.target_max == null) return null;
  const min = card.target_min ?? -Infinity;
  const max = card.target_max ?? Infinity;
  return val >= min && val <= max;
}

// Cible d'une carte : « 7 – 9 dKH », « ≥ 7 dKH » ou « ≤ 9 dKH »
function targetLabel(card: DashboardCardConfig): string {
  const unit = card.unit ? ` ${card.unit}` : '';
  if (card.target_min != null && card.target_max != null) return `${card.target_min} – ${card.target_max}${unit}`;
  if (card.target_min != null) return `≥ ${card.target_min}${unit}`;
  return `≤ ${card.target_max}${unit}`;
}

function getSensorLastChange(sensorId?: number | null): string {
  if (!sensorId) return 'N/A';
  const ts = lastChangeMap.value[sensorId];
  if (!ts) return t('dashboard.unknown');
  const diffMin = Math.round((Date.now() - ts) / 60000);
  if (diffMin < 1) return t('dashboard.justNow');
  if (diffMin < 60) return t('dashboard.minutesAgo', { n: diffMin });
  return t('dashboard.hoursAgo', { n: Math.round(diffMin / 60) });
}

// Niveau logique (inversion du flotteur déjà appliquée par l'API), vert quand il
// correspond à l'état normal choisi sur la carte
function getBinaryStatus(card: DashboardCardConfig) {
  if (getSensorValue(card.sensor_id) === null) {
    return { label: t('sensors.state.waiting'), color: 'grey-6', icon: 'hourglass_empty' };
  }
  const high = isSensorActive(card.sensor_id);
  const normal = card.normal_state ?? legacyNormalState(card);
  const ok = (high ? 'HIGH' : 'LOW') === normal;
  return {
    label: high ? t('dashboard.binary.high') : t('dashboard.binary.low'),
    color: ok ? 'positive' : 'warning',
    icon: ok ? 'check_circle' : 'warning',
  };
}

// Cartes créées avant le choix de l'état normal : un titre de trop-plein
// (« trop-haut », « alerte », « overflow »…) voulait dire « bas = normal »
function legacyNormalState(card: DashboardCardConfig): LevelState {
  const title = card.title.toLowerCase();
  return ['trop-haut', 'alerte', 'alert', 'overflow'].some((word) => title.includes(word)) ? 'LOW' : 'HIGH';
}

// --- Carte équipement ---
// Un ou plusieurs équipements (equipment_ids), ou l'ancien champ equipment_id seul
function cardEquipmentIds(card: DashboardCardConfig): number[] {
  if (card.equipment_ids?.length) return card.equipment_ids;
  return card.equipment_id ? [card.equipment_id] : [];
}

function cardEquipment(card: DashboardCardConfig): Equipment | undefined {
  const id = cardEquipmentIds(card)[0];
  return id ? equipmentStore.getById(id) : undefined;
}

// Interrupteur réservé aux règles : équipement piloté par des règles et en AUTO
function isRuleDriven(equipment: Equipment): boolean {
  return isAutomated(equipment.id) && isEquipmentAuto(equipment);
}

function toggleEquipmentMode(equipment: Equipment) {
  void setEquipmentMode(equipment, isEquipmentAuto(equipment) ? EquipmentMode.MANUAL : EquipmentMode.AUTO);
}

// --- Évolution des paramètres : titre traduit, repliable (mémorisé sur l'appareil) ---
const COLLAPSED_KEY = 'aquas-dashboard-collapsed';
function readCollapsed(): number[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(COLLAPSED_KEY) ?? '[]');
    return Array.isArray(value) ? value.filter((v): v is number => typeof v === 'number') : [];
  } catch {
    return [];
  }
}
const collapsedIds = ref<Set<number>>(new Set(readCollapsed()));

function isCollapsed(card: DashboardCardConfig): boolean {
  return collapsedIds.value.has(card.id);
}

function toggleCollapsed(card: DashboardCardConfig) {
  const next = new Set(collapsedIds.value);
  if (next.has(card.id)) next.delete(card.id);
  else next.add(card.id);
  collapsedIds.value = next;
  try {
    localStorage.setItem(COLLAPSED_KEY, JSON.stringify([...next]));
  } catch {
    // stockage indisponible (navigation privée) : repli pour cette visite seulement
  }
}

function cardTitle(card: DashboardCardConfig): string {
  return card.type === MetricType.WATER_TREND ? t('dashboard.trend.title') : card.title;
}

// Pleine largeur sur téléphone ; les grandes cartes aussi sur tablette
function cardColClass(card: DashboardCardConfig): string {
  const span = card.col_span || 4;
  return `col-12 col-sm-${span >= 8 ? 12 : 6} col-md-${span}`;
}

const widthOptions = computed(() => [
  { label: t('dashboard.form.widths.small'), value: 4 },
  { label: t('dashboard.form.widths.medium'), value: 6 },
  { label: t('dashboard.form.widths.large'), value: 8 },
  { label: t('dashboard.form.widths.full'), value: 12 },
]);

function defaultColSpan(type?: MetricType): number {
  if (type === MetricType.WATER_TREND) return 12;
  return type === MetricType.RO_RESERVE ? 8 : 4;
}

function isEquipmentOnline(equipment: Equipment): boolean {
  const controller = controllerStore.controllers.find((c) => c.id === equipment.controller_id);
  if (!controller?.technical_name) return false;
  return (wsStore.controllersState[controller.technical_name] ?? controller.status) === 'ONLINE';
}

function isEquipmentAuto(equipment: Equipment): boolean {
  return equipment.mode == null || String(equipment.mode).toUpperCase() === String(EquipmentMode.AUTO);
}

function equipmentState(equipment: Equipment) {
  if (!isEquipmentOnline(equipment)) return { label: t('equipments.state.offline'), color: 'grey-6', icon: 'cloud_off' };
  if (faultStore.openFaults.some((f) => f.equipment_id === equipment.id)) {
    return { label: t('equipments.state.fault'), color: 'negative', icon: 'report_problem' };
  }
  return isEquipmentOn(equipment.id)
    ? { label: t('equipments.state.on'), color: 'positive', icon: 'power' }
    : { label: t('equipments.state.off'), color: 'grey-7', icon: 'power_off' };
}

async function setEquipmentStatus(equipment: Equipment, on: boolean) {
  const status = on ? EquipmentStatus.ON : EquipmentStatus.OFF;
  const previous = equipment.status;
  equipment.status = status;
  wsStore.equipmentsState[equipment.id] = status;
  try {
    await equipmentStore.status({ id: equipment.id, status });
  } catch (err) {
    equipment.status = previous;
    wsStore.equipmentsState[equipment.id] = previous;
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.notify.commandFailed')) });
  }
}

async function setEquipmentMode(equipment: Equipment, mode: EquipmentMode) {
  const previous = equipment.mode;
  equipment.mode = mode;
  try {
    await equipmentStore.mode({ id: equipment.id, mode });
  } catch (err) {
    equipment.mode = previous;
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.notify.modeFailed')) });
  }
}

function getCardTheme(card: DashboardCardConfig) {
  switch (card.type) {
    case MetricType.TEMPERATURE:
      return { bg: 'red-1', color: 'negative', hexColor: '#C10015' };
    case MetricType.WATER_PARAM:
      return { bg: 'teal-1', color: 'teal', hexColor: '#009688' };
    case MetricType.RO_RESERVE:
      return { bg: 'blue-1', color: 'primary', hexColor: '#027BE3' };
    case MetricType.OSMOLATOR_EVENTS:
      return { bg: 'cyan-1', color: 'cyan-9', hexColor: '#00b4d8' };
    case MetricType.EQUIPMENT:
      return { bg: 'green-1', color: 'positive', hexColor: '#21ba45' };
    case MetricType.WATER_TREND:
      return { bg: 'indigo-1', color: 'indigo-7', hexColor: '#3949ab' };
    default:
      return { bg: 'grey-2', color: 'grey-8', hexColor: '#757575' };
  }
}

// --- Helpers Carte Osmolateur ---
function getOsmolateurStats(equipmentId?: number | null) {
  const logs = equipmentActivations(equipmentId);
  if (logs.length === 0) {
    return { count: 0, totalDuration: 0, avgDuration: 0, formattedTotal: '0s' };
  }
  const count = logs.length;
  const totalDuration = logs.reduce((acc, log) => acc + (log.duration_seconds || 0), 0);
  const avgDuration = Math.round(totalDuration / count);

  const mins = Math.floor(totalDuration / 60);
  const secs = totalDuration % 60;
  const formattedTotal = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;

  return { count, totalDuration, avgDuration, formattedTotal };
}

function getBarMax(logs: EquipmentActivation[]): number {
  const max = Math.max(...logs.map((l) => l.duration_seconds || 0), 10);
  return max * 1.15;
}

function getBarWidth(totalLogs: number): number {
  return Math.max(6, Math.min(18, Math.floor(250 / totalLogs) - 4));
}

function getBarX(index: number, totalLogs: number): number {
  if (totalLogs === 1) return 140;
  const step = 270 / (totalLogs - 1);
  return index * step + 5;
}

function getBarHeight(duration: number, max: number): number {
  return Math.max(4, (duration / max) * 65);
}

function getBarY(duration: number, max: number): number {
  return 75 - getBarHeight(duration, max);
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleString(intlLocale(), {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatShortDate(dateStr?: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleString(intlLocale(), {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// --- Historique détaillé d'un capteur ---
const sensorHistoryOpen = ref(false);
const sensorHistoryCard = ref<DashboardCardConfig | null>(null);
const sensorHistorySensor = computed(() => {
  const id = sensorHistoryCard.value ? historySensorId(sensorHistoryCard.value) : null;
  return id ? sensorStore.getById(id) ?? null : null;
});

// Capteur dont on peut afficher l'historique (pas pour un paramètre saisi à la main)
function historySensorId(card: DashboardCardConfig): number | null {
  if (card.type === MetricType.TEMPERATURE || card.type === MetricType.WATER_PARAM || card.type === MetricType.BINARY_LEVEL) {
    return card.water_parameter_id ? null : card.sensor_id ?? null;
  }
  return null;
}

// --- Vue agrandie d'une carte : historique sur une période, avec zoom ---
const detailParameter = computed(() => {
  const id = sensorHistoryCard.value?.water_parameter_id;
  return id ? waterParameterStore.parameters.find((p) => p.id === id) ?? null : null;
});
const activationOpen = ref(false);
const activationEquipmentId = ref<number | null>(null);
const activationTitle = ref<string | undefined>();
const activationPeriod = ref<string | null | undefined>();

// Carte équipement à plusieurs lignes : l'historique s'ouvre par le nom de chaque ligne
function hasActivations(card: DashboardCardConfig): boolean {
  if (card.type === MetricType.EQUIPMENT) return cardEquipmentIds(card).length === 1;
  return !!card.equipment_id && card.type === MetricType.OSMOLATOR_EVENTS;
}

function openEquipmentHistory(equipmentId: number, card?: DashboardCardConfig) {
  activationEquipmentId.value = equipmentId;
  activationTitle.value = card ? card.title : equipmentStore.getById(equipmentId)?.name;
  activationPeriod.value = card?.period;
  activationOpen.value = true;
}

function hasDetail(card: DashboardCardConfig): boolean {
  return !!historySensorId(card) || !!card.water_parameter_id || hasActivations(card);
}

function openDetail(card: DashboardCardConfig) {
  if (hasActivations(card)) {
    openEquipmentHistory(card.equipment_id ?? cardEquipmentIds(card)[0]!, card);
  } else if (historySensorId(card) || card.water_parameter_id) {
    sensorHistoryCard.value = card;
    sensorHistoryOpen.value = true;
  }
}

// --- Réorganisation par glisser-déposer (poignée, souris ou doigt) ---
const arranging = ref(false);
const gridEl = ref<HTMLElement | null>(null);
let sortable: Sortable | null = null;

watch([arranging, gridEl], ([on, el]) => {
  sortable?.destroy();
  sortable = null;
  if (on && el) {
    sortable = Sortable.create(el, { handle: '.card-drag', animation: 150, forceFallback: true, fallbackTolerance: 3, ghostClass: 'dash-card--ghost', onEnd: onDragEnd });
  }
});
onBeforeUnmount(() => sortable?.destroy());

function onDragEnd(evt: Sortable.SortableEvent) {
  const { oldIndex, newIndex, item, from } = evt;
  if (oldIndex == null || newIndex == null || oldIndex === newIndex) return;
  // Sortable a déplacé l'élément dans la page : on le remet en place et Vue
  // réordonne la grille d'après les données
  from.removeChild(item);
  from.insertBefore(item, from.children[oldIndex] ?? null);
  const ids = cards.value.map((c) => c.id);
  const [moved] = ids.splice(oldIndex, 1);
  ids.splice(newIndex, 0, moved!);
  cardStore.reorderCards(props.aquaId, ids).catch((err: unknown) => {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('dashboard.arrangeFailed')) });
    void cardStore.fetchCards(props.aquaId);
  });
}

// --- Actions Modale ---
function openAddCardDialog() {
  isEditing.value = false;
  editingCardId.value = null;
  paramSource.value = 'sensor';
  newCard.value = {
    title: '',
    type: MetricType.TEMPERATURE,
    icon: 'sensors',
    unit: '°C',
    col_span: 4,
  };
  addCardDialog.value = true;
}

function cardValidationError(): string | null {
  const card = newCard.value;
  if (card.type === MetricType.WATER_TREND) return null;
  if (!card.title?.trim()) return t('dashboard.errors.title');
  if (card.type === MetricType.TEMPERATURE && !card.sensor_id) return t('dashboard.errors.tempSensor');
  if (card.type === MetricType.WATER_PARAM && !card.sensor_id && !card.water_parameter_id) {
    return paramSource.value === 'manual' ? t('dashboard.errors.param') : t('dashboard.errors.sensor');
  }
  if (card.type === MetricType.BINARY_LEVEL && !card.sensor_id) return t('dashboard.errors.levelSensor');
  if (card.type === MetricType.OSMOLATOR_EVENTS && !card.equipment_id) return t('dashboard.errors.osmolator');
  if (card.type === MetricType.RO_RESERVE && !card.sensor_high_id && !card.sensor_low_id) {
    return t('dashboard.errors.reserve');
  }
  if (card.type === MetricType.EQUIPMENT && !card.equipment_ids?.length) return t('dashboard.errors.equipment');
  return null;
}

async function saveCard() {
  const error = cardValidationError();
  // Évolution des paramètres : titre affiché traduit, valeur stockée technique
  if (newCard.value.type === MetricType.WATER_TREND) newCard.value.title = 'water_trend';
  if (error || !newCard.value.title || !newCard.value.type) {
    $q.notify({ type: 'warning', message: error ?? t('dashboard.errors.incomplete') });
    return;
  }
  // Un seul équipement : champ equipment_id (carte grand format) ; plusieurs : equipment_ids
  const ids = newCard.value.equipment_ids ?? [];
  const equipment =
    newCard.value.type === MetricType.EQUIPMENT
      ? { equipment_id: ids.length === 1 ? ids[0]! : null, equipment_ids: ids.length > 1 ? ids : null }
      : { equipment_id: newCard.value.equipment_id, equipment_ids: null };

  savingCard.value = true;
  try {
    if (isEditing.value && editingCardId.value !== null) {
      await cardStore.updateCard(editingCardId.value, {
        title: newCard.value.title,
        type: newCard.value.type,
        icon: newCard.value.icon || 'sensors',
        col_span: newCard.value.col_span || defaultColSpan(newCard.value.type),
        unit: newCard.value.unit,
        target_min: newCard.value.target_min,
        target_max: newCard.value.target_max,
        sensor_id: newCard.value.sensor_id,
        sensor_high_id: newCard.value.sensor_high_id,
        sensor_low_id: newCard.value.sensor_low_id,
        ...equipment,
        water_parameter_id: newCard.value.water_parameter_id,
        period: newCard.value.period ?? null,
        normal_state: newCard.value.normal_state ?? null,
      });
    } else {
      const cardToSave: DashboardCardCreate = {
        aquarium_id: props.aquaId,
        title: newCard.value.title,
        type: newCard.value.type,
        icon: newCard.value.icon || 'sensors',
        col_span: newCard.value.col_span || defaultColSpan(newCard.value.type),
        sensor_id: newCard.value.sensor_id,
        sensor_high_id: newCard.value.sensor_high_id,
        sensor_low_id: newCard.value.sensor_low_id,
        ...equipment,
        water_parameter_id: newCard.value.water_parameter_id,
        period: newCard.value.period ?? null,
        normal_state: newCard.value.normal_state ?? null,
        unit: newCard.value.unit,
        target_min: newCard.value.target_min,
        target_max: newCard.value.target_max,
      };
      await cardStore.createCard(cardToSave);
    }

    addCardDialog.value = false;
    await loadCardData();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('dashboard.errors.saveFailed')) });
  } finally {
    savingCard.value = false;
  }
}

function removeCard(card: DashboardCardConfig) {
  confirmRemove(t('dashboard.item', { name: cardTitle(card) }), () => cardStore.deleteCard(card.id), {
    message: t('dashboard.deleteMessage', { name: cardTitle(card) }),
  });
}

function editCard(card: DashboardCardConfig) {
  isEditing.value = true;
  editingCardId.value = card.id;
  paramSource.value = card.water_parameter_id ? 'manual' : 'sensor';
  newCard.value = { ...card, equipment_ids: [...cardEquipmentIds(card)], col_span: card.col_span || defaultColSpan(card.type) };
  addCardDialog.value = true;
}
</script>

<style scoped>
.equip-list .q-item {
  min-height: 40px;
}

.equip-dot-section {
  min-width: 20px;
  padding-right: 8px;
}

.equip-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.equip-name:hover {
  text-decoration: underline;
}

.dash-card--clickable {
  cursor: pointer;
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}

.dash-card--clickable:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  transform: translateY(-1px);
}

.dash-card--arranging {
  border-style: dashed;
}

.card-drag {
  cursor: grab;
  touch-action: none;
}

:deep(.dash-card--ghost) {
  opacity: 0.35;
}

.bar-item {
  transition: fill 0.2s ease, opacity 0.2s ease;
  cursor: pointer;
}

.live-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #fff;
  animation: live-pulse 2s ease-in-out infinite;
}

@keyframes live-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.bar-item:hover {
  fill: #00b0ff;
  opacity: 0.85;
}

.card-title {
  min-width: 0;
  line-height: 1.3;
  overflow-wrap: anywhere;
}
</style>
