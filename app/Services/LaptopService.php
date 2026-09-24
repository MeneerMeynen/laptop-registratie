<?php

namespace App\Services;

use App\Models\Laptop;
use App\Models\LaptopIssue;
use App\Models\StorageCabinet;
use App\Models\Student;
use App\Support\DetailException;
use App\Support\Fmt;
use App\Support\Sql;
use Carbon\CarbonImmutable;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

class LaptopService
{
    public const EIGEN_LAPTOP_TRIGGER = 'eigen laptop';

    /** Serienummers komen van barcode-scans: alfanumeriek plus enkele scheidingstekens. */
    public const SERIAL_RE = '/^[A-Za-z0-9._-]{1,100}\z/';

    public const VALID_KINDS = ['all', 'normal', 'reserve', 'cabinet', 'magazijn'];

    public const COLUMN_FILTER_KEYS = ['serial', 'student', 'klas', 'status', 'acc', 'date'];

    // ── Helpers ─────────────────────────────────────────────────────────────

    public static function isEigenLaptopScan(string $serial): bool
    {
        return mb_strtolower(trim($serial)) === self::EIGEN_LAPTOP_TRIGGER;
    }

    /** Leesbare omschrijving van een laptop (voor foutmeldingen). */
    public static function describeSerial(Laptop $laptop): string
    {
        if ($laptop->eigen_laptop) {
            return 'eigen laptop';
        }
        if ($laptop->is_reserve) {
            return "reserve-laptop '".($laptop->alias ?: $laptop->serial_number ?: '')."'";
        }

        return $laptop->serial_number ?? '';
    }

    /** Laptop als JSON-antwoord (LaptopLinkResponse in de Python-versie). */
    public static function toResponse(Laptop $laptop): array
    {
        return [
            'id' => $laptop->id,
            'serial_number' => $laptop->serial_number,
            'stamnummer' => $laptop->stamnummer,
            'eigen_laptop' => (bool) $laptop->eigen_laptop,
            'is_reserve' => (bool) $laptop->is_reserve,
            'alias' => $laptop->alias,
            'storage_cabinet_id' => $laptop->storage_cabinet_id,
            'linked_at' => Fmt::iso($laptop->linked_at),
            'unlinked_at' => Fmt::iso($laptop->unlinked_at),
            'hoes_ingeleverd' => (bool) $laptop->hoes_ingeleverd,
            'oplader_ingeleverd' => (bool) $laptop->oplader_ingeleverd,
        ];
    }

    private function activeNonReserve(string $serial): ?Laptop
    {
        return Laptop::where('serial_number', $serial)
            ->whereNull('unlinked_at')
            ->where('is_reserve', false)
            ->first();
    }

    // ── Koppelen / ontkoppelen ─────────────────────────────────────────────

