
import math
from collections.abc import Mapping
from itertools import islice

from qdrant_client import QdrantClient, models


class VectorEngine:
    MAX_SEARCH_LIMIT = 10
    DEFAULT_UPSERT_BATCH_SIZE = 256
    DEFAULT_SEARCH_BATCH_SIZE = 32

    def __init__(
        self,
        url,
        api_key,
        collection,
        dimension=512,
        similarity_threshold=None,
    ):
        if (
            not isinstance(dimension, int)
            or isinstance(dimension, bool)
            or dimension < 1
        ):
            raise ValueError("dimension must be a positive integer.")
        if not collection or not isinstance(collection, str):
            raise ValueError("collection must be a non-empty string.")

        self.collection = collection
        self.dimension = dimension
        self.similarity_threshold = self._validate_threshold(
            similarity_threshold
        )

        self.client = QdrantClient(
            url=url,
            api_key=api_key or None,
            timeout=30,
            check_compatibility=False,
        )

    def ensure_collection(self):
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(
                    size=self.dimension,
                    distance=models.Distance.COSINE,
                ),
            )

    @staticmethod
    def _validate_threshold(threshold):
        if threshold is None:
            return None

        if isinstance(threshold, bool):
            raise ValueError(
                "similarity_threshold must be between 0 and 100."
            )

        try:
            threshold = float(threshold)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "similarity_threshold must be between 0 and 100."
            ) from exc

        if not math.isfinite(threshold) or not 0 <= threshold <= 100:
            raise ValueError(
                "similarity_threshold must be between 0 and 100."
            )

        return threshold

    def _validated_vector(self, vector):
        if isinstance(vector, (str, bytes, bytearray)):
            raise ValueError("Vector must be a numeric sequence.")

        try:
            values = [float(value) for value in vector]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Vector must be a numeric sequence.") from exc

        if len(values) != self.dimension:
            raise ValueError(
                f"Vector dimension must be {self.dimension}; "
                f"received {len(values)}."
            )

        if not all(math.isfinite(value) for value in values):
            raise ValueError("Vector values must all be finite.")

        norm = math.hypot(*values)
        if norm == 0:
            raise ValueError("Vector must not be all zeroes.")

        return [value / norm for value in values]

    @staticmethod
    def _validated_batch_size(batch_size, name):
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size < 1
        ):
            raise ValueError(f"{name} must be a positive integer.")

        return batch_size

    def _effective_limit(self, limit):
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit < 1
        ):
            raise ValueError("limit must be a positive integer.")

        return min(limit, self.MAX_SEARCH_LIMIT)

    def _effective_threshold(self, similarity_threshold):
        threshold = (
            self.similarity_threshold
            if similarity_threshold is None
            else self._validate_threshold(similarity_threshold)
        )

        return threshold / 100 if threshold is not None else None

    @staticmethod
    def _format_results(points):
        results = []

        for point in points:
            payload = point.payload or {}
            score = float(point.score)
            if not math.isfinite(score):
                raise ValueError(
                    "Qdrant returned a non-finite similarity score."
                )

            results.append({
                "id": str(point.id),
                "score": round(max(0.0, min(1.0, score)) * 100, 2),
                "trademark_id": payload.get("trademark_id"),
                "name": payload.get("name"),
                "registration_number": payload.get(
                    "registration_number"
                ),
                "application_number": payload.get(
                    "application_number"
                ),
                "jurisdiction": payload.get("jurisdiction"),
                "nice_classes": payload.get("nice_classes", []),
                "image_url": payload.get("image_url"),
                "image_hash": payload.get("image_hash"),
            })

        return results

    def search(
        self,
        vector,
        limit=10,
        similarity_threshold=None,
    ):
        query_vector = self._validated_vector(vector)
        response = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=self._effective_limit(limit),
            with_payload=True,
            score_threshold=self._effective_threshold(
                similarity_threshold
            ),
        )

        return self._format_results(response.points)

    def search_batch(
        self,
        vectors,
        limit=10,
        similarity_threshold=None,
        batch_size=DEFAULT_SEARCH_BATCH_SIZE,
    ):
        batch_size = self._validated_batch_size(batch_size, "batch_size")
        limit = self._effective_limit(limit)
        score_threshold = self._effective_threshold(similarity_threshold)

        try:
            vector_iterator = iter(vectors)
        except TypeError as exc:
            raise TypeError("vectors must be an iterable of vectors.") from exc

        results = []
        while True:
            vector_batch = list(islice(vector_iterator, batch_size))
            if not vector_batch:
                break

            requests = [
                models.QueryRequest(
                    query=self._validated_vector(vector),
                    limit=limit,
                    with_payload=True,
                    score_threshold=score_threshold,
                )
                for vector in vector_batch
            ]
            responses = self.client.query_batch_points(
                collection_name=self.collection,
                requests=requests,
            )

            if len(responses) != len(requests):
                raise RuntimeError(
                    "Qdrant returned an unexpected number of batch results."
                )

            results.extend(
                self._format_results(response.points)
                for response in responses
            )

        return results

    def upsert(self, point_id, vector, payload=None, wait=True):
        if point_id is None:
            raise ValueError("point_id is required.")
        if payload is not None and not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping or None.")

        point = models.PointStruct(
            id=point_id,
            vector=self._validated_vector(vector),
            payload=dict(payload) if payload is not None else None,
        )

        return self.client.upsert(
            collection_name=self.collection,
            points=[point],
            wait=wait,
        )

    def upsert_batch(
        self,
        points,
        batch_size=DEFAULT_UPSERT_BATCH_SIZE,
        wait=True,
    ):
        batch_size = self._validated_batch_size(batch_size, "batch_size")

        try:
            point_iterator = iter(points)
        except TypeError as exc:
            raise TypeError(
                "points must be an iterable of point mappings."
            ) from exc

        updates = []
        while True:
            point_batch = list(islice(point_iterator, batch_size))
            if not point_batch:
                break

            validated_points = []
            for point in point_batch:
                if isinstance(point, Mapping):
                    if "id" not in point or "vector" not in point:
                        raise ValueError(
                            "Each point mapping must include 'id' and 'vector'."
                        )
                    point_id = point["id"]
                    vector = point["vector"]
                    payload = point.get("payload")
                elif isinstance(point, models.PointStruct):
                    point_id = point.id
                    vector = point.vector
                    payload = point.payload
                else:
                    raise TypeError(
                        "Each point must be a mapping or Qdrant PointStruct."
                    )

                if point_id is None:
                    raise ValueError("Each point must have an id.")
                if payload is not None and not isinstance(payload, Mapping):
                    raise TypeError("Point payload must be a mapping or None.")

                validated_points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=self._validated_vector(vector),
                        payload=dict(payload) if payload is not None else None,
                    )
                )

            updates.append(
                self.client.upsert(
                    collection_name=self.collection,
                    points=validated_points,
                    wait=wait,
                )
            )

        return updates

    def retrieve(self, point_ids, with_vectors=True):
        try:
            point_ids = list(point_ids)
        except TypeError as exc:
            raise TypeError("point_ids must be an iterable.") from exc

        if not point_ids:
            return []

        points = self.client.retrieve(
            collection_name=self.collection,
            ids=point_ids,
            with_payload=True,
            with_vectors=with_vectors,
        )

        return [
            {
                "id": str(point.id),
                "vector": point.vector,
                "payload": point.payload or {},
            }
            for point in points
        ]

    def find_duplicate(self, image_hash):
        if not isinstance(image_hash, str) or not image_hash.strip():
            raise ValueError("image_hash must be a non-empty string.")

        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="image_hash",
                        match=models.MatchValue(value=image_hash),
                    )
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            return None

        point = points[0]
        return {
            "id": str(point.id),
            "payload": point.payload or {},
        }
