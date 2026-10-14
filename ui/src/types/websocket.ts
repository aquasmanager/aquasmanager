export type WsMessageType = 'SENSOR_READING' | 'EQUIPMENT_STATE' | 'CONTROLLER_STATUS';

export interface SensorReadingPayload {
  type: 'SENSOR_READING';
  sensor_id: number;
  controller_id: number;
  sensor_name: string;
  value: number;
}

export interface EquipmentStatePayload {
  type: 'EQUIPMENT_STATE';
  equipment_id: number;
  state: 'ON' | 'OFF';
}

export interface ControllerStatusPayload {
  type: 'CONTROLLER_STATUS';
  controller_id: number;
  status: 'ONLINE' | 'OFFLINE';
}

export type WsMessage = SensorReadingPayload | EquipmentStatePayload | ControllerStatusPayload;