    /**
     * Koppel een laptop (of "eigen laptop") aan een leerling.
     *
     * Bij de scan "eigen laptop" wordt eigen_laptop=true gezet en blijft het serienummer leeg.
     */
    public function linkLaptopToStudent(string $stamnummer, string $serialNumber, bool $overwriteExisting = false): Laptop
    {
        $stamnummer = trim($stamnummer);
        $serial = trim($serialNumber);
        $isOwn = self::isEigenLaptopScan($serial);

        return DB::transaction(function () use ($stamnummer, $serial, $isOwn, $overwriteExisting) {
            // 1. Leerling moet bestaan.
            $student = Student::with('laptops')->find($stamnummer);
            if ($student === null) {
                throw new DetailException(404, "Student {$stamnummer} does not exist.");
            }

            // 2. Gewoon serienummer: al actief gekoppeld aan iemand anders, of in een kast/magazijn?
            $fromMagazijn = null;
            if (! $isOwn) {
                $existing = $this->activeNonReserve($serial);
                if ($existing !== null && $existing->storage_cabinet_id !== null) {
                    $cabinet = StorageCabinet::find($existing->storage_cabinet_id);
                    if ($cabinet !== null && $cabinet->kind === 'magazijn') {
                        // Een magazijn-laptop mag toegekend worden: hij verlaat het magazijn.
                        $fromMagazijn = $existing;
                    } else {
                        $label = $cabinet ? $cabinet->name : "#{$existing->storage_cabinet_id}";
                        throw new DetailException(409,
                            "Laptop {$serial} staat in uitleenkast '{$label}' en kan niet aan een leerling gekoppeld worden.");
                    }
                }
                if ($existing !== null && $fromMagazijn === null && $existing->stamnummer !== $stamnummer) {
                    $owner = $existing->stamnummer ? Student::find($existing->stamnummer) : null;
                    $ownerName = $owner ? "{$owner->voornaam} {$owner->naam}" : ($existing->stamnummer ?? '?');
                    throw new DetailException(409,
                        "Laptop {$serial} is already linked to {$ownerName} ({$existing->stamnummer}).");
                }
            }

            // 3. Heeft deze leerling al een actieve (niet-reserve) laptop?
            $active = $student->laptops->filter(fn (Laptop $l) => $l->isActive() && ! $l->is_reserve)->values();
            $match = $active->first(fn (Laptop $l) => ($isOwn && $l->eigen_laptop) || (! $isOwn && $l->serial_number === $serial));
            $others = $active->reject(fn (Laptop $l) => $match !== null && $l->id === $match->id)->values();

            if ($others->isNotEmpty() && ! $overwriteExisting) {
                $serials = $others->map(fn (Laptop $l) => self::describeSerial($l))->all();
                throw new DetailException(409, [
                    'message' => "Student {$stamnummer} already has laptop(s): ".implode(', ', $serials).'.',
                    'stamnummer' => $stamnummer,
                    'existing_serials' => $serials,
                    'requires_confirmation' => true,
                ]);
            }

            // 4. Bij overschrijven: de *andere* actieve laptops ontkoppelen; de overeenkomende blijft.
            foreach ($others as $other) {
                $other->unlinked_at = now();
                $other->save();
            }

            // Idempotent: exact deze laptop is al aan deze leerling gekoppeld → geen nieuw record.
            if ($match !== null) {
                return $match->refresh();
            }

            // 5a. Magazijn-laptop: hetzelfde record uit het magazijn halen en toekennen.
            if ($fromMagazijn !== null) {
                $fromMagazijn->fill([
                    'storage_cabinet_id' => null,
                    'stamnummer' => $stamnummer,
                    'linked_at' => now(),
                    'hoes_ingeleverd' => true,
                    'oplader_ingeleverd' => true,
                ])->save();

                return $fromMagazijn->refresh();
            }

            // 5b. Nieuw laptoprecord.
            $laptop = Laptop::create([
                'serial_number' => $isOwn ? null : $serial,
                'stamnummer' => $stamnummer,
                'eigen_laptop' => $isOwn,
                'linked_at' => now(),
            ]);

            return $laptop->refresh();
        });
    }

    /**
     * Markeer een toewijzing als ingeleverd. Ontbreekt de hoes of oplader, dan wordt
     * automatisch een issue aangemaakt zodat het ontbrekende item opgevolgd wordt.
     */
    public function unlinkLaptop(int $laptopId, bool $hoesIngeleverd = true, bool $opladerIngeleverd = true): Laptop
    {
        return DB::transaction(function () use ($laptopId, $hoesIngeleverd, $opladerIngeleverd) {
            $laptop = Laptop::find($laptopId);
            if ($laptop === null) {
                throw new DetailException(404, 'Laptop niet gevonden.');
            }
            if ($laptop->unlinked_at !== null) {
                throw new DetailException(409, 'Laptop is al ingeleverd.');
            }

            $laptop->unlinked_at = now();
            $laptop->hoes_ingeleverd = $hoesIngeleverd;
            $laptop->oplader_ingeleverd = $opladerIngeleverd;
            $laptop->save();

            if ((! $hoesIngeleverd || ! $opladerIngeleverd) && $laptop->serial_number) {
                $missing = [];
                if (! $hoesIngeleverd) {
                    $missing[] = 'hoes';
                }
                if (! $opladerIngeleverd) {
                    $missing[] = 'oplader';
                }
                LaptopIssue::create([
                    'serial_number' => $laptop->serial_number,
                    'description' => 'Bij inlevering ontbraken: '.implode(', ', $missing).'.',
                    'reported_date' => now()->toDateString(),
                    'status' => 'aangemeld',
                    'category' => 'Accessoires',
                ]);
            }

            return $laptop->refresh();
        });
    }

