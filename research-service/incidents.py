"""Validated incident requests shared by HTTP handlers and deterministic schedules."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from traffic import NODES, PAIRS


class IncidentRequest(BaseModel):
    kind: Literal['accident', 'closure', 'congestion', 'readback', 'write', 'configuration', 'partition', 'pedestrian']
    controller: str | None = None
    edge: list[str] | None = None
    lane: int = Field(default=0, ge=0, le=0)
    position: float = Field(default=0.5, ge=0, le=1)
    duration: float | None = Field(default=None, gt=0, le=600)
    intensity: float = Field(default=0.7, ge=0.1, le=0.95)
    trigger: Literal['now', 'time', 'approach'] = 'now'
    at: float | None = Field(default=None, ge=0, le=600)
    junction: str | None = None
    distance: float = Field(default=30, ge=1, le=300)

    @model_validator(mode='after')
    def locations(self):
        if self.kind in ('accident', 'closure', 'congestion'):
            if not self.edge or len(self.edge) != 2 or tuple(self.edge) not in directed_edges():
                raise ValueError('Choose a directed road in this network')
        elif self.controller not in NODES or not self.controller.startswith('J'):
            raise ValueError('Choose a known controller')
        if self.trigger == 'time' and self.at is None:
            raise ValueError('Simulation time is required')
        if self.trigger == 'approach' and (self.junction not in NODES or not self.junction.startswith('J')):
            raise ValueError('Approach trigger requires a known junction')
        if self.kind == 'pedestrian' and self.duration is None:
            self.duration = 8
        return self


def directed_edges():
    return [(x, y) for a, b in PAIRS for x, y in ((a, b), (b, a))]
