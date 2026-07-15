import os
from pydantic import BaseSettings

class Settings(BaseSettings):

    ANNOQ_ES_URL:str = os.environ.get("ANNOQ_ES_URL")
    ANNOQ_ES_PORT:str = os.environ.get("ANNOQ_ES_PORT")
    ANNOQ_ANNOTATIONS_INDEX :str = os.environ.get("ANNOQ_ANNOTATIONS_INDEX")
    # Bulk-load chunk size (docs per ES bulk request). Default 5000 matches prod (large heap).
    # Lower it (e.g. 500) for a small-heap local node to avoid the parent circuit breaker on
    # wide (~700-field) docs.
    ANNOQ_ES_BULK_CHUNK_SIZE :int = int(os.environ.get("ANNOQ_ES_BULK_CHUNK_SIZE") or 5000)
    PROJECT_TITLE: str = "Annoq"
    PROJECT_VERSION: str = "0.2.0"


settings = Settings()