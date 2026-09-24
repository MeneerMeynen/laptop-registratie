<?php

namespace Tests;

use App\Models\Student;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Foundation\Testing\TestCase as BaseTestCase;
use Illuminate\Testing\TestResponse;

abstract class TestCase extends BaseTestCase
{
    use RefreshDatabase;

    /** Standaard ingelogd, zoals de `client`-fixture van de Python-tests. */
    protected bool $loggedIn = true;

    protected function setUp(): void
    {
        parent::setUp();
        if ($this->loggedIn) {
            $this->withSession(['user' => 'test']);
        }
    }

    protected function addStudent(string $stamnummer, string $naam = 'Doe', string $voornaam = 'John', string $klas = '3A'): Student
    {
        return Student::create(['stamnummer' => $stamnummer, 'naam' => $naam, 'voornaam' => $voornaam, 'klas' => $klas]);
    }

    protected function link(string $stamnummer, string $serial, bool $overwrite = false): TestResponse
    {
        return $this->postJson('/api/laptops/link', [
            'stamnummer' => $stamnummer,
            'serial_number' => $serial,
            'overwrite_existing' => $overwrite,
        ]);
    }

    protected function unlink(int $laptopId, bool $hoes = true, bool $oplader = true): TestResponse
    {
        return $this->postJson("/api/laptops/{$laptopId}/unlink", [
            'hoes_ingeleverd' => $hoes,
            'oplader_ingeleverd' => $oplader,
        ]);
    }

    protected function createReserve(string $alias, ?string $serial = null): TestResponse
    {
        $payload = ['is_reserve' => true, 'alias' => $alias];
        if ($serial) {
            $payload['serial_number'] = $serial;
        }

        return $this->postJson('/api/laptops', $payload);
    }

    protected function createIssue(string $serial, string $description = 'Scherm kapot', array $extra = []): TestResponse
    {
        return $this->postJson('/api/laptop-issues', array_merge([
            'serial_number' => $serial,
            'description' => $description,
            'reported_date' => '2026-04-30',
        ], $extra));
    }
}
