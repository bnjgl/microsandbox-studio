import re
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)


class Port(BaseModel):
    host: int = Field(ge=1, le=65535)
    guest: int = Field(ge=1, le=65535)


class NetworkSettings(BaseModel):
    mode: Literal["none", "internet", "all"] = "internet"
    ports: list[Port] = []

    @field_validator("ports")
    @classmethod
    def _one_per_host_port(cls, ports: list[Port]) -> list[Port]:
        if len({port.host for port in ports}) < len(ports):
            raise ValueError("each host port can only be published once")
        return ports


Name = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
Text = Annotated[str, StringConstraints(pattern=r"^[^\x00]*$")]


class SecretSettings(BaseModel):
    value: Annotated[Text, Field(min_length=1)]
    allow: list[str]

    @field_validator("allow")
    @classmethod
    def _hosts(cls, allow: list[str]) -> list[str]:
        if not (hosts := [host.strip() for host in allow if host.strip()]):
            raise ValueError("enter at least one allowed host")
        return hosts


class EnvironmentSettings(BaseModel):
    env: dict[Name, Text] = {}
    secrets: dict[Name, SecretSettings] = {}

    @model_validator(mode="after")
    def _check(self) -> Self:
        if both := self.env.keys() & self.secrets.keys():
            raise ValueError(f"{', '.join(sorted(both))}: both a variable and a secret")
        return self


def _existing_folder(source: str) -> str:
    try:
        path = Path(source).resolve(strict=True)
    except OSError as error:
        raise ValueError(f"folder not found: {source}") from error
    if not path.is_dir():
        raise ValueError(f"not a folder: {path}")
    return str(path)


Folders = Annotated[
    list[Annotated[str, AfterValidator(_existing_folder)]],
    AfterValidator(lambda folders: list(dict.fromkeys(folders))),
]
FOLDERS = TypeAdapter(Folders)


class Resources(BaseModel):
    cpus: int = Field(ge=1)
    memory: int = Field(ge=1)


class NewSandbox(Resources):
    name: str = Field(min_length=1)
    image: str = Field(min_length=1)
    folders: Folders = []
    environment: EnvironmentSettings = Field(default_factory=EnvironmentSettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)


_SSH_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


def is_ssh_name(name: str) -> bool:
    return bool(_SSH_NAME.fullmatch(name))
