<?php

namespace App\Http\Controllers;

use App\Services\LaptopIssueService;
use App\Services\LaptopService;
use App\Services\PhotoService;
use App\Support\CsvWriter;
use App\Support\DetailException;
use App\Support\Fmt;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;

class LaptopController extends Controller
{
    public function __construct(
        private readonly LaptopService $laptops,
        private readonly LaptopIssueService $issues,
        private readonly PhotoService $photos,
    ) {}

    public function index(Request $request): JsonResponse
    {
        $active = $request->has('active') ? Fmt::bool($request->query('active')) : null;
        $laptops = $this->laptops->getAllLaptops(
            q: $request->query('q'),
            active: $active,
            kind: (string) $request->query('kind', 'all'),
        );

        return response()->json(LaptopService::listForJson($laptops));
    }

    /** Beheeroverzicht als CSV (respecteert de huidige filters). */
    public function export(Request $request): \Symfony\Component\HttpFoundation\Response
    {
        [$active, $kind] = LaptopService::parseLaptopFilters($request->query('active', 'all'), $request->query('kind', 'all'));
        $columns = LaptopService::parseColumnFilters([
            'serial' => $request->query('c_serial'), 'student' => $request->query('c_student'),
            'klas' => $request->query('c_klas'), 'status' => $request->query('c_status'),
            'acc' => $request->query('c_acc'), 'date' => $request->query('c_date'),
        ]);
        $laptops = $this->laptops->getAllLaptops(q: $request->query('q') ?: null, active: $active, kind: $kind, columns: $columns);

        // Labels hieronder spiegelen de weergave in partials/manage_laptop_list — houd beide in sync.
        $typeLabel = function (array $l): string {
            if ($l['eigen_laptop']) {
                return 'Eigen laptop';
            }
            if ($l['is_reserve']) {
                return 'Reserve';
            }
            if ($l['cabinet_kind'] === 'magazijn') {
                return 'Magazijn';
            }

            return $l['storage_cabinet_id'] !== null ? 'Kast' : 'Leerling';
        };
        // Accessoire-status alleen zinvol voor ingeleverde leerling-laptops.
        $jaNee = function (array $l, string $field): string {
            if ($l['is_active'] || $l['is_reserve'] || $l['eigen_laptop'] || $l['storage_cabinet_id'] !== null) {
                return '';
            }

            return $l[$field] ? 'ja' : 'nee';
        };

        $csv = new CsvWriter(';');
        $csv->row([
            'Serienummer', 'Type', 'Leerling', 'Stamnummer', 'Klas',
            'Alias', 'Locatie', 'Status', 'Hoes ingeleverd', 'Oplader ingeleverd',
            'Gekoppeld op', 'Ingeleverd op',
        ]);
        foreach ($laptops as $l) {
            $leerling = trim(($l['voornaam'] ?? '').' '.($l['naam'] ?? ''));
            $locatie = $l['cabinet_name'] ?? '';
            if ($locatie && $l['cabinet_location']) {
                $locatie = "{$locatie} ({$l['cabinet_location']})";
            }
            $csv->row([
                $l['serial_number'] ?: '',
                $typeLabel($l),
                Fmt::csvSafe($leerling),
                $l['stamnummer'] ?? '',
                Fmt::csvSafe($l['klas']),
                Fmt::csvSafe($l['alias']),
                Fmt::csvSafe($locatie),
                $l['is_active'] ? 'Actief' : 'Inactief',
                $jaNee($l, 'hoes_ingeleverd'),
                $jaNee($l, 'oplader_ingeleverd'),
                $l['linked_at']?->format('d/m/Y H:i') ?? '',
                $l['unlinked_at']?->format('d/m/Y H:i') ?? '',
            ]);
        }

        return $csv->download('laptops-'.now()->format('Ymd').'.csv');
    }

    public function reservesAvailable(): JsonResponse
    {
        return response()->json($this->laptops->listAvailableReserveLaptops());
    }

    public function store(Request $request): JsonResponse
    {
        $data = $this->body($request);
        $laptop = $this->laptops->createLaptop(
            serialNumber: $this->optString($data, 'serial_number'),
            stamnummer: $this->optString($data, 'stamnummer'),
            isReserve: $this->optBool($data, 'is_reserve', false),
            alias: $this->optString($data, 'alias'),
            storageCabinetId: $this->optInt($data, 'storage_cabinet_id'),
        );

        return response()->json(LaptopService::toResponse($laptop));
    }

