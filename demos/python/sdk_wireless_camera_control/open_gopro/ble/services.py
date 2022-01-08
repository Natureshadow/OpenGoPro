# services.py/Open GoPro, Version 2.0 (C) Copyright 2021 GoPro, Inc. (http://gopro.com/OpenGoPro).
# This copyright was auto-generated on Wed, Sep  1, 2021  5:05:50 PM

"""Objects to nicely interact with BLE services, characteristics, and attributes."""

from __future__ import annotations
import csv
import json
import logging
from pathlib import Path
from collections import Mapping
from enum import Enum, IntFlag, IntEnum
from dataclasses import dataclass, field, asdict
from typing import Dict, Iterator, Generator, List, Mapping, Optional, Union, Tuple, Type

logger = logging.getLogger(__name__)


class CharProps(IntFlag):
    NONE = 0x00
    BROADCAST = 0x01
    READ = 0x02
    WRITE_NO_RSP = 0x04
    WRITE_YES_RSP = 0x08
    NOTIFY = 0x10
    INDICATE = 0x20
    AUTH_SIGN_WRITE = 0x40
    EXTENDED = 0x80
    NOTIFY_ENCRYPTION_REQ = 0x100
    INDICATE_ENCRYPTION_REQ = 0x200


class SpecUuidNumber(IntEnum):
    PRIMARY_SERVICE = 0x2800
    SECONDARY_SERVICE = 0x2801
    INCLUDE = 0x2802
    CHAR_DECLARATION = 0x2803
    CHAR_EXTENDED_PROPS = 0x2900
    CHAR_USER_DESCR = 0x2901
    CLIENT_CHAR_CONFIG = 0x2902
    SERVER_CHAR_CONFIG = 0x2903
    CHAR_FORMAT = 0x2904
    CHAR_AGGREGATE_FORMAT = 0x2905


class UuidFormat(IntEnum):
    TWO_BYTE = 2
    SIXTEEN_BYTE = 16


@dataclass
class UUID:
    value: bytes
    name: str = ""

    def __str__(self) -> str:
        return self.as_string if self.name == "" else self.name

    def __repr__(self) -> str:
        return self.__str__()

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other: Union["UUID", int, bytes, str, IntEnum, Enum]) -> bool:
        if isinstance(other, UUID):
            return self.value == other.value
        elif isinstance(other, int):
            return self.as_int == other
        elif isinstance(other, bytes):
            return self.value == other
        elif isinstance(other, str):
            return self.as_string.replace(":", "").lower() == other.lower()
        else:
            return False

    @property
    def as_int(self) -> int:
        return int.from_bytes(self.value, "big")

    @property
    def as_string(self) -> str:
        return f"{self.value.hex()[:8]}-{self.value.hex()[8:12]}-{self.value.hex()[12:16]}-{self.value.hex()[16:20]}-{self.value.hex()[20:]}"

    @classmethod
    def from_int(cls, uuid: int, format: UuidFormat, name="") -> "UUID":
        return cls(int.to_bytes(uuid, format, "big"), name)

    @classmethod
    def normalize(cls, uuid: str) -> str:
        return uuid.replace(":", "").replace("-", "")

    @classmethod
    def from_string(cls, uuid: str, name="") -> "UUID":
        return cls(bytes.fromhex(UUID.normalize(uuid)), name)

    @classmethod
    def from_enum(cls, uuid: Enum) -> "UUID":
        return cls(uuid.value, str(uuid))


@dataclass
class Descriptor:
    """A charactersistic descriptor.
    Args:
        handle (int) : the handle of the attribute table that the descriptor resides at
        uuid (UUID): UUID of this descriptor
        value (bytes) : the byte stream value of the descriptor
    """

    handle: int
    uuid: UUID
    value: Optional[bytes] = None

    def __str__(self) -> str:  # pylint: disable=missing-return-doc
        return json.dumps(asdict(self), indent=4, default=str)


