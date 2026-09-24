<?php

namespace App\Services;

use App\Models\Laptop;
use App\Models\LaptopIssue;
use App\Models\LaptopIssueEntry;
use App\Support\DetailException;
use App\Support\Fmt;
use App\Support\Sql;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\Facades\DB;

class LaptopIssueService
{
    public const VALID_STATUSES = ['aangemeld', 'open', 'gesloten'];

    public const VALID_CATEGORIES = [
        'Scherm', 'Toetsenbord', 'Software', 'Oplader',
        'Batterij', 'Luidspreker', 'Accessoires', 'Overig',
    ];

    private static function studentLabel(?string $naam, ?string $voornaam): string
    {
        $parts = trim(implode(' ', array_filter([$voornaam, $naam])));

        return $parts ?: 'onbekende leerling';
    }

    private static function reserveLabel(Laptop $laptop): string
    {
        if ($laptop->alias && $laptop->serial_number) {
            return "{$laptop->alias} ({$laptop->serial_number})";
        }

        return $laptop->alias ?: ($laptop->serial_number ?: "#{$laptop->id}");
    }

    private function validateReserveLaptop(int $reserveLaptopId): Laptop
    {
        $laptop = Laptop::find($reserveLaptopId);
        if ($laptop === null) {
            throw new DetailException(422, 'Reserve-laptop niet gevonden.');
        }
        if (! $laptop->is_reserve) {
            throw new DetailException(422, 'Geselecteerde laptop is geen reserve-laptop.');
        }

        return $laptop;
    }

    /** Basisquery: issue + huidige leerling van de laptop + reserve-laptopinfo. */
    private function issueQuery(): Builder
    {
        return DB::table('laptop_issues')
            ->leftJoin('laptops', function ($join) {
                $join->on('laptops.serial_number', '=', 'laptop_issues.serial_number')
                    ->whereNull('laptops.unlinked_at');
            })
            ->leftJoin('students', 'students.stamnummer', '=', 'laptops.stamnummer')
            ->leftJoin('laptops as reserve', 'reserve.id', '=', 'laptop_issues.reserve_laptop_id')
            ->select([
                'laptop_issues.*',
                'students.naam', 'students.voornaam', 'students.stamnummer',
                'reserve.alias as reserve_alias', 'reserve.serial_number as reserve_serial',
            ])
            ->orderByDesc('laptop_issues.reported_date')
            ->orderByDesc('laptop_issues.id');
    }

    public function listIssues(string $search = '', bool $includeClosed = false, ?int $issueId = null): array
    {
        $query = $this->issueQuery();

        if ($issueId !== null) {
            $query->where('laptop_issues.id', $issueId);
        }
        if (! $includeClosed) {
            $query->where('laptop_issues.status', '!=', 'gesloten');
        }
        if ($search !== '') {
            $like = Sql::likeValue($search);
            $query->where(function (Builder $w) use ($like) {
                foreach (['laptop_issues.serial_number', 'students.naam', 'students.voornaam'] as $col) {
                    $w->orWhereRaw(Sql::likeExpr($col), [$like]);
                }
            });
        }

        return $query->get()->map(fn ($row) => [
            'id' => (int) $row->id,
            'serial_number' => $row->serial_number,
            'description' => $row->description,
            'reported_date' => LaptopService::parseDate($row->reported_date),
            'status' => $row->status,
            'solution' => $row->solution,
            'category' => $row->category,
            'naam' => $row->naam,
            'voornaam' => $row->voornaam,
            'stamnummer' => $row->stamnummer,
            'reserve_laptop_id' => $row->reserve_laptop_id !== null ? (int) $row->reserve_laptop_id : null,
            'reserve_laptop_alias' => $row->reserve_alias,
            'reserve_laptop_serial' => $row->reserve_serial,
        ])->all();
    }

    /** Issue als JSON (LaptopIssueRead). */
    public static function toJson(array $issue): array
    {
        $issue['reported_date'] = Fmt::date($issue['reported_date']);

        return $issue;
    }

    public function findForResponse(int $issueId): ?array
    {
        $rows = $this->listIssues(includeClosed: true, issueId: $issueId);

        return $rows ? self::toJson($rows[0]) : null;
    }

