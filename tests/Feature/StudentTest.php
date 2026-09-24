<?php

namespace Tests\Feature;

use App\Models\Laptop;
use App\Models\Student;
use App\Services\LaptopService;
use App\Services\StudentService;
use Tests\TestCase;

class StudentTest extends TestCase
{
    public function test_delete_students_returns_correct_count(): void
    {
        $this->addStudent('D001');
        $this->addStudent('D002');
        $this->addStudent('D003');

        $this->assertSame(2, app(StudentService::class)->deleteByStamnummers(['D001', 'D002']));
        $this->assertSame(['D003'], Student::pluck('stamnummer')->all());
    }

    public function test_delete_cascades_to_laptops(): void
    {
        $this->addStudent('D010');
        Laptop::create(['serial_number' => 'SN-CASCADE-01', 'stamnummer' => 'D010']);

        app(StudentService::class)->deleteByStamnummers(['D010']);

        $this->assertSame(0, Laptop::where('stamnummer', 'D010')->count());
    }

    public function test_delete_ignores_empty_list(): void
    {
        $this->addStudent('D020');

        $this->assertSame(0, app(StudentService::class)->deleteByStamnummers([]));
        $this->assertSame(1, Student::count());
    }

    public function test_list_students_sorted_by_naam_then_voornaam(): void
    {
        $this->addStudent('L001', 'Zorro', 'A');
        $this->addStudent('L002', 'Aardig', 'Z');
        $this->addStudent('L003', 'Aardig', 'A');

        $names = app(LaptopService::class)->listStudents()->map(fn ($s) => [$s->naam, $s->voornaam])->all();
        $this->assertSame([['Aardig', 'A'], ['Aardig', 'Z'], ['Zorro', 'A']], $names);
    }

    public function test_delete_route(): void
    {
        $this->addStudent('R001');
        $this->addStudent('R002');

        $this->deleteJson('/api/students', ['stamnummers' => ['R001', 'R002']])->assertOk()->assertJson(['deleted' => 2]);
    }

    public function test_get_students_route(): void
    {
        $this->addStudent('G001', 'Alpha');
        $this->addStudent('G002', 'Beta');
        $this->link('G001', 'SN-G1');

        $students = collect($this->getJson('/api/students')->assertOk()->json())->keyBy('stamnummer');
        $this->assertTrue($students->has('G002'));
        $this->assertSame([['id' => $students['G001']['laptops'][0]['id'], 'serial_number' => 'SN-G1', 'eigen_laptop' => false]],
            $students['G001']['laptops']);
        $this->assertFalse($students['G001']['is_leerkracht']);
    }

    public function test_create_and_update_student(): void
    {
        $this->postJson('/api/students', ['stamnummer' => ' N001 ', 'naam' => ' Nieuw ', 'klasnummer' => '0'])
            ->assertOk()->assertJson(['stamnummer' => 'N001', 'naam' => 'Nieuw', 'klasnummer' => '0']);
        $this->postJson('/api/students', ['stamnummer' => 'N001'])->assertStatus(409);
        $this->postJson('/api/students', ['stamnummer' => '  '])->assertStatus(422);

        $this->putJson('/api/students/N001', ['klas' => '5B', 'naam' => null])
            ->assertOk()->assertJson(['klas' => '5B', 'naam' => 'Nieuw']);
        $this->putJson('/api/students/ONBEKEND', ['klas' => '5B'])->assertStatus(404);
    }

    public function test_students_list_partial_shows_linked_laptop(): void
    {
        $this->addStudent('P001', "O'Brien", 'Sean');
        $this->link('P001', 'SN-P1');

        $html = $this->get('/ui/students/list')->assertOk()->getContent();
        $this->assertStringContainsString('Laptop serienummer: SN-P1', $html);
        $this->assertStringContainsString('O&#039;Brien', $html);
    }
}
