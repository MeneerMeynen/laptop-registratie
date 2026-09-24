<?php

namespace App\Services;

/**
 * Minimale tegenhanger van Python's csv.DictReader.
 */
class CsvReader
{
    /**
     * Parse CSV-tekst naar een lijst associatieve rijen (sleutels = kolomkoppen).
     * Lege regels worden overgeslagen; ontbrekende velden worden null,
     * extra velden zonder kop worden genegeerd.
     *
     * @return list<array<string, string|null>>
     */
    public static function dictRows(string $content, string $delimiter): array
    {
        $content = self::stripBom($content);
        $stream = fopen('php://temp', 'r+');
        fwrite($stream, $content);
        rewind($stream);

        $header = null;
        $rows = [];
        while (($fields = fgetcsv($stream, null, $delimiter, '"', '')) !== false) {
            if ($fields === [null]) {
                continue; // lege regel
            }
            if ($header === null) {
                $header = $fields;

                continue;
            }
            $row = [];
            foreach ($header as $i => $name) {
                $row[$name] = $fields[$i] ?? null;
            }
            $rows[] = $row;
        }
        fclose($stream);

        return $rows;
    }

    public static function stripBom(string $content): string
    {
        return str_starts_with($content, "\xEF\xBB\xBF") ? substr($content, 3) : $content;
    }
}
