<?php

namespace Tests\Feature;

use App\Models\LaptopIssue;
use App\Services\LaptopIssueService;
use Tests\TestCase;

class LaptopIssueTest extends TestCase
{
    private function entries(int $issueId): array
    {
        return array_column(app(LaptopIssueService::class)->getEntriesForIssue($issueId), 'text');
    }

    private function setupLaptop(string $stam, string $serial): void
    {
        $this->addStudent($stam);
        $this->link($stam, $serial)->assertOk();
    }

    // ── Reserve-laptop bij een issue ──────────────────────────────────────

    public function test_create_issue_with_reserve_laptop(): void
    {
        $this->setupLaptop('IS001', 'LAPTOP-IS001');
        $reserve = $this->createReserve('Reserve-Test', 'RES-TEST')->json();

        $issue = $this->createIssue('LAPTOP-IS001', extra: ['reserve_laptop_id' => $reserve['id']])
            ->assertCreated()
            ->assertJson([
                'reserve_laptop_id' => $reserve['id'],
                'reserve_laptop_alias' => 'Reserve-Test',
                'reserve_laptop_serial' => 'RES-TEST',
                'reported_date' => '2026-04-30',
                'status' => 'aangemeld',
                'stamnummer' => 'IS001',
            ])->json();

        $texts = $this->entries($issue['id']);
        $this->assertCount(1, $texts);
        $this->assertStringContainsString('Reserve-Test', $texts[0]);
        $this->assertStringContainsString('uitgeleend', $texts[0]);
        $this->assertStringContainsString('John Doe', $texts[0]);
    }

    public function test_create_issue_with_invalid_reserve_id_returns_422(): void
    {
        $this->setupLaptop('IS010', 'LAPTOP-IS010');

        $this->createIssue('LAPTOP-IS010', 'Test', ['reserve_laptop_id' => 99999])->assertStatus(422);
    }

    public function test_cannot_use_normal_laptop_as_reserve(): void
    {
        $this->setupLaptop('IS020', 'LAPTOP-IS020');
        $this->addStudent('IS021');
        $normal = $this->link('IS021', 'LAPTOP-IS021')->json();

        $this->createIssue('LAPTOP-IS020', 'Test', ['reserve_laptop_id' => $normal['id']])->assertStatus(422);
    }

    public function test_create_issue_validates_input(): void
    {
        $this->createIssue('  ')->assertStatus(422)->assertJson(['detail' => 'Serienummer is verplicht.']);
        $this->createIssue('X', '  ')->assertStatus(422)->assertJson(['detail' => 'Beschrijving is verplicht.']);
        $this->createIssue('X', 'Y', ['reported_date' => '2026-02-30'])->assertStatus(422);
    }

    public function test_close_issue_releases_reserve_and_writes_entry(): void
    {
        $this->setupLaptop('IS030', 'LAPTOP-IS030');
        $reserve = $this->createReserve('Reserve-Close', 'RES-CLOSE')->json();
        $issue = $this->createIssue('LAPTOP-IS030', extra: ['reserve_laptop_id' => $reserve['id']])->json();

        $this->patchJson("/api/laptop-issues/{$issue['id']}", ['status' => 'gesloten', 'solution' => 'Scherm vervangen.'])
            ->assertOk()->assertJson(['reserve_laptop_id' => null, 'status' => 'gesloten', 'solution' => 'Scherm vervangen.']);

        $texts = $this->entries($issue['id']);
        $this->assertNotEmpty(array_filter($texts, fn ($t) => str_contains($t, 'teruggebracht')));
        $this->assertNotEmpty(array_filter($texts, fn ($t) => str_contains($t, 'Reserve-Close')));
    }

    public function test_close_issue_without_reserve_does_not_crash(): void
    {
        $this->setupLaptop('IS040', 'LAPTOP-IS040');
        $issue = $this->createIssue('LAPTOP-IS040')->json();

        $this->patchJson("/api/laptop-issues/{$issue['id']}", ['status' => 'gesloten', 'solution' => 'Opgelost.'])
            ->assertOk()->assertJson(['status' => 'gesloten', 'reserve_laptop_id' => null]);
    }

