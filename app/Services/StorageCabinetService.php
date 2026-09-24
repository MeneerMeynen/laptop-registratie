<?php

namespace App\Services;

use App\Models\Laptop;
use App\Models\StorageCabinet;
use App\Support\DetailException;
use App\Support\Fmt;
use App\Support\Sql;
use Illuminate\Support\Facades\DB;

class StorageCabinetService
{
    public const VALID_KINDS = ['kast', 'magazijn'];

    public static function serialize(StorageCabinet $cabinet, int $laptopCount = 0): array
    {
        return [
            'id' => $cabinet->id,
            'name' => $cabinet->name,
            'kind' => $cabinet->kind,
            'location' => $cabinet->location,
            'description' => $cabinet->description,
            'capacity' => $cabinet->capacity,
            'created_at' => Fmt::iso($cabinet->created_at),
            'laptop_count' => $laptopCount,
        ];
    }

    /** Alle locaties met het aantal gekoppelde laptops; optioneel gefilterd op type ("kast"/"magazijn"). */
    public function listCabinets(?string $q = null, ?string $kind = null): array
    {
        $counts = DB::table('laptops')
            ->whereNotNull('storage_cabinet_id')
            ->groupBy('storage_cabinet_id')
            ->pluck(DB::raw('COUNT(id)'), 'storage_cabinet_id');

        $query = StorageCabinet::query()->orderBy('name');
        if ($kind !== null) {
            $query->where('kind', $kind);
        }
        if ($q !== null && $q !== '') {
            $like = Sql::likeValue($q);
            $query->where(function ($w) use ($like) {
                foreach (['name', 'location', 'description'] as $col) {
                    $w->orWhereRaw(Sql::likeExpr($col), [$like]);
                }
            });
        }

        return $query->get()
            ->map(fn (StorageCabinet $c) => self::serialize($c, (int) ($counts[$c->id] ?? 0)))
            ->all();
    }

    public function getCabinet(int $cabinetId): StorageCabinet
    {
        $cabinet = StorageCabinet::find($cabinetId);
        if ($cabinet === null) {
            throw new DetailException(404, "Uitleenkast {$cabinetId} bestaat niet.");
        }

        return $cabinet;
    }

    private static function normalizeCapacity(mixed $value): ?int
    {
        if ($value === null || $value === '') {
            return null;
        }
        if (is_bool($value) || filter_var($value, FILTER_VALIDATE_INT) === false) {
            throw new DetailException(422, 'Capaciteit moet een geheel getal zijn.');
        }
        $n = (int) $value;
        if ($n < 0) {
            throw new DetailException(422, 'Capaciteit kan niet negatief zijn.');
        }

        return $n;
    }

    public function createCabinet(string $name, string $kind = 'kast', ?string $location = null,
        ?string $description = null, mixed $capacity = null): StorageCabinet
    {
        $name = trim($name);
        if ($name === '') {
            throw new DetailException(422, 'Naam is verplicht.');
        }
        if (! in_array($kind, self::VALID_KINDS, true)) {
            throw new DetailException(422, "Ongeldig type: {$kind}.");
        }
        if (StorageCabinet::where('name', $name)->exists()) {
            throw new DetailException(409, "Locatie met naam '{$name}' bestaat al.");
        }

        return StorageCabinet::create([
            'name' => $name,
            'kind' => $kind,
            'location' => Fmt::strOrNull($location),
            'description' => Fmt::strOrNull($description),
            'capacity' => self::normalizeCapacity($capacity),
            'created_at' => now(),
        ])->refresh();
    }

    /** Alleen sleutels die in $data zitten (en niet null zijn) worden aangepast. */
    public function updateCabinet(int $cabinetId, array $data): StorageCabinet
    {
        $cabinet = $this->getCabinet($cabinetId);

        if (isset($data['name'])) {
            $name = trim((string) $data['name']);
            if ($name === '') {
                throw new DetailException(422, 'Naam mag niet leeg zijn.');
            }
            if ($name !== $cabinet->name
                && StorageCabinet::where('name', $name)->where('id', '!=', $cabinetId)->exists()) {
                throw new DetailException(409, "Uitleenkast met naam '{$name}' bestaat al.");
            }
            $cabinet->name = $name;
        }
        if (isset($data['location'])) {
            $cabinet->location = Fmt::strOrNull($data['location']);
        }
        if (isset($data['description'])) {
            $cabinet->description = Fmt::strOrNull($data['description']);
        }
        if (isset($data['capacity'])) {
            $cabinet->capacity = self::normalizeCapacity($data['capacity']);
        }
        $cabinet->save();

        return $cabinet->refresh();
    }

    /** Locaties definitief verwijderen. Weigert als er nog laptops in zitten. */
    public function deleteCabinets(array $ids): int
    {
        $ids = array_map('intval', $ids);
        if (! $ids) {
            return 0;
        }
        if (Laptop::whereIn('storage_cabinet_id', $ids)->exists()) {
            throw new DetailException(409, 'Eén of meer locaties bevatten nog laptops. Verplaats die laptops eerst.');
        }

        return StorageCabinet::whereIn('id', $ids)->delete();
    }
}
