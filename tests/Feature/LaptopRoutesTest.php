<?php

namespace Tests\Feature;

use App\Models\Laptop;
use App\Models\LaptopIssue;
use Illuminate\Http\UploadedFile;
use Tests\TestCase;

class LaptopRoutesTest extends TestCase
{
    public function test_link_laptop_to_student(): void
    {
        $this->addStudent('S001');

        $this->link('S001', 'ABC-001')->assertOk()
            ->assertJson(['stamnummer' => 'S001', 'serial_number' => 'ABC-001', 'eigen_laptop' => false]);
    }

    public function test_link_laptop_alphanumeric_serial(): void
    {
        $this->addStudent('S002');

        $this->link('S002', 'HP-NB-2024-XZ99')->assertOk()->assertJson(['serial_number' => 'HP-NB-2024-XZ99']);
    }

    public function test_link_laptop_returns_404_for_unknown_student(): void
    {
        $this->link('UNKNOWN', 'SER-999')->assertStatus(404);
    }

    public function test_link_requires_fields(): void
    {
        $this->postJson('/api/laptops/link', ['stamnummer' => 'S1'])->assertStatus(422);
    }

    public function test_link_laptop_conflict_existing_serial(): void
    {
        $this->addStudent('S010');
        $this->addStudent('S011');
        $this->link('S010', 'SHARED-001');

        $resp = $this->link('S011', 'SHARED-001')->assertStatus(409);
        $this->assertIsString($resp->json('detail'));
    }

    public function test_link_requires_confirmation_when_student_already_has_laptop(): void
    {
        $this->addStudent('S020');
        $this->link('S020', 'FIRST-001');

        $detail = $this->link('S020', 'SECOND-001')->assertStatus(409)->json('detail');
        $this->assertTrue($detail['requires_confirmation']);
        $this->assertContains('FIRST-001', $detail['existing_serials']);
    }

    public function test_link_overwrites_after_confirmation(): void
    {
        $this->addStudent('S030');
        $this->link('S030', 'OLD-001');

        $this->link('S030', 'NEW-001', true)->assertOk()->assertJson(['serial_number' => 'NEW-001']);
    }

    public function test_link_eigen_laptop(): void
    {
        $this->addStudent('S040');

        $this->link('S040', 'eigen laptop')->assertOk()
            ->assertJson(['eigen_laptop' => true, 'serial_number' => null]);
    }

    public function test_link_eigen_laptop_overwrites_existing(): void
    {
        $this->addStudent('S050');
        $this->link('S050', 'REG-001');

        $this->link('S050', 'eigen laptop', true)->assertOk()->assertJson(['eigen_laptop' => true]);
    }

    public function test_relinking_same_laptop_is_idempotent(): void
    {
        $this->addStudent('S070');
        $first = $this->link('S070', 'REPEAT-001')->assertOk();
        $second = $this->link('S070', 'REPEAT-001')->assertOk();
        $third = $this->link('S070', 'REPEAT-001')->assertOk();

        $this->assertSame($first->json('id'), $second->json('id'));
        $this->assertSame($first->json('id'), $third->json('id'));
        $this->assertNull($second->json('unlinked_at'));
        $this->assertSame(1, Laptop::where('serial_number', 'REPEAT-001')->count());
    }

    public function test_relinking_same_eigen_laptop_is_idempotent(): void
    {
        $this->addStudent('S071');
        $first = $this->link('S071', 'eigen laptop');
        $second = $this->link('S071', 'eigen laptop')->assertOk();

        $this->assertSame($first->json('id'), $second->json('id'));
        $this->assertSame(1, Laptop::where('stamnummer', 'S071')->where('eigen_laptop', true)->count());
    }

    public function test_multiple_students_can_each_have_eigen_laptop(): void
    {
        $this->addStudent('S060');
        $this->addStudent('S061');

        $this->link('S060', 'eigen laptop')->assertOk();
        $this->link('S061', 'eigen laptop')->assertOk();
    }

    // ── Inleveren ─────────────────────────────────────────────────────────

    public function test_unlink_sets_unlinked_at(): void
    {
        $this->addStudent('S100');
        $id = $this->link('S100', 'UNL-001')->json('id');

        $resp = $this->unlink($id)->assertOk()->assertJson(['hoes_ingeleverd' => true, 'oplader_ingeleverd' => true]);
        $this->assertNotNull($resp->json('unlinked_at'));
        $this->assertSame(0, LaptopIssue::where('serial_number', 'UNL-001')->count());
    }

    public function test_unlink_returns_404_for_unknown_laptop(): void
    {
        $this->unlink(99999)->assertStatus(404);
    }