    /** Alle toewijzingen (actief + historisch) voor een serienummer, nieuwste eerst. */
    public function getAssignmentHistory(string $serial): array
    {
        return DB::table('laptops')
            ->leftJoin('students', 'students.stamnummer', '=', 'laptops.stamnummer')
            ->where('laptops.serial_number', $serial)
            ->orderByDesc('laptops.linked_at')
            ->get([
                'laptops.id', 'laptops.stamnummer', 'laptops.linked_at', 'laptops.unlinked_at',
                'students.naam', 'students.voornaam', 'students.klas',
            ])
            ->map(fn ($row) => [
                'id' => (int) $row->id,
                'stamnummer' => $row->stamnummer,
                'naam' => $row->naam,
                'voornaam' => $row->voornaam,
                'klas' => $row->klas,
                'linked_at' => self::parseDate($row->linked_at),
                'unlinked_at' => self::parseDate($row->unlinked_at),
                'is_active' => $row->unlinked_at === null,
            ])
            ->all();
    }

    // ── Beheer (CRUD) ───────────────────────────────────────────────────────

    /** Vertaal UI-queryparams (active='actief'/'inactief'/'all') naar filters. */
    public static function parseLaptopFilters(?string $active, ?string $kind): array
    {
        $activeFilter = ['actief' => true, 'inactief' => false][$active ?? ''] ?? null;

        return [$activeFilter, in_array($kind, self::VALID_KINDS, true) ? $kind : 'all'];
    }

    /** Houd alleen de niet-lege kolomfilters over (getrimd). */
    public static function parseColumnFilters(array $values): array
    {
        $columns = [];
        foreach (self::COLUMN_FILTER_KEYS as $key) {
            $value = trim((string) ($values[$key] ?? ''));
            if ($value !== '') {
                $columns[$key] = $value;
            }
        }

        return $columns;
    }

    /** Vertaal 'jjjj', 'mm/jjjj' of 'dd/mm/jjjj' naar een [start, einde)-bereik. */
    public static function dateRange(string $term): ?array
    {
        $parts = preg_split('/[\/\-.]/', trim($term));
        foreach ($parts as $part) {
            if (! preg_match('/^\s*[+-]?\d+\s*$/', $part)) {
                return null;
            }
        }
        $nums = array_map('intval', $parts);

        try {
            if (count($nums) === 1) {
                [$year] = $nums;
                self::assertDate($year, 1, 1);

                return [CarbonImmutable::create($year, 1, 1), CarbonImmutable::create($year + 1, 1, 1)];
            }
            if (count($nums) === 2) {
                [$month, $year] = $nums;
                self::assertDate($year, $month, 1);
                $start = CarbonImmutable::create($year, $month, 1);

                return [$start, $start->addMonthNoOverflow()];
            }
            if (count($nums) === 3) {
                [$day, $month, $year] = $nums;
                self::assertDate($year, $month, $day);
                $start = CarbonImmutable::create($year, $month, $day);

                return [$start, $start->addDay()];
            }
        } catch (\InvalidArgumentException) {
            return null;
        }

        return null;
    }

    private static function assertDate(int $year, int $month, int $day): void
    {
        if ($year < 1 || $year > 9999 || ! checkdate($month, $day, $year)) {
            throw new \InvalidArgumentException('Ongeldige datum');
        }
    }

