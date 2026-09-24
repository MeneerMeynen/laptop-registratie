<?php

namespace Tests\Feature;

use App\Models\Laptop;
use App\Services\LaptopService;
use App\Services\StorageCabinetService;
use App\Support\DetailException;
use Tests\TestCase;

class LaptopBulkTest extends TestCase
{
    private function bulk(array $serials, bool $reserve = false, ?int $cabinet = null): array
    {
        return app(LaptopService::class)->bulkCreateLaptops($serials, $reserve, $cabinet);
    }

    public function test_bulk_reserve_generates_aliases(): void
    {
        $this->assertSame(['created' => 3, 'skipped' => 0, 'errors' => []], $this->bulk(['SN-R1', 'SN-R2', 'SN-R3'], true));

        $reserves = Laptop::where('is_reserve', true)->get();
        $this->assertSame(['Reserve-1', 'Reserve-2', 'Reserve-3'], $reserves->pluck('alias')->sort()->values()->all());
        $this->assertTrue($reserves->every(fn ($l) => $l->linked_at === null));
    }

    public function test_bulk_reserve_alias_continues_numbering(): void
    {
        Laptop::create(['serial_number' => 'SN-OLD', 'is_reserve' => true, 'alias' => 'Reserve-2']);

        $this->bulk(['SN-NEW1', 'SN-NEW2'], true);

        $this->assertSame(['Reserve-2', 'Reserve-3', 'Reserve-4'],
            Laptop::where('is_reserve', true)->pluck('alias')->sort()->values()->all());
    }

    public function test_bulk_reserve_skips_existing_serial(): void
    {
        Laptop::create(['serial_number' => 'SN-DUP', 'is_reserve' => true, 'alias' => 'Reserve-1']);

        $result = $this->bulk(['SN-DUP', 'SN-FRESH'], true);
        $this->assertSame(1, $result['created']);
        $this->assertSame(1, $result['skipped']);
    }

    public function test_bulk_cabinet_adds_laptops(): void
    {
        $cab = app(StorageCabinetService::class)->createCabinet('Bulk-Kast');

        $this->assertSame(['created' => 2, 'skipped' => 0, 'errors' => []], $this->bulk(['SN-C1', 'SN-C2'], cabinet: $cab->id));
        $laptops = Laptop::where('storage_cabinet_id', $cab->id)->get();
        $this->assertEqualsCanonicalizing(['SN-C1', 'SN-C2'], $laptops->pluck('serial_number')->all());
        $this->assertTrue($laptops->every(fn ($l) => $l->is_reserve === false && $l->linked_at !== null));
    }

    public function test_bulk_cabinet_skips_active_serial(): void
    {
        $cab = app(StorageCabinetService::class)->createCabinet('Kast-Skip');
        Laptop::create(['serial_number' => 'SN-LINKED', 'storage_cabinet_id' => $cab->id]);

        $result = $this->bulk(['SN-LINKED', 'SN-OK'], cabinet: $cab->id);
        $this->assertSame(1, $result['created']);
        $this->assertSame(1, $result['skipped']);
    }

    public function test_bulk_cabinet_unknown_cabinet_raises(): void
    {
        $this->expectException(DetailException::class);
        $this->bulk(['SN-X'], cabinet: 9999);
    }

    public function test_bulk_dedupes_input(): void
    {
        $result = $this->bulk(['SN-A', 'SN-A', ' SN-A ', 'SN-B'], true);
        $this->assertSame(2, $result['created']);
        $this->assertSame(2, $result['skipped']);
    }

    public function test_bulk_invalid_serial_collected_as_error(): void
    {
        $result = $this->bulk(['SN-OK', 'bad serial!', ''], true);
        $this->assertSame(1, $result['created']);
        $this->assertCount(1, $result['errors']);
        $this->assertStringContainsString('bad serial!', $result['errors'][0]);
    }

    public function test_bulk_requires_a_target(): void
    {
        $this->expectException(DetailException::class);
        $this->bulk(['SN-A']);
    }

    public function test_bulk_route_reserve(): void
    {
        $this->postJson('/api/laptops/bulk', ['serials' => ['SN-RT1', 'SN-RT2'], 'is_reserve' => true])
            ->assertOk()->assertExactJson(['created' => 2, 'skipped' => 0, 'errors' => []]);
    }

    public function test_bulk_route_cabinet(): void
    {
        $cabId = $this->postJson('/api/storage-cabinets', ['name' => 'RT-Kast'])->json('id');

        $this->postJson('/api/laptops/bulk', ['serials' => ['SN-RTC1'], 'storage_cabinet_id' => $cabId])
            ->assertOk()->assertJson(['created' => 1]);
    }

    public function test_bulk_route_unknown_cabinet_returns_422(): void
    {
        $this->postJson('/api/laptops/bulk', ['serials' => ['SN-Z'], 'storage_cabinet_id' => 9999])->assertStatus(422);
    }
}