    public function test_reserve_in_use_visible_in_available_list(): void
    {
        $this->setupLaptop('IS050', 'LAPTOP-IS050');
        $reserve = $this->createReserve('Reserve-InUse', 'RES-INUSE')->json();
        $this->createIssue('LAPTOP-IS050', extra: ['reserve_laptop_id' => $reserve['id']]);

        $match = collect($this->getJson('/api/laptops/reserves/available')->assertOk()->json())->firstWhere('id', $reserve['id']);
        $this->assertNotNull($match['in_use_by_issue_id']);
        $this->assertSame('John Doe', $match['in_use_by_student']);
    }

    public function test_reserve_available_after_issue_closed(): void
    {
        $this->setupLaptop('IS060', 'LAPTOP-IS060');
        $reserve = $this->createReserve('Reserve-Free', 'RES-FREE')->json();
        $issue = $this->createIssue('LAPTOP-IS060', extra: ['reserve_laptop_id' => $reserve['id']])->json();
        $this->patchJson("/api/laptop-issues/{$issue['id']}", ['status' => 'gesloten', 'solution' => 'Fixed.']);

        $match = collect($this->getJson('/api/laptops/reserves/available')->json())->firstWhere('id', $reserve['id']);
        $this->assertNull($match['in_use_by_issue_id']);
    }

    public function test_change_reserve_logs_timeline_entry(): void
    {
        $this->setupLaptop('IS070', 'LAPTOP-IS070');
        $r1 = $this->createReserve('Reserve-First')->json();
        $r2 = $this->createReserve('Reserve-Second')->json();
        $issue = $this->createIssue('LAPTOP-IS070', extra: ['reserve_laptop_id' => $r1['id']])->json();

        $this->patchJson("/api/laptop-issues/{$issue['id']}", ['reserve_laptop_id' => $r2['id']])->assertOk();

        $texts = $this->entries($issue['id']);
        $this->assertStringContainsString('Reserve-First → Reserve-Second', end($texts));
    }

    public function test_remove_reserve_logs_terug_entry(): void
    {
        $this->setupLaptop('IS080', 'LAPTOP-IS080');
        $reserve = $this->createReserve('Reserve-Remove')->json();
        $issue = $this->createIssue('LAPTOP-IS080', extra: ['reserve_laptop_id' => $reserve['id']])->json();

        $this->patchJson("/api/laptop-issues/{$issue['id']}", ['reserve_laptop_id' => null])
            ->assertOk()->assertJson(['reserve_laptop_id' => null]);

        $this->assertNotEmpty(array_filter($this->entries($issue['id']), fn ($t) => str_contains($t, 'teruggebracht')));
    }

    public function test_patch_without_reserve_key_keeps_reserve(): void
    {
        $this->setupLaptop('IS090', 'LAPTOP-IS090');
        $reserve = $this->createReserve('Reserve-Keep')->json();
        $issue = $this->createIssue('LAPTOP-IS090', extra: ['reserve_laptop_id' => $reserve['id']])->json();

        $this->patchJson("/api/laptop-issues/{$issue['id']}", ['status' => 'open'])
            ->assertOk()->assertJson(['reserve_laptop_id' => $reserve['id'], 'status' => 'open']);
    }

    // ── CRUD, lijsten en export ───────────────────────────────────────────

    public function test_list_hides_closed_by_default_and_delete(): void
    {
        $this->setupLaptop('IS100', 'LAPTOP-IS100');
        $open = $this->createIssue('LAPTOP-IS100', 'Open issue')->json();
        $closed = $this->createIssue('LAPTOP-IS100', 'Dicht issue')->json();
        $this->patchJson("/api/laptop-issues/{$closed['id']}", ['status' => 'gesloten']);

        $this->assertSame([$open['id']], array_column($this->getJson('/api/laptop-issues')->json(), 'id'));
        $this->assertCount(2, $this->getJson('/api/laptop-issues?include_closed=true')->json());
        $this->assertCount(1, $this->getJson('/api/laptop-issues?search=doe')->json());

        $this->deleteJson("/api/laptop-issues/{$open['id']}")->assertNoContent();
        $this->deleteJson("/api/laptop-issues/{$open['id']}")->assertStatus(404);
        $this->patchJson('/api/laptop-issues/99999', ['status' => 'open'])->assertStatus(404);
    }

