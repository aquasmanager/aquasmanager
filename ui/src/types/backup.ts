export type BackupPart = 'photos' | 'icp' | 'documents' | 'certificates';
export type BackupLocation = 'local' | 'external';

// Libellés : backup.parts.<valeur> (i18n)
export const BACKUP_PARTS: BackupPart[] = ['photos', 'icp', 'documents', 'certificates'];

export interface BackupInfo {
  filename: string;
  location: BackupLocation;
  size_bytes: number;
  created_at: string;
  label: string;
  label_text: string;
  parts: string[];
  // Archive antérieure au contenu au choix : base + tous les fichiers
  legacy: boolean;
  valid: boolean;
}

export interface BackupSettings {
  enabled: boolean;
  frequency: 'daily' | 'weekly';
  hour: number;
  weekday: number;
  keep_count: number;
  include_photos: boolean;
  include_icp: boolean;
  include_documents: boolean;
  include_certificates: boolean;
  destination: BackupLocation;
  external_path: string | null;
  last_run_at?: string | null;
  last_status?: string | null;
  last_message?: string | null;
  next_run_at?: string | null;
  external_ok?: boolean | null;
  external_error?: string | null;
}
