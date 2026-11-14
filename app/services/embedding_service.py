import hashlib
import math
from itertools import islice

import torch


class EmbeddingService:
    DEFAULT_BATCH_SIZE = 32

    def __init__(self, vision_engine):
        self.vision_engine = vision_engine

    @staticmethod
    def _image_bytes(image_bytes):
        if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
            raise TypeError("Image content must be bytes-like.")

        image_bytes = bytes(image_bytes)
        if not image_bytes:
            raise ValueError("Image content is empty.")

        return image_bytes

    @staticmethod
    def _validated_vector(vector):
        if isinstance(vector, (str, bytes, bytearray)):
            raise ValueError("Vision engine returned an invalid embedding.")

        try:
            values = [float(value) for value in vector]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "Vision engine returned an invalid embedding."
            ) from exc

        if not values or not all(math.isfinite(value) for value in values):
            raise ValueError(
                "Vision engine returned an empty or non-finite embedding."
            )

        norm = math.hypot(*values)
        if norm == 0:
            raise ValueError("Vision engine returned a zero embedding.")

        return [value / norm for value in values]

    def _encode_unique_images(self, image_bytes):
        batch_encoder = getattr(self.vision_engine, "encode_images", None)
        if callable(batch_encoder):
            vectors = list(batch_encoder(image_bytes))
            if len(vectors) != len(image_bytes):
                raise ValueError(
                    "Vision engine returned an unexpected number of embeddings."
                )
        elif all(
            hasattr(self.vision_engine, attribute)
            for attribute in ("prepare_image", "preprocess", "model", "device")
        ):
            images = [
                self.vision_engine.prepare_image(image)
                for image in image_bytes
            ]
            tensors = [
                self.vision_engine.preprocess(image)
                for image in images
            ]
            image_tensor = torch.stack(tensors).to(
                self.vision_engine.device
            )

            with torch.inference_mode():
                features = self.vision_engine.model.encode_image(image_tensor)

            vectors = features.float().cpu().numpy().tolist()
            if len(vectors) != len(image_bytes):
                raise ValueError(
                    "Vision engine returned an unexpected number of embeddings."
                )
        else:
            vectors = [
                self.vision_engine.encode_image(image)
                for image in image_bytes
            ]

        return [self._validated_vector(vector) for vector in vectors]

    def generate(self, image_bytes):
        return self.generate_batch([image_bytes], batch_size=1)[0]

    def generate_batch(
        self,
        images,
        batch_size=DEFAULT_BATCH_SIZE,
    ):
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size < 1
        ):
            raise ValueError("batch_size must be a positive integer.")

        try:
            image_iterator = iter(images)
        except TypeError as exc:
            raise TypeError("images must be an iterable of image bytes.") from exc

        results = []
        while True:
            image_batch = list(islice(image_iterator, batch_size))
            if not image_batch:
                break

            prepared_images = [
                self._image_bytes(image)
                for image in image_batch
            ]

            unique_images = []
            hash_to_index = {}
            image_hashes = []

            for image in prepared_images:
                image_hash = hashlib.sha256(image).hexdigest()
                image_hashes.append(image_hash)

                if image_hash not in hash_to_index:
                    hash_to_index[image_hash] = len(unique_images)
                    unique_images.append(image)

            unique_vectors = self._encode_unique_images(unique_images)
            vectors_by_hash = {
                image_hash: unique_vectors[index]
                for image_hash, index in hash_to_index.items()
            }

            for image_hash in image_hashes:
                vector = vectors_by_hash[image_hash]
                results.append({
                    "vector": vector.copy(),
                    "image_hash": image_hash,
                    "dimension": len(vector),
                })

        return results