    public function bulk(Request $request): JsonResponse
    {
        $data = $this->body($request);

        return response()->json($this->laptops->bulkCreateLaptops(
            $this->stringList($data, 'serials'),
            isReserve: $this->optBool($data, 'is_reserve', false),
            storageCabinetId: $this->optInt($data, 'storage_cabinet_id'),
        ));
    }

    public function import(Request $request): JsonResponse
    {
        $file = $request->file('file');
        if (! $file || ! str_ends_with($file->getClientOriginalName(), '.csv')) {
            throw new DetailException(400, 'Alleen CSV-bestanden zijn toegestaan.');
        }

        return response()->json($this->laptops->importLaptopsCsv($file->get()));
    }

    public function update(Request $request, int $laptopId): JsonResponse
    {
        $data = $this->body($request);
        $update = [];
        foreach (['serial_number', 'stamnummer', 'alias'] as $key) {
            if (array_key_exists($key, $data)) {
                $update[$key] = $this->optString($data, $key);
            }
        }
        if (array_key_exists('is_reserve', $data)) {
            $update['is_reserve'] = $data['is_reserve'] === null ? null : $this->optBool($data, 'is_reserve', false);
        }
        if (array_key_exists('storage_cabinet_id', $data)) {
            $update['storage_cabinet_id'] = $this->optInt($data, 'storage_cabinet_id');
        }

        return response()->json(LaptopService::toResponse($this->laptops->updateLaptop($laptopId, $update)));
    }

    public function destroy(int $laptopId): Response
    {
        $this->laptops->deleteLaptopPermanently($laptopId);

        return response()->noContent();
    }

    public function link(Request $request): JsonResponse
    {
        $data = $this->body($request);
        $laptop = $this->laptops->linkLaptopToStudent(
            $this->requireString($data, 'stamnummer'),
            $this->requireString($data, 'serial_number'),
            $this->optBool($data, 'overwrite_existing', false),
        );

        return response()->json(LaptopService::toResponse($laptop));
    }

    public function unlink(Request $request, int $laptopId): JsonResponse
    {
        $data = $this->body($request, optional: true);
        $laptop = $this->laptops->unlinkLaptop(
            $laptopId,
            $this->optBool($data, 'hoes_ingeleverd', true),
            $this->optBool($data, 'oplader_ingeleverd', true),
        );

        return response()->json(LaptopService::toResponse($laptop));
    }

    public function search(Request $request): JsonResponse
    {
        $q = (string) $request->query('q', '');
        if (mb_strlen($q) < 2) {
            return response()->json([]);
        }

        return response()->json($this->issues->searchLaptopsForAutocomplete($q));
    }

    /** Laptoptype voor het contextpaneel. */
    public function info(Request $request): JsonResponse
    {
        $serial = $this->requireQuery($request, 'serial');

        return response()->json(['laptop_type' => $this->issues->getLaptopType($serial)]);
    }

    /** Gebundelde rapportdata voor de tab "Laptop info". */
    public function report(Request $request): JsonResponse
    {
        $serial = trim($this->requireQuery($request, 'serial'));
        if ($serial === '') {
            return response()->json([
                'serial' => '', 'laptop_type' => null, 'student' => null,
                'history' => [], 'issues' => [], 'photos' => [],
            ]);
        }

        $student = $this->issues->getStudentForSerial($serial);
        if ($student) {
            $student['linked_at'] = Fmt::iso($student['linked_at']);
        }

        return response()->json([
            'serial' => $serial,
            'laptop_type' => $this->issues->getLaptopType($serial),
            'student' => $student,
            'history' => array_map(function (array $h) {
                $h['linked_at'] = Fmt::iso($h['linked_at']);
                $h['unlinked_at'] = Fmt::iso($h['unlinked_at']);

                return $h;
            }, $this->laptops->getAssignmentHistory($serial)),
            'issues' => array_map(fn (array $i) => [
                'id' => $i['id'],
                'description' => $i['description'],
                'status' => $i['status'],
                'category' => $i['category'],
                'reported_date' => Fmt::date($i['reported_date']),
            ], $this->issues->getIssuesForSerial($serial)),
            'photos' => array_slice($this->photos->listPhotos($serial), 0, 5),
        ]);
    }

    private function requireQuery(Request $request, string $key): string
    {
        if (! $request->has($key)) {
            throw new DetailException(422, "Queryparameter '{$key}' is verplicht.");
        }

        return (string) $request->query($key, '');
    }
}
