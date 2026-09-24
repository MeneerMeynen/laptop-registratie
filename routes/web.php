<?php

use App\Http\Controllers\AuthController;
use App\Http\Controllers\LaptopController;
use App\Http\Controllers\LaptopIssueController;
use App\Http\Controllers\PhotoController;
use App\Http\Controllers\StorageCabinetController;
use App\Http\Controllers\StudentController;
use App\Http\Controllers\UiController;
use App\Http\Middleware\RequireLogin;
use Illuminate\Support\Facades\Route;

// ── Publiek ───────────────────────────────────────────────────────────────
Route::get('/login', [AuthController::class, 'showLogin']);
Route::post('/login', [AuthController::class, 'login']);
Route::post('/logout', [AuthController::class, 'logout']);

// ── Achter de login ───────────────────────────────────────────────────────
Route::middleware(RequireLogin::class)->group(function () {
    // Volledige pagina's
    Route::get('/', [UiController::class, 'index']);
    Route::get('/barcodes', [UiController::class, 'barcodes']);
    Route::get('/photos', [UiController::class, 'photos']);
    Route::get('/laptop-issues/{issueId}/fiche', [LaptopIssueController::class, 'fiche'])->whereNumber('issueId');
    Route::get('/uploads/laptops/{serial}/{filename}', [PhotoController::class, 'show']);

    // HTMX-partials
    Route::get('/ui/students/list', [UiController::class, 'studentsList']);
    Route::get('/ui/students/manage', [UiController::class, 'studentsManage']);
    Route::post('/ui/students/import', [UiController::class, 'importStudents']);
    Route::get('/ui/photos/gallery', [UiController::class, 'photoGallery']);
    Route::get('/ui/laptops/manage', [UiController::class, 'laptopsManage']);
    Route::post('/ui/laptops/import', [UiController::class, 'importLaptops']);
    Route::get('/ui/storage-cabinets/manage', [UiController::class, 'cabinetsManage']);
    Route::get('/ui/laptop-tracker/sidebar', [LaptopIssueController::class, 'sidebar']);
    Route::get('/ui/laptop-tracker/detail', [LaptopIssueController::class, 'detail']);
    Route::post('/ui/laptop-issues/{issueId}/entries', [LaptopIssueController::class, 'storeEntry'])->whereNumber('issueId');
    Route::patch('/ui/laptop-issues/entries/{entryId}', [LaptopIssueController::class, 'updateEntry'])->whereNumber('entryId');
    Route::delete('/ui/laptop-issues/entries/{entryId}', [LaptopIssueController::class, 'destroyEntry'])->whereNumber('entryId');

    // JSON-API: leerlingen
    Route::get('/api/students', [StudentController::class, 'index']);
    Route::post('/api/students', [StudentController::class, 'store']);
    Route::post('/api/students/import', [StudentController::class, 'import']);
    Route::delete('/api/students', [StudentController::class, 'destroy']);
    Route::put('/api/students/{stamnummer}', [StudentController::class, 'update']);

    // JSON-API: laptops (vaste paden vóór /{laptopId})
    Route::get('/api/laptops', [LaptopController::class, 'index']);
    Route::post('/api/laptops', [LaptopController::class, 'store']);
    Route::get('/api/laptops/export', [LaptopController::class, 'export']);
    Route::get('/api/laptops/reserves/available', [LaptopController::class, 'reservesAvailable']);
    Route::get('/api/laptops/search', [LaptopController::class, 'search']);
    Route::get('/api/laptops/info', [LaptopController::class, 'info']);
    Route::get('/api/laptops/report', [LaptopController::class, 'report']);
    Route::post('/api/laptops/bulk', [LaptopController::class, 'bulk']);
    Route::post('/api/laptops/import', [LaptopController::class, 'import']);
    Route::post('/api/laptops/link', [LaptopController::class, 'link']);
    Route::put('/api/laptops/{laptopId}', [LaptopController::class, 'update'])->whereNumber('laptopId');
    Route::delete('/api/laptops/{laptopId}', [LaptopController::class, 'destroy'])->whereNumber('laptopId');
    Route::post('/api/laptops/{laptopId}/unlink', [LaptopController::class, 'unlink'])->whereNumber('laptopId');

    // JSON-API: issues
    Route::get('/api/laptop-issues', [LaptopIssueController::class, 'index']);
    Route::post('/api/laptop-issues', [LaptopIssueController::class, 'store']);
    Route::get('/api/laptop-issues/export', [LaptopIssueController::class, 'export']);
    Route::patch('/api/laptop-issues/{issueId}', [LaptopIssueController::class, 'update'])->whereNumber('issueId');
    Route::delete('/api/laptop-issues/{issueId}', [LaptopIssueController::class, 'destroy'])->whereNumber('issueId');

    // JSON-API: foto's
    Route::get('/api/photos/latest/serial', [PhotoController::class, 'latestSerial']);
    Route::get('/api/photos/{serialNumber}', [PhotoController::class, 'index']);
    Route::post('/api/photos', [PhotoController::class, 'store']);
    Route::post('/api/photos/base64', [PhotoController::class, 'storeBase64']);
    Route::delete('/api/photos/{photoId}', [PhotoController::class, 'destroy'])->whereNumber('photoId');

    // JSON-API: uitleenkasten en magazijnen
    Route::get('/api/storage-cabinets', [StorageCabinetController::class, 'index']);
    Route::post('/api/storage-cabinets', [StorageCabinetController::class, 'store']);
    Route::put('/api/storage-cabinets/{cabinetId}', [StorageCabinetController::class, 'update'])->whereNumber('cabinetId');
    Route::delete('/api/storage-cabinets', [StorageCabinetController::class, 'destroy']);
});