    public function createIssue(string $serialNumber, string $description, string $reportedDate,
        ?string $category = null, ?int $reserveLaptopId = null): LaptopIssue
    {
        $reserve = $reserveLaptopId !== null ? $this->validateReserveLaptop($reserveLaptopId) : null;

        return DB::transaction(function () use ($serialNumber, $description, $reportedDate, $category, $reserve) {
            $issue = LaptopIssue::create([
                'serial_number' => trim($serialNumber),
                'description' => trim($description),
                'reported_date' => $reportedDate,
                'status' => 'aangemeld',
                'category' => $category ?: null,
                'reserve_laptop_id' => $reserve?->id,
            ]);

            if ($reserve !== null) {
                $student = $this->getStudentForSerial($issue->serial_number);
                $label = self::studentLabel($student['naam'] ?? null, $student['voornaam'] ?? null);
                LaptopIssueEntry::create([
                    'issue_id' => $issue->id,
                    'text' => 'Reserve-laptop '.self::reserveLabel($reserve)." uitgeleend aan {$label}.",
                ]);
            }

            return $issue->refresh();
        });
    }

    /**
     * Issue bijwerken. Alleen sleutels die in $data zitten worden aangepast;
     * reserve_laptop_id => null betekent "reserve-laptop teruggebracht".
     */
    public function updateIssue(int $issueId, array $data): ?LaptopIssue
    {
        $issue = LaptopIssue::find($issueId);
        if ($issue === null) {
            return null;
        }

        $oldStatus = $issue->status;
        $oldReserveId = $issue->reserve_laptop_id;
        $reserveChanged = array_key_exists('reserve_laptop_id', $data);
        $newReserveId = $reserveChanged ? $data['reserve_laptop_id'] : $oldReserveId;

        if ($reserveChanged && $newReserveId !== null) {
            $this->validateReserveLaptop((int) $newReserveId);
        }

        return DB::transaction(function () use ($issue, $data, $oldStatus, $oldReserveId, $reserveChanged) {
            foreach ($data as $key => $value) {
                $issue->{$key} = $value;
            }

            $autoReleasedId = null;
            if ($issue->status === 'gesloten' && $oldStatus !== 'gesloten' && $issue->reserve_laptop_id !== null) {
                $autoReleasedId = $issue->reserve_laptop_id;
                $issue->reserve_laptop_id = null;
            }

            // Tijdlijnregels opbouwen vóór het opslaan zodat de hele wijziging atomair is.
            $finalReserveId = $issue->reserve_laptop_id;
            $texts = [];
            if ($autoReleasedId !== null) {
                $laptop = Laptop::find($autoReleasedId);
                if ($laptop !== null) {
                    $texts[] = 'Reserve-laptop '.self::reserveLabel($laptop).' teruggebracht (issue gesloten).';
                }
            } elseif ($reserveChanged && $oldReserveId !== $finalReserveId) {
                $student = $this->getStudentForSerial($issue->serial_number);
                $label = self::studentLabel($student['naam'] ?? null, $student['voornaam'] ?? null);
                if ($finalReserveId === null && $oldReserveId !== null) {
                    $old = Laptop::find($oldReserveId);
                    if ($old !== null) {
                        $texts[] = 'Reserve-laptop '.self::reserveLabel($old).' teruggebracht.';
                    }
                } elseif ($finalReserveId !== null) {
                    $new = Laptop::find($finalReserveId);
                    if ($new !== null) {
                        if ($oldReserveId === null) {
                            $texts[] = 'Reserve-laptop '.self::reserveLabel($new)." uitgeleend aan {$label}.";
                        } else {
                            $old = Laptop::find($oldReserveId);
                            $oldLabel = $old ? self::reserveLabel($old) : "#{$oldReserveId}";
                            $texts[] = "Reserve-laptop gewijzigd: {$oldLabel} → ".self::reserveLabel($new).'.';
                        }
                    }
                }
            }

            $issue->save();
            foreach ($texts as $text) {
                LaptopIssueEntry::create(['issue_id' => $issue->id, 'text' => trim($text)]);
            }

            return $issue->refresh();
        });
    }

    public function deleteIssue(int $issueId): bool
    {
        $issue = LaptopIssue::find($issueId);
        if ($issue === null) {
            return false;
        }
        $issue->delete();

        return true;
    }

