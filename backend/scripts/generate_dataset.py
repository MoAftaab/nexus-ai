"""Generate inspectable synthetic datasets without starting the HTTP server."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dataset_export import export_dataset
from app.services.seed import generate_dataset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create context-relevant NexusAI datasets.")
    parser.add_argument("--seed", type=int, default=None, help="Optional reproducible data seed")
    options = parser.parse_args()
    dataset = generate_dataset(options.seed)
    export_dataset(dataset)
    print(f"Generated synthetic operation with seed {dataset.seed} into backend/datasets")
