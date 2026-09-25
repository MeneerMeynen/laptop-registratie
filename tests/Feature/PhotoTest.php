<?php

namespace Tests\Feature;

use App\Services\PhotoService;
use App\Support\DetailException;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\File;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class PhotoTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config(['laptops.upload_dir' => storage_path('framework/testing/uploads-'.getmypid())]);
        File::deleteDirectory(PhotoService::uploadDir());
    }

    protected function tearDown(): void
    {
        File::deleteDirectory(PhotoService::uploadDir());
        parent::tearDown();
    }

    public static function badSerials(): array
    {
        return array_map(fn ($s) => [$s], [
            '../../etc/passwd', '../escape', 'with/slash', 'with\\backslash',
            'spaces not allowed', '', str_repeat('a', 101), 'weird;chars', "ABC\n",
        ]);
    }

    #[DataProvider('badSerials')]
    public function test_safe_serial_rejects_bad_inputs(string $serial): void
    {
        $this->expectException(DetailException::class);
        PhotoService::safeSerial($serial);
    }

    public function test_safe_serial_accepts_normal_barcodes(): void
    {
        foreach (['ABC123', 'abc-123', 'abc_123', 'ABC.123', 'a', str_repeat('A', 100)] as $serial) {
            $this->assertSame($serial, PhotoService::safeSerial($serial));
        }
    }

    public function test_safe_extension(): void
    {
        foreach (['.php', '.html', '.svg', '.exe', '', '.', 'jpg'] as $ext) {
            try {
                PhotoService::safeExtension($ext);
                $this->fail("Extensie {$ext} had geweigerd moeten worden");
            } catch (DetailException) {
                $this->addToAssertionCount(1);
            }
        }
        foreach (['.jpg', '.jpeg', '.png', '.webp', '.JPG', '.PNG'] as $ext) {
            $this->assertContains(PhotoService::safeExtension($ext), PhotoService::ALLOWED_EXTENSIONS);
        }
    }

    public function test_save_photo_rejects_bad_input(): void
    {
        $photos = app(PhotoService::class);
        foreach ([['../evil', 'data'], ['ABC123', str_repeat('x', PhotoService::MAX_PHOTO_BYTES + 1)], ['ABC123', '']] as [$serial, $bytes]) {
            try {
                $photos->savePhoto($serial, $bytes, '.jpg');
                $this->fail('Had geweigerd moeten worden');
            } catch (DetailException $e) {
                $this->assertSame(400, $e->status);
            }
        }
    }

    public function test_upload_list_serve_and_delete_photo(): void
    {
        // 1×1 PNG (geen GD-extensie nodig); hoofdletterextensie wordt genormaliseerd.
        $png = base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==');
        $file = UploadedFile::fake()->createWithContent('foto.PNG', $png);
        $photo = $this->post('/api/photos?serial_number=PH-001', ['file' => $file], ['Accept' => '*/*'])
            ->assertCreated()->assertJson(['serial_number' => 'PH-001'])->json();
        $this->assertMatchesRegularExpression('/^[a-f0-9]{32}\.png$/', $photo['filename']);
        $this->assertSame("/uploads/laptops/PH-001/{$photo['filename']}", $photo['url']);

        $list = $this->getJson('/api/photos/PH-001')->assertOk()->json();
        $this->assertCount(1, $list);
        $this->assertMatchesRegularExpression('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/', $list[0]['created_at']);
        $this->getJson('/api/photos/latest/serial')->assertExactJson(['serial_number' => 'PH-001']);

        $this->get($photo['url'])->assertOk()->assertHeader('Content-Type', 'image/png');
        $this->assertStringContainsString('PH-001', $this->get('/ui/photos/gallery?serial=PH-001')->getContent());

        $this->deleteJson("/api/photos/{$photo['id']}")->assertNoContent();
        $this->deleteJson("/api/photos/{$photo['id']}")->assertStatus(404);
        $this->get($photo['url'])->assertNotFound();
    }

    public function test_upload_base64_photo(): void
    {
        $jpeg = base64_encode("\xFF\xD8\xFF\xE0fake-jpeg");
        $this->postJson('/api/photos/base64', ['serial_number' => 'PH-002', 'image_data' => "data:image/jpeg;base64,{$jpeg}"])
            ->assertCreated()->assertJson(['serial_number' => 'PH-002']);
        $this->postJson('/api/photos/base64', ['serial_number' => 'PH-002', 'image_data' => '!!!niet-base64!!!'])
            ->assertStatus(400)->assertJson(['detail' => 'Ongeldige base64 data.']);
        $this->postJson('/api/photos/base64', ['serial_number' => '../x', 'image_data' => $jpeg])->assertStatus(400);
    }

    public function test_upload_rejects_dangerous_extension(): void
    {
        $file = UploadedFile::fake()->createWithContent('shell.php', '<?php echo 1;');
        $this->post('/api/photos?serial_number=PH-003', ['file' => $file], ['Accept' => '*/*'])
            ->assertStatus(400)->assertJson(['detail' => 'Ongeldig bestandstype.']);
    }

    public function test_serving_rejects_traversal(): void
    {
        $this->get('/uploads/laptops/..%2F..%2F.env/0123456789abcdef0123456789abcdef.jpg')->assertNotFound();
        $this->get('/uploads/laptops/ABC/..%2F..%2F.env')->assertNotFound();
    }
}
