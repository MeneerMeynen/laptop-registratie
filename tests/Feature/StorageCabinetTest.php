<?php

namespace Tests\Feature;

use App\Models\Laptop;
use App\Models\StorageCabinet;
use App\Models\Student;
use App\Services\LaptopService;
use App\Services\StorageCabinetService;
use App\Support\DetailException;
use Tests\TestCase;

class StorageCabinetTest extends TestCase
{
    private function cabinets(): StorageCabinetService
    {
        return app(StorageCabinetService::class);
    }

    private function assertDetail(int $status, callable $fn): void
    {
        try {
            $fn();
            $this->fail("Verwachtte DetailException {$status}");
        } catch (DetailException $e) {
            $this->assertSame($status, $e->status);
        }
    }

    // ── Service ───────────────────────────────────────────────────────────

    public function test_create_cabinet_minimal_and_full(): void
    {
        $cab = $this->cabinets()->createCabinet('Kast B201');
        $this->assertSame('Kast B201', $cab->name);
        $this->assertNull($cab->location);
        $this->assertNull($cab->capacity);
        $this->assertSame('kast', $cab->kind);

        $full = $this->cabinets()->createCabinet('Kast 1', location: 'A101', description: 'Voor 2e jaar', capacity: 8);
        $this->assertSame('A101', $full->location);
        $this->assertSame('Voor 2e jaar', $full->description);
        $this->assertSame(8, $full->capacity);
    }

    public function test_create_cabinet_validation(): void
    {
        $this->assertDetail(422, fn () => $this->cabinets()->createCabinet('   '));
        $this->assertDetail(422, fn () => $this->cabinets()->createCabinet('Bad', 'garage'));
        $this->assertDetail(422, fn () => $this->cabinets()->createCabinet('Neg', capacity: -1));
        $this->cabinets()->createCabinet('Kast 1');
        $this->assertDetail(409, fn () => $this->cabinets()->createCabinet('Kast 1'));
    }

    public function test_update_cabinet(): void
    {
        $cab = $this->cabinets()->createCabinet('Kast 1', location: 'A101');
        $updated = $this->cabinets()->updateCabinet($cab->id, ['location' => 'B202', 'capacity' => 12]);
        $this->assertSame('B202', $updated->location);
        $this->assertSame(12, $updated->capacity);
        $this->assertSame('Kast 1', $updated->name);

        $this->assertDetail(404, fn () => $this->cabinets()->updateCabinet(9999, ['name' => 'x']));
    }

    public function test_list_cabinets_with_laptop_count_and_kind(): void
    {
        $a = $this->cabinets()->createCabinet('Kast A', capacity: 4);
        $this->cabinets()->createCabinet('Kast B');
        $this->cabinets()->createCabinet('Magazijn C', 'magazijn');
        Laptop::create(['serial_number' => 'SN-CAB-1', 'storage_cabinet_id' => $a->id]);

        $byName = collect($this->cabinets()->listCabinets())->keyBy('name');
        $this->assertSame(1, $byName['Kast A']['laptop_count']);
        $this->assertSame(0, $byName['Kast B']['laptop_count']);
        $this->assertSame(['Kast A', 'Kast B'], array_column($this->cabinets()->listCabinets(kind: 'kast'), 'name'));
        $this->assertSame(['Magazijn C'], array_column($this->cabinets()->listCabinets(kind: 'magazijn'), 'name'));
    }

    public function test_delete_cabinets(): void
    {
        $inUse = $this->cabinets()->createCabinet('Kast X');
        Laptop::create(['serial_number' => 'SN-CAB-X', 'storage_cabinet_id' => $inUse->id]);
        $this->assertDetail(409, fn () => $this->cabinets()->deleteCabinets([$inUse->id]));

        $empty = $this->cabinets()->createCabinet('Empty');
        $this->assertSame(1, $this->cabinets()->deleteCabinets([$empty->id]));
        $this->assertSame(1, StorageCabinet::count());
    }

    // ── Integratie met laptops ────────────────────────────────────────────

    public function test_create_cabinet_laptop(): void
    {
        $cab = $this->cabinets()->createCabinet('Kast Y');
        $laptops = app(LaptopService::class);

        $lap = $laptops->createLaptop('SN-CAB-Y1', storageCabinetId: $cab->id);
        $this->assertSame($cab->id, $lap->storage_cabinet_id);
        $this->assertNull($lap->stamnummer);
        $this->assertFalse($lap->is_reserve);

        $this->assertDetail(422, fn () => $laptops->createLaptop(storageCabinetId: $cab->id));
        $this->assertDetail(422, fn () => $laptops->createLaptop('SN-XYZ', storageCabinetId: 999));
    }

    public function test_link_refuses_kast_laptop_but_accepts_magazijn_laptop(): void
    {
        $kast = $this->cabinets()->createCabinet('Kast Q');
        $mag = $this->cabinets()->createCabinet('Magazijn Q', 'magazijn');
        Laptop::create(['serial_number' => 'SN-KQ1', 'storage_cabinet_id' => $kast->id]);
        Laptop::create(['serial_number' => 'SN-MQ1', 'storage_cabinet_id' => $mag->id]);
        Student::create(['stamnummer' => 'S001', 'naam' => 'Test', 'voornaam' => 'Leerling']);
        $laptops = app(LaptopService::class);

        $this->assertDetail(409, fn () => $laptops->linkLaptopToStudent('S001', 'SN-KQ1'));

        $laptop = $laptops->linkLaptopToStudent('S001', 'SN-MQ1');
        $this->assertSame('S001', $laptop->stamnummer);
        $this->assertNull($laptop->storage_cabinet_id);
        $this->assertNotNull($laptop->linked_at);
        $active = Laptop::where('serial_number', 'SN-MQ1')->whereNull('unlinked_at')->get();
        $this->assertCount(1, $active);
        $this->assertSame($laptop->id, $active[0]->id);
    }

