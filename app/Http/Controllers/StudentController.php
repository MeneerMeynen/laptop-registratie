<?php

namespace App\Http\Controllers;

use App\Services\LaptopService;
use App\Services\StudentImportService;
use App\Services\StudentService;
use App\Support\DetailException;
use App\Support\Fmt;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class StudentController extends Controller
{
    public function __construct(
        private readonly StudentService $students,
        private readonly StudentImportService $importer,
        private readonly LaptopService $laptops,
    ) {}

    public function index(): JsonResponse
    {
        return response()->json($this->laptops->listStudents()->map([StudentService::class, 'toResponse'])->values());
    }

    public function import(Request $request): JsonResponse
    {
        $file = $request->file('file');
        if (! $file || ! str_ends_with($file->getClientOriginalName(), '.csv')) {
            throw new DetailException(400, 'Only CSV files are accepted.');
        }
        $count = $this->importer->importFromString($file->get(), Fmt::bool($request->query('leerkracht')));

        return response()->json(['imported' => $count]);
    }

    public function store(Request $request): JsonResponse
    {
        $data = $this->body($request);
        $fields = [];
        foreach (StudentService::EDITABLE_FIELDS as $key) {
            $fields[$key] = $this->optString($data, $key);
        }
        $student = $this->students->create(
            $this->requireString($data, 'stamnummer'),
            $this->optBool($data, 'is_leerkracht', false),
            $fields,
        );

        return response()->json(StudentService::toResponse($student->load('laptops')));
    }

    public function update(Request $request, string $stamnummer): JsonResponse
    {
        $data = $this->body($request);
        $fields = [];
        foreach (StudentService::EDITABLE_FIELDS as $key) {
            $fields[$key] = $this->optString($data, $key);
        }

        return response()->json(StudentService::toResponse($this->students->update($stamnummer, $fields)->load('laptops')));
    }

    public function destroy(Request $request): JsonResponse
    {
        $data = $this->body($request);

        return response()->json(['deleted' => $this->students->deleteByStamnummers($this->stringList($data, 'stamnummers'))]);
    }
}