    /** Filter per tabelkolom; elke waarde is een vrij in te voeren, hoofdletterongevoelige term. */
    private function applyColumnFilters(Builder $query, array $columns): void
    {
        if (isset($columns['serial'])) {
            $query->whereRaw(Sql::likeExpr('laptops.serial_number'), [Sql::likeValue($columns['serial'])]);
        }

        if (isset($columns['student'])) {
            $term = $columns['student'];
            $termL = mb_strtolower($term);
            $like = Sql::likeValue($term);
            $typeLabels = [
                'leerling' => fn (Builder $q) => $q->where('laptops.is_reserve', false)->whereNull('laptops.storage_cabinet_id'),
                'reserve' => fn (Builder $q) => $q->where('laptops.is_reserve', true),
                'kast' => fn (Builder $q) => $q->whereNotNull('laptops.storage_cabinet_id')->where('storage_cabinets.kind', 'kast'),
                'magazijn' => fn (Builder $q) => $q->whereNotNull('laptops.storage_cabinet_id')->where('storage_cabinets.kind', 'magazijn'),
                'eigen laptop' => fn (Builder $q) => $q->where('laptops.eigen_laptop', true),
            ];
            $query->where(function (Builder $q) use ($like, $termL, $typeLabels) {
                foreach (['laptops.stamnummer', 'laptops.alias', 'students.naam', 'students.voornaam'] as $col) {
                    $q->orWhereRaw(Sql::likeExpr($col), [$like]);
                }
                $q->orWhereRaw(Sql::likeExpr(Sql::concatSpace('students.voornaam', 'students.naam')), [$like]);
                $q->orWhereRaw(Sql::likeExpr('storage_cabinets.name'), [$like]);
                $q->orWhereRaw(Sql::likeExpr('storage_cabinets.location'), [$like]);
                foreach ($typeLabels as $label => $condition) {
                    if (str_contains($label, $termL)) {
                        $q->orWhere($condition);
                    }
                }
            });
        }

        if (isset($columns['klas'])) {
            $query->whereRaw(Sql::likeExpr('students.klas'), [Sql::likeValue($columns['klas'])]);
        }

        if (isset($columns['status'])) {
            $termL = mb_strtolower($columns['status']);
            if (str_starts_with('inactief', $termL)) {
                $query->whereNotNull('laptops.unlinked_at');
            } elseif (str_starts_with('actief', $termL)) {
                $query->whereNull('laptops.unlinked_at');
            } else {
                $query->whereRaw('1 = 0');
            }
        }

        if (isset($columns['acc'])) {
            $termL = mb_strtolower($columns['acc']);
            // Accessoires zijn alleen zinvol voor ingeleverde leerling-laptops (zie template).
            $applicable = fn (Builder $q) => $q->whereNotNull('laptops.unlinked_at')
                ->where('laptops.is_reserve', false)
                ->whereNull('laptops.storage_cabinet_id')
                ->where('laptops.eigen_laptop', false);

            if (str_starts_with('hoes', $termL) || str_starts_with($termL, 'hoes')) {
                $query->where($applicable)->where('laptops.hoes_ingeleverd', false);
            } elseif (str_starts_with('oplader', $termL) || str_starts_with($termL, 'oplader')) {
                $query->where($applicable)->where('laptops.oplader_ingeleverd', false);
            } elseif (str_starts_with('compleet', $termL)) {
                $query->where($applicable)
                    ->where('laptops.hoes_ingeleverd', true)
                    ->where('laptops.oplader_ingeleverd', true);
            } elseif (in_array($termL, ['—', '-', 'n.v.t', 'nvt', 'n.v.t.'], true)) {
                $query->whereNot($applicable);
            } else {
                $query->whereRaw('1 = 0');
            }
        }

        if (isset($columns['date'])) {
            $window = self::dateRange($columns['date']);
            if ($window === null) {
                $query->whereRaw('1 = 0');
            } else {
                $query->where('laptops.linked_at', '>=', $window[0]->format('Y-m-d H:i:s'))
                    ->where('laptops.linked_at', '<', $window[1]->format('Y-m-d H:i:s'));
            }
        }
    }

