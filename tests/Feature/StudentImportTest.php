<?php

namespace Tests\Feature;

use App\Models\Student;
use App\Services\StudentImportService;
use Illuminate\Http\UploadedFile;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class StudentImportTest extends TestCase
{
    private const HEADER = 'Instellingsnummer;Naam;Voornaam;Klas;Klascode;Klasnummer;Gebruikersnaam;Pointer;Stamnummer';

    private function csv(string ...$rows): string
    {
        return implode("\n", [self::HEADER, ...$rows]);
    }

    private function row(string $stamnummer, string $naam = 'Doe', string $voornaam = 'John', string $klas = '3A'): string
    {
        return "12345;{$naam};{$voornaam};{$klas};KL01;1;user_{$stamnummer};PTR1;{$stamnummer}";
    }

    private function import(string $content, bool $leerkracht = false): int
    {
        return app(StudentImportService::class)->importFromString($content, $leerkracht);
    }

    private function upload(string $content, string $name = 'students.csv', string $query = ''): TestResponse
    {
        return $this->post('/api/students/import'.$query, [
            'file' => UploadedFile::fake()->createWithContent($name, $content),
        ], ['Accept' => 'application/json']);
    }

    public function test_import_inserts_students(): void
    {
        $this->assertSame(2, $this->import($this->csv($this->row('S001'), $this->row('S002'))));
        $this->assertEqualsCanonicalizing(['S001', 'S002'], Student::pluck('stamnummer')->all());
    }

    public function test_import_upserts_existing_students(): void
    {
        $this->import($this->csv($this->row('S010', naam: 'OldName')));
        $this->assertSame(1, $this->import($this->csv($this->row('S010', naam: 'NewName'))));

        $this->assertSame(1, Student::where('stamnummer', 'S010')->count());
        $this->assertSame('NewName', Student::find('S010')->naam);
    }

    public function test_import_sets_last_import_timestamp(): void
    {
        $this->import($this->csv($this->row('S020')));
        $this->assertNotNull(Student::find('S020')->last_import);
    }

    public function test_import_strips_utf8_bom(): void
    {
        $this->import("\xEF\xBB\xBF".$this->csv($this->row('S021')));
        $this->assertSame('12345', Student::find('S021')->instellingsnummer);
    }

    public function test_import_route_returns_imported_count(): void
    {
        $this->upload($this->csv($this->row('S030'), $this->row('S031')))
            ->assertOk()->assertJson(['imported' => 2]);
    }

    public function test_import_route_rejects_non_csv(): void
    {
        $this->upload('some data', 'students.txt')->assertStatus(400);
    }

    public function test_import_teachers_sets_flag(): void
    {
        $this->assertSame(1, $this->import($this->csv($this->row('L001', klas: '')), true));
        $this->assertTrue(Student::find('L001')->is_leerkracht);
    }

    public function test_student_import_defaults_to_not_teacher(): void
    {
        $this->import($this->csv($this->row('S100')));
        $this->assertFalse(Student::find('S100')->is_leerkracht);
    }

    public function test_teacher_without_stamnummer_uses_gebruikersnaam(): void
    {
        $this->assertSame(1, $this->import("Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n", true));

        $teacher = Student::find('an.peeters');
        $this->assertSame('Peeters', $teacher->naam);
        $this->assertTrue($teacher->is_leerkracht);
    }

    public function test_student_without_stamnummer_is_still_skipped(): void
    {
        $this->assertSame(0, $this->import("Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n"));
    }

    public function test_teacher_import_headers_are_case_insensitive(): void
    {
        $this->import("NAAM ; voornaam;GEBRUIKERSNAAM\nJanssens;Tom;tom.janssens\n", true);

        $teacher = Student::find('tom.janssens');
        $this->assertSame('Janssens', $teacher->naam);
        $this->assertSame('Tom', $teacher->voornaam);
    }

    public function test_teacher_import_does_not_convert_existing_student(): void
    {
        $this->import($this->csv($this->row('X001', naam: 'Leerling')));

        $this->assertSame(0, $this->import($this->csv($this->row('X001', naam: 'Leerkracht')), true));
        $student = Student::find('X001');
        $this->assertFalse($student->is_leerkracht);
        $this->assertSame('Leerling', $student->naam);
    }

    public function test_import_route_teachers(): void
    {
        $this->upload("Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n", 'leerkrachten.csv', '?leerkracht=true')
            ->assertOk()->assertJson(['imported' => 1]);
        $this->assertTrue(Student::find('an.peeters')->is_leerkracht);
    }

    public function test_uitgeschreven_is_scoped_per_group(): void
    {
        $this->upload($this->csv($this->row('S200')), 's.csv');
        $this->upload("Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n", 'l.csv', '?leerkracht=true');

        $html = $this->get('/ui/students/manage')->getContent();

        $this->assertStringNotContainsString('Uitgeschreven', $html);
        $this->assertStringContainsString('badge-teacher', $html);
        $this->assertStringContainsString('data-group="leerkracht"', $html);
        $this->assertStringContainsString('data-group="leerling"', $html);
    }

    public function test_uitgeschreven_still_flags_students_missing_from_latest_import(): void
    {
        $this->import($this->csv($this->row('S300'), $this->row('S301')));
        $this->import($this->csv($this->row('L300')), true);
        $old = Student::find('S300');
        $old->last_import = $old->last_import->subDays(30);
        $old->save();

        $html = $this->get('/ui/students/list')->getContent();

        $this->assertSame(1, substr_count($html, 'badge-old'));
    }

    public function test_teacher_can_be_linked_to_laptop(): void
    {
        $this->upload("Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n", 'l.csv', '?leerkracht=true');

        $this->link('an.peeters', 'SN-LK-1')->assertOk();
        $serials = collect($this->getJson('/api/laptops')->json())->pluck('serial_number');
        $this->assertContains('SN-LK-1', $serials);
    }

    public function test_create_teacher_manually(): void
    {
        $this->postJson('/api/students', ['stamnummer' => 'lk.manual', 'is_leerkracht' => true])
            ->assertOk()->assertJson(['is_leerkracht' => true]);
    }

    public function test_index_shows_teacher_import_and_filters(): void
    {
        $html = $this->get('/')->getContent();

        $this->assertStringContainsString('/ui/students/import?leerkracht=true', $html);
        $this->assertStringContainsString('__leerkrachten__', $html);
    }

    // ── Echte leerkrachten-export (tab-gescheiden, fictieve gegevens) ─────

    private function teacherCsv(): string
    {
        $header = implode("\t", [
            'Instellingsnummers', 'Naam', 'Voornaam', 'Roepnaam', 'Gebruikersnaam', 'StandaardPaswoord',
            'Pointer', 'Betaalkaart', 'Barcode', 'Pincode', 'PointerZonderPrefix', 'Gebruikersnaam AD (kort)',
            'Gebruikersnaam AD', 'Gebruikersnaam O365', 'Gebruikersnaam Google', 'Afkorting',
        ]);
        $row = implode("\t", [
            '099999', 'Voorbeeld', 'Élise', '', 'elise.voorbeeld', 'geheim-Wachtwoord1', '500001', '', '22222',
            '98765432', '500001', 'elise.voorbeeld', 'elise.voorbeeld@school.example', 'elise.voorbeeld@school.example',
            'elise.voorbeeld@', 'VOOEL',
        ]);

        return "{$header}\n{$row}\n";
    }

    public function test_real_teacher_export_is_imported(): void
    {
        $this->assertSame(1, $this->import($this->teacherCsv(), true));

        $teacher = Student::find('elise.voorbeeld');
        $this->assertTrue($teacher->is_leerkracht);
        $this->assertSame('Voorbeeld', $teacher->naam);
        $this->assertSame('Élise', $teacher->voornaam);
        $this->assertSame('VOOEL', $teacher->afkorting);
        $this->assertSame('099999', $teacher->instellingsnummer);
        $this->assertSame('500001', $teacher->pointer);
    }

    public function test_teacher_export_passwords_are_not_stored(): void
    {
        $this->import($this->teacherCsv(), true);

        $stored = array_map('strval', array_values(Student::find('elise.voorbeeld')->getAttributes()));
        $this->assertNotContains('geheim-Wachtwoord1', $stored); // StandaardPaswoord
        $this->assertNotContains('98765432', $stored); // Pincode
    }

    public function test_teacher_export_is_searchable_by_afkorting(): void
    {
        $this->import($this->teacherCsv(), true);

        $this->assertStringContainsString('VOOEL', $this->get('/ui/students/manage')->getContent());
    }

    public function test_semicolon_and_comma_csv_still_work(): void
    {
        $this->import($this->csv($this->row('S400')));
        $this->import("Naam,Voornaam,Gebruikersnaam\nJanssens,Tom,tom.janssens\n", true);

        $this->assertSame('Doe', Student::find('S400')->naam);
        $this->assertSame('Janssens', Student::find('tom.janssens')->naam);
    }
}
