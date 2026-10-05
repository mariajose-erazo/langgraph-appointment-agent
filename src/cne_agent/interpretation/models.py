"""Modelos de lo expresado en el turno conversacional actual.

Estos modelos conservan el texto original y no resuelven identidades,
fechas, horas ni disponibilidad.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TurnIntent(StrEnum):
    INFORMATION_QUERY = "information_query"
    CHECK_AVAILABILITY = "check_availability"
    BOOK_APPOINTMENT = "book_appointment"
    MODIFY_APPOINTMENT = "modify_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"


class ChangeOperation(StrEnum):
    ADD = "add"
    REMOVE = "remove"
    SET = "set"
    CLEAR = "clear"


class AppointmentField(StrEnum):
    SERVICES = "services"
    PROFESSIONAL = "professional"
    DATE = "date"
    TIME = "time"
    REMOVAL = "removal"


class InterpretedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: AppointmentField
    operation: ChangeOperation
    raw_text: str | None = None
    raw_values: list[str] = Field(default_factory=list)
    suggested_id: str | None = None

    @model_validator(mode="after")
    def validate_change(self) -> Self:
        allowed_operations = {
            AppointmentField.SERVICES: {
                ChangeOperation.ADD,
                ChangeOperation.REMOVE,
                ChangeOperation.SET,
                ChangeOperation.CLEAR,
            },
            AppointmentField.PROFESSIONAL: {
                ChangeOperation.SET,
                ChangeOperation.CLEAR,
            },
            AppointmentField.DATE: {
                ChangeOperation.SET,
                ChangeOperation.CLEAR,
            },
            AppointmentField.TIME: {
                ChangeOperation.SET,
                ChangeOperation.CLEAR,
            },
            AppointmentField.REMOVAL: {
                ChangeOperation.SET,
                ChangeOperation.CLEAR,
            },
        }
        if self.operation not in allowed_operations[self.field]:
            raise ValueError(
                f"{self.operation.value} no es compatible con "
                f"{self.field.value}"
            )

        if self.operation is ChangeOperation.CLEAR:
            if (
                self.raw_text is not None
                or self.raw_values
                or self.suggested_id is not None
            ):
                raise ValueError(
                    "CLEAR no admite raw_text, raw_values ni suggested_id"
                )
            return self

        if self.raw_text is None or not self.raw_text.strip():
            raise ValueError(
                "ADD, REMOVE y SET requieren raw_text no vacío"
            )

        if self.field is AppointmentField.SERVICES:
            for raw_value in self.raw_values:
                if not raw_value.strip():
                    raise ValueError(
                        "raw_values no puede contener valores vacíos"
                    )
            if (
                self.operation in {
                    ChangeOperation.ADD,
                    ChangeOperation.REMOVE,
                }
                and len(self.raw_values) > 1
            ):
                raise ValueError(
                    "ADD y REMOVE admiten como máximo un raw_value"
                )
        elif self.raw_values:
            raise ValueError(
                "raw_values solo puede usarse con services"
            )

        if self.suggested_id is not None:
            if not self.suggested_id.strip():
                raise ValueError("suggested_id no puede estar vacío")
            if self.field is not AppointmentField.PROFESSIONAL:
                raise ValueError(
                    "suggested_id solo puede usarse con professional"
                )

        return self


class InterpretedAmbiguity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: AppointmentField
    description: str

    @model_validator(mode="after")
    def validate_description(self) -> Self:
        if not self.description.strip():
            raise ValueError("description no puede estar vacía")
        return self


class TurnInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intents: list[TurnIntent] = Field(default_factory=list)
    appointment_changes: list[InterpretedChange] = Field(
        default_factory=list
    )
    information_queries: list[str] = Field(default_factory=list)
    ambiguities: list[InterpretedAmbiguity] = Field(default_factory=list)
