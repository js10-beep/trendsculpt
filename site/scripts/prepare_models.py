"""Install the trusted, offline-trained reference artifact without network access."""

import hashlib, json, pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
metadata = json.loads(
    (ROOT / "server/reference-data/artifact-manifest.json").read_text()
)
artifact = ROOT / metadata["artifact"]
if hashlib.sha256(artifact.read_bytes()).hexdigest() != metadata["sha256"]:
    raise RuntimeError(
        "Reference model artifact checksum mismatch; retrain or restore trusted assets."
    )
destination = ROOT / ".models"
destination.mkdir(exist_ok=True)
shutil.copyfile(artifact, destination / "models.joblib")
if "--skip-metadata" not in sys.argv:
    (ROOT / "src/model-data.json").write_text(json.dumps(metadata, indent=2) + "\n")
print("Checksum-verified offline models installed:", metadata["version"])
