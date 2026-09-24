<?php

namespace App\Services;

use App\Models\Student;
use Illuminate\Support\Facades\DB;

class StudentImportService
{
    private const FIELDS = [
        'instellingsnummer', 'naam', 'voornaam', 'klas', 'klascode',
        'klasnummer', 'gebruikersnaam', 'pointer', 'afkorting',
    ];

    /** De leerkrachten-export gebruikt licht afwijkende kolomnamen (genormaliseerde sleutels). */
    private const HEADER_ALIASES = [
        'instellingsnummers' => 'instellingsnummer',
        'klasnr' => 'klasnummer',
    ];

    /** Kolommen die nooit bewaard mogen worden (paswoorden, betaalkaart, PIN). Expliciet, niet toevallig. */
    private const IGNORED_COLUMNS = ['standaardpaswoord', 'betaalkaart', 'pincode'];

    private const DELIMITERS = [';', "\t", ','];

    /** Kies het scheidingsteken dat de kopregel in de meeste kolommen splitst. */
    public static function sniffDelimiter(string $headerLine): string
    {
        $best = self::DELIMITERS[0];
        foreach (self::DELIMITERS as $delimiter) {
            if (substr_count($headerLine, $delimiter) > substr_count($headerLine, $best)) {
                $best = $delimiter;
            }
        }

        return $best;
    }

    /** Kopnamen normaliseren (kleine letters, getrimd, aliassen) en waarden trimmen. */
    private static function normalizeRow(array $row): array
    {
        $normalized = [];
        foreach ($row as $key => $value) {
            $name = mb_strtolower(trim((string) $key));
            $name = self::HEADER_ALIASES[$name] ?? $name;
            if (in_array($name, self::IGNORED_COLUMNS, true)) {
                continue;
            }
            $normalized[$name] = trim((string) ($value ?? ''));
        }

        return $normalized;
    }

    /**
     * CSV (puntkomma, tab of komma) inlezen en leerlingen upserten.
     *
     * Zet last_import op elk aangeraakt record zodat records die ontbreken in de meest
     * recente import van dezelfde groep als "Uitgeschreven" herkend worden.
     * Leerkrachten worden geïdentificeerd via Stamnummer of, als dat leeg is, via
     * Gebruikersnaam. Rijen waarvan de sleutel al tot de andere groep behoort,
     * worden overgeslagen en nooit omgezet.
     *
     * @return int aantal verwerkte records
     */
    public function importFromString(string $content, bool $isLeerkracht = false): int
    {
        $content = CsvReader::stripBom($content);
        if (trim($content) === '') {
            return 0;
        }
        $firstLine = preg_split('/\r\n|\r|\n/', $content, 2)[0];
        $rows = CsvReader::dictRows($content, self::sniffDelimiter($firstLine));
        $importTimestamp = now();
        $count = 0;

        DB::transaction(function () use ($rows, $isLeerkracht, $importTimestamp, &$count) {
            foreach ($rows as $rawRow) {
                $row = self::normalizeRow($rawRow);
                $stamnummer = $row['stamnummer'] ?? '';
                if ($stamnummer === '' && $isLeerkracht) {
                    $stamnummer = $row['gebruikersnaam'] ?? '';
                }
                if ($stamnummer === '') {
                    continue;
                }

                $student = Student::find($stamnummer);
                if ($student === null) {
                    $student = new Student(['stamnummer' => $stamnummer, 'is_leerkracht' => $isLeerkracht]);
                } elseif ((bool) $student->is_leerkracht !== $isLeerkracht) {
                    continue;
                }

                foreach (self::FIELDS as $field) {
                    $student->{$field} = $row[$field] ?? '';
                }
                $student->last_import = $importTimestamp;
                $student->save();
                $count++;
            }
        });

        return $count;
    }
}
