<?php

namespace App\Support;

use Symfony\Component\HttpFoundation\Response;

/**
 * CSV-uitvoer zoals Python's csv.writer (QUOTE_MINIMAL, regeleinde \r\n).
 */
class CsvWriter
{
    private array $lines = [];

    public function __construct(private readonly string $delimiter = ';') {}

    public function row(array $fields): void
    {
        $this->lines[] = implode($this->delimiter, array_map(function ($field) {
            $value = (string) ($field ?? '');
            if (strpbrk($value, $this->delimiter."\"\r\n") !== false) {
                return '"'.str_replace('"', '""', $value).'"';
            }

            return $value;
        }, $fields));
    }

    public function download(string $filename): Response
    {
        return response(implode("\r\n", $this->lines)."\r\n", 200, [
            'Content-Type' => 'text/csv; charset=utf-8',
            'Content-Disposition' => "attachment; filename={$filename}",
        ]);
    }
}
