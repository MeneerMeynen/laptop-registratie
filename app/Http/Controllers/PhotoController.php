<?php

namespace App\Http\Controllers;

use App\Models\LaptopPhoto;
use App\Services\PhotoService;
use App\Support\DetailException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

class PhotoController extends Controller
{
    public function __construct(private readonly PhotoService $photos) {}

    /** Serienummer van de meest recent geüploade foto. */
    public function latestSerial(): JsonResponse
    {
        return response()->json(['serial_number' => $this->photos->latestSerialWithPhotos()]);
    }

    public function index(string $serialNumber): JsonResponse
    {
        return response()->json($this->photos->listPhotos($serialNumber));
    }

    /** Fotobestand uploaden (multipart). */
    public function store(Request $request): JsonResponse
    {
        if (! $request->has('serial_number')) {
            throw new DetailException(422, "Queryparameter 'serial_number' is verplicht.");
        }
        $serial = trim((string) $request->query('serial_number'));
        if ($serial === '') {
            throw new DetailException(400, 'Serienummer is verplicht.');
        }
        $file = $request->file('file');
        if (! $file || ! $file->isValid()) {
            throw new DetailException(400, 'Upload mislukt: bestand ontbreekt of is te groot voor de server.');
        }

        $ext = '.jpg';
        $parts = explode('.', $file->getClientOriginalName());
        if (count($parts) > 1) {
            $ext = '.'.strtolower(end($parts));
        }

        return response()->json($this->payload($this->photos->savePhoto($serial, $file->get(), $ext)), 201);
    }

    /** Base64-foto uploaden (webcam / iOS). */
    public function storeBase64(Request $request): JsonResponse
    {
        $data = $this->body($request);
        $serial = trim($this->requireString($data, 'serial_number'));
        $imageData = $this->requireString($data, 'image_data');
        if ($serial === '') {
            throw new DetailException(400, 'Serienummer is verplicht.');
        }

        // Data-URL-prefix verwijderen indien aanwezig (bv. "data:image/jpeg;base64,").
        if (str_contains($imageData, ',')) {
            $imageData = explode(',', $imageData, 2)[1];
        }
        $bytes = base64_decode($imageData, true);
        if ($bytes === false) {
            throw new DetailException(400, 'Ongeldige base64 data.');
        }

        return response()->json($this->payload($this->photos->savePhoto($serial, $bytes, '.jpg')), 201);
    }

    public function destroy(int $photoId): Response
    {
        if (! $this->photos->deletePhoto($photoId)) {
            throw new DetailException(404, 'Foto niet gevonden.');
        }

        return response()->noContent();
    }

    /** Foto serveren (achter de login, net als in de Python-versie). */
    public function show(string $serial, string $filename): BinaryFileResponse
    {
        $path = PhotoService::resolvePath($serial, $filename);
        if ($path === null) {
            abort(404);
        }

        return response()->file($path, ['Cache-Control' => 'private, max-age=86400']);
    }

    private function payload(LaptopPhoto $photo): array
    {
        return [
            'id' => $photo->id,
            'serial_number' => $photo->serial_number,
            'filename' => $photo->filename,
            'url' => PhotoService::url($photo),
        ];
    }
}
