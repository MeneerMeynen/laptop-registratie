<?php

namespace App\Http\Controllers;

use App\Services\LaptopIssueService;
use App\Services\LaptopService;
use App\Services\PhotoService;
use App\Support\CsvWriter;
use App\Support\DetailException;
use App\Support\Fmt;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\View\View;

class LaptopIssueController extends Controller
{
    public function __construct(
        private readonly LaptopIssueService $issues,
        private readonly LaptopService $laptops,
        private readonly PhotoService $photos,
    ) {}

    // ── JSON-API ─────────────────────────────────────────────────────────────

    public function index(Request $request): JsonResponse
    {
        $issues = $this->issues->listIssues(
            search: (string) $request->query('search', ''),
            includeClosed: Fmt::bool($request->query('include_closed')),
        );

        return response()->json(array_map([LaptopIssueService::class, 'toJson'], $issues));
    }

    /** Alle issues als CSV-download. */
    public function export(Request $request): \Symfony\Component\HttpFoundation\Response
    {
        $issues = $this->issues->listIssues(includeClosed: Fmt::bool($request->query('include_closed'), true));

        $csv = new CsvWriter(';');
        $csv->row(['ID', 'Serienummer', 'Leerling', 'Categorie', 'Beschrijving', 'Status', 'Datum gemeld', 'Oplossing']);
        foreach ($issues as $issue) {
            $leerling = trim(($issue['voornaam'] ?? '').' '.($issue['naam'] ?? ''));
            $csv->row([
                $issue['id'],
                $issue['serial_number'],
                Fmt::csvSafe($leerling),
                $issue['category'] ?? '',
                Fmt::csvSafe($issue['description']),
                $issue['status'],
                Fmt::date($issue['reported_date']),
                Fmt::csvSafe($issue['solution']),
            ]);
        }

        return $csv->download('laptop-defecten.csv');
    }

    public function store(Request $request): JsonResponse
    {
        $data = $this->body($request);
        $serial = $this->requireString($data, 'serial_number');
        $description = $this->requireString($data, 'description');
        $date = $this->requireDate($data, 'reported_date');
        $category = $this->optString($data, 'category');
        $reserveId = $this->optInt($data, 'reserve_laptop_id');

        if (trim($serial) === '') {
            throw new DetailException(422, 'Serienummer is verplicht.');
        }
        if (trim($description) === '') {
            throw new DetailException(422, 'Beschrijving is verplicht.');
        }

        $issue = $this->issues->createIssue($serial, $description, $date, $category, $reserveId);

        return response()->json($this->issues->findForResponse($issue->id), 201);
    }

    public function update(Request $request, int $issueId): JsonResponse
    {
        $data = $this->body($request);
        $update = [];
        foreach (['description', 'status', 'solution', 'category'] as $key) {
            if (array_key_exists($key, $data)) {
                $update[$key] = $this->optString($data, $key);
            }
        }
        if (array_key_exists('reported_date', $data)) {
            $update['reported_date'] = $data['reported_date'] === null ? null : $this->requireDate($data, 'reported_date');
        }
        if (array_key_exists('reserve_laptop_id', $data)) {
            $update['reserve_laptop_id'] = $this->optInt($data, 'reserve_laptop_id');
        }
        if (array_key_exists('status', $update) && $update['status'] !== null
            && ! in_array($update['status'], LaptopIssueService::VALID_STATUSES, true)) {
            throw new DetailException(422, 'Ongeldige status.');
        }
        // Verplichte kolommen kunnen niet leeggemaakt worden.
        foreach (['description', 'status', 'reported_date'] as $key) {
            if (array_key_exists($key, $update) && $update[$key] === null) {
                unset($update[$key]);
            }
        }

        $issue = $this->issues->updateIssue($issueId, $update);
        if ($issue === null) {
            throw new DetailException(404, 'Probleem niet gevonden.');
        }

        return response()->json($this->issues->findForResponse($issue->id));
    }