    /**
     * Alle laptoprecords met leerling- en kastinfo, optioneel gefilterd.
     *
     * $kind: "all", "normal" (zonder reserve en kast), "reserve", "cabinet" (kast) of "magazijn".
     */
    public function getAllLaptops(?string $q = null, ?bool $active = null, string $kind = 'all', array $columns = []): array
    {
        $query = DB::table('laptops')
            ->leftJoin('students', 'students.stamnummer', '=', 'laptops.stamnummer')
            ->leftJoin('storage_cabinets', 'storage_cabinets.id', '=', 'laptops.storage_cabinet_id')
            ->select([
                'laptops.*',
                'students.naam', 'students.voornaam', 'students.klas', 'students.is_leerkracht',
                'storage_cabinets.name as cabinet_name',
                'storage_cabinets.location as cabinet_location',
                'storage_cabinets.kind as cabinet_kind',
            ])
            // NULL-datums achteraan (portabel alternatief voor NULLS LAST).
            ->orderByRaw('laptops.linked_at IS NULL')
            ->orderByDesc('laptops.linked_at')
            ->orderByDesc('laptops.id');

        match ($kind) {
            'reserve' => $query->where('laptops.is_reserve', true),
            'cabinet' => $query->whereNotNull('laptops.storage_cabinet_id')->where('storage_cabinets.kind', 'kast'),
            'magazijn' => $query->whereNotNull('laptops.storage_cabinet_id')->where('storage_cabinets.kind', 'magazijn'),
            'normal' => $query->where('laptops.is_reserve', false)->whereNull('laptops.storage_cabinet_id'),
            default => null,
        };

        if ($active !== null) {
            $active ? $query->whereNull('laptops.unlinked_at') : $query->whereNotNull('laptops.unlinked_at');
        }

        if ($q !== null && $q !== '') {
            $like = Sql::likeValue($q);
            $query->where(function (Builder $w) use ($like) {
                foreach ([
                    'laptops.serial_number', 'laptops.stamnummer', 'laptops.alias',
                    'students.naam', 'students.voornaam', 'students.klas',
                    'storage_cabinets.name', 'storage_cabinets.location',
                ] as $col) {
                    $w->orWhereRaw(Sql::likeExpr($col), [$like]);
                }
            });
        }

        if ($columns) {
            $this->applyColumnFilters($query, $columns);
        }

        return $query->get()->map(fn ($row) => [
            'id' => (int) $row->id,
            'serial_number' => $row->serial_number ?? '',
            'stamnummer' => $row->stamnummer,
            'eigen_laptop' => (bool) $row->eigen_laptop,
            'is_reserve' => (bool) $row->is_reserve,
            'alias' => $row->alias,
            'storage_cabinet_id' => $row->storage_cabinet_id !== null ? (int) $row->storage_cabinet_id : null,
            'cabinet_name' => $row->cabinet_name,
            'cabinet_location' => $row->cabinet_location,
            'cabinet_kind' => $row->cabinet_kind,
            'linked_at' => self::parseDate($row->linked_at),
            'unlinked_at' => self::parseDate($row->unlinked_at),
            'is_active' => $row->unlinked_at === null,
            'hoes_ingeleverd' => (bool) $row->hoes_ingeleverd,
            'oplader_ingeleverd' => (bool) $row->oplader_ingeleverd,
            'naam' => $row->naam,
            'voornaam' => $row->voornaam,
            'klas' => $row->klas ?: ($row->is_leerkracht ? 'Leerkracht' : null),
        ])->all();
    }

    /** Lijst voor JSON-antwoorden: datums als ISO-strings. */
    public static function listForJson(array $laptops): array
    {
        return array_map(function (array $l) {
            $l['linked_at'] = Fmt::iso($l['linked_at']);
            $l['unlinked_at'] = Fmt::iso($l['unlinked_at']);

            return $l;
        }, $laptops);
    }