@dataclass
class Characteristic:
    """A BLE charactersistic.
    Args:
        handle (int) : the handle of the attribute table that the characteristic resides at
        descriptor_handle (int) : TODO
        uuid (UUID) : the UUID of the characteristic
        props (CharProps) : the characteristic's properties (READ, WRITE, NOTIFY, etc)
        name (str) : the characteristic's name
        value (bytes) : the current byte stream value of the characteristic value
        descriptors (List[Descriptor], optional) : Any relevant descriptors if they exist
    """

    handle: int
    descriptor_handle: int
    uuid: UUID
    props: CharProps
    name: str = ""
    value: Optional[bytes] = None
    descriptors: Dict[UUID, Descriptor] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.props = CharProps(int(self.props))
        if self.uuid.name == "":
            self.uuid.name = self.name


    def __str__(self) -> str:  # pylint: disable=missing-return-doc
        return f"UUID {str(self.uuid)} @ handle {self.handle}: {self.props}"

    @property
    def is_readable(self) -> bool:
        return CharProps.NOTIFY in self.props

    @property
    def is_writeable_with_response(self) -> bool:
        return CharProps.WRITE_YES_RSP in self.props

    @property
    def is_writeable_without_response(self) -> bool:
        return CharProps.WRITE_NO_RSP in self.props

    @property
    def is_writeable(self) -> bool:
        return self.is_writeable_with_response or self.is_writeable_without_response

    @property
    def is_notifiable(self) -> bool:
        return CharProps.NOTIFY in self.props

    @property
    def is_indicatable(self) -> bool:
        return CharProps.INDICATE in self.props

    @property
    def cccd_handle(self) -> int:
        return self.descriptors[UUID.from_int(SpecUuidNumber.CLIENT_CHAR_CONFIG, UuidFormat.TWO_BYTE)].handle


@dataclass
class Service:
    """A BLE service or grouping of Characteristics.
    Args:
        uuid (UUID) : the service's UUID
        start_handle(int): the attribute handle where the service begins
        end_handle(int): the attribute handle where the service ends
        name (str) : the service's name
        chars (Dict[str, Characteristic]) : the dictionary of characteristics, indexed by name
    """

    uuid: UUID
    start_handle: int
    name: str
    end_handle: int = 0xFFFF
    chars: Dict[UUID, Characteristic] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.uuid.name == "":
            self.uuid.name = self.name


class GattDB:
    """The attribute table to store / look up BLE services, characteristics, and attributes.
    Args:
        services (Dict[UUID, Service]): A dictionary of Services indexed by UUID.
        characteristics (Dict[UUID, Characteristic]): A dictionary of Characteristics indexed by UUID.
    """

    class CharacteristicView(Mapping):
        def __init__(self, db: "GattDB"):
            self._db = db

        def __getitem__(self, key: UUID):
            for service in self._db.services.values():
                for char in service.chars.values():
                    if char.uuid == key:
                        return char
            raise KeyError

        def __contains__(self, key):
            for service in self._db.services.values():
                for char in service.chars.values():
                    if char.uuid == key:
                        return True
            return False

        def __iter__(self) -> Iterator[UUID]:
            # keys = []
            # for service in self._db.services.values():
            #     keys.extend(service.chars.keys())
            # return iter(keys)
            return self.keys()

        def __len__(self):
            return sum(len(service.chars) for service in self._db.services.values())

        def keys(self) -> Generator[UUID, None, None]:
            def iter_keys():
                for service in self._db.services.values():
                    for uuid in service.chars.keys():
                        yield uuid

            return iter_keys()

        def values(self) -> Generator[Characteristic, None, None]:
            def iter_values():
                for service in self._db.services.values():
                    for char in service.chars.values():
                        yield char

            return iter_values()

        def items(self) -> Generator[Tuple[UUID, Characteristic], None, None]:
            def iter_items():
                for service in self._db.services.values():
                    for uuid, char in service.chars.items():
                        yield (uuid, char)

            return iter_items()

    def __init__(self, services: Dict[UUID, Service]) -> None:
        self.services: Dict[UUID, Service] = services
        self.characteristics = self.CharacteristicView(self)

    def handle2uuid(self, handle: int) -> UUID:
        """Get a UUID from a handle.
        Args:
            handle (int): the handle to search for
        Raises:
            Exception: No characteristic was found at this handle
        Returns:
            UUID: The found UUID
        """
        for s in self.services.values():
            for c in s.chars.values():
                if c.handle == handle:
                    return c.uuid
        raise Exception(f"Matching UUID not found for handle {handle}")

    def uuid2handle(self, uuid: UUID) -> int:
        return self.characteristics[uuid].handle

    def dump_to_csv(self, file: Path = Path("attributes.csv")) -> None:
        """Dump discovered services to a csv file.
        Args:
            file (Path, optional): File to write to. Defaults to "./attributes.csv".
        """
        with open(file, mode="w") as f:
            logger.debug(f"Dumping discovered BLE characteristics to {file}")

            w = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
            w.writerow(["handle", "description", "UUID", "properties", "value"])

            # For each service in table
            for service in self.services.values():  # type: ignore
                desc = "unknown" if service.name == "" else service.name
                w.writerow(
                    [
                        service.start_handle,
                        SpecUuidNumber.PRIMARY_SERVICE,
                        service.uuid.as_string,
                        desc,
                        "SERVICE",
                    ]
                )
                # For each characteristic in service
                for char in service.chars.values():
                    w.writerow(
                        [char.descriptor_handle, SpecUuidNumber.CHAR_DECLARATION, "28:03", str(char.props), ""]
                    )
                    description = "unknown" if char.name == "" else char.name
                    w.writerow([char.handle, description, char.uuid.as_string, "", char.value])
                    # For each descriptor in characteristic
                    for descriptor in char.descriptors.values():
                        description = SpecUuidNumber(descriptor.uuid.as_int)
                        w.writerow(
                            [descriptor.handle, description, descriptor.uuid.as_string, "", descriptor.value]
                        )


