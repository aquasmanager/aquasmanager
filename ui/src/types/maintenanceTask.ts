import type { SharedScope } from 'src/utils/sharedScope';

export type TaskRecurrence = 'none' | 'daily' | 'weekly' | 'monthly' | 'custom_days';

export interface MaintenanceTaskCompletion {
  id: number;
  task_id: number;
  completed_at: string;
  note?: string | null;
}

export interface MaintenanceTask {
  id: number;
  aquarium_id: number;
  title: string;
  description?: string | null;
  recurrence: TaskRecurrence;
  recurrence_days?: number | null;
  next_due_at?: string | null;
  last_completed_at?: string | null;
  scope: SharedScope;
  aquarium_ids: number[];
}

export interface MaintenanceTaskCreate {
  aquarium_id: number;
  title: string;
  description?: string | null;
  recurrence: TaskRecurrence;
  recurrence_days?: number | null;
  next_due_at?: string | null;
  scope?: SharedScope;
  aquarium_ids?: number[];
}

export type MaintenanceTaskUpdate = Partial<Omit<MaintenanceTaskCreate, 'aquarium_id'>>;

export interface MaintenanceTaskCompletionCreate {
  completed_at?: string | null;
  note?: string | null;
}

export interface CalendarEvent {
  kind: 'due' | 'planned' | 'done';
  date: string;
  task_id: number;
  title: string;
  aquarium_id: number;
  aquarium_name: string;
  aquarium_ids: number[];
  shared: boolean;
  overdue: boolean;
  note?: string | null;
}