    public function test_export_issues_csv(): void
    {
        $this->setupLaptop('IS110', 'LAPTOP-IS110');
        $this->createIssue('LAPTOP-IS110', 'Scherm; gebarsten', ['category' => 'Scherm']);

        $body = $this->get('/api/laptop-issues/export')->assertOk()->getContent();
        $this->assertStringContainsString('ID;Serienummer;Leerling;Categorie;Beschrijving;Status;Datum gemeld;Oplossing', $body);
        $this->assertStringContainsString(';John Doe;Scherm;"Scherm; gebarsten";aangemeld;2026-04-30;', $body);
    }

    // ── HTMX-partials van de tracker ─────────────────────────────────────

    public function test_sidebar_and_detail_partials(): void
    {
        $this->setupLaptop('IS120', 'LAPTOP-IS120');
        $issue = $this->createIssue('LAPTOP-IS120', 'Toetsenbord <b>stuk</b>', ['category' => 'Toetsenbord'])->json();

        $sidebar = $this->get('/ui/laptop-tracker/sidebar')->assertOk()->getContent();
        $this->assertStringContainsString('LAPTOP-IS120', $sidebar);
        $this->assertStringContainsString('<span id="lt-count-aangemeld" hx-swap-oob="innerHTML">1</span>', $sidebar);

        // Herhaalde statuses-parameter zoals de frontend die stuurt.
        $this->assertStringNotContainsString('LAPTOP-IS120', $this->get('/ui/laptop-tracker/sidebar?statuses=gesloten')->getContent());
        $this->assertStringContainsString('LAPTOP-IS120', $this->get('/ui/laptop-tracker/sidebar?statuses=open&statuses=aangemeld')->getContent());

        $detail = $this->get('/ui/laptop-tracker/detail?serial=LAPTOP-IS120')->assertOk()->getContent();
        $this->assertStringContainsString('John Doe', $detail);
        $this->assertStringContainsString('1 aangemeld', $detail);
        $this->assertStringContainsString('Toetsenbord &lt;b&gt;stuk&lt;/b&gt;', $detail);
        $this->assertStringContainsString('data-date="2026-04-30"', $detail);
        $this->assertStringContainsString("setIssueStatus({$issue['id']}, 'open', 'aangemeld')", $detail);
    }

    public function test_issue_entries_crud_via_htmx(): void
    {
        $this->setupLaptop('IS130', 'LAPTOP-IS130');
        $issue = $this->createIssue('LAPTOP-IS130')->json();

        $html = $this->post("/ui/laptop-issues/{$issue['id']}/entries", ['text' => 'Aangemeld bij partner'])->assertOk()->getContent();
        $this->assertStringContainsString('Aangemeld bij partner', $html);
        $entryId = app(LaptopIssueService::class)->getEntriesForIssue($issue['id'])[0]['id'];

        $this->assertStringContainsString('lt-entry-error', $this->post("/ui/laptop-issues/{$issue['id']}/entries", ['text' => '  '])->getContent());

        $html = $this->patch("/ui/laptop-issues/entries/{$entryId}", ['text' => 'Teruggekomen'])->assertOk()->getContent();
        $this->assertStringContainsString('Teruggekomen', $html);

        $this->delete("/ui/laptop-issues/entries/{$entryId}")->assertOk();
        $this->assertSame([], $this->entries($issue['id']));
        $this->assertStringContainsString('niet gevonden', $this->delete("/ui/laptop-issues/entries/{$entryId}")->getContent());
    }

    public function test_deleting_issue_cascades_entries(): void
    {
        $this->setupLaptop('IS140', 'LAPTOP-IS140');
        $reserve = $this->createReserve('Reserve-Casc')->json();
        $issue = $this->createIssue('LAPTOP-IS140', extra: ['reserve_laptop_id' => $reserve['id']])->json();

        $this->deleteJson("/api/laptop-issues/{$issue['id']}")->assertNoContent();
        $this->assertSame([], $this->entries($issue['id']));
        $this->assertSame(0, LaptopIssue::count());
    }
}
