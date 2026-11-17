import logging
import ssl
import threading

from contextlib import asynccontextmanager
from urllib.parse import urlparse, parse_qs, unquote
from uuid import uuid4
from typing import Any

import pg8000.dbapi

from fastapi import (
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile,
)

from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.config import settings

from app.engines.vector_engine import VectorEngine


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("apexiveai")


# =========================================================
# GLOBAL SERVICES
# =========================================================

database_ready = False

trademark_primary_key = None

trademark_columns: set[str] = set()

vector_engine = None

vision_engine = None

vector_engine_lock = threading.Lock()

vision_engine_lock = threading.Lock()


# =========================================================
# POSTGRESQL CONNECTION
# =========================================================

def get_database_connection():

    parsed = urlparse(settings.DATABASE_URL)

    if not parsed.hostname or not parsed.username:
        raise RuntimeError(
            "Invalid PostgreSQL DATABASE_URL."
        )

    if not parsed.path or parsed.path == "/":
        raise RuntimeError(
            "PostgreSQL database name is missing."
        )

    query_params = parse_qs(parsed.query)

    sslmode = query_params.get(
        "sslmode",
        ["prefer"],
    )[0]

    ssl_context = None

    if sslmode != "disable":

        ssl_context = ssl.create_default_context()

        if sslmode == "require":
            ssl_context.check_hostname = False

        elif sslmode == "verify-ca":
            ssl_context.check_hostname = False

    connection = pg8000.dbapi.connect(
        user=unquote(parsed.username),
        password=unquote(parsed.password or ""),
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=unquote(parsed.path.lstrip("/")),
        ssl_context=ssl_context,
        timeout=30,
    )

    return connection


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():

    global database_ready
    global trademark_primary_key
    global trademark_columns

    connection = get_database_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (
                settings.DATABASE_SCHEMA,
                settings.DATABASE_TABLE,
            ),
        )

        trademark_columns = {
            row[0]
            for row in cursor.fetchall()
        }

        if not trademark_columns:

            raise RuntimeError(
                f"Required database table "
                f"'{settings.DATABASE_SCHEMA}."
                f"{settings.DATABASE_TABLE}' "
                f"does not exist or has no visible columns."
            )

        if "id" in trademark_columns:

            trademark_primary_key = "id"

        elif "trademark_id" in trademark_columns:

            trademark_primary_key = "trademark_id"

        else:

            raise RuntimeError(
                "Trademark table requires an id "
                "or trademark_id column."
            )

        cursor.execute("SELECT 1")

        cursor.fetchone()

        database_ready = True

        logger.info(
            "PostgreSQL connected successfully."
        )

        logger.info(
            "Trademark table: %s.%s",
            settings.DATABASE_SCHEMA,
            settings.DATABASE_TABLE,
        )

        logger.info(
            "Trademark primary key: %s",
            trademark_primary_key,
        )

        logger.info(
            "Trademark columns: %s",
            sorted(trademark_columns),
        )

    finally:

        connection.close()


# =========================================================
# DATABASE RECORD LOOKUP
# =========================================================

def get_trademark_records(
    trademark_ids: list[Any],
) -> dict[str, dict]:

    if not database_ready:
        raise RuntimeError(
            "PostgreSQL is not initialized."
        )

    if not trademark_primary_key:
        raise RuntimeError(
            "Trademark primary key is unavailable."
        )

    records = {}

    if not trademark_ids:
        return records

    connection = get_database_connection()

    try:

        cursor = connection.cursor()

        for trademark_id in trademark_ids:

            if trademark_id is None:
                continue

            record_id = str(trademark_id)

            query = (
                f'SELECT * FROM "{settings.DATABASE_SCHEMA}"'
                f'."{settings.DATABASE_TABLE}" '
                f'WHERE "{trademark_primary_key}"::text = %s '
                f'LIMIT 1'
            )

            cursor.execute(
                query,
                (record_id,),
            )

            row = cursor.fetchone()

            if row is None:
                continue

            field_names = [
                description[0]
                for description in cursor.description
            ]

            record = dict(
                zip(field_names, row)
            )

            records[record_id] = record

        return records

    finally:

        connection.close()


def get_trademark_record(
    trademark_id: Any,
):

    records = get_trademark_records(
        [trademark_id]
    )

    return records.get(str(trademark_id))


# =========================================================
# QDRANT INITIALIZATION
# =========================================================

