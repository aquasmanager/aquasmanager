import { t } from 'src/i18n/instance';

export type MetricAlertSource = 'water_parameter' | 'sensor' | 'task_overdue' | 'low_stock' | 'sensor_stale';

export interface MetricAlert {
  id: number;
  aquarium_id: number;
  source: MetricAlertSource;
  water_parameter_id?: number | null;
  dashboard_card_id?: number | null;
  maintenance_task_id?: number | null;
  inventory_item_id?: number | null;
  sensor_id?: number | null;
  label: string;
  unit?: string | null;
  initial_value: number;
  resolved_value?: number | null;
  target_min?: number | null;
  target_max?: number | null;
  created_at: string;
  resolved_at?: string | null;
  acknowledged: boolean;
}

export const METRIC_ALERT_ICONS: Record<MetricAlertSource, string> = {
  water_parameter: 'science',
  sensor: 'sensors',
  task_overdue: 'event_busy',
  low_stock: 'inventory_2',
  sensor_stale: 'sensors_off',
};

export function metricAlertMessage(a: MetricAlert, currentValue?: number | null): string {
  const value = currentValue ?? (a.resolved_at != null && a.resolved_value != null ? a.resolved_value : a.initial_value);
  if (a.source === 'task_overdue') {
    return t('alerts.metric.overdue', { n: Math.round(value) });
  }
  if (a.source === 'sensor_stale') {
    if (a.resolved_at != null) return t('alerts.metric.backOnline');
    // Durée sans mesure (minutes) : celle du déclenchement, plus le temps écoulé
    // depuis ; affichée en heures ou en jours au-delà
    const elapsed = Math.max(0, (Date.now() - new Date(a.created_at).getTime()) / 60_000);
    const minutes = Math.round(a.initial_value + elapsed);
    if (minutes >= 1440) return t('alerts.metric.staleDays', Math.floor(minutes / 1440));
    if (minutes >= 60) return t('alerts.metric.staleHours', { n: Math.floor(minutes / 60) });
    return t('alerts.metric.stale', { n: minutes });
  }
  if (a.source === 'low_stock') {
    return t('alerts.metric.stock', {
      value: `${value} ${a.unit ?? ''}`.trim(),
      threshold: `${a.target_min ?? '--'} ${a.unit ?? ''}`.trim(),
    });
  }
  const range = `${a.target_min ?? '--'} - ${a.target_max ?? '--'} ${a.unit ?? ''}`.trim();
  return t('alerts.metric.value', { value: `${value} ${a.unit ?? ''}`.trim(), range });
}