    public function destroy(int $issueId): Response
    {
        if (! $this->issues->deleteIssue($issueId)) {
            throw new DetailException(404, 'Probleem niet gevonden.');
        }

        return response()->noContent();
    }

    // ── HTMX-partials ───────────────────────────────────────────────────────

    public function sidebar(Request $request): View
    {
        // FastAPI leest herhaalde parameters (?statuses=a&statuses=b) als lijst;
        // PHP houdt alleen de laatste over, dus de ruwe querystring zelf parsen.
        $statuses = self::repeatedQueryParam($request, 'statuses');

        return view('partials.laptop_tracker_sidebar', [
            'laptops' => $this->issues->listLaptopsWithIssues(
                (string) $request->query('search', ''),
                $statuses ?: null,
            ),
            'stats' => $this->issues->getGlobalStats(),
        ]);
    }

    public function detail(Request $request): View
    {
        $serial = (string) $request->query('serial', '');
        $issues = $this->issues->getIssuesForSerial($serial);
        $count = fn (string $status) => count(array_filter($issues, fn ($i) => $i['status'] === $status));

        return view('partials.laptop_tracker_detail', [
            'serial' => $serial,
            'student' => $this->issues->getStudentForSerial($serial),
            'laptop_type' => $this->issues->getLaptopType($serial),
            'issues' => $issues,
            'history' => $this->laptops->getAssignmentHistory($serial),
            'open_count' => $count('open'),
            'gesloten_count' => $count('gesloten'),
            'aangemeld_count' => $count('aangemeld'),
            'categories' => LaptopIssueService::VALID_CATEGORIES,
            'photo_count' => count($this->photos->listPhotos($serial)),
        ]);
    }

    /** A4-afdrukfiche (defect- + herstelfiche) voor één ticket. */
    public function fiche(int $issueId): View
    {
        $rows = $this->issues->listIssues(includeClosed: true, issueId: $issueId);
        if (! $rows) {
            abort(404, 'Ticket niet gevonden.');
        }
        $issue = $rows[0];

        return view('issue_fiche', [
            'issue' => $issue,
            'student' => $this->issues->getStudentForSerial($issue['serial_number']),
        ]);
    }

    public function storeEntry(Request $request, int $issueId): View|Response
    {
        $text = (string) $request->input('text', '');
        if (trim($text) === '') {
            return response('<p class="lt-entry-error">Opvolgingstekst mag niet leeg zijn.</p>');
        }
        $this->issues->addIssueEntry($issueId, $text);

        return view('partials.laptop_issue_entries', ['entries' => $this->issues->getEntriesForIssue($issueId)]);
    }

    public function updateEntry(Request $request, int $entryId): View|Response
    {
        $text = (string) $request->input('text', '');
        if (trim($text) === '') {
            return response('<p class="lt-entry-error">Tekst mag niet leeg zijn.</p>');
        }
        $entry = $this->issues->updateEntry($entryId, $text);
        if ($entry === null) {
            return response('<p class="lt-entry-error">Opvolging niet gevonden.</p>');
        }

        return view('partials.laptop_issue_entries', ['entries' => $this->issues->getEntriesForIssue($entry->issue_id)]);
    }

    public function destroyEntry(int $entryId): View|Response
    {
        $issueId = $this->issues->deleteEntry($entryId);
        if ($issueId === null) {
            return response('<p class="lt-entry-error">Opvolging niet gevonden.</p>');
        }

        return view('partials.laptop_issue_entries', ['entries' => $this->issues->getEntriesForIssue($issueId)]);
    }

    /** Alle waarden van een herhaalde queryparameter (?key=a&key=b). */
    public static function repeatedQueryParam(Request $request, string $key): array
    {
        $values = [];
        foreach (explode('&', (string) $request->server('QUERY_STRING')) as $pair) {
            if ($pair === '') {
                continue;
            }
            [$name, $value] = array_pad(explode('=', $pair, 2), 2, '');
            $name = urldecode($name);
            if ($name === $key || $name === $key.'[]') {
                $values[] = urldecode($value);
            }
        }

        return $values;
    }
}
