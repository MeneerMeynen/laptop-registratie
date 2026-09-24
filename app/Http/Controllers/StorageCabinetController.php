<?php

namespace App\Http\Controllers;

use App\Services\StorageCabinetService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class StorageCabinetController extends Controller
{
    public function __construct(private readonly StorageCabinetService $cabinets) {}

    public function index(Request $request): JsonResponse
    {
        return response()->json($this->cabinets->listCabinets($request->query('q'), $request->query('kind')));
    }

    public function store(Request $request): JsonResponse
    {
        $data = $this->body($request);
        $cabinet = $this->cabinets->createCabinet(
            $this->requireString($data, 'name'),
            $this->optString($data, 'kind') ?? 'kast',
            $this->optString($data, 'location'),
            $this->optString($data, 'description'),
            $this->optInt($data, 'capacity'),
        );

        return response()->json(StorageCabinetService::serialize($cabinet, 0));
    }

    public function update(Request $request, int $cabinetId): JsonResponse
    {
        $data = $this->body($request);
        $update = [];
        foreach (['name', 'location', 'description'] as $key) {
            if (array_key_exists($key, $data)) {
                $update[$key] = $this->optString($data, $key);
            }
        }
        if (array_key_exists('capacity', $data)) {
            $update['capacity'] = $this->optInt($data, 'capacity');
        }
        $cabinet = $this->cabinets->updateCabinet($cabinetId, $update);
        $count = $cabinet->laptops()->whereNull('unlinked_at')->count();

        return response()->json(StorageCabinetService::serialize($cabinet, $count));
    }

    public function destroy(Request $request): JsonResponse
    {
        $data = $this->body($request);
        $ids = array_map(fn ($id) => (int) $id, $this->stringList($data, 'ids'));

        return response()->json(['deleted' => $this->cabinets->deleteCabinets($ids)]);
    }
}
