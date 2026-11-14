
from app.config import settings
from app.engines.vector_engine import VectorEngine
from app.engines.vision_engine import VisionEngine
from app.repositories.trademark_repository import TrademarkRepository
from app.services.embedding_service import EmbeddingService
from app.services.indexing_service import IndexingService


def main():

    print("=" * 60)
    print("MARKLENS AI - TRADEMARK INDEXING")
    print("=" * 60)

    repository = TrademarkRepository(
        settings.DATABASE_URL
    )

    vision_engine = VisionEngine(
        model_name=settings.CLIP_MODEL_NAME,
        pretrained=settings.CLIP_PRETRAINED,
    )

    vector_engine = VectorEngine(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection=settings.QDRANT_COLLECTION,
        dimension=settings.VECTOR_DIMENSION,
    )

    embedding_service = EmbeddingService(
        vision_engine
    )

    indexing_service = IndexingService(
        repository=repository,
        embedding_service=embedding_service,
        vector_engine=vector_engine,
        model_name=settings.CLIP_MODEL_NAME,
    )

    result = indexing_service.index_all(
        batch_size=50
    )

    print("\nINDEXING COMPLETED")
    print("-" * 60)
    print("Total trademarks:", result["total_trademarks"])
    print("Indexed images:", result["total_indexed_images"])

    for item in result["results"]:
        print(
            item["trademark_id"],
            item["status"],
            item["indexed_images"],
        )


if __name__ == "__main__":
    main()
