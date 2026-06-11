import chromadb
import uuid
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = "./chroma_data"


class TurbovecEngine:
    """
    Production vector memory engine using ChromaDB (Module C — PRD Req-C.1/C.2/C.3).
    Provides semantic search over task history for contextual recall queries
    like "What did I finish last Thursday?"
    """

    def __init__(self):
        self._ready = False
        try:
            self.client = chromadb.PersistentClient(path=DB_PATH)
            self.collection = self.client.get_or_create_collection(
                name="chronospet_tasks",
                metadata={"hnsw:space": "cosine"}
            )
            self._ready = True
            logger.info(f"ChromaDB initialized at '{DB_PATH}' — {self.count()} vectors loaded.")
        except Exception as e:
            logger.error(f"ChromaDB initialization failed (non-fatal, running without vector memory): {e}")
            self.client = None
            self.collection = None

    @property
    def is_ready(self) -> bool:
        return self._ready

    def embed_and_store(self, text: str, metadata: dict) -> bool:
        """Embed a task string and store it in the local vector index."""
        if not self._ready:
            logger.warning("Vector store unavailable — skipping embed.")
            return False

        try:
            task_id = metadata.get("task_id", str(uuid.uuid4()))
            # Sanitize metadata values — ChromaDB requires str/int/float/bool only
            clean_meta = {}
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)

            self.collection.upsert(
                documents=[text],
                metadatas=[clean_meta],
                ids=[task_id]
            )
            logger.info(f"Vector stored: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Vector storage failed: {e}")
            return False

    def query(self, search_text: str, top_k: int = 5) -> Dict:
        """Execute a cosine similarity search against stored task vectors (Req-C.3)."""
        if not self._ready:
            logger.warning("Vector store unavailable — returning empty results.")
            return {"documents": [], "metadatas": [], "distances": []}

        try:
            results = self.collection.query(
                query_texts=[search_text],
                n_results=min(top_k, self.count() or 1)
            )
            return results
        except Exception as e:
            logger.error(f"Vector query failed: {e}")
            return {"documents": [], "metadatas": [], "distances": []}

    def delete(self, task_id: str) -> bool:
        """Remove a task vector from the index."""
        if not self._ready:
            return False
        try:
            self.collection.delete(ids=[task_id])
            logger.info(f"Vector deleted: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Vector deletion failed: {e}")
            return False

    def count(self) -> int:
        """Return total number of vectors in the store."""
        if not self._ready:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0


# Singleton instance
memory_db = TurbovecEngine()
