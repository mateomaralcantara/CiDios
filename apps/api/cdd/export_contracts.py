"""Exporta los contratos versionados a packages/contracts/*.schema.json"""
import json

from .experience.contracts import PACKET_VERSION, SPEC_VERSION, ExperienceSpec, KnowledgePacket
from .paths import repo_root

if __name__ == "__main__":
    OUT = repo_root() / "packages" / "contracts"
    OUT.mkdir(parents=True, exist_ok=True)
    for name, model, ver in (("knowledge-packet", KnowledgePacket, PACKET_VERSION), ("experience-spec", ExperienceSpec, SPEC_VERSION)):
        schema = model.model_json_schema()
        schema["$id"] = f"https://cienciaydios.org/contracts/{name}/{ver}"
        schema["x-version"] = ver
        (OUT / f"{name}.schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("→", name, ver)
