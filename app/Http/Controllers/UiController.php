<?php

namespace App\Http\Controllers;

use App\Services\LaptopService;
use App\Services\PhotoService;
use App\Services\StorageCabinetService;
use App\Services\StudentImportService;
use App\Support\Fmt;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Collection;
use Illuminate\View\View;

/** Volledige pagina's en HTMX-partials. */
class UiController extends Controller
{
    public function __construct(
        private readonly LaptopService $laptops,
        private readonly StorageCabinetService $cabinets,
        private readonly StudentImportService $importer,
        private readonly PhotoService $photos,
    ) {}

    /**
     * Meest recente last_import per groep (leerling / leerkracht).
     * Per groep zodat een leerkrachten-import niet elke leerling als "Uitgeschreven" markeert.
     */
    public static function latestImportAt(Collection $students): array
    {
        $latest = [0 => null, 1 => null];
        foreach ($students as $student) {
            $group = $student->is_leerkracht ? 1 : 0;
            if ($student->last_import && ($latest[$group] === null || $student->last_import->gt($latest[$group]))) {
                $latest[$group] = $student->last_import;
            }
        }

        return $latest;
    }

    private function studentViewData(): array
    {
        $students = $this->laptops->listStudents();

        return ['students' => $students, 'latest_import_at' => self::latestImportAt($students)];
    }

    public function index(): View
    {
        return view('index', $this->studentViewData());
    }

    public function barcodes(): View
    {
        return view('barcodes');
    }

    /** Mobiele fotopagina. */
    public function photos(): View
    {
        return view('photos');
    }

    public function studentsList(): View
    {
        return view('partials.student_list', $this->studentViewData());
    }

    public function studentsManage(): View
    {
        return view('partials.manage_student_list', $this->studentViewData());
    }

    public function photoGallery(Request $request): View
    {
        $serial = (string) $request->query('serial', '');

        return view('partials.photo_gallery', [
            'photos' => $serial !== '' ? $this->photos->listPhotos($serial) : [],
            'serial_number' => $serial,
        ]);
    }

    public function laptopsManage(Request $request): View
    {
        [$active, $kind] = LaptopService::parseLaptopFilters($request->query('active', 'all'), $request->query('kind', 'all'));
        $columns = LaptopService::parseColumnFilters([
            'serial' => $request->query('c_serial'), 'student' => $request->query('c_student'),
            'klas' => $request->query('c_klas'), 'status' => $request->query('c_status'),
            'acc' => $request->query('c_acc'), 'date' => $request->query('c_date'),
        ]);

        return view('partials.manage_laptop_list', [
            'laptops' => $this->laptops->getAllLaptops(q: $request->query('q') ?: null, active: $active, kind: $kind, columns: $columns),
        ]);
    }

    public function cabinetsManage(Request $request): View
    {
        return view('partials.manage_cabinet_list', [
            'cabinets' => $this->cabinets->listCabinets($request->query('q') ?: null, $request->query('kind') ?: null),
        ]);
    }

    public function importLaptops(Request $request): Response
    {
        $file = $request->file('file');
        if (! $file || ! str_ends_with($file->getClientOriginalName(), '.csv')) {
            return response('<span class="status error">Alleen CSV-bestanden zijn toegestaan.</span>', 400);
        }
        $result = $this->laptops->importLaptopsCsv($file->get());
        $errors = $result['errors']
            ? ' <span style="color:var(--red)">('.count($result['errors']).' fout(en))</span>'
            : '';

        return response("<span class=\"status success\">✓ {$result['created']} aangemaakt, {$result['updated']} ongewijzigd.{$errors}</span>");
    }

    /**
     * CSV-import via de UI; geeft een statusmelding terug. De frontend (Alpine.js)
     * vernieuwt daarna beide leerlingenlijsten via aparte HTMX-GETs.
     */
    public function importStudents(Request $request): Response
    {
        $file = $request->file('file');
        if (! $file || ! str_ends_with($file->getClientOriginalName(), '.csv')) {
            return response('<span class="status error">Alleen CSV-bestanden zijn toegestaan.</span>', 400);
        }
        $leerkracht = Fmt::bool($request->query('leerkracht'));
        $count = $this->importer->importFromString($file->get(), $leerkracht);
        $label = $leerkracht ? 'leerkracht(en)' : 'student(en)';

        return response("<span class=\"status success\">✓ {$count} {$label} geïmporteerd.</span>");
    }
}
