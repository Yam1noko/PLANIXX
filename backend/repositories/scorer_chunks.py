from pathlib import Path
import logging
from time import perf_counter

from backend.core.observability import get_request_id
from backend.core.config import SCORER_CHUNKS_DIR
from backend.models.scoring import (
    SolverResultChunk,
    SolverResultChunkingResponse,
)

logger = logging.getLogger(__name__)


class ScorerChunkRepository:
    def __init__(self):
        self.base_dir = SCORER_CHUNKS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_chunking_response(
        self,
        response: SolverResultChunkingResponse,
    ) -> SolverResultChunkingResponse:
        started_at = perf_counter()
        logger.info(
            "ScorerChunkRepository.save_chunking_response started | request_id=%s batch_id=%s total_chunks=%s",
            get_request_id(),
            response.batch_id,
            response.total_chunks,
        )
        batch_dir = self.base_dir / response.batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        for stale_chunk_path in batch_dir.glob("chunk_*.json"):
            stale_chunk_path.unlink()

        for stale_variant_path in batch_dir.glob("variant_*.json"):
            stale_variant_path.unlink()

        manifest_path = batch_dir / "manifest.json"
        manifest_path.write_text(
            response.model_dump_json(indent=2),
            encoding="utf-8",
        )

        for chunk in response.chunks:
            chunk_path = self._get_chunk_path(
                response.batch_id,
                chunk.schedule_variant.variant_id,
            )
            chunk_path.write_text(
                chunk.model_dump_json(indent=2),
                encoding="utf-8",
            )

        logger.info(
            "ScorerChunkRepository.save_chunking_response finished | request_id=%s batch_id=%s duration_ms=%s",
            get_request_id(),
            response.batch_id,
            round((perf_counter() - started_at) * 1000, 2),
        )
        return response

    def get_chunk(
        self,
        batch_id: str,
        chunk_id: int,
        variant_id: int | None = None,
    ) -> SolverResultChunk:
        batch_dir = self.base_dir / batch_id
        legacy_chunk_path = batch_dir / f"chunk_{chunk_id}.json"

        if variant_id is not None:
            chunk = self._read_chunk_file(self._get_chunk_path(batch_id, variant_id))
            if chunk.chunk_id != chunk_id:
                raise FileNotFoundError
            return chunk

        if legacy_chunk_path.exists():
            return self._read_chunk_file(legacy_chunk_path)

        matches = [
            self._read_chunk_file(chunk_path)
            for chunk_path in sorted(batch_dir.glob("variant_*.json"))
        ]
        matches = [chunk for chunk in matches if chunk.chunk_id == chunk_id]

        if not matches:
            raise FileNotFoundError

        if len(matches) > 1:
            raise ValueError(
                "Multiple variants found for the same chunk_id. "
                "Specify variant_id to fetch an exact chunk."
            )

        return matches[0]

    def _get_chunk_path(self, batch_id: str, variant_id: int) -> Path:
        return self.base_dir / batch_id / f"variant_{variant_id}.json"

    def _read_chunk_file(self, chunk_path: Path) -> SolverResultChunk:
        return SolverResultChunk.model_validate_json(
            chunk_path.read_text(encoding="utf-8")
        )