    /** Alle laptops met minstens één issue in de gevraagde statussen. */
    public function listLaptopsWithIssues(string $search = '', ?array $statuses = null): array
    {
        $statuses ??= ['aangemeld', 'open'];
        $valid = array_values(array_intersect($statuses, self::VALID_STATUSES));
        if (! $valid) {
            return [];
        }

        $counts = DB::table('laptop_issues')
            ->select('serial_number')
            ->selectRaw("SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_count")
            ->selectRaw("SUM(CASE WHEN status = 'gesloten' THEN 1 ELSE 0 END) AS gesloten_count")
            ->selectRaw("SUM(CASE WHEN status = 'aangemeld' THEN 1 ELSE 0 END) AS aangemeld_count")
            ->groupBy('serial_number');

        $query = DB::query()
            ->fromSub($counts, 'counts')
            ->leftJoin('laptops', function ($join) {
                $join->on('laptops.serial_number', '=', 'counts.serial_number')
                    ->whereNull('laptops.unlinked_at');
            })
            ->leftJoin('students', 'students.stamnummer', '=', 'laptops.stamnummer')
            ->select([
                'counts.serial_number', 'counts.open_count', 'counts.gesloten_count', 'counts.aangemeld_count',
                'students.naam', 'students.voornaam', 'students.klas',
            ])
            ->where(function (Builder $w) use ($valid) {
                foreach ($valid as $status) {
                    $w->orWhere("counts.{$status}_count", '>', 0);
                }
            })
            ->orderByDesc('counts.open_count')
            ->orderBy('counts.serial_number');

        if ($search !== '') {
            $like = Sql::likeValue($search);
            $query->where(function (Builder $w) use ($like) {
                foreach (['counts.serial_number', 'students.naam', 'students.voornaam'] as $col) {
                    $w->orWhereRaw(Sql::likeExpr($col), [$like]);
                }
            });
        }

        return $query->get()->map(fn ($row) => [
            'serial_number' => $row->serial_number,
            'open_count' => (int) $row->open_count,
            'gesloten_count' => (int) $row->gesloten_count,
            'aangemeld_count' => (int) $row->aangemeld_count,
            'naam' => $row->naam,
            'voornaam' => $row->voornaam,
            'klas' => $row->klas,
        ])->all();
    }

    /** Alle opvolgingsregels van een issue, oudste eerst. */
    public function getEntriesForIssue(int $issueId): array
    {
        return LaptopIssueEntry::where('issue_id', $issueId)
            ->orderBy('created_at')
            ->orderBy('id')
            ->get()
            ->map(fn ($e) => ['id' => $e->id, 'text' => $e->text, 'created_at' => $e->created_at])
            ->all();
    }

    public function addIssueEntry(int $issueId, string $text): LaptopIssueEntry
    {
        return LaptopIssueEntry::create(['issue_id' => $issueId, 'text' => trim($text)])->refresh();
    }

    public function updateEntry(int $entryId, string $text): ?LaptopIssueEntry
    {
        $entry = LaptopIssueEntry::find($entryId);
        if ($entry === null) {
            return null;
        }
        $entry->text = trim($text);
        $entry->save();

        return $entry;
    }

    /** Verwijder een opvolgingsregel en geef de issue_id terug (of null als niet gevonden). */
    public function deleteEntry(int $entryId): ?int
    {
        $entry = LaptopIssueEntry::find($entryId);
        if ($entry === null) {
            return null;
        }
        $issueId = $entry->issue_id;
        $entry->delete();

        return $issueId;
    }