class UUIDsMeta(type):
    def __new__(cls, name, bases, dct):
        x = super().__new__(cls, name, bases, dct)
        x._uuids: Dict[uuid, str] = {}
        uuid: UUID
        for _, uuid in [(k, v) for k, v in dct.items() if not k.startswith("__")]:
            x._uuids[uuid] = uuid.name
        return x

    def __getitem__(self, key: UUID) -> str:
        return self._uuids[key]

    def __contains__(self, uuid: UUID) -> bool:
        return uuid in self._uuids.keys()

    def __iter__(self):
        for item in self._uuids.items():
            yield item


@dataclass(frozen=True)
class UUIDs(metaclass=UUIDsMeta):
    """BLE Spec-defined UUIDs that are common across all applications."""

    def __new__(cls: Type[UUIDs]) -> Type[UUIDs]:
        raise Exception("This class shall not be instantiated")

    # Generic Attribute Service
    S_GENERIC_ATT: UUID = UUID.from_string("00001801-0000-1000-8000-00805f9b34fb", "Generic Attribute Service")

    # Generic Access Service
    S_GENERIC_ACCESS: UUID = UUID.from_string("00001800-0000-1000-8000-00805f9b34fb", "Generic Access Service")
    ACC_DEVICE_NAME: UUID = UUID.from_string("00002a00-0000-1000-8000-00805f9b34fb", "Device Name")
    ACC_APPEARANCE: UUID = UUID.from_string("00002a01-0000-1000-8000-00805f9b34fb", "Appearance")
    ACC_PREF_CONN_PARAMS: UUID = UUID.from_string(
        "00002a04-0000-1000-8000-00805f9b34fb", "Peripheral Preferred Connection Parameters"
    )
    ACC_CENTRAL_ADDR_RES: UUID = UUID.from_string(
        "00002aa6-0000-1000-8000-00805f9b34fb", "Central Address Resolution"
    )

    # Tx Power
    S_TX_POWER: UUID = UUID.from_string("00001804-0000-1000-8000-00805f9b34fb", "Tx Power Service")
    TX_POWER_LEVEL: UUID = UUID.from_string("00002a07-0000-1000-8000-00805f9b34fb", "Tx Power Level")

    # Battery Service
    S_BATTERY: UUID = UUID.from_string("0000180f-0000-1000-8000-00805f9b34fb", "Battery Service")
    BATT_LEVEL: UUID = UUID.from_string("00002a19-0000-1000-8000-00805f9b34fb", "Battery Level")

    # Device Information Service
    S_DEV_INFO: UUID = UUID.from_string("0000180a-0000-1000-8000-00805f9b34fb", "Device Information Service")
    INF_MAN_NAME: UUID = UUID.from_string("00002a29-0000-1000-8000-00805f9b34fb", "Manufacturer Name")
    INF_MODEL_NUM: UUID = UUID.from_string("00002a24-0000-1000-8000-00805f9b34fb", "Model Number")
    INF_SERIAL_NUM: UUID = UUID.from_string("00002a25-0000-1000-8000-00805f9b34fb", "Serial Number")
    INF_FW_REV: UUID = UUID.from_string("00002a26-0000-1000-8000-00805f9b34fb", "Firmware Revision")
    INF_HW_REV: UUID = UUID.from_string("00002a27-0000-1000-8000-00805f9b34fb", "Hardware Revision")
    INF_SW_REV: UUID = UUID.from_string("00002a28-0000-1000-8000-00805f9b34fb", "Software Revision")
    INF_SYS_ID: UUID = UUID.from_string("00002a23-0000-1000-8000-00805f9b34fb", "System ID")
    INF_CERT_DATA: UUID = UUID.from_string("00002a2a-0000-1000-8000-00805f9b34fb", "Certification Data")
    INF_PNP_ID: UUID = UUID.from_string("00002a50-0000-1000-8000-00805f9b34fb", "PNP ID")