    public function test_unlink_already_unlinked_returns_409(): void
    {
        $this->addStudent('S110');
        $id = $this->link('S110', 'UNL-002')->json('id');
        $this->unlink($id);

        $this->unlink($id)->assertStatus(409);
    }

    public function test_unlink_without_body_uses_defaults(): void
    {
        $this->addStudent('S105');
        $id = $this->link('S105', 'UNL-NB')->json('id');

        $this->post("/api/laptops/{$id}/unlink", [], ['Accept' => '*/*'])->assertOk()
            ->assertJson(['hoes_ingeleverd' => true, 'oplader_ingeleverd' => true]);
    }

    public function test_unlink_with_missing_accessories_creates_issue(): void
    {
        $this->addStudent('S120');
        $id = $this->link('S120', 'UNL-MISS')->json('id');

        $this->unlink($id, hoes: false)->assertOk()->assertJson(['hoes_ingeleverd' => false, 'oplader_ingeleverd' => true]);

        $laptop = Laptop::find($id);
        $this->assertFalse($laptop->hoes_ingeleverd);
        $this->assertTrue($laptop->oplader_ingeleverd);

        $issues = LaptopIssue::where('serial_number', 'UNL-MISS')->get();
        $this->assertCount(1, $issues);
        $this->assertSame('Accessoires', $issues[0]->category);
        $this->assertSame('aangemeld', $issues[0]->status);
        $this->assertStringContainsString('hoes', strtolower($issues[0]->description));
        $this->assertStringNotContainsString('oplader', strtolower($issues[0]->description));
    }

    public function test_unlink_with_both_accessories_missing_lists_both_in_issue(): void
    {
        $this->addStudent('S121');
        $id = $this->link('S121', 'UNL-BOTH')->json('id');

        $this->unlink($id, hoes: false, oplader: false)->assertOk();

        $issues = LaptopIssue::where('serial_number', 'UNL-BOTH')->get();
        $this->assertCount(1, $issues);
        $this->assertStringContainsString('hoes', $issues[0]->description);
        $this->assertStringContainsString('oplader', $issues[0]->description);
    }

    public function test_relink_resets_accessory_flags(): void
    {
        $this->addStudent('S130');
        $this->addStudent('S131');
        $firstId = $this->link('S130', 'UNL-RST')->json('id');
        $this->unlink($firstId, false, false);

        $secondId = $this->link('S131', 'UNL-RST')->assertOk()->json('id');

        $this->assertNotSame($firstId, $secondId);
        $record = Laptop::find($secondId);
        $this->assertTrue($record->hoes_ingeleverd);
        $this->assertTrue($record->oplader_ingeleverd);
    }

    // ── Reserve-laptops ───────────────────────────────────────────────────

    public function test_create_reserve_laptop_without_stamnummer(): void
    {
        $this->createReserve('Reserve-1', 'RES-001')->assertOk()->assertJson([
            'is_reserve' => true, 'alias' => 'Reserve-1', 'serial_number' => 'RES-001', 'stamnummer' => null,
        ]);
    }

    public function test_create_reserve_laptop_without_serial(): void
    {
        $this->createReserve('Reserve-2')->assertOk()->assertJson(['is_reserve' => true, 'serial_number' => null]);
    }

    public function test_create_reserve_requires_alias(): void
    {
        $this->postJson('/api/laptops', ['is_reserve' => true])->assertStatus(422);
    }

    public function test_create_normal_laptop_still_requires_stamnummer(): void
    {
        $this->assertContains($this->postJson('/api/laptops', ['serial_number' => 'ABC123'])->status(), [404, 422]);
    }

    public function test_list_laptops_kind_filter_reserve(): void
    {
        $this->addStudent('S200');
        $this->postJson('/api/laptops', ['serial_number' => 'NORM-001', 'stamnummer' => 'S200']);
        $this->createReserve('Reserve-X', 'RES-X01');

        $items = $this->getJson('/api/laptops?kind=reserve')->assertOk()->json();
        $this->assertCount(1, $items);
        $this->assertTrue($items[0]['is_reserve']);
        $this->assertSame('Reserve-X', $items[0]['alias']);
    }

    public function test_list_laptops_kind_filter_normal(): void
    {
        $this->addStudent('S210');
        $this->postJson('/api/laptops', ['serial_number' => 'NORM-002', 'stamnummer' => 'S210']);
        $this->createReserve('Reserve-Y');

        $items = collect($this->getJson('/api/laptops?kind=normal')->assertOk()->json());
        $this->assertContains('NORM-002', $items->pluck('serial_number'));
        $this->assertNotContains('Reserve-Y', $items->pluck('alias'));
    }

