# MarkLens AI

## Local PostgreSQL setup

The backend connects to PostgreSQL directly; pgAdmin 4 is the UI for managing that server.
The local database used here is `trademark_conflict_db` on `127.0.0.1:5432`.

To create the application tables in another local setup:

1. In pgAdmin 4, select `trademark_conflict_db` and open **Query Tool**.
2. Open and run [`database/product_tables/apexiveai_trademark_conflict_schema.sql`](./database/product_tables/apexiveai_trademark_conflict_schema.sql).
   It creates the tables, indexes, update triggers, and initial reference settings.
3. Set `DATABASE_URL` in `backend/.env` to your local PostgreSQL connection. For a local
   server using the `postgres` role without password authentication:

   ```env
   DATABASE_URL=postgresql://postgres@127.0.0.1:5432/trademark_conflict_db?sslmode=disable
   ```

   If your PostgreSQL server requires a password, add it to the URL-encoded connection
   string and keep the password only in your local `.env` file.

## API key

`API_KEY` is a private key for this backend, not a key issued by pgAdmin or PostgreSQL.
Generate one locally with Python:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output into `backend/.env` as `API_KEY=<generated-value>`. The API accepts it
in the `X-API-Key` request header. Leaving `API_KEY` empty disables this check.

`QDRANT_API_KEY` is separate: it is issued by the Qdrant service configured for vector
search and is not interchangeable with `API_KEY`.

## Run the local app

Start the backend from `backend/` after installing its requirements:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
```

The backend checks PostgreSQL during startup. Qdrant and OpenCLIP initialize on demand,
so an unavailable remote service or a model download does not prevent the API from
starting.

In another terminal, start the frontend from `frontend/`:

```powershell
npm ci
npm run dev
```

The Vite proxy sends `/api` requests to `VITE_API_URL` (default
`http://127.0.0.1:8081`) and forwards `API_KEY` from `backend/.env` server-side; the key
is not included in the browser bundle.

## Compare two logos

```powershell
curl.exe -X POST http://127.0.0.1:8081/api/v1/compare-logos `
  -H "X-API-Key: <your-API_KEY>" `
  -F "image_a=@C:\path\to\logo-a.png" `
  -F "image_b=@C:\path\to\logo-b.png"
```
