export type RuleConditionType = 'SENSOR_STATE' | 'THRESHOLD' | 'TIME_RANGE';
export type ThresholdOperator = '>' | '>=' | '<' | '<=';
export type RuleAction = 'ON' | 'OFF' | 'NOTIFY';

export interface RuleCondition {
  id?: number;
  rule_id?: number;
  sensor_id: number | null;
  condition_type: RuleConditionType;
  trigger_state?: string | null;
  operator?: ThresholdOperator | null;
  threshold_value?: number | null;
  // Plage horaire "HH:MM" (ou "HH:MM:SS" renvoyé par l'API) ; peut passer minuit
  start_time?: string | null;
  end_time?: string | null;
}

export interface Rule {
  id: number;
  name: string;
  action: RuleAction;
  match_type: 'AND' | 'OR';
  is_active: boolean;
  is_safety_lock: boolean;
  equipment_id?: number | null;
  group_id?: number | null;
  max_duration_seconds?: number | null;
  // Applique l'action inverse quand la condition n'est plus remplie
  revert_on_exit?: boolean;
  notification_channel?: string | null;
  notification_message?: string | null;
  conditions: RuleCondition[];
}

export type RuleCreate = Omit<Rule, 'id'>;