def initialize_vector_engine():

    global vector_engine

    engine = VectorEngine(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection=settings.QDRANT_COLLECTION,
        dimension=settings.VECTOR_DIMENSION,
    )

    engine.ensure_collection()

    vector_engine = engine

    logger.info(
        "Qdrant connection established."
    )

    logger.info(
        "Qdrant collection: %s",
        settings.QDRANT_COLLECTION,
    )


def get_vector_engine():

    global vector_engine

    if vector_engine is None:

        with vector_engine_lock:

            if vector_engine is None:
                try:
                    initialize_vector_engine()
                except Exception as exc:
                    logger.exception(
                        "Qdrant initialization failed."
                    )
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Qdrant is unavailable. Check QDRANT_URL "
                            "and QDRANT_API_KEY."
                        ),
                    ) from exc

    return vector_engine


# =========================================================
# OPENCLIP INITIALIZATION
# =========================================================

def initialize_vision_engine():

    global vision_engine

    from app.engines.vision_engine import VisionEngine

    vision_engine = VisionEngine(
        model_name=settings.CLIP_MODEL_NAME,
        pretrained=settings.CLIP_PRETRAINED,
    )

    logger.info(
        "OpenCLIP Vision Engine initialized."
    )

    logger.info(
        "Vision model: %s / %s",
        settings.CLIP_MODEL_NAME,
        settings.CLIP_PRETRAINED,
    )

    logger.info(
        "Vision device: %s",
        vision_engine.device,
    )


def get_vision_engine():

    global vision_engine

    if vision_engine is None:

        with vision_engine_lock:

            if vision_engine is None:
                try:
                    initialize_vision_engine()
                except Exception as exc:
                    logger.exception(
                        "OpenCLIP initialization failed."
                    )
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "OpenCLIP could not be initialized. Check the "
                            "backend runtime and model availability."
                        ),
                    ) from exc

    return vision_engine


# =========================================================
# APPLICATION LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(
        "Starting %s...",
        settings.APP_NAME,
    )

    try:

        initialize_database()

        logger.info(
            "Application startup complete. Qdrant and vision services will "
            "initialize on demand."
        )

        yield

    except Exception:

        logger.exception(
            "Application startup failed."
        )

        raise

    finally:

        logger.info(
            "Application shutdown complete."
        )


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Global Trademark Intelligence API "
        "powered by OpenCLIP, Qdrant and PostgreSQL. "
        "Search results are validated against "
        "stored trademark records."
    ),
    lifespan=lifespan,
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
    ],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
    ],
)


# =========================================================
# API SECURITY
# =========================================================

def verify_api_key(
    api_key: str | None,
):

    if not settings.API_KEY:
        return

    if not api_key or api_key != settings.API_KEY:

        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
        )


# =========================================================
# SERVICE READINESS
# =========================================================

def ensure_services_ready():

    if not database_ready:

        raise HTTPException(
            status_code=503,
            detail="PostgreSQL is not ready.",
        )


# =========================================================
# IMAGE VALIDATION
# =========================================================

async def read_image(
    file: UploadFile,
) -> bytes:

    if file.content_type not in settings.ALLOWED_IMAGE_TYPES:

        raise HTTPException(
            status_code=415,
            detail=(
                "Only JPEG, PNG and WEBP images are supported."
            ),
        )

    file_bytes = await file.read(
        settings.MAX_UPLOAD_SIZE + 1
    )

    if not file_bytes:

        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    if len(file_bytes) > settings.MAX_UPLOAD_SIZE:

        raise HTTPException(
            status_code=413,
            detail=(
                "Image exceeds the maximum upload size."
            ),
        )

    try:

        vision = await run_in_threadpool(
            get_vision_engine
        )

        await run_in_threadpool(
            vision.prepare_image,
            file_bytes,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return file_bytes


# =========================================================
# REAL TRADEMARK RECORD SEARCH
# =========================================================

def search_real_records(
    vector: list[float],
):

    vector_results = vector_engine.search(
        vector=vector,
        limit=settings.SEARCH_LIMIT,
    )

    if not vector_results:
        return []

    trademark_ids = list(
        dict.fromkeys(
            result.get("trademark_id")
            for result in vector_results
            if result.get("trademark_id") is not None
        )
    )

    # PostgreSQL is the source of record truth.
    # Qdrant payload alone cannot verify a trademark.
    database_records = get_trademark_records(
        trademark_ids
    )

    verified_results = []

    for result in vector_results:

        trademark_id = result.get(
            "trademark_id"
        )

        if trademark_id is None:
            continue

        record = database_records.get(
            str(trademark_id)
        )

        if record is None:
            continue

        record_id = record.get(
            "id",
            record.get("trademark_id"),
        )

        verified_results.append({

            "trademark_id": (
                str(record_id)
                if record_id is not None
                else None
            ),

            "name": record.get("name"),

            "registration_number": record.get(
                "registration_number"
            ),

            "application_number": record.get(
                "application_number"
            ),

            "jurisdiction": record.get(
                "jurisdiction"
            ),

            "nice_classes": record.get(
                "nice_classes"
            ) or [],

            "similarity_score": result.get(
                "score",
                0,
            ),

            "record_status": record.get(
                "status"
            ),

            "image_url": record.get(
                "image_url"
            ) or result.get("image_url"),

        })

    return verified_results


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "success": True,
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "data_policy": "REAL_DATABASE_RECORDS_ONLY",
    }


