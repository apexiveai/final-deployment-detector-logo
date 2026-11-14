
import ssl
from urllib.parse import urlparse, parse_qs, unquote

import pg8000.dbapi


class TrademarkRepository:

    def __init__(self, database_url):
        self.database_url = database_url
        self.connection_info = self._parse_url(database_url)

    @staticmethod
    def _parse_url(database_url):
        parsed = urlparse(database_url)
        query = parse_qs(parsed.query)

        if parsed.scheme not in ("postgresql", "postgres"):
            raise ValueError("Unsupported database URL")

        return {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/"),
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "ssl": query.get("sslmode", ["require"])[0] != "disable",
        }

    def connect(self):
        info = self.connection_info

        return pg8000.dbapi.connect(
            host=info["host"],
            port=info["port"],
            database=info["database"],
            user=info["user"],
            password=info["password"],
            ssl_context=ssl.create_default_context()
            if info["ssl"] else None,
            timeout=30,
        )

    def get_trademarks(self, limit=100, offset=0):
        connection = self.connect()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    owner_name,
                    registration_number,
                    application_number,
                    jurisdiction,
                    status,
                    source_name,
                    source_url,
                    source_record_id,
                    verification_status
                FROM public.trademarks
                ORDER BY id
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )

            columns = [item[0] for item in cursor.description]

            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        finally:
            connection.close()

    def get_trademark_images(self, trademark_id):
        connection = self.connect()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    trademark_id,
                    image_url,
                    storage_path,
                    original_filename,
                    mime_type,
                    file_hash,
                    is_primary
                FROM public.trademark_images
                WHERE trademark_id = %s
                ORDER BY is_primary DESC, id ASC
                """,
                (trademark_id,),
            )

            columns = [item[0] for item in cursor.description]

            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        finally:
            connection.close()

    def get_trademark_classes(self, trademark_id):
        connection = self.connect()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT nice_class, class_description
                FROM public.trademark_classes
                WHERE trademark_id = %s
                ORDER BY nice_class
                """,
                (trademark_id,),
            )

            return [
                {
                    "nice_class": row[0],
                    "class_description": row[1],
                }
                for row in cursor.fetchall()
            ]

        finally:
            connection.close()

    def save_embedding(
        self,
        trademark_id,
        image_id,
        point_id,
        model_name,
        dimension,
        image_hash,
    ):
        connection = self.connect()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO public.image_embeddings (
                    trademark_id,
                    image_id,
                    qdrant_point_id,
                    model_name,
                    vector_dimension,
                    image_hash,
                    indexed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (qdrant_point_id)
                DO UPDATE SET
                    model_name = EXCLUDED.model_name,
                    vector_dimension = EXCLUDED.vector_dimension,
                    image_hash = EXCLUDED.image_hash,
                    indexed_at = NOW()
                """,
                (
                    trademark_id,
                    image_id,
                    str(point_id),
                    model_name,
                    dimension,
                    image_hash,
                ),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()