    /**
     * Nieuw laptoprecord. Drie elkaar uitsluitende types:
     * - gewone laptop: stamnummer en serienummer verplicht;
     * - reserve-laptop: is_reserve en alias verplicht, geen leerling/kast;
     * - kast-laptop: storage_cabinet_id en serienummer verplicht, geen leerling/reserve.
     */
    public function createLaptop(?string $serialNumber = null, ?string $stamnummer = null, bool $isReserve = false,
        ?string $alias = null, ?int $storageCabinetId = null): Laptop
    {
        $serial = Fmt::strOrNull($serialNumber);
        $stam = Fmt::strOrNull($stamnummer);
        $alias = Fmt::strOrNull($alias);

        if ($isReserve && $storageCabinetId !== null) {
            throw new DetailException(422, 'Een laptop kan niet tegelijk reserve en in een uitleenkast zijn.');
        }

        if ($storageCabinetId !== null) {
            if ($stam) {
                throw new DetailException(422, 'Een kast-laptop mag niet aan een leerling gekoppeld zijn.');
            }
            if (! $serial) {
                throw new DetailException(422, 'Serienummer is verplicht voor een kast-laptop.');
            }
            if (StorageCabinet::find($storageCabinetId) === null) {
                throw new DetailException(422, "Uitleenkast {$storageCabinetId} bestaat niet.");
            }
        } elseif ($isReserve) {
            if ($stam) {
                throw new DetailException(422, 'Een reserve-laptop mag niet aan een leerling gekoppeld zijn.');
            }
            if (! $alias) {
                throw new DetailException(422, 'Reserve-laptop vereist een alias.');
            }
        } else {
            if (! $stam) {
                throw new DetailException(422, 'Stamnummer is verplicht voor een gewone laptop.');
            }
            if (! $serial) {
                throw new DetailException(422, 'Serienummer is verplicht voor een gewone laptop.');
            }
            if (Student::find($stam) === null) {
                throw new DetailException(404, "Student {$stam} bestaat niet.");
            }
        }

        if ($serial && ! $isReserve && $this->activeNonReserve($serial) !== null) {
            throw new DetailException(409, "Serienummer {$serial} is al actief gekoppeld.");
        }

        $laptop = Laptop::create([
            'serial_number' => $serial,
            'stamnummer' => ($isReserve || $storageCabinetId !== null) ? null : $stam,
            'eigen_laptop' => false,
            'is_reserve' => $isReserve,
            'alias' => $alias,
            'storage_cabinet_id' => $storageCabinetId,
            'linked_at' => $isReserve ? null : now(),
        ]);

        return $laptop->refresh();
    }

    /** Hoogste bestaande Reserve-N-nummer + 1 (standaard 1). */
    private function nextReserveAliasNumber(): int
    {
        $highest = 0;
        $aliases = Laptop::where('is_reserve', true)->whereNotNull('alias')->pluck('alias');
        foreach ($aliases as $alias) {
            if (preg_match('/^Reserve-(\d+)$/', $alias, $m)) {
                $highest = max($highest, (int) $m[1]);
            }
        }

        return $highest + 1;
    }

    /**
     * Meerdere reserve- of kastlaptops aanmaken vanuit een lijst serienummers.
     * Dubbele serials in de invoer en al actief gekoppelde serials worden overgeslagen.
     *
     * @return array{created:int, skipped:int, errors:list<string>}
     */
    public function bulkCreateLaptops(array $serials, bool $isReserve = false, ?int $storageCabinetId = null): array
    {
        if ($isReserve && $storageCabinetId !== null) {
            throw new DetailException(422, 'Een laptop kan niet tegelijk reserve en in een uitleenkast zijn.');
        }
        if (! $isReserve && $storageCabinetId === null) {
            throw new DetailException(422, 'Kies een doel: reserve-pool of een uitleenkast.');
        }
        if ($storageCabinetId !== null && StorageCabinet::find($storageCabinetId) === null) {
            throw new DetailException(422, "Uitleenkast {$storageCabinetId} bestaat niet.");
        }

        return DB::transaction(function () use ($serials, $isReserve, $storageCabinetId) {
            $created = 0;
            $skipped = 0;
            $errors = [];
            $seen = [];
            $nextAlias = $isReserve ? $this->nextReserveAliasNumber() : 0;

            foreach ($serials as $raw) {
                $serial = trim((string) ($raw ?? ''));
                if ($serial === '') {
                    continue;
                }
                if (! preg_match(self::SERIAL_RE, $serial)) {
                    $errors[] = "Ongeldig serienummer: {$serial}";

                    continue;
                }
                if (isset($seen[$serial])) {
                    $skipped++;

                    continue;
                }
                $seen[$serial] = true;

                if ($isReserve) {
                    if (Laptop::where('serial_number', $serial)->where('is_reserve', true)->exists()) {
                        $skipped++;

                        continue;
                    }
                    Laptop::create([
                        'serial_number' => $serial,
                        'is_reserve' => true,
                        'alias' => 'Reserve-'.$nextAlias,
                        'linked_at' => null,
                    ]);
                    $nextAlias++;
                } else {
                    if ($this->activeNonReserve($serial) !== null) {
                        $skipped++;

                        continue;
                    }
                    Laptop::create([
                        'serial_number' => $serial,
                        'storage_cabinet_id' => $storageCabinetId,
                        'linked_at' => now(),
                    ]);
                }
                $created++;
            }

            return ['created' => $created, 'skipped' => $skipped, 'errors' => $errors];
        });
    }