    /** Alle issues voor één serienummer, nieuwste eerst, met hun opvolgingsregels. */
    public function getIssuesForSerial(string $serial): array
    {
        $rows = DB::table('laptop_issues')
            ->leftJoin('laptops as reserve', 'reserve.id', '=', 'laptop_issues.reserve_laptop_id')
            ->where('laptop_issues.serial_number', $serial)
            ->orderByDesc('laptop_issues.reported_date')
            ->orderByDesc('laptop_issues.id')
            ->get(['laptop_issues.*', 'reserve.alias as reserve_alias', 'reserve.serial_number as reserve_serial']);

        if ($rows->isEmpty()) {
            return [];
        }

        $entries = LaptopIssueEntry::whereIn('issue_id', $rows->pluck('id'))
            ->orderBy('created_at')
            ->orderBy('id')
            ->get()
            ->groupBy('issue_id');

        return $rows->map(fn ($row) => [
            'id' => (int) $row->id,
            'serial_number' => $row->serial_number,
            'description' => $row->description,
            'reported_date' => LaptopService::parseDate($row->reported_date),
            'status' => $row->status,
            'solution' => $row->solution,
            'category' => $row->category,
            'reserve_laptop_id' => $row->reserve_laptop_id !== null ? (int) $row->reserve_laptop_id : null,
            'reserve_laptop_alias' => $row->reserve_alias,
            'reserve_laptop_serial' => $row->reserve_serial,
            'entries' => ($entries[$row->id] ?? collect())
                ->map(fn ($e) => ['id' => $e->id, 'text' => $e->text, 'created_at' => $e->created_at])
                ->values()->all(),
        ])->all();
    }

    /** De leerling die momenteel aan een serienummer gekoppeld is, of null. */
    public function getStudentForSerial(string $serial): ?array
    {
        $row = DB::table('students')
            ->join('laptops', function ($join) {
                $join->on('laptops.stamnummer', '=', 'students.stamnummer')
                    ->whereNull('laptops.unlinked_at');
            })
            ->where('laptops.serial_number', $serial)
            ->first(['students.naam', 'students.voornaam', 'students.klas', 'students.stamnummer', 'laptops.linked_at']);

        if ($row === null) {
            return null;
        }

        return [
            'naam' => $row->naam,
            'voornaam' => $row->voornaam,
            'klas' => $row->klas,
            'stamnummer' => $row->stamnummer,
            'linked_at' => LaptopService::parseDate($row->linked_at),
        ];
    }

    /** Totalen aangemeld / open / gesloten over alle laptops. */
    public function getGlobalStats(): array
    {
        $row = DB::table('laptop_issues')
            ->selectRaw("SUM(CASE WHEN status = 'aangemeld' THEN 1 ELSE 0 END) AS aangemeld")
            ->selectRaw("SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open")
            ->selectRaw("SUM(CASE WHEN status = 'gesloten' THEN 1 ELSE 0 END) AS gesloten")
            ->first();

        return [
            'aangemeld' => (int) ($row->aangemeld ?? 0),
            'open' => (int) ($row->open ?? 0),
            'gesloten' => (int) ($row->gesloten ?? 0),
        ];
    }

    /** 'reserve' of 'uitleen' voor speciale laptoptypes, null voor gewone laptops. */
    public function getLaptopType(string $serial): ?string
    {
        $row = DB::table('laptops')
            ->where('serial_number', $serial)
            ->orderByRaw('unlinked_at IS NULL DESC')
            ->orderByDesc('id')
            ->first(['is_reserve', 'storage_cabinet_id']);

        if ($row === null) {
            return null;
        }
        if ($row->is_reserve) {
            return 'reserve';
        }
        if ($row->storage_cabinet_id !== null) {
            return 'uitleen';
        }

        return null;
    }

    /** Laptops die matchen op serienummer of leerlingnaam (autocomplete). */
    public function searchLaptopsForAutocomplete(string $q): array
    {
        $like = Sql::likeValue($q);

        return DB::table('laptops')
            ->leftJoin('students', 'students.stamnummer', '=', 'laptops.stamnummer')
            ->whereNotNull('laptops.serial_number')
            ->whereNull('laptops.unlinked_at')
            ->where('laptops.is_reserve', false)
            ->where(function (Builder $w) use ($like) {
                foreach (['laptops.serial_number', 'students.naam', 'students.voornaam'] as $col) {
                    $w->orWhereRaw(Sql::likeExpr($col), [$like]);
                }
            })
            ->limit(20)
            ->get(['laptops.serial_number', 'students.naam', 'students.voornaam', 'students.stamnummer'])
            ->map(fn ($row) => [
                'serial_number' => $row->serial_number,
                'naam' => $row->naam,
                'voornaam' => $row->voornaam,
                'stamnummer' => $row->stamnummer,
            ])
            ->all();
    }
}
