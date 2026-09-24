<?php

namespace App\Services;

use App\Models\Student;
use App\Support\DetailException;
use App\Support\Fmt;

class StudentService
{
    public const EDITABLE_FIELDS = [
        'instellingsnummer', 'naam', 'voornaam', 'klas', 'klascode',
        'klasnummer', 'gebruikersnaam', 'pointer', 'afkorting',
    ];

    /** Leerlingen (en via cascade hun laptops) verwijderen op stamnummer. */
    public function deleteByStamnummers(array $stamnummers): int
    {
        $normalized = array_values(array_filter(array_map(fn ($s) => trim((string) $s), $stamnummers)));
        if (! $normalized) {
            return 0;
        }

        $students = Student::whereIn('stamnummer', $normalized)->get();
        foreach ($students as $student) {
            $student->delete();
        }

        return $students->count();
    }

    /** Eén leerling (of leerkracht) manueel aanmaken. */
    public function create(string $stamnummer, bool $isLeerkracht = false, array $fields = []): Student
    {
        $normalized = trim($stamnummer);
        if ($normalized === '') {
            throw new DetailException(422, 'Stamnummer is verplicht.');
        }
        if (Student::find($normalized) !== null) {
            throw new DetailException(409, "Student {$normalized} bestaat al.");
        }

        $student = new Student([
            'stamnummer' => $normalized,
            'is_leerkracht' => $isLeerkracht,
            'last_import' => now(),
        ]);
        foreach (self::EDITABLE_FIELDS as $key) {
            if (isset($fields[$key])) {
                $student->{$key} = Fmt::strOrNull($fields[$key]);
            }
        }
        $student->save();

        return $student->refresh();
    }

    /** Bewerkbare velden bijwerken. Het stamnummer (sleutel) kan niet wijzigen. */
    public function update(string $stamnummer, array $fields): Student
    {
        $student = Student::find($stamnummer);
        if ($student === null) {
            throw new DetailException(404, "Student {$stamnummer} bestaat niet.");
        }

        foreach (self::EDITABLE_FIELDS as $key) {
            if (isset($fields[$key])) {
                $student->{$key} = Fmt::strOrNull($fields[$key]);
            }
        }
        $student->save();

        return $student->refresh();
    }

    /** Leerling als JSON (StudentRead in de Python-versie). */
    public static function toResponse(Student $student): array
    {
        return [
            'stamnummer' => $student->stamnummer,
            'instellingsnummer' => $student->instellingsnummer,
            'naam' => $student->naam,
            'voornaam' => $student->voornaam,
            'klas' => $student->klas,
            'klascode' => $student->klascode,
            'klasnummer' => $student->klasnummer,
            'gebruikersnaam' => $student->gebruikersnaam,
            'pointer' => $student->pointer,
            'afkorting' => $student->afkorting,
            'last_import' => Fmt::iso($student->last_import),
            'is_leerkracht' => (bool) $student->is_leerkracht,
            'laptops' => $student->laptops->map(fn ($l) => [
                'id' => $l->id,
                'serial_number' => $l->serial_number,
                'eigen_laptop' => (bool) $l->eigen_laptop,
            ])->values()->all(),
        ];
    }
}