    /**
     * Velden van een laptoprecord bijwerken. Alleen sleutels die in $data aanwezig zijn
     * worden behandeld (zoals Pydantic's exclude_unset); storage_cabinet_id=null wist de kast.
     */
    public function updateLaptop(int $laptopId, array $data): Laptop
    {
        return DB::transaction(function () use ($laptopId, $data) {
            $laptop = Laptop::find($laptopId);
            if ($laptop === null) {
                throw new DetailException(404, 'Laptop niet gevonden.');
            }

            $isReserve = array_key_exists('is_reserve', $data) && $data['is_reserve'] !== null ? (bool) $data['is_reserve'] : null;
            if ($isReserve !== null && $isReserve !== (bool) $laptop->is_reserve) {
                if ($isReserve) {
                    $laptop->is_reserve = true;
                    $laptop->stamnummer = null;
                    $laptop->storage_cabinet_id = null;
                    if ($laptop->unlinked_at === null && $laptop->linked_at !== null) {
                        $laptop->unlinked_at = now();
                    }
                } else {
                    $laptop->is_reserve = false;
                }
            }

            if (array_key_exists('storage_cabinet_id', $data)) {
                $cabinetId = $data['storage_cabinet_id'];
                if ($cabinetId !== null) {
                    if (StorageCabinet::find($cabinetId) === null) {
                        throw new DetailException(422, "Uitleenkast {$cabinetId} bestaat niet.");
                    }
                    $laptop->storage_cabinet_id = (int) $cabinetId;
                    $laptop->stamnummer = null;
                    $laptop->is_reserve = false;
                } else {
                    $laptop->storage_cabinet_id = null;
                }
            }

            if (isset($data['alias'])) {
                $laptop->alias = Fmt::strOrNull($data['alias']);
            }

            if (isset($data['stamnummer']) && ! $laptop->is_reserve && $laptop->storage_cabinet_id === null) {
                $stam = trim((string) $data['stamnummer']);
                if ($stam === '') {
                    throw new DetailException(422, 'Stamnummer mag niet leeg zijn voor een gewone laptop.');
                }
                if (Student::find($stam) === null) {
                    throw new DetailException(404, "Student {$stam} bestaat niet.");
                }
                $laptop->stamnummer = $stam;
            }

            if (isset($data['serial_number'])) {
                $serial = Fmt::strOrNull($data['serial_number']);
                if ($serial) {
                    $conflict = Laptop::where('serial_number', $serial)
                        ->whereNull('unlinked_at')
                        ->where('is_reserve', false)
                        ->where('id', '!=', $laptopId)
                        ->exists();
                    if ($conflict && ! $laptop->is_reserve) {
                        throw new DetailException(409, "Serienummer {$serial} is al actief gekoppeld aan een andere laptop.");
                    }
                }
                $laptop->serial_number = $serial;
            }

            if ($laptop->is_reserve && ! $laptop->alias) {
                throw new DetailException(422, 'Reserve-laptop vereist een alias.');
            }
            if ($laptop->storage_cabinet_id !== null && ! $laptop->serial_number) {
                throw new DetailException(422, 'Serienummer is verplicht voor een kast-laptop.');
            }

            $laptop->save();

            return $laptop->refresh();
        });
    }

