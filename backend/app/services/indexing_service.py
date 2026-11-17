
import os
from pathlib import Path

from qdrant_client import models


class IndexingService:

    def __init__(
        self,
        repository,
        embedding_service,
        vector_engine,
        model_name,
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.vector_engine = vector_engine
        self.model_name = model_name

    @staticmethod
    def read_image(storage_path):
        path = Path(storage_path).expanduser()

        if not path.is_file():
            raise FileNotFoundError(
                f"Image file not found: {path}"
            )

        return path.read_bytes()

    def index_trademark(self, trademark):
        trademark_id = trademark["id"]

        images = self.repository.get_trademark_images(
            trademark_id
        )

        if not images:
            return {
                "trademark_id": trademark_id,
                "status": "skipped",
                "reason": "No image records",
                "indexed_images": 0,
            }

        indexed = 0
        errors = []

        for image in images:
            storage_path = image.get("storage_path")

            if not storage_path:
                errors.append({
                    "image_id": image["id"],
                    "reason": "No local storage_path",
                })
                continue

            try:
                image_bytes = self.read_image(
                    storage_path
                )

                result = self.embedding_service.generate(
                    image_bytes
                )

                point_id = int(image["id"])

                payload = {
                    "trademark_id": trademark_id,
                    "image_id": image["id"],
                    "name": trademark["name"],
                    "registration_number": trademark.get(
                        "registration_number"
                    ),
                    "application_number": trademark.get(
                        "application_number"
                    ),
                    "jurisdiction": trademark.get(
                        "jurisdiction"
                    ),
                    "nice_classes": trademark.get(
                        "nice_classes"
                    ) or [],
                    "image_url": trademark.get(
                        "image_url"
                    ),
                    "image_hash": result["image_hash"],
                    "model_name": self.model_name,
                }

                self.vector_engine.client.upsert(
                    collection_name=self.vector_engine.collection,
                    points=[
                        models.PointStruct(
                            id=point_id,
                            vector=result["vector"],
                            payload=payload,
                        )
                    ],
                    wait=True,
                )

                self.repository.save_embedding(
                    trademark_id=trademark_id,
                    image_id=image["id"],
                    point_id=point_id,
                    model_name=self.model_name,
                    dimension=result["dimension"],
                    image_hash=result["image_hash"],
                    qdrant_collection=self.vector_engine.collection,
                )

                indexed += 1

            except Exception as exc:
                errors.append({
                    "image_id": image["id"],
                    "reason": str(exc),
                })

        return {
            "trademark_id": trademark_id,
            "name": trademark["name"],
            "status": "indexed" if indexed else "failed",
            "indexed_images": indexed,
            "errors": errors,
        }

    def index_all(self, batch_size=50):
        self.vector_engine.ensure_collection()

        offset = 0
        total_records = 0
        total_indexed = 0
        results = []

        while True:
            trademarks = self.repository.get_trademarks(
                limit=batch_size,
                offset=offset,
            )

            if not trademarks:
                break

            for trademark in trademarks:
                total_records += 1

                result = self.index_trademark(
                    trademark
                )

                total_indexed += result["indexed_images"]
                results.append(result)

            offset += batch_size

        return {
            "total_trademarks": total_records,
            "total_indexed_images": total_indexed,
            "results": results,
        }