    public function test_get_all_laptops_kind_magazijn_vs_cabinet(): void
    {
        $kast = $this->cabinets()->createCabinet('Kast F');
        $mag = $this->cabinets()->createCabinet('Magazijn F', 'magazijn');
        Laptop::create(['serial_number' => 'SN-K', 'storage_cabinet_id' => $kast->id]);
        Laptop::create(['serial_number' => 'SN-M', 'storage_cabinet_id' => $mag->id]);
        $laptops = app(LaptopService::class);

        $this->assertSame(['SN-K'], array_column($laptops->getAllLaptops(kind: 'cabinet'), 'serial_number'));
        $this->assertSame(['SN-M'], array_column($laptops->getAllLaptops(kind: 'magazijn'), 'serial_number'));
    }

    // ── HTTP ──────────────────────────────────────────────────────────────

    public function test_cabinet_routes(): void
    {
        $this->postJson('/api/storage-cabinets', ['name' => 'Kast 1', 'location' => 'A101', 'capacity' => 8])
            ->assertOk()->assertJson(['name' => 'Kast 1', 'location' => 'A101', 'capacity' => 8, 'laptop_count' => 0, 'kind' => 'kast']);
        $this->postJson('/api/storage-cabinets', ['name' => 'Kast 1'])->assertStatus(409);
        $this->postJson('/api/storage-cabinets', ['name' => 'M1', 'kind' => 'magazijn'])->assertOk()->assertJson(['kind' => 'magazijn']);

        $this->assertSame(['Kast 1'], array_column($this->getJson('/api/storage-cabinets?kind=kast')->json(), 'name'));
        $this->assertSame(['M1'], array_column($this->getJson('/api/storage-cabinets?kind=magazijn')->json(), 'name'));

        $id = $this->postJson('/api/storage-cabinets', ['name' => 'Edit', 'location' => 'Old'])->json('id');
        $this->putJson("/api/storage-cabinets/{$id}", ['location' => 'New', 'capacity' => 10])
            ->assertOk()->assertJson(['location' => 'New', 'capacity' => 10]);

        $this->deleteJson('/api/storage-cabinets', ['ids' => [$id]])->assertOk()->assertJson(['deleted' => 1]);
    }

    public function test_delete_cabinet_in_use_returns_409(): void
    {
        $id = $this->postJson('/api/storage-cabinets', ['name' => 'InUse'])->json('id');
        Laptop::create(['serial_number' => 'SN-USE', 'storage_cabinet_id' => $id]);

        $this->deleteJson('/api/storage-cabinets', ['ids' => [$id]])->assertStatus(409);
    }

    public function test_cabinet_laptop_via_api_and_link_rejection(): void
    {
        $cabId = $this->postJson('/api/storage-cabinets', ['name' => 'Block-Kast'])->json('id');
        $this->postJson('/api/laptops', ['serial_number' => 'SN-BLOCK', 'storage_cabinet_id' => $cabId])
            ->assertOk()->assertJson(['storage_cabinet_id' => $cabId, 'stamnummer' => null]);
        $this->addStudent('L100');

        $detail = $this->link('L100', 'SN-BLOCK')->assertStatus(409)->json('detail');
        $this->assertStringContainsString('uitleenkast', strtolower($detail));
    }

    public function test_link_endpoint_accepts_magazijn_laptop(): void
    {
        $magId = $this->postJson('/api/storage-cabinets', ['name' => 'Link Magazijn', 'kind' => 'magazijn'])->json('id');
        $this->postJson('/api/laptops', ['serial_number' => 'SN-LINK-M', 'storage_cabinet_id' => $magId]);
        $this->addStudent('L200');

        $this->link('L200', 'SN-LINK-M')->assertOk()->assertJson(['stamnummer' => 'L200', 'storage_cabinet_id' => null]);
    }

    public function test_ui_partials(): void
    {
        $magId = $this->postJson('/api/storage-cabinets', ['name' => 'UI-Magazijn', 'kind' => 'magazijn'])->json('id');
        $kastId = $this->postJson('/api/storage-cabinets', ['name' => 'UI-Kast', 'location' => 'Z9'])->json('id');
        $this->postJson('/api/laptops', ['serial_number' => 'MAG-FX', 'storage_cabinet_id' => $magId]);
        $this->postJson('/api/laptops', ['serial_number' => 'KAST-FX', 'storage_cabinet_id' => $kastId]);

        $html = $this->get('/ui/storage-cabinets/manage')->assertOk()->getContent();
        $this->assertStringContainsString('UI-Kast', $html);
        $this->assertStringContainsString('Z9', $html);
        $this->assertStringContainsString('UI-Magazijn', $this->get('/ui/storage-cabinets/manage?kind=magazijn')->getContent());

        $mag = $this->get('/ui/laptops/manage?kind=magazijn')->getContent();
        $this->assertStringContainsString('MAG-FX', $mag);
        $this->assertStringNotContainsString('KAST-FX', $mag);
        $this->assertStringContainsString('>Magazijn<', $mag);

        $kast = $this->get('/ui/laptops/manage?kind=cabinet')->getContent();
        $this->assertStringContainsString('KAST-FX', $kast);
        $this->assertStringContainsString('UI-Kast', $kast);
    }
}
