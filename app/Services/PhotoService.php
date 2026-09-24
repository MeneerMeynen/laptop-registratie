<?php

namespace App\Services;

use App\Models\LaptopPhoto;
use App\Support\DetailException;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;

class PhotoService
{
    /** Serienummers komen van barcode-scans — alfanumeriek plus enkele scheidingstekens, max 100 tekens. */
    private const SERIAL_RE = '/^[A-Za-z0-9._-]{1,100}\z/';

    public const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];

    public const MAX_PHOTO_BYTES = 10 * 1024 * 1024; // 10 MiB per foto

    public static function uploadDir(): string
    {
        return rtrim(config('laptops.upload_dir'), '/');
    }

    public static function safeSerial(string $serial): string
    {
        if (! preg_match(self::SERIAL_RE, $serial)) {
            throw new DetailException(400, 'Ongeldig serienummer.');
        }

        return $serial;
    }

    public static function safeExtension(string $extension): string
    {
        $ext = strtolower($extension);
        if (! in_array($ext, self::ALLOWED_EXTENSIONS, true)) {
            throw new DetailException(400, 'Ongeldig bestandstype.');
        }

        return $ext;
    }

    /** Maak de uploadmap voor een (gevalideerd) serienummer aan en geef het pad terug. */
    private static function ensureDir(string $serial): string
    {
        $base = self::uploadDir();
        File::ensureDirectoryExists($base);
        $target = $base.DIRECTORY_SEPARATOR.$serial;
        // Dubbele zekerheid: ook met een gevalideerd serienummer controleren we
        // dat het pad binnen de uploadmap blijft.
        if (in_array($serial, ['.', '..'], true) || dirname($target) !== $base) {
            throw new DetailException(400, 'Ongeldig serienummer.');
        }
        File::ensureDirectoryExists($target);

        return $target;
    }

    public static function url(LaptopPhoto $photo): string
    {
        return "/uploads/laptops/{$photo->serial_number}/{$photo->filename}";
    }

    public function savePhoto(string $serial, string $bytes, string $extension = '.jpg'): LaptopPhoto
    {
        $serial = self::safeSerial($serial);
        $extension = self::safeExtension($extension);
        if (strlen($bytes) > self::MAX_PHOTO_BYTES) {
            throw new DetailException(400, 'Foto is te groot (max 10 MB).');
        }
        if ($bytes === '') {
            throw new DetailException(400, 'Lege foto.');
        }

        $dir = self::ensureDir($serial);
        $filename = Str::replace('-', '', (string) Str::uuid()).$extension;
        File::put($dir.DIRECTORY_SEPARATOR.$filename, $bytes);

        return LaptopPhoto::create(['serial_number' => $serial, 'filename' => $filename])->refresh();
    }

    /** Alle foto's van een serienummer, nieuwste eerst. */
    public function listPhotos(string $serial): array
    {
        return LaptopPhoto::where('serial_number', $serial)
            ->orderByDesc('created_at')
            ->orderByDesc('id')
            ->get()
            ->map(fn (LaptopPhoto $p) => [
                'id' => $p->id,
                'serial_number' => $p->serial_number,
                'filename' => $p->filename,
                'url' => self::url($p),
                'created_at' => $p->created_at?->format('Y-m-d\TH:i:s'),
            ])
            ->all();
    }

    public function latestSerialWithPhotos(): ?string
    {
        return LaptopPhoto::orderByDesc('created_at')->orderByDesc('id')->value('serial_number');
    }

    public function deletePhoto(int $photoId): bool
    {
        $photo = LaptopPhoto::find($photoId);
        if ($photo === null) {
            return false;
        }
        $path = self::uploadDir().DIRECTORY_SEPARATOR.$photo->serial_number.DIRECTORY_SEPARATOR.$photo->filename;
        if (is_file($path)) {
            unlink($path);
        }
        $photo->delete();

        return true;
    }

    /** Absoluut pad van een foto voor weergave, of null als het pad ongeldig is of niet bestaat. */
    public static function resolvePath(string $serial, string $filename): ?string
    {
        if (! preg_match(self::SERIAL_RE, $serial) || ! preg_match('/^[a-f0-9]{32}\.(jpg|jpeg|png|webp)\z/', $filename)) {
            return null;
        }
        $path = self::uploadDir().DIRECTORY_SEPARATOR.$serial.DIRECTORY_SEPARATOR.$filename;

        return is_file($path) ? $path : null;
    }
}