    public function test_list_laptops_active_filter(): void
    {
        $this->addStudent('S220');
        $this->addStudent('S221');
        $this->link('S220', 'ACT-1');
        $id = $this->link('S221', 'ACT-2')->json('id');
        $this->unlink($id);

        $this->assertSame(['ACT-1'], collect($this->getJson('/api/laptops?active=true')->json())->pluck('serial_number')->all());
        $this->assertSame(['ACT-2'], collect($this->getJson('/api/laptops?active=false')->json())->pluck('serial_number')->all());
    }

    public function test_available_reserves_endpoint(): void
    {
        $this->createReserve('Res-A', 'RES-A');
        $this->createReserve('Res-B', 'RES-B');

        $aliases = collect($this->getJson('/api/laptops/reserves/available')->assertOk()->json())->pluck('alias');
        $this->assertContains('Res-A', $aliases);
        $this->assertContains('Res-B', $aliases);
    }

    public function test_update_laptop_alias(): void
    {
        $id = $this->createReserve('Oud-Alias', 'RES-UP')->json('id');

        $this->putJson("/api/laptops/{$id}", ['alias' => 'Nieuw-Alias'])->assertOk()->assertJson(['alias' => 'Nieuw-Alias']);
    }

    public function test_delete_laptop(): void
    {
        $id = $this->createReserve('Weg', 'RES-DEL')->json('id');

        $this->deleteJson("/api/laptops/{$id}")->assertNoContent();
        $this->deleteJson("/api/laptops/{$id}")->assertStatus(404);
    }

    // ── CSV-export ────────────────────────────────────────────────────────

    public function test_export_laptops_returns_csv(): void
    {
        $this->addStudent('S300', 'Jansen', 'Lotte');
        $this->link('S300', 'EXP-001');

        $resp = $this->get('/api/laptops/export')->assertOk();
        $this->assertStringStartsWith('text/csv', $resp->headers->get('Content-Type'));
        $this->assertStringContainsString('attachment', $resp->headers->get('Content-Disposition'));
        $body = $resp->getContent();
        $this->assertStringContainsString('Serienummer;Type;Leerling', $body);
        $this->assertStringContainsString('EXP-001', $body);
        $this->assertStringContainsString('Lotte Jansen', $body);
    }

    public function test_export_laptops_includes_accessory_status(): void
    {
        $this->addStudent('S310');
        $id = $this->link('S310', 'EXP-MISS')->json('id');
        $this->unlink($id, hoes: false);

        $body = $this->get('/api/laptops/export')->assertOk()->getContent();
        $line = collect(explode("\r\n", $body))->first(fn ($l) => str_contains($l, 'EXP-MISS'));
        $cols = explode(';', $line);
        $this->assertSame('Inactief', $cols[7]);
        $this->assertSame('nee', $cols[8]);
        $this->assertSame('ja', $cols[9]);
    }

    public function test_export_laptops_respects_kind_filter(): void
    {
        $this->addStudent('S320');
        $this->link('S320', 'EXP-NORM');
        $this->createReserve('Reserve-Exp', 'EXP-RES');

        $body = $this->get('/api/laptops/export?kind=reserve')->assertOk()->getContent();
        $this->assertStringContainsString('EXP-RES', $body);
        $this->assertStringNotContainsString('EXP-NORM', $body);
    }

    public function test_export_neutralises_formula_injection(): void
    {
        $this->addStudent('S330', '=HYPERLINK("x")', 'Evil');
        $this->link('S330', 'EXP-INJ');

        $body = $this->get('/api/laptops/export')->getContent();
        $this->assertStringContainsString('Evil =HYPERLINK', $body);
        $this->addStudent('S331', 'Naam', '+cmd');
        $this->link('S331', 'EXP-INJ2');
        $this->assertStringContainsString("'+cmd Naam", $this->get('/api/laptops/export')->getContent());
    }

    // ── Kolomfilters (beheer laptops) ─────────────────────────────────────

    private function manage(array $params): string
    {
        return $this->get('/ui/laptops/manage?'.http_build_query($params))->assertOk()->getContent();
    }

    public function test_manage_column_filter_serial(): void
    {
        $this->addStudent('S400');
        $this->addStudent('S401');
        $this->link('S400', 'COL-AAA');
        $this->link('S401', 'COL-BBB');

        $body = $this->manage(['c_serial' => 'aaa']);
        $this->assertStringContainsString('COL-AAA', $body);
        $this->assertStringNotContainsString('COL-BBB', $body);
    }