# =========================================================
# LIVENESS
# =========================================================

@app.get("/health/live")
def health_live():

    return {
        "status": "alive",
    }


# =========================================================
# READINESS
# =========================================================

@app.get("/health/ready")
def health_ready():

    ensure_services_ready()

    connection = None

    try:

        connection = get_database_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT 1")

        cursor.fetchone()

        get_vector_engine().client.get_collection(
            settings.QDRANT_COLLECTION
        )

        return {
            "status": "ready",
            "database": "connected",
            "vector_database": "connected",
            "vision_engine": "lazy-loaded",
            "data_policy": "REAL_DATABASE_RECORDS_ONLY",
        }

    except Exception:

        logger.exception(
            "Readiness check failed."
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "One or more application services "
                "are unavailable."
            ),
        )

    finally:

        if connection is not None:
            connection.close()


# =========================================================
# TRADEMARK LOGO COMPARISON
# =========================================================

@app.post(
    f"{settings.API_PREFIX}/compare-logos"
)
async def compare_logos(
    image_a: UploadFile = File(...),
    image_b: UploadFile = File(...),
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
):

    verify_api_key(x_api_key)

    ensure_services_ready()

    search_id = str(uuid4())

    try:

        await run_in_threadpool(
            get_vector_engine
        )

        # -------------------------------------------------
        # READ UPLOADED IMAGES
        # -------------------------------------------------

        bytes_a = await read_image(
            image_a
        )

        bytes_b = await read_image(
            image_b
        )

        # -------------------------------------------------
        # GENERATE IMAGE EMBEDDINGS
        # -------------------------------------------------

        vision = await run_in_threadpool(
            get_vision_engine
        )

        vector_a = await run_in_threadpool(
            vision.encode_image,
            bytes_a,
        )

        vector_b = await run_in_threadpool(
            vision.encode_image,
            bytes_b,
        )

        # -------------------------------------------------
        # DIRECT IMAGE SIMILARITY
        # -------------------------------------------------

        visual_similarity = vision.similarity(
            vector_a,
            vector_b,
        )

        # -------------------------------------------------
        # SEARCH REAL TRADEMARK RECORDS
        # -------------------------------------------------

        matches_a = await run_in_threadpool(
            search_real_records,
            vector_a,
        )

        matches_b = await run_in_threadpool(
            search_real_records,
            vector_b,
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return {

            "success": True,

            "search_id": search_id,

            "engine": (
                "OpenCLIP + Qdrant + PostgreSQL"
            ),

            "data_policy": (
                "REAL_DATABASE_RECORDS_ONLY"
            ),

            "comparison": {

                "visual_similarity": (
                    visual_similarity
                ),

                "similarity_level": (

                    "HIGH"
                    if visual_similarity >= 80

                    else "MEDIUM"
                    if visual_similarity >= 50

                    else "LOW"
                ),

                "interpretation": (
                    "AI visual similarity screening only. "
                    "This score is not a legal determination "
                    "of trademark infringement, ownership "
                    "or registrability."
                ),
            },

            "image_a_matches": {

                "total": len(matches_a),

                "results": matches_a,
            },

            "image_b_matches": {

                "total": len(matches_b),

                "results": matches_b,
            },

        }

    except HTTPException:

        raise

    except Exception:

        logger.exception(
            "Trademark comparison failed. Search ID: %s",
            search_id,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Trademark comparison could not be completed."
            ),
        )

    finally:

        await image_a.close()
        await image_b.close()
