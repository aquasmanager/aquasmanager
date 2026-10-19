<template>
  <q-page class="app-page">
    <PageHeader icon="content_cut" :title="t('frags.title')" :subtitle="t('frags.subtitle')">
      <template #actions>
        <q-btn v-if="canScan && can.bourse" outline color="primary" icon="qr_code_scanner" :label="t('frags.scan')" @click="scannerOpen = true" />
        <!-- Étiquettes QR et scan : outils de vente en bourse (licence) -->
        <q-btn v-if="can.bourse" outline color="primary" icon="qr_code_2" :label="t('frags.labels')" @click="labelsDialog = true" />
        <q-btn outline color="primary" icon="query_stats" :label="t('frags.stats')" @click="openStats" />
        <!-- Vente (vitrine, cessions) : licence « bourse » -->
        <q-btn v-if="can.sell" outline color="primary" icon="storefront" :label="t('frags.showcase')" @click="showcaseOpen = true">
          <q-badge v-if="newReservations" color="negative" floating rounded>{{ newReservations }}</q-badge>
        </q-btn>
        <q-btn v-if="can.sell" outline color="primary" icon="description" :label="t('frags.transfers')" to="/transfers" />
        <q-btn v-if="can.frags" unelevated color="primary" icon="add" :label="t('frags.new')" @click="openCreate()" />
      </template>
    </PageHeader>

    <div class="row items-center gap-sm q-mb-md">
      <!-- Téléphone : les statuts défilent sur une ligne au lieu de déborder de l'écran -->
      <div class="status-scroll">
        <q-btn-toggle
          v-model="statusFilter"
          unelevated
          no-caps
          no-wrap
          toggle-color="primary"
          color="grey-2"
          text-color="grey-8"
          :options="statusOptions"
        />
      </div>
      <AppInput v-model="search" icon="search" :placeholder="t('frags.search')" clearable class="app-search" style="width: 280px; max-width: 100%" />
      <!-- Où se trouvent les boutures -->
      <q-select
        v-model="aquariumFilter"
        :options="aquariumFilterOptions"
        emit-value
        map-options
        dense
        outlined
        options-dense
        :label="t('frags.tank')"
        class="aquarium-filter"
      >
        <template #prepend><q-icon name="water" /></template>
      </q-select>
    </div>

    <div v-if="loading" class="text-center q-py-xl"><q-spinner color="primary" size="3em" /></div>

    <EmptyState
      v-else-if="frags.length === 0"
      icon="content_cut"
      :title="t('frags.emptyTitle')"
      :message="t('frags.emptyMessage')"
    >
      <q-btn v-if="can.frags" unelevated color="primary" icon="add" :label="t('frags.new')" @click="openCreate()" />
    </EmptyState>

    <EmptyState v-else-if="filtered.length === 0" icon="search_off" :title="t('frags.noMatch')" />

    <div v-else class="row q-col-gutter-md">
      <div v-for="frag in filtered" :key="frag.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
        <q-card
          :id="`frag-${frag.id}`"
          flat
          bordered
          class="full-height column no-wrap overflow-hidden frag-card"
          :class="{ 'frag-card--selected': selected.has(frag.id), 'frag-card--highlight': highlighted === frag.id }"
        >
          <q-img :src="mainPhotoUrl(PhotoEntityType.frags, frag.id, imageTimestamp)" :ratio="16 / 10">
            <div class="absolute-top frag-card__overlay row items-start justify-between no-wrap q-pa-sm">
              <q-checkbox
                v-if="frag.quantity > 0 && can.frags"
                :model-value="selected.has(frag.id)"
                dark
                dense
                color="white"
                keep-color
                @update:model-value="toggle(frag)"
              />
              <span v-else />
              <q-badge :color="FRAG_STATUS[frag.status].color" class="text-weight-bold q-px-sm q-py-xs">
                {{ t(`frags.status.${frag.status}`) }}
              </q-badge>
            </div>
            <div class="absolute-bottom frag-card__ref text-caption text-weight-bold">{{ frag.reference }}</div>
          </q-img>

          <q-card-section class="col q-py-sm">
            <div class="text-subtitle1 text-weight-bold ellipsis">{{ frag.name }}</div>
            <div v-if="frag.scientific_name" class="text-caption text-italic text-grey-8 ellipsis">{{ frag.scientific_name }}</div>
            <div class="frag-card__facts q-mt-xs text-caption">
              <div><span class="text-grey-7">CITES</span> {{ frag.cites || '—' }}</div>
              <div class="ellipsis"><span class="text-grey-7">{{ t('frags.card.origin') }}</span> {{ frag.origin || '—' }}</div>
              <div v-if="frag.acquired_from" class="ellipsis"><span class="text-grey-7">{{ t('frags.card.acquiredFrom') }}</span> {{ frag.acquired_from }}</div>
              <div><span class="text-grey-7">{{ t('frags.card.cutOn') }}</span> {{ formatDate(frag.cut_date) }}</div>
              <div v-if="frag.mother_name" class="ellipsis"><span class="text-grey-7">{{ t('frags.card.mother') }}</span> {{ frag.mother_name }}</div>
              <div v-if="aquariumName(frag)" class="ellipsis"><span class="text-grey-7">{{ t('frags.card.tank') }}</span> {{ aquariumName(frag) }}</div>
              <div v-if="frag.reserved_quantity || frag.transferred_quantity" class="text-weight-medium">
                <span v-if="frag.reserved_quantity" class="text-orange-9">{{ t('frags.card.reserved', frag.reserved_quantity) }}</span>
                <span v-if="frag.reserved_quantity && frag.transferred_quantity"> · </span>
                <span v-if="frag.transferred_quantity" class="text-grey-8">{{ t('frags.card.transferred', frag.transferred_quantity) }}</span>
              </div>
              <div v-if="frag.showcase_hidden && can.sell" class="text-grey-7">
                <q-icon name="visibility_off" size="xs" class="q-mr-xs" />{{ t('frags.card.hidden') }}
              </div>
              <div v-if="frag.certificate_number && can.sell">
                <span class="text-grey-7">{{ t('frags.card.certificate') }}</span>
                <router-link to="/transfers" class="text-primary">{{ frag.certificate_number }}</router-link>
              </div>
            </div>
          </q-card-section>

          <q-separator />
          <q-card-actions class="q-px-sm q-py-xs no-wrap">
            <!-- Quantité disponible : − / + ou saisie directe en touchant le nombre -->
            <div class="row items-center no-wrap frag-qty">
              <q-btn v-if="can.frags" round dense flat size="sm" icon="remove" :disable="frag.quantity === 0" @click="adjust(frag, -1)" />
              <div class="frag-qty__value" :class="{ 'cursor-pointer': can.frags }">
                {{ frag.quantity }}
                <q-popup-edit
                  v-if="can.frags"
                  v-slot="scope"
                  :model-value="frag.quantity"
                  buttons
                  :label-set="t('frags.card.ok')"
                  :label-cancel="t('common.cancel')"
                  @save="(value: number) => setQuantity(frag, value, 'correction')"
                >
                  <q-input
                    v-model.number="scope.value"
                    type="number"
                    min="0"
                    dense
                    autofocus
                    :label="t('frags.card.quantity')"
                    @keyup.enter="scope.set"
                  />
                </q-popup-edit>
              </div>
              <q-btn v-if="can.frags" round dense flat size="sm" icon="add" @click="adjust(frag, 1)" />
              <span class="text-caption text-grey-7 q-ml-xs">{{ t('frags.card.available') }}</span>
            </div>
            <q-space />
            <span v-if="can.sell" class="text-caption text-weight-bold q-px-xs">
              {{ formatPrice(frag.price) }}<span v-if="frag.price != null" class="text-grey-7">{{ t('frags.card.perUnit') }}</span>
            </span>
            <q-btn flat round dense size="sm" color="grey-7" icon="history" @click="openHistory(frag)">
              <q-tooltip>{{ t('frags.card.history') }}</q-tooltip>
            </q-btn>
            <q-btn flat round dense size="sm" color="grey-7" icon="photo_library" @click="openGallery(frag)">
              <q-tooltip>{{ t('frags.card.photos') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.frags" flat round dense size="sm" color="grey-7" icon="more_vert">
              <q-menu auto-close>
                <q-list style="min-width: 190px">
                  <q-item clickable @click="openEdit(frag)">
                    <q-item-section avatar><q-icon name="edit" size="xs" /></q-item-section>
                    <q-item-section>{{ t('actions.edit') }}</q-item-section>
                  </q-item>
                  <q-item v-if="frag.mother_coral_id" v-close-popup clickable @click="originFrag = frag">
                    <q-item-section avatar><q-icon name="folder_shared" size="xs" /></q-item-section>
                    <q-item-section>{{ t('frags.card.originDocs') }}</q-item-section>
                  </q-item>
                  <q-item v-if="frag.mother_coral_id" clickable @click="openCreate(frag.mother_coral_id)">
                    <q-item-section avatar><q-icon name="content_cut" size="xs" /></q-item-section>
                    <q-item-section>{{ t('frags.card.sameMother') }}</q-item-section>
                  </q-item>
                  <q-item v-if="can.sell" clickable @click="toggleShowcase(frag)">
                    <q-item-section avatar><q-icon :name="frag.showcase_hidden ? 'visibility' : 'visibility_off'" size="xs" /></q-item-section>
                    <q-item-section>{{ frag.showcase_hidden ? t('frags.card.showInShowcase') : t('frags.card.hideFromShowcase') }}</q-item-section>
                  </q-item>
                  <q-item v-if="can.frags && !frag.reserved_quantity" clickable class="text-negative" @click="removeFrag(frag)">
                    <q-item-section avatar><q-icon name="delete" size="xs" color="negative" /></q-item-section>
                    <q-item-section>{{ t('actions.delete') }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </q-card-actions>
        </q-card>
      </div>
    </div>

    <!-- Sélection en cours : création du certificat -->
    <q-page-sticky v-if="selected.size > 0" position="bottom" :offset="[0, 16]">
      <q-card class="selection-bar row items-center no-wrap q-pa-sm gap-sm shadow-6">
        <q-btn flat round dense icon="close" color="grey-7" @click="selected.clear()" />
        <div class="text-weight-bold q-pr-sm">{{ t('frags.selection.batches', selected.size) }}</div>
        <q-btn v-if="can.bourse" flat round dense color="primary" icon="qr_code_2" @click="labelsDialog = true">
          <q-tooltip>{{ t('frags.selection.labels') }}</q-tooltip>
        </q-btn>
        <q-btn v-if="can.frags" flat round dense color="primary" icon="move_down">
          <q-tooltip>{{ t('frags.selection.move') }}</q-tooltip>
          <q-menu anchor="top middle" self="bottom middle">
            <q-list dense style="min-width: 200px">
              <q-item-label header>{{ t('frags.selection.moveTo', selected.size) }}</q-item-label>
              <q-item v-for="opt in aquariumOptions" :key="opt.value" v-close-popup clickable @click="moveSelection(opt.value)">
                <q-item-section avatar><q-icon name="water" size="xs" /></q-item-section>
                <q-item-section>{{ opt.label }}</q-item-section>
              </q-item>
              <q-item v-close-popup clickable @click="moveSelection(null)">
                <q-item-section avatar><q-icon name="block" size="xs" /></q-item-section>
                <q-item-section>{{ t('frags.tanks.none') }}</q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
        <q-btn v-if="can.sell" unelevated color="primary" icon="description" :label="t('frags.selection.certificate')" @click="openCertificate" />
      </q-card>
    </q-page-sticky>

    <!-- Création / modification -->
    <FormDialog
      v-model="fragDialog"
      icon="content_cut"
      :title="editing ? t('frags.form.editTitle', { ref: editing.reference }) : t('frags.new')"
      :subtitle="editing ? editing.name : t('frags.form.subtitle')"
      width="620px"
      :loading="saving"
      :submit-label="editing ? t('common.save') : t('frags.form.create')"
      @submit="saveFrag"
    >
      <AppSelect
        v-if="!editing"
        :model-value="form.mother_coral_id"
        :options="coralOptions"
        :label="t('frags.form.mother')"
        clearable
        use-input
        input-debounce="0"
        :hint="t('frags.form.motherHint')"
        @filter="filterCorals"
        @update:model-value="applyMother"
      />
      <div class="row q-col-gutter-md">
        <div class="col-12 col-sm-6"><q-input v-model="form.name" :label="t('frags.form.name')" outlined dense /></div>
        <div class="col-12 col-sm-6"><q-input v-model="form.scientific_name" :label="t('frags.form.scientificName')" outlined dense /></div>
        <div class="col-12 col-sm-6">
          <q-input v-model="form.cites" :label="t('frags.form.cites')" outlined dense :hint="t('frags.form.citesHint')" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="form.origin" :label="t('frags.form.origin')" outlined dense :hint="t('frags.form.originHint')" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="form.acquired_from" :label="t('frags.form.acquiredFrom')" outlined dense :hint="t('frags.form.acquiredFromHint')" />
        </div>
        <div class="col-12 col-sm-6"><DateInput v-model="form.cut_date" :label="t('frags.form.cutDate')" /></div>
        <div class="col-12 col-sm-6">
          <AppSelect v-model="form.aquarium_id" :options="aquariumOptions" :label="t('frags.form.tank')" clearable />
        </div>
        <div v-if="can.sell" class="col-6">
          <q-input v-model.number="form.price" type="number" min="0" step="0.5" :label="t('frags.form.price')" suffix="€" outlined dense />
        </div>
        <div class="col-6">
          <q-input
            v-model.number="form.quantity"
            type="number"
            :min="editing ? 0 : 1"
            :label="t('frags.form.quantity')"
            :hint="editing ? t('frags.form.quantityHint') : undefined"
            outlined
            dense
          />
        </div>
      </div>
      <q-input v-model="form.notes" :label="t('frags.form.notes')" type="textarea" outlined dense autogrow />
    </FormDialog>

    <!-- Certificat de cession à partir de la sélection -->
    <FormDialog
      v-model="certificateDialog"
      icon="description"
      :title="t('frags.certificate.title')"
      :subtitle="t('frags.certificate.subtitle', selectedFrags.length)"
      width="620px"
      :loading="saving"
      :submit-label="t('frags.certificate.create')"
      @submit="createCertificate"
    >
      <q-banner v-if="sellerProfile && !sellerProfile.complete" rounded dense class="bg-amber-1 text-amber-10">
        <template #avatar><q-icon name="badge" color="amber-9" /></template>
        {{ t('frags.certificate.profileMissing') }}
        <template #action>
          <q-btn flat color="amber-10" :label="t('frags.certificate.complete')" @click="profileDialog = true" />
        </template>
      </q-banner>
      <q-list bordered separator class="rounded-borders">
        <q-item v-for="frag in selectedFrags" :key="frag.id" class="column items-stretch">
          <div class="text-weight-bold">{{ frag.reference }} · {{ frag.name }}</div>
          <div class="text-caption text-grey-7">CITES {{ frag.cites || '—' }} · {{ frag.origin || t('frags.certificate.noOrigin') }}</div>
          <div class="row items-center no-wrap gap-sm q-mt-sm">
            <q-input
              v-model.number="quantities[frag.id]"
              type="number"
              min="1"
              :max="frag.quantity"
              dense
              outlined
              :label="t('frags.certificate.quantity')"
              :suffix="`/ ${frag.quantity}`"
              style="width: 120px"
            />
            <q-icon name="close" size="xs" color="grey-6" />
            <q-input
              v-model.number="prices[frag.id]"
              type="number"
              min="0"
              step="0.5"
              suffix="€"
              dense
              outlined
              :label="t('frags.certificate.unitPrice')"
              style="width: 120px"
            />
            <q-space />
            <div class="text-weight-bold text-no-wrap">{{ formatPrice(lineAmount(frag)) }}</div>
          </div>
        </q-item>
      </q-list>
      <div class="text-right text-weight-bold">
        {{ t('frags.certificate.total', { n: certificateCount, total: formatPrice(certificateTotal) }, certificateCount) }}
      </div>
      <LocationSelect v-model="saleLocation" @loaded="restoreLastLocation" />
      <DateInput v-model="certificateForm.transfer_date" :label="t('frags.certificate.date')" />
      <q-input v-model="certificateForm.notes" :label="t('frags.certificate.notes')" type="textarea" outlined dense autogrow />
    </FormDialog>

    <SellerProfileDialog v-model="profileDialog" @saved="(p) => (sellerProfile = p)" />

    <!-- Étiquettes à imprimer -->
    <FormDialog
      v-model="labelsDialog"
      icon="qr_code_2"
      :title="t('frags.labels')"
      :subtitle="t('frags.labelsDialog.subtitle')"
      width="480px"
      :submit-label="t('frags.labelsDialog.download')"
      submit-icon="download"
      :loading="labelsLoading"
      @submit="downloadLabels"
    >
      <q-option-group
        v-model="labelsScope"
        :options="[
          { label: t('frags.labelsDialog.selection', { n: selected.size }), value: 'selection', disable: selected.size === 0 },
          { label: t('frags.labelsDialog.available', { n: count('available') }), value: 'available' },
        ]"
      />
      <q-toggle v-model="labelsPerUnit" :label="t('frags.labelsDialog.perUnit')" />
      <div class="text-caption text-grey-7">{{ t('frags.labelsDialog.help') }}</div>
    </FormDialog>

    <QrScannerDialog v-model="scannerOpen" @detected="onScanned" />

    <!-- Documents d'achat du pied mère : preuve de l'origine d'une bouture en cas de contrôle -->
    <q-dialog :model-value="originFrag !== null" @update:model-value="(v: boolean) => !v && (originFrag = null)">
      <q-card v-if="originFrag" style="width: 520px; max-width: 94vw">
        <q-card-section class="row items-center no-wrap">
          <div class="col">
            <div class="text-subtitle1 text-weight-bold">{{ t('frags.originDialog.title') }}</div>
            <div class="text-caption text-grey-7">
              {{ originFrag.reference }} · {{ t('frags.originDialog.mother', { name: originFrag.mother_name ?? '' }) }}
              <template v-if="originFrag.cites"> · CITES {{ originFrag.cites }}</template>
            </div>
          </div>
          <q-btn flat round dense icon="close" :aria-label="t('common.close')" v-close-popup />
        </q-card-section>
        <q-card-section class="q-pt-none">
          <SpecimenDocuments entity-type="corals" :entity-id="originFrag.mother_coral_id!" :title="t('frags.originDialog.docs')" />
        </q-card-section>
      </q-card>
    </q-dialog>

    <ShowcaseDialog v-model="showcaseOpen" @changed="load" @update:model-value="(open: boolean) => !open && loadReservationCount()" />

    <!-- Historique d'un lot -->
    <FormDialog
      v-model="historyDialog"
      icon="history"
      :title="t('frags.historyDialog.title')"
      :subtitle="historyFrag ? `${historyFrag.reference} · ${historyFrag.name}` : undefined"
      width="520px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <q-list v-if="movements.length" bordered separator class="rounded-borders">
        <q-item v-for="m in movements" :key="m.id">
          <q-item-section avatar>
            <q-avatar size="36px" :color="MOVEMENT_REASONS[m.reason].color" text-color="white" :icon="MOVEMENT_REASONS[m.reason].icon" />
          </q-item-section>
          <q-item-section>
            <q-item-label class="text-weight-bold">
              {{ m.delta > 0 ? '+' : '' }}{{ m.delta }}
              <span class="text-weight-regular">· {{ t(`frags.reasons.${m.reason}`) }}</span>
            </q-item-label>
            <q-item-label caption>
              {{ formatDateTime(m.created_at) }}
              <template v-if="m.certificate_number"> · {{ m.certificate_number }}</template>
              <template v-if="m.note"> · {{ m.note }}</template>
            </q-item-label>
          </q-item-section>
          <q-item-section v-if="can.frags && isManual(m)" side>
            <q-btn flat dense round icon="swap_horiz" color="grey-7">
              <q-tooltip>{{ t('frags.historyDialog.changeReason') }}</q-tooltip>
              <q-menu auto-close>
                <q-list dense style="min-width: 170px">
                  <q-item
                    v-for="reason in reasonChoices(m)"
                    :key="reason"
                    clickable
                    :active="reason === m.reason"
                    @click="changeReason(m, reason)"
                  >
                    <q-item-section avatar><q-icon :name="MOVEMENT_REASONS[reason].icon" size="xs" /></q-item-section>
                    <q-item-section>{{ t(`frags.reasons.${reason}`) }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </q-item-section>
        </q-item>
      </q-list>
      <div v-else class="text-grey-6 text-center q-pa-md">{{ t('frags.historyDialog.none') }}</div>
      <div class="text-caption text-grey-7">{{ t('frags.historyDialog.help') }}</div>
    </FormDialog>

    <!-- Suivi : survie et ventes par espèce / pied mère -->
    <FormDialog
      v-model="statsDialog"
      icon="query_stats"
      :title="t('frags.statsDialog.title')"
      :subtitle="t('frags.statsDialog.subtitle')"
      width="760px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <q-btn-toggle
        v-model="statsGroup"
        unelevated
        no-caps
        toggle-color="primary"
        color="grey-2"
        text-color="grey-8"
        :options="[
          { label: t('frags.statsDialog.bySpecies'), value: 'species' },
          { label: t('frags.statsDialog.byMother'), value: 'mother' },
        ]"
        @update:model-value="loadStats"
      />
      <q-markup-table flat bordered dense class="stats-table">
        <thead>
          <tr>
            <th class="text-left">{{ statsGroup === 'mother' ? t('frags.statsDialog.mother') : t('frags.statsDialog.species') }}</th>
            <th>{{ t('frags.statsDialog.survival') }}</th>
            <th>{{ t('frags.statsDialog.produced') }}</th>
            <th>{{ t('frags.statsDialog.transferred') }}</th>
            <th>{{ t('frags.statsDialog.lost') }}</th>
            <th class="gt-xs">{{ t('frags.statsDialog.gifts') }}</th>
            <th>{{ t('frags.statsDialog.available') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in stats" :key="row.key">
            <td class="text-left">
              <div class="text-weight-medium ellipsis stats-name">{{ row.name }}</div>
              <div v-if="row.scientific_name" class="text-caption text-italic text-grey-7 ellipsis stats-name">
                {{ row.scientific_name }}
              </div>
            </td>
            <td class="text-center">
              <q-badge v-if="row.survival_rate !== null" :color="survivalColor(row.survival_rate)" class="text-weight-bold">
                {{ Math.round(row.survival_rate * 100) }} %
              </q-badge>
              <span v-else>—</span>
            </td>
            <td class="text-center">{{ row.produced }}</td>
            <td class="text-center">{{ row.transferred }}<span v-if="row.reserved" class="text-orange-9"> +{{ row.reserved }}</span></td>
            <td class="text-center">{{ row.lost }}</td>
            <td class="text-center gt-xs">{{ row.gift }}</td>
            <td class="text-center">{{ row.available }}</td>
          </tr>
          <tr v-if="!stats.length">
            <td colspan="7" class="text-center text-grey-6">{{ t('frags.statsDialog.none') }}</td>
          </tr>
        </tbody>
      </q-markup-table>
      <div class="text-caption text-grey-7">{{ t('frags.statsDialog.help') }}</div>
    </FormDialog>

    <PhotoGalleryDialog
      v-if="galleryFrag"
      v-model="galleryOpen"
      :entity-type="PhotoEntityType.frags"
      :entity-id="galleryFrag.id"
      :entity-label="`${galleryFrag.reference} · ${galleryFrag.name}`"
      @main-changed="imageTimestamp = Date.now()"
    />
  </q-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios, { type AxiosError } from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import AppInput from 'src/components/AppInput.vue';
import AppSelect from 'src/components/AppSelect.vue';
import DateInput from 'src/components/DateInput.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import LocationSelect from 'src/components/LocationSelect.vue';
import PageHeader from 'src/components/PageHeader.vue';
import QrScannerDialog from 'src/components/QrScannerDialog.vue';
import { isQueued, newKey } from 'src/offline/queued';
import { offlineSales, unsyncedSaleQuantities, type OfflineSalePayload, type OfflineSaleRecord } from 'src/pro/offline/sales';
import { SYNCED_EVENT, useOfflineStore } from 'src/stores/offlineStore';
import ShowcaseDialog from 'src/pro/components/ShowcaseDialog.vue';
import type { Reservation } from 'src/pro/types/showcase';
import SpecimenDocuments from 'src/components/SpecimenDocuments.vue';
import { fragRefFromQr, scannerAvailable } from 'src/utils/qrScanner';
import PhotoGalleryDialog from 'src/components/PhotoGalleryDialog.vue';
import SellerProfileDialog from 'src/pro/components/SellerProfileDialog.vue';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { usePermissions } from 'src/composables/usePermissions';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { useCoralStore } from 'src/stores/coralStore';
import { mainPhotoUrl } from 'src/stores/photoStore';
import {
  FRAG_STATUS,
  MOVEMENT_REASONS,
  locationPayload,
  type Certificate,
  type Frag,
  type FragMovement,
  type FragStatRow,
  type LocationChoice,
  type ManualReason,
  type SaleLocation,
  type SellerProfile,
} from 'src/types/frag';
import { PhotoEntityType } from 'src/types/photo';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatDateTime, formatPrice, isoDate } from 'src/utils/format';

const { t } = useI18n();
const $q = useQuasar();
const route = useRoute();
const router = useRouter();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const aquariumStore = useAquariumStore();
const coralStore = useCoralStore();
const offline = useOfflineStore();

const frags = ref<Frag[]>([]);
const loading = ref(true);
const saving = ref(false);
const imageTimestamp = ref(Date.now());
const search = ref<string | null>('');
type Filter = 'available' | 'reserved' | 'transferred' | 'all';
const statusFilter = ref<Filter>('available');

// Un lot peut être à la fois disponible, en partie réservé et en partie cédé
const FILTERS: Record<Filter, (f: Frag) => boolean> = {
  available: (f) => f.quantity > 0,
  reserved: (f) => f.reserved_quantity > 0,
  transferred: (f) => f.transferred_quantity > 0,
  all: () => true,
};

const statusOptions = computed(() => [
  { label: t('frags.filters.available', { n: count('available') }), value: 'available' },
  { label: t('frags.filters.reserved', { n: count('reserved') }), value: 'reserved' },
  { label: t('frags.filters.transferred', { n: count('transferred') }), value: 'transferred' },
  { label: t('frags.filters.all'), value: 'all' },
]);

function count(filter: Filter) {
  return frags.value.filter(FILTERS[filter]).length;
}

const filtered = computed(() => {
  const s = (search.value ?? '').trim().toLowerCase();
  return frags.value.filter(
    (f) =>
      FILTERS[statusFilter.value](f) &&
      (aquariumFilter.value === null || (aquariumFilter.value === 0 ? !f.aquarium_id : f.aquarium_id === aquariumFilter.value)) &&
      (!s || [f.name, f.scientific_name, f.reference, f.cites, f.origin, f.acquired_from, f.mother_name].some((v) => v?.toLowerCase().includes(s))),
  );
});

function aquariumName(frag: Frag) {
  return frag.aquarium_id ? aquariumStore.getById(frag.aquarium_id)?.name : null;
}

async function load() {
  try {
    const { data } = await axios.get<Frag[]>('/frags/');
    frags.value = await withOfflineChanges(data);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

// Hors connexion : les données lues peuvent dater ; on y applique ce qui
// attend l'envoi (quantités modifiées, ventes pas encore synchronisées)
async function withOfflineChanges(list: Frag[]): Promise<Frag[]> {
  const quantities = new Map<number, number>();
  for (const op of offline.pending) {
    const match = /^\/frags\/(\d+)$/.exec(op.url);
    const quantity = (op.data as { quantity?: unknown } | null)?.quantity;
    if (op.method === 'PATCH' && match && typeof quantity === 'number') quantities.set(Number(match[1]), quantity);
  }
  const sold = await unsyncedSaleQuantities();
  return list.map((frag) => {
    const quantity = Math.max(0, (quantities.get(frag.id) ?? frag.quantity) - (sold.get(frag.id) ?? 0));
    return quantity === frag.quantity ? frag : { ...frag, quantity };
  });
}

// --- Création / modification ---
const fragDialog = ref(false);
const editing = ref<Frag | null>(null);
const emptyForm = () => ({
  mother_coral_id: null as number | null,
  aquarium_id: null as number | null,
  name: '',
  scientific_name: '',
  coral_type: null as Frag['coral_type'],
  cites: '',
  origin: '',
  acquired_from: '',
  cut_date: isoDate() as string | null,
  price: null as number | null,
  notes: '',
  quantity: 1,
});
const form = ref(emptyForm());

const coralFilter = ref('');
const coralOptions = computed(() => {
  const s = coralFilter.value.toLowerCase();
  return coralStore.corals
    .map((c) => ({
      label: `${c.name} — ${aquariumStore.getById(c.aquarium_id)?.name ?? '?'}`,
      value: c.id,
      caption: c.scientific_name,
    }))
    .filter((o) => !s || o.label.toLowerCase().includes(s));
});
const aquariumOptions = computed(() => aquariumStore.aquariums.map((a) => ({ label: a.name, value: Number(a.id) })));

// Filtre « où se trouve la bouture » : tous, un bac, ou hors bac (0)
const aquariumFilter = ref<number | null>(null);
const aquariumFilterOptions = computed(() => {
  const count = (id: number | null) =>
    frags.value.filter((f) => FILTERS[statusFilter.value](f) && (id === 0 ? !f.aquarium_id : f.aquarium_id === id)).length;
  return [
    { label: t('frags.tanks.all'), value: null },
    ...aquariumOptions.value
      .filter((a) => count(a.value) > 0)
      .map((a) => ({ label: t('frags.tanks.count', { name: a.label, n: count(a.value) }), value: a.value })),
    { label: t('frags.tanks.noneCount', { n: count(0) }), value: 0 },
  ];
});

async function moveSelection(aquariumId: number | null) {
  try {
    const { data } = await axios.post<Frag[]>('/frags/move', { frag_ids: [...selected], aquarium_id: aquariumId });
    const moved = new Map(data.map((f) => [f.id, f]));
    frags.value = frags.value.map((f) => moved.get(f.id) ?? f);
    const target = (aquariumId ? aquariumStore.getById(aquariumId)?.name : null) ?? t('frags.notify.outOfTank');
    $q.notify({ type: 'positive', message: t('frags.notify.moved', { n: data.length, target }, data.length) });
    selected.clear();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.moveFailed')) });
  }
}

function filterCorals(value: string, update: (fn: () => void) => void) {
  update(() => (coralFilter.value = value));
}

function applyMother(coralId: number | null) {
  form.value.mother_coral_id = coralId;
  const coral = coralId ? coralStore.getById(coralId) : undefined;
  if (!coral) return;
  Object.assign(form.value, {
    name: coral.name,
    scientific_name: coral.scientific_name,
    coral_type: coral.type,
    cites: coral.cites,
    origin: coral.origin,
    acquired_from: coral.acquired_from ?? '',
    aquarium_id: coral.aquarium_id,
  });
}

function openCreate(motherId?: number | null) {
  editing.value = null;
  form.value = emptyForm();
  if (motherId) applyMother(motherId);
  fragDialog.value = true;
}

function openEdit(frag: Frag) {
  editing.value = frag;
  form.value = {
    ...emptyForm(),
    aquarium_id: frag.aquarium_id,
    name: frag.name,
    scientific_name: frag.scientific_name,
    coral_type: frag.coral_type,
    cites: frag.cites,
    origin: frag.origin,
    acquired_from: frag.acquired_from ?? '',
    cut_date: frag.cut_date,
    price: frag.price,
    notes: frag.notes ?? '',
    quantity: frag.quantity,
  };
  fragDialog.value = true;
}

async function saveFrag() {
  const f = form.value;
  if (!f.name.trim()) {
    $q.notify({ type: 'warning', message: t('frags.notify.nameRequired') });
    return;
  }
  const payload = {
    aquarium_id: f.aquarium_id,
    name: f.name.trim(),
    scientific_name: f.scientific_name.trim(),
    coral_type: f.coral_type,
    cites: f.cites.trim(),
    origin: f.origin.trim(),
    acquired_from: f.acquired_from.trim() || null,
    cut_date: f.cut_date || null,
    price: typeof f.price === 'number' ? f.price : null,
    notes: f.notes || null,
    quantity: Math.max(editing.value ? 0 : 1, Number(f.quantity) || 0),
  };
  saving.value = true;
  try {
    if (editing.value) {
      const { data } = await axios.patch<Frag>(`/frags/${editing.value.id}`, payload);
      frags.value = frags.value.map((x) => (x.id === data.id ? data : x));
    } else {
      const { data } = await axios.post<Frag>('/frags/', { ...payload, mother_coral_id: f.mother_coral_id });
      frags.value = [data, ...frags.value];
      statusFilter.value = 'available';
      $q.notify({
        type: 'positive',
        message: t('frags.notify.created', { ref: data.reference, n: data.quantity }, data.quantity),
      });
    }
    fragDialog.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

// Quantité : mise à jour immédiate à l'écran, envoyée après une courte pause
// (plusieurs appuis sur + / − = un seul enregistrement)
const pendingQuantity = new Map<number, ReturnType<typeof setTimeout>>();

// Quantité enregistrée côté serveur au début d'une série d'appuis
const baseQuantity = new Map<number, number>();

function adjust(frag: Frag, delta: number) {
  setQuantity(frag, frag.quantity + delta);
}

// Raison : + = ajout, − = perte (requalifiable dans l'historique), saisie directe = correction
function setQuantity(frag: Frag, value: number, reason?: ManualReason) {
  const quantity = Math.max(0, Math.round(Number(value) || 0));
  if (!baseQuantity.has(frag.id)) baseQuantity.set(frag.id, frag.quantity);
  const previous = baseQuantity.get(frag.id)!;
  frag.quantity = quantity;
  if (quantity === 0) selected.delete(frag.id);
  clearTimeout(pendingQuantity.get(frag.id));
  pendingQuantity.set(
    frag.id,
    setTimeout(() => {
      pendingQuantity.delete(frag.id);
      baseQuantity.delete(frag.id);
      if (frag.quantity === previous) return;
      const quantityReason = reason ?? (frag.quantity > previous ? 'added' : 'lost');
      axios
        .patch<Frag>(
          `/frags/${frag.id}`,
          { quantity: frag.quantity, quantity_reason: quantityReason },
          { offline: { label: t('frags.notify.quantityLabel', { ref: frag.reference, name: frag.name, n: frag.quantity }) } },
        )
        .then((response) => {
          // Hors connexion (en file d'attente) : on garde la valeur affichée
          if (isQueued(response)) return;
          // Ne pas écraser un appui fait pendant l'envoi
          const { data } = response;
          if (!pendingQuantity.has(frag.id)) frags.value = frags.value.map((x) => (x.id === data.id ? data : x));
        })
        .catch((err) => {
          frag.quantity = previous;
          $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.quantityFailed')) });
        });
    }, 600),
  );
}

function removeFrag(frag: Frag) {
  confirmRemove(t('frags.item', { ref: frag.reference }), async () => {
    await axios.delete(`/frags/${frag.id}`);
    frags.value = frags.value.filter((x) => x.id !== frag.id);
    selected.delete(frag.id);
  });
}

// --- Photos ---
const galleryOpen = ref(false);
const galleryFrag = ref<Frag | null>(null);
function openGallery(frag: Frag) {
  galleryFrag.value = frag;
  galleryOpen.value = true;
}

// --- Sélection et certificat ---
const selected = reactive(new Set<number>());
const selectedFrags = computed(() => frags.value.filter((f) => selected.has(f.id)));
const prices = ref<Record<number, number | null>>({});
const quantities = ref<Record<number, number>>({});
const saleLocation = ref<LocationChoice>(null);

// Dernier lieu utilisé sur cet appareil (toute une bourse sur le même lieu)
const LAST_LOCATION_KEY = 'aquas.lastSaleLocation';

const knownLocations = ref<SaleLocation[]>([]);

function restoreLastLocation(locations: SaleLocation[]) {
  knownLocations.value = locations;
  if (saleLocation.value !== null) return;
  try {
    const lastId = Number(localStorage.getItem(LAST_LOCATION_KEY));
    if (locations.some((l) => l.id === lastId)) saleLocation.value = lastId;
  } catch {
    // stockage local indisponible (navigation privée) : pas de lieu par défaut
  }
}

function rememberLocation(id: number | null) {
  // Seul l'identifiant d'un lieu de vente connu est gardé sur l'appareil
  const known = knownLocations.value.find((l) => l.id === id);
  try {
    if (known) localStorage.setItem(LAST_LOCATION_KEY, String(known.id));
  } catch {
    // stockage local indisponible
  }
}
const certificateDialog = ref(false);
const certificateForm = ref<{ transfer_date: string | null; notes: string }>({ transfer_date: isoDate(), notes: '' });
const sellerProfile = ref<SellerProfile | null>(null);
const profileDialog = ref(false);

function lineQuantity(frag: Frag): number {
  return Math.min(frag.quantity, Math.max(1, Math.round(Number(quantities.value[frag.id]) || 1)));
}

function lineAmount(frag: Frag): number | null {
  const price = prices.value[frag.id];
  return typeof price === 'number' ? price * lineQuantity(frag) : null;
}

const certificateCount = computed(() => selectedFrags.value.reduce((sum, f) => sum + lineQuantity(f), 0));
const certificateTotal = computed(() => {
  const values = selectedFrags.value.map(lineAmount).filter((p): p is number => p !== null);
  return values.length ? values.reduce((a, b) => a + b, 0) : null;
});

function toggle(frag: Frag) {
  if (selected.has(frag.id)) selected.delete(frag.id);
  else selected.add(frag.id);
}

async function openCertificate() {
  prices.value = Object.fromEntries(selectedFrags.value.map((f) => [f.id, f.price]));
  quantities.value = Object.fromEntries(selectedFrags.value.map((f) => [f.id, 1]));
  saleLocation.value = null;
  certificateForm.value = { transfer_date: isoDate(), notes: '' };
  certificateDialog.value = true;
  try {
    sellerProfile.value = (await axios.get<SellerProfile>('/seller-profile/')).data;
  } catch {
    sellerProfile.value = null;
  }
}

async function createCertificate() {
  if (sellerProfile.value && !sellerProfile.value.complete) {
    profileDialog.value = true;
    return;
  }
  saving.value = true;
  const payload = {
    items: selectedFrags.value.map((f) => ({
      frag_id: f.id,
      quantity: lineQuantity(f),
      price: typeof prices.value[f.id] === 'number' ? (prices.value[f.id] as number) : null,
    })),
    transfer_date: certificateForm.value.transfer_date || null,
    notes: certificateForm.value.notes || null,
    ...locationPayload(saleLocation.value),
  };
  // Hors connexion : vente préparée sur l'appareil, signée tout de suite
  if (!offline.online) {
    await createOfflineSale(payload);
    saving.value = false;
    return;
  }
  try {
    // Serveur qui ne répond pas : vente hors connexion sans attendre davantage
    const { data } = await axios.post<Certificate>('/transfer-certificates/', payload, { timeout: 10_000 });
    rememberLocation(data.location_id);
    certificateDialog.value = false;
    selected.clear();
    void router.push({ path: '/transfers', query: { sign: String(data.id) } });
  } catch (err) {
    if (!(err as AxiosError).response) await createOfflineSale(payload);
    else $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.certificateFailed')) });
  } finally {
    saving.value = false;
  }
}

// Pas de réseau : la vente est préparée sur l'appareil et signée tout de suite
async function createOfflineSale(payload: OfflineSalePayload) {
  const profile = sellerProfile.value;
  if (!profile) {
    $q.notify({ type: 'negative', message: t('frags.notify.offlineNoProfile') });
    return;
  }
  const choice = saleLocation.value;
  const sale: OfflineSaleRecord = {
    id: newKey(),
    created_at: new Date().toISOString(),
    status: 'awaiting_signature',
    payload,
    location_label: typeof choice === 'number' ? (knownLocations.value.find((l) => l.id === choice)?.name ?? null) : choice,
    seller: profile,
    legal_mention: profile.legal_mention,
    privacy_notice: profile.effective_privacy_notice ?? '',
    items: selectedFrags.value.map((f, index) => ({
      id: index + 1,
      frag_id: f.id,
      reference: f.reference,
      name: f.name,
      scientific_name: f.scientific_name,
      cites: f.cites,
      origin: f.origin,
      mother_name: f.mother_name,
      cut_date: f.cut_date,
      quantity: lineQuantity(f),
      price: payload.items[index]!.price,
    })),
  };
  try {
    await offlineSales.save(sale);
  } catch {
    $q.notify({ type: 'negative', message: t('frags.notify.offlineSaveFailed') });
    return;
  }
  if (typeof choice === 'number') rememberLocation(choice);
  certificateDialog.value = false;
  selected.clear();
  $q.notify({ type: 'info', icon: 'cloud_off', message: t('frags.notify.offlineReady') });
  void router.push(`/signature/hors-ligne/${sale.id}`);
}

// --- Documents d'origine (pied mère) ---
const originFrag = ref<Frag | null>(null);

// --- Vitrine ---
const showcaseOpen = ref(false);
const newReservations = ref(0);

async function loadReservationCount() {
  try {
    const { data } = await axios.get<Reservation[]>('/showcase/reservations');
    newReservations.value = data.filter((r) => r.status === 'new').length;
  } catch {
    newReservations.value = 0;
  }
}

async function toggleShowcase(frag: Frag) {
  try {
    const { data } = await axios.patch<Frag>(`/frags/${frag.id}`, { showcase_hidden: !frag.showcase_hidden });
    frags.value = frags.value.map((x) => (x.id === data.id ? data : x));
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.updateFailed')) });
  }
}

// --- Historique d'un lot ---
const historyDialog = ref(false);
const historyFrag = ref<Frag | null>(null);
const movements = ref<FragMovement[]>([]);
const MANUAL: ManualReason[] = ['added', 'lost', 'gift', 'correction'];

function isManual(m: FragMovement): boolean {
  return (MANUAL as string[]).includes(m.reason);
}

function reasonChoices(m: FragMovement): ManualReason[] {
  return m.delta > 0 ? ['added', 'correction'] : ['lost', 'gift', 'correction'];
}

async function openHistory(frag: Frag) {
  historyFrag.value = frag;
  try {
    movements.value = (await axios.get<FragMovement[]>(`/frags/${frag.id}/movements`)).data;
    historyDialog.value = true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.historyFailed')) });
  }
}

async function changeReason(m: FragMovement, reason: ManualReason) {
  if (!historyFrag.value || reason === m.reason) return;
  try {
    const { data } = await axios.patch<FragMovement>(`/frags/${historyFrag.value.id}/movements/${m.id}`, { reason });
    movements.value = movements.value.map((x) => (x.id === data.id ? data : x));
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.reasonFailed')) });
  }
}

// --- Suivi ---
const statsDialog = ref(false);
const statsGroup = ref<'species' | 'mother'>('species');
const stats = ref<FragStatRow[]>([]);

async function loadStats() {
  try {
    stats.value = (await axios.get<FragStatRow[]>('/frags/stats', { params: { group_by: statsGroup.value } })).data;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.statsFailed')) });
  }
}

async function openStats() {
  await loadStats();
  statsDialog.value = true;
}

function survivalColor(rate: number): string {
  if (rate >= 0.9) return 'positive';
  if (rate >= 0.7) return 'orange-8';
  return 'negative';
}

// --- Étiquettes et QR codes ---
const labelsDialog = ref(false);
const labelsLoading = ref(false);
const labelsScope = ref<'selection' | 'available'>('available');
const labelsPerUnit = ref(false);
const scannerOpen = ref(false);
const canScan = scannerAvailable();
const highlighted = ref<number | null>(null);

watch(labelsDialog, (open) => {
  if (open) labelsScope.value = selected.size ? 'selection' : 'available';
});

async function downloadLabels() {
  labelsLoading.value = true;
  try {
    const params: Record<string, string | boolean> = { base_url: window.location.origin, per_unit: labelsPerUnit.value };
    if (labelsScope.value === 'selection') params.ids = [...selected].join(',');
    const { data } = await axios.get<Blob>('/frags/labels.pdf', { params, responseType: 'blob' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(data);
    link.download = t('frags.labelsDialog.fileName');
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 10_000);
    labelsDialog.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('frags.notify.labelsFailed')) });
  } finally {
    labelsLoading.value = false;
  }
}

// Lot ouvert depuis une étiquette (lien « /frags?ref=… » ou scanner) : affiché et sélectionné
async function openByReference(reference: string) {
  const frag = frags.value.find((f) => f.reference === reference);
  if (!frag) {
    $q.notify({ type: 'warning', message: t('frags.notify.notFound', { ref: reference }) });
    return;
  }
  search.value = '';
  statusFilter.value = frag.quantity > 0 ? 'available' : 'all';
  if (frag.quantity > 0 && can.frags && !selected.has(frag.id)) {
    selected.add(frag.id);
    $q.notify({
      type: 'positive',
      icon: 'qr_code_scanner',
      message: t('frags.notify.addedToSelection', { ref: frag.reference, name: frag.name }),
    });
  }
  highlighted.value = frag.id;
  setTimeout(() => (highlighted.value = null), 2500);
  await nextTick();
  // Laisser les cartes (photos) se mettre en place avant de défiler
  setTimeout(() => document.getElementById(`frag-${frag.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 400);
}

function onScanned(value: string) {
  const reference = fragRefFromQr(value);
  if (reference) void openByReference(reference);
  else $q.notify({ type: 'warning', message: t('frags.notify.notALabel') });
}

watch(
  () => route.query.ref,
  (reference) => {
    if (typeof reference === 'string' && !loading.value) {
      void openByReference(reference);
      void router.replace({ query: {} });
    }
  },
);

// Envois hors connexion terminés : données à jour côté serveur
function onSynced() {
  void load();
}
window.addEventListener(SYNCED_EVENT, onSynced);
onBeforeUnmount(() => window.removeEventListener(SYNCED_EVENT, onSynced));

onMounted(async () => {
  await Promise.all([load(), aquariumStore.fetch(), coralStore.fetch(), can.sell ? loadReservationCount() : Promise.resolve()]);
  // Paramètres d'arrivée lus puis retirés de l'adresse AVANT d'ouvrir une
  // fenêtre : un changement de route referme les dialogues Quasar
  const reference = typeof route.query.ref === 'string' ? route.query.ref : null;
  const coralId = Number(route.query.coral);
  if (reference || coralId) await router.replace({ query: {} });
  if (reference) await openByReference(reference);
  // Arrivée depuis un corail (« Bouturer ») : création pré-remplie
  if (coralId && can.frags) openCreate(coralId);
});
</script>

<style scoped>
.aquarium-filter {
  min-width: 180px;
}

.frag-card--selected {
  border-color: var(--q-primary);
  box-shadow: 0 0 0 2px var(--q-primary);
}

.frag-card__overlay {
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.55) 0%, rgba(0, 0, 0, 0) 100%);
}

.frag-card__ref {
  background: rgba(0, 0, 0, 0.45);
  padding: 2px 8px;
  font-family: 'Roboto Mono', ui-monospace, monospace;
}

.frag-card__facts {
  display: grid;
  gap: 2px;
}

.frag-card__facts span {
  margin-right: 4px;
}

.frag-card--highlight {
  animation: frag-flash 0.8s ease-in-out 3;
}

@keyframes frag-flash {
  50% {
    box-shadow: 0 0 0 4px var(--q-positive);
  }
}

.frag-qty__value {
  min-width: 32px;
  text-align: center;
  font-size: 18px;
  font-weight: 700;
}

.stats-name {
  max-width: 34vw;
}

.selection-bar {
  border-radius: 28px;
}

.status-scroll {
  max-width: 100%;
  overflow-x: auto;
  scrollbar-width: none;
}
</style>