    public function deleteLaptopPermanently(int $laptopId): void
    {
        $laptop = Laptop::find($laptopId);
        if ($laptop === null) {
            throw new DetailException(404, 'Laptop niet gevonden.');
        }
        $laptop->delete();
    }

    /**
     * Laptops importeren vanuit CSV (serial_number,stamnummer).
     *
     * @return array{created:int, updated:int, errors:list<string>}
     */
    public function importLaptopsCsv(string $content): array
    {
        $created = 0;
        $updated = 0;
        $errors = [];

        $rows = CsvReader::dictRows($content, ',');

        DB::transaction(function () use ($rows, &$created, &$updated, &$errors) {
            foreach ($rows as $i => $row) {
                $line = $i + 2;
                $serial = trim($row['serial_number'] ?? $row['Serienummer'] ?? '');
                $stam = trim($row['stamnummer'] ?? $row['Stamnummer'] ?? '');

                if ($serial === '' || $stam === '') {
                    $errors[] = "Rij {$line}: serial_number en stamnummer zijn verplicht.";

                    continue;
                }
                if (Student::find($stam) === null) {
                    $errors[] = "Rij {$line}: student {$stam} niet gevonden.";

                    continue;
                }

                $active = $this->activeNonReserve($serial);
                if ($active !== null && $active->stamnummer === $stam) {
                    $updated++;

                    continue;
                }
                if ($active !== null) {
                    $active->unlinked_at = now();
                    $active->save();
                }

                Laptop::create([
                    'serial_number' => $serial,
                    'stamnummer' => $stam,
                    'eigen_laptop' => false,
                    'linked_at' => now(),
                ]);
                $created++;
            }
        });

        return ['created' => $created, 'updated' => $updated, 'errors' => $errors];
    }

    /**
     * Alle reserve-laptops met info of ze in gebruik zijn (gekoppeld aan een niet-gesloten issue).
     */
    public function listAvailableReserveLaptops(): array
    {
        $reserves = Laptop::where('is_reserve', true)
            ->orderByRaw('alias IS NULL')
            ->orderBy('alias')
            ->orderBy('id')
            ->get();

        $inUse = DB::table('laptop_issues')
            ->whereNotNull('reserve_laptop_id')
            ->where('status', '!=', 'gesloten')
            ->get(['reserve_laptop_id', 'id', 'serial_number']);

        $results = [];
        foreach ($reserves as $laptop) {
            $issues = $inUse->where('reserve_laptop_id', $laptop->id);
            if ($issues->isEmpty()) {
                $issues = collect([null]);
            }
            foreach ($issues as $issue) {
                $inUseBy = null;
                if ($issue !== null) {
                    $student = DB::table('laptops')
                        ->leftJoin('students', 'students.stamnummer', '=', 'laptops.stamnummer')
                        ->where('laptops.serial_number', $issue->serial_number)
                        ->whereNull('laptops.unlinked_at')
                        ->first(['students.naam', 'students.voornaam']);
                    $name = trim(implode(' ', array_filter([$student?->voornaam, $student?->naam])));
                    $inUseBy = $name ?: ($issue->serial_number ?: '?');
                }
                $results[] = [
                    'id' => $laptop->id,
                    'alias' => $laptop->alias,
                    'serial_number' => $laptop->serial_number,
                    'in_use_by_issue_id' => $issue ? (int) $issue->id : null,
                    'in_use_by_student' => $inUseBy,
                ];
            }
        }

        return $results;
    }

    /** Alle leerlingen/leerkrachten met hun laptops, gesorteerd op naam, voornaam, stamnummer. */
    public function listStudents(): Collection
    {
        return Student::with(['laptops' => fn ($q) => $q->orderBy('id')])
            ->orderBy('naam')
            ->orderBy('voornaam')
            ->orderBy('stamnummer')
            ->get();
    }

    public static function parseDate(mixed $value): ?CarbonImmutable
    {
        return $value === null ? null : CarbonImmutable::parse($value);
    }
}
