<?php

namespace Tests\Feature;

use Tests\TestCase;

class IssueFicheTest extends TestCase
{
    public function test_fiche_renders_all_ticket_data(): void
    {
        $this->addStudent('FICHE1', 'Janssens', 'Mila', '4B');
        $this->link('FICHE1', 'LAPTOP-FICHE1');
        $reserve = $this->createReserve('Reserve-7', 'RES-7')->json();
        $issue = $this->createIssue('LAPTOP-FICHE1', 'Toetsenbord defect',
            ['category' => 'Toetsenbord', 'reserve_laptop_id' => $reserve['id']])->json();

        $html = $this->get("/laptop-issues/{$issue['id']}/fiche")->assertOk()->getContent();

        foreach (['Defect fiche', 'Herstel Fiche', 'Mila', 'Janssens', '4B', 'LAPTOP-FICHE1', 'Toetsenbord',
            'Toetsenbord defect', 'In te leveren reserve toestel', 'RES-7', '30 April 2026'] as $needle) {
            $this->assertStringContainsString($needle, $html);
        }
    }

    public function test_fiche_without_reserve_shows_blank_field(): void
    {
        $this->addStudent('FICHE2');
        $this->link('FICHE2', 'LAPTOP-FICHE2');
        $issue = $this->createIssue('LAPTOP-FICHE2')->json();

        $this->get("/laptop-issues/{$issue['id']}/fiche")->assertOk()->assertSee('In te leveren reserve toestel');
    }

    public function test_fiche_unknown_issue_returns_404(): void
    {
        $this->get('/laptop-issues/999999/fiche')->assertNotFound();
    }
}
