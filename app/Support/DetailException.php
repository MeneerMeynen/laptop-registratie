<?php

namespace App\Support;

use Illuminate\Http\JsonResponse;
use RuntimeException;

/**
 * Fout die als {"detail": ...} met een HTTP-statuscode teruggegeven wordt,
 * net zoals FastAPI's HTTPException. De frontend leest `data.detail`.
 */
class DetailException extends RuntimeException
{
    public function __construct(
        public readonly int $status,
        public readonly string|array $detail,
    ) {
        parent::__construct(is_string($detail) ? $detail : ($detail['message'] ?? ''));
    }

    public function render(): JsonResponse
    {
        return response()->json(['detail' => $this->detail], $this->status);
    }
}