    public function test_manage_column_filter_student_and_type(): void
    {
        $this->addStudent('S410', 'Peeters', 'Anna');
        $this->link('S410', 'COL-STU');
        $this->createReserve('Reserve-Col', 'COL-RES');

        $this->assertStringContainsString('COL-STU', $this->manage(['c_student' => 'peeters']));
        $this->assertStringNotContainsString('COL-RES', $this->manage(['c_student' => 'peeters']));
        $this->assertStringContainsString('COL-RES', $this->manage(['c_student' => 'Reserve']));
        $this->assertStringNotContainsString('COL-STU', $this->manage(['c_student' => 'Reserve']));
        $this->assertStringContainsString('COL-STU', $this->manage(['c_student' => 'anna peet']));
    }

    public function test_manage_column_filter_status_and_accessories(): void
    {
        $this->addStudent('S420');
        $this->addStudent('S421');
        $this->link('S420', 'COL-ACT');
        $id = $this->link('S421', 'COL-INACT')->json('id');
        $this->unlink($id, hoes: false);

        $actief = $this->manage(['c_status' => 'actief']);
        $this->assertStringContainsString('COL-ACT', $actief);
        $this->assertStringNotContainsString('COL-INACT', $actief);
        $inactief = $this->manage(['c_status' => 'inactief']);
        $this->assertStringContainsString('COL-INACT', $inactief);
        $this->assertStringNotContainsString('COL-ACT"', $inactief);
        $this->assertStringContainsString('COL-INACT', $this->manage(['c_acc' => 'hoes']));
        $this->assertStringNotContainsString('COL-INACT', $this->manage(['c_acc' => 'oplader']));
        $this->assertStringContainsString('COL-ACT', $this->manage(['c_acc' => 'n.v.t.']));
    }

    public function test_manage_column_filter_date_and_combination(): void
    {
        $this->addStudent('S430');
        $this->link('S430', 'COL-DATE');
        $year = (string) now()->year;
        $month = now()->format('m/Y');
        $day = now()->format('d/m/Y');

        $this->assertStringContainsString('COL-DATE', $this->manage(['c_date' => $year]));
        $this->assertStringContainsString('COL-DATE', $this->manage(['c_date' => $month]));
        $this->assertStringContainsString('COL-DATE', $this->manage(['c_date' => $day]));
        $this->assertStringNotContainsString('COL-DATE', $this->manage(['c_date' => '1999']));
        $this->assertStringNotContainsString('COL-DATE', $this->manage(['c_date' => 'onzin']));
        $this->assertStringContainsString('COL-DATE', $this->manage(['c_date' => $year, 'c_klas' => '3A', 'c_serial' => 'DATE']));
        $this->assertStringNotContainsString('COL-DATE', $this->manage(['c_date' => $year, 'c_klas' => '9Z']));
    }

    public function test_export_laptops_respects_column_filters(): void
    {
        $this->addStudent('S440');
        $this->addStudent('S441');
        $this->link('S440', 'EXPCOL-ONE');
        $this->link('S441', 'EXPCOL-TWO');

        $body = $this->get('/api/laptops/export?c_serial=one')->getContent();
        $this->assertStringContainsString('EXPCOL-ONE', $body);
        $this->assertStringNotContainsString('EXPCOL-TWO', $body);
    }

    // ── Autocomplete / rapport ────────────────────────────────────────────

    public function test_search_and_report(): void
    {
        $this->addStudent('S500', 'Maes', 'Lore');
        $this->link('S500', 'RPT-001');
        $this->createIssue('RPT-001')->assertCreated();

        $this->assertSame([], $this->getJson('/api/laptops/search?q=R')->json());
        $this->getJson('/api/laptops/search?q=maes')->assertOk()->assertJson([['serial_number' => 'RPT-001', 'stamnummer' => 'S500']]);

        $report = $this->getJson('/api/laptops/report?serial=RPT-001')->assertOk()->json();
        $this->assertSame('RPT-001', $report['serial']);
        $this->assertSame('Maes', $report['student']['naam']);
        $this->assertCount(1, $report['history']);
        $this->assertTrue($report['history'][0]['is_active']);
        $this->assertMatchesRegularExpression('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/', $report['history'][0]['linked_at']);
        $this->assertSame('2026-04-30', $report['issues'][0]['reported_date']);

        $this->getJson('/api/laptops/info?serial=RPT-001')->assertExactJson(['laptop_type' => null]);
    }

    public function test_import_laptops_csv(): void
    {
        $this->addStudent('S600');
        $file = UploadedFile::fake()->createWithContent('laptops.csv',
            "serial_number,stamnummer\nIMP-1,S600\nIMP-2,ONBEKEND\n,S600\n");

        $this->post('/api/laptops/import', ['file' => $file], ['Accept' => 'application/json'])->assertOk()
            ->assertJson(['created' => 1, 'updated' => 0])
            ->assertJsonCount(2, 'errors');
    }
}
