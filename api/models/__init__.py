"""
Modèles SQLAlchemy. Tous sont importés ici pour être enregistrés dans
Base.metadata (create_all, relations par nom) et importables via « from models import X ».
"""
# ruff: noqa: F401

from .aquarium import Aquarium
from .coral import Coral
from .photo import Photo
from .plant import Plant
from .user import User
from .fish import Fish
from .refresh_token import RefreshToken
from .equipment import Equipment
from .sensor import Sensor
from .controller import Controller
from .controller_pin import ControllerPin
from .invertebrate import Invertebrate
from .sensor_reading import SensorReading
from .light import Light
from .light_channel import LightChannel
from .light_schedule import LightSchedule
from .io_module import IoModule
from .rule import Rule
from .rule_condition import RuleCondition
from .equipment_group import EquipmentGroup
from .logs import LogModel
from .fault import EquipmentFault
from .dashboard_card import DashboardCard
from .equipment_activation import EquipmentActivation
from .water_parameter import WaterParameter, WaterParameterReading, IcpImportBatch
from .maintenance_task import MaintenanceTask, MaintenanceTaskCompletion
from .inventory import InventoryItem, InventoryMovement
from .metric_alert import MetricAlert
from .species import FishSpecies, CoralSpecies, PlantSpecies, InvertebrateSpecies
from .catalog_sync import CatalogSyncState
from .notification_settings import NotificationSettings
from .audit_log import AuditLog
from .frag import Frag, FragMovement
from pro.models.transfer_certificate import SaleLocation, TransferCertificate, TransferCertificateItem, SellerProfile
from pro.models.showcase import ShowcaseSettings, ShowcaseReservation
from .idempotency import IdempotencyRecord
from .push_subscription import PushSubscription
from .equipment_usage import EquipmentUsage, EnergySettings
from .assistant import AssistantSettings
from .purchase_document import PurchaseDocument, PurchaseDocumentFile, PurchaseDocumentLink
from .parameter_share import ParameterShareLink
from .group_order import GroupOrderLink, GroupOrderSettings
from .journal import JournalEntry
from .water_change import WaterChange
from .dosing import DosingProduct
from .backup_settings import BackupSettings
from .camera import Camera
from .license import AppLicense
