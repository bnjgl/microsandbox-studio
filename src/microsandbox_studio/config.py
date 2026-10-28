from typing import Any

from pydantic import BaseModel, ConfigDict


class _Stored(BaseModel):
    model_config = ConfigDict(extra="ignore")


class EnvVar(_Stored):
    key: str
    value: str


class StoredResources(_Stored):
    cpus: int
    memory_mib: int


class Runtime(_Stored):
    workdir: str | None = None


class Mount(_Stored):
    type: str
    guest: str
    host: str | None = None


class PublishedPort(_Stored):
    host_port: int
    guest_port: int


class SecretSource(_Stored):
    kind: str
    var: str | None = None


class StoredSecret(_Stored):
    env_var: str
    value: str = ""
    source: SecretSource | None = None
    allowed_hosts: list[str | dict[str, str]] = []

    @property
    def hosts(self) -> list[str]:
        return [
            "*" if host == "any" else host if isinstance(host, str) else next(iter(host.values()))
            for host in self.allowed_hosts
        ]


class Secrets(_Stored):
    secrets: list[StoredSecret] = []


class StoredNetwork(_Stored):
    ports: list[PublishedPort] = []
    secrets: Secrets = Secrets()


class StoredConfig(_Stored):
    image: dict[str, dict[str, Any]]
    env: list[EnvVar]
    resources: StoredResources
    runtime: Runtime
    mounts: list[Mount]
    network: StoredNetwork
    labels: dict[str, str]

    @property
    def oci_reference(self) -> str | None:
        return (self.image.get("Oci") or {}).get("reference")

    @property
    def image_label(self) -> str:
        variant = next(iter(self.image.values()), {})
        return variant.get("reference") or variant.get("path") or "—"
